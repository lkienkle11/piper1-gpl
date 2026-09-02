## Context

See proposal.md for the motivation. The current server combines language detection, limited keyword-based context classification, language-specific phonemizers, and Piper VITS inference. Existing Piper ONNX voices accept phoneme IDs, sequence length, three legacy scales, and an optional speaker ID; they do not expose explicit pitch, energy, emphasis, or style controls. The existing Voice Studio is intentionally user-facing and must remain unchanged.

## Goals / Non-Goals

**Goals:**

- Establish one normalized server-side prosody representation independent of any particular NLP provider or acoustic executor.
- Improve sentence, paragraph, punctuation, ellipsis, stress, tone, and language-specific front-end handling without breaking current voices.
- Support richer prosody for newly trained or integrated capable voices while giving legacy voices a safe fallback.
- Make quality measurable through repeatable fixtures and audio/listening evaluation.

**Non-Goals:**

- Redesigning or modifying the visible Voice Studio UI.
- Running a large NLP model in the browser.
- Claiming that an NLP classification result alone can change the pitch or emphasis of an existing Piper waveform.
- Forcing every existing ONNX voice to accept new inputs without retraining or a compatible export.

## Decisions

### Use a server-side ProsodyPlan as the stable boundary

Create a normalized intermediate representation containing language, paragraph and sentence boundaries, clause context, break events, emphasis spans, emotion or intent signals, pronunciation annotations, and requested acoustic dimensions. Keep source confidence and executor support separate so an accurate analysis is not mistaken for an applied audio change.

Alternative considered: pass provider-specific labels directly to Piper. Rejected because it couples the API to one analyzer and cannot represent language-specific or model-specific capabilities safely.

### Make the executor capability-adaptive

Describe voice/model support explicitly for duration, pitch, energy, emphasis, style, and language-specific markers. The current Piper executor remains the fallback. A new Piper export can consume additional prosody inputs only after model training/finetuning and export support; an external full TTS executor can be evaluated behind the same server boundary.

Alternative considered: map pitch or emphasis to `noise_scale` or `length_scale`. Rejected because those parameters control stochastic variation and duration, not the intended acoustic dimension, and would produce misleading or unstable behavior.

### Keep NLP optional and server-side

Use local deterministic analysis as the baseline and add an optional replaceable provider interface for multilingual intent, emotion, discourse, or emphasis extraction. Provider output is validated, bounded, and merged into the ProsodyPlan. Provider failures never prevent the legacy synthesis path when local analysis can continue.

Alternative considered: train a new NLP model before fixing deterministic front-end behavior. Rejected because segmentation and punctuation errors are independently observable, cheaper to correct, and must be fixed regardless of the eventual semantic model.

### Prefer Piper-compatible expressive training as the primary on-device path

First benchmark an expressive Piper/VITS-compatible model design using prosody tokens or explicit acoustic controls, with training data that contains natural variation and reliable alignment where available. Evaluate an external full TTS backend as a fallback when the on-device model cannot meet the quality gate or language coverage requirements. Do not replace existing voices automatically.

Alternative considered: apply waveform pitch/time post-processing to every current voice. Rejected as a rapid experiment only; it can provide a baseline but cannot reliably reproduce phrase-level intonation and may introduce artifacts.

### Preserve the existing HTTP and UI contracts

Keep current request fields valid and make any new prosody metadata optional and internal. Do not edit the template's HTML, CSS, labels, selectors, layout, or visible interaction. If a frontend change is later required to send an optional field, limit it to non-visual request/state plumbing and verify that the rendered interface is unchanged.

## Risks / Trade-offs

- [Risk] Existing voice models may accept new phoneme IDs syntactically but have never learned their prosodic meaning. -> Mitigation: declare vocabulary/model capability separately and use new markers only for trained compatible voices.
- [Risk] External NLP adds latency, privacy exposure, cost, and network failure modes. -> Mitigation: keep it optional, server-side, bounded by timeouts, and backed by local analysis.
- [Risk] More paragraph context can increase memory and latency. -> Mitigation: use bounded context windows and retain sentence-level streaming fallback.
- [Risk] Objective F0/energy metrics can disagree with perceived naturalness across languages. -> Mitigation: combine acoustic measurements with native-speaker listening panels and intelligibility checks.
- [Risk] Better prosody may expose pronunciation or phonemizer defects. -> Mitigation: evaluate pronunciation separately and preserve per-language fallback paths.

## Migration Plan

1. Add plan and capability schemas internally while keeping current API requests valid.
2. Correct deterministic segmentation and phonemizer behavior, then compare against the existing baseline.
3. Add local and optional external analysis adapters without changing the UI.
4. Train/export or integrate a capable executor behind capability negotiation; keep legacy voices on fallback.
5. Run the multilingual quality gate before enabling any new executor by default.
6. Roll back by disabling the new executor and retaining the plan-to-legacy fallback; no browser settings or UI migration is required.

## Resolved Planning Assumptions

- The initial quality-gate pilot covers representative English, Vietnamese, Chinese, Japanese, and Arabic voices. The implementation may expand coverage after the pilot, but it must retain a language-independent plan and compatibility boundary.
- The first capable executor to prototype is a new Piper-compatible expressive model/export. Existing Piper voices remain supported and selectable through the legacy fallback; they are not removed or silently migrated.
- An external full TTS backend remains an evaluation fallback only. It is not required for the first implementation unless the Piper expressive prototype fails the agreed quality gate.
