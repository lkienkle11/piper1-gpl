"""Flask web server with HTTP API for Piper."""

import argparse
import io
import json
import logging
import time
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional
from urllib.request import urlopen

from flask import Flask, Response, jsonify, render_template, request

from . import PiperVoice, SynthesisConfig
from .download_voices import (
    VOICES_JSON,
    VoiceDownloadCircuitOpenError,
    VoiceDownloadPermanentError,
    VoiceDownloadUpstreamError,
    download_voice,
)
from .linguistic_analysis import StanzaLinguisticAnalyzer
from .prosody import ProsodyPlan, map_plan_to_segments, negotiate_prosody
from .semantic_analysis import (
    ExternalSemanticAnalyzer,
    LlamaCppSemanticProvider,
    SemanticAnalyzerConfig,
)
from .voice_selection import (
    EMOTION_VALUES,
    InvalidScriptError,
    TextAnalyzer,
    catalog_entry_from_config,
    normalize_selection,
    normalize_voice_catalog,
)

_LOGGER = logging.getLogger()
_CATALOG_TTL_SECONDS = 60 * 60


def _fetch_voice_catalog() -> Mapping[str, Mapping[str, Any]]:
    with urlopen(VOICES_JSON) as response:
        return json.load(response)


def _json_error(message: str, code: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": code, "message": message}), status


def _download_error(err: Any) -> tuple[Response, int]:
    """Return a stable download error and optional retry metadata."""
    retry_after = getattr(err, "retry_after", None)
    payload = {"error": err.error_code, "message": str(err)}
    if retry_after is not None:
        payload["retry_after"] = retry_after
    response = jsonify(payload)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response, err.status_code


def _invalid_script_error(err: InvalidScriptError) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "error": "invalid_script",
                "message": str(err),
                "line": err.line,
                "reason": err.reason,
            }
        ),
        400,
    )


