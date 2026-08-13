from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_launcher_opens_dedicated_chat_window_without_jan():
    script = (ROOT / "scripts" / "start_openmontage.ps1").read_text(encoding="utf-8-sig")
    assert "scripts.openmontage_chat.desktop" in script
    assert "--app=http://127.0.0.1:" not in script
    assert "msedge.exe" not in script
    assert "Jan.exe" not in script


def test_native_window_is_explicitly_resizable():
    source = (ROOT / "scripts" / "openmontage_chat" / "desktop.py").read_text(encoding="utf-8")
    assert "resizable=True" in source


def test_native_picker_is_bound_to_the_window_and_native_drop_is_enabled():
    source = (ROOT / "scripts" / "openmontage_chat" / "desktop.py").read_text(encoding="utf-8")

    assert "NativeApi(root=args.root, window=window)" in source
    assert '["powershell.exe", "-NoProfile", "-STA", "-Command", script]' in source
    assert "dialog.ShowDialog($owner)" in source
    assert "window.dom.document.on(" in source
    assert 'DOMEventHandler(on_drop, prevent_default=True)' in source
    assert 'file.get("pywebviewFullPath")' in source
