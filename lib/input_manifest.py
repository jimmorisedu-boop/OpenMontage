"""Deterministic inventory for heterogeneous, read-only project inputs."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from schemas.artifacts import validate_artifact


class InputPriority(str, Enum):
    REQUIRED = "required"
    REFERENCE = "reference"
    OPTIONAL = "optional"


_EXTENSION_TYPES = {
    **{ext: "video" for ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".mxf", ".mts", ".m2ts")},
    **{ext: "audio" for ext in (".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".aiff")},
    **{ext: "image" for ext in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".svg")},
    **{ext: "document" for ext in (".pdf", ".doc", ".docx", ".odt", ".rtf")},
    **{ext: "text" for ext in (".txt", ".md", ".fountain")},
    **{ext: "subtitle" for ext in (".srt", ".vtt", ".ass", ".ssa")},
    **{ext: "edit-data" for ext in (".edl", ".xml", ".fcpxml", ".csv", ".otio")},
}


def _role(path: Path, media_type: str) -> str:
    name = path.stem.casefold()
    if any(token in name for token in ("storyboard", "раскадров")):
        return "storyboard"
    if any(token in name for token in ("script", "scenario", "сценар")):
        return "script"
    if media_type == "video":
        return "source-footage"
    if media_type == "audio":
        return "source-audio"
    if media_type == "subtitle":
        return "subtitles"
    if media_type == "edit-data":
        return "edit-reference"
    if media_type in {"document", "text"}:
        return "production-notes"
    if media_type == "image":
        return "visual-reference"
    return "unclassified"


def _stable_id(source_kind: str, value: str) -> str:
    normalized = os.path.normcase(value) if source_kind == "local" else value
    digest = hashlib.sha256(f"{source_kind}\0{normalized}".encode("utf-8")).hexdigest()
    return f"input-{digest[:16]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _technical_metadata(path: Path, media_type: str, project_root: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {"size_bytes": path.stat().st_size, "extension": path.suffix.lower()}
    if media_type not in {"video", "audio"}:
        return metadata
    candidates = [project_root.parents[1] / "runtime" / "ffmpeg" / "ffprobe.exe"] if len(project_root.parents) > 1 else []
    candidates.append(Path("ffprobe"))
    for executable in candidates:
        try:
            result = subprocess.run(
                [str(executable), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                metadata["ffprobe"] = json.loads(result.stdout)
                break
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue
    return metadata


def _manifest_path(project_id: str, pipeline_dir: Path) -> Path:
    return pipeline_dir / project_id / "artifacts" / "input_manifest.json"


def _load(project_id: str, pipeline_dir: Path) -> dict[str, Any]:
    path = _manifest_path(project_id, pipeline_dir)
    if not path.is_file():
        raise FileNotFoundError(f"Project input manifest is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, manifest: dict[str, Any]) -> None:
    validate_artifact("input_manifest", manifest)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _files(paths: Iterable[str]) -> list[Path]:
    found: set[Path] = set()
    for raw in paths:
        candidate = Path(raw).expanduser().resolve(strict=True)
        if candidate.is_dir():
            found.update(item.resolve() for item in candidate.rglob("*") if item.is_file())
        elif candidate.is_file():
            found.add(candidate)
        else:
            raise ValueError(f"Input is not a file or folder: {candidate}")
    return sorted(found, key=lambda item: os.path.normcase(str(item)))


def register_inputs(
    project_id: str,
    paths: list[str],
    *,
    priority: InputPriority,
    pipeline_dir: Path = Path("projects"),
) -> dict[str, Any]:
    pipeline_dir = pipeline_dir.resolve()
    manifest = _load(project_id, pipeline_dir)
    existing = {item["id"]: item for item in manifest["inputs"]}
    project_root = pipeline_dir / project_id
    for path in _files(paths):
        media_type = _EXTENSION_TYPES.get(path.suffix.lower(), "unknown")
        item_id = _stable_id("local", str(path))
        existing[item_id] = {
            "id": item_id,
            "path": str(path),
            "source_kind": "local",
            "media_type": media_type,
            "role": _role(path, media_type),
            "priority": priority.value,
            "interpretation_status": "unsupported" if media_type == "unknown" else "supported",
            "relationships": [],
            "technical_metadata": _technical_metadata(path, media_type, project_root),
        }
    manifest["inputs"] = sorted(existing.values(), key=lambda item: os.path.normcase(item["path"]))
    _write(_manifest_path(project_id, pipeline_dir), manifest)
    return manifest


def register_download(
    project_id: str,
    source_url: str,
    local_path: Path,
    metadata: dict[str, Any],
    *,
    pipeline_dir: Path = Path("projects"),
) -> dict[str, Any]:
    pipeline_dir = pipeline_dir.resolve()
    project_root = (pipeline_dir / project_id).resolve()
    local_path = local_path.resolve(strict=True)
    downloads = (project_root / "inputs" / "downloads").resolve()
    if not local_path.is_relative_to(downloads):
        raise ValueError("Downloaded inputs must live under the project's inputs/downloads directory")
    manifest = _load(project_id, pipeline_dir)
    media_type = _EXTENSION_TYPES.get(local_path.suffix.lower(), "unknown")
    item_id = _stable_id("download", f"{source_url}\0{local_path.name}")
    item = {
        "id": item_id,
        "path": str(local_path),
        "source_kind": "download",
        "source_url": source_url,
        "media_type": media_type,
        "role": _role(local_path, media_type),
        "priority": InputPriority.REQUIRED.value,
        "interpretation_status": "unsupported" if media_type == "unknown" else "supported",
        "relationships": [],
        "technical_metadata": _technical_metadata(local_path, media_type, project_root),
        "sha256": _sha256(local_path),
        "provenance": dict(metadata),
    }
    current = {entry["id"]: entry for entry in manifest["inputs"]}
    current[item_id] = item
    manifest["inputs"] = sorted(current.values(), key=lambda entry: os.path.normcase(entry["path"]))
    _write(_manifest_path(project_id, pipeline_dir), manifest)
    return manifest
