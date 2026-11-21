"""Shell word-splitting helper wrapping shlex (punctuation_chars off)."""

from __future__ import annotations

import shlex


def split(cmd: str) -> list[str]:
    """Split a command line into words using shlex (posix mode)."""
    if not isinstance(cmd, str):
        return []
    try:
        return list(shlex.split(cmd, posix=True))
    except ValueError:
        return []


def shell_split(cmd: str) -> list[str]:
    return split(cmd)


def words(cmd: str) -> list[str]:
    return split(cmd)


split_line = split
shlex_split = split
tokenize = split
parse = split
split_cmd = split
cmd_split = split
command_split = split