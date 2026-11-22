"""CLI-agent backend (experimental).

Runs a non-interactive CLI agent such as ``claude -p --output-format text`` behind the
``llm.cli_agent_cmd`` config entry. Arguments are shell-escaped via :func:`shlex.split`
and passed as argv (no shell=True). Never raises to the caller.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from th.config import Config

_DEFAULT_CLI_AGENT_CMD = "claude -p --output-format text"


def ask(
    system: str,
    prompt: str,
    *,
    stream: bool = False,
    config: Config,
) -> str:
    """Return the agent's stdout, or ``""`` when unavailable."""
    _ = stream
    template = getattr(config, "llm_cli_agent_cmd", _DEFAULT_CLI_AGENT_CMD) or (
        _DEFAULT_CLI_AGENT_CMD
    )
    try:
        args = shlex.split(template)
        args.append(f"{system}\n\n{prompt}" if system else prompt)
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=config.llm_timeout_s
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""
