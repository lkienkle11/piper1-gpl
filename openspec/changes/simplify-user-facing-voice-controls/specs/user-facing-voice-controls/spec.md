## Purpose

Provide a clear, user-oriented voice selection experience while preserving the technical analysis and synthesis controls needed for internal behavior, compatibility, and future debugging.

## ADDED Requirements

### Requirement: Developer analysis is not presented in the normal UI

The normal Voice Studio experience SHALL NOT display per-segment analysis cards or other technical fields that expose context, emotion classification, synthesis rate, pause timing, confidence, or internal voice-selection diagnostics. The corresponding analysis result SHALL remain available to the application for synthesis, state inspection, and future debugging without requiring it to be rendered to the user.

#### Scenario: User views analyzed text

- **WHEN** text analysis completes
- **THEN** the text and voice controls remain usable, but the technical analysis panel and per-segment diagnostic preview are not visible or accessible as user-facing content

#### Scenario: Debugging needs the analysis result

- **WHEN** the application analyzes or synthesizes text
- **THEN** the analysis metadata remains available through the existing internal result/state path or temporary diagnostic logging and is not discarded solely because its UI presentation is hidden

### Requirement: Delivery behavior is automatic and not user-configurable

The standard Voice Studio flow SHALL use adaptive delivery with normal synthesis speed as its baseline. The synthesis engine SHALL continue to derive timing/prosody adjustments from the text structure and detected or selected emotion. Delivery mode, synthesis-speed presets, and custom speed values MAY remain in internal compatibility/debug data, but SHALL NOT be exposed as ordinary user controls.

#### Scenario: New or reset settings are used

- **WHEN** the standard flow starts or settings are reset
- **THEN** the effective delivery mode is adaptive and the effective baseline synthesis speed is normal (1.00x)

#### Scenario: Text or emotion calls for automatic variation

- **WHEN** analyzed text contains different contexts, segment structures, or emotions
- **THEN** the generated synthesis may use the corresponding automatic timing/prosody variation without requiring the user to choose a delivery mode or speed preset

#### Scenario: Existing settings contain a legacy delivery choice

- **WHEN** previously persisted settings contain fixed delivery or custom speed values
- **THEN** they may be read and retained for compatibility/debugging, but the standard user-facing flow uses adaptive delivery and the normal baseline rather than presenting those values as editable controls

### Requirement: Language options use human-readable labels

Every option in the user-facing Language selector SHALL identify the language and, when needed, its region or country using words such as `English (Great Britain)` or `English (United States)`. Language option labels MUST NOT contain locale codes such as `en_GB`, `en_US`, or any other machine language identifier. Locale codes SHALL remain available only as internal values used for catalog lookup and synthesis.

#### Scenario: User opens the Language selector

- **WHEN** the language options are rendered
- **THEN** the labels are understandable language/region names and no option label contains an underscore-form locale code or other language code

#### Scenario: Two regional variants share a language name

- **WHEN** multiple regions exist for the same language
- **THEN** their country or region names distinguish them clearly without showing the machine locale code

### Requirement: Voice name and speaker are selected together

The manual voice controls SHALL provide one user-facing selector titled `Voice name` that represents the voice and speaker choice together. For a multi-speaker voice, each option SHALL include the voice name and the speaker name or number in a clear label; the selected option SHALL still resolve to the correct underlying voice key and speaker identifier. A separate user-facing Speaker selector SHALL NOT be required.

#### Scenario: User selects a multi-speaker voice

- **WHEN** a voice has multiple speakers
- **THEN** the Voice name selector offers distinct combined options such as `aru - 03 (0)` and `aru - 06 (1)`, and synthesis uses the speaker represented by the selected option

#### Scenario: User selects a single-speaker voice

- **WHEN** a voice has no meaningful speaker choices
- **THEN** the Voice name selector offers the voice without forcing the user to configure a separate speaker control, while synthesis keeps the existing default-speaker behavior

#### Scenario: User reloads the application

- **WHEN** a previously selected combined voice/speaker option is restored
- **THEN** the same visible option is selected when available and the stored internal voice/speaker identifiers continue to resolve correctly

### Requirement: Existing voice availability behavior remains intact

Simplifying the selectors SHALL NOT change language filtering, quality selection, installed/download status, voice loading, or synthesis error handling. The internal identifiers sent to the server SHALL continue to identify the same model and speaker as before.

#### Scenario: Selected voice is not installed

- **WHEN** a user selects a catalog voice that is not installed
- **THEN** the existing download-required state and download action remain available without exposing technical delivery controls

#### Scenario: Selected voice is synthesized

- **WHEN** a user submits text with a selected manual or automatically resolved voice
- **THEN** the request resolves the same model and speaker semantics as the prior separate Voice name and Speaker controls
