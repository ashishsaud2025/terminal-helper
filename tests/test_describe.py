"""Tests for `th describe` (English -> shell command).

The LLM is stubbed everywhere; no live Ollama is consulted.
"""

import hashlib
import json

from th import cli, context


# Recorded English -> command fixtures (>= 10).

RECORDED = [
    ("list all files including hidden ones", "ls -la", "List all files in long format, including hidden files"),
    ("change to the parent directory", "cd ..", "Change to the parent directory"),
    ("create a directory named src", "mkdir src", "Create a new directory called src"),
    ("print the current working directory", "pwd", "Print the current working directory"),
    ("show running processes", "ps aux", "List all running processes"),
    ("show disk usage", "df -h", "Show disk space usage in human-readable form"),
    ("copy file a.txt to b.txt", "cp a.txt b.txt", "Copy a.txt to b.txt"),
    ("move file a.txt to b.txt", "mv a.txt b.txt", "Move a.txt to b.txt"),
    ("remove file foo.txt", "rm foo.txt", "Remove the file foo.txt"),
    ("display the contents of readme.txt", "cat readme.txt", "Display the contents of readme.txt"),
    ("search for TODO in source files", "grep -R TODO .", "Search recursively for TODO in the current directory"),
    ("show the first ten lines of a file", "head -n 10 file.txt", "Print the first 10 lines of file.txt"),
]


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _canned_reply(command: str, explanation: str, confidence: float = 0.9) -> str:
    return json.dumps({"command": command, "explanation": explanation, "confidence": confidence})


def _stub_ask(monkeypatch, tmp_path):
    """Stub llm.ask with canned replies keyed by the hash of the actual prompt.

    The prompt hash is computed here (with TH_DATA_DIR already pointing at
    tmp_path) so it matches the prompt `cmd_describe` builds at runtime.
    """
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    canned = {
        _prompt_hash(cli._describe_prompt(context.build_context("", 0, ""), req)): _canned_reply(cmd, expl)
        for req, cmd, expl in RECORDED
    }

    def ask(system, prompt, **kwargs):
        return canned.get(_prompt_hash(prompt), "")

    monkeypatch.setattr(cli.llm, "ask", ask)


def _run(monkeypatch, tmp_path, *args):
    monkeypatch.setenv("TH_DATA_DIR", str(tmp_path))
    return cli.main(["describe", *args])


def test_describe_single_candidate_rc0(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            {"command": "ls -la", "explanation": "list all files", "confidence": 0.9}
        ),
    )
    rc = _run(monkeypatch, tmp_path, "list", "all", "files")
    assert rc == 0
    assert capsys.readouterr().out == "ls -la\tlist all files\n"


def test_describe_three_candidates_rc4(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            [
                {"command": "ls -la", "explanation": "list all files", "confidence": 0.6},
                {"command": "ls", "explanation": "list files", "confidence": 0.5},
                {"command": "find .", "explanation": "find all files", "confidence": 0.4},
            ]
        ),
    )
    rc = _run(monkeypatch, tmp_path, "list", "files")
    assert rc == 4
    out = capsys.readouterr().out
    assert out == (
        "1) ls -la\tlist all files\n"
        "2) ls\tlist files\n"
        "3) find .\tfind all files\n"
    )


def test_describe_danger_candidate_bang_prefix(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            [
                {"command": "ls -la", "explanation": "list files", "confidence": 0.8},
                {"command": "rm -rf /tmp/foo", "explanation": "nuke dir", "confidence": 0.7},
                {"command": "pwd", "explanation": "show cwd", "confidence": 0.6},
            ]
        ),
    )
    rc = _run(monkeypatch, tmp_path, "something")
    assert rc == 4
    out = capsys.readouterr().out
    assert out == (
        "1) ls -la\tlist files\n"
        "2) ! rm -rf /tmp/foo\tnuke dir\n"
        "3) pwd\tshow cwd\n"
    )


def test_describe_llm_disabled_rc1(monkeypatch, tmp_path, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text("llm.enabled = false\n", encoding="utf-8")
    monkeypatch.setenv("TH_CONFIG_PATH", str(cfg))
    rc = _run(monkeypatch, tmp_path, "list", "files")
    assert rc == 1
    err = capsys.readouterr().err
    assert err == "th: English→command needs the LLM; it is disabled. Try: th help <cmd>.\n"


def test_describe_empty_request_rc1(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, "")
    assert rc == 1
    assert capsys.readouterr().out == ""


def test_describe_llm_garbage_rc1(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.llm, "ask", lambda system, prompt, **kwargs: "not json at all")
    rc = _run(monkeypatch, tmp_path, "list", "files")
    assert rc == 1
    assert capsys.readouterr().out == ""


def test_describe_json_structured(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli.llm,
        "ask",
        lambda system, prompt, **kwargs: json.dumps(
            {"command": "ls -la", "explanation": "list all files", "confidence": 0.9}
        ),
    )
    rc = _run(monkeypatch, tmp_path, "list", "files", "--json")
    assert rc == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj == {"command": "ls -la", "explanation": "list all files", "danger": False}


def test_describe_recorded_prompts_canned_replies(monkeypatch, tmp_path, capsys):
    """>= 10 recorded English->command prompts answered from stubbed canned replies keyed by prompt hash."""
    assert len(RECORDED) >= 10
    _stub_ask(monkeypatch, tmp_path)
    for request, command, explanation in RECORDED:
        rc = _run(monkeypatch, tmp_path, *request.split())
        assert rc == 0, request
        assert capsys.readouterr().out == f"{command}\t{explanation}\n", request
