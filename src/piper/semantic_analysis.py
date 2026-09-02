"""Optional server-side semantic analysis with a local-safe fallback."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
import json
import math
from typing import Any, Callable, Mapping, Optional, Set
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .prosody import (
    PROSODY_DIMENSIONS,
    PROSODY_EVENT_KINDS,
    ProsodyEvent,
    events_from_mappings,
)


SEMANTIC_EMOTIONS = frozenset({"neutral", "happy", "sad", "angry", "excited"})
SEMANTIC_CONTEXTS = frozenset(
    {"fragment", "conversation", "narration", "announcement", "question"}
)
PILOT_SEMANTIC_LANGUAGES = frozenset({"ar", "en", "ja", "vi", "zh"})
SEMANTIC_INTENTS = frozenset(
    {
        "announcement",
        "command",
        "conversation",
        "narration",
        "question",
        "request",
        "statement",
        "unknown",
        "warning",
    }
)
MAX_SEMANTIC_EVENTS = 32
SEMANTIC_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["context", "intent", "emotion", "events"],
    "properties": {
        "context": {"type": ["string", "null"], "enum": [*SEMANTIC_CONTEXTS, None]},
        "intent": {"type": "string", "enum": sorted(SEMANTIC_INTENTS)},
        "emotion": {
            "type": ["string", "null"],
            "enum": [*SEMANTIC_EMOTIONS, None],
        },
        "events": {
            "type": "array",
            "maxItems": MAX_SEMANTIC_EVENTS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "dimension", "value", "confidence"],
                "properties": {
                    "kind": {"type": "string", "enum": sorted(PROSODY_EVENT_KINDS)},
                    "dimension": {
                        "type": ["string", "null"],
                        "enum": [*PROSODY_DIMENSIONS, None],
                    },
                    "value": {"type": ["number", "null"]},
                    "text_start": {"type": ["integer", "null"]},
                    "text_end": {"type": ["integer", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
}
SemanticProvider = Callable[[str, str], Mapping[str, Any]]


class SemanticProviderStatus(RuntimeError):
    """A provider failure that should be exposed as a local fallback status."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


@dataclass(frozen=True)
class SemanticAnalyzerConfig:
    """Backend-only policy for optional local semantic analysis."""

    linguistic_enabled: bool = True
    linguistic_model_dir: Optional[str] = None
    linguistic_use_gpu: bool = False
    enabled: bool = False
    endpoint: str = "http://127.0.0.1:8080/completion"
    timeout_seconds: float = 1.0
    max_text_length: int = 4000
    supported_languages: frozenset[str] = PILOT_SEMANTIC_LANGUAGES
    privacy_mode: bool = True
    allow_external_endpoint: bool = False

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("semantic analyzer timeout must be positive")
        if self.max_text_length <= 0:
            raise ValueError("semantic analyzer max text length must be positive")
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("semantic analyzer endpoint must be an HTTP URL")
        if self.privacy_mode and self.allow_external_endpoint:
            raise ValueError(
                "privacy mode cannot allow an external semantic endpoint"
            )
        if not self.allow_external_endpoint and parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("semantic analyzer endpoint must be loopback")
        unknown_languages = set(self.supported_languages) - PILOT_SEMANTIC_LANGUAGES
        if unknown_languages:
            raise ValueError(
                f"unsupported semantic languages: {sorted(unknown_languages)}"
            )

    @classmethod
    def from_mapping(cls, value: Optional[Mapping[str, Any]] = None) -> "SemanticAnalyzerConfig":
        """Load validated backend settings without enabling the provider."""
        data = value if isinstance(value, Mapping) else {}
        raw_languages = data.get("supported_languages", PILOT_SEMANTIC_LANGUAGES)
        if isinstance(raw_languages, str):
            raw_languages = [raw_languages]
        return cls(
            linguistic_enabled=bool(data.get("linguistic_enabled", True)),
            linguistic_model_dir=(
                str(data["linguistic_model_dir"])
                if data.get("linguistic_model_dir")
                else None
            ),
            linguistic_use_gpu=bool(data.get("linguistic_use_gpu", False)),
            enabled=bool(data.get("enabled", False)),
            endpoint=str(
                data.get("endpoint", "http://127.0.0.1:8080/completion")
            ),
            timeout_seconds=float(data.get("timeout_seconds", 1.0)),
            max_text_length=int(data.get("max_text_length", 4000)),
            supported_languages=frozenset(
                str(language).strip().casefold()
                for language in raw_languages
                if str(language).strip()
            ),
            privacy_mode=bool(data.get("privacy_mode", True)),
            allow_external_endpoint=bool(data.get("allow_external_endpoint", False)),
        )