def _synthesize_segments_wav(
    voice: PiperVoice,
    segments: List[Dict[str, Any]],
    config_for_segment: Callable[[Mapping[str, Any]], SynthesisConfig],
) -> tuple[bytes, List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Synthesize a complete WAV so failures can be returned as JSON."""
    phonemes: List[str] = []
    alignments: List[Dict[str, Any]] = []
    executed_segments: List[Dict[str, Any]] = []
    produced_audio = False

    with io.BytesIO() as wav_io:
        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        with wav_file:
            wav_file.setframerate(voice.config.sample_rate)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)

            for segment in segments:
                if segment["kind"] == "pause":
                    pause = float(segment["pause"])
                    wav_file.writeframes(
                        bytes(round(voice.config.sample_rate * pause) * 2)
                    )
                    executed_segments.append(dict(segment))
                    continue

                syn_config = config_for_segment(segment)
                segment_details = dict(segment)
                segment_details["prosody"] = {
                    "length_scale": syn_config.length_scale,
                    "noise_scale": syn_config.noise_scale,
                    "noise_w_scale": syn_config.noise_w_scale,
                }
                executed_segments.append(segment_details)
                for audio_chunk in voice.synthesize(
                    str(segment["text"]),
                    syn_config,
                    include_alignments=True,
                ):
                    produced_audio = True
                    wav_file.writeframes(audio_chunk.audio_int16_bytes)
                    phonemes.extend(audio_chunk.phonemes)
                    for alignment in audio_chunk.phoneme_alignments or []:
                        alignments.append(
                            {
                                "phoneme": alignment.phoneme,
                                "seconds": (
                                    alignment.num_samples / audio_chunk.sample_rate
                                ),
                            }
                        )

                pause_after = float(segment.get("pause_after", 0.0))
                if pause_after > 0:
                    wav_file.writeframes(
                        bytes(round(voice.config.sample_rate * pause_after) * 2)
                    )

        if not produced_audio:
            raise ValueError("Voice produced no audio")
        return wav_io.getvalue(), phonemes, alignments, executed_segments


def create_app(
    args: argparse.Namespace,
    model_path: Path,
    default_voice: PiperVoice,
    *,
    catalog_fetcher: Callable[[], Mapping[str, Mapping[str, Any]]] = (
        _fetch_voice_catalog
    ),
    voice_loader: Callable[..., PiperVoice] = PiperVoice.load,
) -> Flask:
    """Create the Piper HTTP application."""
    default_model_id = model_path.name.removesuffix(".onnx")
    loaded_voices: Dict[str, PiperVoice] = {default_model_id: default_voice}
    data_dirs = [Path(data_dir) for data_dir in args.data_dir]
    download_dir = Path(args.download_dir)
    if download_dir not in data_dirs:
        data_dirs.append(download_dir)

    app = Flask(__name__, static_folder="img", static_url_path="/img")
    last_synthesis: Dict[str, Any] = {}
    analyzer = TextAnalyzer()
    semantic_settings = dict(getattr(args, "semantic_config", {}) or {})
    semantic_settings.setdefault(
        "linguistic_enabled", not bool(getattr(args, "disable_linguistic", False))
    )
    semantic_settings.setdefault(
        "linguistic_model_dir", getattr(args, "linguistic_model_dir", None)
    )
    semantic_settings.setdefault(
        "linguistic_use_gpu", bool(getattr(args, "cuda", False))
    )
    semantic_settings.setdefault(
        "enabled", bool(getattr(args, "semantic_enable", False))
    )
    semantic_settings.setdefault("endpoint", getattr(args, "semantic_endpoint", None))
    semantic_settings.setdefault(
        "timeout_seconds", getattr(args, "semantic_timeout", None)
    )
    semantic_settings.setdefault(
        "max_text_length", getattr(args, "semantic_max_text_length", None)
    )
    semantic_settings.setdefault(
        "allow_external_endpoint",
        bool(getattr(args, "semantic_allow_external_endpoint", False)),
    )
    if getattr(args, "semantic_disable_privacy", False):
        semantic_settings["privacy_mode"] = False
    semantic_settings = {
        key: value for key, value in semantic_settings.items() if value is not None
    }
    semantic_config = SemanticAnalyzerConfig.from_mapping(semantic_settings)
    analyzer.set_linguistic_analyzer(
        StanzaLinguisticAnalyzer(
            model_dir=semantic_config.linguistic_model_dir,
            use_gpu=semantic_config.linguistic_use_gpu,
            enabled=semantic_config.linguistic_enabled,
        )
    )
    if semantic_config.enabled:
        analyzer.set_semantic_analyzer(
            ExternalSemanticAnalyzer(
                LlamaCppSemanticProvider(
                    semantic_config.endpoint,
                    timeout_seconds=semantic_config.timeout_seconds,
                    max_text_length=semantic_config.max_text_length,
                    allow_external_endpoint=semantic_config.allow_external_endpoint,
                ),
                timeout_seconds=semantic_config.timeout_seconds,
                supported_languages=set(semantic_config.supported_languages),
                max_text_length=semantic_config.max_text_length,
            )
        )
    catalog_cache: Dict[str, Any] = {
        "loaded_at": 0.0,
        "voices": {},
        "error": None,
    }

    def get_installed_configs() -> Dict[str, Dict[str, Any]]:
        config_paths = [Path(f"{model_path}.json")]
        for data_dir in data_dirs:
            for onnx_path in data_dir.glob("*.onnx"):
                config_path = Path(f"{onnx_path}.json")
                if config_path.exists():
                    config_paths.append(config_path)

        installed: Dict[str, Dict[str, Any]] = {}
        for config_path in config_paths:
            model_id = config_path.name.removesuffix(".onnx.json")
            if model_id in installed or not config_path.exists():
                continue

            with open(config_path, "r", encoding="utf-8") as config_file:
                installed[model_id] = json.load(config_file)

        return installed

    def get_catalog() -> tuple[List[Dict[str, Any]], bool, Optional[str]]:
        installed_configs = get_installed_configs()
        installed_ids = set(installed_configs)
        now = time.monotonic()
        if (
            not catalog_cache["voices"]
            or (now - catalog_cache["loaded_at"]) >= _CATALOG_TTL_SECONDS
        ):
            try:
                catalog_cache["voices"] = dict(catalog_fetcher())
                catalog_cache["loaded_at"] = now
                catalog_cache["error"] = None
            except Exception as err:  # network errors must not hide installed voices
                _LOGGER.warning("Unable to load voice catalog: %s", err)
                catalog_cache["loaded_at"] = now
                catalog_cache["error"] = str(err)

        raw_catalog = catalog_cache["voices"]
        voices = normalize_voice_catalog(raw_catalog, installed_ids)
        known_ids = {voice["key"] for voice in voices}
        for model_id, config in installed_configs.items():
            if model_id not in known_ids:
                voices.append(catalog_entry_from_config(model_id, config))

        voices.sort(
            key=lambda voice: (
                voice["language"]["name_english"],
                voice["language"]["code"],
                voice["name"],
                voice["quality"],
                voice["key"],
            )
        )
        return voices, bool(raw_catalog), catalog_cache["error"]

    def analyze_text(
        text: str,
        *,
        delivery: str = "adaptive",
        voice_speed: float = 1.0,
        manual_voice_id: Optional[str] = None,
        emotion: str = "auto",
        language_code: Optional[str] = None,
        voice_family_id: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> Dict[str, Any]:
        voices, catalog_available, catalog_error = get_catalog()
        result = analyzer.analyze(
            text,
            voices,
            default_model_id,
            delivery=delivery,
            voice_speed=voice_speed,
            manual_voice_id=manual_voice_id,
            emotion=emotion,
            language_code=language_code,
            voice_family_id=voice_family_id,
            quality=quality,
        )
        result["catalog_available"] = catalog_available
        result["catalog_error"] = catalog_error
        return result

    def find_model(model_id: str) -> Optional[Path]:
        if model_id == default_model_id:
            return model_path

        for data_dir in data_dirs:
            maybe_model_path = data_dir / f"{model_id}.onnx"
            if maybe_model_path.exists() and Path(f"{maybe_model_path}.json").exists():
                return maybe_model_path

        return None

    @app.route("/", methods=["GET"])
    def app_index() -> str:
        """Web page for testing voices in the browser."""
        return render_template("index.html")

    @app.route("/info", methods=["GET"])
    def app_info() -> Dict[str, Any]:
        """Return default voice and most recent synthesis information."""
        return {
            "voice": {
                "name": default_model_id,
                "language": default_voice.config.espeak_voice,
                "num_speakers": default_voice.config.num_speakers,
            },
            "last": last_synthesis or None,
        }

    @app.route("/voices", methods=["GET"])
    def app_voices() -> Dict[str, Any]:
        """List downloaded voice configuration files."""
        return get_installed_configs()

    @app.route("/all-voices", methods=["GET"])
    def app_all_voices() -> Any:
        """List all voices from the Piper catalog."""
        try:
            voices = dict(catalog_fetcher())
            catalog_cache.update(loaded_at=time.monotonic(), voices=voices, error=None)
            return voices
        except Exception as err:
            _LOGGER.warning("Unable to load voice catalog: %s", err)
            return _json_error(str(err), "catalog_unavailable", 503)

    @app.route("/voice-catalog", methods=["GET"])
    def app_voice_catalog() -> Dict[str, Any]:
        """Return normalized catalog and local installation status."""
        voices, available, error = get_catalog()
        return {
            "voices": voices,
            "catalog_available": available,
            "catalog_error": error,
        }

    @app.route("/analyze", methods=["POST"])
    def app_analyze() -> Any:
        """Analyze text and resolve an automatic voice/prosody profile."""
        data = request.get_json(silent=True) or {}
        text = str(data.get("text", "")).strip()
        if not text:
            return _json_error("No text provided", "invalid_text", 400)

        unified_selection = None
        if "selection" in data:
            try:
                unified_selection = normalize_selection(data.get("selection"))
            except ValueError as err:
                return _json_error(str(err), "invalid_selection", 400)

        mode = data.get("mode", "auto") if unified_selection is None else "unified"
        if unified_selection is None and mode not in ("auto", "manual"):
            return _json_error("mode must be auto or manual", "invalid_mode", 400)
        manual_voice_id: Optional[str] = None
        if mode == "manual":
            manual_voice_id = str(data.get("voice", "")).strip()
            if not manual_voice_id:
                return _json_error(
                    "voice is required in manual mode", "invalid_voice", 400
                )

        emotion = (
            unified_selection["emotion"]
            if unified_selection is not None
            else str(data.get("emotion", "auto")).strip().casefold()
        )
        if emotion not in EMOTION_VALUES:
            choices = ", ".join(sorted(EMOTION_VALUES))
            return _json_error(
                f"emotion must be one of: {choices}", "invalid_emotion", 400
            )

        try:
            return analyze_text(
                text,
                delivery=str(data.get("delivery", "adaptive")),
                voice_speed=float(data.get("voice_speed", 1.0)),
                manual_voice_id=manual_voice_id,
                emotion=emotion,
                language_code=(
                    None
                    if unified_selection is None
                    or unified_selection["language"] == "auto"
                    else unified_selection["language"]
                ),
                voice_family_id=(
                    None
                    if unified_selection is None or unified_selection["voice"] == "auto"
                    else unified_selection["voice"]
                ),
                quality=(
                    None
                    if unified_selection is None
                    or unified_selection["quality"] == "auto"
                    else unified_selection["quality"]
                ),
            )
        except InvalidScriptError as err:
            return _invalid_script_error(err)
        except (TypeError, ValueError) as err:
            return _json_error(str(err), "analysis_failed", 400)

    @app.route("/download", methods=["POST"])
    def app_download() -> Any:
        """Download a voice model and configuration file."""
        data = request.get_json(silent=True) or {}
        model_id = str(data.get("voice", "")).strip()
        if not model_id:
            return _json_error("voice is required", "invalid_voice", 400)

        try:
            download_voice(
                model_id,
                download_dir,
                force_redownload=bool(data.get("force_redownload", False)),
            )
        except (VoiceDownloadCircuitOpenError, VoiceDownloadUpstreamError) as err:
            return _download_error(err)
        except VoiceDownloadPermanentError as err:
            return _download_error(err)
        except ValueError as err:
            return _json_error(str(err), "download_failed", 400)
        except OSError as err:
            return _json_error(str(err), "download_failed", 500)

        return model_id

    @app.route("/synthesize", methods=["POST"])
    def app_synthesize() -> Any:
        """Synthesize audio with legacy, automatic, or manual voice selection."""
        data = request.get_json(silent=True) or {}
        unified_selection = None
        if "selection" in data:
            try:
                unified_selection = normalize_selection(data.get("selection"))
            except ValueError as err:
                return _json_error(str(err), "invalid_selection", 400)

        mode = "unified" if unified_selection is not None else data.get("mode")
        if unified_selection is None and mode not in (None, "auto", "manual"):
            return _json_error("mode must be auto or manual", "invalid_mode", 400)

        text = str(data.get("text", "")).strip()
        if not text:
            if mode is None:
                raise ValueError("No text provided")
            return _json_error("No text provided", "invalid_text", 400)

        delivery = str(
            data.get(
                "delivery",
                "adaptive" if mode in ("auto", "manual", "unified") else "fixed",
            )
        )
        try:
            voice_speed = float(data.get("voice_speed", 1.0))
        except (TypeError, ValueError):
            return _json_error("voice_speed must be a number", "analysis_failed", 400)
        emotion = (
            unified_selection["emotion"]
            if unified_selection is not None
            else str(data.get("emotion", "auto")).strip().casefold()
        )
        if emotion not in EMOTION_VALUES:
            choices = ", ".join(sorted(EMOTION_VALUES))
            return _json_error(
                f"emotion must be one of: {choices}", "invalid_emotion", 400
            )

        analysis: Optional[Dict[str, Any]] = None
        if unified_selection is not None:
            try:
                analysis = analyze_text(
                    text,
                    delivery=delivery,
                    voice_speed=voice_speed,
                    emotion=emotion,
                    language_code=(
                        None
                        if unified_selection["language"] == "auto"
                        else unified_selection["language"]
                    ),
                    voice_family_id=(
                        None
                        if unified_selection["voice"] == "auto"
                        else unified_selection["voice"]
                    ),
                    quality=(
                        None
                        if unified_selection["quality"] == "auto"
                        else unified_selection["quality"]
                    ),
                )
            except InvalidScriptError as err:
                return _invalid_script_error(err)
            except (TypeError, ValueError) as err:
                return _json_error(str(err), "analysis_failed", 400)

            selected_voice = analysis.get("voice")
            if not selected_voice:
                return _json_error(
                    "No voice is available for the configured selection",
                    "voice_unavailable",
                    400,
                )
            model_id = selected_voice["key"]
            if not selected_voice.get("installed"):
                return (
                    jsonify(
                        {
                            "error": "voice_not_installed",
                            "message": f"Voice '{model_id}' must be downloaded before synthesis",
                            "voice": selected_voice,
                        }
                    ),
                    409,
                )
        elif mode == "auto":
            try:
                analysis = analyze_text(
                    text,
                    delivery=delivery,
                    voice_speed=voice_speed,
                    emotion=emotion,
                )
            except InvalidScriptError as err:
                return _invalid_script_error(err)
            except (TypeError, ValueError) as err:
                return _json_error(str(err), "analysis_failed", 400)

            selected_voice = analysis.get("voice")
            if not selected_voice:
                return _json_error(
                    "No voice is available for the detected language",
                    "voice_unavailable",
                    400,
                )

            model_id = selected_voice["key"]
            if not selected_voice.get("installed"):
                return (
                    jsonify(
                        {
                            "error": "voice_not_installed",
                            "message": (
                                f"Voice '{model_id}' must be downloaded before synthesis"
                            ),
                            "voice": selected_voice,
                        }
                    ),
                    409,
                )
        elif mode == "manual":
            model_id = str(data.get("voice", "")).strip()
            if not model_id:
                return _json_error(
                    "voice is required in manual mode", "invalid_voice", 400
                )
            try:
                analysis = analyze_text(
                    text,
                    delivery=delivery,
                    voice_speed=voice_speed,
                    manual_voice_id=model_id,
                    emotion=emotion,
                )
            except InvalidScriptError as err:
                return _invalid_script_error(err)
            except (TypeError, ValueError) as err:
                return _json_error(str(err), "analysis_failed", 400)
        else:
            model_id = str(data.get("voice", default_model_id))

        voice = loaded_voices.get(model_id)
        selected_model_path = find_model(model_id)
        if voice is None and selected_model_path is not None:
            _LOGGER.debug("Loading voice %s", model_id)
            voice = voice_loader(selected_model_path, use_cuda=args.cuda)
            loaded_voices[model_id] = voice

        if voice is None:
            if mode in ("auto", "manual", "unified"):
                return _json_error(
                    f"Voice '{model_id}' must be downloaded before synthesis",
                    "voice_not_installed",
                    409,
                )

            _LOGGER.warning("Voice not found: %s. Using default voice.", model_id)
            model_id = default_model_id
            voice = default_voice

        if analysis is None:
            try:
                analysis = analyze_text(
                    text,
                    delivery=delivery,
                    voice_speed=voice_speed,
                    manual_voice_id=model_id,
                    emotion=emotion,
                )
            except InvalidScriptError as err:
                return _invalid_script_error(err)
            except (TypeError, ValueError) as err:
                return _json_error(str(err), "analysis_failed", 400)

        if unified_selection is not None:
            selected_speaker = unified_selection["speaker"]
            speaker_id: Optional[int] = selected_speaker["id"]
            speaker = selected_speaker["name"]
        else:
            speaker_id = data.get("speaker_id")
            speaker = data.get("speaker")
        if (voice.config.num_speakers > 1) and (speaker_id is None):
            if speaker:
                speaker_id = voice.config.speaker_id_map.get(speaker)

            if speaker_id is None:
                if speaker:
                    _LOGGER.warning(
                        "Speaker not found: '%s' in %s",
                        speaker,
                        voice.config.speaker_id_map.keys(),
                    )
                speaker_id = args.speaker or voice.config.default_speaker_id

        if (speaker_id is not None) and (
            speaker_id < 0 or speaker_id >= voice.config.num_speakers
        ):
            speaker_id = voice.config.default_speaker_id

        segments = map_plan_to_segments(
            analysis["segments"], analysis.get("prosody_plan")
        )
        plan_data = analysis.get("prosody_plan")
        plan = (
            ProsodyPlan.from_dict(plan_data)
            if isinstance(plan_data, Mapping)
            else ProsodyPlan.empty(text, "")
        )
        execution = negotiate_prosody(plan)
        text_segment_indexes = [
            index for index, segment in enumerate(segments) if segment["kind"] == "text"
        ]
        if delivery == "fixed":
            for index in text_segment_indexes[:-1]:
                segments[index]["pause_after"] = float(args.sentence_silence)
        elif args.sentence_silence > 0:
            for index in text_segment_indexes[:-1]:
                segments[index]["pause_after"] = max(
                    float(segments[index].get("pause_after", 0.0)),
                    float(args.sentence_silence),
                )

        base_length_scale = (
            args.length_scale
            if args.length_scale is not None
            else voice.config.length_scale
        )
        base_noise_scale = (
            args.noise_scale
            if args.noise_scale is not None
            else voice.config.noise_scale
        )
        base_noise_w_scale = (
            args.noise_w_scale
            if args.noise_w_scale is not None
            else voice.config.noise_w_scale
        )

        def config_for_segment(segment: Mapping[str, Any]) -> SynthesisConfig:
            segment_prosody = dict(segment.get("prosody", {}))
            if delivery == "adaptive" or segment.get("emotion_override"):
                length_scale = segment_prosody.get("length_scale", base_length_scale)
                noise_scale = segment_prosody.get("noise_scale", base_noise_scale)
                noise_w_scale = segment_prosody.get("noise_w_scale", base_noise_w_scale)
            else:
                length_scale = base_length_scale / float(
                    segment.get("voice_speed", voice_speed)
                )
                noise_scale = base_noise_scale
                noise_w_scale = base_noise_w_scale

            return SynthesisConfig(
                speaker_id=speaker_id,
                length_scale=float(data.get("length_scale", length_scale)),
                noise_scale=float(data.get("noise_scale", noise_scale)),
                noise_w_scale=float(data.get("noise_w_scale", noise_w_scale)),
            )

        _LOGGER.debug(
            "Synthesizing text: '%s' with delivery=%s segments=%s",
            text,
            delivery,
            len(segments),
        )
        start_time = time.monotonic()
        try:
            wav_bytes, phonemes, alignments, executed_segments = (
                _synthesize_segments_wav(voice, segments, config_for_segment)
            )
        except ImportError as err:
            phoneme_type = getattr(
                voice.config.phoneme_type, "value", str(voice.config.phoneme_type)
            )
            extra = {"japanese": "ja", "pinyin": "zh"}.get(phoneme_type)
            install_hint = (
                f" Install Piper with the '{extra}' language extra."
                if extra
                else " Install the optional dependency required by this voice."
            )
            missing_package = getattr(err, "name", None) or "unknown"
            _LOGGER.exception(
                "Missing phonemizer dependency '%s' for voice %s",
                missing_package,
                model_id,
            )
            return _json_error(
                f"Voice '{model_id}' requires missing package "
                f"'{missing_package}'.{install_hint}",
                "phonemizer_dependency_missing",
                503,
            )
        except (OSError, RuntimeError, ValueError) as err:
            _LOGGER.exception("Synthesis failed for voice %s", model_id)
            return _json_error(str(err), "synthesis_failed", 500)

        first_text_segment = next(
            (segment for segment in executed_segments if segment.get("kind") == "text"),
            None,
        )
        synthesis_details: Dict[str, Any] = {
            "text": text,
            "synthesize_seconds": time.monotonic() - start_time,
            "phonemes": phonemes,
            "alignments": alignments,
            "mode": mode or "legacy",
            "voice": model_id,
            "speaker_id": speaker_id,
            "delivery": delivery,
            "voice_speed": voice_speed,
            "emotion_override": analysis.get("emotion_override"),
            "prosody": (
                first_text_segment["prosody"]
                if first_text_segment is not None
                else analysis["prosody"]
            ),
            "prosody_execution": execution.to_dict(),
            "segments": executed_segments,
        }
        synthesis_details.update(
            language=analysis["language"],
            context=analysis["context"],
            emotion=analysis["emotion"],
            fallback_reason=analysis["fallback_reason"],
        )

        last_synthesis.clear()
        last_synthesis.update(synthesis_details)
        return Response(wav_bytes, mimetype="audio/wav")

    return app


def main() -> None:
    """Run HTTP server."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="HTTP server host")
    parser.add_argument("--port", type=int, default=5000, help="HTTP server port")
    parser.add_argument("-m", "--model", required=True, help="Path to Onnx model file")
    parser.add_argument("-s", "--speaker", type=int, help="Id of speaker (default: 0)")
    parser.add_argument(
        "--length-scale", "--length_scale", type=float, help="Phoneme length"
    )
    parser.add_argument(
        "--noise-scale", "--noise_scale", type=float, help="Generator noise"
    )
    parser.add_argument(
        "--noise-w-scale",
        "--noise_w_scale",
        "--noise-w",
        "--noise_w",
        type=float,
        help="Phoneme width noise",
    )
    parser.add_argument("--cuda", action="store_true", help="Use GPU")
    parser.add_argument(
        "--sentence-silence",
        "--sentence_silence",
        type=float,
        default=0.0,
        help="Seconds of silence after each sentence",
    )
    parser.add_argument(
        "--data-dir",
        "--data_dir",
        action="append",
        default=[str(Path.cwd())],
        help="Data directory to check for downloaded models (default: current directory)",
    )
    parser.add_argument(
        "--download-dir",
        "--download_dir",
        help="Path to download voices (default: first data dir)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    parser.add_argument(
        "--disable-linguistic",
        action="store_true",
        help="Disable optional Stanza linguistic analysis",
    )
    parser.add_argument(
        "--linguistic-model-dir",
        help="Directory containing pre-installed Stanza resources",
    )
    parser.add_argument(
        "--semantic-enable",
        action="store_true",
        help="Enable the opt-in local llama.cpp semantic analyzer",
    )
    parser.add_argument(
        "--semantic-endpoint",
        default="http://127.0.0.1:8080/completion",
        help="Local llama.cpp completion endpoint",
    )
    parser.add_argument(
        "--semantic-timeout",
        type=float,
        default=1.0,
        help="Semantic provider timeout in seconds",
    )
    parser.add_argument(
        "--semantic-max-text-length",
        type=int,
        default=4000,
        help="Maximum characters sent to the semantic provider",
    )
    parser.add_argument(
        "--semantic-allow-external-endpoint",
        action="store_true",
        help="Allow a non-loopback semantic endpoint when privacy is disabled",
    )
    parser.add_argument(
        "--semantic-disable-privacy",
        action="store_true",
        help="Disable the loopback-only privacy policy for explicit deployments",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    if not args.download_dir:
        args.download_dir = args.data_dir[0]

    model_path = Path(args.model)
    if not model_path.exists():
        voice_name = args.model
        for data_dir in args.data_dir:
            maybe_model_path = Path(data_dir) / f"{voice_name}.onnx"
            _LOGGER.debug("Checking '%s'", maybe_model_path)
            if maybe_model_path.exists():
                model_path = maybe_model_path
                break

    if not model_path.exists():
        raise ValueError(
            f"Unable to find voice: {model_path} (use piper.download_voices)"
        )

    default_voice = PiperVoice.load(
        model_path, use_cuda=args.cuda, include_alignments=True
    )
    app = create_app(args, model_path, default_voice)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
