## Why

The source setup instructions hard-code port 7860 in multiple commands even
though Piper and Docker use port 5000 by default. This makes copied instructions
unexpectedly start the service on 7860 and forces users to edit repeated values.

## What Changes

- Add a dedicated port configuration section to `docs/API_HTTP.md`.
- Define port 5000 as the documented default through one `PIPER_PORT` value.
- Explain that users can change `PIPER_PORT` to 7860 when they need the alternate
  port.
- Update the source setup commands and URLs to reference `PIPER_PORT` instead of
  repeating a hard-coded port.
- Clarify that the Piper web UI and HTTP API share the configured server port.
- Make no changes to the runtime CLI, Docker internal port, or HTTP API behavior.

## Capabilities

### New Capabilities

None. This is a documentation-only change.

### Modified Capabilities

None. No system requirement or externally observable runtime behavior changes.

## Impact

- Affected documentation: `docs/API_HTTP.md`.
- No code, dependency, API, Docker image, or deployment behavior changes.
- No spec delta is required because the change only improves instructions.

## Scope

This change covers the source setup instructions and their port guidance. The
existing `--port` CLI option remains the mechanism for selecting the runtime
port.
