"""Ollama backend tests against a stub HTTP server (http.server in a thread)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from th.config import Config
from th.llm import ask

GOOD_BODY = b'{"response": "ls -la\n"}'
MALFORMED_BODY = b"{ not valid json }"


class _OllamaStub(BaseHTTPRequestHandler):
    """Simulates Ollama's /api/generate endpoint."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        self.server.received_body = self.rfile.read(length)
        self.server.received_path = self.path
        status = getattr(self.server, "status", 200)
        body = getattr(self.server, "body", GOOD_BODY)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence request logs


def _start_stub():
    server = HTTPServer(("127.0.0.1", 0), _OllamaStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_ollama_round_trip_verifies_request_payload():
    server = _start_stub()
    try:
        port = server.server_address[1]
        cfg = Config(
            llm_backend="ollama",
            llm_ollama_url=f"http://127.0.0.1:{port}",
            llm_timeout_s=3.0,
        )
        out = ask(
            "You output exactly one bash command for Linux.",
            "list files",
            config=cfg,
        )
        assert out == "ls -la\n"
        assert server.received_path == "/api/generate"
        payload = json.loads(server.received_body)
        assert payload == {
            "model": "qwen3:4b",
            "prompt": "list files",
            "system": "You output exactly one bash command for Linux.",
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
    finally:
        server.shutdown()
        server.server_close()


def test_ollama_non_2xx_returns_empty():
    server = _start_stub()
    try:
        port = server.server_address[1]
        server.status = 500
        server.body = b"{}"
        cfg = Config(
            llm_backend="ollama",
            llm_ollama_url=f"http://127.0.0.1:{port}",
            llm_timeout_s=3.0,
        )
        assert ask("sys", "prompt", config=cfg) == ""
    finally:
        server.shutdown()
        server.server_close()


def test_ollama_malformed_body_returns_empty():
    server = _start_stub()
    try:
        port = server.server_address[1]
        server.status = 200
        server.body = MALFORMED_BODY
        cfg = Config(
            llm_backend="ollama",
            llm_ollama_url=f"http://127.0.0.1:{port}",
            llm_timeout_s=3.0,
        )
        assert ask("sys", "prompt", config=cfg) == ""
    finally:
        server.shutdown()
        server.server_close()
