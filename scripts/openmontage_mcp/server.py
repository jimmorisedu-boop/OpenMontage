from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from lib.agent_permissions import (
    OperationKind,
    PermissionContext,
    PermissionDenied,
    PermissionMode,
    authorize,
    set_permission_mode,
)
from lib.checkpoint import init_project
from lib.input_manifest import InputPriority, register_inputs
from scripts.openmontage_mcp.context import ContextStore, ContextViolation
from scripts.openmontage_mcp.progress import OperationStore
from scripts.openmontage_mcp.tool_adapter import ToolAdapter, structured_error
from tools.analysis.url_import_gateway import URLImportGateway
from tools.publishers.project_collector import ProjectCollector


HiddenContext = Annotated[dict[str, Any], Field(alias="_openmontage_context")]


class OpenMontageMCP:
    def __init__(self, *, root: Path, pipeline_dir: Path) -> None:
        self.root = root.resolve()
        self.pipeline_dir = pipeline_dir.resolve()
        self.state_root = self.root / "runtime" / "state"
        self.contexts = ContextStore(self.state_root)
        self.operations = OperationStore()
        self.adapter = ToolAdapter()

    @staticmethod
    def _error(category: str, attempted: str, exc: Exception):
        result = structured_error(category, attempted, str(exc))
        if category == "approval_required":
            result["next_actions"] = ["Approve this exact operation in Jan, then retry with its one-time token."]
            result["recommended_action"] = "Review the target paths before approving."
        return result

    def bootstrap_conversation(self, project_id: str, title: str, pipeline_type: str, _openmontage_context: dict[str, Any]):
        try:
            project = init_project(project_id, title=title, pipeline_type=pipeline_type, pipeline_dir=self.pipeline_dir)
            ctx = PermissionContext(
                str(_openmontage_context.get("conversation_id", "")), project_id, project, self.state_root, ()
            )
            state = set_permission_mode(ctx, PermissionMode.CONFIRM)
            context = self.contexts.bootstrap(project_id, _openmontage_context, state["revision"])
            return {"ok": True, "project_root": str(project), "permission_mode": "confirm", "context": context}
        except Exception as exc:
            return self._error("blocked", "bootstrap_conversation", exc)

    def _permission_context(self, _openmontage_context: dict[str, Any]):
        record = self.contexts.validate(_openmontage_context)
        project = self.pipeline_dir / record["project_id"]
        manifest_path = project / "artifacts" / "input_manifest.json"
        declared = ()
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            declared = tuple(Path(item["path"]) for item in manifest.get("inputs", []))
        return record, PermissionContext(
            record["conversation_id"], record["project_id"], project, self.state_root, declared
        )

    def set_permission_mode(self, mode: str, _openmontage_context: dict[str, Any]):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            state = set_permission_mode(ctx, PermissionMode(mode))
            record["thread_revision"] = state["revision"]
            self.contexts.write(record)
            return {"ok": True, "permission_mode": mode, "context": dict(record)}
        except Exception as exc:
            return self._error("blocked", "set_permission_mode", exc)

    def inspect_project(self, _openmontage_context: dict[str, Any]):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            return {
                "ok": True,
                "project_id": ctx.project_id,
                "project_root": str(ctx.project_root),
                "checkpoint_files": sorted(path.name for path in ctx.project_root.glob("checkpoint_*.json")),
            }
        except Exception as exc:
            return self._error("blocked", "inspect_project", exc)

    def register_inputs(self, paths: list[str], priority: str, _openmontage_context: dict[str, Any], approval_token: str | None = None):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            mode = PermissionMode(json.loads((self.state_root / "conversations" / f"{ctx.conversation_id}.json").read_text("utf-8"))["mode"])
            authorize(ctx, mode, OperationKind.WRITE, [ctx.project_root / "artifacts" / "input_manifest.json"], approval_token)
            manifest = register_inputs(ctx.project_id, paths, priority=InputPriority(priority), pipeline_dir=self.pipeline_dir)
            return {"ok": True, "manifest": manifest}
        except PermissionDenied as exc:
            return self._error("approval_required" if "approval" in str(exc).lower() else "blocked", "register_inputs", exc)
        except Exception as exc:
            return self._error("tool_error", "register_inputs", exc)

    def list_available_tools(self, _openmontage_context: dict[str, Any]):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            state = json.loads((self.state_root / "conversations" / f"{ctx.conversation_id}.json").read_text("utf-8"))
            read_only = state["mode"] == PermissionMode.READ_ONLY.value
            tools = []
            for name in self.adapter.registry.list_all():
                tool = self.adapter.registry.get(name)
                mutating = bool(getattr(tool, "side_effects", []))
                if not (read_only and mutating):
                    tools.append({"name": name, "mutating": mutating, "capability": getattr(tool, "capability", "generic")})
            return {"ok": True, "tools": tools}
        except Exception as exc:
            return self._error("blocked", "list_available_tools", exc)

    def run_openmontage_tool(self, name: str, params: dict[str, Any], _openmontage_context: dict[str, Any], approval_token: str | None = None):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            tool = self.adapter.registry.get(name)
            if tool is None:
                return structured_error("blocked", name, "Unknown tool")
            mutating = bool(getattr(tool, "side_effects", []))
            if mutating:
                state = json.loads((self.state_root / "conversations" / f"{ctx.conversation_id}.json").read_text("utf-8"))
                target = Path(params.get("output_path") or ctx.project_root)
                authorize(ctx, PermissionMode(state["mode"]), OperationKind.WRITE, [target], approval_token)
            operation_id = self.operations.start(name)
            result = self.adapter.run(name, params)
            result["operation_id"] = operation_id
            self.operations.finish(operation_id, result)
            return result
        except PermissionDenied as exc:
            return self._error("approval_required" if "approval" in str(exc).lower() else "blocked", name, exc)
        except Exception as exc:
            return self._error("tool_error", name, exc)

    def import_public_url(self, url: str, bulk_approved: bool, _openmontage_context: dict[str, Any], expected_item_count: int | None = None, approval_token: str | None = None):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            state = json.loads((self.state_root / "conversations" / f"{ctx.conversation_id}.json").read_text("utf-8"))
            authorize(ctx, PermissionMode(state["mode"]), OperationKind.DOWNLOAD, [ctx.project_root / "inputs" / "downloads"], approval_token)
            result = URLImportGateway(root=self.root, pipeline_dir=self.pipeline_dir).execute(
                {"project_id": ctx.project_id, "url": url, "bulk_approved": bulk_approved, "expected_item_count": expected_item_count}
            )
            return {"ok": result.success, "data": result.data, "artifacts": result.artifacts, "error": result.error}
        except PermissionDenied as exc:
            return self._error("approval_required" if "approval" in str(exc).lower() else "blocked", "import_public_url", exc)
        except Exception as exc:
            return self._error("tool_error", "import_public_url", exc)

    def collect_project(self, destination: str, include_conversation: bool, _openmontage_context: dict[str, Any], approval_token: str | None = None):
        try:
            record, ctx = self._permission_context(_openmontage_context)
            state = json.loads((self.state_root / "conversations" / f"{ctx.conversation_id}.json").read_text("utf-8"))
            authorize(ctx, PermissionMode(state["mode"]), OperationKind.WRITE, [ctx.project_root], approval_token)
            result = ProjectCollector(pipeline_dir=self.pipeline_dir).execute(
                {"project_id": ctx.project_id, "destination": destination, "include_conversation": include_conversation}
            )
            return {"ok": result.success, "data": result.data, "error": result.error}
        except PermissionDenied as exc:
            return self._error("approval_required" if "approval" in str(exc).lower() else "blocked", "collect_project", exc)
        except Exception as exc:
            return self._error("tool_error", "collect_project", exc)

    def get_operation_status(self, operation_id: str, _openmontage_context: dict[str, Any]):
        try:
            self.contexts.validate(_openmontage_context)
            return {"ok": True, **self.operations.get(operation_id)}
        except Exception as exc:
            return self._error("blocked", "get_operation_status", exc)

    def cancel_operation(self, operation_id: str, _openmontage_context: dict[str, Any]):
        try:
            self.contexts.validate(_openmontage_context)
            return {"ok": self.operations.cancel(operation_id), "operation_id": operation_id}
        except Exception as exc:
            return self._error("blocked", "cancel_operation", exc)


