"""Normalized prosody plans and voice capability contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence


PROSODY_DIMENSIONS = frozenset(
    {"duration", "pitch", "energy", "emphasis", "style"}
)
PROSODY_EVENT_KINDS = frozenset(
    {"pause", "boundary", "stress", "tone", "pitch", "energy", "emphasis", "style"}
)
# Markers emitted by the language-specific phonemizers.  They are kept as
# phoneme symbols only when the voice explicitly declares that it was trained
# to consume them; ordinary legacy voices keep their historical input stream.
PHONEME_PROSODY_MARKERS = frozenset(
    {
        "ˈ",
        "ˌ",
        "↑",
        "↓",
        "#",
        "1",
        "2",
        "3",
        "4",
        "5",
    }
)


def _bounded_confidence(value: float) -> float:
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("prosody confidence must be between 0 and 1")
    return round(confidence, 4)


@dataclass(frozen=True)
class VoiceCapabilities:
    """Acoustic and phoneme capabilities declared by a voice executor."""

    model_id: str
    executor: str = "piper-legacy"
    dimensions: frozenset[str] = field(default_factory=frozenset)
    phoneme_markers: frozenset[str] = field(default_factory=frozenset)
    supports_speaker: bool = False
    legacy: bool = True

    def __post_init__(self) -> None:
        unknown = set(self.dimensions) - PROSODY_DIMENSIONS
        if unknown:
            raise ValueError(f"unknown prosody dimensions: {sorted(unknown)}")

    def supports(self, dimension: str) -> bool:
        """Return whether this executor can apply one prosody dimension."""
        return dimension in self.dimensions

    @classmethod
    def from_mapping(
        cls,
        model_id: str,
        value: Optional[Mapping[str, Any]] = None,
        *,
        num_speakers: int = 1,
    ) -> "VoiceCapabilities":
        """Load optional capability metadata, defaulting to legacy Piper."""
        metadata = value if isinstance(value, Mapping) else {}
        if "dimensions" in metadata:
            dimensions = frozenset(
                str(item).strip().casefold()
                for item in metadata.get("dimensions", ())
                if str(item).strip()
            )
        else:
            # Current Piper voices can already control duration through
            # length_scale, even though they have no expressive controls.
            dimensions = frozenset({"duration"})
        markers = frozenset(
            str(item)
            for item in metadata.get("phoneme_markers", ())
            if str(item)
        )
        executor = str(metadata.get("executor", "piper-legacy"))
        return cls(
            model_id=model_id,
            executor=executor,
            dimensions=dimensions,
            phoneme_markers=markers,
            supports_speaker=bool(
                metadata.get("supports_speaker", int(num_speakers) > 1)
            ),
            legacy=bool(metadata.get("legacy", executor == "piper-legacy")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible capability description."""
        return {
            "model_id": self.model_id,
            "executor": self.executor,
            "dimensions": sorted(self.dimensions),
            "phoneme_markers": sorted(self.phoneme_markers),
            "supports_speaker": self.supports_speaker,
            "legacy": self.legacy,
        }


