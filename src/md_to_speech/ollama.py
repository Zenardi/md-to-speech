from __future__ import annotations

from dataclasses import dataclass
import json
from urllib import error, request

from md_to_speech.errors import OllamaError


DEFAULT_OLLAMA_PROMPT = (
    "Rewrite the following text to sound natural when spoken aloud. "
    "Preserve the meaning, order, and educational intent. "
    "Do not add new facts. "
    "Reply with ONLY the rewritten narration text. "
    "Do NOT include any preamble, introduction, label, or explanation such as "
    "'Here is the rewritten text' or 'Sure, here you go'. "
    "Start directly with the narration."
)

# Common LLM preamble patterns to strip defensively even when the prompt is followed.
_PREAMBLE_PATTERNS = (
    "here's the rewritten",
    "here is the rewritten",
    "here's the narration",
    "here is the narration",
    "here's the text",
    "here is the text",
    "sure, here",
    "sure! here",
    "certainly, here",
    "certainly! here",
    "of course, here",
    "of course! here",
)


@dataclass(frozen=True)
class OllamaRewriteOptions:
    model: str
    host: str
    system_prompt: str = DEFAULT_OLLAMA_PROMPT


def rewrite_text_for_speech(text: str, options: OllamaRewriteOptions) -> str:
    payload = json.dumps(
        {
            "model": options.model,
            "prompt": text,
            "system": options.system_prompt,
            "stream": False,
        }
    ).encode("utf-8")
    endpoint = f"{options.host.rstrip('/')}/api/generate"
    http_request = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise OllamaError(
            f"Ollama returned HTTP {exc.code}. Check that the model '{options.model}' is available."
        ) from exc
    except error.URLError as exc:
        raise OllamaError(
            f"Could not reach Ollama at {options.host}. Start Ollama first or update --ollama-host."
        ) from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON.") from exc

    rewritten = parsed.get("response", "").strip()
    if not rewritten:
        raise OllamaError("Ollama did not return any rewritten text.")
    return _strip_preamble(rewritten)


def _strip_preamble(text: str) -> str:
    """Remove common LLM preamble lines that precede the actual narration."""
    lines = text.splitlines()
    while lines:
        first = lines[0].strip().lower().rstrip(":.")
        if any(first.startswith(pattern) for pattern in _PREAMBLE_PATTERNS):
            lines.pop(0)
        else:
            break
    return "\n".join(lines).strip()
