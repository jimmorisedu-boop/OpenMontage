from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_launcher_opens_dedicated_chat_window_without_jan():
    script = (ROOT / "scripts" / "start_openmontage.ps1").read_text(encoding="utf-8-sig")
    assert "scripts.openmontage_chat.desktop" in script
    assert "--app=http://127.0.0.1:" not in script
    assert "msedge.exe" not in script
    assert "Jan.exe" not in script
