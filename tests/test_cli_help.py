import re

from th import cli

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _help_args(*query):
    return cli.build_parser().parse_args(["help", *query])


def test_help_exact_prints_full_entry(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.cmd_help(_help_args("git"))
    out = capsys.readouterr().out
    assert rc == 0
    # summary + >= 1 example + >= 1 flag
    assert "Distributed version control system" in out
    assert "Examples:" in out
    assert "git status" in out
    assert "Flags:" in out
    assert "--version" in out


def test_help_prefix_lists_matches(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.cmd_help(_help_args("gi"))
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.splitlines()
    assert any("git" in line for line in lines)


def test_help_fuzzy_typo(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.cmd_help(_help_args("grpe"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "grep" in out


def test_help_unknown_exits_nonzero(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.cmd_help(_help_args("zzznonexistent"))
    out = capsys.readouterr().out
    assert rc == 1
    assert "did you mean" in out.lower()


def test_help_no_args_lists_all(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    rc = cli.cmd_help(_help_args())
    out = capsys.readouterr().out
    assert rc == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) >= 80


def test_help_no_color_strips_ansi(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NO_COLOR", "1")
    rc = cli.cmd_help(_help_args("git"))
    out = capsys.readouterr().out
    assert rc == 0
    assert _ANSI_RE.search(out) is None
