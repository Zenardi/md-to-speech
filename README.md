# md-to-speech

`md-to-speech` is a local CLI app that reads a Markdown file, turns the content into narration-friendly text, and writes a `.wav` audio file to disk using Kokoro TTS.

## What it does

- Reads Markdown course content from disk
- Converts headings, paragraphs, lists, links, and quotes into speech text
- Replaces Markdown images with a short configurable pause instead of reading alt text
- Skips fenced code blocks by default, with an option to read them literally
- Splits long content into stable chunks
- Synthesizes audio locally with `hexgrad/Kokoro-82M`
- Optionally rewrites chunks with a local Ollama model before synthesis
- Saves the final merged `.wav` file to disk

## Requirements

- Python `3.11` or `3.12`
- A working local Kokoro setup via the `kokoro` Python package
- For local Linux installs, `espeak-ng` available on the machine

> Python `3.13` is not currently supported by the pinned `kokoro==0.9.4` dependency in `requirements.txt`.

## Local install on Ubuntu

Install the system packages first.

For Ubuntu 24.04, this is usually:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv espeak-ng
```

Then create a virtual environment and install the project:

```bash
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Quick smoke check:

```bash
md-to-speech --help
```

> If your Ubuntu image does not provide Python `3.12`, use Python `3.11` instead and create the virtual environment with `python3.11 -m venv .venv`.

## Local install on macOS

```bash
brew install espeak-ng
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Docker

The included `Dockerfile` uses a two-stage build on top of a [Chainguard `wolfi-base`](https://images.chainguard.dev/directory/image/wolfi-base/overview) image — minimal, rootless, and security-hardened.

The Docker setup is slightly different from a local Ubuntu install: the image relies on the `espeakng-loader` Python package for Linux shared-library support, so it does not install the `espeak-ng` system package separately.

**Build the image:**

```bash
docker build -t md-to-speech .
```

**First run — download the model (~327 MB):**

```bash
docker run --rm \
  -v "$HOME/.cache/huggingface":/cache \
  -v "$(pwd)":/data \
  md-to-speech /data/course.md --output /data/course.mp3
```

**All subsequent runs — fully offline:**

```bash
docker run --rm \
  -v "$HOME/.cache/huggingface":/cache \
  -v "$(pwd)":/data \
  md-to-speech /data/course.md --output /data/course.mp3 --offline
```

| Volume | Purpose |
|--------|---------|
| `/cache` | HuggingFace model cache — mount once, reuse forever |
| `/data` | Your input `.md` files and output `.wav`/`.mp3` files |

The container runs as a non-root user (`uid 65532`) by default.

## Usage

Generate a WAV file from Markdown:

```bash
md-to-speech course.md --output course.wav
```

Use a different Kokoro voice:

```bash
md-to-speech course.md --output course.wav --voice af_bella
```

Read fenced code blocks instead of skipping them:

```bash
md-to-speech course.md --output course.wav --code-block-behavior read
```

Use a longer pause when Markdown includes diagrams or figures:

```bash
md-to-speech course.md --output course.wav --image-pause-seconds 1.5
```

Rewrite each chunk with a local Ollama model before TTS:

```bash
md-to-speech course.md \
  --output course.wav \
  --rewrite-with-ollama \
  --ollama-model llama3.2
```

```bash
md-to-speech course.md --output course.mp3 --offline
```

## Running fully offline

When `md-to-speech` starts, the Kokoro library uses the `huggingface_hub` package to check whether a newer version of the model is available. The check is a lightweight HTTP request to Hugging Face — your audio is never sent anywhere — but it does mean a network call happens on every run, and you'll see this warning if you're not authenticated:

```
Warning: You are sending unauthenticated requests to the HF Hub.
Please set a HF_TOKEN to enable higher rate limits and faster downloads.
```

Once the model weights have been downloaded once (they are cached at `~/.cache/huggingface/hub/`), you never need to contact Hugging Face again. Pass `--offline` to block all network calls and run completely air-gapped:

```bash
md-to-speech course.md --output course.mp3 --offline
```

You can also set the environment variable permanently in your shell profile so you never need the flag:

```bash
export HF_HUB_OFFLINE=1
```

**First run** — leave `--offline` off so the model weights can download (~327 MB). Every run after that can use `--offline`.

## Narration rewriting with Ollama

By default the app converts your Markdown to speech almost literally — headings become *"Section. Introduction."*, list items become *"List item. Step one."*, and so on. This works well for most content, but the result can sound a bit mechanical.

When you pass `--rewrite-with-ollama`, each text chunk is first sent to a local LLM running in Ollama with a prompt that asks it to rewrite the content so it sounds natural when spoken aloud. The rewritten text is then passed to Kokoro for synthesis.

**Example difference:**

| Without Ollama | With Ollama |
|---|---|
| *"Section. Variables. List item. A variable stores a value. List item. Use let to declare one."* | *"Let's talk about variables. A variable is used to store a value, and you declare one using the let keyword."* |

**Enable it when:**
- Your Markdown is dense, bullet-heavy, or very technical
- You want the audio to feel like a human narration rather than a document read aloud
- Tone and flow matter — e.g. producing content for learners

**Skip it when:**
- You want fast, predictable output
- Your Markdown is already written in a conversational style
- You don't want the extra per-chunk latency

Ollama must be running locally before you start. The default model is `llama3.2`; pass `--ollama-model` to use any other model you have pulled.

## CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `INPUT` | *(required)* | Path to the input Markdown file |
| `-o`, `--output` | `<input>.wav` (same directory) | Output `.wav` file path, or an existing directory |
| `--voice` | `af_heart` | Kokoro voice name (see [Available voices](#available-voices)) |
| `--lang-code` | `a` | Language code matching the chosen voice (`a`=American English) |
| `--speed` | `1.0` | Speech speed multiplier — `0.5` is slower, `2.0` is faster |
| `--image-pause-seconds` | `1.0` | Silence inserted for each Markdown image reference. Use `0` to disable image pauses. |
| `--max-chars` | `1200` | Maximum characters per narration chunk |
| `--code-block-behavior` | `skip` | What to do with fenced code blocks: `skip` ignores them, `read` speaks them literally |
| `--quiet` | *(off)* | Suppress all progress output — only errors are printed |
| `--offline` | *(off)* | Block all Hugging Face Hub network calls. Use this after the model has been downloaded once to run fully air-gapped. |
| `--mp3-bitrate` | `192` | MP3 encoding bitrate in kbps — only used when output is `.mp3`. Options: `64`, `96`, `128`, `160`, `192`, `256`, `320` |
| `--kokoro-model` | `hexgrad/Kokoro-82M` | Kokoro model identifier |
| `--rewrite-with-ollama` | *(off)* | Enable Ollama-powered narration rewriting before TTS |
| `--ollama-model` | `llama3.2` | Ollama model to use when `--rewrite-with-ollama` is enabled |
| `--ollama-host` | `http://localhost:11434` | Base URL of the local Ollama server |

