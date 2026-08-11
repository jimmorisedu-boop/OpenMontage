import pytest

from lib.gpu_guard import GpuGuardError, ensure_ollama_models_unloaded


class FakeClient:
    def __init__(self, sequences):
        self.sequences = list(sequences)
        self.unloaded = []
    def running_models(self): return self.sequences.pop(0)
    def unload(self, model): self.unloaded.append(model)


def test_guard_unloads_both_configured_models(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD", "1")
    client = FakeClient([[{"name": "openmontage-gpt-oss:20b-32k"}, {"name": "qwen3.5:9b"}], []])
    ensure_ollama_models_unloaded(client)
    assert client.unloaded == ["openmontage-gpt-oss:20b-32k", "qwen3.5:9b"]


def test_guard_fails_closed(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD", "1")
    client = FakeClient([[{"name": "qwen3.5:9b"}], [{"name": "qwen3.5:9b"}]])
    with pytest.raises(GpuGuardError, match="qwen3.5:9b"):
        ensure_ollama_models_unloaded(client)
