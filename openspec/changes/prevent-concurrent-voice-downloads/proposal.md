## Why

The web interface exposes voice downloads from a shared server-side directory, but concurrent requests currently perform independent existence checks and writes. When two users download the same missing voice at the same time, the server can fetch the same model twice and can expose partially written files after an interrupted download.

## What Changes

- Coordinate downloads per voice across concurrent requests that share a download directory.
- Make a waiting request reuse the completed files instead of starting a second upstream download.
- Publish model and configuration files only after each file has been downloaded successfully.
- Allow a later request to retry cleanly after an earlier download fails.
- Preserve the existing `POST /download` request and successful response contract.
- Add backend and downloader regression coverage for concurrent requests, failed downloads, and complete-file reuse.

## Capabilities

### New Capabilities

- `concurrent-voice-downloads`: Coordinate shared voice downloads and expose only complete model artifacts.

### Modified Capabilities

<!-- No existing main capability spec currently defines the voice download contract. -->

## Impact

- `src/piper/download_voices.py`: shared download coordination, temporary files, and completion handling.
- `src/piper/http_server.py`: concurrent `/download` requests and shared download-directory behavior.
- `src/piper/templates/index.html`: preserve the current per-user progress state while allowing the server to deduplicate work.
- `tests/`: concurrency, retry, atomic publication, and API compatibility tests.
- Deployment behavior: the coordination mechanism must work across concurrent server threads/processes that use the same download directory, without requiring a new external service.
