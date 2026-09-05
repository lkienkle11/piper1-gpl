"""Tests for the optional server-side semantic provider adapter."""

import io
import json
import sys
import time
from pathlib import Path

import pytest

from piper.semantic_analysis import (
    ExternalSemanticAnalyzer,
    LlamaCppSemanticProvider,
    SemanticAnalyzerConfig,
)
from piper.linguistic_analysis import StanzaLinguisticAnalyzer


def test_semantic_configuration_is_disabled_and_loopback_by_default() -> None:
    config = SemanticAnalyzerConfig.from_mapping()

    assert not config.enabled
    assert config.privacy_mode
    assert config.supported_languages == frozenset({"ar", "en", "ja", "vi", "zh"})


def test_semantic_configuration_rejects_external_endpoint_in_privacy_mode() -> None:
    with pytest.raises(ValueError, match="loopback"):
        SemanticAnalyzerConfig.from_mapping(
            {"endpoint": "https://semantic.example.test/completion"}
        )


def test_stanza_analyzer_normalizes_languages_and_caches_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline_calls = []

    class Word:
        text = "Hello"
        lemma = "hello"
        upos = "INTJ"
        xpos = "UH"
        feats = None
        head = 0
        deprel = "root"

    class ClauseWord:
        text = "world"
        lemma = "world"
        upos = "NOUN"
        xpos = "NN"
        feats = None
        head = 1
        deprel = "conj"

    class PunctuationWord:
        text = "."
        lemma = "."
        upos = "PUNCT"
        xpos = "."
        feats = None
        head = 1
        deprel = "punct"

    class Sentence:
        text = "Hello."
        words = [Word(), ClauseWord(), PunctuationWord()]

    class Document:
        sentences = [Sentence()]

    class FakeStanza:
        @staticmethod
        def Pipeline(**_kwargs: object):
            pipeline_calls.append(_kwargs)
            return lambda _text: Document()

    monkeypatch.setitem(sys.modules, "stanza", FakeStanza)
    analyzer = StanzaLinguisticAnalyzer()

    first = analyzer.analyze("Hello.", "en_GB")
    second = analyzer.analyze("Hello.", "en")
    all_languages = {
        analyzer.analyze("Native text.", language).language
        for language in ("ar", "zh", "en", "ja", "vi")
    }

    assert first.source == "stanza"
    assert first.sentences[0]["tokens"][0]["upos"] == "INTJ"
    assert first.sentences[0]["punctuation"] == ["."]
    assert first.sentences[0]["clauses"] == [{"head": 1, "deprel": "conj"}]
    assert first.paragraphs[0]["text"] == "Hello."
    assert second.source == "stanza"
    assert all_languages == {"ar", "zh", "en", "ja", "vi"}
    assert len(pipeline_calls) == 5
    assert pipeline_calls[0]["lang"] == "en"
    assert pipeline_calls[0]["download_method"] is None
    processors_by_language = {
        call["lang"]: call["processors"] for call in pipeline_calls
    }
    assert processors_by_language["en"] == {
        "tokenize": "combined_nocharlm",
        "mwt": "combined",
        "pos": "combined_nocharlm",
        "lemma": "combined_nocharlm",
        "depparse": "combined_nocharlm",
    }
    assert processors_by_language["vi"] == {
        "tokenize": "vtb",
        "pos": "vtb_nocharlm",
        "lemma": "identity",
        "depparse": "vtb_nocharlm",
    }


def test_stanza_resource_download_uses_selected_language_processors(
    tmp_path: Path,
) -> None:
    from piper.stanza_resources import download_resources

    calls = []

    class FakeStanza:
        @staticmethod
        def download(language: str, **kwargs: object) -> None:
            calls.append((language, kwargs))

    download_resources(tmp_path, ("vi", "en", "vi"), stanza_module=FakeStanza)

    assert [language for language, _kwargs in calls] == ["vi", "en"]
    assert calls[0][1]["processors"] == {
        "tokenize": "vtb",
        "pos": "vtb_nocharlm",
        "depparse": "vtb_nocharlm",
    }
    assert calls[1][1]["processors"] == {
        "tokenize": "combined_nocharlm",
        "mwt": "combined",
        "pos": "combined_nocharlm",
        "lemma": "combined_nocharlm",
        "depparse": "combined_nocharlm",
    }


def test_stanza_analyzer_falls_back_when_resources_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStanza:
        @staticmethod
        def Pipeline(**_kwargs: object):
            raise RuntimeError("resources missing")

    monkeypatch.setitem(sys.modules, "stanza", FakeStanza)

    result = StanzaLinguisticAnalyzer().analyze("こんにちは。", "ja")

    assert result.source == "local"
    assert result.unavailable == ("linguistic_resources:ja",)


