## Purpose

Ensure that shared voice storage remains consistent when multiple users request the same missing model concurrently, while preserving the existing download API and user-visible workflow.

## ADDED Requirements

### Requirement: Deduplicate concurrent downloads for the same voice

For ordinary download requests that do not explicitly request a force-redownload, the system SHALL coordinate requests for the same voice and shared download directory so that at most one request performs the upstream download at a time.

#### Scenario: Two users request the same missing voice concurrently

- **WHEN** two download requests for the same voice arrive while its artifacts are missing
- **THEN** one request downloads the artifacts, the other request waits for that operation, and the upstream model and configuration are fetched no more than once
- **AND** both successful requests retain the existing `POST /download` success response contract

#### Scenario: Different voices are requested concurrently

- **WHEN** requests for two different voices arrive at the same time
- **THEN** coordination for one voice SHALL NOT prevent the other voice from being downloaded independently

### Requirement: Publish only complete voice artifacts

The system SHALL make a voice available for catalog status and synthesis only after its required model and configuration artifacts have each been downloaded successfully.

#### Scenario: Download is still in progress

- **WHEN** a voice download has not completed
- **THEN** incomplete temporary artifacts SHALL NOT be treated as an installed voice or loaded for synthesis

#### Scenario: Download fails partway through

- **WHEN** an upstream download fails before all required artifacts are complete
- **THEN** the failed operation SHALL leave no artifact that can be mistaken for a complete voice
- **AND** a later request SHALL be able to retry the voice download

### Requirement: Reuse completed artifacts

The system SHALL re-check the shared download directory after obtaining coordination for a voice and SHALL reuse valid completed artifacts instead of downloading them again.

#### Scenario: First request completes before a waiting request proceeds

- **WHEN** a waiting request obtains access after another request has completed the same voice download
- **THEN** it SHALL return success without fetching the voice from the upstream source again

#### Scenario: Voice is already installed

- **WHEN** a download request targets a voice whose required artifacts are already complete and does not request force-redownload
- **THEN** the request SHALL succeed without replacing or re-downloading those artifacts
