from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import wave

from md_to_speech.errors import ValidationError


@dataclass(frozen=True)
class PcmAudio:
    sample_rate: int
    channels: int
    sample_width: int
    frames: bytes

    @property
    def frame_count(self) -> int:
        return len(self.frames) // (self.channels * self.sample_width)

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / float(self.sample_rate)


def samples_to_pcm16(audio_samples: object) -> bytes:
    flat_samples = _flatten_samples(audio_samples)
    if not flat_samples:
        raise ValidationError("The TTS engine returned an empty audio buffer.")

    pcm = array("h")
    for sample in flat_samples:
        numeric_sample = float(sample)
        if -1.5 <= numeric_sample <= 1.5:
            scaled = int(round(max(-1.0, min(1.0, numeric_sample)) * 32767))
        else:
            scaled = int(round(max(-32768, min(32767, numeric_sample))))
        pcm.append(scaled)
    return pcm.tobytes()


def audio_from_samples(
    audio_samples: object,
    *,
    sample_rate: int,
    channels: int = 1,
    sample_width: int = 2,
) -> PcmAudio:
    if channels != 1:
        raise ValidationError("Only mono audio is supported in the current MVP.")
    if sample_width != 2:
        raise ValidationError("Only 16-bit PCM WAV output is supported.")
    return PcmAudio(
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frames=samples_to_pcm16(audio_samples),
    )


def concatenate_audio(chunks: list[PcmAudio]) -> PcmAudio:
    if not chunks:
        raise ValidationError("No audio chunks were generated.")

    first = chunks[0]
    for chunk in chunks[1:]:
        if chunk.sample_rate != first.sample_rate:
            raise ValidationError("Audio chunks use different sample rates.")
        if chunk.channels != first.channels:
            raise ValidationError("Audio chunks use different channel counts.")
        if chunk.sample_width != first.sample_width:
            raise ValidationError("Audio chunks use different sample widths.")

    return PcmAudio(
        sample_rate=first.sample_rate,
        channels=first.channels,
        sample_width=first.sample_width,
        frames=b"".join(chunk.frames for chunk in chunks),
    )


def write_audio(audio: PcmAudio, output_path: Path, *, mp3_bitrate: int = 192) -> None:
    """Write audio to disk; format is inferred from the output path extension."""
    suffix = output_path.suffix.lower()
    if suffix == ".mp3":
        write_mp3(audio, output_path, bitrate=mp3_bitrate)
    else:
        write_wav(audio, output_path)


def write_wav(audio: PcmAudio, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(audio.channels)
        wav_file.setsampwidth(audio.sample_width)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.frames)


def write_mp3(audio: PcmAudio, output_path: Path, *, bitrate: int = 192) -> None:
    try:
        import lameenc
    except ImportError as exc:
        raise ValidationError(
            "MP3 output requires the 'lameenc' package. Run: pip install lameenc"
        ) from exc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(audio.sample_rate)
    encoder.set_channels(audio.channels)
    encoder.set_quality(2)  # 2 = high quality, 7 = fastest

    mp3_data = encoder.encode(audio.frames)
    mp3_data += encoder.flush()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(mp3_data)


def _flatten_samples(audio_samples: object) -> list[float]:
    if hasattr(audio_samples, "detach") and hasattr(audio_samples, "cpu"):
        detached = audio_samples.detach().cpu()
        if hasattr(detached, "flatten"):
            return [float(value) for value in detached.flatten().tolist()]

    if hasattr(audio_samples, "flatten") and hasattr(audio_samples, "tolist"):
        flattened = audio_samples.flatten()
        to_list = flattened.tolist()
        if isinstance(to_list, list):
            return [float(value) for value in to_list]

    if isinstance(audio_samples, (list, tuple)):
        return _flatten_sequence(audio_samples)

    raise ValidationError(
        "The TTS engine returned an unsupported audio sample format."
    )


def _flatten_sequence(sequence: list[object] | tuple[object, ...]) -> list[float]:
    values: list[float] = []
    for item in sequence:
        if isinstance(item, (list, tuple)):
            values.extend(_flatten_sequence(item))
        else:
            values.append(float(item))
    return values
