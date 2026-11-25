"""Tests for `th check` pre-flight and rules.preflight."""

import sqlite3
import time
from pathlib import Path

from th import cli, db, rules

KNOWN = {
    "git", "grep", "ls", "cat", "cp", "mv", "rm", "find", "tar",
    "chmod", "chown", "curl", "ssh", "python3", "mkdir", "touch",
}


def _seed_failure(tmp_path, monkeypatch, cmd, exit_code, stderr_tail=""):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    p = tmp_path / "th.db"
    db.init_db(p)
    db.record_command(p, cmd=cmd, cwd=str(tmp_path), exit_code=exit_code, stderr_tail=stderr_tail)
    return p


def _insert_suggestion(p, input_cmd, accepted):
    conn = sqlite3.connect(str(p))
    conn.execute(
        "INSERT INTO suggestions (ts, kind, input, output, accepted) "
        "VALUES (?, ?, ?, ?, ?)",
        (time.time(), "rules", input_cmd, "some fix", int(accepted)),
    )
    conn.commit()
    conn.close()


def test_typo_warning():
    probs = rules.preflight(
        "grpe foo", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    )
    assert len(probs) == 1
    assert probs[0].kind == "typo"
    assert probs[0].message == "grpe -> grep"
    assert probs[0].suggestion == "grep"


def test_known_command_no_typo():
    assert rules.preflight(
        "git status", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    ) == []


def test_nonexistent_path(tmp_path):
    missing = str(tmp_path / "no-such-file.txt").replace("\\", "/")
    probs = rules.preflight(
        f"cat {missing}", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    )
    paths = [p for p in probs if p.kind == "path"]
    assert len(paths) == 1
    assert missing in paths[0].message


def test_existing_path_not_flagged(tmp_path):
    existing = tmp_path / "here.txt"
    existing.write_text("x")
    probs = rules.preflight(
        f"cat {existing}".replace("\\", "/"), known_commands=KNOWN,
        db_path=Path("does-not-exist.db"), history=[], help_texts={},
    )
    assert not any(p.kind == "path" for p in probs)


def test_unknown_flag_cached_help():
    help_texts = {"git": "--version  show version\n-C <path>  run elsewhere\n"}
    probs = rules.preflight(
        "git --versio", known_commands={"git"}, db_path=Path("does-not-exist.db"),
        history=[], help_texts=help_texts,
    )
    flags = [p for p in probs if p.kind == "flag"]
    assert len(flags) == 1
    assert flags[0].message == "unknown flag: --versio"
    assert flags[0].suggestion == "--version"
    # valid flag not flagged
    assert rules.preflight(
        "git --version", known_commands={"git"}, db_path=Path("does-not-exist.db"),
        history=[], help_texts=help_texts,
    ) == []


def test_flag_check_skipped_on_cache_miss():
    probs = rules.preflight(
        "git --versio", known_commands={"git"}, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    )
    assert not any(p.kind == "flag" for p in probs)


def test_history_recall_warns(tmp_path, monkeypatch):
    p = _seed_failure(tmp_path, monkeypatch, "no-such-cmd x", 1)
    probs = rules.preflight(
        "no-such-cmd x", known_commands=KNOWN, db_path=p,
        history=[rules.normalize_cmd("no-such-cmd x")], help_texts={},
    )
    assert any(problem.kind == "history" for problem in probs)


def test_history_recall_accepted_fix_suppresses(tmp_path, monkeypatch):
    p = _seed_failure(tmp_path, monkeypatch, "no-such-cmd x", 1)
    _insert_suggestion(p, "no-such-cmd x", accepted=True)
    probs = rules.preflight(
        "no-such-cmd x", known_commands=KNOWN, db_path=p,
        history=[rules.normalize_cmd("no-such-cmd x")], help_texts={},
    )
    assert not any(problem.kind == "history" for problem in probs)


def test_history_recall_unaccepted_fix_still_warns(tmp_path, monkeypatch):
    p = _seed_failure(tmp_path, monkeypatch, "no-such-cmd x", 1)
    _insert_suggestion(p, "no-such-cmd x", accepted=False)
    probs = rules.preflight(
        "no-such-cmd x", known_commands=KNOWN, db_path=p,
        history=[rules.normalize_cmd("no-such-cmd x")], help_texts={},
    )
    assert any(problem.kind == "history" for problem in probs)


def test_danger_pattern():
    probs = rules.preflight(
        "git push --force origin main", known_commands={"git"},
        db_path=Path("does-not-exist.db"), history=[], help_texts={},
    )
    dangers = [p for p in probs if p.kind == "danger"]
    assert len(dangers) == 1
    assert dangers[0].suggestion == "git push --force-with-lease"
    assert rules.danger_matches("rm -rf /tmp/x")  # direct danger scan


def test_compound_line_scoped_per_segment():
    probs = rules.preflight(
        "gti status | grp foo", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    )
    typos = [p for p in probs if p.kind == "typo"]
    assert {p.message for p in typos} == {"gti -> git", "grp -> grep"}


def test_opaque_pipeline_returns_empty():
    assert rules.preflight(
        "echo $(whoami)", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
        history=[], help_texts={},
    ) == []
    assert rules.preflight("cat < in.txt", known_commands=KNOWN,
                           db_path=Path("does-not-exist.db"), history=[], help_texts={}) == []


def test_empty_line_clean():
    assert rules.preflight("", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
                           history=[], help_texts={}) == []
    assert rules.preflight("   ", known_commands=KNOWN, db_path=Path("does-not-exist.db"),
                           history=[], help_texts={}) == []


# `th check` CLI

def test_check_typo_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["check", "--", "grpe", "foo"])
    assert rc == 10
    out = capsys.readouterr().out
    assert "typo: grpe -> grep" in out


def test_check_clean_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["check", "--", "ls"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_check_path_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    missing = str(tmp_path / "nope.txt").replace("\\", "/")
    rc = cli.main(["check", "--", "cat", missing])
    assert rc == 10
    out = capsys.readouterr().out
    assert "path does not exist" in out
    assert missing in out


def test_check_unknown_flag_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["check", "--", "git", "--versio"])
    assert rc == 10
    out = capsys.readouterr().out
    assert "flag: unknown flag: --versio" in out


def test_check_history_recall_via_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    _seed_failure(tmp_path, monkeypatch, "no-such-cmd x", 1)
    rc = cli.main(["check", "--", "no-such-cmd", "x"])
    assert rc == 10
    out = capsys.readouterr().out
    assert "history" in out


def test_check_history_suppressed_after_accepted_fix(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    p = _seed_failure(tmp_path, monkeypatch, "no-such-cmd x", 1)
    _insert_suggestion(p, "no-such-cmd x", accepted=True)
    rc = cli.main(["check", "--", "no-such-cmd", "x"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_check_empty_line_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.main(["check", "--", ""])
    assert rc == 0
    assert capsys.readouterr().out == ""
