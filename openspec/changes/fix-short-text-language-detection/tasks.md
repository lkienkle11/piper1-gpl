## 1. Short-text resolution

- [x] 1.1 Add script-profile and language-candidate handling for low-confidence Auto Detect input, and verify `Привет, как дела?` resolves to the Russian family even when the full catalog lowers unrestricted confidence.
- [x] 1.2 Update the low-confidence branch to use the script-aware result before default fallback, and verify genuinely ambiguous short text still reports a safe fallback reason.
- [x] 1.3 Preserve explicit language, voice, quality, and speaker precedence, and verify explicit-selection regression tests continue to pass.

## 2. HTTP and UI behavior

- [x] 2.1 Add `/analyze` regression coverage proving a short Russian Auto Detect request returns a Russian catalog voice and `needs_download` when that voice is absent locally.
- [x] 2.2 Add `/synthesize` regression coverage proving a missing Russian voice returns the structured download-required response instead of synthesizing with an installed English voice, then verify download-then-synthesize returns a valid non-empty WAV.
- [x] 2.3 Run the Chrome DevTools MCP smoke flow with language, voice, quality, speaker, and emotion on Auto Detect; enter `Привет, как дела?`, click Download voice when required, click Speak, and verify the current `/synthesize` response is `200 audio/wav` and the audio element reaches a positive duration and playback end.

## 3. Verification

- [x] 3.1 Run the focused language-selection and HTTP regression tests, and verify the short Russian, short Japanese, ambiguous fallback, and explicit-selection cases pass.
- [x] 3.2 Run the complete test suite and `openspec validate fix-short-text-language-detection --type change --strict`, and verify no existing multilingual synthesis regressions are introduced.
