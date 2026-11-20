import argparse
import os
import sys
from pathlib import Path

from th import db


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="th")
    sub = parser.add_subparsers(dest="command")

    log = sub.add_parser("log", help="log a command")
    log.add_argument("--cmd", required=True)
    log.add_argument("--exit", type=int, required=True, dest="exit")
    log.add_argument("--cwd", default=os.getcwd())
    log.add_argument("--stderr-file", dest="stderr_file", default=None)
    log.set_defaults(func=cmd_log)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args))
