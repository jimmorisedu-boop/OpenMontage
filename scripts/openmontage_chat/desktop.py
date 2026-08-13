from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import webview
from webview.dom import DOMEventHandler

from scripts.openmontage_chat.app import DesktopApi


class NativeApi(DesktopApi):
    def __init__(self, *, window, **kwargs):
        super().__init__(**kwargs)
        self.window = window

    def pick_materials(self, project_id=None):
        # Bridge methods run on a worker. OpenFileDialog needs its own STA
        # thread on Windows or it can close without ever becoming visible.
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.Opacity = 0
$owner.Width = 1
$owner.Height = 1
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'OpenMontage — добавить материалы'
$dialog.Multiselect = $true
$dialog.RestoreDirectory = $true
$dialog.Filter = 'Все материалы|*.mp4;*.mov;*.mkv;*.avi;*.webm;*.mxf;*.mts;*.m2ts;*.wav;*.mp3;*.m4a;*.aac;*.flac;*.ogg;*.jpg;*.jpeg;*.png;*.webp;*.tif;*.tiff;*.bmp;*.pdf;*.doc;*.docx;*.txt;*.md;*.rtf;*.csv;*.xlsx;*.pptx;*.srt;*.vtt;*.ass;*.json;*.xml;*.edl;*.fcpxml;*.aaf|Все файлы|*.*'
try {
    $owner.Show()
    $owner.Activate()
    if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
        $dialog.FileNames | ConvertTo-Json -Compress
    } else { '[]' }
} finally { $owner.Close(); $owner.Dispose(); $dialog.Dispose() }
'''
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            text=True,
            capture_output=True,
            check=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        selection = json.loads(completed.stdout.strip() or "[]")
        if isinstance(selection, str):
            selection = [selection]
        return self.add_material_paths(project_id, selection)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    window = webview.create_window(
        "OpenMontage", html=html,
        width=1280, height=840, min_size=(820, 620), resizable=True, text_select=True,
    )
    api = NativeApi(root=args.root, window=window)
    window.expose(*[
        getattr(api, name) for name in (
            "bootstrap", "create_project", "open_project", "rename_project", "delete_project",
            "pick_materials", "add_material_paths", "submit", "answer_questions", "set_enhancements",
            "approve_plan", "operation_status", "cancel_operation", "resume_operation", "create_version",
            "open_project_folder", "open_artifact",
        )
    ])

    def bind_native_drop() -> None:
        def on_drop(event):
            paths = [
                file.get("pywebviewFullPath")
                for file in event.get("dataTransfer", {}).get("files", [])
                if file.get("pywebviewFullPath")
            ]
            window.evaluate_js(
                "window.dispatchEvent(new CustomEvent('openmontage:native-drop', "
                f"{{detail: {json.dumps(paths, ensure_ascii=False)}}}))"
            )

        window.dom.document.on("drop", DOMEventHandler(on_drop, prevent_default=True))

    window.events.loaded += bind_native_drop
    webview.start(
        gui="edgechromium", private_mode=False,
        storage_path=str(args.root / "runtime" / "chat-data"),
    )


if __name__ == "__main__":
    main()
