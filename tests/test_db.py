import sqlite3

from th import db


def test_init_creates_tables(tmp_path):
    db.init_db(tmp_path / "t.db")
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"commands", "suggestions", "help_cache"} <= names


def test_record_and_recent_roundtrip(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    db.record_command(p, cmd="ls", cwd="/", exit_code=0)
    db.record_command(p, cmd="pwd", cwd="/", exit_code=0)
    db.record_command(p, cmd="false", cwd="/", exit_code=1)
    rows = db.recent_commands(p, 2)
    assert len(rows) == 2
    assert rows[0]["cmd"] == "false"
    assert rows[1]["cmd"] == "pwd"


def test_last_failure_returns_only_nonzero(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    db.record_command(p, cmd="ok", cwd="/", exit_code=0)
    db.record_command(p, cmd="bad", cwd="/", exit_code=2)
    db.record_command(p, cmd="ok2", cwd="/", exit_code=0)
    r = db.last_failure(p)
    assert r is not None
    assert r["cmd"] == "bad"
    assert r["exit_code"] == 2


def test_last_failure_empty_db(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    assert db.last_failure(p) is None


def test_db_path_created_with_parents(tmp_path):
    p = tmp_path / "a" / "b" / "t.db"
    db.init_db(p)
    assert p.exists()


def test_logging_empty_command_skipped(tmp_path):
    p = tmp_path / "t.db"
    db.init_db(p)
    rc = db.record_command(p, cmd="   ", cwd="/", exit_code=1)
    assert rc == -1
    rows = db.recent_commands(p, 10)
    assert rows == []
