## Purpose

Provide a language-aware server-side prosody pipeline that turns text structure and meaning into natural pauses, emphasis, timing, and intonation while remaining compatible with existing Piper voices and clients.

## ADDED Requirements

### Requirement: The backend SHALL produce a language-aware prosody plan

For each synthesis request, the backend SHALL derive a normalized prosody plan from the selected or detected language, text structure, punctuation, paragraph boundaries, sentence context, and available emotion or intent signals. The plan SHALL distinguish information that is understood from information that the selected acoustic model can actually execute.

#### Scenario: A paragraph contains mixed sentence contexts

- **WHEN** a paragraph contains declarative, interrogative, exclamatory, and subordinate clauses
- **THEN** the plan contains their sentence or clause boundaries, context labels, and pause or intonation events without flattening the complete paragraph into one neutral profile

#### Scenario: Semantic analysis is unavailable

- **WHEN** no external or language-specific semantic analyzer is available for the selected language
- **THEN** the backend still creates a valid plan from punctuation, paragraph structure, phonemizer output, and deterministic language rules, and marks unsupported semantic signals as unavailable

### Requirement: Text boundaries and punctuation SHALL preserve natural narration structure

The backend SHALL treat punctuation according to its language-appropriate role. An ellipsis SHALL represent an inline hesitation or short break unless surrounding text establishes a true sentence boundary. Blank-line paragraph boundaries SHALL remain distinguishable from ordinary sentence boundaries, and native punctuation equivalents SHALL be supported where the selected front end recognizes them.

#### Scenario: Text contains an inline ellipsis

- **WHEN** text contains an ellipsis between two parts of the same thought
- **THEN** the backend keeps the parts in the same narration context and emits a short inline break rather than forcing an independent sentence synthesis boundary

#### Scenario: Text contains separate paragraphs

- **WHEN** two non-empty text blocks are separated by a blank line
- **THEN** the plan emits a paragraph transition distinct from a comma, sentence terminator, or inline ellipsis

### Requirement: Language-specific prosody front ends SHALL be capability-aware

Each supported language front end SHALL be able to preserve the pronunciation and prosody information it can reliably derive, including stress, tone, pitch accent, clause type, and language-specific punctuation where available. It SHALL not emit a prosody symbol or control that the target voice vocabulary and model capability do not support without applying a documented fallback.

#### Scenario: A language front end provides pitch-accent information

- **WHEN** the selected language front end derives reliable pitch-accent or tone events and the voice declares support for them
- **THEN** those events are included in the plan and passed to the synthesis executor

#### Scenario: A legacy voice lacks a prosody capability

- **WHEN** the selected voice accepts only the existing Piper phoneme and scale inputs
- **THEN** synthesis remains successful using the legacy phoneme path and supported timing or variation controls, while unsupported pitch, energy, or emphasis events are reported internally as unavailable

### Requirement: Synthesis SHALL execute prosody only when the model supports it

The synthesis layer SHALL negotiate the plan against the selected voice capability. A prosody-capable model SHALL be able to apply its supported duration, pitch, energy, emphasis, or style controls; an existing model without those controls SHALL use a deterministic backward-compatible fallback and SHALL NOT silently reinterpret unsupported controls as unrelated parameters.

#### Scenario: A prosody-capable voice is selected

- **WHEN** the selected voice declares support for a requested prosody dimension
- **THEN** the synthesis request contains the corresponding normalized control and the generated audio reflects that control within the model's declared bounds

#### Scenario: An existing Piper ONNX voice is selected

- **WHEN** the voice exposes only the current `input`, `input_lengths`, `scales`, and optional speaker inputs
- **THEN** the request remains valid for that voice, existing audio behavior is preserved, and unsupported prosody dimensions do not break synthesis

### Requirement: External analysis SHALL remain server-side and replaceable

The backend MAY use an external multilingual NLP or semantic analyzer, but it SHALL treat its output as structured analysis input to the prosody plan rather than as audio. The provider SHALL be replaceable, and provider failure, timeout, unavailable language coverage, or disabled network access SHALL fall back to local analysis without exposing technical diagnostics in the user-facing experience.

#### Scenario: An external analyzer returns intent and emphasis spans

- **WHEN** the provider successfully analyzes a supported text
- **THEN** the backend validates and bounds its output before merging it into the prosody plan

#### Scenario: The external analyzer is unavailable

- **WHEN** the provider cannot be reached or does not support the selected language
- **THEN** synthesis continues through the local fallback path and preserves the existing API error and audio behavior where possible

### Requirement: Existing clients and the user interface SHALL remain unchanged

The change SHALL preserve the existing `/analyze` and `/synthesize` request compatibility and existing voice, speaker, download, playback, and settings behavior. No user-facing HTML, CSS, label, selector, layout, or visible interaction SHALL be added, removed, or changed. Frontend logic MAY change only when required to carry an optional internal compatibility field, and such a change SHALL not alter the visible interface.

#### Scenario: An existing client sends a current synthesis request

- **WHEN** a client sends the current request shape without prosody-specific fields
- **THEN** the backend accepts it and uses the compatibility fallback without requiring client changes

#### Scenario: The new engine adds internal metadata

- **WHEN** the backend produces prosody metadata for diagnostics or model negotiation
- **THEN** existing clients continue to function, and the metadata does not become visible through a changed UI

### Requirement: Prosody quality SHALL be evaluated before rollout

The project SHALL evaluate representative languages, voices, sentence types, punctuation patterns, paragraph transitions, and emotional or intent-bearing text using objective timing, pitch, energy, and intelligibility measures where applicable, together with human listening comparisons. A model or provider SHALL NOT be considered production-ready solely because text analysis labels are correct.

#### Scenario: A candidate prosody implementation is evaluated

- **WHEN** a candidate front end, model, or external executor is compared with the current baseline
- **THEN** the evaluation records language, voice, input text, generated controls, audio measurements, failure cases, and listener results

#### Scenario: A candidate fails the quality gate

- **WHEN** a candidate introduces audible artifacts, incorrect pronunciation, unstable pauses, or no measurable improvement
- **THEN** the candidate remains behind the compatibility fallback and is not enabled as the default executor
