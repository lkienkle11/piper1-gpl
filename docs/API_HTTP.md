# HTTP API

## Install from PyPI

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
python3 -m piper.download_voices en_GB-cori-high
```

Run the web server:

```sh
python3 -m piper.http_server -m en_GB-cori-high
```

The server listens on port 5000 by default. Use `--host` and `--port` to
override it, and `--data-dir <DIR>` to add directories containing voice files.

## Run the HTTP server from source on Linux and macOS

The following setups assume that Python 3.12 is installed and that the current
directory is the root of a Piper source checkout. Choose one setup; do not run
all three. Each setup downloads `en_GB-cori-high` and serves the web
interface at [http://127.0.0.1:7860](http://127.0.0.1:7860). The examples use
the high-quality British English `en_GB-cori-high` voice.

Building from source also requires Git and a C/C++ build toolchain. On macOS,
install the Xcode Command Line Tools. On Linux, install your distribution's C/C++
build tools and Python 3.12 virtual environment support.

The temporary setups use `/private/tmp` on macOS and `/tmp` on Linux. Files in
either location may be removed by the operating system, so a virtual environment
or voice stored there may need to be recreated.

### 1. Temporary environment and temporary voices

This setup keeps both the Python environment and voice files outside the
checkout. It installs a non-editable snapshot of the source, so run the install
command again after changing the source code.

```sh
PIPER_TEMP_ROOT=/tmp
if [ "$(uname -s)" = "Darwin" ]; then
  PIPER_TEMP_ROOT=/private/tmp
fi

python3.12 -m venv "${PIPER_TEMP_ROOT}/piper1-gpl-env"

"${PIPER_TEMP_ROOT}/piper1-gpl-env/bin/python" -m pip install --upgrade pip
"${PIPER_TEMP_ROOT}/piper1-gpl-env/bin/python" -m pip install '.[http]'

mkdir -p "${PIPER_TEMP_ROOT}/piper1-gpl-voices"
"${PIPER_TEMP_ROOT}/piper1-gpl-env/bin/python" -m piper.download_voices \
  --download-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  en_GB-cori-high

"${PIPER_TEMP_ROOT}/piper1-gpl-env/bin/python" -m piper.http_server \
  --host 127.0.0.1 \
  --port 7860 \
  --data-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  --download-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  -m en_GB-cori-high
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860).

### 2. Project environment and project-local voices

This setup keeps the editable development environment and voices with the
checkout. The ignored `local/voices` directory persists until it is removed
manually.

```sh
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e '.[http,dev]'
./script/dev_build

mkdir -p local/voices
python -m piper.download_voices \
  --download-dir local/voices \
  en_GB-cori-high

python -m piper.http_server \
  --host 127.0.0.1 \
  --port 7860 \
  --data-dir local/voices \
  --download-dir local/voices \
  -m en_GB-cori-high
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860).

### 3. Project environment and temporary voices (recommended)

This setup keeps the editable development environment in the checkout while
placing the larger voice files in the operating system's temporary directory.

```sh
PIPER_TEMP_ROOT=/tmp
if [ "$(uname -s)" = "Darwin" ]; then
  PIPER_TEMP_ROOT=/private/tmp
fi

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e '.[http,dev]'
./script/dev_build

mkdir -p "${PIPER_TEMP_ROOT}/piper1-gpl-voices"
python -m piper.download_voices \
  --download-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  en_GB-cori-high

python -m piper.http_server \
  --host 127.0.0.1 \
  --port 7860 \
  --data-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  --download-dir "${PIPER_TEMP_ROOT}/piper1-gpl-voices" \
  -m en_GB-cori-high
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860).

### Optional clean reset

Stop the HTTP server before resetting its environment. Use only the command for
the environment selected above:

```sh
# Setup 1
PIPER_TEMP_ROOT=/tmp
if [ "$(uname -s)" = "Darwin" ]; then
  PIPER_TEMP_ROOT=/private/tmp
fi
rm -rf "${PIPER_TEMP_ROOT}/piper1-gpl-env"

# Setups 2 and 3
deactivate 2>/dev/null || true
rm -rf .venv
```

If a Python 3.12 build fails because CMake references a stale temporary Ninja
path, remove the generated build cache before installing again:

```sh
rm -rf _skbuild
```

