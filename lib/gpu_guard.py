"""Ensure Ollama releases the single 16 GB GPU before another local GPU tool."""

from __future__ import annotations

import os

from lib.providers.ollama import OllamaClient, OllamaError


class GpuGuardError(RuntimeError):
    pass


def ensure_ollama_models_unloaded(client: OllamaClient | None = None) -> None:
    if os.environ.get("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD") != "1":
        return
    ollama = client or OllamaClient(timeout_seconds=15)
    configured = {
        os.environ.get("OPENMONTAGE_ORCHESTRATOR_MODEL", "openmontage-gpt-oss:20b-32k"),
        os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b"),
    }
    try:
        running = {str(item.get("name") or item.get("model")) for item in ollama.running_models()}
        for model in sorted(configured & running):
            ollama.unload(model)
        remaining = {str(item.get("name") or item.get("model")) for item in ollama.running_models()}
    except OllamaError as exc:
        raise GpuGuardError(f"Cannot verify Ollama GPU state: {exc}") from exc
    blocked = sorted(configured & remaining)
    if blocked:
        raise GpuGuardError(f"Local GPU tool blocked; Ollama models remain loaded: {', '.join(blocked)}")