@dataclass(frozen=True)
class ProsodyEvent:
    """One bounded prosodic event or acoustic request."""

    kind: str
    dimension: Optional[str] = None
    value: Optional[float] = None
    text_start: Optional[int] = None
    text_end: Optional[int] = None
    source: str = "local"
    confidence: float = 1.0
    supported: bool = False

    def __post_init__(self) -> None:
        if self.kind not in PROSODY_EVENT_KINDS:
            raise ValueError(f"unknown prosody event kind: {self.kind}")
        if self.dimension is not None and self.dimension not in PROSODY_DIMENSIONS:
            raise ValueError(f"unknown prosody dimension: {self.dimension}")
        if self.text_start is not None and self.text_start < 0:
            raise ValueError("prosody text_start must be non-negative")
        if self.text_end is not None and (
            self.text_end < 0
            or (self.text_start is not None and self.text_end < self.text_start)
        ):
            raise ValueError("prosody text_end must follow text_start")
        object.__setattr__(self, "confidence", _bounded_confidence(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible event description."""
        return {
            "kind": self.kind,
            "dimension": self.dimension,
            "value": self.value,
            "text_start": self.text_start,
            "text_end": self.text_end,
            "source": self.source,
            "confidence": self.confidence,
            "supported": self.supported,
        }


@dataclass(frozen=True)
class ProsodySegment:
    """A text or pause segment within a prosody plan."""

    kind: str
    text: str = ""
    paragraph_index: int = 0
    sentence_index: int = 0
    context: str = "narration"
    emotion: str = "neutral"
    events: tuple[ProsodyEvent, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"text", "pause"}:
            raise ValueError(f"unknown prosody segment kind: {self.kind}")
        if self.paragraph_index < 0 or self.sentence_index < 0:
            raise ValueError("prosody segment indexes must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible segment description."""
        return {
            "kind": self.kind,
            "text": self.text,
            "paragraph_index": self.paragraph_index,
            "sentence_index": self.sentence_index,
            "context": self.context,
            "emotion": self.emotion,
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class ProsodyPlan:
    """Language-aware prosody intermediate representation."""

    text: str
    language_family: str
    language_code: Optional[str] = None
    segments: tuple[ProsodySegment, ...] = ()
    events: tuple[ProsodyEvent, ...] = ()
    requested_dimensions: frozenset[str] = field(default_factory=frozenset)
    unavailable_signals: tuple[str, ...] = ()
    capabilities: Optional[VoiceCapabilities] = None
    intent: Optional[str] = None

    def __post_init__(self) -> None:
        unknown = set(self.requested_dimensions) - PROSODY_DIMENSIONS
        if unknown:
            raise ValueError(f"unknown requested prosody dimensions: {sorted(unknown)}")

    @classmethod
    def empty(
        cls,
        text: str,
        language_family: str,
        *,
        language_code: Optional[str] = None,
        capabilities: Optional[VoiceCapabilities] = None,
    ) -> "ProsodyPlan":
        """Create a valid plan before optional analyzers add signals."""
        return cls(
            text=text,
            language_family=language_family,
            language_code=language_code,
            capabilities=capabilities,
        )

    def supported_dimensions(self) -> frozenset[str]:
        """Return requested dimensions executable by the selected voice."""
        if self.capabilities is None:
            return frozenset()
        return frozenset(self.requested_dimensions & self.capabilities.dimensions)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible plan for internal APIs and diagnostics."""
        return {
            "text": self.text,
            "language_family": self.language_family,
            "language_code": self.language_code,
            "segments": [segment.to_dict() for segment in self.segments],
            "events": [event.to_dict() for event in self.events],
            "requested_dimensions": sorted(self.requested_dimensions),
            "supported_dimensions": sorted(self.supported_dimensions()),
            "unavailable_signals": list(self.unavailable_signals),
            "intent": self.intent,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProsodyPlan":
        """Rehydrate a serialized plan at the HTTP execution boundary."""
        capabilities_data = value.get("capabilities")
        capabilities = None
        if isinstance(capabilities_data, Mapping):
            capabilities = VoiceCapabilities.from_mapping(
                str(capabilities_data.get("model_id", "")), capabilities_data
            )
        raw_segments = value.get("segments", ())
        if not isinstance(raw_segments, Sequence) or isinstance(
            raw_segments, (str, bytes)
        ):
            raw_segments = ()
        segments = tuple(
            ProsodySegment(
                kind=str(item.get("kind", "text")),
                text=str(item.get("text", "")),
                paragraph_index=int(item.get("paragraph_index", 0)),
                sentence_index=int(item.get("sentence_index", 0)),
                context=str(item.get("context", "narration")),
                emotion=str(item.get("emotion", "neutral")),
                events=events_from_mappings(item.get("events", ())),
            )
            for item in raw_segments
            if isinstance(item, Mapping)
        )
        return cls(
            text=str(value.get("text", "")),
            language_family=str(value.get("language_family", "")),
            language_code=value.get("language_code"),
            segments=segments,
            events=events_from_mappings(value.get("events", ())),
            requested_dimensions=frozenset(
                str(item) for item in value.get("requested_dimensions", ())
            ),
            unavailable_signals=tuple(
                str(item) for item in value.get("unavailable_signals", ())
            ),
            capabilities=capabilities,
            intent=(
                str(value["intent"]).strip().casefold()
                if value.get("intent") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class ProsodyExecution:
    """Bounded executor decision for one normalized plan."""

    executor: str
    requested_dimensions: frozenset[str]
    applied_dimensions: frozenset[str]
    unavailable_dimensions: frozenset[str]
    legacy_fallback: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible executor decision."""
        return {
            "executor": self.executor,
            "requested_dimensions": sorted(self.requested_dimensions),
            "applied_dimensions": sorted(self.applied_dimensions),
            "unavailable_dimensions": sorted(self.unavailable_dimensions),
            "legacy_fallback": self.legacy_fallback,
        }


def negotiate_prosody(
    plan: ProsodyPlan,
    *,
    force_legacy: bool = False,
) -> ProsodyExecution:
    """Select only controls declared by the plan's compatible executor."""
    capabilities = plan.capabilities or VoiceCapabilities.from_mapping("")
    requested = frozenset(plan.requested_dimensions)
    applied = requested & capabilities.dimensions
    unavailable = requested - applied
    use_legacy = force_legacy or capabilities.legacy
    return ProsodyExecution(
        executor="piper-legacy" if use_legacy else capabilities.executor,
        requested_dimensions=requested,
        applied_dimensions=applied,
        unavailable_dimensions=unavailable,
        legacy_fallback=use_legacy and not capabilities.legacy,
    )


def map_plan_to_segments(
    segments: Sequence[Mapping[str, Any]],
    plan: Optional[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach plan metadata while preserving the legacy segment contract.

    The current Piper executor still consumes the existing segment fields.  A
    plan can therefore be carried alongside those fields without changing
    request compatibility or silently mapping unsupported controls to legacy
    noise/speed parameters.
    """
    mapped = [dict(segment) for segment in segments]
    if not isinstance(plan, Mapping):
        return mapped

    plan_segments = plan.get("segments")
    if not isinstance(plan_segments, Sequence) or isinstance(
        plan_segments, (str, bytes)
    ):
        return mapped
    if len(plan_segments) != len(mapped):
        return mapped

    for segment, plan_segment in zip(mapped, plan_segments):
        if not isinstance(plan_segment, Mapping):
            return mapped
        if str(segment.get("kind", "text")) != str(
            plan_segment.get("kind", "text")
        ):
            return mapped

    for segment, plan_segment in zip(mapped, plan_segments):
        events = plan_segment.get("events", ())
        if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
            events = ()
        segment["prosody_events"] = [
            dict(event) for event in events if isinstance(event, Mapping)
        ]
        segment["prosody_supported_dimensions"] = sorted(
            {
                str(event.get("dimension"))
                for event in events
                if isinstance(event, Mapping)
                and event.get("supported")
                and event.get("dimension")
            }
        )
    return mapped


def filter_unsupported_phoneme_markers(
    phoneme_groups: Sequence[Sequence[str]],
    allowed_markers: Sequence[str],
) -> list[list[str]]:
    """Remove explicitly unsupported prosody markers from phoneme groups.

    This helper is opt-in: callers should pass a declared marker allowlist
    from voice metadata.  Voices without that metadata must retain the
    historical phoneme stream for compatibility with existing models.
    """
    allowed = {str(marker) for marker in allowed_markers}
    return [
        [
            phoneme
            for phoneme in group
            if phoneme not in PHONEME_PROSODY_MARKERS
            or phoneme in allowed
        ]
        for group in phoneme_groups
    ]


def events_from_mappings(values: Sequence[Mapping[str, Any]]) -> tuple[ProsodyEvent, ...]:
    """Validate untrusted event mappings before they enter a plan."""
    return tuple(
        ProsodyEvent(
            kind=str(value.get("kind", "boundary")),
            dimension=(
                str(value["dimension"]).strip().casefold()
                if value.get("dimension") is not None
                else None
            ),
            value=(float(value["value"]) if value.get("value") is not None else None),
            text_start=(
                int(value["text_start"])
                if value.get("text_start") is not None
                else None
            ),
            text_end=(
                int(value["text_end"]) if value.get("text_end") is not None else None
            ),
            source=str(value.get("source", "external")),
            confidence=float(value.get("confidence", 0.0)),
            supported=bool(value.get("supported", False)),
        )
        for value in values
    )
