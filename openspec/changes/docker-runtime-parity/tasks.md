## 1. Reconcile the unified runtime dependencies

- [x] 1.1 Update .dockerignore and Dockerfile build inputs to retain every
  source, package-data, web asset, language asset, and license/source file
  required by setup.py; verify the clean Docker build context contains the
  required paths.
- [x] 1.2 Build the local Piper wheel and install the standard final image with
  the current HTTP, Japanese, Chinese, and NLP runtime dependencies; verify
  the image imports Flask, Stanza, PyTorch, and the language runtime modules.
- [x] 1.3 Constrain the Docker NLP runtime to a CPU-only PyTorch distribution
  without CUDA/NVIDIA packages; verify the dependency inventory and runtime
  report CPU execution.
- [x] 1.4 Keep build-only toolchains out of the final image and verify the
  final image contains the runtime wheel and dependencies without the builder
  virtual environment.

## 2. Enforce the persistent Docker data contract

- [x] 2.1 Declare /data as the image data volume and make the Docker runtime
  contract use a Docker-managed named volume; verify image metadata declares
  /data and documented commands contain no host bind mount.
- [x] 2.2 Update the Docker entrypoint so download and server explicitly use
  /data for voice discovery and downloads, while preserving supported argument
  passthrough; verify entrypoint help and command-line inspection.
- [x] 2.3 Verify downloaded model/configuration files, per-voice lock files,
  and circuit-breaker state are created under /data and remain available after
  removing and recreating a container with the same named volume.

## 3. Share Stanza resource and pipeline behavior

- [x] 3.1 Add one shared supported-language processor definition and
  resource-preparation module; verify host preparation and analyzer pipeline
  construction consume the same mapping.
- [x] 3.2 Add an explicit host and Docker resource-preparation command with
  language selection and a model-directory argument; verify selected resources
  are written only to the requested directory and no unselected language is
  downloaded.
- [x] 3.3 Replace the language-independent mwt requirement with language-aware
  processor selection; verify Vietnamese analysis works with its available
  resources and all supported languages retain available serialized fields.
- [x] 3.4 Preserve missing-resource fallback and no-request-time-download
  behavior; verify /analyze falls back cleanly and /synthesize remains
  functional when Stanza resources are absent.

## 4. Preserve HTTP and runtime behavior

- [x] 4.1 Keep port 5000 as the container-side default, pass through the
  existing --port option, and document host-to-container mapping; verify the
  default server responds through 5000:5000 and custom mapping remains
  functional.
- [x] 4.2 Document semantic-provider Docker usage as an explicit connection to
  a separately managed llama.cpp endpoint, including container reachability and
  the existing privacy/external-endpoint policy; verify the Piper image does
  not contain GGUF or llama.cpp runtime files.
- [x] 4.3 Verify Vietnamese, English, Japanese, and Chinese synthesis remains
  playable with and without prepared Stanza resources; verify linguistic
  fallback does not block speech generation.

## 5. Update deployment documentation

- [x] 5.1 Rewrite the Docker section as the standard NLP-enabled flow,
  including CPU-only image build expectations, named-volume creation, voice
  download, Stanza preparation at /data/stanza, server startup on port 5000,
  and an /analyze verification request.
- [x] 5.2 Update all three source setup blocks to use the shared
  processor-aware preparation interface and explain the host-local model
  directory equivalent of Docker /data/stanza.
- [x] 5.3 Document volume reuse, container recreation, optional semantic
  configuration, and explicit volume deletion; verify the documentation
  distinguishes safe container recreation from destructive volume removal.
- [x] 5.4 Remove contradictory wording that presents Stanza as an optional
  Docker-only runtime when the standard Docker and source flows are intended
  to be equivalent; verify all copyable examples describe the same capability.
- [x] 5.5 Make the Docker quick-start self-contained by adding the one-time
  Stanza preparation command before server startup and passing
  --linguistic-model-dir /data/stanza; verify the code block is independently
  copyable, uses only the named volume, and includes the /analyze check.

## 6. Validate image, resources, and parity

- [x] 6.1 Inspect the built wheel and verify it contains the templates, images,
  voice catalog, espeak-ng data, Tashkeel/Hebrew assets, and required
  license/source files.
- [x] 6.2 Build the standard NLP-enabled Docker image from a clean context and
  verify entrypoint help, port contract, CPU-only dependency inventory, and
  absence of baked Stanza model weights.
- [x] 6.3 Run host and container resource-preparation tests for the five pilot
  languages and selected-language subsets; verify equivalent processor mappings
  and persistent volume reuse.
- [x] 6.4 Run HTTP smoke tests covering UI, catalog, /analyze, /download,
  /synthesize, fallback behavior, and error responses; verify Stanza-backed
  analysis for languages with complete resources and Japanese/Chinese
  synthesis when voices are present.
- [x] 6.5 Verify named-volume persistence and concurrent download coordination
  by recreating the server container and issuing concurrent requests against
  the same voice; verify only complete artifacts are exposed and breaker
  metadata remains shared.
- [x] 6.6 Run the relevant Python test suite with
  PYTHONPATH=src .venv/bin/python -m pytest and verify the final worktree diff
  contains only the approved Docker packaging, shared linguistic runtime,
  tests, and documentation scope.
- [x] 6.7 Execute the canonical Docker quick-start with a temporary
  Docker-managed named volume; verify prepared Stanza resources produce
  source=stanza from /analyze and synthesis still returns playable WAV audio,
  then remove only the temporary test resources.
