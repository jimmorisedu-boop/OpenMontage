from __future__ import annotations

from typing import Any

from tools.tool_registry import ToolRegistry


def structured_error(category: str, attempted: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "operation_id": "",
        "category": category,
        "attempted": attempted,
        "message": message,
        "retained_work": [],
        "next_actions": ["Inspect the reported blocker and retry the same operation."],
        "recommended_action": "Resolve the blocker without changing provider or model.",
    }


class ToolAdapter:
    def __init__(self, *, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()
        self.registry.discover()

    def run(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self.registry.get(name)
        if tool is None:
            return structured_error("blocked", name, f"Unknown OpenMontage tool: {name}")
        try:
            result = tool.execute(params)
        except Exception as exc:
            return structured_error("tool_error", name, str(exc))
        if not result.success:
            return structured_error("tool_error", name, result.error or "Tool failed")
        return {
            "ok": True,
            "data": result.data,
            "artifacts": result.artifacts,
            "cost_usd": result.cost_usd,
        }