def test_llama_cpp_provider_sends_bounded_schema_request() -> None:
    requests = []

    def opener(request: object, *, timeout: float) -> io.BytesIO:
        requests.append((request, timeout))
        return io.BytesIO(
            json.dumps(
                {
                    "content": json.dumps(
                        {
                            "context": "narration",
                            "intent": "statement",
                            "emotion": "neutral",
                            "events": [],
                        }
                    )
                }
            ).encode("utf-8")
        )

    provider = LlamaCppSemanticProvider(
        "http://127.0.0.1:8080/completion",
        max_text_length=20,
        opener=opener,
    )
    result = provider("Xin chào.", "vi")

    payload = json.loads(requests[0][0].data.decode("utf-8"))
    assert result["intent"] == "statement"
    assert "model" not in payload
    assert "Language: vi" in payload["prompt"]
    assert "Xin chào." in payload["prompt"]
    assert payload["json_schema"]["required"] == [
        "context",
        "intent",
        "emotion",
        "events",
    ]
    assert requests[0][1] == 1.0


def test_llama_cpp_provider_rejects_malformed_json_as_fallback_status() -> None:
    def opener(_request: object, *, timeout: float) -> io.BytesIO:
        del timeout
        return io.BytesIO(b'{"content":"not-json"}')

    analyzer = ExternalSemanticAnalyzer(
        LlamaCppSemanticProvider(
            "http://127.0.0.1:8080/completion",
            opener=opener,
        )
    )

    result = analyzer.analyze("Text", "en")

    assert result.unavailable == ("provider_invalid_output",)


def test_provider_rejects_out_of_range_event_atomically() -> None:
    analyzer = ExternalSemanticAnalyzer(
        lambda _text, _language: {
            "context": "narration",
            "intent": "statement",
            "emotion": "neutral",
            "events": [
                {
                    "kind": "emphasis",
                    "dimension": "energy",
                    "value": 2.0,
                    "text_start": 0,
                    "text_end": 4,
                    "confidence": 0.9,
                }
            ],
        }
    )

    result = analyzer.analyze("Text", "en")

    assert result.events == ()
    assert result.unavailable == ("provider_invalid_events",)


def test_provider_result_is_validated_and_returned() -> None:
    analyzer = ExternalSemanticAnalyzer(
        lambda _text, _language: {
            "emotion": "happy",
            "context": "announcement",
            "events": [
                {
                    "kind": "emphasis",
                    "dimension": "energy",
                    "value": 0.5,
                    "text_start": 0,
                    "text_end": 4,
                    "confidence": 0.9,
                }
            ],
        }
    )

    result = analyzer.analyze("Important news", "en")

    assert result.source == "external"
    assert result.emotion == "happy"
    assert result.context == "announcement"
    assert len(result.events) == 1
    assert not result.unavailable


def test_provider_rejects_malformed_output() -> None:
    analyzer = ExternalSemanticAnalyzer(
        lambda _text, _language: {"emotion": "dramatic"}
    )

    result = analyzer.analyze("Text", "en")

    assert result.source == "local"
    assert result.unavailable == ("provider_invalid_emotion",)


def test_provider_timeout_falls_back() -> None:
    def slow_provider(_text: str, _language: str) -> dict[str, str]:
        time.sleep(0.05)
        return {"emotion": "happy"}

    analyzer = ExternalSemanticAnalyzer(slow_provider, timeout_seconds=0.001)

    result = analyzer.analyze("Text", "en")

    assert result.unavailable == ("provider_timeout",)


def test_provider_language_and_network_gates_fall_back() -> None:
    provider = lambda _text, _language: {"emotion": "happy"}
    unsupported = ExternalSemanticAnalyzer(provider, supported_languages={"en"})
    offline = ExternalSemanticAnalyzer(provider, network_enabled=False)

    assert unsupported.analyze("Texto", "es").unavailable == ("provider_language:es",)
    assert offline.analyze("Text", "en").unavailable == ("network_disabled",)


def test_provider_is_opt_in_and_bounds_input_before_call() -> None:
    calls = []
    provider = lambda _text, _language: calls.append(True)
    disabled = ExternalSemanticAnalyzer(provider, enabled=False)
    bounded = ExternalSemanticAnalyzer(provider, max_text_length=4)

    assert disabled.analyze("Text", "en").unavailable == ("provider_disabled",)
    assert bounded.analyze("Too long", "en").unavailable == ("provider_text_too_long",)
    assert calls == []
