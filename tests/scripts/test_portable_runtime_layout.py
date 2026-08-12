import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_layout_keeps_every_runtime_path_below_repository_root(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.portable_runtime_layout", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    layout = json.loads(result.stdout)
    runtime = tmp_path / "runtime"
    expected = {
        "root": str(tmp_path),
        "runtime_root": str(runtime),
        "jan_exe": str(runtime / "jan" / "Jan.exe"),
        "jan_data": str(runtime / "jan-data"),
        "python_exe": str(runtime / "python" / "python.exe"),
        "ollama_exe": str(runtime / "ollama" / "ollama.exe"),
        "models_dir": str(runtime / "models"),
        "ffmpeg_exe": str(runtime / "ffmpeg" / "ffmpeg.exe"),
        "ffprobe_exe": str(runtime / "ffmpeg" / "ffprobe.exe"),
        "ytdlp_exe": str(runtime / "downloader" / "yt-dlp.exe"),
        "state_dir": str(runtime / "state"),
        "temp_dir": str(runtime / "temp"),
        "logs_dir": str(runtime / "logs"),
        "orchestrator_model": "openmontage-gpt-oss:20b-32k",
        "vision_model": "qwen3.5:9b",
    }
    assert layout == expected
    assert "codex_integration" not in layout


def test_layout_paths_are_relocation_safe(tmp_path):
    moved = tmp_path / "Open Montage Portable"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.portable_runtime_layout", "--root", str(moved)],
        capture_output=True,
        text=True,
        check=True,
    )
    layout = json.loads(result.stdout)
    assert all(
        Path(value).is_relative_to(moved)
        for key, value in layout.items()
        if key.endswith(("_exe", "_dir", "_root")) or key in {"root", "jan_data"}
    )
