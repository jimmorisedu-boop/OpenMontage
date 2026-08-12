"""Actionable preflight for the repository-local OpenMontage chat runtime."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from lib.network_policy import is_loopback_url
from lib.providers.ollama import OllamaClient, OllamaError
from scripts.portable_runtime_layout import PortableLayout, resolve_layout


REQUIRED_MODELS = frozenset({"openmontage-gpt-oss:20b-32k", "qwen3.5:9b"})


@dataclass(frozen=True)
class OllamaProbe:
    endpoint: str
    running: bool
    models: frozenset[str]
    orchestrator_context: int | None


@dataclass(frozen=True)
class PreflightCheck:
    id: str
    ok: bool
    message: str
    remedy: str


@dataclass(frozen=True)
class PreflightReport:
    status: str
    checks: tuple[PreflightCheck, ...]


def _module_probe(python: Path, module: str) -> bool:
    if not python.is_file():
        return False
    try:
        result = subprocess.run(
            [str(python), "-c", f"import {module}"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _ollama_probe(executable: Path) -> OllamaProbe:
    endpoint = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    if not executable.is_file():
        return OllamaProbe(endpoint, False, frozenset(), None)
    try:
        client = OllamaClient(base_url=endpoint, timeout_seconds=5)
        running = client.health()
        models = frozenset(client.list_models()) if running else frozenset()
        context = (
            client.model_num_ctx("openmontage-gpt-oss:20b-32k")
            if running and "openmontage-gpt-oss:20b-32k" in models
            else None
        )
        return OllamaProbe(endpoint, running, models, context)
    except OllamaError:
        return OllamaProbe(endpoint, False, frozenset(), None)


def _writable_probe(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix="preflight-", delete=True):
            pass
        return True
    except OSError:
        return False


def _file_check(identifier: str, label: str, path: Path) -> PreflightCheck:
    exists = path.is_file()
    return PreflightCheck(
        identifier,
        exists,
        f"{label}: {'ready' if exists else 'missing'} ({path})",
        "Run SETUP_PORTABLE_RUNTIME.bat to restore the verified local artifact."
        if not exists
        else "",
    )


def run_preflight(
    root: Path,
    *,
    module_probe: Callable[[Path, str], bool] = _module_probe,
    ollama_probe: Callable[[Path], OllamaProbe] = _ollama_probe,
    writable_probe: Callable[[Path], bool] = _writable_probe,
) -> PreflightReport:
    layout: PortableLayout = resolve_layout(root)
    path = lambda value: Path(value)
    python = path(layout.python_exe)
    ollama = ollama_probe(path(layout.ollama_exe))
    mcp_ready = python.is_file() and module_probe(python, "mcp")
    checks = [
        _file_check("python", "Portable Python", python),
        PreflightCheck(
            "mcp_sdk",
            mcp_ready,
            "Python MCP SDK is available." if mcp_ready else "Python MCP SDK is missing.",
            "Run SETUP_PORTABLE_RUNTIME.bat to restore the pinned Python environment.",
        ),
        _file_check("ollama_binary", "Portable Ollama", path(layout.ollama_exe)),
        PreflightCheck(
            "ollama_endpoint",
            is_loopback_url(ollama.endpoint),
            f"Ollama endpoint: {ollama.endpoint}",
            "Set Ollama to a loopback endpoint such as http://127.0.0.1:11434.",
        ),
        PreflightCheck(
            "ollama_service",
            ollama.running,
            "Local Ollama service is reachable." if ollama.running else "Local Ollama service is not reachable.",
            "Start the bundled Ollama service with START_OPENMONTAGE.bat.",
        ),
        _file_check("ffmpeg", "FFmpeg", path(layout.ffmpeg_exe)),
        _file_check("ffprobe", "FFprobe", path(layout.ffprobe_exe)),
        _file_check("downloader", "Public URL downloader", path(layout.ytdlp_exe)),
    ]
    missing_models = sorted(REQUIRED_MODELS - ollama.models)
    checks.extend(
        [
            PreflightCheck(
                "models",
                not missing_models,
                "Required local models are present." if not missing_models else "Missing local models: " + ", ".join(missing_models),
                "Run SETUP_PORTABLE_RUNTIME.bat to import the pinned model artifacts.",
            ),
            PreflightCheck(
                "context",
                ollama.running and ollama.orchestrator_context == 32768,
                f"Orchestrator context: {ollama.orchestrator_context or 'unavailable'}",
                "Recreate openmontage-gpt-oss:20b-32k with num_ctx 32768.",
            ),
            PreflightCheck(
                "runtime_writable",
                writable_probe(path(layout.runtime_root)),
                "Runtime directory is writable.",
                "Move OpenMontage to a writable folder and retry.",
            ),
        ]
    )
    return PreflightReport(
        "passed" if all(check.ok for check in checks) else "blocked",
        tuple(checks),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the portable OpenMontage runtime")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_preflight(args.root.resolve())
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(f"Portable OpenMontage preflight: {report.status.upper()}")
        for check in report.checks:
            marker = "OK" if check.ok else "BLOCKED"
            print(f"  [{marker}] {check.message}")
            if not check.ok:
                print(f"            {check.remedy}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
