from pathlib import Path

from tools.tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[2]


def test_launcher_enables_fail_closed_offline_mode():
    text = (ROOT / "scripts" / "start_local_agent.ps1").read_text(encoding="utf-8")
    assert "$env:OPENMONTAGE_OFFLINE = '1'" in text
    assert "http://127.0.0.1:11434" in text
    for forbidden in ["winget", "npm install", "pip install", "ollama pull"]:
        assert forbidden not in text.lower()


def test_setup_never_downloads():
    text = (ROOT / "scripts" / "setup_local_agent.ps1").read_text(encoding="utf-8")
    for forbidden in ["invoke-webrequest", "curl", "winget", "npm install", "pip install", "ollama pull"]:
        assert forbidden not in text.lower()


def test_user_guide_has_no_web_links():
    text = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "http://" not in text


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
