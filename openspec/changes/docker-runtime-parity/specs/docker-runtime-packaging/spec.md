## Purpose

This capability defines a reproducible Docker runtime for the current Piper HTTP
application, including its multilingual web dependencies, packaged assets, port,
and persistent voice-download storage contract.

## ADDED Requirements

### Requirement: Container provides the current multilingual HTTP runtime

The default Docker image SHALL install the local Piper package with the runtime
dependencies required by the current multilingual web application, including
HTTP support and the supported Japanese and Chinese extras. The default image
SHALL not require development, training, linguistic-analysis, or external
services to start the HTTP server. An explicit Docker NLP profile SHALL be
available for users who want the optional Stanza analysis package.

#### Scenario: Japanese and Chinese web synthesis are available

- **WHEN** the image is run with a corresponding voice model available in its
  data volume and a client submits a valid synthesis request for Japanese or
  Chinese text
- **THEN** the server SHALL reach the voice phonemizer and return playable WAV
  audio instead of failing because the web image omitted the language extra

#### Scenario: Default image runs without NLP resources

- **WHEN** the default image is started without an NLP profile or pre-installed
  Stanza resources
- **THEN** the server SHALL remain able to serve the HTTP application and use its
  existing local analysis fallback without requiring host-installed packages or
  downloading resources as part of a normal synthesis request

#### Scenario: NLP profile is selected during Docker build

- **WHEN** a user explicitly builds the Docker NLP profile
- **THEN** the resulting image SHALL contain the declared linguistic-analysis
  package and SHALL remain self-contained, with no dependency installation on
  the host and no required external NLP service

### Requirement: Image contains the HTTP package assets

The Docker-built wheel SHALL contain the web templates and images, the current
voice catalog metadata, language-specific packaged data, and required license or
source files declared by the package metadata.

#### Scenario: Web UI and catalog are served from the image

- **WHEN** a container starts the HTTP server from the Docker-built wheel
- **THEN** the root web page, static image routes, and normalized voice catalog
  endpoint SHALL be available without source files mounted from the host

### Requirement: Runtime data uses one Docker-managed named volume

The Docker deployment SHALL use `/data` as the persistent runtime directory for
downloaded voice artifacts, per-voice download locks, circuit-breaker state, and
any optional linguistic resources. The documented deployment SHALL use a
Docker-managed named volume and SHALL NOT require a host bind mount.

#### Scenario: Voice download persists across container recreation

- **WHEN** a voice is downloaded using a named volume mounted at `/data`, the
  container is removed, and a new container mounts the same named volume
- **THEN** the complete model and configuration files SHALL remain available to
  the new container

#### Scenario: Concurrent download coordination shares the volume

- **WHEN** concurrent server requests download the same voice using the same
  `/data` directory
- **THEN** the lock and circuit-breaker metadata SHALL be stored beside the voice
  artifacts on that shared filesystem and the requests SHALL observe the current
  download coordination behavior

#### Scenario: Docker commands do not depend on host paths

- **WHEN** a user follows the documented build and run flow on a Docker host
- **THEN** the commands SHALL create or reuse a named volume and SHALL not require
  a repository path or other host directory to be mounted at `/data`

### Requirement: Container port and command contract are stable

The HTTP server SHALL listen on port 5000 inside the container by default. The
Docker entrypoint SHALL direct both voice discovery and voice downloads to
`/data`, and SHALL continue to pass supported server and synthesis arguments
through to Piper.

#### Scenario: Default server mapping uses port 5000

- **WHEN** a user starts the container with the default server command and maps
  host port 5000 to container port 5000
- **THEN** the web UI and HTTP API SHALL be reachable on the host through port
  5000

#### Scenario: Custom port override remains supported

- **WHEN** a user passes the existing `--port` option through the Docker
  entrypoint
- **THEN** the server SHALL listen on the requested container port and the user
  SHALL be able to choose a matching host mapping

#### Scenario: Download and server use the same persistent directory

- **WHEN** a user downloads a voice with the Docker download command and then
  starts the Docker server against the same named volume
- **THEN** the server SHALL discover the downloaded voice from `/data` without
  relying on files in the image work directory

### Requirement: Docker deployment documents optional linguistic and semantic services

The Docker deployment documentation SHALL explain how to place optional Stanza
resources under `/data/stanza` using the named volume, and SHALL state that a
semantic `llama.cpp` service and its model are separate from the Piper image.

#### Scenario: Optional Stanza resources are reused

- **WHEN** the NLP profile is used, Stanza resources are prepared in
  `/data/stanza`, and the server is started with the existing linguistic model
  directory option
- **THEN** the container SHALL use those resources without requiring a host bind
  mount

#### Scenario: Semantic provider is enabled explicitly

- **WHEN** a user enables the semantic provider for a container deployment
- **THEN** the documentation SHALL require an endpoint reachable from the
  container and preserve the existing explicit privacy and external-endpoint
  policy
