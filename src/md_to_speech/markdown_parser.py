from __future__ import annotations

from dataclasses import dataclass
import re


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
LIST_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+(.*)$")
ORDERED_LIST_PREFIX_RE = re.compile(r"^\d+\.\s+")
TABLE_SEPARATOR_RE = re.compile(r"^\s*[:\-| ]+\s*$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MarkdownParseOptions:
    code_block_behavior: str = "skip"


def extract_text_blocks(markdown_text: str, options: MarkdownParseOptions) -> list[str]:
    blocks: list[str] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False
    fence_marker = ""

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        paragraph_text = normalize_inline_markdown(" ".join(paragraph_lines))
        if paragraph_text:
            blocks.append(paragraph_text)
        paragraph_lines.clear()

    def flush_code_block() -> None:
        if not code_lines:
            return
        if options.code_block_behavior == "read":
            code_text = " ".join(line.strip() for line in code_lines if line.strip())
            code_text = normalize_inline_markdown(code_text)
            if code_text:
                blocks.append(f"Code example. {code_text}")
        code_lines.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if in_code_block:
            if _is_fence_close(line, fence_marker):
                flush_code_block()
                in_code_block = False
                fence_marker = ""
            else:
                code_lines.append(line)
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            flush_paragraph()
            in_code_block = True
            fence_marker = fence_match.group(1)[0]
            code_lines.clear()
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue

        if _is_horizontal_rule(stripped):
            flush_paragraph()
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            heading_text = normalize_inline_markdown(heading_match.group(2))
            if heading_text:
                blocks.append(f"Section. {heading_text}")
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            flush_paragraph()
            item_text = normalize_inline_markdown(list_match.group(2))
            if item_text:
                blocks.append(f"List item. {item_text}")
            continue

        if stripped.startswith(">"):
            paragraph_lines.append(stripped.lstrip(">").strip())
            continue

        if "|" in stripped and not TABLE_SEPARATOR_RE.match(stripped):
            flush_paragraph()
            table_cells = [normalize_inline_markdown(cell) for cell in stripped.strip("|").split("|")]
            row_text = ", ".join(cell for cell in table_cells if cell)
            if row_text:
                blocks.append(f"Table row. {row_text}")
            continue

        paragraph_lines.append(stripped)

    flush_paragraph()
    if in_code_block:
        flush_code_block()

    return [block for block in blocks if block]


def normalize_inline_markdown(text: str) -> str:
    normalized = text.strip()
    normalized = IMAGE_RE.sub(lambda match: match.group(1), normalized)
    normalized = LINK_RE.sub(lambda match: match.group(1), normalized)
    normalized = INLINE_CODE_RE.sub(lambda match: match.group(1), normalized)
    normalized = HTML_TAG_RE.sub(" ", normalized)
    normalized = normalized.replace("\\", "")
    normalized = normalized.replace("***", "")
    normalized = normalized.replace("___", "")
    normalized = normalized.replace("**", "")
    normalized = normalized.replace("__", "")
    normalized = normalized.replace("*", "")
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("~", "")
    normalized = ORDERED_LIST_PREFIX_RE.sub("", normalized)
    normalized = MULTISPACE_RE.sub(" ", normalized).strip()
    if normalized and normalized[-1].isalnum():
        normalized = f"{normalized}."
    return normalized


def _is_horizontal_rule(stripped_line: str) -> bool:
    if len(stripped_line) < 3:
        return False
    without_spaces = stripped_line.replace(" ", "")
    return set(without_spaces) in ({"-"}, {"*"}, {"_"})


def _is_fence_close(line: str, fence_marker: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {fence_marker} and len(stripped) >= 3
