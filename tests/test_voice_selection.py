"""Tests for automatic text analysis and HTTP voice selection."""

from types import SimpleNamespace
from typing import Any, Dict, Iterable

import pytest

from piper.http_server import create_app
from piper.voice_selection import (
    InvalidScriptError,
    TextAnalyzer,
    classify_text,
    normalize_voice_catalog,
    parse_script,
    prosody_for,
    resolve_voice,
)


def _catalog_voice(
    key: str,
    family: str,
    code: str,
    name: str,
    quality: str,
    installed: bool,
) -> Dict[str, Any]:
    return {
        "key": key,
        "language": {
            "code": code,
            "family": family,
            "region": code.split("_")[-1],
            "name_native": family,
            "name_english": family,
            "country_english": "",
        },
        "name": name,
        "quality": quality,
        "num_speakers": 1,
        "speakers": {},
        "model_size_bytes": 10,
        "installed": installed,
    }


def test_classify_vietnamese_and_english() -> None:
    assert classify_text("Tuyệt quá, tôi rất vui!", "vi") == (
        "excited",
        "conversation",
    )
    assert classify_text("WHY IS THIS UNACCEPTABLE?!", "en") == (
        "angry",
        "question",
    )
    assert classify_text("A long factual passage about a quiet village.", "en") == (
        "neutral",
        "narration",
    )
    assert classify_text("Hello, this is a friendly conversation.", "en") == (
        "neutral",
        "conversation",
    )


def test_generic_language_uses_punctuation_and_neutral_fallback() -> None:
    assert classify_text("Bonjour, comment allez-vous?", "fr") == (
        "neutral",
        "question",
    )
    assert classify_text("Une phrase ordinaire.", "fr") == (
        "neutral",
        "narration",
    )


@pytest.mark.parametrize(
    ("emotion", "context", "length_scale"),
    [
        ("neutral", "conversation", 1.0),
        ("happy", "narration", 0.9975),
        ("sad", "question", 1.127),
        ("angry", "announcement", 0.828),
        ("excited", "conversation", 0.85),
    ],
)
def test_prosody_profiles(emotion: str, context: str, length_scale: float) -> None:
    prosody = prosody_for(emotion, context)
    assert prosody["length_scale"] == length_scale
    assert 0.45 <= prosody["noise_scale"] <= 0.85
    assert 0.6 <= prosody["noise_w_scale"] <= 1.0


def test_normalize_and_resolve_voice_priority() -> None:
    raw = {
        "en_GB-alan-low": {
            "key": "en_GB-alan-low",
            "language": {"code": "en_GB", "family": "en"},
            "name": "alan",
            "quality": "low",
            "num_speakers": 1,
            "speaker_id_map": {},
            "files": {"voice.onnx": {"size_bytes": 123}},
        },
        "en_US-lessac-medium": {
            "key": "en_US-lessac-medium",
            "language": {"code": "en_US", "family": "en"},
            "name": "lessac",
            "quality": "medium",
            "num_speakers": 1,
            "speaker_id_map": {},
            "files": {"voice.onnx": {"size_bytes": 456}},
        },
    }
    voices = normalize_voice_catalog(raw, {"en_GB-alan-low"})
    selected = resolve_voice("en", voices, "vi_VN-vivos-x_low")
    assert selected is not None
    assert selected["key"] == "en_GB-alan-low"
    assert selected["installed"] is True
    assert selected["model_size_bytes"] == 123

    selected = resolve_voice("en", voices, "en_GB-alan-low")
    assert selected is not None
    assert selected["key"] == "en_GB-alan-low"


def test_normalize_preserves_language_metadata_and_speaker_mapping() -> None:
    raw = {
        "en_GB-aru-medium": {
            "key": "en_GB-aru-medium",
            "language": {
                "code": "en_GB",
                "family": "en",
                "name_native": "English",
                "name_english": "English",
                "country_english": "Great Britain",
            },
            "name": "aru",
            "quality": "medium",
            "num_speakers": 2,
            "speaker_id_map": {"03": 0, "06": 1},
            "files": {"voice.onnx": {"size_bytes": 789}},
        }
    }

    voices = normalize_voice_catalog(raw, set())

    assert voices == [
        {
            "key": "en_GB-aru-medium",
            "language": {
                "code": "en_GB",
                "family": "en",
                "region": "",
                "name_native": "English",
                "name_english": "English",
                "country_english": "Great Britain",
            },
            "name": "aru",
            "quality": "medium",
            "num_speakers": 2,
            "speakers": {"03": 0, "06": 1},
            "model_size_bytes": 789,
            "installed": False,
        }
    ]
