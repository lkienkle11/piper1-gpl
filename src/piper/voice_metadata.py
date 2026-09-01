"""Human-readable display metadata for Piper voices."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_METADATA_PATH = Path(__file__).with_name("voice_metadata.json")


def _load_metadata() -> Mapping[str, Mapping[str, Any]]:
    try:
        with _METADATA_PATH.open("r", encoding="utf-8") as metadata_file:
            data = json.load(metadata_file)
    except (OSError, ValueError):
        return {}
    voices = data.get("voices", {}) if isinstance(data, dict) else {}
    return voices if isinstance(voices, dict) else {}


VOICE_DISPLAY_METADATA = _load_metadata()


def humanize_voice_name(value: str) -> str:
    """Turn a dataset-style name into readable title text."""
    words = re.sub(r"[_-]+", " ", str(value).strip()).split()
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def voice_family_id(language_code: str, voice_name: str) -> str:
    """Return the quality-independent identity used by the UI."""
    return f"{language_code}-{voice_name}"


def display_metadata(
    language: Mapping[str, Any], voice_name: str, speaker_count: int
) -> Dict[str, Any]:
    """Return metadata with a truthful neutral fallback for unknown voices."""
    language_code = str(language.get("code", ""))
    family_id = voice_family_id(language_code, voice_name)
    configured = VOICE_DISPLAY_METADATA.get(family_id, {})
    language_name = str(
        language.get("name_english") or language.get("name_native") or "Piper"
    )
    country = str(language.get("country_english") or "")
    traits = [str(item) for item in configured.get("traits", []) if str(item).strip()]
    if not traits:
        traits = [language_name]
        if country:
            traits.append(country)
        traits.append("Multi-speaker" if speaker_count > 1 else "Single-speaker")
    display_name = str(
        configured.get("display_name") or humanize_voice_name(voice_name)
    )
    return {
        "family_id": family_id,
        "display_name": humanize_voice_name(display_name),
        "traits": traits,
        "speaker_label": str(configured.get("speaker_label") or "Speaker {ordinal}"),
    }


def voice_display_label(
    voice: Mapping[str, Any],
    speaker_name: Optional[str] = None,
    speaker_id: Optional[int] = None,
    speaker_ordinal: Optional[int] = None,
) -> str:
    """Build a descriptive label without exposing an opaque speaker ID alone."""
    language = voice.get("language", {})
    speaker_count = int(voice.get("num_speakers", 1) or 1)
    metadata = display_metadata(
        language, str(voice.get("name", "Piper voice")), speaker_count
    )
    label = metadata["display_name"]
    if speaker_count > 1:
        ordinal = (
            speaker_ordinal if speaker_ordinal is not None else speaker_id or 0
        ) + 1
        speaker_title = metadata["speaker_label"].replace("{ordinal}", str(ordinal))
        opaque_speaker = bool(
            speaker_name
            and re.fullmatch(
                r"(?:p\d+|vivos(?:spk|dev)\d+|[a-z]{1,5}\d+)", speaker_name, re.I
            )
        )
        if speaker_name and not speaker_name.isdigit() and not opaque_speaker:
            speaker_title = humanize_voice_name(speaker_name)
        label = f"{label} {speaker_title}"
    traits = ", ".join(metadata["traits"])
    return f"{label} ({traits})"


def metadata_missing_for_catalog(voices: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Return quality-independent catalog families without explicit metadata."""
    missing = set()
    for voice_id, voice in voices.items():
        language = voice.get("language", {})
        code = str(language.get("code", voice_id.split("-")[0]))
        name = str(voice.get("name", ""))
        family_id = voice_family_id(code, name)
        if family_id not in VOICE_DISPLAY_METADATA:
            missing.add(family_id)
    return sorted(missing)
