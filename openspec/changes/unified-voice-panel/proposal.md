## Why

Voice Studio currently makes users choose between separate Auto Detect and Manual Voice modes. This splits one voice-selection task across two menus and makes it impossible to keep a deliberate language, voice, or quality choice while still allowing the remaining settings to be automatic. The manual controls should become the single voice panel, with explicit `Auto Detect` values where automatic behavior is useful and with voice names that explain what each voice sounds like.

## What Changes

- Remove the separate Auto Detect / Manual Voice mode switch and present one unified voice-selection panel based on the existing manual controls.
- Keep the existing manual Language, Voice name, Quality, and Emotion controls and their current user-facing behavior; do not add unrelated manual controls.
- Add an `Auto Detect` option to the Language, Voice name, and Quality selectors.
- Resolve each selector independently for new text:
  - a concrete Language constrains synthesis to that configured language;
  - a concrete Voice name pins the configured voice (and its speaker, where applicable);
  - a concrete Quality constrains the selected language/voice to that quality;
  - `Auto Detect` delegates that dimension to the existing automatic analysis and voice-selection behavior.
- Preserve the existing automatic language detection, contextual/emotional analysis, adaptive delivery, and automatic fallback behavior behind the unified panel.
- Persist the unified selection, including language, voice/speaker choice, quality, and emotion, in browser `localStorage`; migrate existing mode-based/manual settings and retain player/draft settings already stored there.
- Restore persisted selections on reload and ensure that a concrete selection remains effective for subsequent text until the user changes it back to `Auto Detect`.
- Replace opaque voice-name labels, numeric speaker IDs, and dataset-only labels with clear labels composed of a voice name and descriptive attributes such as gender, age, pitch, accent/region, or style. Apply this to every supported language and every voice option, including multi-speaker voices.
- Add or normalize a complete project-owned voice display-metadata source when the upstream Piper catalog lacks descriptive attributes, and validate that no catalog voice falls back to an opaque identifier-only label.
- Keep internal model keys, speaker names/IDs, quality values, download status, and synthesis request semantics unchanged.

## Capabilities

### New Capabilities

- `unified-voice-panel`: Defines the single voice-selection panel, independent Auto Detect/manual dimensions, persistence and migration behavior, and human-readable voice labels.

### Modified Capabilities

None.

## Impact

- `src/piper/templates/index.html`: unified panel markup, selector options, dependent selection resolution, localStorage restoration/persistence, and synthesis payload construction.
- `src/piper/voice_selection.py`: normalized catalog metadata, automatic/manual resolution rules, and stable mapping between display choices and internal voice/speaker identifiers.
- Voice catalog metadata/assets: a complete display-metadata mapping or equivalent catalog extension for all supported voices and languages.
- `src/piper/http_server.py` and HTTP tests: only where the unified selection payload needs to carry independent auto/manual values while preserving existing API compatibility.
- Browser settings migration: existing `piper.voiceStudio.settings.v1` values remain readable; the unified settings schema may introduce a new version/key, with deterministic migration and safe fallback for stale or missing voice metadata.
