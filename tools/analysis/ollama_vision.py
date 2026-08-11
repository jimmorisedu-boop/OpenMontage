"""Offline semantic review of sampled frames using a local Ollama vision model."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from lib.providers.ollama import OllamaClient, OllamaError, OllamaResponseError
from tools.base_tool import (
    BaseTool, Determinism, ExecutionMode, ResourceProfile, ToolResult,
    ToolRuntime, ToolStability, ToolStatus, ToolTier,
)


PROMPT_VERSION = "openmontage-vision-v1"
REVIEW_MODES = {"content", "continuity", "crop", "select", "full"}

FRAME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["timestamp", "scene_id", "description", "issues", "confidence"],
    "properties": {
        "timestamp": {"type": "number"},
        "scene_id": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "people": {"type": "array", "items": {"type": "string"}},
        "objects": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": {"type": "string"}},
        "on_screen_text": {"type": "array", "items": {"type": "string"}},
        "issues": {"type": "array", "items": {"type": "string"}},
        "continuity": {"type": "string"},
        "crop_suitability": {"type": "string"},
        "selection_rank": {"type": ["integer", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["frames", "summary"],
    "properties": {
        "frames": {"type": "array", "items": FRAME_SCHEMA},
        "summary": {"type": "string"},
        "provenance": {"type": "object"},
    },
}


def _timestamp(frame: dict[str, Any]) -> float:
    return float(frame.get("timestamp", frame.get("timestamp_seconds", 0.0)))


class OllamaVisionReview(BaseTool):
    name = "ollama_vision_review"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "ollama"
    runtime = ToolRuntime.LOCAL_GPU
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    dependencies = ["cmd:ollama", "python:requests", "python:jsonschema"]
    install_instructions = "Provide Ollama and both model files through offline installation media."
    agent_skills = ["video-understand"]
    capabilities = ["semantic_frame_review", "continuity_review", "crop_review", "best_frame_selection"]
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=4096, vram_mb=12000, disk_mb=100, network_required=False)
    side_effects = ["writes structured review JSON under the project artifact directory"]
    input_schema = {
        "type": "object",
        "required": ["frames", "mode", "output_path"],
        "properties": {
            "frames": {"type": "array", "minItems": 1, "maxItems": 20},
            "mode": {"type": "string", "enum": sorted(REVIEW_MODES)},
            "target_aspect_ratio": {"type": "string"},
            "output_path": {"type": "string"},
            "model": {"type": "string"},
        },
    }
    output_schema = OUTPUT_SCHEMA

    def __init__(self, client: OllamaClient | None = None):
        self.client = client

    def _client(self) -> OllamaClient:
        return self.client or OllamaClient(timeout_seconds=180)

    def get_status(self) -> ToolStatus:
        try:
            client = self._client()
            model = os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b")
            return ToolStatus.AVAILABLE if client.health() and model in client.list_models() else ToolStatus.UNAVAILABLE
        except OllamaError:
            return ToolStatus.UNAVAILABLE

    def _cache_key(self, frames: list[dict[str, Any]], mode: str, aspect: str, model: str) -> str:
        digest = hashlib.sha256()
        digest.update(f"{model}\0{mode}\0{aspect}\0{PROMPT_VERSION}".encode())
        for frame in frames:
            path = Path(frame["path"]).resolve()
            digest.update(path.read_bytes())
            digest.update(f"\0{_timestamp(frame)}\0{frame.get('scene_id')}".encode())
        return digest.hexdigest()

    def _prompt(self, frames: list[dict[str, Any]], mode: str, aspect: str) -> str:
        manifest = [
            {"index": index, "timestamp": _timestamp(frame), "scene_id": frame.get("scene_id")}
            for index, frame in enumerate(frames)
        ]
        return (
            "Review these ordered video frames for editing. Return JSON matching the supplied schema. "
            "Describe only visible evidence; do not infer identities or unseen events. "
            f"Mode: {mode}. Target aspect ratio: {aspect or 'not specified'}. "
            f"Preserve these timestamps and scene IDs exactly: {json.dumps(manifest, ensure_ascii=False)}"
        )

    @staticmethod
    def _aligned(result: dict[str, Any], frames: list[dict[str, Any]]) -> bool:
        returned = result.get("frames") or []
        if len(returned) != len(frames):
            return False
        return all(
            abs(float(item.get("timestamp", -1)) - _timestamp(source)) < 0.001
            and item.get("scene_id") == source.get("scene_id")
            for item, source in zip(returned, frames)
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        frames = list(inputs.get("frames") or [])
        mode = str(inputs.get("mode") or "")
        if not 1 <= len(frames) <= 20:
            return ToolResult(success=False, error="frames must contain between 1 and 20 items")
        if mode not in REVIEW_MODES:
            return ToolResult(success=False, error=f"unsupported review mode: {mode}")
        paths = [Path(str(frame.get("path", ""))).resolve() for frame in frames]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            return ToolResult(success=False, error=f"frame not found: {missing[0]}")

        output_path = Path(inputs["output_path"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        model = str(inputs.get("model") or os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b"))
        aspect = str(inputs.get("target_aspect_ratio") or "")
        key = self._cache_key(frames, mode, aspect, model)
        if output_path.is_file():
            try:
                cached = json.loads(output_path.read_text(encoding="utf-8"))
                if cached.get("provenance", {}).get("cache_key") == key:
                    cached["provenance"]["cache_status"] = "hit"
                    return ToolResult(success=True, data=cached, artifacts=[str(output_path)], model=model)
            except (OSError, ValueError):
                pass

        client = self._client()
        try:
            result = client.chat_json(
                model=model,
                prompt=self._prompt(frames, mode, aspect),
                image_paths=[str(path) for path in paths],
                schema=OUTPUT_SCHEMA,
                num_ctx=8192,
                keep_alive=0,
            )
            try:
                validate(result, OUTPUT_SCHEMA)
                if not self._aligned(result, frames):
                    raise ValidationError("frame timestamps or scene IDs do not match input")
            except ValidationError:
                result = client.chat_json(
                    model=model,
                    prompt="Repair the previous answer. Return only a complete JSON object matching the schema and frame manifest.\n" + self._prompt(frames, mode, aspect),
                    image_paths=[str(path) for path in paths],
                    schema=OUTPUT_SCHEMA,
                    num_ctx=8192,
                    keep_alive=0,
                )
                validate(result, OUTPUT_SCHEMA)
                if not self._aligned(result, frames):
                    raise OllamaResponseError("vision response timestamps or scene IDs do not match input")
            result["provenance"] = {
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "cache_key": key,
                "cache_status": "miss",
                "source_hashes": [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths],
            }
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return ToolResult(
                success=True, data=result, artifacts=[str(output_path)],
                duration_seconds=round(time.monotonic() - started, 2), model=model,
            )
        except (OllamaError, ValidationError, OSError) as exc:
            return ToolResult(success=False, error=str(exc), model=model)
        finally:
            try:
                client.unload(model)
            except OllamaError:
                pass
