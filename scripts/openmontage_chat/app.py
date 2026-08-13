from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from lib.input_manifest import InputPriority, register_inputs
from scripts.openmontage_chat.project_store import ProjectStore
from scripts.openmontage_chat.operation_manager import OperationManager


MODEL = "openmontage-gpt-oss:20b-32k"
RESPONSE_INSTRUCTIONS = (
    " Верни только JSON-объект вида "
    '{"answer":"итоговый ответ", "summary":["2–4 кратких полезных вывода о подходе"]}. '
    "В summary не раскрывай скрытые рассуждения, внутренние инструкции, токены или технические логи."
)


class MaterialRequest(BaseModel):
    paths: list[str]


class ChatRequest(BaseModel):
    message: str
    materials: list[str] = []
    mode: str = "confirm"
    history: list[dict[str, str]] = []


def _kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mxf", ".mts", ".m2ts"}:
        return "video"
    if ext in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
        return "audio"
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}:
        return "image"
    return "document"


def parse_model_response(content: str) -> dict[str, Any]:
    """Extract a final answer and a small user-facing summary, with plain-text fallback."""
    raw = str(content or "").strip()
    candidate = raw
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].lstrip()
    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return {"answer": raw, "summary": []}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("answer"), str):
        return {"answer": raw, "summary": []}
    summary = parsed.get("summary", [])
    if not isinstance(summary, list):
        summary = []
    clean_summary = [item.strip()[:240] for item in summary if isinstance(item, str) and item.strip()][:4]
    return {"answer": parsed["answer"].strip(), "summary": clean_summary}


