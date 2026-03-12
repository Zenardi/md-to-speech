from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol
import warnings

from md_to_speech.audio import PcmAudio, audio_from_samples, concatenate_audio
from md_to_speech.errors import ModelIntegrationError, ValidationError


DEFAULT_KOKORO_MODEL = "hexgrad/Kokoro-82M"


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str) -> PcmAudio:
        """Convert text to PCM audio."""


@dataclass(frozen=True)
class KokoroConfig:
    model_name: str = DEFAULT_KOKORO_MODEL
    voice: str = "af_heart"
    lang_code: str = "a"
    speed: float = 1.0
    sample_rate: int = 24_000
    split_pattern: str = r"\n+"
    offline: bool = False


class KokoroSynthesizer:
    def __init__(self, config: KokoroConfig) -> None:
        self._config = config
        self._pipeline = self._load_pipeline(config)

    def synthesize(self, text: str) -> PcmAudio:
        if not text.strip():
            raise ValidationError("Cannot synthesize empty text.")

        generator = self._pipeline(
            text,
            voice=self._config.voice,
            speed=self._config.speed,
            split_pattern=self._config.split_pattern,
        )

        chunks: list[PcmAudio] = []
        for _, _, audio in generator:
            chunks.append(
                audio_from_samples(
                    audio,
                    sample_rate=self._config.sample_rate,
                )
            )

        if not chunks:
            raise ModelIntegrationError("Kokoro did not generate any audio chunks.")
        return concatenate_audio(chunks)

    @staticmethod
    def _load_pipeline(config: KokoroConfig):
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise ModelIntegrationError(
                "The 'kokoro' package is not installed. Run 'pip install -e .' and make sure espeak-ng is installed."
            ) from exc

        if config.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"

        # Suppress noisy internal PyTorch warnings that come from the Kokoro model
        # architecture. These are from torch internals, not from our code, and
        # do not affect functionality.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="torch")
            warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
            try:
                return KPipeline(lang_code=config.lang_code, repo_id=config.model_name)
            except TypeError:
                if config.model_name != DEFAULT_KOKORO_MODEL:
                    raise ModelIntegrationError(
                        "The installed kokoro package does not support selecting a custom repo_id. "
                        f"Use the default model '{DEFAULT_KOKORO_MODEL}' or upgrade the package."
                    )
                return KPipeline(lang_code=config.lang_code)
