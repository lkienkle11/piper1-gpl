## Purpose

Give users one predictable voice panel where language, voice, and quality can each be automatic or explicitly chosen, while preserving Piper's existing automatic analysis and synthesis behavior behind clear, persistent controls.

## ADDED Requirements

### Requirement: Voice selection uses one unified panel

The Voice Studio SHALL present one voice-selection panel containing the existing Language, Voice name, Quality, and Emotion controls. The page SHALL NOT require the user to switch between separate Auto Detect and Manual Voice menus, and it SHALL preserve the existing manual controls and their meanings apart from adding the required automatic options.

#### Scenario: User opens Voice Studio

- **WHEN** the page is loaded
- **THEN** one voice panel is visible with Language, Voice name, Quality, and Emotion controls, and no Auto Detect / Manual Voice mode switch is required to use it

#### Scenario: User changes an existing manual control

- **WHEN** the user changes Language, Voice name, Quality, or Emotion
- **THEN** the corresponding existing selection behavior remains available and the current voice availability, download, Speak, and playback interactions continue to work

### Requirement: Automatic and explicit selections coexist in the panel

The Language, Voice name, and Quality selectors SHALL each contain an `Auto Detect` option. Each selector SHALL be resolved independently for every new text submission: an explicit value SHALL remain effective, while `Auto Detect` SHALL use the existing automatic analysis or selection behavior for that dimension.

#### Scenario: All three selectors use Auto Detect

- **WHEN** Language, Voice name, and Quality are all set to `Auto Detect`
- **THEN** the system detects the text language and resolves the voice and quality using the existing automatic fallback and availability rules

#### Scenario: Language is explicit and voice/quality are automatic

- **WHEN** the user selects a concrete Language, leaves Voice name and Quality at `Auto Detect`, and submits new text
- **THEN** synthesis uses the configured language and automatically chooses an available voice and quality within that language

#### Scenario: Voice is explicit

- **WHEN** the user selects a concrete Voice name and submits different text later
- **THEN** synthesis uses that configured voice and speaker for the later text, and automatic language analysis SHALL NOT silently replace the pinned voice

#### Scenario: Quality is explicit

- **WHEN** the user selects a concrete Quality and submits new text
- **THEN** the selected quality is used whenever a matching voice is available, and the Voice name choices remain constrained to compatible catalog entries

#### Scenario: A selection combination is incompatible

- **WHEN** a language, voice, or quality change makes the current combination unavailable
- **THEN** the panel moves the affected dependent selection to `Auto Detect` or another visibly valid option before synthesis, and SHALL NOT send an unintended model or quality while displaying the old choice

### Requirement: Explicit voice choices have descriptive labels for every catalog entry

Every user-facing Voice name option SHALL use a human-readable display label that identifies the voice and describes its characteristics, such as gender, age, pitch, accent or region, vocal quality, or style. Labels SHALL NOT consist only of a dataset key, opaque machine name, numeric speaker ID, or an unexplained index. This requirement SHALL apply to every supported language, every catalog voice, and every multi-speaker variant.

#### Scenario: User opens the Voice name selector

- **WHEN** voice options are rendered for any supported language
- **THEN** each option has a clear voice name plus one or more descriptive attributes, following the readable pattern illustrated by `Alex (Male, High)` without copying Narakeet's voice inventory

#### Scenario: Voice metadata is absent upstream

- **WHEN** the upstream Piper catalog does not provide enough descriptive metadata for a voice
- **THEN** the application obtains the missing display metadata from a complete project-owned source before rendering the option, using a neutral truthful label such as `LibriTTS Speaker 1 (English, Multi-speaker)` when individual characteristics are unavailable, and SHALL NOT fall back to an identifier-only label or invent personal characteristics

#### Scenario: Multi-speaker voice is rendered

- **WHEN** a voice exposes multiple speakers
- **THEN** each selectable speaker variant has a distinct descriptive label while its underlying voice key and speaker name/ID remain unchanged for synthesis

### Requirement: Voice choices are naturally ordered and concise

The Voice name selector SHALL use natural, case-insensitive ordering for voice
names and numeric speaker ordinals. High-cardinality multi-speaker corpus
models SHALL contribute at most one representative default-speaker choice to
the user-facing selector, while remaining available for automatic resolution,
download, and API requests. Smaller multi-speaker models with meaningful names
MAY continue to expose each named speaker.

#### Scenario: Numeric speaker labels are sorted

- **WHEN** a selector contains `Speaker 2` and `Speaker 10`
- **THEN** `Speaker 2` appears before `Speaker 10`

#### Scenario: A corpus has many speakers

- **WHEN** a catalog voice has more than eight speakers
- **THEN** the selector shows one clearly labeled representative choice and does not expand every corpus speaker into a separate option

### Requirement: Voice selection settings persist and migrate safely

The application SHALL persist the unified Language, Voice name/speaker, Quality, and Emotion selections in browser-local settings. A concrete selection SHALL be restored after reload and remain effective for subsequent text until changed to `Auto Detect`. Existing saved settings SHALL be migrated deterministically without losing unrelated saved draft, player, or playback preferences.

#### Scenario: User changes a unified selection

- **WHEN** the user changes Language, Voice name, Quality, or Emotion
- **THEN** the new selection is written to local browser storage and is used by the next analysis or synthesis request

#### Scenario: User reloads with valid saved selections

- **WHEN** the page reloads and the saved voice/speaker and catalog entries still exist
- **THEN** the same visible choices are restored, including the selected `Auto Detect` values, and the internal identifiers resolve to the same model and speaker

#### Scenario: Existing version-one settings are present

- **WHEN** storage contains the existing mode-based settings format
- **THEN** an old automatic mode migrates to `Auto Detect` selector values, an old manual mode migrates its voice, speaker, quality, and emotion to explicit unified selections, and the existing draft/player settings remain available

#### Scenario: Saved voice is no longer available

- **WHEN** a saved voice or speaker cannot be found in the current catalog
- **THEN** the application falls back to a valid `Auto Detect` or available catalog choice, persists the normalized result, and does not submit an invalid internal identifier

### Requirement: Synthesis compatibility and availability are preserved

The unified panel SHALL preserve existing language filtering, quality filtering, installed/download-required status, voice download behavior, synthesis error handling, adaptive delivery, and audio playback behavior. Display labels and automatic selector values SHALL remain separate from the internal model key, quality value, and speaker name/ID sent to the server.

#### Scenario: Selected model is not installed

- **WHEN** the resolved explicit or automatic voice is present in the catalog but is not installed
- **THEN** the existing download-required state and download action remain available, and Speak remains blocked until the voice is ready

#### Scenario: Explicit multi-speaker voice is synthesized

- **WHEN** the user submits text with a descriptive multi-speaker Voice name option selected
- **THEN** the request uses the same underlying voice key and speaker name/ID represented by that option, regardless of its display label

#### Scenario: Automatic analysis remains available

- **WHEN** one or more selectors are set to `Auto Detect`
- **THEN** existing language/context/emotion analysis and adaptive delivery continue to drive only the automatic dimensions without exposing a second mode menu
