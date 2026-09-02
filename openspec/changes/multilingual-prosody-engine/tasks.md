## 1. Establish contracts and a measurable baseline

- [x] 1.1 Define the normalized server-side ProsodyPlan and voice capability schema for language, boundaries, pauses, pronunciation annotations, emphasis, intent, emotion, duration, pitch, energy, and style; verify schema fixtures cover supported and unavailable dimensions.
- [ ] 1.2 Create the pilot evaluation corpus and baseline recordings for representative English, Vietnamese, Chinese, Japanese, and Arabic voices, covering declarative, interrogative, exclamatory, paragraph, ellipsis, emphasis, and emotional text; verify every fixture records voice, language, text, model configuration, and baseline audio metadata.
- [x] 1.3 Add a capability-discovery path for existing Piper ONNX voices and verify legacy voices are classified as compatible with the current inputs without requiring model or browser changes.

## 2. Improve server-side text and prosody planning

- [x] 2.1 Implement structure-aware segmentation that preserves sentence, clause, paragraph, and inline-ellipsis boundaries, including native punctuation equivalents; verify unit tests distinguish comma, sentence, paragraph, and ellipsis breaks.
- [x] 2.2 Refactor local text analysis to populate the ProsodyPlan with bounded context, intent, emotion, confidence, and unavailable-signal markers for all pilot languages; verify language-specific and punctuation-only fallback tests pass.
- [x] 2.3 Add a replaceable server-side external semantic-analysis adapter with timeout, validation, privacy/configuration boundaries, and local fallback; verify provider success, malformed output, timeout, unsupported language, and network-disabled tests.
- [x] 2.4 Map ProsodyPlan data to the existing synthesis path without changing current `/analyze` or `/synthesize` request compatibility; verify existing clients and current audio behavior pass regression tests.

## 3. Make phonemizers and runtime execution capability-aware

- [ ] 3.1 Update the common and language-specific phonemizer paths to preserve reliable stress, tone, pitch-accent, punctuation, and pronunciation annotations for the pilot languages; verify phoneme fixtures and language-specific regression tests pass.
- [x] 3.2 Prevent unsupported prosody symbols or controls from reaching legacy voices and record internal availability status instead; verify legacy models synthesize successfully with deterministic fallback behavior.
- [x] 3.3 Implement executor negotiation so supported duration, pitch, energy, emphasis, and style controls are bounded and applied only by a compatible model; verify supported controls are forwarded and unsupported controls are never silently mapped to noise or speed.

## 4. Prototype the Piper expressive executor

- [ ] 4.1 Compare Piper-compatible prosody-token and explicit-acoustic-control prototypes on the pilot fixtures, then record the selected strategy, model inputs, training labels, and compatibility contract; verify the decision includes measurable and listening results.
- [ ] 4.2 Extend the selected Piper training and inference path to consume the chosen prosody representation while preserving the legacy export path; verify training/inference shape tests and an expressive prototype export pass.
- [ ] 4.3 Prepare or curate expressive pilot training data with language, speaker, text, alignment, and prosody metadata for English, Vietnamese, Chinese, Japanese, and Arabic; verify data validation rejects missing, inconsistent, or out-of-range annotations.
- [ ] 4.4 Train or finetune pilot Piper expressive voices and export them with explicit capability metadata; verify each exported model loads, synthesizes representative fixtures, and remains separate from existing voice files.
- [ ] 4.5 Integrate the expressive executor behind capability negotiation while retaining the current Piper executor as the default fallback; verify legacy voices remain usable and expressive voices apply only declared controls.

## 5. Evaluate quality and protect the unchanged UI contract

- [ ] 5.1 Add objective audio evaluation for pause duration, F0 movement, energy contrast, duration, pronunciation errors, and intelligibility where measurable; verify reports compare each candidate with the baseline per language and voice.
- [ ] 5.2 Run native-speaker listening comparisons for the pilot corpus and record naturalness, emphasis, intonation, fluency, pronunciation, and artifacts; verify the report identifies failures by language, voice, and text pattern.
- [ ] 5.3 Evaluate an external full TTS executor only as a fallback comparison when the Piper expressive prototype misses the quality gate; verify the result records quality, latency, privacy, cost, and coverage trade-offs without enabling it by default.
- [ ] 5.4 Apply the quality gate and enable only candidates that improve the baseline without unstable pauses, incorrect pronunciation, or audible artifacts; verify failing candidates remain behind the compatibility fallback.
- [x] 5.5 Run the project test suite and confirm no UI file or visible frontend behavior changed; verify `PYTHONPATH=src .venv/bin/python -m pytest` passes and the final diff contains no changes to `src/piper/templates/index.html`.
