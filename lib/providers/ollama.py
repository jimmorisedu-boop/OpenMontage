"""Small loopback-only client for the local Ollama service."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


class OllamaError(RuntimeError):
    """Base error for local Ollama operations."""


class OllamaConnectionError(OllamaError):
    pass


class OllamaResponseError(OllamaError):
    pass


class OllamaModelMissingError(OllamaError):
    pass


def _is_loopback_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1", "localhost", "::1",
    }


class OllamaClient:
    """Transport-only Ollama client; remote endpoints are rejected offline."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 120.0):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.timeout_seconds = timeout_seconds
        if os.environ.get("OPENMONTAGE_OFFLINE", "1") == "1" and not _is_loopback_url(self.base_url):
            raise OllamaConnectionError(f"Offline mode rejects non-loopback Ollama endpoint: {self.base_url}")
        self._session = requests.Session()
        self._session.trust_env = False

    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = self._session.get(f"{self.base_url}{path}", timeout=self.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise OllamaConnectionError(f"Ollama request failed at {self.base_url}{path}: {exc}") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._session.post(
                f"{self.base_url}{path}", json=payload, timeout=self.timeout_seconds
            )
            if response.status_code == 404 and "model" in response.text.lower():
                raise OllamaModelMissingError(response.text)
            response.raise_for_status()
            return response.json()
        except OllamaModelMissingError:
            raise
        except (requests.RequestException, ValueError) as exc:
            raise OllamaConnectionError(f"Ollama request failed at {self.base_url}{path}: {exc}") from exc

    def health(self) -> bool:
        try:
            self._get("/api/tags")
            return True
        except OllamaError:
            return False

    def list_models(self) -> set[str]:
        return {str(item.get("name") or item.get("model")) for item in self._get("/api/tags").get("models", [])}

    def running_models(self) -> list[dict[str, Any]]:
        return list(self._get("/api/ps").get("models", []))

    def show_model(self, tag: str) -> dict[str, Any]:
        return self._post("/api/show", {"model": tag})

    def model_num_ctx(self, tag: str) -> int | None:
        body = self.show_model(tag)
        parameters = str(body.get("parameters") or "")
        match = re.search(r"(?m)^num_ctx\s+(\d+)\s*$", parameters)
        return int(match.group(1)) if match else None

    def unload(self, model: str) -> None:
        self._post("/api/generate", {"model": model, "keep_alive": 0})

    def chat_json(
        self,
        *,
        model: str,
        prompt: str,
        image_paths: list[str],
        schema: dict[str, Any],
        num_ctx: int,
        keep_alive: int | str = 0,
    ) -> dict[str, Any]:
        images = []
        for raw_path in image_paths:
            path = Path(raw_path).resolve()
            if not path.is_file():
                raise OllamaResponseError(f"Image not found: {path}")
            images.append(base64.b64encode(path.read_bytes()).decode("ascii"))
        body = self._post("/api/chat", {
            "model": model,
            "stream": False,
            "format": schema,
            "keep_alive": keep_alive,
            "options": {"num_ctx": num_ctx},
            "messages": [{"role": "user", "content": prompt, "images": images}],
        })
        content = body.get("message", {}).get("content")
        try:
            value = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(f"Ollama returned malformed JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise OllamaResponseError("Ollama structured response must be an object")
        return value
