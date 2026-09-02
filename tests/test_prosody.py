"""Tests for the normalized prosody and capability contracts."""

import pytest

from piper.config import PiperConfig
from piper.prosody import (
    ProsodyEvent,
    ProsodyPlan,
    ProsodySegment,
    VoiceCapabilities,
    events_from_mappings,
    filter_unsupported_phoneme_markers,
    negotiate_prosody,
)


def test_legacy_capabilities_default_to_current_piper_inputs() -> None:
    capabilities = VoiceCapabilities.from_mapping("en_US-lessac-medium")

    assert capabilities.legacy
    assert capabilities.dimensions == frozenset({"duration"})
    assert capabilities.executor == "piper-legacy"
    assert capabilities.to_dict()["dimensions"] == ["duration"]


def test_piper_config_discovers_optional_expressive_capabilities() -> None:
    config = PiperConfig.from_dict(
        {
            "audio": {"sample_rate": 22050},
            "espeak": {"voice": "en-us"},
            "num_symbols": 256,
            "num_speakers": 2,
            "phoneme_id_map": {},
            "phoneme_type": "espeak",
            "prosody": {
                "executor": "piper-expressive",
                "dimensions": ["duration", "pitch", "energy"],
                "phoneme_markers": ["↑", "↓"],
                "legacy": False,
            },
        }
    )

    capabilities = config.prosody_capabilities("en_GB-expressive-medium")

    assert capabilities.executor == "piper-expressive"
    assert capabilities.dimensions == frozenset({"duration", "pitch", "energy"})
    assert capabilities.supports_speaker
    assert not capabilities.legacy
    assert config.to_dict()["prosody"]["executor"] == "piper-expressive"


def test_plan_distinguishes_requested_and_supported_dimensions() -> None:
    capabilities = VoiceCapabilities(
        "en_GB-expressive-medium",
        executor="piper-expressive",
        dimensions=frozenset({"duration", "pitch", "energy"}),
        phoneme_markers=frozenset({"↑", "↓"}),
        legacy=False,
    )
    plan = ProsodyPlan(
        text="Is this important?",
        language_family="en",
        language_code="en_GB",
        requested_dimensions=frozenset({"duration", "pitch", "emphasis"}),
        unavailable_signals=("discourse_role",),
        capabilities=capabilities,
    )

    assert plan.supported_dimensions() == frozenset({"duration", "pitch"})
    serialized = plan.to_dict()
    assert serialized["requested_dimensions"] == ["duration", "emphasis", "pitch"]
    assert serialized["supported_dimensions"] == ["duration", "pitch"]
    assert serialized["unavailable_signals"] == ["discourse_role"]


def test_executor_negotiation_never_maps_unsupported_controls_to_legacy_scales() -> None:
    plan = ProsodyPlan(
        text="Important.",
        language_family="en",
        requested_dimensions=frozenset({"duration", "pitch", "energy"}),
        capabilities=VoiceCapabilities.from_mapping("legacy"),
    )

    execution = negotiate_prosody(plan)

    assert execution.executor == "piper-legacy"
    assert execution.applied_dimensions == frozenset({"duration"})
    assert execution.unavailable_dimensions == frozenset({"pitch", "energy"})
    assert not execution.legacy_fallback


def test_plan_serialization_round_trip_preserves_capabilities_and_events() -> None:
    original = ProsodyPlan(
        text="Is this important?",
        language_family="en",
        language_code="en_GB",
        segments=(
            ProsodySegment(
                kind="text",
                text="Is this important?",
                events=(
                    ProsodyEvent(
                        kind="pitch",
                        dimension="pitch",
                        value=0.2,
                        source="external",
                    ),
                ),
            ),
        ),
        events=(
            ProsodyEvent(kind="pitch", dimension="pitch", value=0.2),
        ),
        requested_dimensions=frozenset({"duration", "pitch"}),
        capabilities=VoiceCapabilities(
            "expressive",
            executor="piper-expressive",
            dimensions=frozenset({"duration", "pitch"}),
            legacy=False,
        ),
    )

    restored = ProsodyPlan.from_dict(original.to_dict())

    assert restored.to_dict() == original.to_dict()


def test_external_events_are_validated_and_serialized() -> None:
    events = events_from_mappings(
        [
            {
                "kind": "emphasis",
                "dimension": "energy",
                "value": 0.6,
                "text_start": 3,
                "text_end": 12,
                "confidence": 0.8,
            }
        ]
    )

    assert events == (
        ProsodyEvent(
            kind="emphasis",
            dimension="energy",
            value=0.6,
            text_start=3,
            text_end=12,
            source="external",
            confidence=0.8,
        ),
    )


@pytest.mark.parametrize(
    "value",
    [
        {"kind": "unknown"},
        {"kind": "pitch", "dimension": "unknown"},
        {"kind": "pause", "confidence": 1.1},
    ],
)
def test_invalid_event_mappings_are_rejected(value: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        events_from_mappings([value])


def test_declared_marker_allowlist_preserves_only_supported_annotations() -> None:
    groups = [["m", "ˈ", "a", "↑", "1", "."]]

    assert filter_unsupported_phoneme_markers(groups, ["ˈ", "1"]) == [
        ["m", "ˈ", "a", "1", "."]
    ]


def test_legacy_marker_stream_is_unchanged_without_explicit_metadata() -> None:
    groups = [["m", "ˈ", "a", "↑"]]

    assert filter_unsupported_phoneme_markers(groups, []) == [["m", "a"]]
