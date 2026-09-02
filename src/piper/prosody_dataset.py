"""Validation for expressive Piper training examples."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .prosody import PROSODY_DIMENSIONS, events_from_mappings

PILOT_LANGUAGE_FAMILIES = frozenset({"en", "vi", "zh", "ja", "ar"})


class ProsodyDataError(ValueError):
    """Raised when an expressive training example is not safe to use."""


def validate_prosody_record(
    record: Mapping[str, Any],
    *,
    pilot_languages: Sequence[str] = PILOT_LANGUAGE_FAMILIES,
) -> None:
    """Validate one JSON-compatible expressive training example.

    The validator deliberately requires explicit text alignment and bounded
    event annotations.  It does not infer missing labels, because inferred
    labels could turn a bad training sample into a misleading acoustic target.
    """
    if not isinstance(record, Mapping):
        raise ProsodyDataError("record must be an object")

    language = str(record.get("language", "")).strip().casefold()
    if language not in set(pilot_languages):
        raise ProsodyDataError("language must be one of the pilot language families")
    speaker = str(record.get("speaker", "")).strip()
    if not speaker:
        raise ProsodyDataError("speaker is required")
    text = str(record.get("text", ""))
    if not text.strip():
        raise ProsodyDataError("text is required")

    alignment = record.get("alignment")
    if not isinstance(alignment, Sequence) or isinstance(alignment, (str, bytes)):
        raise ProsodyDataError("alignment must be a non-empty sequence")
    if not alignment:
        raise ProsodyDataError("alignment must be a non-empty sequence")
    previous_end = -1
    for item in alignment:
        if not isinstance(item, Mapping):
            raise ProsodyDataError("alignment items must be objects")
        text_start = item.get("text_start")
        text_end = item.get("text_end")
        start_seconds = item.get("start_seconds")
        end_seconds = item.get("end_seconds")
        if not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in (text_start, text_end)
        ):
            raise ProsodyDataError("alignment text offsets must be integers")
        if not 0 <= text_start < text_end <= len(text):
            raise ProsodyDataError("alignment text offsets are out of range")
        if text_start < previous_end:
            raise ProsodyDataError("alignment text offsets must be ordered")
        if not all(isinstance(value, (int, float)) for value in (start_seconds, end_seconds)):
            raise ProsodyDataError("alignment times must be numeric")
        if not 0 <= float(start_seconds) < float(end_seconds):
            raise ProsodyDataError("alignment times must be ordered and non-negative")
        previous_end = text_end

    prosody = record.get("prosody")
    if not isinstance(prosody, Mapping):
        raise ProsodyDataError("prosody metadata is required")
    events = prosody.get("events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise ProsodyDataError("prosody.events must be a non-empty sequence")
    if not events:
        raise ProsodyDataError("prosody.events must be a non-empty sequence")
    try:
        validated_events = events_from_mappings(events)
    except (TypeError, ValueError) as exc:
        raise ProsodyDataError(f"invalid prosody event: {exc}") from exc

    for event in validated_events:
        if event.dimension not in PROSODY_DIMENSIONS:
            raise ProsodyDataError("prosody event dimension is required")
        if event.value is None:
            raise ProsodyDataError("prosody event value is required")
        if event.dimension == "duration":
            valid_range = 0.0 <= event.value <= 10.0
        else:
            valid_range = -1.0 <= event.value <= 1.0
        if not valid_range:
            raise ProsodyDataError(
                f"prosody {event.dimension} value is outside the supported range"
            )

