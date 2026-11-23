"""Context bundle for `th fix`.

Produces a plain stdlib :class:`ContextBundle` describing the shell context of
the last failed command: OS, shell, cwd, recent commands, and cwd file names.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass

from th import db


@dataclass
class ContextBundle:
    """Snapshot of the shell context used to build (and explain) fix suggestions."""

    os: str
    shell: str
    cwd: str
    last_commands: list[str]
    cwd_files: list[str]
    last_exit_code: int | None


def _db_path():
    """Resolve the th data dir lazily to avoid a circular import with th.cli."""
    from th.cli import db_path

    return db_path()


def build_context(cmdline: str, exit_code: int | None, stderr_tail: str) -> ContextBundle:
    """Build a :class:`ContextBundle` for the failed command.

    - ``os``/``shell`` come from the platform and environment.
    - ``cwd`` is the current working directory.
    - ``cwd_files`` are entry names only (via os.listdir), capped at 50,
      sorted, contents never read.
    - ``last_commands`` is the ``cmd`` field of the last 5 db rows.
    Never raises.
    """
    _ = stderr_tail
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = ""
    try:
        names = sorted(os.listdir(cwd)) if cwd else []
    except OSError:
        names = []
    cwd_files = [str(n) for n in names[:50]]

    last_commands: list[str] = []
    try:
        rows = db.recent_commands(_db_path(), 5)
        last_commands = [str(r["cmd"]) for r in rows]
    except Exception:
        last_commands = []

    return ContextBundle(
        os=platform.system(),
        shell=os.environ.get("SHELL", "bash"),
        cwd=cwd,
        last_commands=last_commands,
        cwd_files=cwd_files,
        last_exit_code=exit_code,
    )
