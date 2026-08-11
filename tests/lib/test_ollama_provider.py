import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import requests

from lib.providers.ollama import OllamaClient, OllamaConnectionError, OllamaResponseError


class Response:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status
        self.text = json.dumps(body)
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)
    def json(self):
        return self.body


def test_offline_client_rejects_remote_endpoint(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    with pytest.raises(OllamaConnectionError, match="non-loopback"):
        OllamaClient("http://ollama.example")


def test_loopback_client_ignores_system_proxy(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"models":[{"name":"local-only:1b"}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)

    try:
        client = OllamaClient(f"http://127.0.0.1:{server.server_port}", timeout_seconds=2)
        assert client.list_models() == {"local-only:1b"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_client_lists_local_models_and_running_models(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    def fake_get(self, url, timeout):
        if url.endswith("/api/tags"):
            return Response({"models": [{"name": "gpt-oss:20b"}]})
        return Response({"models": [{"name": "qwen3.5:9b"}]})
    monkeypatch.setattr(requests.Session, "get", fake_get)
    client = OllamaClient()
    assert client.list_models() == {"gpt-oss:20b"}
    assert client.running_models()[0]["name"] == "qwen3.5:9b"


def test_chat_json_encodes_local_image_and_rejects_bad_json(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    image.write_bytes(b"png")
    calls = []
    def fake_post(self, url, json, timeout):
        calls.append(json)
        return Response({"message": {"content": "not-json"}})
    monkeypatch.setattr(requests.Session, "post", fake_post)
    with pytest.raises(OllamaResponseError, match="malformed"):
        OllamaClient().chat_json(model="qwen3.5:9b", prompt="review", image_paths=[str(image)], schema={"type": "object"}, num_ctx=8192)
    assert calls[0]["messages"][0]["images"]
