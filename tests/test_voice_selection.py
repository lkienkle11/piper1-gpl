"""Tests for automatic text analysis and HTTP voice selection."""

import io
import json
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable

import pytest

from piper.download_voices import download_voice as real_download_voice
from piper.http_server import create_app
from piper.linguistic_analysis import LinguisticAnalysis
from piper.prosody import map_plan_to_segments
from piper.semantic_analysis import ExternalSemanticAnalyzer, SemanticAnalysis
from piper.voice_metadata import (
    VOICE_DISPLAY_METADATA,
    metadata_missing_for_catalog,
    voice_display_label,
)
from piper.voice_selection import (
    InvalidScriptError,
    TextAnalyzer,
    classify_text,
    normalize_selection,
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
        "voice_family_id": f"{code}-{name}",
        "display_name": name.title(),
        "display_traits": [family, "Single-speaker"],
        "speaker_label": "Speaker {ordinal}",
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
            "voice_family_id": "en_GB-aru",
            "display_name": "Aru",
            "display_traits": ["English", "Great Britain", "Multi-speaker"],
            "speaker_label": "Speaker {ordinal}",
            "quality": "medium",
            "num_speakers": 2,
            "speakers": {"03": 0, "06": 1},
            "model_size_bytes": 789,
            "installed": False,
        }
    ]


def test_voice_display_metadata_covers_catalog_snapshot() -> None:
    snapshot_path = Path(__file__).with_name("voice_catalog_snapshot.json")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    catalog = {entry["key"]: entry for entry in snapshot}
    assert len(VOICE_DISPLAY_METADATA) == 153
    assert metadata_missing_for_catalog(catalog) == []

    for entry in snapshot:
        voice = dict(entry)
        labels = {
            voice_display_label(
                voice, speaker_id=speaker_id, speaker_ordinal=speaker_id
            )
            for speaker_id in range(int(entry["num_speakers"]))
        }
        assert len(labels) == int(entry["num_speakers"])
        assert all("(" in label and ")" in label for label in labels)


def test_selection_normalization_and_neutral_unknown_voice_labels() -> None:
    selection = normalize_selection(
        {
            "language": "en_US",
            "voice": "en_US-unknown",
            "quality": "medium",
            "speaker": {"id": 2},
            "emotion": "happy",
        }
    )
    assert selection["voice"] == "en_US-unknown"
    assert selection["speaker"]["id"] == 2

    voice = _catalog_voice(
        "xx_XX-corpus-medium", "xx", "xx_XX", "corpus", "medium", True
    )
    voice["num_speakers"] = 2
    label = voice_display_label(voice, speaker_id=0, speaker_ordinal=0)
    assert label == "Corpus Speaker 1 (xx, Multi-speaker)"
    assert "0" not in label


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


def test_resolver_applies_language_voice_and_quality_constraints_independently() -> (
    None
):
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True),
        _catalog_voice("en_US-lessac-high", "en", "en_US", "lessac", "high", True),
        _catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True),
    ]
    selected = resolve_voice(
        "en",
        voices,
        "en_US-lessac-medium",
        language_code="en_US",
        quality="high",
    )
    assert selected is not None
    assert selected["key"] == "en_US-lessac-high"

    result = TextAnalyzer().analyze(
        "Hello there.",
        voices,
        "en_US-lessac-medium",
        language_code="en_US",
        voice_family_id="en_US-lessac",
        quality="high",
    )
    assert result["voice"]["key"] == "en_US-lessac-high"


def test_normalize_selection_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="selection.quality"):
        normalize_selection({"quality": "ultra"})
    with pytest.raises(ValueError, match="selection.speaker.id"):
        normalize_selection({"speaker": {"id": -1}})


def test_analyzer_rejects_incompatible_explicit_dimensions() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True)
    ]
    with pytest.raises(ValueError, match="not available for language"):
        TextAnalyzer().analyze(
            "Hello there.",
            voices,
            "en_US-lessac-medium",
            language_code="vi_VN",
            voice_family_id="en_US-lessac",
        )
    with pytest.raises(ValueError, match="at quality high"):
        TextAnalyzer().analyze(
            "Hello there.",
            voices,
            "en_US-lessac-medium",
            language_code="en_US",
            quality="high",
        )


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


