"""Secret redaction for command lines, stderr tails, and LLM prompt context.

Patterns (case-insensitive where noted); the ``VALUE`` is replaced with
``[REDACTED]`` while the key name / prefix is kept:

* AWS access key id: ``AKIA`` + 16 uppercase alphanumerics
* ``Authorization: Bearer|Basic <token>``
* ``password``/``passwd``/``pwd``/``token``/``secret``/``api_key``/``api-key`` = value
* ``sk-`` + 20+ alphanumerics (OpenAI-style keys)
* ``ghp_`` + 36+ alphanumerics (GitHub tokens)
* PEM private key blocks (``-----BEGIN ... PRIVATE KEY-----`` ... ``-----END ...``), DOTALL
* Slack tokens ``xox[baprs]-...``

Stdlib only (``re``). Never raises.
"""

from __future__ import annotations

import re

_REPLACEMENT = "[REDACTED]"

_PATTERNS: list[tuple[re.Pattern[str], int | None]] = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), None),

    (re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer|basic)(\s+)(\S+)"), 4),

    (re.compile(r"(?i)(password|passwd|pwd|token|secret|api[-_]?key)(\s*[:=]\s*)(\S+)"), 3),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), None),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), None),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), None),
    (re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]+"), None),
]


def _replace_value(match: re.Match[str], value_group: int | None) -> str:
    if value_group is None:
        return _REPLACEMENT
    return "".join(match.group(i) for i in range(1, value_group)) + _REPLACEMENT


def redact(text: str) -> str:
    """Return ``text`` with secret values replaced by ``[REDACTED]``.

    Key names / prefixes are preserved. ``None`` returns ``""``; empty or
    falsy input is returned as-is.
    """
    if text is None:
        return ""
    if not text:
        return text
    result = text
    for pattern, value_group in _PATTERNS:
        if value_group is None:
            result = pattern.sub(_REPLACEMENT, result)
        else:
            result = pattern.sub(lambda m: _replace_value(m, value_group), result)
    return result
