## Context

The proposal is based on the browser/API test described in `proposal.md`. The package already separates HTTP, Japanese, and Chinese dependencies into optional installation extras. The HTTP server reports a structured 503 when a selected voice's phonemizer import is unavailable, but the Auto Detect flow can select that voice after its model download succeeds.

## Goals / Non-Goals

**Goals:**

- Make the supported web-serving environment capable of synthesizing Japanese and Chinese voices selected by Auto Detect.
- Keep dependency declarations in the package metadata as the source of truth.
- Verify the complete flow: selection, download when needed, synthesis, audio loading, and playback.
- Preserve a useful error for deliberately minimal installations.

**Non-Goals:**

- Changing language detection, voice ranking, catalog data, or the Auto Detect request schema.
- Making every Piper CLI installation depend on all language-specific packages.
- Changing model download URLs or storing voice models in the application image.
- Adding a Docker-specific behavior or requirement.

## Decisions

### Install language extras at the web runtime boundary

The web-server setup and its documentation SHALL install the existing HTTP, Japanese, and Chinese extras together (`http`, `ja`, and `zh`). This uses the already-declared dependency lists, including the transitive phonemizer requirements, without duplicating package versions in application code.

The core package remains language-extra-optional for CLI and library consumers. Making the web install explicitly multilingual is preferred over adding Japanese and Chinese packages to `install_requires`, because it limits the larger dependency footprint to the environment that promises browser-based multilingual Auto Detect playback.

### Validate synthesis, not only downloads

Add regression coverage at the HTTP/API level for both Japanese and Chinese. Each case SHALL use the same all-Auto selection payload, ensure the selected model is available (downloading it when the fixture is absent), call `/synthesize`, and assert an audio response with a valid WAV header and non-empty payload. The test must not consider a 200 response from `/download` sufficient.

Retain a focused missing-extra test that asserts the structured 503 includes the missing package and the corresponding installation extra. This protects intentional minimal installations while preventing that response from being mistaken for successful playback.

### Verify the user-visible browser path separately

After the runtime setup and API tests pass, repeat the flow in Chrome DevTools MCP: open the local web app, enter Japanese and Chinese text, leave language/voice/quality/speaker/emotion on Auto Detect, click Speak, and inspect the network response and audio element state. This catches frontend handling or blob playback regressions that API tests cannot observe.

### Keep model data outside the installation profile

The change SHALL not download voice models as part of dependency installation. Tests may download models into a temporary data directory, and normal runtime behavior continues to use the configured voice data directory.

## Risks / Trade-offs

- [Larger web environment] Japanese and Chinese extras add native or model-backed dependencies → keep them scoped to the web runtime setup and do not add them to base package requirements.
- [Platform availability] A language dependency may not publish a compatible wheel for a supported Python/platform combination → fail setup clearly and test the supported environment in CI before release.
- [Network-dependent regression tests] Voice downloads can be slow or unavailable → use cached/fixture voices when available, isolate data in a temporary directory, and keep deterministic phonemizer/API tests alongside the live browser smoke test.
- [False-positive browser test] A previous audio blob can remain in the page after a failed request → assert the current synthesis response status and audio source/duration after each Speak action.

## Migration Plan

1. Update the web-server installation path and instructions to install the three existing extras.
2. Add dependency, API, and browser regression checks.
3. Run the checks in a clean web environment and release the updated setup guidance.
4. Roll back by reverting the web-install change; minimal installations retain the existing structured missing-dependency response.

## Open Questions

None.
