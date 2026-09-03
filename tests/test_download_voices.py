"""Tests for shared and atomic Piper voice downloads."""

import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List

import pytest

from piper.download_voices import (
    VoiceDownloadCircuitOpenError,
    VoiceDownloadUpstreamError,
    download_voice,
)

VOICE = "en_US-lessac-medium"


def _response_for(url: str) -> io.BytesIO:
    payload = b"config" if ".onnx.json" in url else b"model"
    return io.BytesIO(payload)


def test_same_voice_concurrent_downloads_fetch_each_artifact_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: List[str] = []
    calls_lock = threading.Lock()
    first_started = threading.Event()
    second_started = threading.Event()
    release_first = threading.Event()

    def fake_urlopen(url: str) -> io.BytesIO:
        with calls_lock:
            calls.append(url)
            call_number = len(calls)
        if call_number == 1:
            first_started.set()
        elif call_number == 2:
            second_started.set()
        assert release_first.wait(timeout=5)
        return _response_for(url)

    monkeypatch.setattr("piper.download_voices.urlopen", fake_urlopen)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(download_voice, VOICE, tmp_path)
        assert first_started.wait(timeout=5)
        second = executor.submit(download_voice, VOICE, tmp_path)
        time.sleep(0.2)
        assert not second_started.is_set()
        release_first.set()
        first.result(timeout=5)
        second.result(timeout=5)

    assert len(calls) == 2
    assert (tmp_path / f"{VOICE}.onnx").read_bytes() == b"model"
    assert (tmp_path / f"{VOICE}.onnx.json").read_bytes() == b"config"
    assert not list(tmp_path.glob("*.part"))


def test_different_voice_downloads_can_run_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_model_started = threading.Event()
    model_barrier = threading.Barrier(2)

    def fake_urlopen(url: str) -> io.BytesIO:
        if ".onnx.json" not in url:
            first_model_started.set()
            model_barrier.wait(timeout=5)
        return _response_for(url)

    monkeypatch.setattr("piper.download_voices.urlopen", fake_urlopen)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(download_voice, VOICE, tmp_path)
        assert first_model_started.wait(timeout=5)
        second = executor.submit(download_voice, "vi_VN-vais1000-medium", tmp_path)
        first.result(timeout=5)
        second.result(timeout=5)


def test_existing_voice_is_reused_and_force_redownload_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: List[str] = []

    def fake_urlopen(url: str) -> io.BytesIO:
        calls.append(url)
        return _response_for(url)

    monkeypatch.setattr("piper.download_voices.urlopen", fake_urlopen)
    download_voice(VOICE, tmp_path)
    download_voice(VOICE, tmp_path)
    assert len(calls) == 2

    download_voice(VOICE, tmp_path, force_redownload=True)
    assert len(calls) == 4


def test_failed_download_cleans_staging_files_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0
    monkeypatch.setattr("piper.download_voices.VOICE_DOWNLOAD_COOLDOWN_SECONDS", 0)

    def failing_urlopen(url: str) -> io.BytesIO:
        nonlocal attempts
        attempts += 1
        if ".onnx.json" in url:
            raise OSError("upstream unavailable")
        return _response_for(url)

    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    with pytest.raises(OSError, match="upstream unavailable"):
        download_voice(VOICE, tmp_path)

    assert not (tmp_path / f"{VOICE}.onnx").exists()
    assert not (tmp_path / f"{VOICE}.onnx.json").exists()
    assert not list(tmp_path.glob("*.part"))

    monkeypatch.setattr("piper.download_voices.urlopen", _response_for)
    download_voice(VOICE, tmp_path)
    assert attempts == 2
    assert (tmp_path / f"{VOICE}.onnx").exists()
    assert (tmp_path / f"{VOICE}.onnx.json").exists()


def test_failed_owner_fans_out_to_waiting_callers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    first_started = threading.Event()
    release_first = threading.Event()

    def failing_urlopen(url: str) -> io.BytesIO:
        calls.append(url)
        first_started.set()
        assert release_first.wait(timeout=5)
        raise OSError("upstream unavailable")

    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(download_voice, VOICE, tmp_path)
        assert first_started.wait(timeout=5)
        second = executor.submit(download_voice, VOICE, tmp_path)
        release_first.set()
        with pytest.raises(VoiceDownloadUpstreamError, match="upstream unavailable"):
            first.result(timeout=5)
        with pytest.raises(VoiceDownloadCircuitOpenError):
            second.result(timeout=5)

    assert len(calls) == 1


def test_open_circuit_skips_upstream_until_cooldown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    monkeypatch.setattr("piper.download_voices.VOICE_DOWNLOAD_COOLDOWN_SECONDS", 30)

    def failing_urlopen(_url: str) -> io.BytesIO:
        nonlocal calls
        calls += 1
        raise OSError("upstream unavailable")

    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    with pytest.raises(VoiceDownloadUpstreamError):
        download_voice(VOICE, tmp_path)
    with pytest.raises(VoiceDownloadCircuitOpenError) as error:
        download_voice(VOICE, tmp_path)
    with pytest.raises(VoiceDownloadCircuitOpenError):
        download_voice(VOICE, tmp_path, force_redownload=True)

    assert calls == 1
    assert error.value.retry_after is not None
    assert error.value.retry_after > 0


def test_half_open_probe_recovers_and_clears_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("piper.download_voices.VOICE_DOWNLOAD_COOLDOWN_SECONDS", 0)
    calls = []

    def failing_urlopen(url: str) -> io.BytesIO:
        calls.append(url)
        raise OSError("temporary outage")

    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    with pytest.raises(VoiceDownloadUpstreamError):
        download_voice(VOICE, tmp_path)

    monkeypatch.setattr("piper.download_voices.urlopen", _response_for)
    download_voice(VOICE, tmp_path)
    assert len(calls) == 1
    assert not (tmp_path / f".{VOICE}.download-state.json").exists()


def test_backoff_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from piper import download_voices

    monkeypatch.setattr(download_voices, "VOICE_DOWNLOAD_COOLDOWN_SECONDS", 30)
    monkeypatch.setattr(download_voices, "VOICE_DOWNLOAD_MAX_BACKOFF_SECONDS", 60)
    state_path = tmp_path / ".voice.download-state.json"
    error = VoiceDownloadUpstreamError("temporary outage")

    assert download_voices._record_transient_failure(state_path, 0, error) == 30
    assert download_voices._record_transient_failure(state_path, 1, error) == 60
    assert download_voices._record_transient_failure(state_path, 2, error) == 60


def test_invalid_voice_does_not_create_breaker_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="did not match pattern"):
        download_voice("not-a-voice", tmp_path)

    assert not list(tmp_path.glob("*download-state.json"))
