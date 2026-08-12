from __future__ import annotations

import asyncio
from pathlib import Path

from scripts.openmontage_mcp.server import OpenMontageMCP, create_server


def test_server_lists_bounded_stdio_tools(tmp_path):
    server = create_server(root=tmp_path, pipeline_dir=tmp_path / "projects")
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "bootstrap_conversation", "set_permission_mode", "register_inputs",
        "import_public_url", "inspect_project", "list_available_tools",
        "run_openmontage_tool", "collect_project", "get_operation_status",
        "cancel_operation",
    }
    mutating = next(tool for tool in tools if tool.name == "register_inputs")
    assert "_openmontage_context" in mutating.inputSchema["properties"]


def test_bootstrap_and_context_validation_are_server_authoritative(tmp_path):
    api = OpenMontageMCP(root=tmp_path, pipeline_dir=tmp_path / "projects")
    boot = api.bootstrap_conversation(
        "film", "Film", "cinematic",
        {"conversation_id": "chat-1", "thread_revision": 0, "nonce": "jan-bootstrap"},
    )
    assert boot["ok"]
    context = boot["context"]
    inspected = api.inspect_project(context)
    assert inspected["ok"]
    bad = dict(context, nonce="model-supplied")
    rejected = api.inspect_project(bad)
    assert not rejected["ok"]
    assert rejected["category"] == "blocked"


def test_read_only_tool_listing_omits_mutating_tools(tmp_path):
    api = OpenMontageMCP(root=tmp_path, pipeline_dir=tmp_path / "projects")
    boot = api.bootstrap_conversation(
        "film", "Film", "cinematic",
        {"conversation_id": "chat-1", "thread_revision": 0, "nonce": "jan-bootstrap"},
    )
    changed = api.set_permission_mode("read-only", boot["context"])
    listing = api.list_available_tools(changed["context"])
    assert listing["ok"]
    assert all(not item["mutating"] for item in listing["tools"])


def test_confirm_mode_returns_structured_approval_error(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("notes", encoding="utf-8")
    api = OpenMontageMCP(root=tmp_path, pipeline_dir=tmp_path / "projects")
    boot = api.bootstrap_conversation(
        "film", "Film", "cinematic",
        {"conversation_id": "chat-1", "thread_revision": 0, "nonce": "jan-bootstrap"},
    )
    result = api.register_inputs([str(source)], "reference", boot["context"])
    assert not result["ok"]
    assert result["category"] == "approval_required"
    assert result["next_actions"]
