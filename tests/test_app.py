from pathlib import Path
import tempfile
import unittest
import wave

from md_to_speech.app import AppConfig, synthesize_markdown_file
from md_to_speech.audio import PcmAudio


class FakeSynthesizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, text: str) -> PcmAudio:
        self.calls.append(text)
        frames = (b"\x00\x00" * 1200)
        return PcmAudio(sample_rate=24000, channels=1, sample_width=2, frames=frames)


class AppTests(unittest.TestCase):
    def test_generates_wav_from_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "lesson.md"
            output_path = temp_path / "lesson.wav"
            input_path.write_text("# Title\n\nParagraph one.\n\nParagraph two.\n", encoding="utf-8")

            result = synthesize_markdown_file(
                AppConfig(
                    input_path=input_path,
                    output_path=output_path,
                    max_chars=200,
                ),
                synthesizer=FakeSynthesizer(),
            )

            self.assertEqual(result.output_path, output_path)
            self.assertTrue(output_path.exists())

            with wave.open(str(output_path), "rb") as wav_file:
                self.assertEqual(wav_file.getframerate(), 24000)
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertGreater(wav_file.getnframes(), 0)

    def test_inserts_default_pause_for_images_without_speaking_alt_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "lesson.md"
            output_path = temp_path / "lesson.wav"
            fake_synthesizer = FakeSynthesizer()
            input_path.write_text(
                "Before the figure.\n\n![Projected detections](figure.png)\n\nFigure 1. A BEV projection.\n",
                encoding="utf-8",
            )

            result = synthesize_markdown_file(
                AppConfig(
                    input_path=input_path,
                    output_path=output_path,
                    max_chars=200,
                ),
                synthesizer=fake_synthesizer,
            )

            self.assertEqual(fake_synthesizer.calls, ["Before the figure.", "Figure 1. A BEV projection."])
            self.assertAlmostEqual(result.duration_seconds, 1.1, places=2)

            with wave.open(str(output_path), "rb") as wav_file:
                self.assertEqual(wav_file.getnframes(), 26400)

    def test_uses_configured_image_pause_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "lesson.md"
            output_path = temp_path / "lesson.wav"
            fake_synthesizer = FakeSynthesizer()
            input_path.write_text(
                "First paragraph.\n\n![Projected detections](figure.png)\n\nSecond paragraph.\n",
                encoding="utf-8",
            )

            result = synthesize_markdown_file(
                AppConfig(
                    input_path=input_path,
                    output_path=output_path,
                    max_chars=200,
                    image_pause_seconds=0.25,
                ),
                synthesizer=fake_synthesizer,
            )

            self.assertEqual(fake_synthesizer.calls, ["First paragraph.", "Second paragraph."])
            self.assertAlmostEqual(result.duration_seconds, 0.35, places=2)


if __name__ == "__main__":
    unittest.main()