@dataclass(frozen=True)
class SemanticAnalysis:
    """Validated provider result or a local-fallback status."""

    emotion: Optional[str] = None
    context: Optional[str] = None
    events: tuple[ProsodyEvent, ...] = ()
    source: str = "local"
    unavailable: tuple[str, ...] = ()
    intent: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return an internal JSON-compatible result."""
        return {
            "emotion": self.emotion,
            "context": self.context,
            "intent": self.intent,
            "events": [event.to_dict() for event in self.events],
            "source": self.source,
            "unavailable": list(self.unavailable),
        }


class LlamaCppSemanticProvider:
    """Call a separately managed local llama.cpp completion endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = 1.0,
        max_text_length: int = 4000,
        allow_external_endpoint: bool = False,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("semantic analyzer timeout must be positive")
        if max_text_length <= 0:
            raise ValueError("semantic analyzer max text length must be positive")
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("semantic analyzer endpoint must be an HTTP URL")
        if not allow_external_endpoint and parsed.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("semantic analyzer endpoint must be loopback")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_text_length = max_text_length
        self.opener = opener

    def __call__(self, text: str, language_family: str) -> Mapping[str, Any]:
        if len(text) > self.max_text_length:
            raise SemanticProviderStatus("provider_text_too_long")
        prompt = (
            "Return only a JSON object that follows the supplied schema. "
            "Do not include commentary or repeat the source text.\n"
            f"Language: {language_family}\nText:\n{text}"
        )
        payload: dict[str, Any] = {
            "prompt": prompt,
            "temperature": 0.0,
            "n_predict": 256,
            "cache_prompt": True,
            "json_schema": SEMANTIC_OUTPUT_SCHEMA,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                response_data = json.load(response)
        except TimeoutError as err:
            raise SemanticProviderStatus("provider_timeout") from err
        except OSError as err:
            raise SemanticProviderStatus("provider_error") from err
        except (TypeError, ValueError, json.JSONDecodeError) as err:
            raise SemanticProviderStatus("provider_invalid_output") from err

        content: Any = response_data.get("content") if isinstance(response_data, Mapping) else None
        if content is None and isinstance(response_data, Mapping):
            choices = response_data.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
                message = choices[0].get("message")
                content = (
                    message.get("content")
                    if isinstance(message, Mapping)
                    else choices[0].get("text")
                )
        if isinstance(content, Mapping):
            return content
        if not isinstance(content, str):
            raise SemanticProviderStatus("provider_invalid_output")
        try:
            parsed_content = json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError) as err:
            raise SemanticProviderStatus("provider_invalid_output") from err
        if not isinstance(parsed_content, Mapping):
            raise SemanticProviderStatus("provider_invalid_output")
        return parsed_content