def test_resolver_prefers_configured_british_voice_before_installed_us() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True),
        _catalog_voice("en_GB-alan-medium", "en", "en_GB", "alan", "medium", True),
        _catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", False),
    ]
    selected = resolve_voice("en", voices, "en_US-lessac-medium")
    assert selected is not None
    assert selected["key"] == "en_GB-cori-high"
    assert selected["installed"] is False


def test_parse_script_directions_and_validation() -> None:
    segments = parse_script(
        "(voice-speed: fast)\n\nFirst sentence. Second sentence?\n\n"
        "(pause: 0.5)\n\n(narration-mode: fragment)\n\n"
        "[[wˈɒʃɪŋ ɐ kʌpɪnðə sˈɪŋk]]"
    )
    assert [segment.kind for segment in segments] == ["text", "text", "pause", "text"]
    assert segments[0].voice_speed == 1.15
    assert segments[1].paragraph_end
    assert segments[2].pause == 0.5
    assert segments[3].narration_mode == "fragment"
    assert "kʌpɪn" in segments[3].text

    with pytest.raises(InvalidScriptError, match="Line 1"):
        parse_script("(voice-speed: 3)")
    with pytest.raises(InvalidScriptError, match="unknown stage direction"):
        parse_script("(pitch: high)\n\nHello")


def test_parse_script_emotion_direction_is_stateful() -> None:
    segments = parse_script(
        "(emotion: sad)\n\nThis is the first paragraph.\n\n"
        "(emotion: auto)\n\nThis is the second paragraph."
    )
    assert [segment.emotion for segment in segments] == ["sad", "auto"]

    with pytest.raises(InvalidScriptError, match=r"Line 3: emotion must be"):
        parse_script("Hello.\n\n(emotion: dramatic)")


class _FakeIsoCode:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeDetectedLanguage:
    def __init__(self, name: str) -> None:
        self.iso_code_639_1 = _FakeIsoCode(name)


class _FakeDetector:
    def __init__(self, result: str, confidence: float) -> None:
        self.result = result
        self.confidence = confidence

    def compute_language_confidence_values(self, _text: str) -> Any:
        return [(_FakeDetectedLanguage(self.result), self.confidence)]


def test_analyzer_uses_dominant_language_and_short_text_fallback() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True),
        _catalog_voice("vi_VN-vivos-x_low", "vi", "vi_VN", "vivos", "x_low", True),
    ]
    analyzer = TextAnalyzer()
    analyzer._get_detector = lambda _families: _FakeDetector("VI", 0.91)
    result = analyzer.analyze(
        "Xin chào, hôm nay thật tuyệt!", voices, "en_US-lessac-medium"
    )
    assert result["language"]["family"] == "vi"
    assert result["voice"]["key"] == "vi_VN-vivos-x_low"
    assert result["emotion"] == "happy"
    assert result["segments"][0]["kind"] == "text"
    assert result["segments"][0]["pause_after"] == 0.0

    short_result = analyzer.analyze("Hi", voices, "en_US-lessac-medium")
    assert short_result["language"]["family"] == "en"
    assert short_result["fallback_reason"] == "text_too_short"


def test_analyzer_applies_adaptive_segments_and_manual_voice() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True),
        _catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True),
    ]
    analyzer = TextAnalyzer()
    result = analyzer.analyze(
        "Hello there.\n\nWhy now?",
        voices,
        "en_US-lessac-medium",
        manual_voice_id="en_GB-cori-high",
        delivery="adaptive",
        voice_speed=1.15,
    )
    text_segments = [item for item in result["segments"] if item["kind"] == "text"]
    assert result["voice"]["key"] == "en_GB-cori-high"
    assert text_segments[0]["pause_after"] == 0.3
    assert text_segments[1]["context"] == "question"
    assert text_segments[0]["prosody"]["length_scale"] < 1.0


