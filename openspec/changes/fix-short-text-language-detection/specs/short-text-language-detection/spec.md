## Purpose

Provide dependable Auto Detect voice resolution for short multilingual inputs so a low-confidence detector result does not silently route non-English text to an unrelated default voice.

## ADDED Requirements

### Requirement: Resolve short script-identifiable text before default fallback

When language, voice, and quality are set to Auto Detect, the system SHALL use the text's writing-script evidence and the available voice catalog to resolve a language family before applying the generic default-language fallback. A short input such as `Привет, как дела?` SHALL resolve to Russian when Russian is the strongest supported language interpretation, even when the unrestricted detector confidence is below the normal fallback threshold.

#### Scenario: Short Russian text resolves to Russian

- **WHEN** all selection dimensions are Auto Detect and the input is `Привет, как дела?`
- **THEN** analysis identifies the Russian language family and selects a Russian catalog voice instead of the configured English default voice

#### Scenario: Short Japanese text resolves to Japanese

- **WHEN** all selection dimensions are Auto Detect and the input is a short Japanese phrase containing Japanese-script evidence
- **THEN** analysis selects a Japanese catalog voice instead of falling back to the configured default language

#### Scenario: Ambiguous short text keeps a safe fallback

- **WHEN** all selection dimensions are Auto Detect and the input contains insufficient evidence to distinguish a supported language family
- **THEN** the system may use the configured default voice and SHALL report the low-confidence or ambiguous fallback reason

### Requirement: Do not synthesize short non-English text with an unrelated installed voice

When Auto Detect identifies a supported non-English language but the selected catalog voice is not installed, the system SHALL preserve that language and voice identity in analysis rather than replacing it with an installed voice from another language.

#### Scenario: Matching voice is not installed

- **WHEN** short Auto Detect input resolves to a supported language whose selected voice is absent locally
- **THEN** analysis marks that voice as requiring download, the UI shows the matching voice and Download required state, and Speak remains unavailable until the voice is installed

#### Scenario: Matching voice is installed

- **WHEN** short Auto Detect input resolves to a supported language whose selected voice is installed locally
- **THEN** synthesis uses that language-matched voice and returns playable WAV audio

### Requirement: Preserve explicit selection behavior

Explicit language, voice, quality, and speaker selections SHALL continue to take precedence over script-assisted Auto Detect resolution and SHALL retain their existing validation and error behavior.

#### Scenario: Explicit voice overrides automatic evidence

- **WHEN** the user explicitly selects a voice while the input text belongs to another language
- **THEN** the selected voice is used and automatic short-text resolution does not replace it