def test_analyzer_composes_local_structure_provider_and_linguistic_metadata() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True)
    ]

    class FakeLinguisticAnalyzer:
        def analyze(self, text: str, language: str) -> LinguisticAnalysis:
            return LinguisticAnalysis(
                text=text,
                language=language,
                sentences=({"text": "Are you ready?", "tokens": []},),
                source="stanza",
            )

    analyzer = TextAnalyzer()
    analyzer.set_linguistic_analyzer(FakeLinguisticAnalyzer())  # type: ignore[arg-type]
    analyzer.set_semantic_analyzer(
        ExternalSemanticAnalyzer(
            lambda _text, _language: {
                "context": "announcement",
                "intent": "statement",
                "emotion": "happy",
                "events": [
                    {
                        "kind": "pitch",
                        "dimension": "pitch",
                        "value": 0.5,
                        "text_start": 0,
                        "text_end": 3,
                        "confidence": 0.8,
                    }
                ],
            }
        )
    )

    result = analyzer.analyze(
        "Are you ready?\n\nYes.",
        voices,
        "en_US-lessac-medium",
        language_code="en_US",
    )

    assert result["linguistic"]["text"] == "Are you ready?\n\nYes."
    assert result["segments"][0]["context"] == "question"
    assert result["segments"][0]["emotion"] == "happy"
    assert result["prosody_plan"]["intent"] == "statement"
    assert result["prosody_plan"]["events"][0]["supported"] is False


def test_explicit_script_emotion_is_not_overridden_by_provider() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True)
    ]
    analyzer = TextAnalyzer()
    analyzer.set_semantic_analyzer(
        ExternalSemanticAnalyzer(
            lambda _text, _language: {
                "context": "announcement",
                "intent": "statement",
                "emotion": "happy",
                "events": [],
            }
        )
    )

    result = analyzer.analyze(
        "(emotion: sad)\n\nThis is explicit.",
        voices,
        "en_US-lessac-medium",
        language_code="en_US",
    )

    assert result["segments"][0]["emotion"] == "sad"


def test_disabling_provider_rolls_back_to_local_analysis() -> None:
    voices = [
        _catalog_voice("en_US-lessac-medium", "en", "en_US", "lessac", "medium", True)
    ]
    analyzer = TextAnalyzer()
    analyzer.set_semantic_analyzer(
        ExternalSemanticAnalyzer(
            lambda _text, _language: {
                "context": "announcement",
                "intent": "statement",
                "emotion": "happy",
                "events": [],
            }
        )
    )
    analyzer.set_semantic_analyzer(None)

    result = analyzer.analyze(
        "A factual passage.",
        voices,
        "en_US-lessac-medium",
        language_code="en_US",
    )

    assert result["emotion"] == "neutral"
    assert result["context"] == "narration"
    assert result["prosody_plan"]["intent"] is None


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


@pytest.mark.parametrize(
    ("text", "family", "code"),
    [
        ("Привет, как дела?", "ru", "ru_RU"),
        ("こんにちは", "ja", "ja_JP"),
    ],
)
def test_analyzer_uses_script_detector_before_low_confidence_fallback(
    text: str, family: str, code: str
) -> None:
    voices = [
        _catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True),
        _catalog_voice(f"{code}-voice-medium", family, code, "voice", "medium", False),
    ]
    analyzer = TextAnalyzer()
    analyzer._get_detector = lambda _families: _FakeDetector("EN", 0.44)
    script_families: list[set[str]] = []

    def fake_script_detector(families: Iterable[str]) -> _FakeDetector:
        script_families.append(set(families))
        return _FakeDetector(family.upper(), 0.44)

    analyzer._get_script_detector = fake_script_detector

    result = analyzer.analyze(text, voices, "en_GB-cori-high")

    assert script_families == [{family}]
    assert result["language"]["family"] == family
    assert result["voice"]["key"] == f"{code}-voice-medium"
    assert result["needs_download"] is True
    assert result["fallback_reason"] is None


