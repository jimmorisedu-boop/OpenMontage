import pytest

from lib.offline_guard import OfflineViolation, ensure_tool_is_offline
from tools.base_tool import BaseTool, ResourceProfile, ToolResult, ToolRuntime


class LocalTool(BaseTool):
    name = "local_test"
    runtime = ToolRuntime.LOCAL
    def execute(self, inputs): return ToolResult(success=True)


class RemoteTool(BaseTool):
    name = "remote_test"
    runtime = ToolRuntime.API
    resource_profile = ResourceProfile(network_required=True)
    def execute(self, inputs): return ToolResult(success=True)


def test_offline_guard_allows_files_and_loopback(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    ensure_tool_is_offline(LocalTool(), {"path": "C:/media/a.mp4", "endpoint": "http://127.0.0.1:11434"})


def test_offline_guard_rejects_remote_tool_and_url(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    with pytest.raises(OfflineViolation, match="network-capable"):
        RemoteTool().execute({})
    with pytest.raises(OfflineViolation, match="local paths only"):
        LocalTool().execute({"input": "https://example.com/video.mp4"})
    with pytest.raises(OfflineViolation, match="local paths only"):
        LocalTool().execute({"input": r"\\server\share\video.mp4"})
