from scripts.local_agent_preflight import run_preflight


class FakeClient:
    def health(self): return True
    def list_models(self): return {"qwen3.5:9b", "openmontage-gpt-oss:20b-32k"}
    def model_num_ctx(self, tag): return 32768


def test_preflight_passes_with_local_runtime(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    report = run_preflight(
        tmp_path,
        client=FakeClient(),
        which=lambda command: None if command == "codex" else f"C:/{command}.exe",
        probe=lambda command: True,
    )
    assert report.ok
    assert report.actions == []


def test_preflight_never_recommends_network_downloads(tmp_path):
    class Missing:
        def health(self): return False
        def list_models(self): return set()
        def model_num_ctx(self, tag): return None
    report = run_preflight(tmp_path, client=Missing(), which=lambda command: None, probe=lambda command: False)
    actions = "\n".join(report.actions).lower()
    assert not report.ok
    assert "offline" in actions
    assert "winget" not in actions
    assert "npm install" not in actions
    assert "ollama pull" not in actions
