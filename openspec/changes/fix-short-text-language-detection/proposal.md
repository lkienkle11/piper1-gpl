## Why

The web UI currently treats short non-English text with low language-detector confidence as the default English voice. For example, `Привет, как дела?` is synthesized with the installed English voice instead of selecting the Russian voice or clearly requesting its download, making Auto Detect misleading and causing the reported no-audio/wrong-audio experience.

## What Changes

- Make Auto Detect use script and catalog evidence for short multilingual text before applying the default-language fallback.
- Prevent a low-confidence non-English input from silently resolving to an unrelated installed English voice.
- Preserve the existing explicit low-confidence fallback for genuinely ambiguous text, while exposing enough analysis state for the UI to show the correct voice or download-required state.
- Add regression coverage for short Russian text and equivalent short inputs from supported scripts, including the `/analyze` and `/synthesize` browser/API path.

## Capabilities

### New Capabilities

- `short-text-language-detection`: Defines reliable Auto Detect voice resolution for short multilingual text and the behavior when the matching voice is not installed.

### Modified Capabilities

None.

## Impact

- Affects `src/piper/voice_selection.py` language detection and voice resolution.
- Affects the HTTP server's `/analyze` and `/synthesize` behavior when all selection dimensions are Auto Detect.
- May affect the web UI's selected voice, installed/download-required status, and Speak enablement.
- Adds unit/API/browser regression tests without changing the explicit selection payload contract.
