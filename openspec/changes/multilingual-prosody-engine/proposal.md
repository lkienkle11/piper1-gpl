## Why

Piper Voice Studio currently produces mostly flat or weakly emphasized narration across languages because its text analysis is primarily rule-based and its inference contract exposes duration and stochastic noise controls, but no explicit pitch, energy, emphasis, or prosody contour. Punctuation is preserved as phoneme context, yet paragraph context and semantic intent are not consistently converted into acoustic behavior, so improving the user experience requires a backend and model-capability change rather than a visual redesign.

## What Changes

- Add a backend prosody-planning capability that preserves sentence, paragraph, punctuation, pause, emphasis, intent, and emotion information in a language-aware intermediate representation.
- Correct deterministic text-front-end behavior that conflicts with natural narration, including ellipsis as an inline break, paragraph boundaries, terminal punctuation, and language-specific sentence handling.
- Extend language-specific phonemizer adapters where the selected voice and model vocabulary can safely consume prosody markers; preserve existing phoneme and voice fallbacks for unsupported combinations.
- Define a model capability contract for duration, pitch, energy, emphasis, and style controls, including compatibility behavior for existing Piper ONNX voices that only accept the current inputs.
- Evaluate Piper-compatible retraining/finetuning with expressive data against an external full TTS backend; treat external NLP as an analysis component only unless it is paired with an acoustic engine that can execute its output.
- Add objective and human-listening evaluation for representative languages, voices, punctuation patterns, paragraph transitions, questions, announcements, and emotional text.
- Preserve the current `/analyze` and `/synthesize` behavior for existing clients. FE logic may be adjusted only if a new internal API field is required; no user-facing UI, HTML, CSS, labels, selectors, layout, or settings behavior is part of this change.

## Capabilities

### New Capabilities

- `multilingual-prosody-engine`: Defines language-aware prosody planning, model capability negotiation, compatibility fallbacks, and evaluation requirements for expressive synthesis.

### Modified Capabilities

None.

## Impact

- `src/piper/voice_selection.py`: text segmentation, semantic/context analysis, and prosody-plan generation.
- `src/piper/phonemize_*.py` and `libpiper/src/chinese_phonemizer.cpp`: language-specific punctuation and prosody front ends.
- `src/piper/voice.py`, `src/piper/http_server.py`, and `src/piper/train/export_onnx.py`: synthesis capability handling and compatibility paths.
- Tests, benchmark fixtures, and optional model-training/evaluation dependencies.
- Existing Piper voice files and HTTP clients remain supported through a backward-compatible fallback.
- `src/piper/templates/index.html` is explicitly out of scope; no UI files or visible frontend behavior will be changed.
