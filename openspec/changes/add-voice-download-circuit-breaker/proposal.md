## Why

The current per-voice lock prevents duplicate downloads, but it does not share a failed download result. If the first request fails, every waiting request can acquire the lock in turn and retry the same broken upstream operation, creating a retry storm when many users click Download together.

## What Changes

- Add a shared per-voice circuit breaker for transient voice-download failures.
- Propagate one failed download result to waiting and subsequent users without starting another upstream download.
- Return appropriate server errors (`502` for an upstream failure and `503` while the circuit is open) with `Retry-After` guidance.
- Use a cooldown, single half-open probe, and bounded exponential backoff so a large group of users produces at most one retry probe per interval.
- Clear the failure state after a successful download and preserve the existing successful `/download` response contract.
- Keep invalid voice requests and permanent not-found errors separate from transient upstream failures.
- Add backend/API regression coverage for failure fan-out, cooldown, half-open probing, recovery, and repeated failure.

## Capabilities

### New Capabilities

- `voice-download-circuit-breaker`: Share voice-download failure state and limit retries against an unavailable upstream source.

### Modified Capabilities

<!-- No main capability spec exists for the completed concurrent-download change; integration with its existing lock is described in the new capability. -->

## Impact

- `src/piper/download_voices.py`: failure classification, shared breaker state, cooldown/backoff, and retry coordination.
- `src/piper/http_server.py`: map upstream and open-circuit failures to stable HTTP status codes and headers.
- `src/piper/templates/index.html`: display server retry guidance without issuing uncontrolled automatic download retries.
- `tests/`: concurrent failure, status-code, cooldown, recovery, and upstream-call-count coverage.
- Runtime storage: add small per-voice failure-state metadata beside the existing download lock; no external Redis or distributed service is required.
