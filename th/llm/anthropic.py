"""Anthropic Messages backend (experimental).

POST {base}/v1/messages with the Anthropic version header.
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
    """Return the assistant text content, or ``""`` when unavailable."""
    _ = stream
    base = getattr(config, "llm_anthropic_url", None) or config.llm_ollama_url
    url = base.rstrip("/") + "/v1/messages"
    payload: dict[str, Any] = {
        "model": config.llm_model,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0,
        "stream": False,
    }
    try:
        body = _post_json(
            url,
            payload,
            config.llm_timeout_s,
            headers={"anthropic-version": "2023-06-01"},
        )
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
    content = data.get("content")
    if not isinstance(content, list) or not content:
        return ""
    first = content[0]
    if not isinstance(first, dict):
        return ""
    text = first.get("text")
    return text if isinstance(text, str) else ""
