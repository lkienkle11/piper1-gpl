"""Optional multilingual linguistic analysis backed by Stanza."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import unicodedata
import re
from typing import Any, Dict, List, Optional, Tuple

PILOT_LANGUAGES = frozenset({"ar", "en", "ja", "vi", "zh"})
_LANGUAGE_ALIASES = {
    "ar": "ar",
    "en": "en",
    "ja": "ja",
    "vi": "vi",
    "zh": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
}


@dataclass(frozen=True)
class LinguisticAnalysis:
    """Serializable linguistic signals or an unavailable-resource status."""

    text: str
    language: str
    sentences: Tuple[Dict[str, Any], ...] = ()
    source: str = "local"
    unavailable: Tuple[str, ...] = ()
    paragraphs: Tuple[Dict[str, Any], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        """Return an internal JSON-compatible result."""
        return {
            "text": self.text,
            "language": self.language,
            "sentences": list(self.sentences),
            "paragraphs": list(self.paragraphs),
            "source": self.source,
            "unavailable": list(self.unavailable),
        }


class StanzaLinguisticAnalyzer:
    """Lazily load and cache one Stanza pipeline per pilot language."""

    def __init__(
        self,
        *,
        model_dir: Optional[str] = None,
        use_gpu: bool = False,
        enabled: bool = True,
    ) -> None:
        self.model_dir = Path(model_dir) if model_dir else None
        self.use_gpu = use_gpu
        self.enabled = enabled
        self._pipelines: Dict[str, Any] = {}
        self._unavailable: Dict[str, str] = {}

    def analyze(self, text: str, language: str) -> LinguisticAnalysis:
        """Analyze text without downloading resources or changing the input."""
        normalized_language = self.normalize_language(language)
        if normalized_language not in PILOT_LANGUAGES:
            return LinguisticAnalysis(
                text=text,
                language=normalized_language,
                unavailable=(f"linguistic_language:{normalized_language}",),
                paragraphs=tuple(self._paragraph_signals(text)),
            )
        if not self.enabled:
            return LinguisticAnalysis(
                text=text,
                language=normalized_language,
                unavailable=("linguistic_disabled",),
                paragraphs=tuple(self._paragraph_signals(text)),
            )

        pipeline = self._get_pipeline(normalized_language)
        if pipeline is None:
            return LinguisticAnalysis(
                text=text,
                language=normalized_language,
                unavailable=(self._unavailable[normalized_language],),
                paragraphs=tuple(self._paragraph_signals(text)),
            )

        try:
            document = pipeline(text)
        except Exception:
            self._unavailable[normalized_language] = (
                f"linguistic_runtime:{normalized_language}"
            )
            return LinguisticAnalysis(
                text=text,
                language=normalized_language,
                unavailable=(self._unavailable[normalized_language],),
                paragraphs=tuple(self._paragraph_signals(text)),
            )

        return LinguisticAnalysis(
            text=text,
            language=normalized_language,
            sentences=tuple(self._serialize_sentences(document)),
            paragraphs=tuple(self._paragraph_signals(text)),
            source="stanza",
        )

    @staticmethod
    def normalize_language(language: str) -> str:
        """Normalize locale or Stanza language aliases to a pilot family."""
        value = str(language).strip().casefold().replace("_", "-")
        return _LANGUAGE_ALIASES.get(value, value.split("-", 1)[0])

    def _get_pipeline(self, language: str) -> Any:
        if language in self._pipelines:
            return self._pipelines[language]
        if language in self._unavailable:
            return None

        try:
            import stanza

            kwargs: Dict[str, Any] = {
                "lang": language,
                "processors": "tokenize,mwt,pos,lemma,depparse",
                "use_gpu": self.use_gpu,
            }
            if self.model_dir is not None:
                kwargs["model_dir"] = str(self.model_dir)
            pipeline = stanza.Pipeline(**kwargs)
        except ImportError:
            self._unavailable[language] = "stanza_not_installed"
            return None
        except Exception:
            self._unavailable[language] = f"linguistic_resources:{language}"
            return None

        self._pipelines[language] = pipeline
        return pipeline

    @staticmethod
    def _serialize_sentences(document: Any) -> List[Dict[str, Any]]:
        sentences: List[Dict[str, Any]] = []
        for sentence in getattr(document, "sentences", ()):
            words = list(getattr(sentence, "words", ()))
            if words:
                tokens = [StanzaLinguisticAnalyzer._serialize_word(word) for word in words]
            else:
                tokens = [
                    {"text": str(getattr(token, "text", ""))}
                    for token in getattr(sentence, "tokens", ())
                ]
            sentences.append(
                {
                    "text": str(getattr(sentence, "text", "")),
                    "tokens": tokens,
                    "punctuation": [
                        token["text"]
                        for token in tokens
                        if _is_punctuation(token.get("text", ""))
                    ],
                    "clauses": [
                        {
                            "head": token.get("head"),
                            "deprel": token.get("deprel"),
                        }
                        for token in tokens
                        if token.get("deprel") in _CLAUSE_RELATIONS
                    ],
                }
            )
        return sentences

    @staticmethod
    def _paragraph_signals(text: str) -> List[Dict[str, Any]]:
        """Expose paragraph boundaries without normalizing or rewriting text."""
        paragraphs: List[Dict[str, Any]] = []
        start = 0
        blocks = re.split(r"\r?\n\s*\r?\n", text)
        for index, block in enumerate(blocks):
            end = start + len(block)
            paragraphs.append(
                {
                    "index": index,
                    "text": block,
                    "start": start,
                    "end": end,
                    "blank_line_after": index < len(blocks) - 1,
                }
            )
            if index < len(blocks) - 1:
                separator = re.search(r"\r?\n\s*\r?\n", text[end:])
                start = end + (separator.end() if separator else 2)
        return paragraphs

    @staticmethod
    def _serialize_word(word: Any) -> Dict[str, Any]:
        """Keep only stable JSON-safe Stanza word attributes."""
        result: Dict[str, Any] = {"text": str(getattr(word, "text", ""))}
        for name in ("lemma", "upos", "xpos", "feats", "head", "deprel"):
            value = getattr(word, name, None)
            if value is not None:
                result[name] = value
        return result


_CLAUSE_RELATIONS = frozenset(
    {"advcl", "acl", "ccomp", "conj", "parataxis", "relcl", "xcomp"}
)


def _is_punctuation(value: str) -> bool:
    """Return whether a serialized token is Unicode punctuation."""
    return bool(value) and all(unicodedata.category(char).startswith("P") for char in value)
