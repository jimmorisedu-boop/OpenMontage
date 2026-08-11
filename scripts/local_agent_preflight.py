"""Fail-closed preflight for the air-gapped local editing agent."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from lib.providers.ollama import OllamaClient, OllamaError


COMMANDS = ("ollama", "ffmpeg", "ffprobe")
MODELS = ("qwen3.5:9b", "openmontage-gpt-oss:20b-32k")


def _probe_command(command: str) -> bool:
    try:
        subprocess.run([command, "--version"], capture_output=True, timeout=10, check=False)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


@dataclass
class PreflightReport:
    ok: bool
    ollama_running: bool
    missing_commands: list[str]
    missing_models: list[str]
    profile_context_length: int | None
    venv_python: str | None
    actions: list[str]


def run_preflight(
    root: Path,
    *,
    client: OllamaClient | None = None,
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[str], bool] = _probe_command,
) -> PreflightReport:
    missing_commands = [command for command in COMMANDS if not which(command) or not probe(command)]
    ollama = client or OllamaClient(timeout_seconds=5)
    running = ollama.health()
    try:
        installed = ollama.list_models() if running else set()
    except OllamaError:
        installed = set()
        running = False
    missing_models = [model for model in MODELS if model not in installed]
    try:
        context = ollama.model_num_ctx("openmontage-gpt-oss:20b-32k") if running and "openmontage-gpt-oss:20b-32k" in installed else None
    except OllamaError:
        context = None
    venv = root / ".venv" / "Scripts" / "python.exe"
    actions: list[str] = []
    if missing_commands:
        actions.append("Copy the missing executables from approved offline installation media and add them to PATH: " + ", ".join(missing_commands))
    if not running:
        actions.append("Start the locally installed Ollama service; only 127.0.0.1:11434 is permitted")
    if missing_models:
        actions.append("Import the missing model artifacts from approved offline media: " + ", ".join(missing_models))
    if running and not missing_models and context != 32768:
        actions.append(r"Create the local 32K profile: scripts\setup_local_agent.ps1 -CreateProfile")
    if not venv.is_file():
        actions.append("Restore .venv from the offline wheelhouse or approved environment archive")
    ok = not missing_commands and running and not missing_models and context == 32768 and venv.is_file()
    return PreflightReport(ok, running, missing_commands, missing_models, context, str(venv) if venv.is_file() else None, actions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the fully offline OpenMontage runtime")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_preflight(args.root.resolve())
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print("Offline OpenMontage preflight: " + ("PASSED" if report.ok else "BLOCKED"))
        for action in report.actions:
            print(f"  - {action}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
