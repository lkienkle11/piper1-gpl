## 1. Voice catalog metadata and presentation model

- [x] 1.1 Define the bundled voice display-metadata schema and populate entries for every supported catalog voice and multi-speaker variant; verify the manifest has no missing voice-family or speaker keys against the supported catalog snapshot.
- [x] 1.2 Extend catalog normalization with stable voice-family/speaker presentation identities, descriptive display traits, available quality variants, and installed status without changing model keys; verify normalized catalog tests preserve internal identifiers and produce non-opaque labels for all languages.
- [x] 1.3 Add resolver/presentation tests for single-speaker voices, mapped speaker names, numeric fallback speakers, duplicate dataset names, and quality variants; verify each rendered choice has a distinct stable identity and descriptive label.

## 2. Unified selection resolution and HTTP compatibility

- [x] 2.1 Define and validate the unified selection envelope for automatic or explicit language, voice/speaker, quality, and emotion values; verify malformed, stale, and incompatible combinations return deterministic valid results or actionable errors.
- [x] 2.2 Extend automatic voice analysis to apply explicit voice, language, and quality constraints independently while preserving detector fallback, installed-first selection, adaptive delivery, and emotion/prosody behavior; verify all-auto and mixed-constraint unit tests.
- [x] 2.3 Update `/analyze` and `/synthesize` to accept the unified envelope while preserving legacy mode-based requests and model/speaker payload semantics; verify endpoint tests cover all-auto, explicit language, explicit voice/speaker, explicit quality, unavailable voices, and legacy callers.

## 3. Replace the mode switch with one voice panel

- [x] 3.1 Remove the Auto Detect / Manual Voice mode switch and make the existing Language, Voice name, Quality, and Emotion controls visible in one panel; verify no stale mode event handler, mode-only DOM reference, or inaccessible duplicate menu remains.
- [x] 3.2 Add `Auto Detect` options to Language, Voice name, and Quality and implement dependent selector rebuilding, valid-combination normalization, stable sorting, and descriptive labels for every language and speaker; verify changing one selector preserves valid explicit choices and visibly resets only incompatible dependents.
- [x] 3.3 Update analysis, voice status, download, Speak, quick-voice selection, and audio playback flows to resolve the unified selection and send internal model/speaker identifiers separately from display text; verify explicit and automatic selections produce the expected request payload and installed/download-required behavior.
- [x] 3.4 Keep the existing manual Emotion menu and automatic analysis/adaptive delivery behavior in the unified flow; verify emotion overrides affect analysis/synthesis without reintroducing a second mode menu or changing player playback rate.
- [x] 3.5 Apply natural numeric ordering and collapse high-cardinality multi-speaker corpus voices to one representative picker choice without removing their catalog/API availability; verify `Speaker 2` precedes `Speaker 10` and large corpora no longer flood the selector.

## 4. Browser settings migration and persistence

- [x] 4.1 Upgrade the settings schema and sanitization to persist independent language, voice/speaker, quality, and emotion selections while retaining draft, volume, mute, audible-volume, playback-rate, and storage-warning behavior; verify each selector change is written and restored after reload.
- [x] 4.2 Migrate legacy mode-based settings idempotently: map automatic mode to three `Auto Detect` values, map resolvable manual mode to explicit catalog choices, and normalize missing/stale references safely; verify migration tests preserve unrelated settings and never submit invalid identifiers.
- [x] 4.3 Update reset, reset-everything, cross-tab storage, catalog reload, and download-completion flows for the unified state; verify reset defaults to the intended automatic selections and a later text uses the restored explicit choices until changed.

## 5. End-to-end verification

- [x] 5.1 Run the focused voice-selection and HTTP tests, including metadata completeness and unified resolver cases; verify `.venv/bin/python -m pytest tests/test_voice_selection.py` passes.
- [x] 5.2 Run the complete available test suite and template/static checks; verify `PYTHONPATH=src .venv/bin/python -m pytest` passes and no removed mode selector or stale DOM reference causes runtime errors.
- [ ] 5.3 Exercise the page in a browser at desktop and narrow widths with all-auto, mixed settings, explicit multi-speaker voices, every supported language group, uninstalled voices, reload, legacy localStorage, reset, and cross-tab updates; verify the single panel, clear labels, persistence, download, Speak, and playback all work.
