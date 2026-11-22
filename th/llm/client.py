"""LLM client interface: :class:`CommandReply`, the strict JSON validator, and the shared
stdlib HTTP helper. No third-party dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import urllib.request


@dataclass
class CommandReply:
    """A validated LLM command reply."""

    command: str
    explanation: str
    confidence: float


_REQUIRED_KEYS = ("command", "explanation", "confidence")
_MAX_COMMAND_LEN = 500

_FENCE_RE = re.compile(r"^\s*```(?:\w+)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """Remove an optional ```json fenced code block wrapper around the payload."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


def validate_command_json(text: str) -> CommandReply | None:
    """Validate a JSON command reply.

    Returns a :class:`CommandReply` when the payload is valid, ``None`` otherwise.

    Rules:
    - valid JSON (```json fenced wrappers are stripped first);
    - a JSON object with the required keys ``command``, ``explanation``, ``confidence``;
    - ``command`` and ``explanation`` are strings, ``command`` at most 500 chars;
    - ``confidence`` is a real number in [0, 1] (booleans rejected);
    - extra keys are tolerated.
    """
    try:
        payload = json.loads(_strip_fences(text))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    if any(key not in payload for key in _REQUIRED_KEYS):
        return None
    command = payload["command"]
    explanation = payload["explanation"]
    confidence = payload["confidence"]
    if not isinstance(command, str) or not isinstance(explanation, str):
        return None
    if len(command) > _MAX_COMMAND_LEN:
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        return None
    return CommandReply(command=command, explanation=explanation, confidence=confidence)


def _post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    headers: dict[str, str] | None = None,
) -> str | None:
    """POST JSON to ``url`` with ``timeout``; return the decoded body on 2xx, else ``None``.

    Never raises: connection errors, timeouts, non-2xx statuses all yield ``None``.
    """
    data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        url, data=data, headers=request_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status < 200 or resp.status >= 300:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
