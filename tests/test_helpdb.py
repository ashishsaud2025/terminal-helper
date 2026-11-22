import json
import sqlite3
from pathlib import Path

from th import helpdb


def test_load_creates_table(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "help_db" in names
    conn.close()


def test_load_upserts_entries(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    rows = conn.execute("SELECT COUNT(*) FROM help_db").fetchone()[0]
    assert rows >= 30
    conn.close()


def test_lookup_exact(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    res = helpdb.lookup(conn, "git")
    assert len(res) == 1
    assert res[0].name == "git"
    conn.close()


def test_lookup_prefix(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    res = helpdb.lookup(conn, "gi")
    names = [e.name for e in res]
    assert "git" in names
    conn.close()


def test_lookup_fuzzy(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    res = helpdb.lookup(conn, "grpe")
    names = [e.name for e in res]
    assert "grep" in names
    conn.close()


def test_lookup_cap_5(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    res = helpdb.lookup(conn, "")
    assert res == []
    conn.close()


def test_entry_shape():
    import json
    from pathlib import Path
    data = json.loads(Path("th/help_data/commands.json").read_text())
    assert isinstance(data, list)
    assert len(data) >= 80
    for e in data:
        assert set(["name", "summary", "description", "flags", "examples"]) <= set(e.keys())
        assert isinstance(e["examples"], list) and len(e["examples"]) >= 1
        # examples parse with shlex
        import shlex
        for ex in e["examples"]:
            shlex.split(ex)


def test_helpdb_empty_query_returns_list(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    helpdb.load_help_db(conn)
    assert helpdb.lookup(conn, "   ") == []
    conn.close()