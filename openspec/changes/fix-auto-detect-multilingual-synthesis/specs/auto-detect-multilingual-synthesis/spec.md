## Purpose

Ensure the web application produces playable speech when language, voice, quality, speaker, and emotion are all left on Auto Detect for supported multilingual input.

## ADDED Requirements

### Requirement: Auto Detect synthesizes supported multilingual text

The application SHALL synthesize playable WAV audio for supported English, Vietnamese, Japanese, and Chinese text when all voice-selection options are set to Auto Detect and the selected voice model is available.

#### Scenario: Japanese Auto Detect playback

- **WHEN** a user enters Japanese text, leaves every voice-selection option on Auto Detect, and selects Speak
- **THEN** the application returns successful synthesis with an audio response that can be loaded and played by the browser

#### Scenario: Chinese Auto Detect playback

- **WHEN** a user enters Chinese text, leaves every voice-selection option on Auto Detect, and selects Speak
- **THEN** the application returns successful synthesis with an audio response that can be loaded and played by the browser

#### Scenario: Existing English and Vietnamese playback remains available

- **WHEN** a user enters English or Vietnamese text, leaves every voice-selection option on Auto Detect, and selects Speak
- **THEN** the application returns successful synthesis with playable audio

### Requirement: Download success is not treated as synthesis success

The application and its regression coverage MUST distinguish a successful voice download from successful synthesis and playback.

#### Scenario: Downloaded voice is usable

- **WHEN** Auto Detect selects a voice that is not yet present and the voice download completes successfully
- **THEN** the application proceeds to synthesis and playback, and the test passes only after a valid audio response is produced

#### Scenario: Synthesis dependency failure is actionable

- **WHEN** an installation intentionally omits the optional phonemizer dependency required by the selected language
- **THEN** synthesis returns the existing structured dependency error with the missing package and installation extra identified
