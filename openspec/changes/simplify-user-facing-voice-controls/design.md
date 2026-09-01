## Context

The web UI is a server-rendered HTML page with client-side state and selectors in `src/piper/templates/index.html`. It currently renders analysis metrics and per-segment cards, exposes Delivery controls, builds language labels from a locale code plus country, and models a manual choice as separate voice-name, quality, and speaker selectors. The backend already carries a normalized voice key, speaker map, and adaptive prosody result, so the change can preserve synthesis semantics while changing presentation.

## Goals / Non-Goals

**Goals:**

- Make the standard page show only user-relevant voice and playback controls.
- Keep analysis data and legacy delivery/speed values available to internal code and debugging without making them visible or keyboard-accessible in the normal page.
- Make adaptive delivery and normal speed the canonical effective settings for the standard flow.
- Generate human-readable language labels from existing language names and country fields.
- Derive combined voice/speaker presentation options while preserving the existing model key, speaker name, and numeric speaker ID used by synthesis.
- Preserve settings restoration, download status, quality filtering, and compatibility of existing request fields.

**Non-Goals:**

- Removing language codes, speaker IDs, delivery values, or speed presets from backend schemas or legacy API support.
- Replacing the existing emotion classifier or inventing a new prosody algorithm; the existing adaptive analysis remains the source of automatic variation.
- Changing the audio player playback-rate control, voice catalog contents, model download behavior, or synthesis engine format.

## Decisions

### Keep technical data in state, remove its presentation

Continue storing the latest analysis result in the existing client state and returning the same analysis data from the server. Stop rendering the analysis metrics, segment diagnostic cards, and other internal synthesis details in the ordinary page; leave actionable errors, download status, and the audio player visible. Internal debug code may inspect the state or record a temporary diagnostic snapshot, but no debug log is required for normal operation.

Alternative considered: delete analysis fields after synthesis. Rejected because the fields are needed to drive synthesis and would make future diagnosis harder.

### Treat adaptive/normal as canonical UI settings

Keep the old delivery and synthesis-speed select elements/options and their stable IDs in a non-visible compatibility/debug container so existing code and diagnostic tooling can still find them. During normal initialization, reset their effective values to `adaptive` and `normal`, and make analysis/synthesis payload construction use those canonical values. Preserve legacy stored values when reading them for compatibility/debug inspection, but do not let them override the standard flow or create visible custom controls.

The baseline request remains speed `1.0`; existing adaptive segment prosody and timing calculations continue to vary the resulting delivery based on text and emotion. Script directives and legacy API fields remain accepted internally unless an existing validation rule rejects them.

Alternative considered: remove the old controls and fields entirely. Rejected because it breaks debug hooks, persisted settings compatibility, and existing callers.

### Build a presentation option model for voice plus speaker

Keep catalog entries normalized as voice records with `key`, `quality`, `num_speakers`, and `speakers`. In the client selector layer, expand each voice record into presentation choices: one choice for a single-speaker voice, or one choice per mapped/fallback speaker for a multi-speaker voice. Each choice has a stable internal identity containing the voice key and speaker selection, plus a human-readable label such as `aru - 06 (1)`.

Resolve the selected choice back to the original voice record before populating quality, download status, analysis, and synthesis payloads. Continue sending the model as `voice` and the speaker as `speaker` or `speaker_id`, as appropriate. Store the combined choice’s underlying identifiers in the existing settings fields so old saved settings can be migrated by matching voice key and speaker values.

Alternative considered: encode the combined label directly as the server voice ID. Rejected because labels are presentation text and must not change model lookup or API identifiers.

### Generate language labels without machine identifiers

Use the existing native/English language name and country fields to create option text. The option value remains the locale code for filtering and lookup, but the text omits it. When native and English names are unavailable, use a neutral human-readable fallback rather than exposing the locale code; use country/region text to distinguish regional variants.

Alternative considered: translate or hard-code a second language registry. Rejected because the catalog already supplies the names and regions and a second registry would drift from catalog data.

## Risks / Trade-offs

- [Risk] Hidden compatibility controls could accidentally become visible through a future CSS or layout change → keep one explicit hidden wrapper, assert hidden/aria-hidden behavior in UI checks, and do not use the controls as the normal source of truth.
- [Risk] Old settings may refer to a speaker option that is no longer in the catalog → fall back deterministically to the first valid speaker while preserving the voice key and avoid sending an invalid speaker value.
- [Risk] Two catalog entries may produce the same human-readable language or voice label → include available country/region or speaker number in the label and keep the stable internal value unique.
- [Risk] Removing diagnostic rendering may make ad-hoc debugging less convenient → retain the full analysis result in state and document the temporary debug snapshot/log path in the implementation.
- [Risk] Automatic prosody changes can be mistaken for a user-selected playback speed → keep synthesis speed (generation baseline) separate from the audio player’s playback-rate control and retain clear internal field names.

## Migration Plan

1. Update the template and selector/state logic while retaining existing element IDs and request field names where practical.
2. Normalize old saved settings on load: preserve their diagnostic values, but apply adaptive/normal as the effective standard settings and map old voice/speaker pairs to the new combined option.
3. Verify auto and manual synthesis, installed and uninstalled voices, single- and multi-speaker catalogs, regional language labels, reset behavior, and responsive visibility.
4. Roll back by restoring the previous template/client logic; catalog and backend identifiers remain unchanged, so no data migration outside browser settings is required.