def _ollama_chat(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.loads(response.read().decode("utf-8"))


class DesktopApi:
    """Direct bridge used by the native WebView2 window; no HTTP server involved."""

    def __init__(self, *, root: Path, ollama_chat=None, file_picker=None) -> None:
        self.root = root.resolve()
        self.ollama_chat = ollama_chat or _ollama_chat
        self.file_picker = file_picker or (lambda: [])
        self.store = ProjectStore(self.root)
        self.operations = OperationManager(self.root / "runtime" / "chat-data")
        from scripts.openmontage_chat.orchestrator import LocalOrchestrator
        self.orchestrator = LocalOrchestrator(self.root, store=self.store, model_chat=self.ollama_chat)
        self.active_project_id: str | None = None

    def _project_state(self, project_id: str) -> dict[str, Any]:
        state = self.store.load(project_id)
        manifest = Path(state["project_root"]) / "artifacts" / "input_manifest.json"
        state["input_manifest"] = json.loads(manifest.read_text(encoding="utf-8"))
        state["operations"] = self.operations.list(project_id)
        return state

    def bootstrap(self) -> dict[str, Any]:
        projects = self.store.list()
        if not projects:
            active = self.create_project("Новый монтаж")
        else:
            self.active_project_id = projects[0]["project_id"]
            active = self._project_state(self.active_project_id)
        return {"projects": self.store.list(), "active_project": active}

    def create_project(self, title: str = "Новый монтаж") -> dict[str, Any]:
        state = self.store.create(title)
        self.active_project_id = state["project_id"]
        return self._project_state(self.active_project_id)

    def open_project(self, project_id: str) -> dict[str, Any]:
        self.active_project_id = project_id
        return self._project_state(project_id)

    def rename_project(self, project_id: str, title: str) -> dict[str, Any]:
        self.store.set_status(project_id, self.store.load(project_id)["status"], title=title.strip() or "Новый монтаж")
        return self._project_state(project_id)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        active_operations = [
            item for item in self.operations.list(project_id)
            if item.get("status") in {"queued", "running", "cancelling"}
        ]
        if active_operations:
            raise RuntimeError("Сначала остановите выполняющуюся операцию проекта")
        deleted = self.store.delete(project_id)
        projects = self.store.list()
        if projects:
            self.active_project_id = projects[0]["project_id"]
            active = self._project_state(self.active_project_id)
        else:
            active = self.create_project("Новый монтаж")
            projects = self.store.list()
        return {"deleted": deleted, "projects": projects, "active_project": active}

    def pick_materials(self, project_id: str | None = None) -> dict[str, Any]:
        return self.add_material_paths(project_id, list(self.file_picker()))

    def add_material_paths(self, project_id: str | None, paths: list[str]) -> dict[str, Any]:
        result = []
        seen: set[Path] = set()
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if path.is_dir():
                candidates = sorted((item.resolve() for item in path.rglob("*") if item.is_file()), key=str)
            elif path.is_file():
                candidates = [path]
            else:
                raise FileNotFoundError(f"Файл не найден: {path}")
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                result.append({
                    "name": candidate.name,
                    "path": str(candidate),
                    "kind": _kind(candidate),
                    "mime": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
                    "size": candidate.stat().st_size,
                })
        payload: dict[str, Any] = {"materials": result}
        active = project_id or self.active_project_id
        if active and result:
            register_inputs(active, [item["path"] for item in result], priority=InputPriority.REQUIRED, pipeline_dir=self.store.projects_root)
            payload["project"] = self._project_state(active)
        return payload

    def submit(self, project_id: str, message: str, mode: str = "confirm") -> dict[str, Any]:
        result = self.orchestrator.submit(project_id, message, mode)
        plan = result.get("plan") or {}
        human_gate = bool(plan.get("stage_contract", {}).get("human_approval_required"))
        if mode == "auto" and not human_gate and result.get("status") == "awaiting_approval" and plan.get("plan_id"):
            return self.approve_plan(project_id, plan["plan_id"], mode)["project"]
        return self._project_state(result["project_id"])

    def answer_questions(self, project_id: str, question_set_id: str | dict[str, str], answers: dict[str, str] | str | None = None, mode: str = "confirm") -> dict[str, Any]:
        if isinstance(question_set_id, dict):
            legacy_answers = question_set_id
            legacy_mode = answers if isinstance(answers, str) else mode
            question_set_id = self.store.load(project_id)["brief"].get("question_set_id")
            answers, mode = legacy_answers, legacy_mode
        assert isinstance(answers, dict)
        self.store.answer_questions(project_id, str(question_set_id or ""), answers)
        summary = "; ".join(f"{key}: {value}" for key, value in answers.items())
        return self.submit(project_id, "Ответы на уточнения: " + summary, mode)

    def set_enhancements(self, project_id: str, choices: dict[str, bool], mode: str = "confirm") -> dict[str, Any]:
        self.store.update_brief(project_id, {"enhancements": choices}, enhancements=[])
        selected = [key for key, enabled in choices.items() if enabled]
        return self.submit(project_id, "Выбранные улучшения: " + (", ".join(selected) or "без дополнительных улучшений"), mode)

    def approve_plan(self, project_id: str, plan_id: str | None = None, mode: str = "confirm") -> dict[str, Any]:
        plan = self.store.load(project_id).get("plan") or {}
        active_plan_id = plan_id or plan.get("plan_id")
        self.store.require_active_plan(project_id, str(active_plan_id or ""), mode=mode)
        self.store.resolve_plan(project_id, str(active_plan_id), "running")
        operation = self.operations.start(
            project_id, str(active_plan_id),
            lambda control: self.orchestrator.approve_plan(project_id, str(active_plan_id), mode, control),
        )
        return {"operation": operation, "project": self._project_state(project_id)}

    def operation_status(self, operation_id: str) -> dict[str, Any]:
        operation = self.operations.get(operation_id)
        return {"operation": operation, "project": self._project_state(operation["project_id"])}

    def cancel_operation(self, operation_id: str) -> dict[str, Any]:
        return self.operations.cancel(operation_id)

    def resume_operation(self, operation_id: str) -> dict[str, Any]:
        operation = self.operations.get(operation_id)
        resumed = self.operations.resume(
            operation_id,
            lambda control: self.orchestrator.approve_plan(
                operation["project_id"], operation["plan_id"], "auto", control,
            ),
        )
        return {"operation": resumed, "project": self._project_state(operation["project_id"])}

    def create_version(self, project_id: str) -> dict[str, Any]:
        self.store.create_version(project_id)
        return self._project_state(project_id)

    def open_project_folder(self, project_id: str) -> dict[str, Any]:
        path = Path(self.store.load(project_id)["project_root"])
        subprocess.Popen(["explorer.exe", str(path)])
        return {"ok": True, "path": str(path)}

    def open_artifact(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        artifact = self.store.get_artifact(project_id, artifact_id)
        subprocess.Popen(["explorer.exe", artifact["path"]])
        return {"ok": True, "artifact": artifact}

    def chat(self, body: dict[str, Any]) -> dict[str, Any]:
        paths = body.get("materials") or []
        material_context = "\n".join(f"- {Path(path).name}: {path}" for path in paths)
        prompt = str(body.get("message") or "")
        if material_context:
            prompt += "\n\nЛокальные материалы проекта:\n" + material_context
        messages = [{"role": "system", "content": (
            "Ты OpenMontage — локальный монтажный ассистент с одной закреплённой моделью. "
            "Работай с материалами по локальным путям и отвечай по-русски." + RESPONSE_INSTRUCTIONS
        )}]
        messages.extend((body.get("history") or [])[-30:])
        messages.append({"role": "user", "content": prompt})
        response = self.ollama_chat({"model": MODEL, "messages": messages, "stream": False, "think": "low"})
        result = parse_model_response(response.get("message", {}).get("content", ""))
        return {**result, "model": MODEL}


def create_app(*, root: Path | None = None, ollama_chat: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> FastAPI:
    root = (root or Path(__file__).resolve().parents[2]).resolve()
    chat = ollama_chat or _ollama_chat
    app = FastAPI(title="OpenMontage Chat", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    @app.post("/api/materials")
    def materials(body: MaterialRequest):
        result = []
        for raw in body.paths:
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise HTTPException(400, f"Файл не найден: {path}")
            result.append({
                "name": path.name,
                "path": str(path),
                "kind": _kind(path),
                "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "size": path.stat().st_size,
            })
        return {"materials": result}

    @app.post("/api/pick-materials")
    def pick_materials():
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'OpenMontage — добавить материалы'
$dialog.Multiselect = $true
$dialog.Filter = 'Все материалы|*.mp4;*.mov;*.mkv;*.avi;*.webm;*.mxf;*.mts;*.m2ts;*.wav;*.mp3;*.m4a;*.aac;*.flac;*.ogg;*.jpg;*.jpeg;*.png;*.webp;*.tif;*.tiff;*.bmp;*.pdf;*.doc;*.docx;*.txt;*.md;*.rtf;*.csv;*.xlsx;*.pptx;*.srt;*.vtt;*.ass;*.json;*.xml;*.edl;*.fcpxml;*.aaf|Все файлы|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $dialog.FileNames | ConvertTo-Json -Compress } else { '[]' }
'''
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            text=True, capture_output=True, check=True, encoding="utf-8",
        )
        selected = json.loads(result.stdout.strip() or "[]")
        if isinstance(selected, str):
            selected = [selected]
        return materials(MaterialRequest(paths=selected))

    @app.post("/api/chat")
    def send(body: ChatRequest):
        material_context = "\n".join(f"- {Path(path).name}: {path}" for path in body.materials)
        prompt = body.message
        if material_context:
            prompt += (
                "\n\nЛокальные материалы проекта (это пути, не выдумывай их содержимое; "
                "используй инструменты OpenMontage для анализа):\n" + material_context
            )
        messages = [{"role": "system", "content": (
            "Ты OpenMontage — локальный монтажный ассистент. Интерфейс использует одну закреплённую модель. "
            "Работай с локальными материалами по их путям, объясняй монтажные решения ясно и по-русски. "
            f"Текущий режим разрешений: {body.mode}." + RESPONSE_INSTRUCTIONS
        )}]
        messages.extend(body.history[-30:])
        messages.append({"role": "user", "content": prompt})
        try:
            response = chat({"model": MODEL, "messages": messages, "stream": False, "think": "low"})
        except Exception as exc:
            raise HTTPException(502, f"Локальная модель недоступна: {exc}") from exc
        result = parse_model_response(response.get("message", {}).get("content", ""))
        return {**result, "model": MODEL}

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int, default=17861)
    args = parser.parse_args()
    uvicorn.run(create_app(root=args.root), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