def test_analyzer_keeps_low_confidence_fallback_for_ambiguous_latin_text() -> None:
    voices = [
        _catalog_voice("en_GB-cori-high", "en", "en_GB", "cori", "high", True),
        _catalog_voice("fr_FR-voice-medium", "fr", "fr_FR", "voice", "medium", True),
    ]
    analyzer = TextAnalyzer()
    analyzer._get_detector = lambda _families: _FakeDetector("FR", 0.44)

    result = analyzer.analyze("Bonjour?", voices, "en_GB-cori-high")

    assert result["language"]["family"] == "en"
    assert result["voice"]["key"] == "en_GB-cori-high"
    assert result["fallback_reason"] == "low_confidence"


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
    assert result["prosody_plan"]["language_family"] == "en"
    assert result["prosody_plan"]["supported_dimensions"] == ["duration"]
    assert "acoustic:pitch" in result["prosody_plan"]["unavailable_signals"]


def test_plan_mapping_preserves_legacy_segment_fields() -> None:
    segments = [
        {
            "kind": "text",
            "text": "Hello.",
            "prosody": {"length_scale": 1.0},
            "pause_after": 0.14,
        }
    ]
    plan = {
        "segments": [
            {
                "kind": "text",
                "events": [
                    {
                        "kind": "boundary",
                        "dimension": "duration",
                        "value": 0.14,
                        "supported": True,
                    },
                    {
                        "kind": "pitch",
                        "dimension": "pitch",
                        "value": 0.2,
                        "supported": False,
                    },
                ],
            }
        ]
    }

    mapped = map_plan_to_segments(segments, plan)

    assert mapped[0]["text"] == segments[0]["text"]
    assert mapped[0]["prosody"] == segments[0]["prosody"]
    assert mapped[0]["pause_after"] == segments[0]["pause_after"]
    assert mapped[0]["prosody_supported_dimensions"] == ["duration"]
    assert mapped[0]["prosody_events"][1]["supported"] is False


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


class _MultilingualFakeVoice:
    def __init__(self, family: str) -> None:
        self.config = SimpleNamespace(
            espeak_voice=f"{family}-test",
            num_speakers=1,
            speaker_id_map={},
            default_speaker_id=0,
            length_scale=1.0,
            noise_scale=0.667,
            noise_w_scale=0.8,
            sample_rate=22050,
        )

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


