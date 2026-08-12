"""Single source of truth for the movable OpenMontage Windows runtime."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ORCHESTRATOR_MODEL = "openmontage-gpt-oss:20b-32k"
VISION_MODEL = "qwen3.5:9b"


@dataclass(frozen=True)
class PortableLayout:
    root: str
    runtime_root: str
    jan_exe: str
    jan_data: str
    python_exe: str
    ollama_exe: str
    models_dir: str
    ffmpeg_exe: str
    ffprobe_exe: str
    ytdlp_exe: str
    state_dir: str
    temp_dir: str
    logs_dir: str
    orchestrator_model: str = ORCHESTRATOR_MODEL
    vision_model: str = VISION_MODEL


# Compatibility for existing imports while launchers migrate to PortableLayout.
PortableRuntimeLayout = PortableLayout


def resolve_layout(root: Path) -> PortableLayout:
    root = root.resolve()
    runtime = root / "runtime"
    return PortableLayout(
        root=str(root),
        runtime_root=str(runtime),
        jan_exe=str(runtime / "jan" / "Jan.exe"),
        jan_data=str(runtime / "jan-data"),
        python_exe=str(runtime / "python" / "python.exe"),
        ollama_exe=str(runtime / "ollama" / "ollama.exe"),
        models_dir=str(runtime / "models"),
        ffmpeg_exe=str(runtime / "ffmpeg" / "ffmpeg.exe"),
        ffprobe_exe=str(runtime / "ffmpeg" / "ffprobe.exe"),
        ytdlp_exe=str(runtime / "downloader" / "yt-dlp.exe"),
        state_dir=str(runtime / "state"),
        temp_dir=str(runtime / "temp"),
        logs_dir=str(runtime / "logs"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the OpenMontage portable runtime layout")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(asdict(resolve_layout(args.root)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
