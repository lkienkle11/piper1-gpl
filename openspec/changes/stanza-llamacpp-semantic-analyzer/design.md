## Context

See `proposal.md` for the motivation. The current server already has a rule-based analyzer, language-specific phonemizers, a normalized `ProsodyPlan`, and an optional provider boundary, but no installed semantic model. Existing Piper voices accept the legacy synthesis inputs and must remain unchanged. The Voice Studio template and visible controls are outside this change.

## Goals / Non-Goals

**Goals:**

- Add deterministic linguistic features for all five pilot languages without requiring a generative model.
- Add an optional local semantic provider that returns schema-constrained, validated prosody metadata.
- Preserve punctuation, paragraph boundaries, explicit script directives, request compatibility, privacy controls, and legacy fallback behavior.
- Keep the provider boundary independent of a particular model name so the pilot can benchmark suitable multilingual GGUF models.

**Non-Goals:**

- Train or fine-tune an NLP model in this change.
- Create or modify an expressive acoustic Piper checkpoint.
- Map semantic predictions to unsupported legacy acoustic controls.
- Add UI controls, labels, diagnostics, settings panels, or visible frontend behavior.

## Decisions

### Use a two-layer analyzer

The deterministic linguistic layer will provide sentence/token structure, grammatical features, and clause evidence. The optional semantic layer will interpret context, intent, emotion, and emphasis candidates. Structural boundaries from the existing parser remain authoritative so an NLP model cannot erase punctuation or paragraph pauses.

Stanza is selected for the linguistic layer because it supplies maintained multilingual pipelines and the required token, sentence, POS, and dependency features. A model-specific semantic classifier is not selected because ready-made emotion coverage is uneven across the five pilot languages and would not cover the required prosody event schema.

### Use a local llama.cpp HTTP provider

The semantic layer will communicate with a separately managed local `llama.cpp` server over its HTTP API. The server request will include the language, text, bounded output instructions, and a JSON Schema for the accepted semantic result. The application will not bundle model weights or start a model process implicitly.

Direct `llama.cpp` is preferred over Ollama because it removes an additional application runtime while retaining local execution and constrained JSON generation. vLLM remains a compatible deployment alternative for GPU hosts, but is not the default because the target project also needs lightweight local CPU/Metal operation.

### Keep the existing provider boundary and fallback precedence

The provider result will be decoded into the existing normalized event contract and validated before composition. Precedence will be:

1. explicit user/script directives;
2. preserved punctuation, paragraph, and phonemizer-derived structure;
3. validated semantic-provider signals;
4. deterministic local classification;
5. neutral defaults.

The semantic provider may add or refine context, emotion, intent, and emphasis events, but it may not replace explicit directives, alter source text, or invent unsupported acoustic capabilities. Invalid, incomplete, timed-out, or unavailable provider output will be discarded as one result and will not partially affect synthesis.

### Treat privacy and availability as runtime policy

The default configuration will keep semantic-provider execution opt-in. A privacy-disabled or network-disabled policy will prevent provider calls, including calls to a non-loopback endpoint. Provider endpoint, model identifier, timeout, maximum text length, and supported languages will be backend/runtime settings rather than UI settings. No text or provider response will be persisted by the analyzer.

### Preserve legacy contracts

The analysis response may carry additional internal metadata, but existing request fields and required response fields remain valid. The synthesis path will consume the existing segment fields for legacy voices. Prosody events whose dimensions are not declared by the selected executor will remain availability metadata and will not be mapped to `noise_scale`, `noise_w_scale`, or `length_scale`.

### Validate at the boundary

Validation will enforce the allowed language family, context and emotion labels, event kinds and dimensions, confidence range, text offsets, event value ranges, maximum event count, and JSON object shape. The same validator will be used for an in-process provider and an HTTP provider so switching runtimes cannot weaken safety.

## Risks / Trade-offs

- [Risk] A multilingual LLM can hallucinate emphasis or emotion, especially for short or culturally specific text. -> Mitigation: require schema-constrained output, preserve local structural signals, bound confidence and event spans, and compare against a native-speaker evaluation corpus.
- [Risk] Local model startup and inference add latency and memory usage. -> Mitigation: lazy provider calls, a finite timeout, bounded input, optional short-lived in-memory caching, and immediate local fallback.
- [Risk] Stanza model quality and annotation availability vary by language. -> Mitigation: record unavailable features per language and never treat missing annotations as positive prosody evidence.
- [Risk] A local HTTP service may be misconfigured to send text externally. -> Mitigation: require an explicit opt-in for non-loopback endpoints and fail closed when privacy mode is enabled.
- [Risk] Semantic metadata alone cannot create pitch or energy movement in legacy Piper voices. -> Mitigation: keep acoustic execution capability negotiation explicit and defer expressive model integration to the separate Piper training change.
- [Risk] Optional dependencies may be absent in minimal installations. -> Mitigation: import lazily and retain the existing rule-based analyzer as the default functional path.

## Migration Plan

1. Add optional Stanza resources and a local-provider configuration schema without changing existing defaults.
2. Implement and test the Stanza adapter, schema-constrained HTTP provider, composition rules, and fallback behavior.
3. Benchmark at least one local multilingual model on the five-language evaluation corpus before selecting a default model recommendation.
4. Enable the provider only in an explicit backend/runtime pilot configuration; existing installations continue using local rules.
5. Roll back by disabling the provider or removing its endpoint configuration; no legacy voice files or UI assets require migration.

