"""Resolve the repository-local runtime layout used by Windows launchers."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ORCHESTRATOR_MODEL = "openmontage-gpt-oss:20b-32k"
VISION_MODEL = "qwen3.5:9b"
CODEX_INTEGRATION = "codex-app"


@dataclass(frozen=True)
class PortableRuntimeLayout:
    runtime_root: str
    ollama_exe: str
    ffmpeg_exe: str
    ffprobe_exe: str
    models_dir: str
    logs_dir: str
    orchestrator_model: str = ORCHESTRATOR_MODEL
    vision_model: str = VISION_MODEL
    codex_integration: str = CODEX_INTEGRATION


def resolve_layout(root: Path) -> PortableRuntimeLayout:
    root = root.resolve()
    runtime_root = root / "runtime"
    return PortableRuntimeLayout(
        runtime_root=str(runtime_root),
        ollama_exe=str(runtime_root / "ollama" / "ollama.exe"),
        ffmpeg_exe=str(runtime_root / "ffmpeg" / "ffmpeg.exe"),
        ffprobe_exe=str(runtime_root / "ffmpeg" / "ffprobe.exe"),
        models_dir=str(runtime_root / "models"),
        logs_dir=str(runtime_root / "logs"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the OpenMontage portable runtime layout")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(asdict(resolve_layout(args.root)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
