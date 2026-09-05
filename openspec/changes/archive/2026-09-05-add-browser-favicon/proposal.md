## Why

The Piper Voice Studio page currently has no declared browser-tab icon, so browsers may request `/favicon.ico` and receive a 404. Adding an explicit packaged favicon gives the web UI a consistent tab identity and removes the missing-asset behavior.

## What Changes

- Add a browser-compatible `favicon.ico` asset to the packaged HTTP web assets.
- Declare the favicon from the server-rendered Voice Studio document.
- Serve the icon through the existing Flask static asset path, with a conventional `/favicon.ico` compatibility route if needed.
- Add regression coverage for the HTML declaration and favicon response.

## Capabilities

### New Capabilities

- `browser-favicon`: Provide a packaged favicon for the Piper Voice Studio browser page and expose it through the HTTP server.

### Modified Capabilities

- None.

## Impact

- Affected frontend template: `src/piper/templates/index.html`.
- Affected HTTP server: `src/piper/http_server.py` if the conventional `/favicon.ico` route is included.
- Affected packaged assets: `src/piper/img/favicon.ico` and the existing package-data collection in `setup.py`.
- Affected HTTP/template regression tests; no synthesis API, voice model, or existing client request contract changes.
