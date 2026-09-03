"""Command-line utility for downloading Piper voices."""

import argparse
import json
import logging
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from filelock import FileLock

URL_FORMAT = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang_family}/{lang_code}/{voice_name}/{voice_quality}/{lang_code}-{voice_name}-{voice_quality}{extension}?download=true"
VOICES_JSON = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json?download=true"
)
VOICE_PATTERN = re.compile(
    r"^(?P<lang_family>[^-]+)_(?P<lang_region>[^-]+)-(?P<voice_name>[^-]+)-(?P<voice_quality>.+)$"
)

_LOGGER = logging.getLogger(__name__)

VOICE_DOWNLOAD_COOLDOWN_SECONDS = 30
VOICE_DOWNLOAD_MAX_BACKOFF_SECONDS = 5 * 60
_MAX_FAILURE_MESSAGE_LENGTH = 240


class VoiceDownloadError(OSError):
    """Base error for download failures exposed by the HTTP server."""

    status_code = 500
    error_code = "download_failed"

    def __init__(self, message: str, *, retry_after: Optional[int] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class VoiceDownloadUpstreamError(VoiceDownloadError):
    """A transient failure while contacting or reading the upstream source."""

    status_code = 502
    error_code = "voice_download_upstream_failed"


class VoiceDownloadCircuitOpenError(VoiceDownloadError):
    """A voice download is temporarily blocked by its circuit breaker."""

    status_code = 503
    error_code = "voice_download_circuit_open"


class VoiceDownloadPermanentError(ValueError):
    """An upstream voice request is permanently invalid or unavailable."""

    status_code = 404
    error_code = "voice_not_found"


def main() -> None:
    """Download Piper voices."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "voice", nargs="*", help="Name of voice like 'en_US-lessac-medium'"
    )
    parser.add_argument(
        "--download-dir",
        "--download_dir",
        "--data-dir",
        "--data_dir",
        help="Directory to download voices into (default: current directory)",
    )
    parser.add_argument(
        "--force-redownload",
        "--force_redownload",
        action="store_true",
        help="Force redownloading of voice files even if they exist already",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG logs to console"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if not args.voice:
        list_voices()
        return

    if args.download_dir:
        download_dir = Path(args.download_dir)
    else:
        download_dir = Path.cwd()

    download_dir.mkdir(parents=True, exist_ok=True)

    for voice in args.voice:
        download_voice(voice, download_dir, force_redownload=args.force_redownload)


# -----------------------------------------------------------------------------


def list_voices() -> None:
    """List available voices and exit."""
    _LOGGER.debug("Downloading voices.json file: '%s'", VOICES_JSON)
    with urlopen(VOICES_JSON) as response:
        voices_dict = json.load(response)

    for voice in sorted(voices_dict.keys()):
        print(voice)


def download_voice(
    voice: str, download_dir: Path, force_redownload: bool = False
) -> None:
    """Download a voice model and config file to a directory."""
    voice = voice.strip()
    voice_match = VOICE_PATTERN.match(voice)
    if not voice_match:
        raise ValueError(
            f"Voice '{voice}' did not match pattern: <language>-<name>-<quality> like 'en_US-lessac-medium'",
        )

    lang_family = voice_match.group("lang_family")
    lang_code = lang_family + "_" + voice_match.group("lang_region")
    voice_name = voice_match.group("voice_name")
    voice_quality = voice_match.group("voice_quality")

    voice_code = f"{lang_code}-{voice_name}-{voice_quality}"
    format_args = {
        "lang_family": lang_family,
        "lang_code": lang_code,
        "voice_name": voice_name,
        "voice_quality": voice_quality,
    }

    download_dir.mkdir(parents=True, exist_ok=True)
    model_path = download_dir / f"{voice_code}.onnx"
    config_path = download_dir / f"{voice_code}.onnx.json"

    lock_path = download_dir / f".{voice_code}.download.lock"
    state_path = _breaker_state_path(download_dir, voice_code)
    state = _read_breaker_state(state_path)
    if _circuit_is_open(state):
        raise _circuit_open_error(state)

    with FileLock(str(lock_path)):
        state = _read_breaker_state(state_path)
        if _circuit_is_open(state):
            raise _circuit_open_error(state)

        failure_count = _failure_count(state)
        if state and state.get("state") in {"open", "half-open"}:
            _write_breaker_state(
                state_path,
                {
                    "state": "half-open",
                    "failure_count": failure_count,
                    "probe_started_at": time.time(),
                },
            )

        if not force_redownload and _is_complete_voice(model_path, config_path):
            _clear_breaker_state(state_path)
            _LOGGER.debug("Voice already downloaded: '%s'", voice)
            return

        temporary_files = []
        try:
            if force_redownload or _needs_download(model_path):
                model_url = URL_FORMAT.format(extension=".onnx", **format_args)
                _LOGGER.debug(
                    "Downloading model from '%s' to '%s'", model_url, model_path
                )
                temporary_files.append(
                    (
                        _download_to_temporary_file(model_url, model_path),
                        model_path,
                    )
                )

            if force_redownload or _needs_download(config_path):
                config_url = URL_FORMAT.format(extension=".onnx.json", **format_args)
                _LOGGER.debug(
                    "Downloading config from '%s' to '%s'", config_url, config_path
                )
                temporary_files.append(
                    (
                        _download_to_temporary_file(config_url, config_path),
                        config_path,
                    )
                )

            for temporary_path, final_path in temporary_files:
                os.replace(temporary_path, final_path)
                _LOGGER.debug("Downloaded: '%s'", final_path)
        except VoiceDownloadPermanentError:
            _clear_breaker_state(state_path)
            raise
        except VoiceDownloadUpstreamError as err:
            retry_after = _record_transient_failure(state_path, failure_count, err)
            err.retry_after = retry_after
            raise
        except OSError as err:
            upstream_error = VoiceDownloadUpstreamError(
                f"Voice download failed: {_safe_error_message(err)}"
            )
            retry_after = _record_transient_failure(
                state_path, failure_count, upstream_error
            )
            upstream_error.retry_after = retry_after
            raise upstream_error from err
        finally:
            for temporary_path, _ in temporary_files:
                temporary_path.unlink(missing_ok=True)

        _clear_breaker_state(state_path)

    _LOGGER.info("Downloaded: %s", voice)


def _download_to_temporary_file(url: str, destination: Path) -> Path:
    """Download one artifact to a temporary file beside its final path."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".part",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            try:
                with urlopen(url) as response:
                    shutil.copyfileobj(response, temporary_file)
            except (HTTPError, URLError, TimeoutError, OSError) as err:
                _raise_classified_upstream_error(err)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            if temporary_file.tell() == 0:
                raise VoiceDownloadUpstreamError(
                    "Voice download upstream returned an empty artifact"
                )

        return temporary_path
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _is_complete_voice(model_path: Path, config_path: Path) -> bool:
    """Return True when both artifacts are present and non-empty."""
    return not _needs_download(model_path) and not _needs_download(config_path)


def _breaker_state_path(download_dir: Path, voice_code: str) -> Path:
    """Return the shared circuit-breaker state path for one voice."""
    return download_dir / f".{voice_code}.download-state.json"


def _read_breaker_state(state_path: Path) -> Optional[Dict[str, Any]]:
    """Read breaker state without exposing a partially written state file."""
    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def _write_breaker_state(state_path: Path, state: Dict[str, Any]) -> None:
    """Atomically publish a breaker state record."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".part",
            encoding="utf-8",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(state, temporary_file, separators=(",", ":"))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, state_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _clear_breaker_state(state_path: Path) -> None:
    """Remove a breaker state after a successful or permanent result."""
    state_path.unlink(missing_ok=True)


def _failure_count(state: Optional[Dict[str, Any]]) -> int:
    """Return a safe non-negative failure count from persisted state."""
    if not state:
        return 0
    try:
        return max(0, int(state.get("failure_count", 0)))
    except (TypeError, ValueError):
        return 0


def _circuit_is_open(state: Optional[Dict[str, Any]]) -> bool:
    """Return whether the cooldown still blocks a new download attempt."""
    if not state or state.get("state") != "open":
        return False
    try:
        return time.time() < float(state.get("retry_at", 0))
    except (TypeError, ValueError):
        return False


def _retry_after_seconds(state: Dict[str, Any]) -> int:
    """Return a positive Retry-After value for a persisted state."""
    try:
        remaining = float(state.get("retry_at", time.time())) - time.time()
    except (TypeError, ValueError):
        remaining = 0
    return max(1, int(math.ceil(remaining)))


def _circuit_open_error(
    state: Optional[Dict[str, Any]]
) -> VoiceDownloadCircuitOpenError:
    """Build the shared error returned while a voice circuit is open."""
    state = state or {}
    retry_after = _retry_after_seconds(state)
    message = str(state.get("message") or "Voice download is temporarily unavailable")
    return VoiceDownloadCircuitOpenError(message, retry_after=retry_after)


def _record_transient_failure(
    state_path: Path, previous_failure_count: int, error: VoiceDownloadError
) -> int:
    """Persist an open circuit and return its bounded next retry delay."""
    failure_count = previous_failure_count + 1
    retry_after = min(
        VOICE_DOWNLOAD_MAX_BACKOFF_SECONDS,
        VOICE_DOWNLOAD_COOLDOWN_SECONDS * (2 ** (failure_count - 1)),
    )
    _write_breaker_state(
        state_path,
        {
            "state": "open",
            "failure_count": failure_count,
            "message": _safe_error_message(error),
            "retry_at": time.time() + retry_after,
        },
    )
    return retry_after


def _raise_classified_upstream_error(error: BaseException) -> None:
    """Raise a stable error category for an upstream failure."""
    if isinstance(error, HTTPError) and 400 <= error.code < 500 and error.code != 429:
        raise VoiceDownloadPermanentError(
            f"Voice download upstream returned HTTP {error.code}"
        ) from error

    if isinstance(error, HTTPError):
        message = f"Voice download upstream returned HTTP {error.code}"
    else:
        message = f"Voice download upstream failed: {_safe_error_message(error)}"
    raise VoiceDownloadUpstreamError(message) from error


def _safe_error_message(error: BaseException) -> str:
    """Bound and redact error text before persisting or returning it."""
    message = " ".join(str(error).split())
    message = re.sub(r"https?://\S+", "<upstream>", message)
    return message[:_MAX_FAILURE_MESSAGE_LENGTH] or "unknown upstream error"


def _needs_download(path: Path) -> bool:
    """Return True if file needs to be downloaded."""
    if not path.exists():
        return True

    if path.stat().st_size == 0:
        # Empty
        return True

    return False


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
