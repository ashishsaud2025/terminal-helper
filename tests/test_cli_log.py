import os

from th import cli, db


def test_log_records(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["log", "--cmd", "gti status", "--exit", "2", "--cwd", str(tmp_path)])
    assert rc == 0
    p = tmp_path / "th.db"
    rows = db.recent_commands(p, 10)
    assert len(rows) == 1
    assert rows[0]["cmd"] == "gti status"
    assert rows[0]["exit_code"] == 2


def test_log_never_fails_loudly(tmp_path, monkeypatch, capsys):
    # db path under a read-only dir
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    monkeypatch.setenv("TH_DATA_DIR", str(ro / "nested"))
    try:
        rc = cli.main(["log", "--cmd", "x", "--exit", "0"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower() or "th:" in captured.err.lower()
        assert "Traceback" not in captured.err
    finally:
        ro.chmod(0o755)


def test_log_empty_cmd_is_silent_success(tmp_path, monkeypatch):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["log", "--cmd", "", "--exit", "1"])
    assert rc == 0
    rows = db.recent_commands(tmp_path / "th.db", 10)
    assert rows == []


def test_log_stderr_file_tail(tmp_path, monkeypatch):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    sf = tmp_path / "err.txt"
    sf.write_text("\n".join(f"line{i}" for i in range(50)))
    rc = cli.main(["log", "--cmd", "x", "--exit", "1", "--stderr-file", str(sf)])
    assert rc == 0
    rows = db.recent_commands(tmp_path / "th.db", 10)
    tail = rows[0]["stderr_tail"]
    assert "line49" in tail
    assert tail.count("\n") >= 39
