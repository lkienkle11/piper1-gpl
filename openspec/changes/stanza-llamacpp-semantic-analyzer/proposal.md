## Why

The current prosody pipeline has a safe rule-based fallback, but it cannot reliably infer deep discourse context, intent, emphasis candidates, or emotion across the five pilot languages. Ollama is not required for this capability; a local Stanza pipeline plus a schema-constrained `llama.cpp` server can provide richer analysis without coupling the project to a specific application runtime or changing the Voice Studio UI.

## What Changes

- Add a multilingual Stanza analysis layer for Arabic, Chinese, English, Japanese, and Vietnamese to provide sentence, token, syntactic, and linguistic features.
- Add an optional local `llama.cpp` semantic provider that returns validated JSON matching the server-side `ProsodyPlan` contract.
- Compose deterministic Stanza/rule-based signals with optional LLM semantic signals, with bounded timeout, validation, privacy controls, and local fallback.
- Keep `/analyze` and `/synthesize` request compatibility and keep all existing Piper voices and legacy synthesis behavior available.
- Make the provider configurable through backend/runtime configuration; do not add UI controls or visible diagnostics.
- Do not train a new NLP model in this change; retain a stable adapter boundary for later supervised fine-tuning if evaluation shows that pretrained models are insufficient.

## Capabilities

### New Capabilities

- `multilingual-semantic-analysis`: Analyze pilot-language text with local linguistic and optional schema-constrained semantic models, then produce validated prosody signals with deterministic fallback behavior.

### Modified Capabilities

<!-- No existing main capability specification is present under openspec/specs/. -->

## Impact

- Affects the server-side text analysis and prosody planning path around `src/piper/semantic_analysis.py`, `src/piper/voice_selection.py`, and the existing `ProsodyPlan` contract.
- Adds optional runtime dependencies for Stanza and a local `llama.cpp` server/model; the legacy installation remains usable without them.
- May add backend configuration and tests for model availability, JSON-schema output, timeout, language coverage, privacy mode, and fallback.
- Does not modify `src/piper/templates/index.html`, UI layout, labels, selectors, or visible frontend behavior.