@pytest.fixture()
def multilingual_http_client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    voices = {
        "en_GB-cori-high": {
            "family": "en",
            "code": "en_GB",
            "name": "cori",
            "quality": "high",
            "text": "This is an English voice test.",
        },
        "vi_VN-vais1000-medium": {
            "family": "vi",
            "code": "vi_VN",
            "name": "vais1000",
            "quality": "medium",
            "text": "Đây là một bài kiểm tra giọng nói tiếng Việt.",
        },
        "ja_JP-hi_fi_captain-medium": {
            "family": "ja",
            "code": "ja_JP",
            "name": "hi_fi_captain",
            "quality": "medium",
            "text": "これは日本語の音声テストです。",
        },
        "zh_CN-chaowen-medium": {
            "family": "zh",
            "code": "zh_CN",
            "name": "chaowen",
            "quality": "medium",
            "text": "这是中文语音测试。",
        },
        "ru_RU-denis-medium": {
            "family": "ru",
            "code": "ru_RU",
            "name": "denis",
            "quality": "medium",
            "text": "Привет, как дела?",
        },
    }
    raw_catalog = {
        model_id: {
            "key": model_id,
            "language": {
                "code": details["code"],
                "family": details["family"],
                "name_english": details["family"],
            },
            "name": details["name"],
            "quality": details["quality"],
            "num_speakers": 1,
            "speaker_id_map": {},
            "files": {"voice.onnx": {"size_bytes": 10}},
        }
        for model_id, details in voices.items()
    }

    def write_voice(model_id: str) -> None:
        details = voices[model_id]
        (tmp_path / f"{model_id}.onnx").write_bytes(b"model")
        (tmp_path / f"{model_id}.onnx.json").write_text(
            json.dumps(
                {
                    "audio": {"sample_rate": 22050, "quality": details["quality"]},
                    "language": {
                        "code": details["code"],
                        "family": details["family"],
                        "name_english": details["family"],
                    },
                    "dataset": details["name"],
                    "num_speakers": 1,
                    "speaker_id_map": {},
                }
            ),
            encoding="utf-8",
        )

    write_voice("en_GB-cori-high")
    write_voice("vi_VN-vais1000-medium")

    def fake_download(
        model_id: str, download_dir: Path, *, force_redownload: bool = False
    ) -> None:
        del force_redownload
        assert model_id in voices
        assert download_dir == tmp_path
        write_voice(model_id)

    monkeypatch.setattr("piper.http_server.download_voice", fake_download)
    args = SimpleNamespace(
        data_dir=[str(tmp_path)],
        download_dir=str(tmp_path),
        cuda=False,
        speaker=0,
        length_scale=None,
        noise_scale=None,
        noise_w_scale=None,
        sentence_silence=0.0,
        disable_linguistic=True,
    )
    model_path = tmp_path / "en_GB-cori-high.onnx"

    def voice_loader(model_file: Path, **_kwargs: Any) -> _MultilingualFakeVoice:
        return _MultilingualFakeVoice(voices[model_file.stem]["family"])

    app = create_app(
        args,
        model_path,
        _MultilingualFakeVoice("en"),
        catalog_fetcher=lambda: raw_catalog,
        voice_loader=voice_loader,
    )
    app.config["TESTING"] = True
    return app.test_client()


AUTO_SELECTION = {
    "language": "auto",
    "voice": "auto",
    "quality": "auto",
    "speaker": None,
    "emotion": "auto",
}


def _assert_wav_response(response: Any) -> None:
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.data.startswith(b"RIFF")
    with wave.open(io.BytesIO(response.data), "rb") as wav_file:
        assert wav_file.getnframes() > 0


@pytest.mark.parametrize(
    ("model_id", "text"),
    [
        ("ja_JP-hi_fi_captain-medium", "これは日本語の音声テストです。"),
        ("zh_CN-chaowen-medium", "这是中文语音测试。"),
    ],
)
def test_http_auto_multilingual_download_then_synthesize(
    multilingual_http_client: Any, model_id: str, text: str
) -> None:
    before = multilingual_http_client.get("/voice-catalog").get_json()
    before_voice = next(voice for voice in before["voices"] if voice["key"] == model_id)
    assert before_voice["installed"] is False

    download_response = multilingual_http_client.post(
        "/download", json={"voice": model_id}
    )
    assert download_response.status_code == 200
    assert download_response.get_data(as_text=True) == model_id

    after = multilingual_http_client.get("/voice-catalog").get_json()
    after_voice = next(voice for voice in after["voices"] if voice["key"] == model_id)
    assert after_voice["installed"] is True

    synthesis_response = multilingual_http_client.post(
        "/synthesize", json={"text": text, "selection": AUTO_SELECTION}
    )
    _assert_wav_response(synthesis_response)
    assert multilingual_http_client.get("/info").get_json()["last"]["voice"] == model_id


def test_http_auto_short_russian_requires_matching_voice_then_synthesizes(
    multilingual_http_client: Any,
) -> None:
    analysis_response = multilingual_http_client.post(
        "/analyze", json={"text": "Привет, как дела?", "selection": AUTO_SELECTION}
    )
    assert analysis_response.status_code == 200
    analysis = analysis_response.get_json()
    assert analysis["language"]["family"] == "ru"
    assert analysis["voice"]["key"] == "ru_RU-denis-medium"
    assert analysis["needs_download"] is True

    missing_response = multilingual_http_client.post(
        "/synthesize",
        json={"text": "Привет, как дела?", "selection": AUTO_SELECTION},
    )
    assert missing_response.status_code == 409
    assert missing_response.get_json()["error"] == "voice_not_installed"
    assert missing_response.get_json()["voice"]["key"] == "ru_RU-denis-medium"

    download_response = multilingual_http_client.post(
        "/download", json={"voice": "ru_RU-denis-medium"}
    )
    assert download_response.status_code == 200

    synthesis_response = multilingual_http_client.post(
        "/synthesize",
        json={"text": "Привет, как дела?", "selection": AUTO_SELECTION},
    )
    _assert_wav_response(synthesis_response)
    assert multilingual_http_client.get("/info").get_json()["last"]["voice"] == (
        "ru_RU-denis-medium"
    )


