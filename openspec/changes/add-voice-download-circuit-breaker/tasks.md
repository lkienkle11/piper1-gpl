## 1. Breaker state and failure classification

- [x] 1.1 Define shared per-voice breaker state, cooldown/backoff constants, stable error types, and transient/permanent failure classification; verify invalid IDs and permanent upstream errors do not trip the breaker.
- [x] 1.2 Persist breaker state atomically beside the existing per-voice lock, including sanitized error details and retry timestamp; verify concurrent processes cannot overwrite a newer state transition.

## 2. Download lifecycle integration

- [x] 2.1 Check open state before download and re-check it after lock acquisition, then publish a single half-open probe claim; verify waiting callers reuse the shared failure instead of invoking upstream again.
- [x] 2.2 Clear breaker state after successful download and reopen it with bounded exponential backoff after a failed probe; verify success recovery and repeated-failure cooldown behavior.
- [x] 2.3 Preserve `force_redownload` and completed-artifact behavior while preventing force requests from bypassing an open circuit; verify valid existing voices remain unaffected.

## 3. HTTP and browser behavior

- [x] 3.1 Map owner upstream failures to HTTP 502 and open/half-open circuit responses to HTTP 503 with stable JSON error codes and `Retry-After`; verify invalid/permanent errors retain their client-error categories.
- [x] 3.2 Update the web download error presentation to show retry guidance without scheduling automatic retry loops; verify one explicit browser action produces at most one HTTP download request.

## 4. Regression coverage

- [x] 4.1 Add downloader tests for failure fan-out across waiting callers, zero upstream calls during cooldown, one half-open probe, successful recovery, and bounded repeated backoff.
- [x] 4.2 Add HTTP tests for 502/503 payloads and headers, retry-after behavior, permanent-error classification, and concurrent callers sharing one failure state.
- [x] 4.3 Run focused and full tests, formatting/import checks, strict OpenSpec validation, and confirm no unrelated files are changed.
