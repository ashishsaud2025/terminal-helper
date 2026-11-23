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