def test_http_concurrent_downloads_are_deduplicated(
    multilingual_http_client: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_id = "ru_RU-denis-medium"
    calls = []
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
        payload = (
            b'{"audio":{"sample_rate":22050,"quality":"medium"},'
            b'"language":{"code":"ru_RU","family":"ru",'
            b'"name_english":"Russian"},"dataset":"denis",'
            b'"num_speakers":1,"speaker_id_map":{}}'
            if ".onnx.json" in url
            else b"model"
        )
        return io.BytesIO(payload)

    monkeypatch.setattr("piper.http_server.download_voice", real_download_voice)
    monkeypatch.setattr("piper.download_voices.urlopen", fake_urlopen)
    app = multilingual_http_client.application

    def download_from_client() -> Any:
        with app.test_client() as client:
            return client.post("/download", json={"voice": model_id})

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(download_from_client)
        assert first_started.wait(timeout=5)
        second = executor.submit(download_from_client)
        time.sleep(0.2)
        assert not second_started.is_set()
        release_first.set()
        first_response = first.result(timeout=5)
        second_response = second.result(timeout=5)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(calls) == 2
    assert (tmp_path / f"{model_id}.onnx").read_bytes() == b"model"
    assert json.loads((tmp_path / f"{model_id}.onnx.json").read_text())["dataset"] == (
        "denis"
    )

    catalog = app.test_client().get("/voice-catalog").get_json()
    downloaded_voice = next(
        voice for voice in catalog["voices"] if voice["key"] == model_id
    )
    assert downloaded_voice["installed"] is True

    synthesis_response = app.test_client().post(
        "/synthesize",
        json={"text": "Привет, как дела?", "mode": "manual", "voice": model_id},
    )
    _assert_wav_response(synthesis_response)


def test_http_download_failure_opens_circuit_and_fails_fast(
    multilingual_http_client: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_id = "ru_RU-denis-medium"
    calls = []

    def failing_urlopen(_url: str) -> io.BytesIO:
        calls.append(_url)
        raise OSError("upstream unavailable")

    monkeypatch.setattr("piper.http_server.download_voice", real_download_voice)
    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    app = multilingual_http_client.application

    first_response = app.test_client().post("/download", json={"voice": model_id})
    assert first_response.status_code == 502
    assert first_response.get_json()["error"] == "voice_download_upstream_failed"
    assert first_response.get_json()["retry_after"] > 0
    assert first_response.headers["Retry-After"] == str(
        first_response.get_json()["retry_after"]
    )

    second_response = app.test_client().post("/download", json={"voice": model_id})
    assert second_response.status_code == 503
    assert second_response.get_json()["error"] == "voice_download_circuit_open"
    assert second_response.get_json()["retry_after"] > 0
    assert len(calls) == 1
    assert (tmp_path / f".{model_id}.download-state.json").exists()


def test_http_download_circuit_recovers_after_single_probe(
    multilingual_http_client: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_id = "ru_RU-denis-medium"
    monkeypatch.setattr("piper.download_voices.VOICE_DOWNLOAD_COOLDOWN_SECONDS", 0)

    def failing_urlopen(_url: str) -> io.BytesIO:
        raise OSError("temporary outage")

    monkeypatch.setattr("piper.http_server.download_voice", real_download_voice)
    monkeypatch.setattr("piper.download_voices.urlopen", failing_urlopen)
    app = multilingual_http_client.application
    failed = app.test_client().post("/download", json={"voice": model_id})
    assert failed.status_code == 502

    def healthy_urlopen(url: str) -> io.BytesIO:
        payload = (
            b'{"audio":{"sample_rate":22050,"quality":"medium"},'
            b'"language":{"code":"ru_RU","family":"ru",'
            b'"name_english":"Russian"},"dataset":"denis",'
            b'"num_speakers":1,"speaker_id_map":{}}'
            if ".onnx.json" in url
            else b"model"
        )
        return io.BytesIO(payload)

    monkeypatch.setattr("piper.download_voices.urlopen", healthy_urlopen)
    recovered = app.test_client().post("/download", json={"voice": model_id})
    assert recovered.status_code == 200
    assert not (tmp_path / f".{model_id}.download-state.json").exists()


def test_http_permanent_download_error_does_not_open_circuit(
    multilingual_http_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from urllib.error import HTTPError

    model_id = "ru_RU-denis-medium"
    calls = 0

    def missing_urlopen(_url: str) -> io.BytesIO:
        nonlocal calls
        calls += 1
        raise HTTPError("https://example.test/voice", 404, "not found", {}, None)

    monkeypatch.setattr("piper.http_server.download_voice", real_download_voice)
    monkeypatch.setattr("piper.download_voices.urlopen", missing_urlopen)
    app = multilingual_http_client.application

    first = app.test_client().post("/download", json={"voice": model_id})
    second = app.test_client().post("/download", json={"voice": model_id})
    assert first.status_code == 404
    assert second.status_code == 404
    assert first.get_json()["error"] == "voice_not_found"
    assert second.get_json()["error"] == "voice_not_found"
    assert calls == 2


@pytest.mark.parametrize(
    ("model_id", "text"),
    [
        ("en_GB-cori-high", "This is an English voice test."),
        ("vi_VN-vais1000-medium", "Đây là một bài kiểm tra giọng nói tiếng Việt."),
    ],
)
def test_http_auto_existing_multilingual_voices_synthesize(
    multilingual_http_client: Any, model_id: str, text: str
) -> None:
    response = multilingual_http_client.post(
        "/synthesize", json={"text": text, "selection": AUTO_SELECTION}
    )
    _assert_wav_response(response)
    assert multilingual_http_client.get("/info").get_json()["last"]["voice"] == model_id


def test_http_serves_favicon_and_declares_it(http_client: Any) -> None:
    page_response = http_client.get("/")
    assert page_response.status_code == 200
    assert b'rel="icon"' in page_response.data
    assert b'href="/favicon.ico"' in page_response.data

    favicon_response = http_client.get("/favicon.ico")
    assert favicon_response.status_code == 200
    assert favicon_response.mimetype in {"image/x-icon", "image/vnd.microsoft.icon"}
    assert favicon_response.data


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
    execution = http_client.get("/info").get_json()["last"]["prosody_execution"]
    assert execution["executor"] == "piper-legacy"

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


def test_http_does_not_load_model_without_companion_config(
    http_client: Any, tmp_path: Path
) -> None:
    model_id = "vi_VN-vivos-x_low"
    (tmp_path / f"{model_id}.onnx").write_bytes(b"partial-model")

    response = http_client.post(
        "/synthesize",
        json={"text": "Xin chào", "mode": "manual", "voice": model_id},
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "voice_not_installed"


def test_http_unified_selection_keeps_explicit_dimensions(http_client: Any) -> None:
    selection = {
        "language": "en_US",
        "voice": "auto",
        "quality": "medium",
        "speaker": None,
        "emotion": "happy",
    }
    analysis_response = http_client.post(
        "/analyze", json={"text": "Hello there", "selection": selection}
    )
    assert analysis_response.status_code == 200
    analysis = analysis_response.get_json()
    assert analysis["language"]["code"] == "en_US"
    assert analysis["voice"]["key"] == "en_US-lessac-medium"

    synthesis_response = http_client.post(
        "/synthesize", json={"text": "Hello", "selection": selection}
    )
    assert synthesis_response.status_code == 200
    assert http_client.get("/info").get_json()["last"]["mode"] == "unified"


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
