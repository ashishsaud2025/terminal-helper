"""Validator + dispatcher tests for th.llm (no network)."""

import json
import urllib.error

import pytest

from th.config import Config
from th.llm import ask, build_system_prompt
from th.llm.client import CommandReply, validate_command_json
import th.llm.cli_agent as cli_agent
import th.llm.ollama as ollama


def test_validator_valid():
    reply = validate_command_json(
        '{"command": "ls -la", "explanation": "list files", "confidence": 0.9}'
    )
    assert reply == CommandReply(command="ls -la", explanation="list files", confidence=0.9)


def test_validator_missing_keys():
    for text in (
        '{"command": "ls", "confidence": 0.5}',
        '{"explanation": "x", "confidence": 0.5}',
        '{"command": "ls", "explanation": "x"}',
        "{}",
    ):
        assert validate_command_json(text) is None


def test_validator_bad_confidence():
    base = '{"command": "ls", "explanation": "x", "confidence": %s}'
    for value in (1.5, -0.1, "high", True, None):
        assert validate_command_json(base % json.dumps(value)) is None


def test_validator_command_too_long_is_invalid():
    too_long = "x" * 501
    assert (
        validate_command_json(
            json.dumps({"command": too_long, "explanation": "x", "confidence": 0.5})
        )
        is None
    )
    exactly = "x" * 500
    reply = validate_command_json(
        json.dumps({"command": exactly, "explanation": "x", "confidence": 0.5})
    )
    assert reply is not None and reply.command == exactly


def test_validator_empty_and_wrong_types():
    assert validate_command_json("") is None
    assert validate_command_json("not json at all") is None
    assert validate_command_json('{"command": 42, "explanation": "x", "confidence": 0.5}') is None
    assert validate_command_json('{"command": "ls", "explanation": 7, "confidence": 0.5}') is None
    assert validate_command_json('["command", "explanation", "confidence"]') is None


def test_validator_fenced_json_stripped():
    text = "```json\n{\"command\": \"ls\", \"explanation\": \"list\", \"confidence\": 0.8}\n```"
    reply = validate_command_json(text)
    assert reply == CommandReply(command="ls", explanation="list", confidence=0.8)


def test_validator_fenced_no_language_stripped():
    text = "```\n{\"command\": \"pwd\", \"explanation\": \"x\", \"confidence\": 0.5}\n```"
    reply = validate_command_json(text)
    assert reply == CommandReply(command="pwd", explanation="x", confidence=0.5)


def test_validator_extra_keys_tolerated():
    text = '{"command": "ls", "explanation": "x", "confidence": 0.5, "extra": {"nested": 1}}'
    reply = validate_command_json(text)
    assert reply == CommandReply(command="ls", explanation="x", confidence=0.5)


def test_validator_rm_rf_is_valid():
    # The validator only checks the JSON shape; danger screening runs separately.
    reply = validate_command_json(
        '{"command": "rm -rf /", "explanation": "dangerous", "confidence": 1.0}'
    )
    assert reply is not None
    assert reply.command == "rm -rf /"


def _make_cfg(**overrides):
    data = dict(
        llm_enabled=True,
        llm_backend="ollama",
        llm_model="qwen3:4b",
        llm_ollama_url="http://127.0.0.1:11434",
        llm_timeout_s=3.0,
    )
    data.update(overrides)
    return Config(**data)


def test_disabled_returns_empty_and_no_http(monkeypatch):
    calls = []

    def fake(url, payload, timeout):
        calls.append((url, payload, timeout))
        return '{"response": "unreachable"}'

    monkeypatch.setattr(ollama, "_post_json", fake)
    cfg = _make_cfg(llm_enabled=False)
    assert ask("sys", "prompt", config=cfg) == ""
    assert calls == []


def test_non_2xx_returns_empty(monkeypatch):
    def fake(url, payload, timeout):
        raise urllib.error.HTTPError("http://x", 500, "boom", {}, None)

    monkeypatch.setattr(ollama, "_post_json", fake)
    cfg = _make_cfg()
    assert ask("sys", "prompt", config=cfg) == ""


def test_connection_refused_returns_empty(monkeypatch):
    def fake(url, payload, timeout):
        return None

    monkeypatch.setattr(ollama, "_post_json", fake)
    cfg = _make_cfg()
    assert ask("sys", "prompt", config=cfg) == ""


def test_timeout_returns_empty(monkeypatch):
    seen = {}

    def fake(url, payload, timeout):
        seen["timeout"] = timeout
        return None

    monkeypatch.setattr(ollama, "_post_json", fake)
    cfg = _make_cfg(llm_timeout_s=0.5)
    assert ask("sys", "prompt", config=cfg) == ""
    assert seen["timeout"] == 0.5


def test_malformed_body_returns_empty(monkeypatch):
    monkeypatch.setattr(ollama, "_post_json", lambda url, payload, timeout: "{ not json")
    cfg = _make_cfg()
    assert ask("sys", "prompt", config=cfg) == ""


def test_valid_stub_returns_raw_string(monkeypatch):
    sent = {}

    def fake(url, payload, timeout):
        sent["url"] = url
        sent["payload"] = payload
        sent["timeout"] = timeout
        return '{"response": "ls -la"}'

    monkeypatch.setattr(ollama, "_post_json", fake)
    cfg = _make_cfg()
    assert ask("sys", "prompt", config=cfg) == "ls -la"
    assert sent["url"] == "http://127.0.0.1:11434/api/generate"
    assert sent["payload"] == {
        "model": "qwen3:4b",
        "prompt": "prompt",
        "system": "sys",
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    assert sent["timeout"] == 3.0


def test_unknown_backend_returns_empty():
    cfg = _make_cfg(llm_backend="no-such-backend")
    assert ask("sys", "prompt", config=cfg) == ""


class _CliProc:
    returncode = 0
    stdout = "ls -la\n"


def test_cli_agent_sends_prompt_only(monkeypatch):
    seen = {}

    def fake_run(args, capture_output=True, text=True, timeout=3.0):
        seen["args"] = args
        return _CliProc()

    monkeypatch.setattr("th.llm.cli_agent.subprocess.run", fake_run)
    cfg = _make_cfg(llm_backend="cli_agent")
    out = cli_agent.ask("system prompt here", "list files", config=cfg)
    assert out == "ls -la\n"
    assert seen["args"] == ["claude", "-p", "--output-format", "text", "list files"]


def test_cli_agent_nonzero_returncode_returns_empty(monkeypatch):
    class _BadProc:
        returncode = 1
        stdout = ""

    def fake_run(args, capture_output=True, text=True, timeout=3.0):
        return _BadProc()

    monkeypatch.setattr("th.llm.cli_agent.subprocess.run", fake_run)
    cfg = _make_cfg(llm_backend="cli_agent")
    assert cli_agent.ask("system", "prompt", config=cfg) == ""


def test_build_system_prompt_has_instruction_line():
    out = build_system_prompt("bash", "Linux")
    assert (
        "You output exactly one bash command for Linux. No markdown. "
        "If unsure, return an empty command."
    ) in out


def test_build_system_prompt_includes_few_shot():
    out = build_system_prompt("bash", "Linux")
    assert "ls -la" in out
    assert "mkdir src" in out
