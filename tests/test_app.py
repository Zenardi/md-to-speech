from pathlib import Path
import tempfile
import unittest
import wave

from md_to_speech.app import AppConfig, synthesize_markdown_file
from md_to_speech.audio import PcmAudio


class FakeSynthesizer:
    def synthesize(self, text: str) -> PcmAudio:
        del text
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


if __name__ == "__main__":
    unittest.main()
