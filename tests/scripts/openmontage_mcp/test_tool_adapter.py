from __future__ import annotations

from tools.base_tool import BaseTool, ToolResult
from scripts.openmontage_mcp.tool_adapter import ToolAdapter


class GoodTool(BaseTool):
    name = "good"
    def execute(self, inputs):
        return ToolResult(success=True, data={"echo": inputs["value"]})


class BadTool(BaseTool):
    name = "bad"
    def execute(self, inputs):
        raise RuntimeError("boom")


class FakeRegistry:
    def __init__(self): self.tools = {"good": GoodTool(), "bad": BadTool()}
    def discover(self): return list(self.tools)
    def get(self, name): return self.tools.get(name)
    def list_all(self): return list(self.tools)


def test_adapter_translates_tool_result_and_exception():
    adapter = ToolAdapter(registry=FakeRegistry())
    success = adapter.run("good", {"value": 7})
    assert success == {"ok": True, "data": {"echo": 7}, "artifacts": [], "cost_usd": 0.0}
    failed = adapter.run("bad", {})
    assert not failed["ok"]
    assert failed["category"] == "tool_error"
    assert failed["attempted"] == "bad"


def test_adapter_rejects_unknown_tools():
    result = ToolAdapter(registry=FakeRegistry()).run("missing", {})
    assert not result["ok"]
    assert result["category"] == "blocked"
