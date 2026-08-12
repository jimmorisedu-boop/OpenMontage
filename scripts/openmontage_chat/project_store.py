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
        _atomic_json(project / "brief.json", {"version": "1.0", "known": {}, "questions": [], "enhancements": [], "question_set_id": None})
        _atomic_json(project / "artifacts.json", {"version": "1.0", "expected": [], "verified": []})
        _atomic_json(project / "versions.json", {"version": "1.0", "versions": []})
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
            "artifacts_state": self._read(project_id, "artifacts.json", {"expected": [], "verified": []}),
            "versions": self._read(project_id, "versions.json", {"versions": []}).get("versions", []),
            "projects": self.list(),
        }

    def append_entry(self, project_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        conversation = self._read(project_id, "conversation.json", {"version": "1.0", "entries": []})
        if entry.get("type") in {"questions", "enhancements", "plan"}:
            for previous in conversation["entries"]:
                if previous.get("type") == entry.get("type") and previous.get("active", True):
                    previous["active"] = False
        saved = {"entry_id": uuid.uuid4().hex, "created_at": _now(), **entry}
        if entry.get("type") in {"questions", "enhancements", "plan"}:
            saved.setdefault("active", True)
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

    def set_questions(self, project_id: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
        brief = self._read(project_id, "brief.json", {"version": "1.0", "known": {}, "questions": [], "enhancements": []})
        brief["question_set_id"] = uuid.uuid4().hex
        brief["questions"] = list(questions)[:3]
        _atomic_json(self._dir(project_id) / "brief.json", brief)
        self._touch(project_id, status="needs_brief")
        return {"question_set_id": brief["question_set_id"], "questions": brief["questions"]}

    def answer_questions(self, project_id: str, question_set_id: str, answers: dict[str, str]) -> dict[str, Any]:
        brief = self._read(project_id, "brief.json", {"version": "1.0", "known": {}, "questions": [], "enhancements": []})
        if not question_set_id or question_set_id != brief.get("question_set_id"):
            raise ValueError("Набор вопросов устарел; ответьте на последнюю карточку")
        required = {str(item.get("question_id")) for item in brief.get("questions", []) if item.get("blocking", True)}
        if not required.issubset({str(key) for key, value in answers.items() if str(value).strip()}):
            raise ValueError("Нужно ответить на все обязательные вопросы")
        brief.setdefault("known", {}).update(answers)
        brief["questions"] = []
        brief["question_set_id"] = None
        _atomic_json(self._dir(project_id) / "brief.json", brief)
        self._deactivate_cards(project_id, "questions", question_set_id=question_set_id)
        self._touch(project_id)
        return brief

    def _deactivate_cards(self, project_id: str, card_type: str, **identity: str) -> None:
        conversation = self._read(project_id, "conversation.json", {"version": "1.0", "entries": []})
        changed = False
        for entry in conversation["entries"]:
            if entry.get("type") != card_type or not entry.get("active", True):
                continue
            if card_type == "plan":
                matches = entry.get("plan", {}).get("plan_id") == identity.get("plan_id")
            else:
                matches = all(entry.get(key) == value for key, value in identity.items())
            if matches:
                entry["active"] = False
                changed = True
        if changed:
            _atomic_json(self._dir(project_id) / "conversation.json", conversation)

    def save_plan(self, project_id: str, plan: dict[str, Any], *, mode: str = "confirm") -> dict[str, Any]:
        saved = {**plan, "plan_id": uuid.uuid4().hex, "mode": mode, "created_at": _now(), "status": "active"}
        _atomic_json(self._dir(project_id) / "plan.json", saved)
        self._touch(project_id, status="awaiting_approval")
        return saved

    def require_active_plan(self, project_id: str, plan_id: str, *, mode: str, allow_running: bool = False) -> dict[str, Any]:
        if mode == "read_only":
            raise PermissionError("В режиме только чтение запуск запрещён")
        plan = self._read(project_id, "plan.json", None)
        valid_statuses = {"active", "running"} if allow_running else {"active"}
        if not isinstance(plan, dict) or plan.get("plan_id") != plan_id or plan.get("status") not in valid_statuses:
            raise ValueError("План устарел; подтвердите последнюю карточку")
        if plan.get("mode") == "read_only":
            raise PermissionError("План создан в режиме только чтение")
        return plan

    def resolve_plan(self, project_id: str, plan_id: str, status: str) -> dict[str, Any]:
        plan = self._read(project_id, "plan.json", None)
        if not isinstance(plan, dict) or plan.get("plan_id") != plan_id:
            raise ValueError("План устарел; подтвердите последнюю карточку")
        plan["status"] = status
        _atomic_json(self._dir(project_id) / "plan.json", plan)
        self._deactivate_cards(project_id, "plan", plan_id=plan_id)
        self._touch(project_id)
        return plan

    def set_status(self, project_id: str, status: str, **changes: Any) -> dict[str, Any]:
        self._touch(project_id, status=status, **changes)
        return self.load(project_id)

    def create_version(self, project_id: str, *, change_note: str = "Новая версия") -> dict[str, Any]:
        marker = self._marker(project_id)
        number = int(marker.get("current_version", 0)) + 1
        renders = self._dir(project_id) / "renders" / f"v{number:03d}"
        renders.mkdir(parents=True, exist_ok=True)
        self._touch(project_id, current_version=number)
        versions = self._read(project_id, "versions.json", {"version": "1.0", "versions": []})
        previous = versions["versions"][-1]["version_id"] if versions["versions"] else None
        snapshot = {
            "version_id": f"v{number:03d}", "number": number, "parent_version_id": previous,
            "change_note": change_note.strip() or "Новая версия", "created_at": _now(),
            "renders_dir": str(renders), "plan_id": (self._read(project_id, "plan.json", {}) or {}).get("plan_id"),
        }
        versions["versions"].append(snapshot)
        _atomic_json(self._dir(project_id) / "versions.json", versions)
        return snapshot

    def _verify_path(self, project_id: str, raw_path: str | Path) -> dict[str, Any]:
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
        return {"artifact_id": uuid.uuid4().hex, "path": str(path), "name": path.name, "verified": True, "metadata": metadata}

    def set_expected_artifacts(self, project_id: str, expected: list[dict[str, Any]]) -> dict[str, Any]:
        project = self._dir(project_id)
        normalized = []
        for item in expected:
            path = Path(str(item.get("path") or "")).resolve()
            if not path.is_relative_to(project):
                raise ValueError("Artifact is outside active project")
            normalized.append({"key": str(item.get("key") or path.name), "path": str(path), "required": bool(item.get("required", True))})
        state = self._read(project_id, "artifacts.json", {"version": "1.0", "expected": [], "verified": []})
        state["expected"] = normalized
        state["verified"] = []
        _atomic_json(project / "artifacts.json", state)
        self._touch(project_id)
        return state

    def verify_expected_artifacts(self, project_id: str) -> dict[str, Any]:
        state = self._read(project_id, "artifacts.json", {"version": "1.0", "expected": [], "verified": []})
        verified, missing = [], []
        for item in state.get("expected", []):
            try:
                verified.append({**self._verify_path(project_id, item["path"]), "key": item["key"]})
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                if item.get("required", True):
                    missing.append({"key": item["key"], "path": item["path"], "error": str(exc)})
        state["verified"] = verified
        _atomic_json(self._dir(project_id) / "artifacts.json", state)
        if missing or not verified:
            self._touch(project_id, status="needs_attention")
            return {"ready": False, "artifacts": verified, "missing": missing}
        bundle = {"artifact_id": uuid.uuid4().hex, "artifacts": verified}
        self.append_entry(project_id, {"role": "assistant", "type": "result", "artifact_bundle": bundle, "artifact": verified[0]})
        self._touch(project_id, status="ready", verified_artifact=verified[0], verified_artifacts=verified)
        return {"ready": True, "artifacts": verified, "missing": []}

    def get_artifact(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        state = self._read(project_id, "artifacts.json", {"verified": []})
        for artifact in state.get("verified", []):
            if artifact.get("artifact_id") == artifact_id:
                path = Path(artifact["path"])
                if not path.is_file():
                    raise FileNotFoundError(path)
                return artifact
        marker = self._marker(project_id)
        legacy = marker.get("verified_artifact")
        if isinstance(legacy, dict) and legacy.get("artifact_id") == artifact_id:
            return legacy
        # Migration path for result cards created before artifact IDs were
        # passed to the native bridge. This lookup is intentionally read-only.
        candidate = Path(artifact_id).resolve()
        if candidate.is_relative_to(self._dir(project_id)) and candidate.is_file():
            if isinstance(legacy, dict) and Path(str(legacy.get("path", ""))).resolve() == candidate:
                return legacy
            for artifact in state.get("verified", []):
                if Path(str(artifact.get("path", ""))).resolve() == candidate:
                    return artifact
        raise KeyError("Artifact not found")

    def verify_artifact(self, project_id: str, raw_path: str | Path) -> dict[str, Any]:
        artifact = self._verify_path(project_id, raw_path)
        self.append_entry(project_id, {"role": "assistant", "type": "result", "artifact": artifact})
        self._touch(project_id, status="ready", verified_artifact=artifact)
        return artifact
