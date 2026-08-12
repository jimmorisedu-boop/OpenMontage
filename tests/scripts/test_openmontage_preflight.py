from __future__ import annotations

from pathlib import Path

from scripts.openmontage_preflight import OllamaProbe, run_preflight


def _make_runtime(root: Path) -> None:
    for relative in [
        "runtime/jan/Jan.exe",
        "runtime/python/python.exe",
        "runtime/ollama/ollama.exe",
        "runtime/ffmpeg/ffmpeg.exe",
        "runtime/ffmpeg/ffprobe.exe",
        "runtime/downloader/yt-dlp.exe",
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")


def _ready_ollama(**changes) -> OllamaProbe:
    values = {
        "endpoint": "http://127.0.0.1:11434",
        "running": True,
        "models": frozenset({"openmontage-gpt-oss:20b-32k", "qwen3.5:9b"}),
        "orchestrator_context": 32768,
    }
    values.update(changes)
    return OllamaProbe(**values)


def test_preflight_passes_a_complete_portable_runtime(tmp_path):
    _make_runtime(tmp_path)
    report = run_preflight(
        tmp_path,
        module_probe=lambda python, module: module == "mcp",
        ollama_probe=lambda executable: _ready_ollama(),
        writable_probe=lambda path: True,
    )
    assert report.status == "passed"
    assert all(check.ok for check in report.checks)


def test_preflight_reports_every_missing_local_prerequisite(tmp_path):
    report = run_preflight(
        tmp_path,
        module_probe=lambda python, module: False,
        ollama_probe=lambda executable: _ready_ollama(running=False, models=frozenset()),
        writable_probe=lambda path: False,
    )
    failed = {check.id for check in report.checks if not check.ok}
    assert failed == {
        "jan", "python", "mcp_sdk", "ollama_binary", "ollama_service",
        "ffmpeg", "ffprobe", "downloader", "models", "context", "runtime_writable",
    }
    assert all(check.remedy for check in report.checks if not check.ok)


def test_preflight_rejects_non_loopback_ollama(tmp_path):
    _make_runtime(tmp_path)
    report = run_preflight(
        tmp_path,
        module_probe=lambda python, module: True,
        ollama_probe=lambda executable: _ready_ollama(endpoint="http://192.168.1.5:11434"),
        writable_probe=lambda path: True,
    )
    endpoint = next(check for check in report.checks if check.id == "ollama_endpoint")
    assert not endpoint.ok
    assert "loopback" in endpoint.remedy.lower()


def test_preflight_rejects_wrong_context_and_missing_hidden_model(tmp_path):
    _make_runtime(tmp_path)
    report = run_preflight(
        tmp_path,
        module_probe=lambda python, module: True,
        ollama_probe=lambda executable: _ready_ollama(
            models=frozenset({"openmontage-gpt-oss:20b-32k"}),
            orchestrator_context=8192,
        ),
        writable_probe=lambda path: True,
    )
    failed = {check.id for check in report.checks if not check.ok}
    assert {"models", "context"}.issubset(failed)
