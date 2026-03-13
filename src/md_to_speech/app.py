from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from md_to_speech.audio import PcmAudio, concatenate_audio, silence_audio, write_audio
from md_to_speech.errors import ValidationError
from md_to_speech.markdown_parser import (
    IMAGE_PAUSE_MARKER,
    MarkdownParseOptions,
    extract_text_blocks,
)
from md_to_speech.ollama import OllamaRewriteOptions, rewrite_text_for_speech
from md_to_speech.text_prep import prepare_text_chunks
from md_to_speech.tts import DEFAULT_KOKORO_MODEL, KokoroConfig, KokoroSynthesizer, SpeechSynthesizer


@dataclass(frozen=True)
class AppConfig:
    input_path: Path
    output_path: Path | None
    code_block_behavior: str = "skip"
    max_chars: int = 1200
    rewrite_with_ollama: bool = False
    ollama_model: str = "llama3.2"
    ollama_host: str = "http://localhost:11434"
    ollama_system_prompt: str = (
        "Rewrite the following text to sound natural when spoken aloud. "
        "Preserve the meaning and order. Return only the rewritten narration text."
    )
    kokoro_model: str = DEFAULT_KOKORO_MODEL
    voice: str = "af_heart"
    lang_code: str = "a"
    speed: float = 1.0
    image_pause_seconds: float = 1.0
    mp3_bitrate: int = 192
    offline: bool = False
    quiet: bool = False


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    chunk_count: int
    duration_seconds: float


@dataclass(frozen=True)
class NarrationStep:
    kind: str
    text: str = ""


def synthesize_markdown_file(
    config: AppConfig,
    *,
    synthesizer: SpeechSynthesizer | None = None,
) -> GenerationResult:
    verbose = not config.quiet

    validate_config(config)

    _log(verbose, f"📄 Parsing {config.input_path.name}...")
    input_text = config.input_path.read_text(encoding="utf-8")
    blocks = extract_text_blocks(
        input_text,
        MarkdownParseOptions(code_block_behavior=config.code_block_behavior),
    )
    steps = prepare_narration_steps(blocks, max_chars=config.max_chars)
    chunk_count = sum(1 for step in steps if step.kind == "text")
    _log(verbose, f"✂️  Split into {chunk_count} chunk(s).")

    if config.rewrite_with_ollama:
        rewrite_options = OllamaRewriteOptions(
            model=config.ollama_model,
            host=config.ollama_host,
            system_prompt=config.ollama_system_prompt,
        )
        _log(verbose, f"🤖 Rewriting chunks with Ollama ({config.ollama_model})...")
        steps = [
            NarrationStep(
                kind=step.kind,
                text=rewrite_text_for_speech(step.text, rewrite_options) if step.kind == "text" else step.text,
            )
            for step in tqdm(steps, desc="Rewriting", unit="chunk", disable=not verbose)
        ]

    _log(verbose, f"🔊 Loading Kokoro model ({config.voice})...")
    runtime_synthesizer = synthesizer or KokoroSynthesizer(
        KokoroConfig(
            model_name=config.kokoro_model,
            voice=config.voice,
            lang_code=config.lang_code,
            speed=config.speed,
            offline=config.offline,
        )
    )

    audio_chunks: list[PcmAudio] = []
    pending_leading_pause_seconds = 0.0
    for step in tqdm(steps, desc="Synthesizing", unit="chunk", disable=not verbose):
        if step.kind == "pause":
            if config.image_pause_seconds <= 0:
                continue
            if audio_chunks:
                reference_audio = audio_chunks[-1]
                audio_chunks.append(
                    silence_audio(
                        sample_rate=reference_audio.sample_rate,
                        channels=reference_audio.channels,
                        sample_width=reference_audio.sample_width,
                        duration_seconds=config.image_pause_seconds,
                    )
                )
            else:
                pending_leading_pause_seconds += config.image_pause_seconds
            continue

        synthesized_audio = runtime_synthesizer.synthesize(step.text)
        if pending_leading_pause_seconds > 0:
            audio_chunks.append(
                silence_audio(
                    sample_rate=synthesized_audio.sample_rate,
                    channels=synthesized_audio.channels,
                    sample_width=synthesized_audio.sample_width,
                    duration_seconds=pending_leading_pause_seconds,
                )
            )
            pending_leading_pause_seconds = 0.0
        audio_chunks.append(synthesized_audio)

    _log(verbose, "🔗 Merging audio...")
    merged_audio = concatenate_audio(audio_chunks)

    output_path = resolve_output_path(config.input_path, config.output_path)
    _log(verbose, f"💾 Writing {output_path.suffix.lstrip('.').upper()} to {output_path}...")
    write_audio(merged_audio, output_path, mp3_bitrate=config.mp3_bitrate)

    return GenerationResult(
        output_path=output_path,
        chunk_count=chunk_count,
        duration_seconds=merged_audio.duration_seconds,
    )


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def validate_config(config: AppConfig) -> None:
    if not config.input_path.exists():
        raise ValidationError(f"Input file does not exist: {config.input_path}")
    if not config.input_path.is_file():
        raise ValidationError(f"Input path is not a file: {config.input_path}")
    if config.input_path.suffix.lower() not in {".md", ".markdown", ".mdown"}:
        raise ValidationError("Input file must be a Markdown file with a .md-style extension.")
    if config.code_block_behavior not in {"skip", "read"}:
        raise ValidationError("code_block_behavior must be either 'skip' or 'read'.")
    if config.speed <= 0:
        raise ValidationError("speed must be greater than zero.")
    if config.image_pause_seconds < 0:
        raise ValidationError("image_pause_seconds must be greater than or equal to zero.")


def resolve_output_path(input_path: Path, output_path: Path | None) -> Path:
    if output_path is None:
        return input_path.with_suffix(".wav")

    if output_path.exists() and output_path.is_dir():
        return output_path / f"{input_path.stem}.wav"

    if output_path.suffix.lower() not in {".wav", ".mp3"}:
        raise ValidationError("Output path must end with .wav or .mp3, or point to an existing directory.")
    return output_path


def prepare_narration_steps(blocks: list[str], *, max_chars: int) -> list[NarrationStep]:
    steps: list[NarrationStep] = []
    pending_text_blocks: list[str] = []

    def flush_pending_text() -> None:
        if not pending_text_blocks:
            return
        text_chunks = prepare_text_chunks(pending_text_blocks, max_chars=max_chars)
        steps.extend(NarrationStep(kind="text", text=chunk.text) for chunk in text_chunks)
        pending_text_blocks.clear()

    for block in blocks:
        fragments = block.split(IMAGE_PAUSE_MARKER)
        for index, fragment in enumerate(fragments):
            if fragment.strip():
                pending_text_blocks.append(fragment)
            if index < len(fragments) - 1:
                flush_pending_text()
                steps.append(NarrationStep(kind="pause"))

    flush_pending_text()

    if not any(step.kind == "text" for step in steps):
        raise ValidationError("The markdown file did not produce any readable content.")

    return steps
