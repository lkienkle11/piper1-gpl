## Why

The Docker image and build context predate the current Piper web runtime. Recent
multilingual Auto Detect, voice catalog, Stanza analysis, and concurrent voice
download changes are not fully represented in the image, while the current
entrypoint can leave downloaded artifacts outside the intended persistent data
location. This change is needed now so the container runs the same supported web
runtime as the source installation with predictable persistence.

## What Changes

- Reconcile the multi-stage Docker build with the current package metadata and
  install the default web runtime extras required by the current HTTP
  experience: `http`, `ja`, and `zh`.
- Provide an explicit Docker-only `nlp` build profile for users who need Stanza;
  this profile may be large, but it SHALL not require installing dependencies on
  the host or connecting to an external NLP service.
- Expand the Docker build context to include all package assets required by the
  current wheel, including web templates and images, the voice catalog, language
  data, and license/source files.
- Make `/data` the sole persistent runtime location for downloaded voices,
  per-voice download locks, circuit-breaker state, and optional linguistic
  resources.
- Enforce an explicit `/data` download directory in the Docker entrypoint so
  voice downloads cannot default to the container work directory.
- Declare and document a Docker-managed named volume workflow; do not require or
  document host bind mounts for runtime data.
- Keep port 5000 as the container's default HTTP port and preserve passthrough of
  the existing `--port` override. Host port remapping remains optional.
- Document the Docker build, named-volume lifecycle, voice download, server
  startup, optional Stanza resource setup, and HTTP smoke checks.
- Validate package contents, container startup, HTTP endpoints, and data
  persistence across container recreation.

## Capabilities

### New Capabilities

- `docker-runtime-packaging`: Defines the dependency, asset, port, storage, and
  operational contract for running the current Piper HTTP runtime in Docker.

### Modified Capabilities

None.

## Impact

- Docker build and runtime files: `Dockerfile`, `.dockerignore`, and
  `docker/entrypoint.sh`.
- HTTP deployment documentation in `docs/API_HTTP.md`.
- Runtime dependencies declared by `setup.py` and the packaged wheel contents.
- Container storage behavior for voice files, download coordination metadata, and
  optional Stanza resources.
- Build and container smoke-test procedures; no HTTP request schema or core
  synthesis behavior changes are intended.
