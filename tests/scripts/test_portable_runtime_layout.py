import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_layout_keeps_runtime_and_models_below_repository_root(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.portable_runtime_layout",
            "--root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    layout = json.loads(result.stdout)
    assert layout == {
        "runtime_root": str(tmp_path / "runtime"),
        "ollama_exe": str(tmp_path / "runtime" / "ollama" / "ollama.exe"),
        "ffmpeg_exe": str(tmp_path / "runtime" / "ffmpeg" / "ffmpeg.exe"),
        "ffprobe_exe": str(tmp_path / "runtime" / "ffmpeg" / "ffprobe.exe"),
        "models_dir": str(tmp_path / "runtime" / "models"),
        "logs_dir": str(tmp_path / "runtime" / "logs"),
        "orchestrator_model": "openmontage-gpt-oss:20b-32k",
        "vision_model": "qwen3.5:9b",
        "codex_integration": "codex-app",
    }


def test_launcher_inspection_reports_fixed_portable_models():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "start_local_agent.ps1"),
            "-InspectRuntime",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    layout = json.loads(result.stdout)
    assert Path(layout["runtime_root"]) == ROOT / "runtime"
    assert Path(layout["ollama_exe"]) == ROOT / "runtime" / "ollama" / "ollama.exe"
    assert layout["orchestrator_model"] == "openmontage-gpt-oss:20b-32k"
    assert layout["vision_model"] == "qwen3.5:9b"
    assert layout["codex_integration"] == "codex-app"


def test_portable_setup_plan_downloads_only_required_model_weights():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "setup_portable_runtime.ps1"),
            "-PlanOnly",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["models_to_pull"] == ["gpt-oss:20b", "qwen3.5:9b"]
    assert plan["profile_to_create"] == "openmontage-gpt-oss:20b-32k"
    assert plan["source_tags_to_remove"] == ["gpt-oss:20b"]
    assert plan["codex_app_model"] == "openmontage-gpt-oss:20b-32k"
    assert plan["portable_tools"] == ["ollama", "ffmpeg", "ffprobe"]
