"""Collect a movable project bundle containing only actually referenced inputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from tools.base_tool import BaseTool, Determinism, ToolResult, ToolRuntime, ToolStability, ToolTier


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strings(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


class ProjectCollector(BaseTool):
    name = "project_collector"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "project_export"
    provider = "openmontage"
    stability = ToolStability.PRODUCTION
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    side_effects = ["creates a self-contained project export at the approved destination"]

    def __init__(self, *, pipeline_dir: Path | None = None) -> None:
        self.pipeline_dir = (pipeline_dir or Path("projects")).resolve()

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        project_id = str(inputs["project_id"])
        include_conversation = bool(inputs.get("include_conversation", True))
        source = (self.pipeline_dir / project_id).resolve()
        destination = Path(inputs["destination"]).expanduser().resolve()
        if not (source / "project.json").is_file():
            return ToolResult(success=False, error=f"Project does not exist: {project_id}")
        if destination == source or destination.is_relative_to(source):
            return ToolResult(success=False, error="Collection destination cannot be inside the source project")
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            return ToolResult(success=False, error="Collection destination already exists and is not empty")
        staging = destination.with_name(destination.name + ".partial")
        if staging == source or staging.is_relative_to(source):
            return ToolResult(success=False, error="Collection staging path is unsafe")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        warnings: list[str] = []

        try:
            for directory in ("artifacts", "assets", "history", "renders"):
                path = source / directory
                if path.is_dir():
                    shutil.copytree(path, staging / directory, dirs_exist_ok=True)
            for path in source.glob("checkpoint_*.json"):
                self._copy_file(path, staging / path.name)
            for filename in ("project.json", "decision_log.json"):
                path = source / filename
                if path.is_file():
                    self._copy_file(path, staging / filename)
            conversation = source / "conversation.json"
            if include_conversation and conversation.is_file():
                self._copy_file(conversation, staging / conversation.name)

            input_manifest_path = source / "artifacts" / "input_manifest.json"
            manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
            known = {item["id"] for item in manifest.get("inputs", [])}
            used: set[str] = set()
            scan_paths = [path for path in (source / "artifacts").glob("*.json") if path.name != "input_manifest.json"]
            decision_log = source / "decision_log.json"
            if decision_log.is_file():
                scan_paths.append(decision_log)
            for path in scan_paths:
                try:
                    used.update(value for value in _strings(json.loads(path.read_text("utf-8"))) if value in known)
                except (OSError, json.JSONDecodeError):
                    warnings.append(f"Could not inspect references in {path.name}")

            collected_inputs = []
            copied_input_paths = []
            for item in manifest.get("inputs", []):
                if item["id"] not in used:
                    continue
                original = Path(item["path"])
                if not original.is_file():
                    warnings.append(f"Referenced source is missing: {original}")
                    continue
                safe_name = f"{item['id']}-{original.name}"
                target = staging / "inputs" / safe_name
                self._copy_file(original, target)
                rewritten = dict(item)
                rewritten["path"] = str(Path("inputs") / safe_name)
                provenance = dict(rewritten.get("provenance", {}))
                provenance["collected_from"] = str(original)
                rewritten["provenance"] = provenance
                rewritten["sha256"] = _sha256(target)
                collected_inputs.append(rewritten)
                copied_input_paths.append(str(target.relative_to(staging)))
            manifest["inputs"] = collected_inputs
            (staging / "artifacts" / "input_manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            files = []
            for path in sorted((path for path in staging.rglob("*") if path.is_file()), key=str):
                files.append(
                    {"path": str(path.relative_to(staging)), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
                )
            collection = {
                "version": "1.0",
                "project_id": project_id,
                "copied_inputs": copied_input_paths,
                "warnings": warnings,
                "files": files,
            }
            collection_path = staging / "collection_manifest.json"
            collection_path.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")
            for entry in files:
                if _sha256(staging / entry["path"]) != entry["sha256"]:
                    raise OSError(f"Collection hash verification failed: {entry['path']}")
            if destination.exists():
                destination.rmdir()
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(destination)
        except Exception as exc:
            if staging.exists():
                shutil.rmtree(staging)
            return ToolResult(success=False, error=f"Project collection failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "bundle_root": str(destination),
                "copied_inputs": copied_input_paths,
                "manifest": str(destination / "collection_manifest.json"),
                "warnings": warnings,
            },
            artifacts=[str(destination)],
        )
