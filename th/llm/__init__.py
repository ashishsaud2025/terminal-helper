"""LLM client module for Terminal Helper.

Swappable backends behind a single dispatcher:

* :func:`ask` routes to the backend named by ``config.llm_backend``
  (``ollama``, ``openai_compat``, ``anthropic``, ``cli_agent``).
* :func:`validate_command_json` strictly validates JSON command replies.
* :func:`build_system_prompt` builds the system prompt from the instruction line plus the
  few-shot examples in ``prompts/bash.txt``.

Stdlib only at runtime. Never raises to the caller.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from th import redact
from th.config import Config

from th.llm.client import CommandReply, validate_command_json

from th.llm import anthropic, cli_agent, ollama, openai_compat

_BACKENDS: dict[str, object] = {
    "ollama": ollama,
    "openai_compat": openai_compat,
    "anthropic": anthropic,
    "cli_agent": cli_agent,
}

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"


def build_system_prompt(shell: str, os: str) -> str:
    """Build the LLM system prompt.

    Exact instruction line plus the few-shot block from ``prompts/bash.txt`` when present.
    Never raises.
    """
    try:
        spec = (
            "You output exactly one {shell} command for {os}. No markdown. "
            "If unsure, return an empty command."
        ).format(shell=shell, os=os)
        few_shot = (_PROMPTS_DIR / "bash.txt").read_text(encoding="utf-8").strip()
    except Exception:
        few_shot = ""
        spec = (
            "You output exactly one {shell} command for {os}. No markdown. "
            "If unsure, return an empty command."
        ).format(shell=shell, os=os)
    if few_shot:
        return f"{spec}\n\n{few_shot}"
    return spec


def ask(
    system: str,
    prompt: str,
    *,
    stream: bool = False,
    config: Config | None = None,
) -> str | Iterator[str]:
    """Ask the configured LLM backend.

    Returns the generated text (non-streaming), or an iterator of text chunks when
    ``stream=True``. Returns ``""`` (or an empty iterator) when the LLM is disabled,
    unavailable, or malformed; never raises to the caller.
    """
    cfg = config if config is not None else Config()
    try:
        if not cfg.llm_enabled:
            return iter(()) if stream else ""
        backend = _BACKENDS.get(cfg.llm_backend)
        if backend is None:
            return iter(()) if stream else ""
        if cfg.llm_backend != "ollama":
            system = redact.redact(system)
            prompt = redact.redact(prompt)
        result = backend.ask(system, prompt, stream=stream, config=cfg)
    except Exception:
        return iter(()) if stream else ""
    if stream:
        if isinstance(result, str):
            return iter([result]) if result else iter(())
        return result
    return result if isinstance(result, str) else ""
