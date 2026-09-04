## 1. Centralize Port Configuration

- [x] 1.1 Add a `Port configuration` section before the source setup variants, define `PIPER_PORT=5000`, and explain how to select 7860; verify the section is visible before any source command that references the variable.
- [x] 1.2 State that the Piper web UI and HTTP API share the selected server port; verify the guidance does not imply separate UI and API listeners.

## 2. Update Source and Docker Guidance

- [x] 2.1 Replace hard-coded source command ports and source setup URLs with `PIPER_PORT`; verify all three source variants use the same variable and matching URL.
- [x] 2.2 Add optional Docker host mapping guidance using `host:container` notation while keeping 5000 as the container-side port; verify the example communicates `7860:5000` correctly.
- [x] 2.3 Preserve the existing CLI, PyPI, and source setup flows without adding runtime options or changing their voice/data configuration; verify the diff is limited to the intended documentation file.

## 3. Documentation Validation

- [x] 3.1 Search `docs/API_HTTP.md` for stale source-flow literals and manually inspect every port command and URL; verify no source block hard-codes `--port 7860` or mismatches the configured variable.
- [x] 3.2 Run `openspec validate standardize-http-port-instructions --strict --no-interactive` and verify the change passes validation.
