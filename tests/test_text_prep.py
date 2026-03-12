import unittest

from md_to_speech.text_prep import prepare_text_chunks


class TextPrepTests(unittest.TestCase):
    def test_splits_large_blocks_into_bounded_chunks(self) -> None:
        blocks = [
            "Sentence one. Sentence two. Sentence three. Sentence four.",
            "Sentence five. Sentence six.",
        ]
        chunks = prepare_text_chunks(blocks, max_chars=30)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 30 for chunk in chunks))
        self.assertTrue(chunks[0].text.startswith("Sentence one"))


if __name__ == "__main__":
    unittest.main()
