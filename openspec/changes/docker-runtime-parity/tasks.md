## 1. Reconcile the image build and runtime dependencies

- [x] 1.1 Update `.dockerignore` and Dockerfile build inputs to retain every source, package-data, web asset, language asset, and license/source file required by `setup.py`; verify the clean Docker build context contains the required paths.
- [x] 1.2 Build the local Piper wheel in the builder stage and install the default final image with the declared `http`, `ja`, and `zh` extras while excluding development and training dependencies; verify the installed image can import the HTTP, Japanese, and Chinese runtime modules.
- [x] 1.3 Add an explicit Docker-only NLP build profile that adds the declared `nlp` extra without changing the host environment; verify the profile boundary is visible in the build instructions and the default image does not install Stanza or PyTorch.
- [x] 1.4 Keep build-only toolchains out of the final image and verify the final image contains the runtime wheel and dependencies without the builder virtual environment.

## 2. Enforce the persistent Docker data contract

- [x] 2.1 Declare `/data` as the image data volume and make the Docker runtime contract use a Docker-managed named volume; verify image metadata declares `/data` and the documented commands contain no host bind mount.
- [x] 2.2 Update the Docker entrypoint so `download` and `server` explicitly use `/data` for both voice discovery and downloads, while preserving supported argument passthrough; verify entrypoint help and command-line inspection show the expected directory arguments.
- [x] 2.3 Verify downloaded model/configuration files, per-voice lock files, and circuit-breaker state are created under `/data` and remain available after removing and recreating a container with the same named volume.

## 3. Preserve the current HTTP and optional-analysis behavior

- [x] 3.1 Keep port 5000 as the container-side default, pass through the existing `--port` option, and document host-to-container mapping; verify the default server responds through `5000:5000` and a custom mapping remains functional.
- [ ] 3.2 Document and verify the optional Stanza resource flow using the explicit Docker NLP profile, `/data/stanza` on the named volume, and the existing linguistic model directory option, while preserving default-image fallback behavior when the profile or resources are absent.
- [x] 3.3 Document semantic-provider Docker usage as an explicit connection to a separately managed `llama.cpp` endpoint, including container reachability and the existing privacy/external-endpoint policy; verify the Piper image does not contain GGUF or llama.cpp runtime files.

## 4. Update Docker deployment documentation

- [x] 4.1 Add a complete Docker build, named-volume creation, voice download, and server startup flow to `docs/API_HTTP.md` using port 5000 and `/data`; verify the commands are copyable and use only a Docker-managed named volume.
- [x] 4.2 Document volume reuse, container recreation, optional Stanza preparation, optional semantic configuration, and explicit volume deletion; verify the documentation distinguishes safe container recreation from destructive volume removal.
- [x] 4.3 Add HTTP smoke examples for the web UI, `/voice-catalog`, `/analyze`, `/download`, and `/synthesize`; verify each example targets the documented port and persistent data path.

## 5. Validate package and container parity

- [x] 5.1 Inspect the built wheel and verify it contains the templates, images, voice catalog, espeak-ng data, Tashkeel/Hebrew assets, and required license/source files.
- [x] 5.2 Build the Docker image from a clean context and verify the image starts with the Docker entrypoint and reports the expected help/port contract.
- [ ] 5.3 Run container HTTP smoke tests covering the root UI, catalog, multilingual analysis/synthesis, explicit voice download, and error responses; verify Japanese and Chinese synthesis work when their voices are present.
- [x] 5.4 Verify named-volume persistence and concurrent download coordination by recreating the server container and issuing concurrent requests against the same voice; verify only complete artifacts are exposed and breaker metadata remains shared.
- [x] 5.5 Run the relevant Python test suite with `PYTHONPATH=src .venv/bin/python -m pytest` and verify the final worktree diff contains only the approved Docker packaging and documentation scope.
