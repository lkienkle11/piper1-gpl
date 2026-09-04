## Context

See `proposal.md` for the motivation. The current Dockerfile builds a wheel from
an allowlisted context, installs only Flask in the final image, and exposes port
5000. The package metadata now includes multilingual HTTP extras, Stanza support,
voice catalog and web assets, Hebrew data, and `filelock`. The server and download
paths also now persist per-voice lock and circuit-breaker files beside voice
artifacts.

## Goals / Non-Goals

**Goals:**

- Make the default image's installed runtime match the current multilingual HTTP
  setup without pulling the optional NLP dependency tree.
- Provide an explicit Docker-only NLP profile for Stanza users.
- Produce a wheel containing every asset required by the HTTP application and
  package metadata.
- Make `/data` the only runtime data location and provide a named-volume-first
  deployment flow.
- Keep port 5000 as the container default while preserving existing CLI argument
  passthrough.
- Make optional Stanza resources usable from the named volume without bundling
  large model resources into the image.

**Non-Goals:**

- Do not change the HTTP request or response schema, voice selection behavior,
  synthesis algorithms, or download circuit-breaker logic.
- Do not bake voice models, Stanza model weights, GGUF files, or llama.cpp into
  the Piper image.
- Do not introduce host bind mounts, a database, Redis, or another external
  coordination service for voice downloads.
- Do not remove the application's existing arbitrary `--port` override or make
  another port the container default.

## Decisions

### Install the local wheel with default web extras and an optional NLP profile

The builder will retain the existing source-to-wheel flow. The final stage will
install the local wheel with the default `http`, `ja`, and `zh` extras. A Docker
build argument will allow an explicit NLP profile to add `nlp` to that local
wheel installation, for example `http,ja,zh,nlp`. This keeps dependency versions
owned by `setup.py` and ensures that the final image does not silently resolve a
different package from PyPI. Development and training extras stay in the
builder only or are omitted from every runtime image.

Installing only Flask is rejected because it leaves the current Auto Detect
multilingual path without its phonemizers and language detector. Installing
`nlp` in the default image is also rejected because Stanza currently resolves a
large CUDA-enabled PyTorch dependency tree on the target ARM64 build platform,
despite NLP resources being optional for the HTTP runtime. Copying a developer
virtual environment into the final stage is rejected because it would carry
build tools and unrelated development packages.

### Make the Docker context follow package metadata

The allowlist in `.dockerignore` will be updated to retain the source directories
and root license files that `setup.py` enumerates. The Dockerfile will copy those
files into the builder, while generated `espeak-ng-data` remains produced by the
existing CMake build. The wheel will be inspected after packaging so missing
templates, catalog data, nested language packages, or license files fail
validation before runtime testing.

### Use an explicit named-volume contract at `/data`

The image will declare `/data` as its data volume, and the entrypoint will pass an
explicit `/data` download directory for both the download and server commands.
This avoids the current argparse interaction where the process working directory
can remain the first data directory and become the implicit download destination.

The documented lifecycle will create a named volume such as `piper-data`, mount
it at `/data`, download voices into it, and reuse it when starting or recreating
the server container. A host bind mount is not included in examples or required
for operation. Stanza resources, when prepared, will use `/data/stanza` on the
same volume so they follow the same persistence rule.

### Keep the internal HTTP port at 5000

The entrypoint will continue to bind the server to `0.0.0.0` and pass user
arguments through. Documentation will use `5000:5000` as the mapping; custom
host mappings remain possible when paired with the existing `--port` option.

### Keep optional services outside the image

Stanza Python support will be installed only in the explicit NLP image profile,
and its resources will be prepared into `/data/stanza` rather than downloaded
during ordinary synthesis. The default image does not require Stanza and uses
the existing fallback. The semantic provider remains disabled by default and
connects only to a separately managed `llama.cpp` endpoint. Docker documentation
will explain that an endpoint running outside the Piper container must be
reachable from the container and must use the existing explicit
privacy/external-endpoint flags.

Embedding these services is rejected because their model sizes, accelerator
requirements, lifecycle, and privacy boundaries differ from the Piper HTTP
runtime.

## Risks / Trade-offs

- **Larger optional NLP image:** Stanza may resolve a CUDA-enabled PyTorch tree.
  Keep it out of the default image, make the profile explicit, and do not bake
  model resources into either image.
- **Native dependency compatibility:** Optional phonemizer wheels may vary by
  Python/platform. Build and synthesis smoke tests must run against the target
  Python 3.12 image.
- **Missing Stanza resources:** Installing the package does not provide its
  models. Document the explicit volume-backed preparation flow and preserve the
  existing fallback when resources are absent.
- **Container-to-semantic-service networking:** A loopback endpoint inside the
  Piper container is not the host or another container. Document reachable
  endpoint configuration and retain the privacy policy instead of weakening it.
- **Volume deletion is destructive:** Recreating a container is safe, but removing
  the named volume removes downloaded voices and metadata. Mark volume removal as
  an explicit destructive cleanup operation in the documentation.

## Migration Plan

1. Build the updated image and create a new named volume, or reuse an existing
   volume after verifying its contents.
2. Download or copy voices through the Docker command into `/data`; do not bake
   them into the image.
3. Optionally prepare Stanza resources under `/data/stanza` and start the server
   with the linguistic model directory option.
4. Start the server with `5000:5000`, then verify the UI and HTTP smoke endpoints.
5. Roll back by running the previous image with its own named volume; the image
   change does not modify the host filesystem or the existing application data.

## Open Questions

None.
