"""Rules engine: typo fixes, flag/path checks, did-you-mean parsing, danger scan."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import Container, Iterable


@dataclass
class Problem:
    kind: str
    message: str
    suggestion: str | None = None


@dataclass
class DangerMatch:
    pattern: str
    detail: str
    safer: str | None = None


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 3
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def normalize_cmd(cmd: str) -> str:
    if not isinstance(cmd, str):
        return ""
    return " ".join(cmd.split())


def split_pipeline(cmdline: str) -> list[str]:
    if not isinstance(cmdline, str):
        return []
    s = cmdline.strip()
    if not s:
        return []
    if "$(" in s or "`" in s:
        return []
    if ">" in s:
        return []
    segments: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(s)
    in_single = False
    in_double = False
    while i < n:
        ch = s[i]
        if in_single:
            cur.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            cur.append(ch)
            if ch == "\\" and i + 1 < n:
                cur.append(s[i + 1])
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            cur.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            cur.append(ch)
            i += 1
            continue
        if ch == "\\":
            if i + 1 < n:
                cur.append(ch)
                cur.append(s[i + 1])
                i += 2
                continue
            cur.append(ch)
            i += 1
            continue
        if ch == "|":
            segments.append("".join(cur))
            cur = []
            if i + 1 < n and s[i + 1] == "|":
                i += 2
            else:
                i += 1
            continue
        if ch == ";":
            segments.append("".join(cur))
            cur = []
            i += 1
            continue
        if ch == "&" and i + 1 < n and s[i + 1] == "&":
            segments.append("".join(cur))
            cur = []
            i += 2
            continue
        cur.append(ch)
        i += 1
    segments.append("".join(cur))

    out: list[str] = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        try:
            toks = shlex.split(seg, posix=True)
        except ValueError:
            return []
        if not toks:
            return []
        out.append(seg)
    return out


def fix_command_typo(cmd: str, known_commands: Container[str]) -> str | None:
    if not isinstance(cmd, str):
        return None
    s = cmd.strip()
    if not s:
        return None
    if any(op in s for op in ("|", "&&", "||", ";")):
        return None
    if "$(" in s or "`" in s or ">" in s:
        return None
    try:
        toks = shlex.split(s, posix=True)
    except ValueError:
        return None
    if not toks:
        return None
    first = toks[0]
    try:
        if first in known_commands:
            return None
    except Exception:
        pass

    best_dist = None
    best: list[str] = []
    for cand in known_commands:
        if not isinstance(cand, str):
            continue
        d = _edit_distance(first, cand)
        if d > 2:
            continue
        if best_dist is None or d < best_dist:
            best_dist = d
            best = [cand]
        elif d == best_dist:
            best.append(cand)
    if best_dist is None or best_dist > 2:
        return None
    if len(best) == 1:
        return best[0]
    min_len = min(len(c) for c in best)
    shortest = [c for c in best if len(c) == min_len]
    if len(shortest) == 1:
        return shortest[0]
    return None


def check_flags(cmd: str, args: list[str], help_text: str) -> list[Problem]:
    problems: list[Problem] = []
    valid: set[str] = set(re.findall(r"(?<!\w)(--?[A-Za-z][\w-]*)", help_text or ""))
    for arg in args or []:
        if not isinstance(arg, str):
            continue
        if not arg.startswith("-") or arg == "-":
            continue
        if arg == "--":
            continue
        flag = arg.split("=", 1)[0]
        if flag in valid:
            continue
        suggestion = None
        if valid:
            best = None
            best_d = None
            for v in valid:
                d = _edit_distance(flag, v)
                if best_d is None or d < best_d:
                    best_d = d
                    best = v
            if best is not None and best_d is not None and best_d <= 4:
                suggestion = best
        problems.append(Problem(kind="flag", message=f"unknown flag: {flag}", suggestion=suggestion))
    return problems


def check_paths(args: list[str]) -> list[Problem]:
    problems: list[Problem] = []
    for arg in args or []:
        if not isinstance(arg, str):
            continue
        if arg == "-" or arg.startswith("-"):
            continue
        if "://" in arg:
            continue
        path = os.path.expanduser(arg)
        if os.path.exists(path):
            continue
        problems.append(Problem(kind="path", message=f"path does not exist: {arg}", suggestion=None))
    return problems


_DID_PATTERNS = [
    re.compile(r"did you mean(?: one of)?[: ]*\s*['\"`]?([^\s'\"`]+)['\"`]?", re.IGNORECASE),
    re.compile(r"most similar command is[: ]*\s*['\"`]?([^\s'\"`]+)", re.IGNORECASE),
    re.compile(r"closest match[: ]*\s*['\"`]?([^\s'\"`]+)", re.IGNORECASE),
]


def parse_did_you_mean(stderr: str) -> str | None:
    if not isinstance(stderr, str) or not stderr.strip():
        return None
    for pat in _DID_PATTERNS:
        m = pat.search(stderr)
        if m:
            val = m.group(1).strip().strip("'\"`")
            if val:
                return val
    return None


def _has_rm_rf(cmdline: str) -> bool:
    low = cmdline.lower()
    if "rm -rf" in low or "rm -fr" in low:
        return True
    toks = cmdline.split()
    has_r = False
    has_f = False
    for t in toks:
        tl = t.lower()
        if tl.startswith("-"):
            if "r" in tl:
                has_r = True
            if "f" in tl:
                has_f = True
    rm_present = any(t.lower() == "rm" or t.lower().endswith("/rm") for t in toks)
    if not rm_present:
        # sudo rm ...
        if "rm" not in [t.lower() for t in toks]:
            return False
    if has_r and has_f:
        return True
    return False


def _make_danger_list():
    items = []
    items.append(("rm -rf", "recursive force deletion", "rm -ri",
                  lambda c: _has_rm_rf(c)))
    items.append(("Remove-Item -Recurse -Force", "recursive force deletion (PowerShell)", None,
                  lambda c: ("remove-item" in c.lower() and "-recurse" in c.lower() and "-force" in c.lower())))
    items.append(("dd of=/dev/", "raw disk write via dd", None,
                  lambda c: ("dd" in c.lower().split() or " dd " in (" " + c.lower() + " ")) and "of=/dev/" in c.lower()))
    items.append(("mkfs", "filesystem format", None,
                  lambda c: bool(re.search(r"\bmkfs\b", c.lower()))))
    items.append(("format", "disk format", None,
                  lambda c: bool(re.search(r"\bformat\b", c.lower()))))
    items.append(("chmod -R", "recursive permission change", None,
                  lambda c: "chmod" in c.lower() and ("-R" in c or "-r" in c.lower().split() or " -r" in c.lower())))
    items.append(("> /dev/sd", "write to block device", None,
                  lambda c: bool(re.search(r">\s*/dev/sd", c))))
    items.append(("git push --force", "force push (may overwrite remote history)", "git push --force-with-lease",
                  lambda c: ("git" in c.lower().split() and "push" in c.lower().split()
                             and ("--force" in c.lower() or " -f" in c.lower() or c.lower().strip().endswith(" -f")))))
    items.append(("DROP TABLE", "destructive SQL drop", None,
                  lambda c: "drop table" in c.lower()))
    items.append(("curl … | sh|bash", "pipe remote script to shell", None,
                  lambda c: bool(re.search(r"\bcurl\b.*\|\s*(sh|bash)\b", c, re.IGNORECASE))))
    items.append(("iwr … | iex|sh", "pipe remote script to shell (PowerShell)", None,
                  lambda c: bool(re.search(r"\biwr\b.*\|\s*(iex|sh)\b", c, re.IGNORECASE))))
    items.append(("sudo", "privilege escalation", None,
                  lambda c: c.lstrip().lower().startswith("sudo ") or c.lstrip().lower().startswith("sudo\t")))
    return items


_DANGER = _make_danger_list()


def danger_matches(cmdline: str) -> list[DangerMatch]:
    if not isinstance(cmdline, str):
        return []
    out: list[DangerMatch] = []
    for pattern, detail, safer, pred in _DANGER:
        try:
            if pred(cmdline):
                out.append(DangerMatch(pattern=pattern, detail=detail, safer=safer))
        except Exception:
            continue
    return out