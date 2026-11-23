"""Tests for th/context.py: ContextBundle + build_context."""

from dataclasses import is_dataclass

from th import context, db


def _setup(tmp_path, monkeypatch, cmds):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/bash")
    p = tmp_path / "th.db"
    db.init_db(p)
    for cmd, ec in cmds:
        db.record_command(p, cmd=cmd, cwd=str(tmp_path), exit_code=ec, stderr_tail="")
    return p


def test_context_bundle_is_dataclass():
    assert is_dataclass(context.ContextBundle)
    assert set(context.ContextBundle.__dataclass_fields__) == {
        "os", "shell", "cwd", "last_commands", "cwd_files", "last_exit_code",
    }


def test_build_context_returns_correct_fields(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [("gti status", 127), ("ls -la", 0)])

    from types import SimpleNamespace
    fake_os = SimpleNamespace(
        getcwd=lambda: str(tmp_path),
        listdir=lambda d: ["zeta.txt", "alpha.txt", "mid.txt"],
        environ=__import__("os").environ,
    )
    monkeypatch.setattr(context, "os", fake_os)
    monkeypatch.setattr(context.platform, "system", lambda: "Linux")

    bundle = context.build_context("gti status", 127, "gti: not found")

    assert bundle.os == "Linux"
    assert bundle.shell == "/bin/bash"
    assert bundle.cwd == str(tmp_path)
    assert bundle.last_commands == ["ls -la", "gti status"]
    assert bundle.cwd_files == ["alpha.txt", "mid.txt", "zeta.txt"]
    assert bundle.last_exit_code == 127


def test_build_context_cwd_files_names_only_capped_at_50(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [])

    from types import SimpleNamespace
    names = [f"file{i:03d}.txt" for i in range(60)]
    fake_os = SimpleNamespace(
        getcwd=lambda: str(tmp_path),
        listdir=lambda d: list(names),
        environ=__import__("os").environ,
    )
    monkeypatch.setattr(context, "os", fake_os)
    monkeypatch.setattr(context.platform, "system", lambda: "Linux")

    bundle = context.build_context("x", None, "")

    assert bundle.last_exit_code is None
    assert bundle.last_commands == []
    assert len(bundle.cwd_files) == 50
    assert bundle.cwd_files == sorted(names)[:50]
    # names only: nothing looks like file contents
    assert all(isinstance(n, str) and "\n" not in n for n in bundle.cwd_files)


def test_build_context_last_commands_limit_5(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [(f"cmd{i}", 1) for i in range(8)])

    from types import SimpleNamespace
    fake_os = SimpleNamespace(
        getcwd=lambda: str(tmp_path),
        listdir=lambda d: [],
        environ=__import__("os").environ,
    )
    monkeypatch.setattr(context, "os", fake_os)
    monkeypatch.setattr(context.platform, "system", lambda: "Linux")

    bundle = context.build_context("x", 1, "")
    assert bundle.last_commands == ["cmd7", "cmd6", "cmd5", "cmd4", "cmd3"]
    assert len(bundle.last_commands) == 5
