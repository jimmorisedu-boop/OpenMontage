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


def _ollama_chat(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.loads(response.read().decode("utf-8"))


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
            f"Текущий режим разрешений: {body.mode}."
        )}]
        messages.extend(body.history[-30:])
        messages.append({"role": "user", "content": prompt})
        try:
            response = chat({"model": MODEL, "messages": messages, "stream": False, "think": "low"})
        except Exception as exc:
            raise HTTPException(502, f"Локальная модель недоступна: {exc}") from exc
        return {"answer": response.get("message", {}).get("content", ""), "model": MODEL}

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int, default=17861)
    args = parser.parse_args()
    uvicorn.run(create_app(root=args.root), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
