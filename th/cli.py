import argparse
import json
import os
import re
import sys
from pathlib import Path

import sqlite3

from th import config
from th import context
from th import db
from th import helpdb
from th import llm
from th.llm.client import _strip_fences
from th import rules
from th import shells_util


def data_dir() -> Path:
    env = os.environ.get("TH_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share" / "th"


def db_path() -> Path:
    return data_dir() / "th.db"


def _tail_file(path: str, n: int = 40) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        with p.open("r", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return ""
    tail = lines[-n:]
    return "".join(tail)


def cmd_log(args) -> int:
    try:
        tail = ""
        if args.stderr_file:
            tail = _tail_file(args.stderr_file)
        rc = db.record_command(
            db_path(),
            cmd=args.cmd,
            cwd=args.cwd,
            exit_code=args.exit,
            stderr_tail=tail,
        )
        _ = rc
        return 0
    except Exception as e:
        sys.stderr.write(f"th: warning: {e}\n")
        return 0


_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences; leave other characters intact."""
    return _ANSI_RE.sub("", text)


def _help_conn():
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS help_db (name TEXT PRIMARY KEY, data TEXT NOT NULL)")
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM help_db").fetchone()[0]
    if count == 0:
        helpdb.load_help_db(conn)
    return conn


def _write(text: str) -> None:
    if os.environ.get("NO_COLOR"):
        text = _strip_ansi(text)
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:  # e.g. cp1252 console on Windows
        sys.stdout.buffer.write(text.encode(sys.stdout.encoding or "utf-8", errors="replace"))


def cmd_help(args) -> int:
    query = " ".join(getattr(args, "query", None) or []).strip()
    conn = _help_conn()
    try:
        if not query:
            entries = sorted(helpdb._load_all(conn), key=lambda e: (e.name or "").lower())
            lines = [f"{e.name} \u2014 {e.summary}" for e in entries]
            _write("\n".join(lines) + ("\n" if lines else ""))
            return 0
        results = helpdb.lookup(conn, query)
        if not results:
            _write("nothing found \u2014 did you mean: ...\n")
            return 1
        if len(results) == 1 and results[0].name.lower() == query.lower():
            e = results[0]
            out = []
            out.append(f"{e.name} \u2014 {e.summary}")
            out.append("")
            if e.description:
                out.append(e.description)
                out.append("")
            if e.flags:
                out.append("Flags:")
                for f in e.flags:
                    flag = f.get("flag") if isinstance(f, dict) else str(f)
                    meaning = f.get("meaning", "") if isinstance(f, dict) else ""
                    out.append(f"  {flag}  {meaning}".rstrip())
                out.append("")
            if e.examples:
                out.append("Examples:")
                for ex in e.examples:
                    out.append(f"  {ex}")
                out.append("")
            _write("\n".join(out).rstrip() + "\n")
            return 0
        out = []
        for e in results:
            out.append(f"{e.name} \u2014 {e.summary}")
            out.append(f"  th help {e.name}")
        _write("\n".join(out) + "\n")
        return 0
    finally:
        conn.close()


# `th fix`: rules first, LLM second

_NO_RECENT_FAILURE = "th: no recent failure"
_LLM_DISABLED = "th: no rule-based fix; LLM disabled"

# `th describe`: English -> command

_DESCRIBE_LLM_DISABLED = "th: English→command needs the LLM; it is disabled. Try: th help <cmd>."
_DESCRIBE_EMPTY = "th: describe needs an English request. Try: th describe <what you want to do>."
_DESCRIBE_NO_USABLE = "th: no usable command from LLM"


def _help_text_for(name: str) -> str:
    """Flatten the help-db entry for ``name`` into plain text (flags included)."""
    try:
        conn = _help_conn()
    except Exception:
        return ""
    try:
        results = helpdb.lookup(conn, name)
        if not results or results[0].name.lower() != name.lower():
            return ""
        e = results[0]
        parts: list[str] = []
        if e.description:
            parts.append(e.description)
        if e.summary:
            parts.append(e.summary)
        for f in e.flags or []:
            flag = f.get("flag") if isinstance(f, dict) else str(f)
            meaning = f.get("meaning", "") if isinstance(f, dict) else ""
            parts.append(f"{flag} {meaning}".strip())
        parts.extend(str(ex) for ex in (e.examples or []))
        return "\n".join(parts)
    except Exception:
        return ""
    finally:
        conn.close()


def _try_rules(cmdline: str, stderr_tail: str, known: list[str]) -> tuple[str, str] | None:
    """Try the rule-based strategies in order: typo, flag, did-you-mean."""
    correction = rules.fix_command_typo(cmdline, known)
    if correction:
        toks = shells_util.split(cmdline) or [cmdline]
        first = toks[0] if toks else cmdline
        rest = toks[1:] if len(toks) > 1 else []
        command = correction if not rest else correction + " " + " ".join(rest)
        return command, f"typo: {first} -> {correction}"

    toks = shells_util.split(cmdline) or []
    if toks:
        first = toks[0]
        help_text = _help_text_for(first)
        for p in rules.check_flags(first, toks[1:], help_text):
            if not p.suggestion:
                continue
            flag = p.message.rsplit("unknown flag: ", 1)[-1] if "unknown flag: " in p.message else ""
            new_toks: list[str] = [first]
            replaced = False
            for t in toks[1:]:
                head = t.split("=", 1)[0]
                if not replaced and head == flag:
                    new_toks.append(p.suggestion + t[len(head):])
                    replaced = True
                else:
                    new_toks.append(t)
            if replaced:
                command = " ".join(new_toks)
                return command, f"unknown flag: {flag}; use {p.suggestion}"

    val = rules.parse_did_you_mean(stderr_tail)
    if val:
        toks = shells_util.split(cmdline) or []
        if len(toks) >= 2:
            command = toks[0] + " " + val
            if len(toks) > 2:
                command += " " + " ".join(toks[2:])
        else:
            command = val
        return command, f"did you mean: {val}"

    return None


def _danger_stderr(command: str) -> int:
    """Print a danger message to stderr and return 3 when command is dangerous."""
    matches = rules.danger_matches(command)
    if not matches:
        return 0
    d = matches[0]
    msg = f"th: danger: {command} - {d.detail}"
    if d.safer:
        msg += f" (safer: {d.safer})"
    sys.stderr.write(msg + "\n")
    return 3


def _emit_suggestion(command: str, reason: str, source: str, as_json: bool) -> int:
    if as_json:
        _write(json.dumps({"command": command, "reason": reason, "source": source}) + "\n")
    else:
        _write(f"{command}\t{reason}\n")
    return 0


def _fix_prompt(bundle: context.ContextBundle, cmdline: str, stderr_tail: str) -> str:
    lines: list[str] = [
        f"Failed command: {cmdline}",
        f"Exit code: {bundle.last_exit_code}",
        f"OS: {bundle.os}",
        f"Shell: {bundle.shell}",
        f"CWD: {bundle.cwd}",
    ]
    if stderr_tail:
        lines.append("Stderr tail:\n" + stderr_tail)
    if bundle.last_commands:
        lines.append("Recent commands: " + ", ".join(bundle.last_commands))
    if bundle.cwd_files:
        lines.append("CWD files: " + ", ".join(bundle.cwd_files))
    lines.append(
        'Suggest exactly one fix as JSON: {"command": "...", "explanation": "...", "confidence": 0.0-1.0}'
    )
    return "\n".join(lines)


def _describe_prompt(bundle: context.ContextBundle, request: str) -> str:
    """Build the user prompt for the English -> command LLM request."""
    lines: list[str] = [
        f"English request: {request}",
        f"OS: {bundle.os}",
        f"Shell: {bundle.shell}",
        f"CWD: {bundle.cwd}",
    ]
    if bundle.last_commands:
        lines.append("Recent commands: " + ", ".join(bundle.last_commands))
    if bundle.cwd_files:
        lines.append("CWD files: " + ", ".join(bundle.cwd_files))
    lines.append(
        "Reply with JSON only. If you are confident in exactly one command, reply with a single object: "
        '{"command": "...", "explanation": "...", "confidence": 0.0-1.0}. '
        "If you are uncertain, reply with a JSON array of up to 3 candidates, "
        'each with keys "command", "explanation", "confidence".'
    )
    return "\n".join(lines)


def _parse_candidates(text: str) -> list[tuple[str, str]]:
    """Parse the LLM reply into (command, explanation) candidates.

    Accepts a single JSON object or a JSON array of up to 3 objects. Each entry
    is validated with llm.validate_command_json. Empty/invalid replies yield [].
    """
    try:
        payload = json.loads(_strip_fences(text))
    except (ValueError, TypeError):
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    candidates: list[tuple[str, str]] = []
    for entry in payload[:3]:
        if not isinstance(entry, dict):
            continue
        reply = llm.validate_command_json(json.dumps(entry))
        if reply is None or not reply.command.strip():
            continue
        candidates.append((reply.command, reply.explanation.strip()))
    return candidates


def cmd_fix(args) -> int:
    cfg = config.load_config()
    failure = db.last_failure(db_path())
    if failure is None:
        sys.stderr.write(_NO_RECENT_FAILURE + "\n")
        return 1

    cmdline = str(failure["cmd"])
    exit_code = failure["exit_code"]
    stderr_tail = failure["stderr_tail"] or ""

    conn = _help_conn()
    try:
        known = [e.name for e in helpdb._load_all(conn) if e.name]
    finally:
        conn.close()

    suggestion = _try_rules(cmdline, stderr_tail, known)
    if suggestion is not None:
        command, reason = suggestion
        if _danger_stderr(command) == 3:
            return 3
        return _emit_suggestion(command, reason, "rules", args.json)

    if not cfg.llm_enabled:
        sys.stderr.write(_LLM_DISABLED + "\n")
        return 1

    bundle = context.build_context(cmdline, exit_code, stderr_tail)
    system = llm.build_system_prompt("bash", "Linux")
    text = llm.ask(system, _fix_prompt(bundle, cmdline, stderr_tail), config=cfg) or ""
    reply = llm.validate_command_json(text)
    if reply is None or not reply.command.strip():
        if args.verbose:
            sys.stderr.write("th: no usable fix from LLM\n")
        return 1
    if _danger_stderr(reply.command) == 3:
        return 3
    return _emit_suggestion(reply.command, reply.explanation.strip() or "llm suggestion", "llm", args.json)


def cmd_describe(args) -> int:
    """Convert an English request into a shell command (or up to 3 candidates)."""
    cfg = config.load_config()

    request = " ".join(getattr(args, "request", None) or []).strip()
    if not request:
        sys.stderr.write(_DESCRIBE_EMPTY + "\n")
        return 1

    if not cfg.llm_enabled:
        sys.stderr.write(_DESCRIBE_LLM_DISABLED + "\n")
        return 1

    bundle = context.build_context("", 0, "")
    system = llm.build_system_prompt("bash", "Linux")
    system += (
        "\n\nIf the request is ambiguous, reply with a JSON array of up to 3 candidates; "
        "otherwise reply with a single JSON object."
    )
    text = llm.ask(system, _describe_prompt(bundle, request), config=cfg) or ""

    candidates = _parse_candidates(text)
    if not candidates:
        sys.stderr.write(_DESCRIBE_NO_USABLE + "\n")
        return 1

    scanned = [(cmd, expl, bool(rules.danger_matches(cmd))) for cmd, expl in candidates]

    if args.json:
        if len(scanned) == 1:
            cmd, expl, danger = scanned[0]
            _write(
                json.dumps({"command": cmd, "explanation": expl, "danger": danger}) + "\n"
            )
            return 3 if danger else 0
        _write(
            json.dumps(
                {
                    "ambiguous": True,
                    "candidates": [
                        {"command": cmd, "explanation": expl, "danger": danger}
                        for cmd, expl, danger in scanned
                    ],
                }
            )
            + "\n"
        )
        return 4

    if len(scanned) == 1:
        cmd, expl, danger = scanned[0]
        _write(f"{'! ' if danger else ''}{cmd}\t{expl}\n")
        return 3 if danger else 0

    lines = [
        f"{i}) {'! ' if danger else ''}{cmd}\t{expl}"
        for i, (cmd, expl, danger) in enumerate(scanned, 1)
    ]
    _write("\n".join(lines) + "\n")
    return 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="th")
    sub = parser.add_subparsers(dest="command")

    log = sub.add_parser("log", help="log a command")
    log.add_argument("--cmd", required=True)
    log.add_argument("--exit", type=int, required=True, dest="exit")
    log.add_argument("--cwd", default=os.getcwd())
    log.add_argument("--stderr-file", dest="stderr_file", default=None)
    log.set_defaults(func=cmd_log)

    help_p = sub.add_parser("help", help="show help for a command")
    help_p.add_argument("query", nargs="*", default=[])
    help_p.set_defaults(func=cmd_help)

    fix_p = sub.add_parser("fix", help="suggest a fix for the last failed command")
    fix_p.add_argument("--json", action="store_true", default=False)
    fix_p.add_argument("--verbose", action="store_true", default=False)
    fix_p.set_defaults(func=cmd_fix)

    describe_p = sub.add_parser("describe", help="convert an English request into a shell command")
    describe_p.add_argument("request", nargs="+", help="English description of the command wanted")
    describe_p.add_argument("--json", action="store_true", default=False)
    describe_p.set_defaults(func=cmd_describe)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
