## Context

The completed multilingual packaging change verifies Japanese and Chinese synthesis, but the current detector builds one language model from the full catalog. For short text this can flatten the confidence signal; the Russian phrase `Привет, как дела?` was classified as low-confidence English and resolved to the installed English default even though Russian voices were present in the catalog.

The web client already renders the analysis voice and distinguishes Installed from Download required. The server already returns catalog voices that are not installed and blocks synthesis with a structured `voice_not_installed` response. The missing behavior is selecting the right catalog language before those existing states are applied.

## Goals / Non-Goals

**Goals:**

- Make short inputs with useful Unicode-script evidence resolve to the strongest supported language family.
- Keep the selected catalog voice language-correct when it needs to be downloaded.
- Preserve safe fallback behavior for genuinely ambiguous text and preserve all explicit selections.
- Cover analysis, download-required behavior, synthesis, and browser playback.

**Non-Goals:**

- Automatically downloading voices as part of ordinary analysis or Speak.
- Replacing the language detector or changing the selection payload contract.
- Improving pronunciation, prosody, or audio-device routing.
- Making arbitrary short text distinguish languages that are genuinely indistinguishable from their characters alone.

## Decisions

### Add a script-aware resolution stage before generic fallback

After the existing detector produces a low-confidence result, inspect the input's Unicode script profile and narrow candidate language families to scripts represented in the voice catalog. Re-evaluate language evidence within the relevant candidate set, then use the resulting family for normal voice resolution. This keeps the existing high-confidence path unchanged and avoids letting unrelated catalog languages dominate a short sample.

An alternative is lowering the global confidence threshold. That would make the result dependent on catalog composition and could turn ambiguous Latin or Cyrillic snippets into arbitrary language choices, so it is rejected.

### Keep catalog selection separate from installation state

Resolve the best catalog voice first, including voices that are not installed. The existing `installed` flag then controls the UI download state and the synthesis precondition. This ensures a short Russian input cannot be silently substituted with an installed English model.

An alternative is to select only installed voices. That would recreate the reported bug whenever the matching language has not yet been downloaded, so it is rejected.

### Define a conservative ambiguity boundary

Use script evidence only when it narrows the supported language set enough for a defensible result. If the text remains ambiguous, retain the current default fallback and its diagnostic reason. This preserves compatibility for short Latin text and other cases where automatic language selection cannot be justified.

### Test the complete user-visible contract

Add deterministic unit/API cases for short Russian and Japanese inputs, an ambiguous fallback case, and explicit-selection precedence. Add a Chrome DevTools MCP smoke case that enters the Russian sample with all selectors on Auto Detect, downloads the displayed Russian voice when required, clicks Speak, and verifies a successful WAV response and completed audio element.

## Risks / Trade-offs

- [Script overlap] Several languages share a writing system → use restricted detector evidence and a conservative ambiguity rule; do not force a language when candidates remain tied.
- [Catalog drift] New catalog languages can change unrestricted detector results → make the short-text path depend on script-compatible candidates rather than a global threshold.
- [Download-required flow] Analysis can correctly identify an unavailable voice but Speak cannot proceed → retain the current visible Download required state and test the download-then-synthesize sequence.
- [False confidence] A very short phrase can still be misleading → preserve the generic fallback for inputs without enough script or language evidence.

## Migration Plan

1. Implement the script-aware analysis stage behind the existing Auto Detect path.
2. Add unit and HTTP regression coverage, then run the existing suite.
3. Verify the download-required and playback flow with Chrome DevTools MCP.
4. Roll back by reverting the analysis-stage change; explicit selections and existing fallback behavior remain compatible.