## Available voices

The default voice is `af_heart`. Pass any name below with `--voice NAME` and set `--lang-code` to match.

### 🇺🇸 American English (`--lang-code a`)

| Voice | Gender | Grade | Notes |
|-------|--------|-------|-------|
| `af_heart` | F | **A** | Default — highest overall quality |
| `af_bella` | F | A- | 🔥 Strong, lots of training data |
| `af_nicole` | F | B- | 🎧 Headphone style |
| `af_aoede` | F | C+ | |
| `af_kore` | F | C+ | |
| `af_sarah` | F | C+ | |
| `af_alloy` | F | C | |
| `af_nova` | F | C | |
| `af_jessica` | F | D | |
| `af_river` | F | D | |
| `af_sky` | F | C- | |
| `am_fenrir` | M | C+ | |
| `am_michael` | M | C+ | |
| `am_puck` | M | C+ | |
| `am_echo` | M | D | |
| `am_eric` | M | D | |
| `am_liam` | M | D | |
| `am_onyx` | M | D | |
| `am_adam` | M | F+ | |
| `am_santa` | M | D- | |

### 🇬🇧 British English (`--lang-code b`)

| Voice | Gender | Grade |
|-------|--------|-------|
| `bf_emma` | F | B- |
| `bf_alice` | F | D |
| `bf_isabella` | F | C |
| `bf_lily` | F | D |
| `bm_fable` | M | C |
| `bm_george` | M | C |
| `bm_daniel` | M | D |
| `bm_lewis` | M | D+ |

### 🇯🇵 Japanese (`--lang-code j`)

Requires `pip install misaki[ja]`.

| Voice | Gender | Grade |
|-------|--------|-------|
| `jf_alpha` | F | C+ |
| `jf_gongitsune` | F | C |
| `jf_tebukuro` | F | C |
| `jf_nezumi` | F | C- |
| `jm_kumo` | M | C- |

### 🇨🇳 Mandarin Chinese (`--lang-code z`)

Requires `pip install misaki[zh]`.

| Voice | Gender | Grade |
|-------|--------|-------|
| `zf_xiaobei` | F | D |
| `zf_xiaoni` | F | D |
| `zf_xiaoxiao` | F | D |
| `zf_xiaoyi` | F | D |
| `zm_yunjian` | M | D |
| `zm_yunxi` | M | D |
| `zm_yunxia` | M | D |
| `zm_yunyang` | M | D |

### 🇪🇸 Spanish (`--lang-code e`)

| Voice | Gender |
|-------|--------|
| `ef_dora` | F |
| `em_alex` | M |
| `em_santa` | M |

### 🇫🇷 French (`--lang-code f`)

| Voice | Gender | Grade |
|-------|--------|-------|
| `ff_siwis` | F | B- |

### 🇮🇳 Hindi (`--lang-code h`)

| Voice | Gender | Grade |
|-------|--------|-------|
| `hf_alpha` | F | C |
| `hf_beta` | F | C |
| `hm_omega` | M | C |
| `hm_psi` | M | C |

### 🇮🇹 Italian (`--lang-code i`)

| Voice | Gender | Grade |
|-------|--------|-------|
| `if_sara` | F | C |
| `im_nicola` | M | C |

### 🇧🇷 Brazilian Portuguese (`--lang-code p`)

| Voice | Gender |
|-------|--------|
| `pf_dora` | F |
| `pm_alex` | M |
| `pm_santa` | M |

> Grades reflect quality and quantity of training data. Voices perform best on 100–200 token utterances; very short or very long text may reduce quality. Use `--speed` to tune pacing.

## Notes

- The app defaults to direct Markdown-to-speech.
- Markdown image references insert silence instead of reading image alt text, which helps avoid duplicated figure captions in narration.
- Ollama is optional and only used when `--rewrite-with-ollama` is enabled.
- The current MVP always writes `.wav` output.
- The default Kokoro model target is `hexgrad/Kokoro-82M`.

## Run tests

```bash
source .venv/bin/activate
PYTHONPATH=src python -m unittest discover -s tests -v
```
