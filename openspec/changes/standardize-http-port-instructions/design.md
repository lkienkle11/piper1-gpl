## Context

See `proposal.md` for the motivation. The current HTTP server already accepts a
single `--port` option and defaults it to 5000. The source setup section in
`docs/API_HTTP.md` repeats 7860 in each command and in each URL, while the PyPI
and Docker guidance establishes 5000 as the default.

## Goals / Non-Goals

**Goals:**

- Make port selection visible in one dedicated documentation section.
- Set 5000 as the source-instruction default while preserving 7860 as an easy
  alternate value.
- Make every source setup command and its displayed URL use the same selected
  value.
- Keep the instructions copyable as shell commands after the configuration
  value is selected.

**Non-Goals:**

- Do not add or rename runtime CLI options.
- Do not split the web UI and HTTP API onto separate ports.
- Do not change the Docker container's internal port or the HTTP server behavior.
- Do not introduce a new environment-variable feature in application code.

## Decisions

### Use one shell variable in a dedicated port section

Add a short `Port configuration` section before the source setup variants with
`PIPER_PORT=5000`. Source commands pass `--port "${PIPER_PORT}"`, and the
instructions show the matching URL using the same value. Users who need 7860
change only the assignment.

This is preferred over adding a named `--port-7860` option because the existing
`--port` option already supports arbitrary valid ports and the requested change
is documentation organization, not a runtime capability.

### Apply the variable consistently to all source variants

Replace the repeated source examples and their `127.0.0.1:7860` links with the
selected variable. Keep the three environment/storage variants intact so the
port refactor does not alter their setup behavior.

### Explain Docker mapping separately

Keep the Piper container port documented as 5000. If an external host port is
desired, document the Docker mapping form `-p 7860:5000` as an optional host
mapping, making clear that the right-hand port remains Piper's internal port.

### Preserve direct default behavior

Do not add an explicit `--port` to the PyPI command solely for consistency. Its
existing default behavior remains documented as 5000, while the source examples
make the selected value explicit through `PIPER_PORT`.

## Risks / Trade-offs

- [Risk] A reader copies a setup block without copying the configuration line
  and gets an empty variable → Keep the configuration section immediately before
  the setup variants and state that it must be run first.
- [Risk] A URL or command retains a stale literal port → Verify the edited
  documentation for source-flow port literals and manually inspect every setup
  block.
- [Risk] Users confuse host and container ports in Docker → Label the mapping
  explicitly as `host:container` and retain 5000 as the container-side value.

## Migration Plan

This is a documentation-only change. Update `docs/API_HTTP.md`, then verify the
rendered Markdown/code blocks and search for remaining source-flow references to
7860 or inconsistent source URLs. No runtime migration or rollback procedure is
required; reverting the documentation commit restores the previous guidance.
