import unittest

from md_to_speech.markdown_parser import MarkdownParseOptions, extract_text_blocks


class MarkdownParserTests(unittest.TestCase):
    def test_skips_code_blocks_by_default(self) -> None:
        markdown = """# Intro

This is a [course](https://example.com) lesson.

```python
print("hello")
```

- First item
"""
        blocks = extract_text_blocks(markdown, MarkdownParseOptions())
        self.assertEqual(
            blocks,
            [
                "Section. Intro.",
                "This is a course lesson.",
                "List item. First item.",
            ],
        )

    def test_reads_code_blocks_when_requested(self) -> None:
        markdown = """## Sample

```js
const total = 3;
```
"""
        blocks = extract_text_blocks(
            markdown,
            MarkdownParseOptions(code_block_behavior="read"),
        )
        self.assertEqual(
            blocks,
            [
                "Section. Sample.",
                "Code example. const total = 3;",
            ],
        )


if __name__ == "__main__":
    unittest.main()
