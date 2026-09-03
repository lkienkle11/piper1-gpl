## Context

See proposal.md for the motivation. The completed concurrent-download change uses a per-voice filesystem lock and atomic artifact publication, but a failed owner currently releases the lock without publishing the failure result. Waiting callers then re-enter the downloader one by one and can repeat the same upstream failure.

## Goals / Non-Goals

**Goals:**

- Share transient failure state across threads and processes using the same download directory.
- Return the owner failure once, fail waiting/subsequent callers fast, and prevent repeated upstream attempts during cooldown.
- Permit one controlled half-open probe after cooldown and recover automatically on success.
- Provide correct HTTP status and `Retry-After` metadata.
- Preserve the current successful `/download` response and avoid unbounded browser retries.

**Non-Goals:**

- Do not add Redis, a queue, or a background worker.
- Do not retry downloads automatically in a loop or allow multiple half-open probes.
- Do not treat invalid voice IDs or permanent upstream not-found responses as transient outages.
- Do not change voice selection or automatically download during analysis/synthesis.

## Decisions

### Persist breaker state beside the per-voice lock

Store a small per-voice state record in the shared download directory, for example `.\<voice-id\>.download-state.json`. The record contains the breaker state, failure count, sanitized error information, and the next retry timestamp. State writes use the same atomic publication approach as voice artifacts, and the existing per-voice lock protects read-modify-write transitions.

The request path first reads an open state to fail fast, then re-reads it after acquiring the existing lock to close races. A request that was already waiting on the lock sees the failure record after the owner writes it and returns the shared circuit error instead of re-running the download. A successful download clears the state atomically.

Alternatives considered:

- In-memory breaker state: fast, but invisible to other worker processes and lost on restart.
- One global state file: shared, but creates unnecessary contention between unrelated voices.
- Redis or another distributed store: stronger for multi-host deployments, but outside the local shared-directory scope.

### Use closed, open, and half-open states

Use a default 30-second cooldown after the first transient failure. Repeated failures use bounded exponential backoff, for example 30s, 60s, 120s, up to a five-minute cap. The values should be centralized configuration constants so they can be tuned without changing the API contract.

When `retry_at` is reached, the first request that obtains the voice lock atomically claims half-open state and performs the only probe. Requests that see half-open or probe-in-progress return `503` with the same retry timestamp. This deliberately uses one probe rather than “a few” simultaneous probes: one successful probe is enough to establish recovery, while several probes recreate the duplicate-download problem.

The existing `force_redownload` flag participates in the breaker and lock; it does not bypass an open circuit. This keeps the operator escape hatch from becoming an accidental retry-storm escape hatch.

### Classify errors at the downloader boundary

Map network failures, timeouts, upstream HTTP 5xx, and rate-limit responses to a transient download error that records breaker state. Invalid identifiers remain `ValueError`; upstream 4xx/not-found responses remain permanent errors and do not open the transient circuit. Error text stored in shared state must be sanitized and bounded so it does not expose credentials, request headers, or unbounded upstream bodies.

The HTTP route maps an owner transient error to `502 Bad Gateway` and maps open/half-open circuit responses to `503 Service Unavailable`. Both responses use the existing JSON error shape plus a stable error code and `Retry-After` header. `501 Not Implemented` is not used.

### Keep the browser passive

The browser continues to make one explicit download request. It parses the error response and presents the retry delay; it does not schedule repeated fetches. Manual retry after the indicated time is safe because the server-side half-open transition still allows only one probe.

## Risks / Trade-offs

- [Risk] A stale state record survives a process restart → evaluate `retry_at` using wall-clock timestamps, clear it on success, and allow the cooldown/half-open transition to recover without manual cleanup.
- [Risk] Multiple processes race to claim half-open → perform the claim while holding the existing per-voice filesystem lock and re-check state after lock acquisition.
- [Risk] A large waiting group still wakes after the owner fails → every waiter performs only a local state check and returns `503`; none contacts the upstream source.
- [Risk] Clock changes affect retry timing → clamp negative remaining durations to zero and use a bounded retry calculation; document the state as advisory until the next lock-protected transition.
- [Risk] Permanent upstream errors may be retried manually → do not trip the transient circuit, but return the permanent error category so clients do not interpret it as a temporary outage.
