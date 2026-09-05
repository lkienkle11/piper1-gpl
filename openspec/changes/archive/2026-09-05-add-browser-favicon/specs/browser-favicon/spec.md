## Purpose

Provide a packaged browser-tab icon for the Piper Voice Studio page so supported browsers can identify the application without a missing favicon request.

## ADDED Requirements

### Requirement: Voice Studio declares a favicon

The Voice Studio HTML document SHALL declare `favicon.ico` as its browser icon using a link with `rel="icon"` and the canonical `/favicon.ico` URL.

#### Scenario: Main page includes the favicon declaration

- **WHEN** a client requests the Voice Studio page at `/`
- **THEN** the HTML response SHALL contain a `rel="icon"` declaration pointing to `/favicon.ico`

### Requirement: Server exposes the packaged favicon

The HTTP server SHALL serve a non-empty packaged `favicon.ico` asset at `/favicon.ico` with an icon-compatible MIME type and a successful response status.

#### Scenario: Browser requests the favicon

- **WHEN** a client sends `GET /favicon.ico`
- **THEN** the server SHALL return HTTP `200`, an icon-compatible `Content-Type`, and a non-empty response body

### Requirement: Existing web and API behavior remains compatible

Adding the favicon SHALL NOT change the Voice Studio page behavior, synthesis endpoints, voice endpoints, or existing HTTP request and response contracts.

#### Scenario: Existing synthesis endpoint remains available

- **WHEN** an existing client sends a valid request to `/synthesize`
- **THEN** the server SHALL continue to process it according to the existing synthesis contract
