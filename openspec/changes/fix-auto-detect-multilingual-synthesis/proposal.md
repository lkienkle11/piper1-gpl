## Why

When the web UI is left in Auto Detect mode, English and Vietnamese synthesis returns audio, but Japanese and Chinese synthesis fails after the voice has been downloaded. The browser test reproduced HTTP 503 responses that identify missing language phonemizer packages (`pyopenjtalk` for Japanese and `unicode-rbnf` for Chinese), so Auto Detect does not currently provide the expected multilingual playback behavior.

## What Changes

- Make Auto Detect synthesis resolve and execute supported Japanese and Chinese voices when their models are available.
- Ensure the running application installs or otherwise exposes the language-specific phonemizer dependencies required by the selected voice.
- Preserve the existing automatic language, voice, quality, speaker, and emotion selection contract.
- Keep the existing actionable dependency error response for installations that intentionally omit an optional language extra.
- Add regression coverage that downloads or supplies Japanese and Chinese voice fixtures, synthesizes text in each language, and verifies playable WAV audio rather than only a successful model download.

## Capabilities

### New Capabilities

- `auto-detect-multilingual-synthesis`: Defines the behavior required for Auto Detect to synthesize playable audio across supported languages, including language-specific runtime dependencies.

### Modified Capabilities

None.

## Impact

- Affected runtime dependency installation and language phonemizer loading in the Piper web application.
- Affected browser/API regression tests for `/download` and `/synthesize`.
- Potentially affected packaging or environment setup for the Japanese and Chinese language extras.
- No API payload or user-facing option changes are intended.
