from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from lib.checkpoint import init_project


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _default_media_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise ValueError(f"FFprobe could not verify {path.name}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    streams = [str(item.get("codec_type", "")) for item in data.get("streams", [])]
    duration = float(data.get("format", {}).get("duration") or 0)
    if not streams or duration <= 0:
        raise ValueError(f"Media verification failed for {path.name}")
    return {"duration": duration, "streams": streams}


class ProjectStore:
    def __init__(self, root: Path, *, media_probe: Callable[[Path], dict[str, Any]] | None = None) -> None:
        self.root = root.resolve()
        self.projects_root = self.root / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)
        self.media_probe = media_probe or _default_media_probe

    def _dir(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", project_id):
            raise ValueError("Invalid project id")
        path = (self.projects_root / project_id).resolve()
        if not path.is_relative_to(self.projects_root):
            raise ValueError("Project is outside projects root")
        return path

    def _read(self, project_id: str, filename: str, default: Any) -> Any:
        path = self._dir(project_id) / filename
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _marker(self, project_id: str) -> dict[str, Any]:
        path = self._dir(project_id) / "project.json"
        if not path.is_file():
            raise FileNotFoundError(f"Project not found: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _touch(self, project_id: str, **changes: Any) -> None:
        marker = self._marker(project_id)
        marker.update(changes)
        marker["updated_at"] = _now()
        _atomic_json(self._dir(project_id) / "project.json", marker)

    def create(self, title: str = "Новый монтаж") -> dict[str, Any]:
        stem = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "montage"
        project_id = f"{stem[:55]}-{uuid.uuid4().hex[:8]}"
        project = init_project(
            project_id, title=title.strip() or "Новый монтаж",
            pipeline_type="documentary-montage", pipeline_dir=self.projects_root,
        )
        marker = json.loads((project / "project.json").read_text(encoding="utf-8"))
        marker.update({"status": "needs_brief", "updated_at": _now(), "current_version": 0, "verified_artifact": None})
        _atomic_json(project / "project.json", marker)
        _atomic_json(project / "conversation.json", {"version": "1.0", "entries": []})
        _atomic_json(project / "brief.json", {"version": "1.0", "known": {}, "questions": [], "enhancements": []})
        return self.load(project_id)

    def list(self) -> list[dict[str, Any]]:
        items = []
        for marker_path in self.projects_root.glob("*/project.json"):
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                items.append({
                    "project_id": marker["project_id"], "title": marker.get("title", marker["project_id"]),
                    "status": marker.get("status", "needs_brief"), "updated_at": marker.get("updated_at", marker.get("created_at", "")),
                })
            except (OSError, KeyError, json.JSONDecodeError):
                continue
        return sorted(items, key=lambda item: item["updated_at"], reverse=True)

    def load(self, project_id: str) -> dict[str, Any]:
        project = self._dir(project_id)
        marker = self._marker(project_id)
        return {
            **marker,
            "project_root": str(project),
            "conversation": self._read(project_id, "conversation.json", {"entries": []}).get("entries", []),
            "brief": self._read(project_id, "brief.json", {"known": {}, "questions": [], "enhancements": []}),
            "plan": self._read(project_id, "plan.json", None),
            "projects": self.list(),
        }

    def append_entry(self, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        conversation = self._read(project_id, "conversation.json", {"version": "1.0", "entries": []})
        saved = {"entry_id": uuid.uuid4().hex, "created_at": _now(), **entry}
        conversation["entries"].append(saved)
        _atomic_json(self._dir(project_id) / "conversation.json", conversation)
        self._touch(project_id)
        return saved

    def update_brief(self, project_id: str, known: dict[str, Any], *, questions=None, enhancements=None) -> dict[str, Any]:
        brief = self._read(project_id, "brief.json", {"version": "1.0", "known": {}, "questions": [], "enhancements": []})
        brief["known"].update(known)
        if questions is not None:
            brief["questions"] = list(questions)[:3]
        if enhancements is not None:
            brief["enhancements"] = list(enhancements)[:3]
        _atomic_json(self._dir(project_id) / "brief.json", brief)
        self._touch(project_id)
        return brief

    def save_plan(self, project_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        _atomic_json(self._dir(project_id) / "plan.json", plan)
        self._touch(project_id, status="awaiting_approval")
        return plan

    def set_status(self, project_id: str, status: str, **changes: Any) -> dict[str, Any]:
        self._touch(project_id, status=status, **changes)
        return self.load(project_id)

    def create_version(self, project_id: str) -> dict[str, Any]:
        marker = self._marker(project_id)
        number = int(marker.get("current_version", 0)) + 1
        renders = self._dir(project_id) / "renders" / f"v{number:03d}"
        renders.mkdir(parents=True, exist_ok=True)
        self._touch(project_id, current_version=number)
        return {"number": number, "renders_dir": str(renders)}

    def verify_artifact(self, project_id: str, raw_path: str | Path) -> dict[str, Any]:
        project = self._dir(project_id)
        path = Path(raw_path).resolve()
        if not path.is_relative_to(project):
            raise ValueError("Artifact is outside active project")
        if not path.is_file():
            raise FileNotFoundError(path)
        ext = path.suffix.casefold()
        metadata: dict[str, Any] = {"size": path.stat().st_size}
        if ext in {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac"}:
            metadata.update(self.media_probe(path))
        elif ext == ".json":
            metadata["json"] = isinstance(json.loads(path.read_text(encoding="utf-8")), (dict, list))
        elif path.stat().st_size <= 0:
            raise ValueError("Artifact is empty")
        artifact = {"artifact_id": uuid.uuid4().hex, "path": str(path), "name": path.name, "verified": True, "metadata": metadata}
        self.append_entry(project_id, {"role": "assistant", "type": "result", "artifact": artifact})
        self._touch(project_id, status="ready", verified_artifact=artifact)
        return artifact
