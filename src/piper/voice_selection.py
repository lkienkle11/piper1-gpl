"""Automatic text analysis and Piper voice selection for the HTTP server."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .voice_metadata import display_metadata

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
    "en": "en_GB",
    "es": "es_ES",
    "nl": "nl_NL",
    "pt": "pt_BR",
    "vi": "vi_VN",
}
AUTO_VOICE_DEFAULTS = {"en": "en_GB-cori-high"}

VOICE_SPEED_PRESETS = {"slow": 0.85, "normal": 1.0, "fast": 1.15}
CONTEXT_PAUSES = {
    "fragment": 0.0,
    "conversation": 0.08,
    "narration": 0.14,
    "announcement": 0.12,
    "question": 0.22,
}
PARAGRAPH_PAUSE = 0.30

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
EMOTION_VALUES = frozenset({"auto", *EMOTION_PROFILES})

CONTEXT_LENGTH_MULTIPLIERS = {
    "fragment": 0.95,
    "conversation": 1.0,
    "narration": 1.05,
    "question": 0.98,
    "announcement": 0.92,
}


class InvalidScriptError(ValueError):
    """Raised when a narration stage direction is invalid."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"Line {line}: {message}")
        self.line = line
        self.reason = message


@dataclass(frozen=True)
class ScriptSegment:
    """A parsed narration text or explicit pause segment."""

    kind: str
    line: int
    text: str = ""
    voice_speed: float = 1.0
    emotion: str = "auto"
    narration_mode: str = "normal"
    paragraph_end: bool = False
    pause: float = 0.0


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


_DIRECTIVE_RE = re.compile(r"^\(\s*([a-z-]+)\s*:\s*([^)]*?)\s*\)$", re.I)
_CLOSING_PUNCTUATION = set("\"'”’)]}")
_NON_TERMINAL_ABBREVIATIONS = {
    "dr",
    "e.g",
    "etc",
    "i.e",
    "jr",
    "mr",
    "mrs",
    "ms",
    "prof",
    "sr",
    "st",
    "vs",
}


