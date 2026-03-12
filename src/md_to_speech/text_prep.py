from __future__ import annotations

from dataclasses import dataclass
import re

from md_to_speech.errors import ValidationError


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MULTISPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str


def prepare_text_chunks(blocks: list[str], *, max_chars: int) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValidationError("max_chars must be greater than zero.")

    sanitized_blocks = [normalize_for_speech(block) for block in blocks if normalize_for_speech(block)]
    if not sanitized_blocks:
        raise ValidationError("The markdown file did not produce any readable content.")

    chunks: list[str] = []
    current_parts: list[str] = []
    current_length = 0

    for block in sanitized_blocks:
        for piece in split_long_text(block, max_chars=max_chars):
            projected_length = current_length + len(piece) + (1 if current_parts else 0)
            if current_parts and projected_length > max_chars:
                chunks.append(" ".join(current_parts))
                current_parts = [piece]
                current_length = len(piece)
            else:
                current_parts.append(piece)
                current_length = projected_length

    if current_parts:
        chunks.append(" ".join(current_parts))

    return [TextChunk(index=index, text=text) for index, text in enumerate(chunks)]


def normalize_for_speech(text: str) -> str:
    return MULTISPACE_RE.sub(" ", text).strip()


def split_long_text(text: str, *, max_chars: int) -> list[str]:
    normalized = normalize_for_speech(text)
    if len(normalized) <= max_chars:
        return [normalized]

    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(normalized) if sentence.strip()]
    if len(sentences) <= 1:
        return split_by_words(normalized, max_chars=max_chars)

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    final_chunks: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            final_chunks.extend(split_by_words(chunk, max_chars=max_chars))
        else:
            final_chunks.append(chunk)
    return final_chunks


def split_by_words(text: str, *, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = " ".join([*current_words, word])
        if current_words and len(candidate) > max_chars:
            chunks.append(" ".join(current_words))
            current_words = [word]
        else:
            current_words.append(word)

    if current_words:
        chunks.append(" ".join(current_words))
    return chunks
