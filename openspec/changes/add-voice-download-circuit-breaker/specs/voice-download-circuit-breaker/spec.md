## Purpose

Protect the shared voice-download service from retry storms by sharing transient failures, enforcing a cooldown, and allowing only one controlled recovery probe at a time.

## ADDED Requirements

### Requirement: Share transient download failures

The system SHALL record the latest transient failure for each voice and shared download directory so that requests waiting behind the failed operation and requests arriving while the circuit is open do not start another upstream download.

#### Scenario: Owner download fails while other users wait

- **WHEN** one request fails because the upstream voice download is temporarily unavailable while other requests wait for the same voice
- **THEN** the owner request SHALL receive an upstream failure response
- **AND** waiting requests SHALL receive the shared failure state without performing another upstream download
- **AND** the response SHALL include retry timing guidance

#### Scenario: Many users request a voice while its circuit is open

- **WHEN** multiple users request the same voice during its cooldown period
- **THEN** each request SHALL fail fast with a service-unavailable response
- **AND** no request SHALL contact the upstream voice source during that cooldown

### Requirement: Control recovery with a half-open probe

After a transient failure cooldown expires, the system SHALL allow exactly one request for a voice to probe the upstream source while concurrent requests continue to receive retry guidance.

#### Scenario: First request arrives after cooldown

- **WHEN** the cooldown has expired and a request arrives for the failed voice
- **THEN** that request SHALL become the single half-open probe
- **AND** concurrent requests SHALL NOT start additional probes

#### Scenario: Probe succeeds

- **WHEN** the half-open probe downloads the voice successfully
- **THEN** the circuit SHALL close, the failure state SHALL be cleared, and subsequent requests SHALL use the normal download path

#### Scenario: Probe fails again

- **WHEN** the half-open probe encounters another transient upstream failure
- **THEN** the circuit SHALL reopen
- **AND** the next retry time SHALL use bounded backoff rather than allowing an immediate retry storm

### Requirement: Classify failures and expose stable HTTP responses

The system SHALL distinguish transient upstream failures from invalid requests and permanent missing-voice responses, and SHALL expose the distinction through stable HTTP status and retry metadata.

#### Scenario: Upstream service or network failure

- **WHEN** a valid voice download fails due to an upstream server error, timeout, or network failure
- **THEN** the owner request SHALL receive HTTP `502`
- **AND** the response SHALL identify the voice-download upstream failure and include `Retry-After`

#### Scenario: Circuit is open or a probe is already active

- **WHEN** a request arrives while the voice circuit is open or another request is probing it
- **THEN** the request SHALL receive HTTP `503`
- **AND** the response SHALL include `Retry-After` for the next permitted retry

#### Scenario: Invalid or permanently unavailable voice

- **WHEN** the request contains an invalid voice identifier or the upstream reports a permanent not-found/client error
- **THEN** the request SHALL receive the existing client/permanent-error response category
- **AND** it SHALL NOT open the transient circuit

### Requirement: Avoid uncontrolled client retries

The web interface SHALL display the server's download failure and retry guidance without automatically issuing unbounded retry requests.

#### Scenario: Download is rejected by the circuit breaker

- **WHEN** the download endpoint returns an open-circuit or upstream-failure response
- **THEN** the current user SHALL see an actionable retry message containing the server-provided retry timing
- **AND** the browser SHALL not launch repeated automatic download attempts
