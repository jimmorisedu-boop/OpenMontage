from __future__ import annotations

import argparse
from pathlib import Path

import webview

from scripts.openmontage_chat.app import DesktopApi


class NativeApi(DesktopApi):
    def pick_materials(self, project_id=None):
        selection = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=(
                "Материалы (*.mp4;*.mov;*.mkv;*.avi;*.webm;*.mxf;*.mts;*.m2ts;*.wav;*.mp3;*.m4a;*.aac;*.flac;*.ogg;*.jpg;*.jpeg;*.png;*.webp;*.pdf;*.doc;*.docx;*.txt;*.md;*.rtf;*.csv;*.xlsx;*.pptx;*.srt;*.vtt;*.ass;*.json;*.xml;*.edl;*.fcpxml;*.aaf)",
                "Все файлы (*.*)",
            ),
        )
        original = self.file_picker
        try:
            self.file_picker = lambda: list(selection or [])
            return super().pick_materials(project_id)
        finally:
            self.file_picker = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    webview.create_window(
        "OpenMontage", html=html, js_api=NativeApi(root=args.root),
        width=1280, height=840, min_size=(820, 620), text_select=True,
    )
    webview.start(
        gui="edgechromium", private_mode=False,
        storage_path=str(args.root / "runtime" / "chat-data"),
    )


if __name__ == "__main__":
    main()
