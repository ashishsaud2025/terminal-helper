"""OpenAI-compatible chat backend (experimental).

POST {base}/v1/chat/completions with temperature 0 and stream:false.
Never raises to the caller.
"""

from __future__ import annotations

import json
from typing import Any

from th.config import Config

from th.llm.client import _post_json


def ask(
    system: str,
    prompt: str,
    *,
    stream: bool = False,
    config: Config,
) -> str:
    """Return the assistant message content, or ``""`` when unavailable."""
    _ = stream
    base = getattr(config, "llm_openai_url", None) or config.llm_ollama_url
    url = base.rstrip("/") + "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "stream": False,
    }
    try:
        body = _post_json(url, payload, config.llm_timeout_s)
    except Exception:
        return ""
    if not isinstance(body, str):
        return ""
    try:
        data = json.loads(body, strict=False)
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""
