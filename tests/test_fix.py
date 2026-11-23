"""Tests for `th fix` (rules first, LLM second)."""

import json

from th import cli, db, rules


def _seed(tmp_path, monkeypatch, cmd, exit_code, stderr_tail=""):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    p = tmp_path / "th.db"
    db.init_db(p)
    db.record_command(p, cmd=cmd, cwd=str(tmp_path), exit_code=exit_code, stderr_tail=stderr_tail)
    return p


def _run(tmp_path, monkeypatch, *extra):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    return cli.main(["fix", *extra])


def test_fix_rules_typo_hit(tmp_path, monkeypatch, capsys):
    _seed(tmp_path, monkeypatch, "gti status", 127, "gti: command not found")
    rc = _run(tmp_path, monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "git status\ttypo: gti -> git\n"


def test_fix_rules_did_you_mean(tmp_path, monkeypatch, capsys):
    stderr = "git: 'staus' is not a git command. The most similar command is status"
    _seed(tmp_path, monkeypatch, "git staus", 1, stderr)
    rc = _run(tmp_path, monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "git status\tdid you mean: status\n"


def test_fix_rules_miss_llm_disabled(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text("llm.enabled = false\n", encoding="utf-8")
    monkeypatch.setenv("TH_CONFIG_PATH", str(cfg))
    _seed(tmp_path, monkeypatch, "zzzzyyy foo", 127, "zzzzyyy: command not found")
    rc = _run(tmp_path, monkeypatch)
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "th: no rule-based fix; LLM disabled" in captured.err


def test_fix_rules_miss_llm_stub_valid(tmp_path, monkeypatch, capsys):
    _seed(tmp_path, monkeypatch, "showfiles docs", 127, "showfiles: command not found")
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            {"command": "ls -la", "explanation": "list all files including hidden", "confidence": 0.9}
        ),
    )
    rc = _run(tmp_path, monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert out == "ls -la\tlist all files including hidden\n"


def test_fix_rules_miss_llm_stub_valid_json(tmp_path, monkeypatch, capsys):
    _seed(tmp_path, monkeypatch, "showfiles docs", 127, "showfiles: command not found")
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            {"command": "ls -la", "explanation": "list all files including hidden", "confidence": 0.9}
        ),
    )
    rc = _run(tmp_path, monkeypatch, "--json")
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj == {"command": "ls -la", "reason": "list all files including hidden", "source": "llm"}


def test_fix_rules_miss_llm_garbage(tmp_path, monkeypatch, capsys):
    _seed(tmp_path, monkeypatch, "showfiles docs", 127, "showfiles: command not found")
    monkeypatch.setattr(cli.llm, "ask", lambda system, prompt, **kwargs: "{broken json")
    rc = _run(tmp_path, monkeypatch)
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_fix_llm_danger_exit3(tmp_path, monkeypatch, capsys):
    _seed(tmp_path, monkeypatch, "remove everything", 1, "")
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            {"command": "rm -rf /", "explanation": "nuke it", "confidence": 1.0}
        ),
    )
    rc = _run(tmp_path, monkeypatch)
    assert rc == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "danger" in captured.err.lower()
    assert "rm -rf" in captured.err


def test_fix_empty_db_no_recent_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    # no th.db at all
    rc = _run(tmp_path, monkeypatch)
    assert rc == 1
    assert capsys.readouterr().out == ""
