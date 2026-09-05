## Why

The source setup instructions install and configure Stanza, while the Docker
runtime currently treats NLP as a separate optional profile. This creates two
different supported runtimes, and the shared linguistic analyzer also requests
the mwt processor for languages whose resources do not provide it. The change
is needed to make host and Docker behavior equivalent while reducing avoidable
PyTorch and Stanza model footprint.

## What Changes

- Make the standard Docker runtime include the same HTTP, multilingual, and
  Stanza capabilities used by the supported source setup.
- Install a CPU-only PyTorch runtime for Docker so the image does not pull an
  unnecessary CUDA/NVIDIA dependency tree.
- Keep Stanza model weights outside the image in the Docker-managed named
  volume under /data/stanza.
- Add one shared language-to-processor definition and resource preparation
  flow used by both host and Docker execution.
- Download only the processors required by each supported language instead of
  downloading every default Stanza package component.
- Stop forcing mwt for languages whose Stanza resources do not support it,
  while preserving the existing analysis response and fallback behavior.
- Update Docker and source documentation so both flows expose the same NLP
  behavior, with only their storage paths differing.
- Make the Docker quick-start flow self-contained by including the one-time
  Stanza preparation step and the `/data/stanza` server option before the
  first `/analyze` request.
- Add host and container tests for resource preparation, five-language Stanza
  analysis, missing-resource fallback, and Docker image footprint constraints.
- Preserve port 5000, the Docker-managed /data volume contract, voice download
  coordination, and the existing semantic-provider boundary.

## Capabilities

### New Capabilities

- docker-runtime-packaging: Defines the unified Docker and host linguistic
  runtime, optimized Stanza resource flow, package assets, port, and persistent
  storage contract.

### Modified Capabilities

None.

## Impact

- Docker runtime files: Dockerfile, .dockerignore, and docker/entrypoint.sh.
- Shared linguistic analysis and Stanza resource preparation code under
  src/piper/.
- Package dependency resolution in setup.py and the Docker build.
- Host and Docker sections of docs/API_HTTP.md, including the copyable Docker
  quick-start sequence.
- Unit, integration, and container validation for linguistic analysis and
  runtime parity.