These reset commands preserve both `${PIPER_TEMP_ROOT}/piper1-gpl-voices` and
`local/voices`.

## Web interface

Open [http://localhost:5000](http://localhost:5000) for the PyPI example, or
[http://127.0.0.1:7860](http://127.0.0.1:7860) for the Linux and macOS source
setups. The interface has two voice-selection modes:

* **Auto Detect** detects the dominant language and selects a matching voice.
  British English is preferred for English, with `en_GB-cori-high` as the
  default catalog candidate. English and Vietnamese also have local
  context/emotion rules that adjust synthesis prosody.
* **Manual Voice** selects language, voice name, quality, speaker, and an
  optional emotion override. `Auto detect` keeps per-segment emotion analysis;
  `Neutral`, `Happy`, `Sad`, `Angry`, and `Excited` force the matching prosody.
  Voices from the online catalog must be downloaded explicitly before
  synthesis. Adaptive delivery is enabled by default in both modes.

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

Auto Detect uses one dominant language for the complete text, then analyzes
paragraphs and sentences independently for delivery. It does not split
mixed-language text into multiple voices. Emotion profiles change synthesis
settings; they do not turn a voice into an emotion-trained model.

Voice selection, speaker, manual emotion, delivery mode, synthesis speed,
volume, mute, playback speed, and the narration draft are stored in browser Local Storage.
Use the Delivery panel to reset settings, clear the script, or reset all Voice
Studio data. Audio data, waveform state, and playback position are not stored.

Stage directions must be in their own paragraph and apply to following text:

```text
(voice-speed: fast)

This paragraph is faster.

(emotion: sad)

This paragraph uses sad prosody.

(emotion: auto)

(pause: 0.5)

(narration-mode: fragment)

[[wˈɒʃɪŋ ɐ kʌpɪnðə sˈɪŋk]]
```

Supported directions are `voice-speed` (`slow`, `normal`, `fast`, or
`0.5`–`2.0`), `emotion` (`auto`, `neutral`, `happy`, `sad`, `angry`, or
`excited`), `pause` (`0`–`10` seconds), and `narration-mode` (`normal` or
`fragment`). Emotion remains active for following paragraphs until another
emotion direction changes it. Invalid scripts return HTTP 400 with
`error: "invalid_script"` and the source line number.

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
      "key": "en_GB-cori-high",
      "language": {
        "code": "en_GB",
        "family": "en",
        "region": "GB",
        "name_native": "English",
        "name_english": "English",
        "country_english": "Great Britain"
      },
      "name": "cori",
      "quality": "high",
      "num_speakers": 1,
      "speakers": {},
      "model_size_bytes": 114219352,
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
  "fallback_reason": null,
  "delivery": "adaptive",
  "voice_speed": 1.0,
  "segments": [
    {
      "kind": "text",
      "text": "Xin chào, hôm nay thật tuyệt!",
      "context": "conversation",
      "emotion": "happy",
      "pause_after": 0.0,
      "prosody": {"length_scale": 0.95, "noise_scale": 0.72, "noise_w_scale": 0.85}
    }
  ]
}
```

`/analyze` also accepts `mode`, `voice` (required for manual mode), `delivery`,
`voice_speed`, and `emotion`. Emotion defaults to `auto`; supported overrides
are `neutral`, `happy`, `sad`, `angry`, and `excited`.

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
  "voice": "en_GB-cori-high",
  "emotion": "sad",
  "speaker": "speaker-name"
}
```

Supported synthesis fields are:

* `text` (required)
* `mode`: `auto` or `manual`; omit for legacy behavior
* `voice`: required by manual mode, optional for legacy behavior
* `speaker` or `speaker_id`
* `delivery`: `adaptive` or `fixed` (defaults to adaptive for auto/manual)
* `voice_speed`: synthesis speed from `0.5` to `2.0`
* `emotion`: `auto`, `neutral`, `happy`, `sad`, `angry`, or `excited`
* `length_scale`, `noise_scale`, and `noise_w_scale`

Explicit synthesis scale values override segment prosody. A forced emotion is
also applied in Fixed Delivery, while `auto` retains its neutral fixed
prosody. Requests without a `mode` retain fixed legacy delivery. A new-mode request
for a voice that is not downloaded returns HTTP 409 with
`error: "voice_not_installed"`. Successful synthesis returns `audio/wav`.