def create_server(*, root: Path | None = None, pipeline_dir: Path | None = None) -> FastMCP:
    root = (root or Path(__file__).resolve().parents[2]).resolve()
    api = OpenMontageMCP(root=root, pipeline_dir=pipeline_dir or root / "projects")
    server = FastMCP("OpenMontage", instructions="Local bounded tools for the OpenMontage chat shell")

    @server.tool(name="bootstrap_conversation")
    def bootstrap_conversation(project_id: str, title: str, pipeline_type: str, openmontage_context: HiddenContext):
        return api.bootstrap_conversation(project_id, title, pipeline_type, openmontage_context)

    @server.tool(name="set_permission_mode")
    def set_mode(mode: str, openmontage_context: HiddenContext):
        return api.set_permission_mode(mode, openmontage_context)

    @server.tool(name="register_inputs")
    def register(paths: list[str], priority: str, openmontage_context: HiddenContext, approval_token: str | None = None):
        return api.register_inputs(paths, priority, openmontage_context, approval_token)

    @server.tool(name="import_public_url")
    def import_url(url: str, bulk_approved: bool, openmontage_context: HiddenContext, expected_item_count: int | None = None, approval_token: str | None = None):
        return api.import_public_url(url, bulk_approved, openmontage_context, expected_item_count, approval_token)

    @server.tool(name="inspect_project")
    def inspect(openmontage_context: HiddenContext):
        return api.inspect_project(openmontage_context)

    @server.tool(name="list_available_tools")
    def list_tools(openmontage_context: HiddenContext):
        return api.list_available_tools(openmontage_context)

    @server.tool(name="run_openmontage_tool")
    def run_tool(name: str, params: dict[str, Any], openmontage_context: HiddenContext, approval_token: str | None = None):
        return api.run_openmontage_tool(name, params, openmontage_context, approval_token)

    @server.tool(name="collect_project")
    def collect(destination: str, include_conversation: bool, openmontage_context: HiddenContext, approval_token: str | None = None):
        return api.collect_project(destination, include_conversation, openmontage_context, approval_token)

    @server.tool(name="get_operation_status")
    def operation_status(operation_id: str, openmontage_context: HiddenContext):
        return api.get_operation_status(operation_id, openmontage_context)

    @server.tool(name="cancel_operation")
    def cancel(operation_id: str, openmontage_context: HiddenContext):
        return api.cancel_operation(operation_id, openmontage_context)

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
