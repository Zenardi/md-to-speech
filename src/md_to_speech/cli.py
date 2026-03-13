from __future__ import annotations

import argparse
from pathlib import Path
import sys

from md_to_speech.app import AppConfig, synthesize_markdown_file
from md_to_speech.errors import MdToSpeechError
from md_to_speech.tts import DEFAULT_KOKORO_MODEL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-to-speech",
        description="Convert a Markdown file into a WAV narration file using Kokoro TTS.",
    )
    parser.add_argument("input", help="Path to the input Markdown file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output WAV file path or an existing directory.",
    )
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="Kokoro voice name. Default: af_heart",
    )
    parser.add_argument(
        "--lang-code",
        default="a",
        help="Kokoro language code. Default: a",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed multiplier. Default: 1.0",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=1200,
        help="Maximum characters per narration chunk. Default: 1200",
    )
    parser.add_argument(
        "--code-block-behavior",
        choices=["skip", "read"],
        default="skip",
        help="Whether fenced code blocks are skipped or read literally.",
    )
    parser.add_argument(
        "--kokoro-model",
        default=DEFAULT_KOKORO_MODEL,
        help=f"Kokoro model identifier. Default: {DEFAULT_KOKORO_MODEL}",
    )
    parser.add_argument(
        "--rewrite-with-ollama",
        action="store_true",
        help="Rewrite chunks with a local Ollama model before TTS.",
    )
    parser.add_argument(
        "--ollama-model",
        default="llama3.2",
        help="Ollama model name used when --rewrite-with-ollama is enabled.",
    )
    parser.add_argument(
        "--ollama-host",
        default="http://localhost:11434",
        help="Base URL for the local Ollama server.",
    )
    parser.add_argument(
        "--image-pause-seconds",
        type=float,
        default=1.0,
        help="Pause duration inserted for each Markdown image. Default: 1.0",
    )
    parser.add_argument(
        "--mp3-bitrate",
        type=int,
        default=192,
        choices=[64, 96, 128, 160, 192, 256, 320],
        help="MP3 encoding bitrate in kbps (only used when output is .mp3). Default: 192",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Block all Hugging Face Hub network calls. "
            "Use this after the model has been downloaded once to run fully offline."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all progress output. Only errors are printed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = AppConfig(
        input_path=Path(args.input).expanduser().resolve(),
        output_path=Path(args.output).expanduser().resolve() if args.output else None,
        code_block_behavior=args.code_block_behavior,
        max_chars=args.max_chars,
        rewrite_with_ollama=args.rewrite_with_ollama,
        ollama_model=args.ollama_model,
        ollama_host=args.ollama_host,
        kokoro_model=args.kokoro_model,
        voice=args.voice,
        lang_code=args.lang_code,
        speed=args.speed,
        image_pause_seconds=args.image_pause_seconds,
        mp3_bitrate=args.mp3_bitrate,
        offline=args.offline,
        quiet=args.quiet,
    )

    try:
        result = synthesize_markdown_file(config)
    except MdToSpeechError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"✅ Done — {result.output_path} "
        f"({result.chunk_count} chunk(s), {result.duration_seconds:.2f}s)"
    )
    return 0