def _split_sentences(text: str) -> List[str]:
    """Split paragraph text at terminal punctuation, preserving raw IPA blocks."""
    sentences: List[str] = []
    start = 0
    index = 0
    in_phonemes = False
    while index < len(text):
        if text.startswith("[[", index):
            in_phonemes = True
            index += 2
            continue
        if in_phonemes and text.startswith("]]", index):
            in_phonemes = False
            index += 2
            continue

        char = text[index]
        if in_phonemes or char not in ".!?…":
            index += 1
            continue

        boundary = True
        if char == ".":
            before = text[start:index].rstrip()
            token_match = re.search(r"([A-Za-z](?:[A-Za-z.]*)?)$", before)
            token = token_match.group(1).casefold().rstrip(".") if token_match else ""
            next_nonspace = re.search(r"\S", text[index + 1 :])
            next_char = text[index + 1 + next_nonspace.start()] if next_nonspace else ""
            if (
                token in _NON_TERMINAL_ABBREVIATIONS
                or (len(token) == 1 and token.isalpha())
                or (next_char and next_char.islower())
            ):
                boundary = False

        if not boundary:
            index += 1
            continue

        end = index + 1
        while end < len(text) and text[end] in ".!?…":
            end += 1
        while end < len(text) and text[end] in _CLOSING_PUNCTUATION:
            end += 1
        if end < len(text) and not text[end].isspace():
            index = end
            continue

        sentence = text[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = end
        index = end

    remainder = text[start:].strip()
    if remainder:
        sentences.append(remainder)
    return sentences


def _parse_voice_speed(value: str, line: int) -> float:
    preset = VOICE_SPEED_PRESETS.get(value.casefold())
    if preset is not None:
        return preset
    try:
        speed = float(value)
    except ValueError as err:
        raise InvalidScriptError(
            line, "voice-speed must be slow, normal, fast, or a number"
        ) from err
    if not 0.5 <= speed <= 2.0:
        raise InvalidScriptError(line, "voice-speed must be between 0.5 and 2.0")
    return speed


def _parse_emotion(value: str, line: int) -> str:
    emotion = value.casefold()
    if emotion not in EMOTION_VALUES:
        choices = ", ".join(sorted(EMOTION_VALUES))
        raise InvalidScriptError(line, f"emotion must be one of: {choices}")
    return emotion


def parse_script(
    text: str,
    base_voice_speed: float = 1.0,
    base_emotion: str = "auto",
) -> List[ScriptSegment]:
    """Parse narration paragraphs and Narakeet-style stage directions."""
    if not 0.5 <= base_voice_speed <= 2.0:
        raise InvalidScriptError(1, "voice_speed must be between 0.5 and 2.0")
    base_emotion = _parse_emotion(base_emotion.strip(), 1)

    blocks: List[Tuple[int, str]] = []
    block_lines: List[str] = []
    block_start = 1
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if raw_line.strip():
            if not block_lines:
                block_start = line_number
            block_lines.append(raw_line.strip())
        elif block_lines:
            blocks.append((block_start, " ".join(block_lines)))
            block_lines = []
    if block_lines:
        blocks.append((block_start, " ".join(block_lines)))

    voice_speed = base_voice_speed
    emotion = base_emotion
    narration_mode = "normal"
    segments: List[ScriptSegment] = []
    for block_line, block in blocks:
        directive = _DIRECTIVE_RE.fullmatch(block)
        if directive:
            name = directive.group(1).casefold()
            value = directive.group(2).strip()
            if name == "voice-speed":
                voice_speed = _parse_voice_speed(value, block_line)
            elif name == "emotion":
                emotion = _parse_emotion(value, block_line)
            elif name == "pause":
                try:
                    pause = float(value)
                except ValueError as err:
                    raise InvalidScriptError(
                        block_line, "pause must be a number of seconds"
                    ) from err
                if not 0.0 <= pause <= 10.0:
                    raise InvalidScriptError(
                        block_line, "pause must be between 0 and 10 seconds"
                    )
                segments.append(
                    ScriptSegment(kind="pause", line=block_line, pause=pause)
                )
            elif name == "narration-mode":
                value = value.casefold()
                if value not in ("normal", "fragment"):
                    raise InvalidScriptError(
                        block_line, "narration-mode must be normal or fragment"
                    )
                narration_mode = value
            else:
                raise InvalidScriptError(
                    block_line, f"unknown stage direction '{name}'"
                )
            continue

        if re.match(r"^\s*\([a-z-]+\s*:", block, flags=re.I):
            raise InvalidScriptError(
                block_line,
                "stage directions must be valid and in a separate paragraph",
            )

        sentences = _split_sentences(block)
        for sentence_index, sentence in enumerate(sentences):
            segments.append(
                ScriptSegment(
                    kind="text",
                    line=block_line,
                    text=sentence,
                    voice_speed=voice_speed,
                    emotion=emotion,
                    narration_mode=narration_mode,
                    paragraph_end=sentence_index == len(sentences) - 1,
                )
            )

    if not any(segment.kind == "text" for segment in segments):
        raise InvalidScriptError(1, "script contains no narration text")
    return segments


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
        language_data = {
            "code": language.get("code", voice_id.split("-")[0]),
            "family": language.get("family", voice_id.split("_")[0].lower()),
            "region": language.get("region", ""),
            "name_native": language.get("name_native", ""),
            "name_english": language.get("name_english", ""),
            "country_english": language.get("country_english", ""),
        }
        voice_name = raw_voice.get("name", voice_id)
        speaker_count = int(raw_voice.get("num_speakers", max(1, len(speaker_id_map))))
        presentation = display_metadata(language_data, str(voice_name), speaker_count)
        normalized.append(
            {
                "key": raw_voice.get("key", voice_id),
                "language": language_data,
                "name": voice_name,
                "voice_family_id": presentation["family_id"],
                "display_name": presentation["display_name"],
                "display_traits": presentation["traits"],
                "speaker_label": presentation["speaker_label"],
                "quality": raw_voice.get("quality", ""),
                "num_speakers": speaker_count,
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
    language_data = {
        "code": language.get("code", parts[0]),
        "family": language.get("family", parts[0].split("_")[0].lower()),
        "region": language.get("region", ""),
        "name_native": language.get("name_native", ""),
        "name_english": language.get("name_english", ""),
        "country_english": language.get("country_english", ""),
    }
    voice_name = config.get("dataset", parts[1] if len(parts) > 1 else voice_id)
    speaker_count = int(config.get("num_speakers", max(1, len(speaker_id_map))))
    presentation = display_metadata(language_data, str(voice_name), speaker_count)
    return {
        "key": voice_id,
        "language": language_data,
        "name": voice_name,
        "voice_family_id": presentation["family_id"],
        "display_name": presentation["display_name"],
        "display_traits": presentation["traits"],
        "speaker_label": presentation["speaker_label"],
        "quality": config.get("audio", {}).get(
            "quality", parts[-1] if len(parts) > 2 else ""
        ),
        "num_speakers": speaker_count,
        "speakers": speaker_id_map,
        "model_size_bytes": 0,
        "installed": installed,
    }


def resolve_voice(
    language_family: str,
    voices: Sequence[Mapping[str, Any]],
    default_voice_id: str,
    *,
    language_code: Optional[str] = None,
    voice_family_id: Optional[str] = None,
    quality: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Choose a deterministic installed or catalog voice for a language."""
    candidates = [
        dict(voice)
        for voice in voices
        if voice.get("language", {}).get("family") == language_family
    ]
    if language_code:
        candidates = [
            voice
            for voice in candidates
            if voice.get("language", {}).get("code") == language_code
        ]
    if voice_family_id:
        candidates = [
            voice
            for voice in candidates
            if voice.get("voice_family_id") == voice_family_id
            or voice.get("key") == voice_family_id
        ]
    if quality:
        candidates = [voice for voice in candidates if voice.get("quality") == quality]
    if not candidates:
        return None

    if not voice_family_id and not quality:
        preferred_voice_id = AUTO_VOICE_DEFAULTS.get(language_family)
        if preferred_voice_id:
            for voice in candidates:
                if voice["key"] == preferred_voice_id:
                    return voice

    preferred_locale = language_code or AUTO_LOCALE_DEFAULTS.get(language_family)
    preferred = [
        voice
        for voice in candidates
        if voice.get("language", {}).get("code") == preferred_locale
    ]
    if preferred:
        candidates = preferred

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

    return min(
        candidates,
        key=lambda voice: (
            QUALITY_PRIORITY.get(voice.get("quality", ""), 99),
            voice["key"],
        ),
    )


def normalize_selection(selection: Any) -> Dict[str, Any]:
    """Validate the independent automatic/manual selection dimensions."""
    value = selection if isinstance(selection, Mapping) else {}

    def choice(name: str, allowed: Optional[Set[str]] = None) -> str:
        selected = value.get(name, "auto")
        if not isinstance(selected, str):
            raise ValueError(f"selection.{name} must be a string")
        selected = selected.strip()
        if not selected:
            return "auto"
        if allowed and selected not in allowed and selected != "auto":
            raise ValueError(f"selection.{name} contains an unsupported value")
        return selected

    speaker = value.get("speaker")
    speaker_name: Optional[str] = None
    speaker_id: Optional[int] = None
    if speaker is not None:
        if not isinstance(speaker, Mapping):
            raise ValueError("selection.speaker must be an object")
        raw_name = speaker.get("name")
        if raw_name is not None:
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise ValueError("selection.speaker.name must be a non-empty string")
            speaker_name = raw_name.strip()
        raw_id = speaker.get("id")
        if raw_id is not None:
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id < 0:
                raise ValueError("selection.speaker.id must be a non-negative integer")
            speaker_id = raw_id
    return {
        "language": choice("language"),
        "voice": choice("voice"),
        "quality": choice("quality", set(QUALITY_PRIORITY)),
        "speaker": {"name": speaker_name, "id": speaker_id},
        "emotion": choice("emotion", set(EMOTION_VALUES)),
    }


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
        *,
        delivery: str = "adaptive",
        voice_speed: float = 1.0,
        manual_voice_id: Optional[str] = None,
        emotion: str = "auto",
        language_code: Optional[str] = None,
        voice_family_id: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze text and resolve the most suitable Piper voice."""
        if delivery not in ("adaptive", "fixed"):
            raise ValueError("delivery must be adaptive or fixed")
        emotion_mode = emotion.strip().casefold()
        if emotion_mode not in EMOTION_VALUES:
            choices = ", ".join(sorted(EMOTION_VALUES))
            raise ValueError(f"emotion must be one of: {choices}")
        parsed_segments = parse_script(text, voice_speed, emotion_mode)
        narration_text = " ".join(
            segment.text for segment in parsed_segments if segment.kind == "text"
        )
        default_voice = next(
            (voice for voice in voices if voice["key"] == default_voice_id), None
        )
        default_family = (
            default_voice.get("language", {}).get("family", "en")
            if default_voice
            else "en"
        )
        letter_count = sum(char.isalpha() for char in narration_text)
        fallback_reason: Optional[str] = None
        confidence = 0.0
        language_family = default_family
        voice: Optional[Dict[str, Any]] = None

        if manual_voice_id:
            voice = next(
                (dict(item) for item in voices if item["key"] == manual_voice_id), None
            )
            if voice is None:
                raise ValueError(f"Unknown voice: {manual_voice_id}")
            language_family = voice.get("language", {}).get("family", default_family)
            confidence = 1.0
        elif voice_family_id:
            pinned = [
                voice
                for voice in voices
                if voice.get("voice_family_id") == voice_family_id
                or voice.get("key") == voice_family_id
            ]
            if not pinned:
                raise ValueError(f"Unknown voice family: {voice_family_id}")
            if language_code and any(
                voice.get("language", {}).get("code") != language_code
                for voice in pinned
            ):
                raise ValueError(
                    f"Voice family {voice_family_id} is not available for language {language_code}"
                )
            language_family = (
                pinned[0].get("language", {}).get("family", default_family)
            )
            confidence = 1.0
        elif language_code:
            language_candidates = [
                voice
                for voice in voices
                if voice.get("language", {}).get("code") == language_code
            ]
            if not language_candidates:
                raise ValueError(f"Unknown language: {language_code}")
            language_family = (
                language_candidates[0].get("language", {}).get("family", default_family)
            )
            confidence = 1.0
        elif letter_count < 3:
            fallback_reason = "text_too_short"
        else:
            families = {
                voice.get("language", {}).get("family")
                for voice in voices
                if voice.get("language", {}).get("family")
            }
            detector = self._get_detector(families)
            confidence_values = detector.compute_language_confidence_values(
                narration_text
            )
            if confidence_values:
                detected_language, confidence = confidence_values[0]
                detected_family = detected_language.iso_code_639_1.name.casefold()
                language_family = DETECTOR_LANGUAGE_ALIASES_REVERSE.get(
                    detected_family, detected_family
                )

            if confidence < 0.55:
                language_family = default_family
                fallback_reason = "low_confidence"

        detected_emotion, context = classify_text(narration_text, language_family)
        overall_emotion = detected_emotion if emotion_mode == "auto" else emotion_mode
        if voice is None:
            voice = resolve_voice(
                language_family,
                voices,
                default_voice_id,
                language_code=language_code,
                voice_family_id=voice_family_id,
                quality=quality,
            )
        if voice is None:
            if voice_family_id and quality:
                raise ValueError(
                    f"Voice family {voice_family_id} is not available at quality {quality}"
                )
            if language_code and quality:
                raise ValueError(
                    f"No voice is available for language {language_code} at quality {quality}"
                )
            fallback_reason = fallback_reason or "no_voice_for_language"

        text_segment_indexes = [
            index
            for index, segment in enumerate(parsed_segments)
            if segment.kind == "text"
        ]
        last_text_index = text_segment_indexes[-1]
        analyzed_segments: List[Dict[str, Any]] = []
        for index, segment in enumerate(parsed_segments):
            if segment.kind == "pause":
                analyzed_segments.append(
                    {
                        "kind": "pause",
                        "line": segment.line,
                        "pause": segment.pause,
                    }
                )
                continue

            detected_segment_emotion, segment_context = classify_text(
                segment.text, language_family
            )
            segment_emotion = (
                detected_segment_emotion
                if segment.emotion == "auto"
                else segment.emotion
            )
            word_count = len(_tokens(segment.text))
            has_terminal = bool(re.search(r"[.!?…][\"'”’\])}]*$", segment.text.strip()))
            if segment.narration_mode == "fragment" or (
                not has_terminal and word_count <= 12
            ):
                segment_context = "fragment"

            if delivery == "adaptive":
                segment_prosody = prosody_for(segment_emotion, segment_context)
            elif segment.emotion != "auto":
                segment_prosody = prosody_for(segment_emotion, "conversation")
            else:
                segment_prosody = prosody_for("neutral", "conversation")
            segment_prosody["length_scale"] = round(
                segment_prosody["length_scale"] / segment.voice_speed, 4
            )

            pause_after = 0.0
            if delivery == "adaptive" and index != last_text_index:
                pause_after = CONTEXT_PAUSES.get(segment_context, 0.0)
                if segment.paragraph_end:
                    pause_after = max(pause_after, PARAGRAPH_PAUSE)

            analyzed_segments.append(
                {
                    "kind": "text",
                    "line": segment.line,
                    "text": segment.text,
                    "context": segment_context,
                    "emotion": segment_emotion,
                    "emotion_override": (
                        None if segment.emotion == "auto" else segment.emotion
                    ),
                    "voice_speed": segment.voice_speed,
                    "narration_mode": segment.narration_mode,
                    "paragraph_end": segment.paragraph_end,
                    "prosody": segment_prosody,
                    "pause_after": round(pause_after, 3),
                }
            )

        text_details = [
            segment for segment in analyzed_segments if segment["kind"] == "text"
        ]
        if len(text_details) == 1:
            overall_emotion = text_details[0]["emotion"]
            context = text_details[0]["context"]
        elif text_details and len({item["emotion"] for item in text_details}) == 1:
            overall_emotion = text_details[0]["emotion"]
        overall_prosody = prosody_for(
            (
                overall_emotion
                if delivery == "adaptive" or emotion_mode != "auto"
                else "neutral"
            ),
            context if delivery == "adaptive" else "conversation",
        )
        overall_prosody["length_scale"] = round(
            overall_prosody["length_scale"] / voice_speed, 4
        )

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
            "emotion": overall_emotion,
            "emotion_override": None if emotion_mode == "auto" else emotion_mode,
            "voice": voice,
            "delivery": delivery,
            "voice_speed": voice_speed,
            "prosody": overall_prosody,
            "segments": analyzed_segments,
            "installed": bool(voice and voice.get("installed")),
            "needs_download": bool(voice and not voice.get("installed")),
            "fallback_reason": fallback_reason,
        }
