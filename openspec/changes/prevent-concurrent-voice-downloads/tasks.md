## 1. Shared download coordination

- [x] 1.1 Add a cross-platform filesystem-backed lock keyed by normalized voice ID and download directory, and verify same-voice callers serialize while different voices can acquire independent locks.
- [x] 1.2 Re-check the complete model/configuration artifact pair after acquiring the lock, and verify a second ordinary request reuses completed files without an upstream fetch while explicit force-redownload behavior remains intact.

## 2. Safe artifact publication

- [x] 2.1 Download model and configuration responses to unique temporary files in the target directory, atomically publish successful files, and remove temporary files on failure; verify interrupted transfers never leave a usable-looking partial artifact.
- [x] 2.2 Require both model and configuration artifacts before catalog installation status or synthesis model loading treats a voice as available, and verify a missing companion file cannot be loaded.
- [x] 2.3 Preserve the existing `/download` request and success/error response contract, and verify a waiting request receives success after the owner completes while a failed owner releases coordination for retry.

## 3. Regression coverage

- [x] 3.1 Add downloader-level concurrent same-voice coverage with controlled upstream responses, verifying one model fetch, one configuration fetch, complete final files, and successful reuse by the waiting caller.
- [x] 3.2 Add downloader-level coverage for different voices, existing complete artifacts, force-redownload, partial-download cleanup, and retry after upstream failure.
- [x] 3.3 Add HTTP-level concurrent `/download` coverage using a shared temporary directory, verifying both callers succeed, the upstream fetch count is one, and the resulting voice is installed and synthesizable.
- [x] 3.4 Run the focused download/API tests, the full test suite, formatting/import checks, and strict OpenSpec validation; verify no unrelated files are changed.
