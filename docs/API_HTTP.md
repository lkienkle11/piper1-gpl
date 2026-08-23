# HTTP API

Install the HTTP server and local language detector dependencies:

```sh
python3 -m pip install 'piper-tts[http]'
```

Japanese voices use OpenJTalk and require the Japanese language extra:

```sh
python3 -m pip install 'piper-tts[http,ja]'
```

If it is missing, `/synthesize` returns JSON error
`phonemizer_dependency_missing` with HTTP 503 instead of an HTML error page.

Download a default voice, for example:

```sh
python3 -m piper.download_voices en_US-lessac-medium
```

Run the web server:

```sh
python3 -m piper.http_server -m en_US-lessac-medium
```

The server listens on port 5000 by default. Use `--host` and `--port` to
override it, and `--data-dir <DIR>` to add directories containing voice files.

## Web interface

Open [http://localhost:5000](http://localhost:5000). The interface has two
voice-selection modes:

* **Auto Detect** detects the dominant language and selects a matching voice.
  English and Vietnamese also have local context/emotion rules that adjust
  synthesis prosody. Other languages use punctuation rules and neutral emotion.
* **Manual Voice** selects language, voice name, quality, and speaker. Voices
  from the online catalog must be downloaded explicitly before synthesis.

The custom audio player supports seeking, volume, WAV download, and playback
speed from `0.10x` to `5.00x`. Its slider advances in `0.05x` steps, while the
exact-speed input accepts hundredths and remembers the last value in the
browser. Playback speed is client-side only and does not change synthesis
prosody or the downloaded WAV. After synthesis, the browser decodes the WAV and
renders a responsive waveform: played audio is green and remaining audio is
gray. Clicking, dragging, or using the arrow keys on the waveform seeks audio.

The person button provides a quick picker containing installed voices for the
current manual or automatically detected language. Choosing a voice updates
the existing language/name/quality/speaker selectors and switches to Manual
Voice mode. It never downloads a model automatically.

Auto Detect uses one dominant language for the complete text. It does not split
mixed-language text into multiple voices. Emotion profiles change synthesis
settings; they do not turn a voice into an emotion-trained model.

## Voice information and catalog

`GET /info` returns the default voice and the most recent synthesis. The `last`
object includes the actual voice, selection mode, detected language, context,
emotion, prosody, phonemes, alignments, and synthesis time when available.

`GET /voices` returns raw configuration data for downloaded voices.

`GET /all-voices` returns the raw remote Piper catalog.

`GET /voice-catalog` returns a normalized catalog for clients:

```json
{
  "voices": [
    {
      "key": "en_US-lessac-medium",
      "language": {
        "code": "en_US",
        "family": "en",
        "region": "US",
        "name_native": "English",
        "name_english": "English",
        "country_english": "United States"
      },
      "name": "lessac",
      "quality": "medium",
      "num_speakers": 1,
      "speakers": {},
      "model_size_bytes": 63201294,
      "installed": true
    }
  ],
  "catalog_available": true,
  "catalog_error": null
}
```

The remote catalog is cached for one hour. If it is unavailable, downloaded
voices are still returned with `catalog_available: false`.

## Analyze text

`POST /analyze` resolves Auto Detect without synthesizing audio:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào, hôm nay thật tuyệt!"}' \
  localhost:5000/analyze
```

The response contains:

```json
{
  "language": {
    "family": "vi",
    "code": "vi_VN",
    "name": "Vietnamese",
    "confidence": 0.96
  },
  "context": "conversation",
  "emotion": "happy",
  "voice": {"key": "vi_VN-vais1000-medium", "installed": false},
  "prosody": {
    "length_scale": 0.95,
    "noise_scale": 0.72,
    "noise_w_scale": 0.85
  },
  "installed": false,
  "needs_download": true,
  "fallback_reason": null
}
```

Possible fallback reasons are `text_too_short`, `low_confidence`, and
`no_voice_for_language`.

## Download a voice

`POST /download` downloads the model and configuration into `--download-dir`:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -d '{"voice":"vi_VN-vais1000-medium"}' \
  localhost:5000/download
```

Downloads are explicit and synchronous. Auto Detect never starts a download.

## Synthesize audio

Legacy requests remain supported and use the default `-m` voice:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"This is a test."}' \
  -o test.wav localhost:5000/synthesize
```

Auto Detect request:

```json
{"text":"This is a happy local test!", "mode":"auto"}
```

Manual Voice request:

```json
{
  "text": "This is a manual voice test.",
  "mode": "manual",
  "voice": "en_US-lessac-medium",
  "speaker": "speaker-name"
}
```

Supported synthesis fields are:

* `text` (required)
* `mode`: `auto` or `manual`; omit for legacy behavior
* `voice`: required by manual mode, optional for legacy behavior
* `speaker` or `speaker_id`
* `length_scale`, `noise_scale`, and `noise_w_scale`

Explicit synthesis scale values override Auto Detect prosody. A new-mode request
for a voice that is not downloaded returns HTTP 409 with
`error: "voice_not_installed"`. Successful synthesis returns `audio/wav`.
