"""Shared Stanza processor definitions and resource preparation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Union

PILOT_LANGUAGES = ("ar", "en", "ja", "vi", "zh")

# Keep this mapping shared by model preparation and pipeline construction. The
# nocharlm models avoid downloading character language models. Vietnamese uses
# Stanza's identity lemmatizer at runtime because it has no lemma model file;
# the resource downloader excludes that processor from the download request.
STANZA_PROCESSORS: Mapping[str, Mapping[str, str]] = {
    "ar": {
        "tokenize": "padt",
        "mwt": "padt",
        "pos": "padt_nocharlm",
        "lemma": "padt_nocharlm",
        "depparse": "padt_nocharlm",
    },
    "en": {
        "tokenize": "combined_nocharlm",
        "mwt": "combined",
        "pos": "combined_nocharlm",
        "lemma": "combined_nocharlm",
        "depparse": "combined_nocharlm",
    },
    "ja": {
        "tokenize": "combined_nocharlm",
        "pos": "combined_nocharlm",
        "lemma": "combined_nocharlm",
        "depparse": "combined_nocharlm",
    },
    "vi": {
        "tokenize": "vtb",
        "pos": "vtb_nocharlm",
        "lemma": "identity",
        "depparse": "vtb_nocharlm",
    },
    "zh": {
        "tokenize": "gsdsimp",
        "pos": "gsdsimp_nocharlm",
        "lemma": "gsdsimp_nocharlm",
        "depparse": "gsdsimp_nocharlm",
    },
}


def normalize_languages(
    languages: Optional[Iterable[str]] = None,
) -> tuple[str, ...]:
    """Return validated, de-duplicated Stanza language families."""
    selected = PILOT_LANGUAGES if languages is None else tuple(languages)
    normalized: list[str] = []
    for language in selected:
        value = str(language).strip().casefold().replace("_", "-")
        value = value.split("-", 1)[0]
        if value not in STANZA_PROCESSORS:
            choices = ", ".join(PILOT_LANGUAGES)
            raise ValueError(
                f"unsupported Stanza language {language!r}; choose from {choices}"
            )
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("at least one Stanza language is required")
    return tuple(normalized)


def processors_for_language(language: str) -> tuple[str, ...]:
    """Return the processor tuple used for one supported language."""
    normalized = normalize_languages((language,))[0]
    return tuple(STANZA_PROCESSORS[normalized])


def processor_packages_for_language(language: str) -> dict[str, str]:
    """Return the exact Stanza model package for each processor."""
    normalized = normalize_languages((language,))[0]
    return dict(STANZA_PROCESSORS[normalized])


def download_resources(
    model_dir: Union[str, Path],
    languages: Optional[Sequence[str]] = None,
    *,
    stanza_module: Optional[object] = None,
) -> tuple[str, ...]:
    """Download only the shared processor set for the selected languages."""
    selected = normalize_languages(languages)
    target = Path(model_dir)
    target.mkdir(parents=True, exist_ok=True)
    if stanza_module is None:
        import stanza as stanza_module

    download = getattr(stanza_module, "download")
    for language in selected:
        processors = {
            processor: package
            for processor, package in processor_packages_for_language(language).items()
            if package != "identity"
        }
        download(
            language,
            model_dir=str(target),
            package=None,
            processors=processors,
            verbose=False,
        )
    return selected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download shared Stanza resources")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--languages", nargs="+", default=None, metavar="LANG")
    args = parser.parse_args(argv)
    download_resources(args.model_dir, args.languages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
