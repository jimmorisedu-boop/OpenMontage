from pathlib import Path

from tools.tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[2]


def test_launcher_enables_url_import_only_local_mode():
    text = (ROOT / "scripts" / "start_openmontage.ps1").read_text(encoding="utf-8")
    assert "$env:OPENMONTAGE_NETWORK_MODE = 'url-import-only'" in text
    assert "http://127.0.0.1:11434" in text
    assert "OPENMONTAGE_JAN_DATA_ROOT" in text
    for forbidden in ["winget", "npm install", "pip install", "ollama pull"]:
        assert forbidden not in text.lower()


def test_batch_launcher_delegates_to_portable_powershell_launcher():
    text = (ROOT / "START_OPENMONTAGE.bat").read_text(encoding="utf-8")
    lowered = text.lower()
    assert 'cd /d "%~dp0"' in lowered
    assert 'scripts\\start_openmontage.ps1' in lowered
    assert "powershell.exe -nologo -noprofile -executionpolicy bypass" in lowered
    for forbidden in [
        "invoke-webrequest", "curl", "winget", "npm install", "pip install", "ollama pull",
    ]:
        assert forbidden not in lowered


def test_normal_launcher_never_downloads_or_installs():
    text = (ROOT / "scripts" / "start_openmontage.ps1").read_text(encoding="utf-8")
    for forbidden in ["invoke-restmethod", "curl", "winget", "npm install", "pip install", "ollama pull"]:
        assert forbidden not in text.lower()


def test_user_guide_explains_the_only_network_exception():
    text = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    assert "публичную ссылку" in text
    assert "Cookie" in text
    assert "START_OPENMONTAGE.bat" in text
    assert "Codex Desktop не нужен" in text


def test_offline_provider_menu_contains_only_ready_nonnetwork_tools(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    registry = ToolRegistry()
    registry.discover()
    menu = registry.provider_menu()
    for bucket in menu.values():
        assert bucket["unavailable"] == []
        for entry in bucket["available"]:
            assert entry["runtime"] not in {"api", "hybrid"}
            assert entry["provider"] != "hyperframes"
    summary = registry.provider_menu_summary()
    assert summary["offline_mode"] is True
    assert summary["setup_offers"] == []
    assert summary["composition_runtimes"] == {
        "ffmpeg": True, "remotion": False, "hyperframes": False,
    }
