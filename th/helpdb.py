"""Help database: load shipped JSON into SQLite and lookup entries."""

from __future__ import annotations

import json
import sqlite3
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HelpEntry:
    name: str
    summary: str = ""
    description: str = ""
    flags: list[Any] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


def _data_file() -> Path:
    return Path(__file__).resolve().parent / "help_data" / "commands.json"


def _connect_if_needed(conn):
    if isinstance(conn, (str, Path)):
        c = sqlite3.connect(str(conn))
        c.row_factory = sqlite3.Row
        return c, True
    return conn, False


def load_help_db(conn) -> None:
    c, owned = _connect_if_needed(conn)
    try:
        c.execute("CREATE TABLE IF NOT EXISTS help_db (name TEXT PRIMARY KEY, data TEXT NOT NULL)")
        c.commit()
        data = json.loads(_data_file().read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else (data.get("commands") or [])
        for e in entries:
            name = e.get("name") if isinstance(e, dict) else e["name"]
            c.execute(
                "INSERT INTO help_db (name, data) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET data=excluded.data",
                (name, json.dumps(e)),
            )
        c.commit()
    finally:
        if owned:
            c.close()


def _row_value(row, key, idx):
    try:
        return row[key]
    except Exception:
        try:
            return row[idx]
        except Exception:
            return None


def _to_entry(obj) -> HelpEntry:
    if isinstance(obj, HelpEntry):
        return obj
    if isinstance(obj, str):
        d = json.loads(obj)
    elif isinstance(obj, sqlite3.Row):
        data = _row_value(obj, "data", 1)
        if data is not None:
            d = json.loads(data)
        else:
            d = {"name": _row_value(obj, "name", 0)}
    elif isinstance(obj, dict):
        d = obj
    else:
        d = json.loads(str(obj))
    kwargs = {}
    for k in ("name", "summary", "description", "flags", "examples"):
        if k in d and d.get(k) is not None:
            kwargs[k] = d.get(k)
    if "name" not in kwargs:
        kwargs["name"] = str(d.get("name", ""))
    return HelpEntry(**kwargs)


def _load_all(conn) -> list[HelpEntry]:
    c, owned = _connect_if_needed(conn)
    try:
        c.execute("CREATE TABLE IF NOT EXISTS help_db (name TEXT PRIMARY KEY, data TEXT NOT NULL)")
        c.commit()
        rows = c.execute("SELECT name, data FROM help_db").fetchall()
        out = []
        for r in rows:
            try:
                out.append(_to_entry(r))
            except Exception:
                continue
        return out
    finally:
        if owned:
            c.close()


def lookup(conn, query: str) -> list[HelpEntry]:
    q = (query or "").strip()
    all_entries = _load_all(conn)
    if not q:
        return []
    ql = q.lower()
    exact = [e for e in all_entries if e.name.lower() == ql]
    if exact:
        return exact[:5]
    prefix = [e for e in all_entries if e.name.lower().startswith(ql)]
    if prefix:
        return prefix[:5]
    names = [e.name for e in all_entries]
    matches = difflib.get_close_matches(q, names, n=5, cutoff=0.6)
    by_name = {e.name: e for e in all_entries}
    res = [by_name[m] for m in matches if m in by_name]
    return res[:5]