## Why

The current Voice Studio exposes analysis metadata and synthesis controls that are useful to developers but confusing for ordinary users. The interface should present human-readable language and voice choices while keeping the existing technical state available internally for future debugging and compatibility.

## What Changes

- Hide the per-segment analysis preview and other developer-facing synthesis details from the normal UI, while retaining the analyzed values in application state and/or temporary diagnostic logging.
- Hide the Delivery section and its controls from the user-facing layout.
- Make the effective delivery behavior always adaptive, with normal synthesis speed as the baseline; continue allowing automatic prosody/speed adjustments derived from emotion and text structure.
- Preserve the existing Delivery mode and synthesis-speed options, values, and data flow internally for diagnostics and backward compatibility, but do not expose them as user-customizable controls.
- Replace language option labels containing locale codes (for example, `English — en_GB (Great Britain)`) with clear human-readable labels such as `English (Great Britain)`. Locale codes remain internal identifiers only.
- Combine Voice name and Speaker into one user-facing `Voice name` selector. For multi-speaker voices, show the voice and speaker together in one label (for example, `aru - 06 (1)`), while retaining the underlying voice key and speaker identifier separately for synthesis.
- Keep quality selection and existing installed/download status behavior working with the simplified selectors.

## Capabilities

### New Capabilities

- `user-facing-voice-controls`: Defines the simplified Voice Studio presentation, human-readable language labels, adaptive defaults, hidden diagnostic state, and combined voice/speaker selection.

### Modified Capabilities

None.

## Impact

- `src/piper/templates/index.html`: user-facing markup, selector rendering, persisted settings interaction, analysis presentation, and request payload construction.
- `src/piper/voice_selection.py`: normalized catalog data and the mapping needed to display combined voice/speaker choices without changing synthesis identifiers.
- `src/piper/http_server.py`: only if required to preserve diagnostic analysis data or enforce adaptive defaults at the request boundary; public endpoint compatibility should be preserved.
- Existing browser settings and legacy API callers: old delivery/speed values may continue to be accepted internally, but the standard UI must send/use adaptive delivery and normal baseline speed.