@pytest.mark.parametrize("delivery", ["adaptive", "fixed"])
def test_analyzer_applies_manual_emotion_override(delivery: str) -> None:
    voices = [_catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True)]
    result = TextAnalyzer().analyze(
        "A quiet factual sentence.",
        voices,
        "en_GB-cori-high",
        manual_voice_id="en_GB-cori-high",
        delivery=delivery,
        emotion="sad",
    )
    segment = result["segments"][0]
    assert result["emotion"] == "sad"
    assert result["emotion_override"] == "sad"
    assert segment["emotion"] == "sad"
    assert segment["emotion_override"] == "sad"
    assert segment["prosody"]["length_scale"] > 1.0


def test_script_emotion_overrides_manual_default() -> None:
    voices = [_catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True)]
    result = TextAnalyzer().analyze(
        "(emotion: angry)\n\nA quiet factual sentence.",
        voices,
        "en_GB-cori-high",
        manual_voice_id="en_GB-cori-high",
        emotion="happy",
    )
    assert result["segments"][0]["emotion"] == "angry"
    assert result["segments"][0]["emotion_override"] == "angry"


class _FakeConfig:
    espeak_voice = "en-us"
    num_speakers = 1
    speaker_id_map: Dict[str, int] = {}
    default_speaker_id = 0
    length_scale = 1.0
    noise_scale = 0.667
    noise_w_scale = 0.8
    sample_rate = 22050


class _FakeChunk:
    sample_rate = 22050
    sample_width = 2
    sample_channels = 1
    audio_int16_bytes = b"\x00\x00" * 32
    phonemes = ["h", "i"]
    phoneme_alignments: Iterable[Any] = []


class _FakeVoice:
    config = _FakeConfig()

    def synthesize(self, *_args: Any, **_kwargs: Any) -> Iterable[_FakeChunk]:
        yield _FakeChunk()


@pytest.fixture()
def http_client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    model_path = tmp_path / "en_US-lessac-medium.onnx"
    model_path.write_bytes(b"model")
    (tmp_path / "en_US-lessac-medium.onnx.json").write_text(
        """{
          "audio": {"sample_rate": 22050, "quality": "medium"},
          "language": {"code": "en_US", "family": "en", "name_english": "English"},
          "dataset": "lessac", "num_speakers": 1, "speaker_id_map": {}
        }""",
        encoding="utf-8",
    )
    raw_catalog = {
        "en_US-lessac-medium": {
            "key": "en_US-lessac-medium",
            "language": {
                "code": "en_US",
                "family": "en",
                "name_english": "English",
            },
            "name": "lessac",
            "quality": "medium",
            "num_speakers": 1,
            "speaker_id_map": {},
            "files": {"voice.onnx": {"size_bytes": 10}},
        },
        "vi_VN-vivos-x_low": {
            "key": "vi_VN-vivos-x_low",
            "language": {
                "code": "vi_VN",
                "family": "vi",
                "name_english": "Vietnamese",
            },
            "name": "vivos",
            "quality": "x_low",
            "num_speakers": 1,
            "speaker_id_map": {},
            "files": {"voice.onnx": {"size_bytes": 10}},
        },
    }
    args = SimpleNamespace(
        data_dir=[str(tmp_path)],
        download_dir=str(tmp_path),
        cuda=False,
        speaker=0,
        length_scale=None,
        noise_scale=None,
        noise_w_scale=None,
        sentence_silence=0.0,
    )
    fake_analysis = {
        "language": {
            "family": "en",
            "code": "en_US",
            "name": "English",
            "confidence": 0.99,
        },
        "context": "conversation",
        "emotion": "neutral",
        "emotion_override": None,
        "voice": _catalog_voice(
            "en_US-lessac-medium", "en", "en_US", "lessac", "medium", True
        ),
        "prosody": prosody_for("neutral", "conversation"),
        "delivery": "adaptive",
        "voice_speed": 1.0,
        "segments": [
            {
                "kind": "text",
                "line": 1,
                "text": "Hello",
                "context": "fragment",
                "emotion": "neutral",
                "emotion_override": None,
                "voice_speed": 1.0,
                "narration_mode": "normal",
                "paragraph_end": True,
                "prosody": prosody_for("neutral", "conversation"),
                "pause_after": 0.0,
            }
        ],
        "installed": True,
        "needs_download": False,
        "fallback_reason": None,
    }

    def fake_analyze(_self: Any, text: str, *_args: Any, **kwargs: Any) -> Any:
        parse_script(text, float(kwargs.get("voice_speed", 1.0)))
        emotion = kwargs.get("emotion", "auto")
        result = {**fake_analysis, "segments": [dict(fake_analysis["segments"][0])]}
        if emotion != "auto":
            result["emotion"] = emotion
            result["emotion_override"] = emotion
            result["prosody"] = prosody_for(emotion, "conversation")
            result["segments"][0]["emotion"] = emotion
            result["segments"][0]["emotion_override"] = emotion
            result["segments"][0]["prosody"] = prosody_for(emotion, "conversation")
        return result

    monkeypatch.setattr(TextAnalyzer, "analyze", fake_analyze)
    app = create_app(
        args,
        model_path,
        _FakeVoice(),
        catalog_fetcher=lambda: raw_catalog,
        voice_loader=lambda *_args, **_kwargs: _FakeVoice(),
    )
    app.config["TESTING"] = True
    return app.test_client()


