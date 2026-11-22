"""Ollama backend: POST {ollama_url}/api/generate with format:"json".

Stdlib only (urllib). Never raises to the caller.
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
    """Return the generated text from Ollama, or ``""`` when unavailable.

    The request payload always uses ``stream: false``; the ``stream`` argument is
    accepted for interface compatibility with the dispatcher.
    """
    _ = stream
    payload: dict[str, Any] = {
        "model": config.llm_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    url = config.llm_ollama_url.rstrip("/") + "/api/generate"
    try:
        body = _post_json(url, payload, config.llm_timeout_s)
    except Exception:
        body = None
    if not isinstance(body, str):
        return ""
    try:
        data = json.loads(body, strict=False)
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    response = data.get("response")
    return response if isinstance(response, str) else ""
