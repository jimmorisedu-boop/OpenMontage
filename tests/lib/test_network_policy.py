from __future__ import annotations

import pytest

from lib.network_policy import (
    NetworkMode,
    NetworkRequest,
    NetworkViolation,
    authorize_network,
    current_network_mode,
)
from tools.base_tool import BaseTool, ResourceProfile, ToolResult, ToolRuntime, ToolStatus
from tools.tool_registry import ToolRegistry


class _RemoteTool(BaseTool):
    name = "remote_policy_test"
    runtime = ToolRuntime.API
    resource_profile = ResourceProfile(network_required=True)

    def execute(self, inputs):
        return ToolResult(success=True)


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11434/api/tags", "http://localhost:8000", "http://[::1]:9000"],
)
@pytest.mark.parametrize("mode", list(NetworkMode))
def test_loopback_is_allowed_in_every_mode(url, mode):
    authorize_network(NetworkRequest(component="ollama", submitted_url=url), mode)


def test_legacy_offline_flag_maps_to_strict_mode(monkeypatch):
    monkeypatch.delenv("OPENMONTAGE_NETWORK_MODE", raising=False)
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    assert current_network_mode() is NetworkMode.STRICT_OFFLINE


def test_strict_offline_rejects_public_network():
    with pytest.raises(NetworkViolation, match="strict-offline"):
        authorize_network(
            NetworkRequest(component="url_import_gateway", submitted_url="https://example.com/v"),
            NetworkMode.STRICT_OFFLINE,
        )


def test_url_import_mode_allows_only_the_gateway_exact_public_url():
    request = NetworkRequest(
        component="url_import_gateway", submitted_url="https://example.com/video?id=7"
    )
    authorize_network(request, NetworkMode.URL_IMPORT_ONLY)

    with pytest.raises(NetworkViolation, match="only url_import_gateway"):
        authorize_network(
            NetworkRequest(component="video_generator", submitted_url=request.submitted_url),
            NetworkMode.URL_IMPORT_ONLY,
        )


def test_url_import_mode_disables_cloud_tool_dependencies(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_NETWORK_MODE", "url-import-only")
    monkeypatch.delenv("OPENMONTAGE_OFFLINE", raising=False)
    assert _RemoteTool().get_status() is ToolStatus.UNAVAILABLE


def test_url_import_provider_menu_hides_all_other_network_tools(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_NETWORK_MODE", "url-import-only")
    monkeypatch.delenv("OPENMONTAGE_OFFLINE", raising=False)
    registry = ToolRegistry()
    registry.discover()
    menu = registry.provider_menu()
    entries = [entry for bucket in menu.values() for entry in bucket["available"]]
    for entry in entries:
        if entry["name"] != "url_import_gateway":
            assert entry["runtime"] not in {"api", "hybrid"}


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/secret.mp4",
        r"\\server\share\video.mp4",
        "https://user:password@example.com/video",
        "http://localhost/video",
        "http://127.0.0.1/video",
        "http://10.1.2.3/video",
        "http://172.16.0.1/video",
        "http://192.168.1.2/video",
        "http://169.254.1.1/video",
        "ftp://example.com/video",
    ],
)
def test_url_gateway_rejects_non_public_or_non_http_sources(url):
    with pytest.raises(NetworkViolation):
        authorize_network(
            NetworkRequest(component="url_import_gateway", submitted_url=url),
            NetworkMode.URL_IMPORT_ONLY,
        )
