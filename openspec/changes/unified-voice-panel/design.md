## Context

The current page has one manual selector group behind a mode switch, while automatic analysis is selected by the separate `mode` value sent to `/analyze` and `/synthesize`. The browser already persists settings under `piper.voiceStudio.settings.v1`, including the legacy mode, manual voice key, speaker identity, emotion, delivery, and player preferences. The normalized Piper catalog currently exposes language metadata, dataset names, quality, speaker maps, installation state, and model size, but not enough human-oriented voice characteristics for display labels.

See `proposal.md` and `specs/unified-voice-panel/spec.md` for the motivation and externally observable contract.

## Goals / Non-Goals

**Goals:**

- Make one selector group the source of truth for automatic and explicit selection dimensions.
- Keep automatic analysis running when needed for language/voice/quality resolution and adaptive emotion/prosody, even when the user pins another dimension.
- Keep presentation identities separate from Piper model keys, quality variants, and speaker IDs.
- Make the voice catalog self-describing enough that every rendered option has a useful label across all languages and speakers.
- Migrate existing browser settings without discarding draft or audio-player preferences.
- Preserve legacy HTTP request shapes for existing callers while giving the new page an unambiguous selection payload.

**Non-Goals:**

- Do not import Narakeet voice names, voice inventory, or audio assets. Its public voice list is only a UX reference for the pattern of a name followed by descriptive traits.
- Do not change Piper model files, speaker IDs, quality values, download URLs, synthesis formats, or the audio player's playback-speed control.
- Do not replace the existing language detector, emotion classifier, adaptive delivery algorithm, or script-directive syntax.
- Do not localize the metadata taxonomy or build a second text-to-speech provider catalog as part of this change.

## Decisions

### Use selector sentinels and a normalized selection envelope

Represent the three automatic choices with a stable internal sentinel, such as `auto`, while keeping visible text as `Auto Detect`. Store the selection as independent dimensions:

```json
{
  "language": "auto | <locale-code>",
  "voice": "auto | <voice-family-id>",
  "quality": "auto | <quality>",
  "speaker": {"name": "<name>", "id": 0},
  "emotion": "auto | <emotion>"
}
```

The page sends this envelope to analysis and synthesis. The server continues accepting legacy `mode`, `voice`, `speaker`, `speaker_id`, `delivery`, and `voice_speed` fields; when the envelope is present, it takes precedence and is translated into the existing analyzer/loader path. This keeps old API clients working while preventing the UI from encoding a combination of independent choices as a binary auto/manual mode.

Alternative considered: keep sending `mode: auto` or `mode: manual` and infer the other choices in JavaScript. Rejected because it duplicates resolver rules in the browser and cannot express combinations such as an explicit quality with automatic voice selection reliably.

### Resolve constraints in a deterministic precedence order

The normalized resolver will apply constraints in this order:

1. An explicit voice family and speaker pin the model family and speaker; the language associated with that voice is authoritative.
2. Otherwise, an explicit language limits candidates to that language family/locale.
3. An explicit quality limits candidates to that quality.
4. Any remaining automatic dimensions use the existing detector, preferred-locale/default-voice rules, installed-first selection, and quality priority.

The selector layer will prevent invalid combinations before submission: language changes rebuild voice choices, quality changes filter available voice variants, and a no-longer-valid explicit dependent choice is changed to `Auto Detect` with the new visible value persisted. When a voice is explicitly selected while Language is `Auto Detect`, the UI will synchronize the displayed language to that voice's catalog language so the panel never claims a conflicting language; the explicit voice remains the synthesis authority.

Alternative considered: let the server silently downgrade any incompatible explicit choice. Rejected because the user could see one selection while receiving another voice or quality.

### Keep one presentation model for voice and speaker choices

Normalize each catalog voice into a presentation record independent of quality, with its language, voice-family identity, speaker variant, available qualities, installation state by model key, and display metadata. Single-speaker entries produce one choice; multi-speaker entries produce one choice per speaker. The stable choice identity will use internal catalog identity plus speaker name/ID, while the display label is generated separately.

For an explicit language, the Voice name list is filtered to that language. For Language `Auto Detect`, it can show choices from all catalog languages, disambiguated with the human-readable language label where needed, so a user can pin a voice directly. Quality options are derived from the current voice choice when pinned, or from the eligible catalog candidates when the voice is automatic.