def test_http_catalog_analyze_and_synthesis_modes(http_client: Any) -> None:
    catalog_response = http_client.get("/voice-catalog")
    assert catalog_response.status_code == 200
    catalog = catalog_response.get_json()
    assert len(catalog["voices"]) == 2
    assert next(
        voice for voice in catalog["voices"] if voice["key"] == "en_US-lessac-medium"
    )["installed"]

    analysis_response = http_client.post("/analyze", json={"text": "Hello there"})
    assert analysis_response.status_code == 200
    assert analysis_response.get_json()["voice"]["key"] == "en_US-lessac-medium"

    legacy_response = http_client.post("/synthesize", json={"text": "Hello"})
    assert legacy_response.status_code == 200
    assert legacy_response.mimetype == "audio/wav"

    auto_response = http_client.post(
        "/synthesize", json={"text": "Hello", "mode": "auto"}
    )
    assert auto_response.status_code == 200
    assert http_client.get("/info").get_json()["last"]["mode"] == "auto"

    missing_response = http_client.post(
        "/synthesize",
        json={
            "text": "Xin chào",
            "mode": "manual",
            "voice": "vi_VN-vivos-x_low",
        },
    )
    assert missing_response.status_code == 409
    assert missing_response.get_json()["error"] == "voice_not_installed"


def test_http_manual_emotion_and_validation(
    http_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthesis_configs = []

    def capture_synthesis(
        _self: Any, _text: str, syn_config: Any, **_kwargs: Any
    ) -> Iterable[_FakeChunk]:
        synthesis_configs.append(syn_config)
        yield _FakeChunk()

    monkeypatch.setattr(_FakeVoice, "synthesize", capture_synthesis)
    response = http_client.post(
        "/synthesize",
        json={
            "text": "A quiet factual sentence.",
            "mode": "manual",
            "voice": "en_US-lessac-medium",
            "delivery": "fixed",
            "emotion": "sad",
        },
    )
    assert response.status_code == 200
    assert synthesis_configs[0].length_scale == 1.15
    last = http_client.get("/info").get_json()["last"]
    assert last["emotion"] == "sad"
    assert last["emotion_override"] == "sad"

    invalid = http_client.post(
        "/analyze",
        json={
            "text": "Hello",
            "mode": "manual",
            "voice": "en_US-lessac-medium",
            "emotion": "dramatic",
        },
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_emotion"


def test_http_reports_missing_phonemizer_dependency(
    http_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_phonemizer(*_args: Any, **_kwargs: Any) -> Any:
        raise ModuleNotFoundError("No module named 'pyopenjtalk'", name="pyopenjtalk")

    monkeypatch.setattr(_FakeConfig, "phoneme_type", "japanese", raising=False)
    monkeypatch.setattr(_FakeVoice, "synthesize", missing_phonemizer)

    response = http_client.post("/synthesize", json={"text": "こんにちは"})
    assert response.status_code == 503
    assert response.is_json
    result = response.get_json()
    assert result["error"] == "phonemizer_dependency_missing"
    assert "pyopenjtalk" in result["message"]
    assert "'ja' language extra" in result["message"]


def test_http_reports_invalid_script_with_line_number(http_client: Any) -> None:
    response = http_client.post(
        "/synthesize",
        json={
            "text": "Hello.\n\n(voice-speed: 3)",
            "mode": "auto",
        },
    )
    assert response.status_code == 400
    result = response.get_json()
    assert result["error"] == "invalid_script"
    assert result["line"] == 3
