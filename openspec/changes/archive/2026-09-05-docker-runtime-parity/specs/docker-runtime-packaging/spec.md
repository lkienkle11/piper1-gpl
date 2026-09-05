## Purpose

This capability defines one optimized linguistic runtime contract for Piper on
the host and in Docker, including Stanza dependencies, processor-specific
resource preparation, HTTP behavior, and Docker-managed persistence.

## ADDED Requirements

### Requirement: Standard runtime provides the supported linguistic capability

The standard Docker runtime SHALL provide the same supported Stanza linguistic
analysis capability as the supported source installation. The Docker runtime
SHALL use a CPU execution dependency set without requiring CUDA or NVIDIA
runtime packages. Basic voice synthesis SHALL remain usable when linguistic
resources are absent.

#### Scenario: Standard Docker image contains the linguistic runtime

- **WHEN** the standard Docker image is built and its runtime dependencies are
  inspected
- **THEN** Stanza and its CPU-compatible execution dependency SHALL be
  available without requiring a separate NLP image or host installation

#### Scenario: Standard image does not pull accelerator runtime packages

- **WHEN** the built image dependency set is inspected
- **THEN** it SHALL not contain CUDA/NVIDIA runtime packages used only for
  accelerator execution

#### Scenario: Synthesis remains available without linguistic resources

- **WHEN** the standard image starts with a voice in /data but no Stanza model
  resources
- **THEN** the HTTP server and basic speech synthesis SHALL remain available
  and linguistic analysis SHALL report the existing local fallback status

### Requirement: Host and Docker use one processor-aware Stanza flow

The host and Docker runtimes SHALL use the same supported-language processor
definition for Stanza resource preparation and pipeline loading. The flow SHALL
allow a caller to select languages and SHALL download only the processors
required for those languages rather than every default package component.

#### Scenario: Resource preparation uses the shared processor definition

- **WHEN** a caller prepares resources for a supported language
- **THEN** the preparation command SHALL request the processor set defined for
  that language and SHALL place the resulting files under the requested model
  directory

#### Scenario: Unused languages are not downloaded

- **WHEN** a caller selects a subset of supported languages
- **THEN** the preparation flow SHALL not create model directories for
  unselected languages

#### Scenario: Host and Docker select equivalent processors

- **WHEN** the same language selection is prepared on the host and in Docker
- **THEN** both runtimes SHALL use the same processor mapping, with only the
  model directory path differing

### Requirement: Linguistic analysis handles language-specific resources

The linguistic analyzer SHALL load only processors available and required for
the requested supported language. It SHALL NOT force mwt or another unsupported
processor for a language whose installed Stanza resources do not provide it.

#### Scenario: Vietnamese analysis does not require an unavailable MWT model

- **WHEN** Vietnamese resources contain the supported Vietnamese processors but
  no mwt model and a client calls /analyze
- **THEN** the analyzer SHALL run with the compatible processor set and SHALL
  return a Stanza-backed result instead of failing during pipeline creation

#### Scenario: Complete resources produce Stanza analysis

- **WHEN** a supported language has all processors defined for that language
  under the configured model directory
- **THEN** /analyze SHALL return source equal to stanza and include the stable
  serialized linguistic fields available from that pipeline

#### Scenario: Incomplete resources preserve fallback

- **WHEN** a requested language is supported but its required resources are
  missing or cannot be loaded
- **THEN** /analyze SHALL return the existing local fallback status without
  downloading resources or preventing speech synthesis

### Requirement: Linguistic resources use the Docker-managed volume

The Docker runtime SHALL keep Stanza model weights outside the image in
/data/stanza on the same Docker-managed named volume used for voices and runtime
state. Docker operation SHALL NOT require a host bind mount.

#### Scenario: Docker preparation persists Stanza resources

- **WHEN** the documented preparation command runs with piper-data mounted at
  /data
- **THEN** the selected resources SHALL be stored under /data/stanza and SHALL
  remain available after the preparation container exits

#### Scenario: Container recreation reuses Stanza resources

- **WHEN** a server container is removed and recreated with the same named
  volume
- **THEN** the server SHALL reuse /data/stanza without downloading the models
  again

#### Scenario: Model weights are not baked into the image

- **WHEN** the Docker image filesystem is inspected before mounting a data
  volume
- **THEN** it SHALL contain the Stanza runtime but SHALL not contain language
  model weights

### Requirement: HTTP and storage contracts remain stable

The unified runtime SHALL keep the HTTP server on container port 5000 by
default, SHALL preserve the existing port override, and SHALL keep voices,
download coordination state, and linguistic resources under /data.

#### Scenario: Default Docker mapping remains port 5000

- **WHEN** a user starts the standard image with 5000:5000 and a named volume
- **THEN** the web UI, /analyze, and /synthesize SHALL be reachable through host
  port 5000

#### Scenario: Custom port override remains supported

- **WHEN** a user passes the existing --port option through the Docker
  entrypoint
- **THEN** the server SHALL listen on the requested container port and accept a
  matching host mapping

#### Scenario: Voice synthesis is unaffected by Stanza preparation

- **WHEN** a voice is downloaded into /data and the server is started with or
  without prepared Stanza resources
- **THEN** valid synthesis requests SHALL continue to return playable WAV audio

### Requirement: Documentation exposes one complete host and Docker flow

The deployment documentation SHALL show the same Stanza installation,
processor-aware preparation, and analysis behavior for host and Docker. The
copyable Docker quick-start SHALL be a complete standard NLP-enabled flow: it
SHALL include Stanza preparation in the named volume before server startup and
SHALL pass `/data/stanza` to the server's linguistic model directory option.
Docker examples SHALL use the named volume at /data, SHALL not require a host
bind mount, and SHALL explain that resource preparation is explicit.

#### Scenario: Docker documentation shows the unified NLP flow

- **WHEN** a user follows the Docker section
- **THEN** the quick-start SHALL show the standard image build, named-volume
  creation, voice download, resource preparation under /data/stanza, server
  startup on port 5000 with `/data/stanza` configured, and an /analyze
  verification request

#### Scenario: Docker quick-start reaches Stanza-backed analysis

- **WHEN** a user follows the copyable Docker quick-start with its named volume
  and completes the documented Stanza preparation step
- **THEN** the subsequent /analyze verification request SHALL report a
  Stanza-backed result, while synthesis SHALL remain available from the same
  container

#### Scenario: Source documentation uses the same preparation interface

- **WHEN** a user follows any supported source setup
- **THEN** it SHALL use the same processor-aware resource preparation interface
  with a host-local model directory

#### Scenario: Documentation distinguishes fallback from successful Stanza

- **WHEN** resources are absent or incomplete
- **THEN** the documentation SHALL state that the server remains usable through
  local fallback and SHALL distinguish that from a Stanza-backed result
