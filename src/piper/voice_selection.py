"""Automatic text analysis and Piper voice selection for the HTTP server."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

QUALITY_PRIORITY = {"medium": 0, "high": 1, "low": 2, "x_low": 3}
PIPER_LANGUAGE_FAMILIES = {
    "ar",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "is",
    "it",
    "ja",
    "ka",
    "kk",
    "lb",
    "lv",
    "ml",
    "ne",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "sw",
    "te",
    "tr",
    "uk",
    "vi",
    "zh",
}
DETECTOR_LANGUAGE_ALIASES = {"no": "nb"}
DETECTOR_LANGUAGE_ALIASES_REVERSE = {
    detector: piper for piper, detector in DETECTOR_LANGUAGE_ALIASES.items()
}
AUTO_LOCALE_DEFAULTS = {
    "en": "en_US",
    "es": "es_ES",
    "nl": "nl_NL",
    "pt": "pt_BR",
    "vi": "vi_VN",
}

EMOTION_PROFILES: Mapping[str, Mapping[str, float]] = {
    "neutral": {
        "length_scale": 1.0,
        "noise_scale": 0.667,
        "noise_w_scale": 0.8,
    },
    "happy": {
        "length_scale": 0.95,
        "noise_scale": 0.72,
        "noise_w_scale": 0.85,
    },
    "sad": {
        "length_scale": 1.15,
        "noise_scale": 0.55,
        "noise_w_scale": 0.65,
    },
    "angry": {
        "length_scale": 0.9,
        "noise_scale": 0.8,
        "noise_w_scale": 0.9,
    },
    "excited": {
        "length_scale": 0.85,
        "noise_scale": 0.78,
        "noise_w_scale": 0.95,
    },
}

CONTEXT_LENGTH_MULTIPLIERS = {
    "conversation": 1.0,
    "narration": 1.05,
    "question": 0.98,
    "announcement": 0.92,
}


@dataclass(frozen=True)
class LanguageRuleProfile:
    """Language-specific words used by the extensible text classifier."""

    happy: Set[str]
    sad: Set[str]
    angry: Set[str]
    excited: Set[str]
    question: Set[str]
    announcement: Set[str]
    conversation: Set[str]


LANGUAGE_RULES: Mapping[str, LanguageRuleProfile] = {
    "en": LanguageRuleProfile(
        happy={
            "amazing",
            "awesome",
            "beautiful",
            "congratulations",
            "delighted",
            "excellent",
            "glad",
            "good",
            "great",
            "happy",
            "love",
            "wonderful",
        },
        sad={
            "alone",
            "cry",
            "disappointed",
            "grief",
            "lonely",
            "miss",
            "regret",
            "sad",
            "sorry",
            "unhappy",
        },
        angry={
            "angry",
            "damn",
            "furious",
            "hate",
            "idiot",
            "mad",
            "never",
            "outrageous",
            "stupid",
            "unacceptable",
        },
        excited={
            "can't wait",
            "excited",
            "fantastic",
            "incredible",
            "let's go",
            "surprise",
            "unbelievable",
            "wow",
        },
        question={
            "can",
            "could",
            "did",
            "do",
            "how",
            "is",
            "what",
            "when",
            "where",
            "which",
            "who",
            "why",
            "would",
        },
        announcement={
            "alert",
            "announcement",
            "attention",
            "breaking",
            "important",
            "notice",
            "warning",
        },
        conversation={
            "hello",
            "hey",
            "hi",
            "i",
            "please",
            "thanks",
            "we",
            "you",
        },
    ),
    "vi": LanguageRuleProfile(
        happy={
            "hạnh phúc",
            "hay",
            "tuyệt",
            "tuyệt vời",
            "vui",
            "yêu",
            "đẹp",
            "chúc mừng",
        },
        sad={
            "buồn",
            "cô đơn",
            "khóc",
            "hối tiếc",
            "nhớ",
            "thất vọng",
            "tiếc",
            "xin lỗi",
        },
        angry={
            "bực",
            "đáng ghét",
            "giận",
            "không thể chấp nhận",
            "ngu",
            "tức",
            "vô lý",
        },
        excited={
            "bất ngờ",
            "háo hức",
            "không thể tin",
            "quá đã",
            "tuyệt quá",
            "wow",
        },
        question={
            "ai",
            "bao giờ",
            "bao nhiêu",
            "có",
            "gì",
            "khi nào",
            "làm sao",
            "nào",
            "ở đâu",
            "sao",
            "tại sao",
            "thế nào",
        },
        announcement={
            "cảnh báo",
            "chú ý",
            "khẩn cấp",
            "quan trọng",
            "thông báo",
            "tin mới",
        },
        conversation={
            "bạn",
            "chào",
            "chúng ta",
            "cảm ơn",
            "mình",
            "tôi",
            "xin chào",
        },
    ),
}


def _tokens(text: str) -> Set[str]:
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


def _matches(text: str, tokens: Set[str], terms: Iterable[str]) -> bool:
    lowered = text.casefold()
    return any((term in lowered) if " " in term else (term in tokens) for term in terms)


def classify_text(text: str, language_family: str) -> Tuple[str, str]:
    """Classify emotion and context with language-specific, extensible rules."""
    stripped = text.strip()
    tokens = _tokens(stripped)
    profile = LANGUAGE_RULES.get(language_family)
    letters = [char for char in stripped if char.isalpha()]
    uppercase_ratio = (
        sum(char.isupper() for char in letters) / len(letters) if letters else 0.0
    )

    angry_match = bool(profile and _matches(stripped, tokens, profile.angry))
    excited_match = bool(profile and _matches(stripped, tokens, profile.excited))
    sad_match = bool(profile and _matches(stripped, tokens, profile.sad))
    happy_match = bool(profile and _matches(stripped, tokens, profile.happy))

    if angry_match or (len(letters) >= 8 and uppercase_ratio >= 0.65 and "!" in text):
        emotion = "angry"
    elif excited_match or "!!" in text:
        emotion = "excited"
    elif sad_match:
        emotion = "sad"
    elif happy_match or any(mark in text for mark in ("😊", "😀", "❤️", "❤")):
        emotion = "happy"
    else:
        emotion = "neutral"

    lowered = stripped.casefold()
    question_match = bool(
        profile
        and any(
            lowered == term
            or lowered.startswith(f"{term} ")
            or lowered.startswith(f"{term},")
            for term in profile.question
        )
    )
    announcement_match = bool(
        profile and _matches(stripped, tokens, profile.announcement)
    )
    conversation_match = bool(
        profile and _matches(stripped, tokens, profile.conversation)
    )

    if "?" in text or question_match:
        context = "question"
    elif announcement_match or (
        len(letters) >= 8 and uppercase_ratio >= 0.65 and "!" in text
    ):
        context = "announcement"
    elif conversation_match or any(mark in text for mark in ('"', "“", "”", "‘", "’")):
        context = "conversation"
    else:
        context = "narration"

    return emotion, context


def prosody_for(emotion: str, context: str) -> Dict[str, float]:
    """Return bounded synthesis settings for an emotion/context pair."""
    profile = EMOTION_PROFILES.get(emotion, EMOTION_PROFILES["neutral"])
    length_scale = profile["length_scale"] * CONTEXT_LENGTH_MULTIPLIERS.get(
        context, 1.0
    )
    return {
        "length_scale": round(min(1.25, max(0.75, length_scale)), 4),
        "noise_scale": round(min(0.85, max(0.45, profile["noise_scale"])), 4),
        "noise_w_scale": round(min(1.0, max(0.6, profile["noise_w_scale"])), 4),
    }


def normalize_voice_catalog(
    voices: Mapping[str, Mapping[str, Any]], installed_ids: Set[str]
) -> List[Dict[str, Any]]:
    """Normalize voices.json entries for the web UI and resolver."""
    normalized: List[Dict[str, Any]] = []
    for voice_id, raw_voice in voices.items():
        language = dict(raw_voice.get("language", {}))
        model_size = 0
        for file_name, file_info in raw_voice.get("files", {}).items():
            if file_name.endswith(".onnx"):
                model_size = int(file_info.get("size_bytes", 0))
                break

        speaker_id_map = dict(raw_voice.get("speaker_id_map", {}))
        normalized.append(
            {
                "key": raw_voice.get("key", voice_id),
                "language": {
                    "code": language.get("code", voice_id.split("-")[0]),
                    "family": language.get("family", voice_id.split("_")[0].lower()),
                    "region": language.get("region", ""),
                    "name_native": language.get("name_native", ""),
                    "name_english": language.get("name_english", ""),
                    "country_english": language.get("country_english", ""),
                },
                "name": raw_voice.get("name", voice_id),
                "quality": raw_voice.get("quality", ""),
                "num_speakers": int(
                    raw_voice.get("num_speakers", max(1, len(speaker_id_map)))
                ),
                "speakers": speaker_id_map,
                "model_size_bytes": model_size,
                "installed": voice_id in installed_ids,
            }
        )

    return sorted(
        normalized,
        key=lambda voice: (
            voice["language"]["name_english"],
            voice["language"]["code"],
            voice["name"],
            QUALITY_PRIORITY.get(voice["quality"], 99),
            voice["key"],
        ),
    )


def catalog_entry_from_config(
    voice_id: str, config: Mapping[str, Any], installed: bool = True
) -> Dict[str, Any]:
    """Create a normalized entry from an installed ONNX config."""
    language = dict(config.get("language", {}))
    speaker_id_map = dict(config.get("speaker_id_map", {}))
    parts = voice_id.split("-")
    return {
        "key": voice_id,
        "language": {
            "code": language.get("code", parts[0]),
            "family": language.get("family", parts[0].split("_")[0].lower()),
            "region": language.get("region", ""),
            "name_native": language.get("name_native", ""),
            "name_english": language.get("name_english", ""),
            "country_english": language.get("country_english", ""),
        },
        "name": config.get("dataset", parts[1] if len(parts) > 1 else voice_id),
        "quality": config.get("audio", {}).get(
            "quality", parts[-1] if len(parts) > 2 else ""
        ),
        "num_speakers": int(config.get("num_speakers", max(1, len(speaker_id_map)))),
        "speakers": speaker_id_map,
        "model_size_bytes": 0,
        "installed": installed,
    }


def resolve_voice(
    language_family: str,
    voices: Sequence[Mapping[str, Any]],
    default_voice_id: str,
) -> Optional[Dict[str, Any]]:
    """Choose a deterministic installed or catalog voice for a language."""
    candidates = [
        dict(voice)
        for voice in voices
        if voice.get("language", {}).get("family") == language_family
    ]
    if not candidates:
        return None

    for voice in candidates:
        if voice["key"] == default_voice_id and voice.get("installed"):
            return voice

    installed = [voice for voice in candidates if voice.get("installed")]
    if installed:
        return min(
            installed,
            key=lambda voice: (
                QUALITY_PRIORITY.get(voice.get("quality", ""), 99),
                voice["key"],
            ),
        )

    preferred_locale = AUTO_LOCALE_DEFAULTS.get(language_family)
    preferred = [
        voice
        for voice in candidates
        if voice.get("language", {}).get("code") == preferred_locale
    ]
    if preferred:
        candidates = preferred

    return min(
        candidates,
        key=lambda voice: (
            QUALITY_PRIORITY.get(voice.get("quality", ""), 99),
            voice["key"],
        ),
    )


class TextAnalyzer:
    """Lazily detect the dominant language and classify text style."""

    def __init__(self) -> None:
        self._detector: Any = None
        self._detector_families: Tuple[str, ...] = ()

    def _get_detector(self, language_families: Iterable[str]) -> Any:
        piper_families = set(language_families) | PIPER_LANGUAGE_FAMILIES
        detector_families = {
            DETECTOR_LANGUAGE_ALIASES.get(family, family) for family in piper_families
        }
        families = tuple(sorted(detector_families))
        if self._detector is not None and families == self._detector_families:
            return self._detector

        from lingua import Language, LanguageDetectorBuilder

        languages = [
            language
            for language in Language
            if language.iso_code_639_1
            and language.iso_code_639_1.name.casefold() in families
        ]
        if not languages:
            raise ValueError("No supported languages are available for detection")

        self._detector = LanguageDetectorBuilder.from_languages(*languages).build()
        self._detector_families = families
        return self._detector

    def analyze(
        self,
        text: str,
        voices: Sequence[Mapping[str, Any]],
        default_voice_id: str,
    ) -> Dict[str, Any]:
        """Analyze text and resolve the most suitable Piper voice."""
        default_voice = next(
            (voice for voice in voices if voice["key"] == default_voice_id), None
        )
        default_family = (
            default_voice.get("language", {}).get("family", "en")
            if default_voice
            else "en"
        )
        letter_count = sum(char.isalpha() for char in text)
        fallback_reason: Optional[str] = None
        confidence = 0.0
        language_family = default_family

        if letter_count < 3:
            fallback_reason = "text_too_short"
        else:
            families = {
                voice.get("language", {}).get("family")
                for voice in voices
                if voice.get("language", {}).get("family")
            }
            detector = self._get_detector(families)
            confidence_values = detector.compute_language_confidence_values(text)
            if confidence_values:
                detected_language, confidence = confidence_values[0]
                detected_family = detected_language.iso_code_639_1.name.casefold()
                language_family = DETECTOR_LANGUAGE_ALIASES_REVERSE.get(
                    detected_family, detected_family
                )

            if confidence < 0.55:
                language_family = default_family
                fallback_reason = "low_confidence"

        emotion, context = classify_text(text, language_family)
        voice = resolve_voice(language_family, voices, default_voice_id)
        if voice is None:
            fallback_reason = fallback_reason or "no_voice_for_language"

        return {
            "language": {
                "family": language_family,
                "code": voice.get("language", {}).get("code") if voice else None,
                "name": (
                    voice.get("language", {}).get("name_english") if voice else None
                ),
                "confidence": round(float(confidence), 4),
            },
            "context": context,
            "emotion": emotion,
            "voice": voice,
            "prosody": prosody_for(emotion, context),
            "installed": bool(voice and voice.get("installed")),
            "needs_download": bool(voice and not voice.get("installed")),
            "fallback_reason": fallback_reason,
        }
