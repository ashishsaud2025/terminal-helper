"""CLI-agent backend (experimental).

Runs a non-interactive CLI agent such as ``claude -p --output-format text`` behind the
``llm.cli_agent_cmd`` config entry. The template is split with :func:`shlex.split` and
the prompt is appended as the final argv element; :func:`subprocess.run` is called with
the resulting list and no ``shell=True``. The ``system`` prompt is accepted for interface
compatibility but is not sent to the CLI. Never raises to the caller.
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
    _ = system
    template = getattr(config, "llm_cli_agent_cmd", _DEFAULT_CLI_AGENT_CMD) or (
        _DEFAULT_CLI_AGENT_CMD
    )
    try:
        args = shlex.split(template)
        args.append(prompt)
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=config.llm_timeout_s
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""