class ExternalSemanticAnalyzer:
    """Run an injected semantic provider with bounded failure behavior."""

    def __init__(
        self,
        provider: SemanticProvider,
        *,
        timeout_seconds: float = 1.0,
        supported_languages: Optional[Set[str]] = None,
        enabled: bool = True,
        network_enabled: bool = True,
        max_text_length: int = 4000,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("semantic analyzer timeout must be positive")
        if max_text_length <= 0:
            raise ValueError("semantic analyzer max text length must be positive")
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.supported_languages = supported_languages
        self.enabled = enabled
        self.network_enabled = network_enabled
        self.max_text_length = max_text_length

    def analyze(self, text: str, language_family: str) -> SemanticAnalysis:
        """Return validated provider output or an unavailable status."""
        if not self.enabled:
            return SemanticAnalysis(unavailable=("provider_disabled",))
        if not self.network_enabled:
            return SemanticAnalysis(unavailable=("network_disabled",))
        if len(text) > self.max_text_length:
            return SemanticAnalysis(unavailable=("provider_text_too_long",))
        if (
            self.supported_languages is not None
            and language_family not in self.supported_languages
        ):
            return SemanticAnalysis(
                unavailable=(f"provider_language:{language_family}",)
            )

        executor = ThreadPoolExecutor(max_workers=1)
        future: Future[Mapping[str, Any]] = executor.submit(
            self.provider, text, language_family
        )
        try:
            raw_result = future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            future.cancel()
            return SemanticAnalysis(unavailable=("provider_timeout",))
        except SemanticProviderStatus as err:
            return SemanticAnalysis(unavailable=(err.status,))
        except Exception:
            return SemanticAnalysis(unavailable=("provider_error",))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return self._validate(raw_result, text_length=len(text))

    @staticmethod
    def _validate(
        raw_result: Mapping[str, Any], *, text_length: Optional[int] = None
    ) -> SemanticAnalysis:
        if not isinstance(raw_result, Mapping):
            return SemanticAnalysis(unavailable=("provider_invalid_output",))

        emotion = raw_result.get("emotion")
        if emotion is not None:
            emotion = str(emotion).strip().casefold()
            if emotion not in SEMANTIC_EMOTIONS:
                return SemanticAnalysis(unavailable=("provider_invalid_emotion",))

        context = raw_result.get("context")
        if context is not None:
            context = str(context).strip().casefold()
            if context not in SEMANTIC_CONTEXTS:
                return SemanticAnalysis(unavailable=("provider_invalid_context",))

        intent = raw_result.get("intent", "unknown")
        if intent is None:
            return SemanticAnalysis(unavailable=("provider_invalid_intent",))
        intent = str(intent).strip().casefold()
        if intent not in SEMANTIC_INTENTS:
            return SemanticAnalysis(unavailable=("provider_invalid_intent",))

        raw_events = raw_result.get("events", ())
        if not isinstance(raw_events, (list, tuple)) or len(raw_events) > MAX_SEMANTIC_EVENTS:
            return SemanticAnalysis(unavailable=("provider_invalid_events",))
        if any(not isinstance(event, Mapping) for event in raw_events):
            return SemanticAnalysis(unavailable=("provider_invalid_events",))
        try:
            events = ExternalSemanticAnalyzer._validate_events(
                raw_events, text_length=text_length
            )
        except (TypeError, ValueError):
            return SemanticAnalysis(unavailable=("provider_invalid_events",))

        return SemanticAnalysis(
            emotion=emotion,
            context=context,
            events=events,
            source="external",
            intent=intent,
        )

    @staticmethod
    def _validate_events(
        raw_events: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        *,
        text_length: Optional[int] = None,
    ) -> tuple[ProsodyEvent, ...]:
        """Validate provider events atomically before constructing the plan."""
        checked: list[Mapping[str, Any]] = []
        for event in raw_events:
            kind = str(event.get("kind", "")).strip().casefold()
            dimension_value = event.get("dimension")
            dimension = (
                str(dimension_value).strip().casefold()
                if dimension_value is not None
                else None
            )
            if kind not in PROSODY_EVENT_KINDS:
                raise ValueError("unknown event kind")
            if dimension is not None and dimension not in PROSODY_DIMENSIONS:
                raise ValueError("unknown event dimension")
            if dimension is None:
                raise ValueError("event dimension is required")
            for offset_name in ("text_start", "text_end"):
                offset = event.get(offset_name)
                if offset is not None and (
                    isinstance(offset, bool) or not isinstance(offset, int) or offset < 0
                ):
                    raise ValueError("event offset is invalid")
            confidence = float(event.get("confidence", -1.0))
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError("event confidence is invalid")
            value = event.get("value")
            if value is None:
                raise ValueError("event value is required")
            if value is not None:
                numeric_value = float(value)
                if not math.isfinite(numeric_value):
                    raise ValueError("event value is invalid")
                ranges = {
                    "duration": (0.0, 10.0),
                    "pitch": (-1.0, 1.0),
                    "energy": (-1.0, 1.0),
                    "emphasis": (0.0, 1.0),
                    "style": (0.0, 1.0),
                }
                if dimension in ranges and not ranges[dimension][0] <= numeric_value <= ranges[dimension][1]:
                    raise ValueError("event value is out of range")
            if (
                event.get("text_start") is not None
                and event.get("text_end") is not None
                and int(event["text_end"]) < int(event["text_start"])
            ):
                raise ValueError("event offsets are reversed")
            if text_length is not None and any(
                event.get(name) is not None and int(event[name]) > text_length
                for name in ("text_start", "text_end")
            ):
                raise ValueError("event offset is outside source text")
            checked.append(event)
        return events_from_mappings(checked)
