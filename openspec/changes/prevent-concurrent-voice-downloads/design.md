## Context

See proposal.md for the motivation. The current downloader checks whether each final path is non-empty and writes directly to that path. The HTTP route and CLI both use this downloader, while the web page keeps `downloading` state only in the current browser. The server's installed catalog status is derived from the shared model and configuration files on each catalog read.

## Goals / Non-Goals

**Goals:**

- Deduplicate same-voice downloads across concurrent threads and processes that share a download directory.
- Prevent partial model or configuration files from being published as usable artifacts.
- Preserve the current `/download` request shape, success response, and per-user browser workflow.
- Keep different voice downloads independent.
- Make failures release coordination and leave a clean retry path.

**Non-Goals:**

- Do not add a distributed service such as Redis or change deployment topology.
- Do not automatically download voices during analysis or synthesis.
- Do not redesign cross-browser progress reporting; server-side deduplication is the correctness mechanism.
- Do not alter voice catalog selection, model URLs, or the existing force-redownload intent.

## Decisions

### Use a filesystem-backed per-voice lock

The downloader SHALL acquire a lock derived from the normalized voice ID and download directory before checking or writing artifacts. The lock must work across server threads and separate processes using the same directory, so an in-memory `threading.Lock` alone is insufficient. A small cross-platform locking abstraction is preferred over an external service or a lock scoped only to Flask's process.

The lock is held across both model and configuration downloads. Once acquired, the downloader re-checks the final artifacts; a request that arrives after a successful download therefore becomes a no-op. Different voice IDs use different locks and can proceed concurrently.

Alternatives considered:

- In-memory per-voice locks: simple, but fail with multiple workers/processes.
- One global lock: prevents duplicate work, but unnecessarily serializes unrelated voice downloads.
- Redis or another distributed lock: supports multiple hosts, but adds infrastructure outside the current local shared-directory deployment model.

### Download to same-directory temporary files and publish atomically

Each missing artifact is downloaded to a unique temporary file in the target directory. After the transfer succeeds, the temporary file is atomically renamed to the final `.onnx` or `.onnx.json` path. Temporary files are removed on failure.

The completion check must require both artifacts. Model discovery used for synthesis must not load a model whose companion configuration is absent. This avoids exposing a partially published pair during the short interval between two individual atomic renames and protects manual or concurrent synthesis requests from incomplete files.

### Keep the existing API contract

`POST /download` continues to accept the current voice identifier and returns the identifier on success. A request that waited for another request and then reused complete files is still a successful download operation from the client's perspective. Existing error handling remains in place, with the lock released before the failure response.

### Test at the downloader and HTTP layers

Downloader tests will control the upstream response and coordinate concurrent callers to prove only one transfer occurs, complete files are reused, and failed transfers can be retried. HTTP tests will send concurrent `/download` requests against a shared temporary directory and verify both responses succeed, the files are complete, and the upstream fetch count is one. Existing sequential API and browser behavior remains covered by the current tests.

## Risks / Trade-offs

- [Risk] A process can terminate while holding a lock → use an OS-managed lock whose ownership is released automatically, and keep lock artifacts separate from model completion checks.
- [Risk] Atomic publication of two files is not a single filesystem transaction → stage both files first, publish only completed files, require the pair for installation/loading, and retry any missing companion file.
- [Risk] A slow download makes concurrent users wait → serialize only requests for the same voice and leave unrelated voice downloads parallel.
- [Risk] A shared directory mounted by multiple hosts may not provide reliable lock semantics → document the supported scope as concurrent workers sharing a filesystem with reliable locking; multi-host distributed storage remains out of scope.
