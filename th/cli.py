import argparse
import os
import sys
from pathlib import Path

import sqlite3

from th import db
from th import helpdb


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


def cmd_help(args) -> int:
    query = " ".join(getattr(args, "query", None) or []).strip()
    conn = _help_conn()
    try:
        if not query:
            entries = sorted(helpdb._load_all(conn), key=lambda e: (e.name or "").lower())
            lines = [f"{e.name} \u2014 {e.summary}" for e in entries]
            sys.stdout.write("\n".join(lines) + ("\n" if lines else ""))
            return 0
        results = helpdb.lookup(conn, query)
        if not results:
            sys.stdout.write("nothing found \u2014 did you mean: ...\n")
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
            sys.stdout.write("\n".join(out).rstrip() + "\n")
            return 0
        out = []
        for e in results:
            out.append(f"{e.name} \u2014 {e.summary}")
            out.append(f"  th help {e.name}")
        sys.stdout.write("\n".join(out) + "\n")
        return 0
    finally:
        conn.close()


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

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))
