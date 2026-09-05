## Context

The HTTP application is a Flask server-rendering `src/piper/templates/index.html`. It already configures `src/piper/img` as its static folder, and `setup.py` collects files under both `templates` and `img` as package data. The current page has a normal HTML `<head>` but no favicon declaration, and the conventional `/favicon.ico` request can therefore return 404.

## Goals / Non-Goals

**Goals:**

- Add one valid `favicon.ico` asset to the existing packaged web assets.
- Expose that asset at the conventional `/favicon.ico` URL.
- Declare the URL in the server-rendered page.
- Verify the HTML declaration and HTTP response without changing synthesis behavior.

**Non-Goals:**

- Redesign the existing Piper logo or page branding.
- Add a frontend build pipeline, a new static-file dependency, or a separate web service.
- Change the existing `/img` static URL or any voice/audio API.

## Decisions

### Use the existing Flask static folder

Place `favicon.ico` in `src/piper/img/` and serve it through the Flask application's existing static-folder configuration. This reuses the current packaging path and avoids adding a second asset-serving mechanism.

### Add a canonical `/favicon.ico` route

Add a small route that returns the file from the configured Flask static folder, then use `/favicon.ico` in the HTML link. This is preferable to exposing only `/img/favicon.ico` because browsers and operational checks commonly request the conventional root path directly.

### Keep the icon declaration server-rendered

Add the `rel="icon"` link to the existing template and generate the canonical URL from the Flask route. No client-side JavaScript is needed for browser-tab metadata.

### Test at the HTTP/template boundary

Use the Flask test client to assert that `/` contains the icon declaration and `/favicon.ico` returns a successful non-empty icon response. Keep synthesis regression coverage unchanged because the favicon has no effect on synthesis inputs or outputs.

## Risks / Trade-offs

- [Risk] Browser favicon caches can hide a newly replaced icon during manual verification. -> Mitigation: verify the HTTP response directly and use a hard refresh or a fresh browser context when checking visually.
- [Risk] A malformed or non-icon asset may be served successfully but not render. -> Mitigation: validate the committed file as an ICO image and assert its non-empty packaged response in tests.
- [Risk] The asset could be omitted from a built distribution. -> Mitigation: retain the existing recursive package-data collection and verify the built package contains `piper/img/favicon.ico`.
