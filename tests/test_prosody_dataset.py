"""Tests for expressive training-record validation."""

import pytest

from piper.prosody_dataset import ProsodyDataError, validate_prosody_record


def _record() -> dict[str, object]:
    return {
        "language": "vi",
        "speaker": "speaker-1",
        "text": "Xin chào.",
        "alignment": [
            {"text_start": 0, "text_end": 9, "start_seconds": 0.0, "end_seconds": 0.8}
        ],
        "prosody": {
            "events": [
                {
                    "kind": "emphasis",
                    "dimension": "energy",
                    "value": 0.4,
                    "text_start": 0,
                    "text_end": 2,
                }
            ]
        },
    }


def test_valid_expressive_record() -> None:
    validate_prosody_record(_record())


@pytest.mark.parametrize(
    "field",
    ["language", "speaker", "text", "alignment", "prosody"],
)
def test_missing_required_metadata_is_rejected(field: str) -> None:
    record = _record()
    record.pop(field)

    with pytest.raises(ProsodyDataError):
        validate_prosody_record(record)


def test_alignment_and_prosody_ranges_are_rejected() -> None:
    record = _record()
    record["alignment"] = [
        {"text_start": 0, "text_end": 99, "start_seconds": 0.0, "end_seconds": 0.8}
    ]
    with pytest.raises(ProsodyDataError, match="text offsets"):
        validate_prosody_record(record)

    record = _record()
    record["prosody"] = {
        "events": [{"kind": "pitch", "dimension": "pitch", "value": 2.0}]
    }
    with pytest.raises(ProsodyDataError, match="outside"):
        validate_prosody_record(record)

