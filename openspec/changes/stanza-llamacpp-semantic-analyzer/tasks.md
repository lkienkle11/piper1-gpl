## 1. Optional runtime setup

- [x] 1.1 Add an optional NLP dependency extra for the deterministic linguistic analyzer and verify a minimal installation still imports and runs the existing rule-based path.
- [x] 1.2 Define backend-only configuration for linguistic resources and the local semantic provider, including endpoint, model identifier, timeout, maximum text length, supported languages, and privacy policy; verify defaults keep provider execution disabled.

## 2. Multilingual linguistic analysis

- [x] 2.1 Implement lazy, cached linguistic pipelines for Arabic, Chinese, English, Japanese, and Vietnamese; verify each pilot language returns sentence and token structure when its resources are available.
- [x] 2.2 Map available token, grammatical, clause, and punctuation signals into the normalized analysis contract without changing the original text; verify native punctuation, paragraph boundaries, and short-text fallback behavior.
- [x] 2.3 Record missing language resources or unavailable annotations as internal availability status and verify analysis still completes with the existing deterministic fallback.

## 3. Local schema-constrained semantic provider

- [x] 3.1 Implement a local HTTP provider for a schema-constrained text model and verify requests contain the language, bounded text, and semantic output schema without sending data to non-approved endpoints.
- [x] 3.2 Validate provider responses for allowed context, intent, emotion, event kinds, dimensions, offsets, confidence, value ranges, and event-count limits; verify malformed and incomplete output is rejected as one atomic result.
- [x] 3.3 Enforce timeout, network/privacy policy, model availability, and maximum input length; verify each failure returns a local-fallback status without blocking synthesis.

## 4. Prosody composition and compatibility

- [x] 4.1 Compose explicit script directives, structural punctuation, linguistic signals, provider signals, local rules, and neutral defaults in the documented precedence order; verify provider output cannot erase explicit or structural signals.
- [x] 4.2 Integrate the composed plan with the existing analysis and synthesis paths while preserving request/response compatibility; verify legacy voices continue using their existing inputs and audio behavior.
- [x] 4.3 Ensure unsupported pitch, energy, emphasis, or style signals remain availability metadata and are never mapped to legacy speed or noise parameters; verify capability regression tests pass.

## 5. Evaluation and rollout safety

- [x] 5.1 Add unit and integration tests for all five pilot languages, provider success, disabled provider, unsupported language, timeout, malformed JSON, invalid events, privacy mode, and legacy fallback; verify the relevant test suite passes.
- [ ] 5.2 Benchmark at least one local multilingual model against the pilot evaluation corpus for semantic accuracy, latency, memory, and fallback rate; record the selected model recommendation without bundling weights.
- [x] 5.3 Keep the provider opt-in and add a rollback verification that disabling the provider restores the previous local-analysis path without model or data migration.
- [x] 5.4 Run the full project test suite and verify no changes exist in `src/piper/templates/index.html` or visible frontend behavior.
