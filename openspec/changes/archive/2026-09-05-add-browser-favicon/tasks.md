## 1. Favicon Asset

- [x] 1.1 Add a valid, non-empty `src/piper/img/favicon.ico` suitable for browser-tab rendering and verify the file is recognized as an ICO image
- [x] 1.2 Verify the existing package-data collection includes `piper/img/favicon.ico` in a built distribution without adding a new packaging mechanism

## 2. HTTP and Template Integration

- [x] 2.1 Add the canonical `GET /favicon.ico` handler using the existing Flask static asset directory and verify it returns HTTP 200 with an icon-compatible content type and non-empty body
- [x] 2.2 Add a server-rendered `rel="icon"` declaration to `src/piper/templates/index.html` that points to `/favicon.ico`, and verify the page response contains the declaration

## 3. Regression Verification

- [x] 3.1 Add or extend HTTP/template tests for the favicon response, HTML declaration, and unchanged existing web/API route registration; verify the focused tests pass
- [x] 3.2 Run the relevant test suite and package/static checks, including `PYTHONPATH=src .venv/bin/python -m pytest`, and verify no synthesis or voice HTTP contract regressions are introduced. **WAIVED:** user requested bypass; full-suite failures remain outside this favicon change and are not treated as passed by this waiver.
- [x] 3.3 Start the HTTP server in a clean packaged/runtime environment and verify a browser or direct HTTP check loads `/favicon.ico` successfully while the Voice Studio page remains usable
