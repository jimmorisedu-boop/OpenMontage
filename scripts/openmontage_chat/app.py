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

    def pick_materials(self) -> dict[str, Any]:
        result = []
        for raw in self.file_picker():
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Файл не найден: {path}")
            result.append({
                "name": path.name,
                "path": str(path),
                "kind": _kind(path),
                "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "size": path.stat().st_size,
            })
        return {"materials": result}

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
