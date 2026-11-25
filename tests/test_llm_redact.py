"""LLM prompt redaction: secrets must never be sent to non-ollama backends."""

from th.config import Config
from th import llm


def _captured_backend(monkeypatch, backend_module):
    captured = {}

    def fake(system, prompt, *, stream=False, config):
        captured["system"] = system
        captured["prompt"] = prompt
        return '{"command": "ls", "explanation": "list files", "confidence": 0.9}'

    monkeypatch.setattr(backend_module, "ask", fake)
    return captured


def test_non_ollama_backend_redacts_prompt(monkeypatch):
    captured = _captured_backend(monkeypatch, llm.openai_compat)
    text = llm.ask(
        "system prompt",
        "connect to the DB with password=hunter2 and token=sk-1234567890abcdefghij",
        config=Config(llm_backend="openai_compat", llm_enabled=True),
    )
    assert text  # backend still answered
    assert "hunter2" not in captured["prompt"]
    assert "sk-1234567890abcdefghij" not in captured["prompt"]
    assert "[REDACTED]" in captured["prompt"]


def test_ollama_backend_is_exempt(monkeypatch):
    captured = _captured_backend(monkeypatch, llm.ollama)
    secret = "sk-1234567890abcdefghij"
    llm.ask("system prompt", f"token={secret}", config=Config(llm_backend="ollama", llm_enabled=True))
    assert secret in captured["prompt"]
    assert "[REDACTED]" not in captured["prompt"]
