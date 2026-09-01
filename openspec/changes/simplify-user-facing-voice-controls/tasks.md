## 1. Preserve internal analysis and canonical delivery behavior

- [x] 1.1 Refactor the client settings/request path in `src/piper/templates/index.html` so the standard flow always uses adaptive delivery and normal synthesis baseline (`1.0`), while retaining the legacy delivery and speed option values for compatibility/debug inspection; verify fresh, reset, and legacy-settings cases produce the canonical effective values.
- [x] 1.2 Keep the full analysis result available in client state for synthesis and debugging, and remove any dependency on its visual rendering; verify analysis still succeeds and the `/analyze` and `/synthesize` payloads retain the expected internal fields.
- [x] 1.3 Confirm existing adaptive prosody/timing calculation remains the source of emotion- and text-driven variation, without changing the audio player playback-rate feature; verify representative neutral, emotional, and multi-paragraph text produces valid synthesis requests/audio.

## 2. Remove developer-only presentation

- [x] 2.1 Update the Voice Studio markup and presentation logic to hide the analysis metrics, per-segment diagnostic preview, and related technical synthesis details from the normal user-facing page while keeping actionable errors, download status, and audio playback visible; verify the elements are not visible or keyboard-accessible after analysis completes.
- [x] 2.2 Retain the existing Delivery mode and synthesis-speed option menus/identifiers inside an explicit non-visible compatibility/debug boundary, including the old custom option data, and ensure they cannot be edited through the normal UI; verify the controls are hidden and their options remain discoverable to internal debug code.

## 3. Render human-readable language choices

- [x] 3.1 Change Language selector option text generation to use native/English language names plus country or region names, with a human-readable fallback when catalog names are missing; verify examples render as `English (Great Britain)` and `English (United States)`.
- [x] 3.2 Keep locale codes as option values/internal lookup identifiers only and ensure no user-visible Language option or related selector label contains a machine language code; verify regional variants remain distinct without `en_GB`-style text.

## 4. Combine voice and speaker selection

- [x] 4.1 Replace the separate user-facing Speaker selector with a combined `Voice name` presentation choice model that expands mapped and fallback multi-speaker entries into unique labels such as `aru - 03 (0)` and `aru - 06 (1)`; verify single-speaker voices remain selectable without a separate speaker control.
- [x] 4.2 Resolve each combined choice back to the original voice key and speaker name or numeric ID before status, analysis, download, and synthesis operations; verify manual synthesis sends the same model/speaker semantics as the previous selectors.
- [x] 4.3 Migrate/restores existing settings by matching stored voice key plus speaker name/ID to a combined choice, with deterministic fallback for missing speakers; verify reload, reset, quality changes, installed status, and download-required status retain correct selections.

## 5. Validate the complete user experience

- [x] 5.1 Extend relevant voice-selection/catalog tests for speaker maps, fallback speaker IDs, regional language metadata, and unchanged normalized internal identifiers; verify `.venv/bin/python -m pytest tests/test_voice_selection.py` passes.
- [x] 5.2 Run the project test suite and static/template checks after the UI refactor; verify `PYTHONPATH=src .venv/bin/python -m pytest` passes and no stale event handler or null DOM reference remains for removed/hidden controls.
- [ ] 5.3 Exercise Auto Detect and Manual Voice in a browser at desktop and narrow widths, including fresh settings, legacy settings, multi-speaker voices, and uninstalled voices; verify technical cards and Delivery controls are absent while language labels, combined Voice name choices, Speak, download, and playback remain usable.