The picker uses natural numeric sorting for names and speaker ordinals, so
`Speaker 2` precedes `Speaker 10`. High-cardinality multi-speaker corpus
models (more than eight speakers) remain available to automatic resolution and
download/API flows but contribute one representative default-speaker choice to
the user-facing picker. Smaller multi-speaker models with meaningful speaker
names remain individually selectable. This keeps the panel usable without
removing any Piper model from the catalog.

### Add a complete project-owned display metadata manifest

Keep Piper's upstream catalog as the source of model availability and synthesis identifiers, and add a bundled metadata manifest keyed by catalog voice family and speaker variant. Each entry supplies a display name and one or more readable traits (for example gender, age, pitch, accent/region, timbre, or style). For corpus voices whose speakers only have opaque IDs, the manifest uses neutral, truthful traits such as the corpus name, language, and `Multi-speaker`, with a human-readable ordinal such as `Speaker 1`; it does not guess gender, age, pitch, or accent. The normalizer merges this manifest into catalog records and rejects or marks incomplete records during validation; runtime code must never render a raw dataset key or numeric speaker ID as the only label.

The manifest is deliberately separate from Piper's model IDs so descriptive text can evolve without changing downloads or API identifiers. A completeness test will compare the supported catalog snapshot and all speaker variants against the manifest. If the upstream catalog gains a new entry, catalog validation will fail until its display metadata is added.

Alternative considered: infer gender, age, or pitch from names and numeric IDs. Rejected because those identifiers do not encode reliable human characteristics and would create misleading labels. Neutral corpus/language labels are the approved fallback for speakers without trustworthy descriptive metadata.

### Use a version-two migration in the existing settings store

Keep the existing `piper.voiceStudio.settings.v1` storage key discoverable, but read both the current version-one object and the new version-two shape. On migration:

- legacy automatic mode becomes Language/Voice name/Quality `Auto Detect`;
- legacy manual mode becomes explicit language, voice-family/speaker, quality, and existing emotion when the catalog can resolve them;
- missing or stale voice/speaker references fall back to a valid automatic choice and are rewritten in normalized form;
- delivery is normalized to the existing adaptive/normal canonical values;
- draft, volume, mute, audible-volume, and playback-rate values remain untouched;
- storage errors retain the current in-memory behavior and warning message.

The migration is idempotent and also applies to cross-tab storage events. Reset settings writes the new defaults; reset everything removes the same Voice Studio and legacy playback keys already covered by the current implementation.

Alternative considered: introduce a second unrelated localStorage key and leave the old object untouched. Rejected because it leaves ambiguous sources of truth and makes cross-tab synchronization harder.

### Keep analysis as internal state, not a second mode UI

The client will request analysis whenever text or a selector changes, using the normalized selection envelope. Analysis remains the source for automatically resolved language/voice/quality and for existing emotion/prosody behavior; explicit selector dimensions override only their corresponding result. The existing user-facing manual controls remain visible, while technical analysis/debug fields stay behind the current internal-only boundary.

## Risks / Trade-offs

- [Risk] A complete descriptive metadata manifest requires judgment and maintenance for a large, changing catalog → keep it versioned, validate coverage in tests, and fail loudly for new unclassified entries instead of inventing traits.
- [Risk] Showing all-language voice choices when Language is automatic can create a large list → retain filtering when a language is explicit, use stable sorting and searchable/native select behavior where available, and include language only when needed for disambiguation.
- [Risk] Explicit voice and language can conflict during rapid selector changes → rebuild dependent options atomically, normalize state before analysis, and display the normalized selection after every change.
- [Risk] Legacy callers may depend on `mode` in `/info` or synthesis logs → preserve accepted legacy fields and retain compatibility telemetry fields while marking new requests with the unified selection semantics.
- [Risk] Catalog download failure can leave metadata unavailable → preserve installed-config fallback and use only metadata bundled with installed/catalog-known entries; show the existing catalog warning when remote data is unavailable.

## Migration Plan

1. Add the metadata manifest/schema and normalization/completeness tests before changing the selector behavior.
2. Extend catalog and resolver responses with stable presentation choices while preserving current model and speaker identifiers.
3. Add unified selection handling to analysis/synthesis endpoints, retaining the legacy request path and validation.
4. Replace the mode switch with the unified panel, add the three `Auto Detect` options, and update state/persistence/migration logic.
5. Run backend tests, template/static checks, and browser checks for all-auto, mixed constraints, explicit multi-speaker choices, unavailable downloads, reload, and legacy storage.
6. Roll back the template/client and server selection envelope independently if needed; model files, catalog IDs, and old HTTP request shapes remain compatible throughout.
