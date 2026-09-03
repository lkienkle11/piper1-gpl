## 1. Web Runtime Dependencies

- [x] 1.1 Update the web-server setup path to install the existing `http`, `ja`, and `zh` extras together, and verify in a clean environment that Flask, `pyopenjtalk`, and `unicode_rbnf` are importable.
- [x] 1.2 Update the web-server setup documentation and commands to match the multilingual runtime dependency profile, and verify the documented command starts the local web server without missing-extra errors.
- [x] 1.3 Preserve the lightweight core/CLI installation and the structured missing-dependency response, and verify a deliberately minimal environment still reports the missing package and installation extra.

## 2. HTTP Regression Coverage

- [x] 2.1 Add isolated Japanese and Chinese voice fixtures or temporary voice-data setup that can exercise Auto Detect without relying on a user's existing data directory, and verify each fixture is recognized by the voice catalog.
- [x] 2.2 Add API regression tests using the all-Auto selection payload for Japanese and Chinese, and verify `/synthesize` returns a non-empty WAV response with a valid header.
- [x] 2.3 Cover the missing-model sequence by completing `/download` before `/synthesize`, and verify the test passes only when synthesis succeeds rather than when download alone returns 200.
- [x] 2.4 Keep English and Vietnamese all-Auto synthesis covered, and verify the dependency change does not regress their playable audio responses.

## 3. Browser Verification

- [x] 3.1 Re-run the Japanese and Chinese flows in Chrome DevTools MCP with language, voice, quality, speaker, and emotion all set to Auto Detect; download the selected voice when it is absent, then verify the current Speak request succeeds and the resulting audio element loads and plays.
- [x] 3.2 Re-run English and Vietnamese with all options on Auto Detect and verify each Speak action has a successful synthesis response, a valid audio source, and advancing playback time rather than reusing a previous blob.

## 4. Final Validation

- [x] 4.1 Run the project test suite in a clean Python 3.12 environment with `PYTHONPATH=src <env>/bin/python -m pytest` after installing the web runtime extras, and verify all affected tests pass.
- [x] 4.2 Run the clean-environment web/API smoke test and the Chrome DevTools MCP browser flows, and record the response status, audio MIME type, and playback evidence for each supported language.
