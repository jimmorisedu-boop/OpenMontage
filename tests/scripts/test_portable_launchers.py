from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_setup_installs_only_portable_jan_runtime():
    setup = _read("scripts/setup_portable_runtime.ps1")
    setup_and_manifest = setup + _read("config/runtime/artifacts.json")
    required = [
        "runtime\\python",
        "python-3.12.10-embed-amd64.zip",
        "get-pip.py",
        "runtime\\jan",
        "portable_url",
        "runtime\\downloader",
        "yt-dlp.exe",
        "runtime\\ffmpeg",
        "ollama-windows-amd64.zip",
        "gpt-oss:20b",
        "qwen3.5:9b",
        "seed_jan_profile.py",
        "openmontage_preflight",
        "..\\..",
    ]
    for marker in required:
        assert marker in setup_and_manifest
    assert "codex" not in setup.lower()
    assert "winget" not in setup.lower()
    assert "npm" not in setup.lower()
    assert "ollama launch" not in setup.lower()


def test_launcher_opens_the_patched_jan_window():
    launcher = _read("scripts/start_openmontage.ps1")
    assert "OPENMONTAGE_JAN_DATA_ROOT" in launcher
    assert "OPENMONTAGE_NETWORK_MODE" in launcher
    assert "url-import-only" in launcher
    assert "OPENMONTAGE_OFFLINE = '1'" not in launcher
    assert "Start-Process" in launcher
    assert "jan_exe" in launcher
    assert "codex" not in launcher.lower()


def test_user_facing_bat_names_match_the_new_windowed_shell():
    start = _read("START_OPENMONTAGE.bat")
    setup = _read("SETUP_PORTABLE_RUNTIME.bat")
    assert "start_openmontage.ps1" in start
    assert "OpenMontage" in start
    assert "setup_portable_runtime.ps1" in setup
