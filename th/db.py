import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    cmd TEXT NOT NULL,
    cwd TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    stderr_tail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS help_cache (
    command TEXT PRIMARY KEY,
    help_text TEXT NOT NULL,
    ts REAL NOT NULL
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def record_command(db_path: Path, *, cmd: str, cwd: str, exit_code: int, stderr_tail: str = "") -> int:
    trimmed = (cmd or "").strip()
    if not trimmed:
        return -1
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "INSERT INTO commands (ts, cmd, cwd, exit_code, stderr_tail) VALUES (?, ?, ?, ?, ?)",
            (time.time(), trimmed, cwd, int(exit_code), stderr_tail or ""),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def recent_commands(db_path: Path, limit: int) -> list[sqlite3.Row]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "SELECT * FROM commands ORDER BY ts DESC, id DESC LIMIT ?", (int(limit),)
        )
        return cur.fetchall()
    finally:
        conn.close()


def last_failure(db_path: Path) -> "sqlite3.Row | None":
    db_path = Path(db_path)
    if not db_path.exists():
        return None
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA)
        cur = conn.execute(
            "SELECT * FROM commands WHERE exit_code != 0 ORDER BY ts DESC, id DESC LIMIT 1"
        )
        return cur.fetchone()
    finally:
        conn.close()
