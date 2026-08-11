# Local LLM Video Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows-first, air-gapped OpenMontage workflow using Codex CLI with `gpt-oss:20b` for orchestration and loopback-only Ollama-hosted `qwen3.5:9b` for schema-validated frame review.

**Architecture:** Codex CLI remains the ready-made agent shell and follows the repository's existing agent-first contracts. A focused Ollama HTTP client and `BaseTool` visual provider add frame understanding without creating a second orchestrator, while an opt-in GPU guard ensures Ollama models are unloaded before non-Ollama local GPU tools run.

**Tech Stack:** Python 3.11+, Pydantic 2, requests, jsonschema, pytest, PowerShell 7/Windows PowerShell, Ollama native HTTP API, Codex CLI, FFmpeg.

## Global Constraints

- Target Windows machine has exactly 16 GB VRAM and 64 GB system RAM.
- Pipeline orchestration uses Codex CLI and `gpt-oss:20b`; do not add a Python agent loop.
- Semantic frame review uses `qwen3.5:9b`; it cannot invoke tools or act as an autonomous agent.
- The initial orchestrator context is 32,768 tokens.
- Orchestrator, vision, and local generation models must be resident sequentially, never concurrently.
- Visual requests contain at most 20 frames; normal scene-guided use is one to three frames per scene.
- No cloud LLM fallback, automatic model download, global approval bypass, or silent provider substitution.
- No web search, URL ingestion, media download, publishing, remote Ollama host,
  network-assisted setup, or execution of API/HYBRID/network-required tools.
- Strict offline composition uses FFmpeg; do not invoke npm/npx/Remotion/
  HyperFrames or any project that can resolve web fonts, CDN scripts, or registries.
- Do not install ComfyUI/WAN, Piper, ACE-Step, Real-ESRGAN, CodeFormer, rembg, Wav2Lip, SadTalker, or another optional generation/enhancement stack.
- Every generated artifact path is explicitly under `projects/<project-id>/`.
- Preserve the user's existing `remotion-composer/package-lock.json` modification.

## File Map

- `lib/providers/ollama.py` — transport-only Ollama client and typed errors.
- `lib/gpu_guard.py` — opt-in unloading/recheck boundary for non-Ollama `LOCAL_GPU` tools.
- `tools/base_tool.py` — invokes the GPU guard before relevant tool execution.
- `tools/analysis/ollama_vision.py` — registered semantic frame review provider, validation, repair, and cache.
- `tests/lib/test_ollama_provider.py` — fake-HTTP client tests.
- `tests/lib/test_gpu_guard.py` — lifecycle and BaseTool guard tests.
- `tests/tools/test_ollama_vision.py` — contract, cache, schema, execution, and registry tests.
- `pipeline_defs/{talking-head,clip-factory,hybrid,screen-demo,podcast-repurpose,cinematic,localization-dub}.yaml` — allows semantic review during scene planning.
- `skills/creative/video-understand-usage.md` — routing between deterministic metrics and Ollama semantic review.
- `.agents/skills/video-understand/SKILL.md` — Layer 3 Ollama/Qwen request and VRAM-lifecycle guidance.
- `skills/pipelines/*/scene-director.md` for the seven source-led pipelines — instructs bounded use and degraded behavior.
- `scripts/__init__.py` — makes launcher preflight importable in tests.
- `scripts/local_agent_preflight.py` — dependency/model/profile checks with human and JSON output.
- `scripts/setup_local_agent.ps1` — explicit model pulls and 32K derived Ollama profile creation.
- `scripts/start_local_agent.ps1` — validated Codex CLI launch from repository root.
- `config/ollama/gpt-oss-20b-32k.Modelfile` — fixed 32K local profile derived from `gpt-oss:20b`.
- `tests/scripts/test_local_agent_preflight.py` — mocked preflight behavior.
- `tests/integration/test_local_llm_smoke.py` — opt-in two-model local smoke test.
- `README.md` and `docs/PROVIDERS.md` — installation, usage, VRAM lifecycle, and troubleshooting.
- `docs/LOCAL_TEXT_EDITING_GUIDE.md` — end-to-end operator handbook and copyable local editing requests.
- `skills/creative/video-editing.md` — shared evidence-driven editorial decision playbook.
- `skills/pipelines/{talking-head,clip-factory,hybrid,screen-demo,podcast-repurpose,cinematic,localization-dub}/edit-director.md` — routes source-led edits through the shared playbook.
- `tests/contracts/test_local_editing_guidance.py` — verifies handbook coverage and agent routing.

---

### Task 1: Ollama Transport Client

**Files:**
- Create: `lib/providers/ollama.py`
- Create: `tests/lib/test_ollama_provider.py`

**Interfaces:**
- Produces: `OllamaClient(base_url: str | None = None, timeout_seconds: float = 120.0)`.
- Produces: `health() -> bool`, `list_models() -> set[str]`, `running_models() -> list[dict[str, Any]]`, `has_model(tag: str) -> bool`, `show_model(tag: str) -> dict[str, Any]`, `model_num_ctx(tag: str) -> int | None`, `chat_json(...) -> dict[str, Any]`, and `unload(model: str) -> None`.
- Produces typed errors: `OllamaError`, `OllamaConnectionError`, `OllamaModelMissingError`, `OllamaResponseError`.
- Consumes: `requests`, `OLLAMA_BASE_URL`, Ollama `/api/tags`, `/api/ps`, and `/api/chat`.

- [ ] **Step 1: Write fake-response and health/model-list tests**

```python
# tests/lib/test_ollama_provider.py
from __future__ import annotations

import requests
import pytest

from lib.providers.ollama import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelMissingError,
    OllamaResponseError,
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text="ok"):
        self.payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}: {self.text}")


def test_health_and_model_queries(monkeypatch):
    def fake_get(url, timeout):
        if url.endswith("/api/tags"):
            return FakeResponse({"models": [{"name": "gpt-oss:20b"}, {"model": "qwen3.5:9b"}]})
        if url.endswith("/api/ps"):
            return FakeResponse({"models": [{"name": "gpt-oss:20b", "size_vram": 12_000}]})
        raise AssertionError(url)

    monkeypatch.setattr(requests, "get", fake_get)
    client = OllamaClient("http://ollama.test")
    assert client.health()
    assert client.list_models() == {"gpt-oss:20b", "qwen3.5:9b"}
    assert client.has_model("qwen3.5:9b")
    assert client.running_models()[0]["name"] == "gpt-oss:20b"


def test_connection_error_is_typed(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")))
    with pytest.raises(OllamaConnectionError, match="http://ollama.test"):
        OllamaClient("http://ollama.test").list_models()
```

- [ ] **Step 2: Run the focused tests and verify the module is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_ollama_provider.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'lib.providers.ollama'`.

- [ ] **Step 3: Implement URL normalization, GET helpers, health, tags, and running models**

```python
# lib/providers/ollama.py
from __future__ import annotations

import json
import os
from typing import Any

import requests


class OllamaError(RuntimeError):
    pass


class OllamaConnectionError(OllamaError):
    pass


class OllamaModelMissingError(OllamaError):
    pass


class OllamaResponseError(OllamaError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 120.0):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}{path}", timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise OllamaConnectionError(f"Ollama request failed at {self.base_url}{path}: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise OllamaResponseError(f"Ollama returned invalid JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise OllamaResponseError(f"Ollama returned a non-object payload for {path}")
        return payload

    def health(self) -> bool:
        try:
            self._get("/api/tags")
            return True
        except OllamaError:
            return False

    def list_models(self) -> set[str]:
        models = self._get("/api/tags").get("models", [])
        return {str(item.get("name") or item.get("model")) for item in models if item.get("name") or item.get("model")}

    def running_models(self) -> list[dict[str, Any]]:
        models = self._get("/api/ps").get("models", [])
        return [item for item in models if isinstance(item, dict)]

    def has_model(self, tag: str) -> bool:
        return tag in self.list_models()
```

- [ ] **Step 4: Add tests for structured chat, malformed content, missing models, and unload payloads**

```python
def test_chat_json_and_unload(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, timeout):
        return FakeResponse({"models": [{"name": "qwen3.5:9b"}, {"name": "gpt-oss:20b"}]})

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        if json.get("messages"):
            return FakeResponse({"message": {"content": '{"frames": []}'}})
        return FakeResponse({"done": True})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    client = OllamaClient("http://ollama.test", timeout_seconds=9)
    result = client.chat_json(
        model="qwen3.5:9b",
        prompt="review",
        image_paths=[],
        schema={"type": "object"},
        num_ctx=8192,
        keep_alive=0,
    )
    client.unload("gpt-oss:20b")
    assert result == {"frames": []}
    assert calls[0][1]["format"] == {"type": "object"}
    assert calls[0][1]["options"]["num_ctx"] == 8192
    assert calls[0][1]["keep_alive"] == 0
    assert calls[1][1] == {"model": "gpt-oss:20b", "keep_alive": 0}


def test_chat_rejects_missing_model(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"models": []}))
    with pytest.raises(OllamaModelMissingError, match="qwen3.5:9b"):
        OllamaClient("http://ollama.test").chat_json(
            model="qwen3.5:9b", prompt="x", image_paths=[], schema={"type": "object"}
        )


def test_chat_rejects_non_json_content(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"models": [{"name": "qwen3.5:9b"}]}))
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"message": {"content": "not-json"}}))
    with pytest.raises(OllamaResponseError, match="valid JSON"):
        OllamaClient("http://ollama.test").chat_json(
            model="qwen3.5:9b", prompt="x", image_paths=[], schema={"type": "object"}
        )


def test_model_num_ctx_reads_derived_profile(monkeypatch):
    def fake_post(url, json, timeout):
        assert url.endswith("/api/show")
        assert json == {"model": "openmontage-gpt-oss:20b-32k"}
        return FakeResponse({"parameters": "num_ctx                       32768\nstop                          <|end|>"})

    monkeypatch.setattr(requests, "post", fake_post)
    client = OllamaClient("http://ollama.test")
    assert client.model_num_ctx("openmontage-gpt-oss:20b-32k") == 32768
```

- [ ] **Step 5: Implement native multimodal chat and unload**

Add to `OllamaClient`:

```python
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}{path}", json=payload, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise OllamaConnectionError(f"Ollama request failed at {self.base_url}{path}: {exc}") from exc
        except (ValueError, TypeError) as exc:
            raise OllamaResponseError(f"Ollama returned invalid JSON for {path}") from exc
        if not isinstance(body, dict):
            raise OllamaResponseError(f"Ollama returned a non-object payload for {path}")
        return body

    def chat_json(
        self,
        *,
        model: str,
        prompt: str,
        image_paths: list[str],
        schema: dict[str, Any],
        num_ctx: int = 8192,
        keep_alive: int | str = 0,
    ) -> dict[str, Any]:
        import base64
        from pathlib import Path

        if not self.has_model(model):
            raise OllamaModelMissingError(f"Ollama model is not installed: {model}")
        images = [base64.b64encode(Path(path).read_bytes()).decode("ascii") for path in image_paths]
        body = self._post("/api/chat", {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": images}],
            "format": schema,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_ctx": num_ctx},
        })
        content = body.get("message", {}).get("content")
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OllamaResponseError("Ollama message content is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise OllamaResponseError("Ollama structured response must be a JSON object")
        return parsed

    def unload(self, model: str) -> None:
        self._post("/api/generate", {"model": model, "keep_alive": 0})

    def show_model(self, tag: str) -> dict[str, Any]:
        return self._post("/api/show", {"model": tag})

    def model_num_ctx(self, tag: str) -> int | None:
        import re
        parameters = str(self.show_model(tag).get("parameters", ""))
        match = re.search(r"(?m)^num_ctx\s+(\d+)\s*$", parameters)
        return int(match.group(1)) if match else None
```

- [ ] **Step 6: Run the client tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_ollama_provider.py -v
```

Expected: all tests pass with no live Ollama requests.

- [ ] **Step 7: Commit Task 1**

```powershell
git add lib/providers/ollama.py tests/lib/test_ollama_provider.py
git commit -m "feat: add local Ollama provider client"
```

---

### Task 2: Schema-Validated Ollama Vision Tool and Cache

**Files:**
- Create: `tools/analysis/ollama_vision.py`
- Create: `tests/tools/test_ollama_vision.py`

**Interfaces:**
- Consumes: `OllamaClient.chat_json()`, `OllamaClient.unload()`, ordered frame objects `{path, timestamp, scene_id?}`.
- Produces: discoverable `OllamaVisionReview(BaseTool)` named `ollama_vision_review` with `capability="analysis"`, `provider="ollama"`, `runtime=LOCAL_GPU`.
- Produces: JSON artifact at caller-supplied `output_path`, `ToolResult.data` containing `frames`, `duplicate_groups`, `summary`, `model`, `schema_version`, `source_hashes`, and `cache_hit`.

- [ ] **Step 1: Write contract, status, and registry tests**

```python
# tests/tools/test_ollama_vision.py
from pathlib import Path

from lib.providers.ollama import OllamaResponseError
from tools.base_tool import BaseTool, ToolRuntime, ToolStatus, ToolTier
from tools.tool_registry import ToolRegistry
from tools.analysis.ollama_vision import OllamaVisionReview


def test_contract_and_discovery(monkeypatch):
    monkeypatch.setattr("tools.analysis.ollama_vision.OllamaClient.health", lambda self: True)
    monkeypatch.setattr("tools.analysis.ollama_vision.OllamaClient.has_model", lambda self, model: True)
    tool = OllamaVisionReview()
    assert issubclass(OllamaVisionReview, BaseTool)
    assert tool.name == "ollama_vision_review"
    assert tool.capability == "analysis"
    assert tool.provider == "ollama"
    assert tool.runtime == ToolRuntime.LOCAL_GPU
    assert tool.tier == ToolTier.ANALYZE
    assert tool.get_status() == ToolStatus.AVAILABLE
    registry = ToolRegistry()
    registry.discover("tools")
    assert registry.get("ollama_vision_review") is not None


def test_status_requires_server_and_model(monkeypatch):
    monkeypatch.setattr("tools.analysis.ollama_vision.OllamaClient.health", lambda self: False)
    assert OllamaVisionReview().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setattr("tools.analysis.ollama_vision.OllamaClient.health", lambda self: True)
    monkeypatch.setattr("tools.analysis.ollama_vision.OllamaClient.has_model", lambda self, model: False)
    assert OllamaVisionReview().get_status() == ToolStatus.UNAVAILABLE
```

- [ ] **Step 2: Run the focused test and verify the tool is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/tools/test_ollama_vision.py -v
```

Expected: collection fails with `ModuleNotFoundError` for `ollama_vision`.

- [ ] **Step 3: Define the tool contract and strict review schema**

Create `tools/analysis/ollama_vision.py` with these constants and class metadata:

```python
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from lib.providers.ollama import OllamaClient, OllamaError, OllamaResponseError
from tools.base_tool import (
    BaseTool, Determinism, ExecutionMode, ResourceProfile,
    ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier,
)

SCHEMA_VERSION = "1.0.0"
PROMPT_VERSION = "1.0.0"
REVIEW_MODES = ["content", "continuity", "crop", "select", "full"]
FRAME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["index", "timestamp", "scene_id", "description", "people", "objects", "actions", "on_screen_text", "issues", "continuity", "crop", "rank", "confidence"],
    "properties": {
        "index": {"type": "integer", "minimum": 0},
        "timestamp": {"type": "number", "minimum": 0},
        "scene_id": {"type": ["string", "integer", "null"]},
        "description": {"type": "string"},
        "people": {"type": "array", "items": {"type": "string"}},
        "objects": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": {"type": "string"}},
        "on_screen_text": {"type": "array", "items": {"type": "string"}},
        "issues": {"type": "array", "items": {"type": "string"}},
        "continuity": {"type": "string", "enum": ["not_applicable", "good", "acceptable", "poor"]},
        "crop": {"type": "object", "additionalProperties": False, "required": ["suitable", "reason"], "properties": {"suitable": {"type": "boolean"}, "reason": {"type": "string"}}},
        "rank": {"type": "integer", "minimum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["frames", "duplicate_groups", "summary"],
    "properties": {
        "frames": {"type": "array", "items": FRAME_SCHEMA},
        "duplicate_groups": {"type": "array", "items": {"type": "array", "items": {"type": "integer", "minimum": 0}}},
        "summary": {"type": "string"},
    },
}
ARTIFACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["frames", "duplicate_groups", "summary", "model", "schema_version", "prompt_version", "source_hashes", "cache_key", "cache_hit"],
    "properties": {
        **REVIEW_SCHEMA["properties"],
        "model": {"type": "string"},
        "schema_version": {"type": "string", "const": SCHEMA_VERSION},
        "prompt_version": {"type": "string", "const": PROMPT_VERSION},
        "source_hashes": {"type": "array", "items": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
        "cache_key": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "cache_hit": {"type": "boolean"},
    },
}


class OllamaVisionReview(BaseTool):
    name = "ollama_vision_review"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "ollama"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU
    dependencies = []
    install_instructions = "Start Ollama and run: ollama pull qwen3.5:9b"
    agent_skills = ["video-understand"]
    capabilities = ["semantic_frame_review", "continuity_review", "crop_review", "best_frame_selection"]
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=4096, vram_mb=7000, disk_mb=100)
    side_effects = ["writes visual review JSON to output_path", "loads and unloads local Ollama models"]
    fallback_tools = []
    input_schema = {
        "type": "object",
        "required": ["frames", "output_path"],
        "properties": {
            "frames": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "object", "required": ["path", "timestamp"], "properties": {"path": {"type": "string"}, "timestamp": {"type": "number"}, "scene_id": {"type": ["string", "integer"]}}}},
            "mode": {"type": "string", "enum": REVIEW_MODES, "default": "full"},
            "target_aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "default": "16:9"},
            "model": {"type": "string", "default": "qwen3.5:9b"},
            "output_path": {"type": "string"},
        },
    }
    output_schema = ARTIFACT_SCHEMA

    def __init__(self, client: OllamaClient | None = None):
        self.client = client or OllamaClient(timeout_seconds=180)
        self.status_client = client or OllamaClient(timeout_seconds=2)

    def get_status(self) -> ToolStatus:
        model = os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b")
        return ToolStatus.AVAILABLE if self.status_client.health() and self.status_client.has_model(model) else ToolStatus.UNAVAILABLE
```

- [ ] **Step 4: Add execution tests for guardrails, cache, repair, provenance, and model switching**

```python
import json


VALID_REVIEW = {
    "frames": [{
        "index": 0, "timestamp": 1.5, "scene_id": "s1",
        "description": "Presenter at a desk", "people": ["presenter"],
        "objects": ["desk"], "actions": ["speaking"], "on_screen_text": [],
        "issues": [], "continuity": "not_applicable",
        "crop": {"suitable": True, "reason": "face remains centered"},
        "rank": 1, "confidence": 0.92,
    }],
    "duplicate_groups": [],
    "summary": "Usable presenter frame",
}


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.unloaded = []
        self.calls = 0

    def health(self): return True
    def has_model(self, model): return True
    def unload(self, model): self.unloaded.append(model)
    def chat_json(self, **kwargs):
        self.calls += 1
        return self.replies.pop(0)


def test_execute_writes_provenance_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ORCHESTRATOR_MODEL", "gpt-oss:20b")
    project = tmp_path / "projects" / "demo"
    frame = project / "assets" / "frames" / "f.jpg"
    output = project / "artifacts" / "visual-review.json"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"jpeg-frame")
    client = FakeClient([VALID_REVIEW])
    tool = OllamaVisionReview(client)
    inputs = {"frames": [{"path": str(frame), "timestamp": 1.5, "scene_id": "s1"}], "output_path": str(output), "mode": "full", "target_aspect_ratio": "9:16"}
    first = tool.execute(inputs)
    second = tool.execute(inputs)
    assert first.success and second.success
    assert first.data["cache_hit"] is False
    assert second.data["cache_hit"] is True
    assert client.calls == 1
    assert client.unloaded == ["gpt-oss:20b", "qwen3.5:9b"]
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["model"] == "qwen3.5:9b"
    assert written["schema_version"] == "1.0.0"
    assert written["prompt_version"] == "1.0.0"
    assert written["source_hashes"]


def test_invalid_first_response_gets_one_repair(tmp_path):
    project = tmp_path / "projects" / "demo"
    frame = project / "f.jpg"
    output = project / "artifacts" / "review.json"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"x")
    client = FakeClient([{"frames": []}, VALID_REVIEW])
    result = OllamaVisionReview(client).execute({"frames": [{"path": str(frame), "timestamp": 1.5, "scene_id": "s1"}], "output_path": str(output)})
    assert result.success
    assert client.calls == 2


def test_invalid_second_response_fails_without_writing(tmp_path):
    project = tmp_path / "projects" / "demo"
    frame = project / "f.jpg"
    output = project / "artifacts" / "review.json"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"x")
    client = FakeClient([{"frames": []}, {"frames": []}])
    result = OllamaVisionReview(client).execute({"frames": [{"path": str(frame), "timestamp": 1.5, "scene_id": "s1"}], "output_path": str(output)})
    assert not result.success
    assert "schema" in result.error.lower()
    assert not output.exists()


def test_non_json_first_response_gets_one_repair(tmp_path):
    project = tmp_path / "projects" / "demo"
    frame = project / "f.jpg"
    output = project / "artifacts" / "review.json"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"x")

    class ParseRepairClient(FakeClient):
        def chat_json(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise OllamaResponseError("message content is not valid JSON")
            return VALID_REVIEW

    client = ParseRepairClient([])
    result = OllamaVisionReview(client).execute({"frames": [{"path": str(frame), "timestamp": 1.5, "scene_id": "s1"}], "output_path": str(output)})
    assert result.success
    assert client.calls == 2
```

- [ ] **Step 5: Implement prompt construction, cache key, validation/repair, and artifact writing**

Add these focused helpers and `execute()` to `OllamaVisionReview`:

```python
    @staticmethod
    def _source_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _cache_key(source_hashes: list[str], model: str, mode: str, aspect: str) -> str:
        raw = json.dumps({"sources": source_hashes, "model": model, "mode": mode, "aspect": aspect, "schema": SCHEMA_VERSION, "prompt": PROMPT_VERSION}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _prompt(frames: list[dict[str, Any]], mode: str, aspect: str, repair_error: str | None = None) -> str:
        metadata = [{"index": i, "timestamp": frame["timestamp"], "scene_id": frame.get("scene_id")} for i, frame in enumerate(frames)]
        repair = f"\nYour previous JSON failed validation: {repair_error}. Return a complete corrected object." if repair_error else ""
        return (
            "Act only as a video editor's visual reviewer. Analyze the ordered images using the matching metadata. "
            "Do not estimate numeric blur, brightness, contrast, or exposure values. "
            f"Review mode: {mode}. Target aspect ratio: {aspect}. Metadata: {json.dumps(metadata, ensure_ascii=False)}. "
            "Copy each supplied index, timestamp, and scene_id exactly into its result. Use concise observable descriptions, flag uncertainty, rank every supplied frame exactly once, and return only the required JSON schema."
            + repair
        )

    @staticmethod
    def _validate_review(review: dict[str, Any], frames: list[dict[str, Any]]) -> None:
        validate(review, REVIEW_SCHEMA)
        reviewed = review["frames"]
        if len(reviewed) != len(frames):
            raise ValidationError("vision response must contain exactly one record per input frame")
        by_index = {item["index"]: item for item in reviewed}
        if set(by_index) != set(range(len(frames))):
            raise ValidationError("vision response frame indexes must match every input exactly once")
        for index, source in enumerate(frames):
            item = by_index[index]
            if item["timestamp"] != source["timestamp"] or item["scene_id"] != source.get("scene_id"):
                raise ValidationError(f"vision response metadata mismatch at frame {index}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = __import__("time").monotonic()
        frames = list(inputs.get("frames") or [])
        if not 1 <= len(frames) <= 20:
            return ToolResult(success=False, error="frames must contain between 1 and 20 items")
        paths = [Path(item["path"]).resolve() for item in frames]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            return ToolResult(success=False, error=f"Frame not found: {missing[0]}")
        output_path = Path(inputs["output_path"]).resolve()
        if "projects" not in {part.lower() for part in output_path.parts}:
            return ToolResult(success=False, error="output_path must be inside projects/<project-id>/")
        model = inputs.get("model") or os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b")
        mode = inputs.get("mode", "full")
        aspect = inputs.get("target_aspect_ratio", "16:9")
        source_hashes = [self._source_hash(path) for path in paths]
        cache_key = self._cache_key(source_hashes, model, mode, aspect)
        cache_path = output_path.parent / "visual-review-cache" / f"{cache_key}.json"
        if cache_path.is_file():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            data["cache_hit"] = True
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return ToolResult(success=True, data=data, artifacts=[str(output_path)], model=model)
        try:
            orchestrator = os.environ.get("OPENMONTAGE_ORCHESTRATOR_MODEL", "gpt-oss:20b")
            self.client.unload(orchestrator)
            try:
                try:
                    review = self.client.chat_json(model=model, prompt=self._prompt(frames, mode, aspect), image_paths=[str(path) for path in paths], schema=REVIEW_SCHEMA, num_ctx=8192, keep_alive=0)
                    self._validate_review(review, frames)
                except (OllamaResponseError, ValidationError) as first_error:
                    review = self.client.chat_json(model=model, prompt=self._prompt(frames, mode, aspect, str(first_error)), image_paths=[str(path) for path in paths], schema=REVIEW_SCHEMA, num_ctx=8192, keep_alive=0)
                    self._validate_review(review, frames)
            finally:
                self.client.unload(model)
        except (OllamaError, ValidationError, OSError, ValueError) as exc:
            return ToolResult(success=False, error=f"Ollama vision review failed schema validation or execution: {exc}")
        data = {**review, "model": model, "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION, "source_hashes": source_hashes, "cache_key": cache_key, "cache_hit": False}
        validate(data, ARTIFACT_SCHEMA)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(data, indent=2, ensure_ascii=False)
        cache_path.write_text(encoded, encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
        elapsed = __import__("time").monotonic() - started
        return ToolResult(success=True, data=data, artifacts=[str(output_path), str(cache_path)], model=model, duration_seconds=round(elapsed, 2))
```

- [ ] **Step 6: Run tool and registry tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/tools/test_ollama_vision.py tests/contracts/test_phase0_contracts.py -v
```

Expected: all tests pass and registry discovery performs no live Ollama generation request.

- [ ] **Step 7: Commit Task 2**

```powershell
git add tools/analysis/ollama_vision.py tests/tools/test_ollama_vision.py
git commit -m "feat: add Ollama visual review tool"
```

---

### Task 3: Enforced Sequential GPU Lifecycle

**Files:**
- Create: `lib/gpu_guard.py`
- Create: `tests/lib/test_gpu_guard.py`
- Modify: `tools/base_tool.py:164-221`

**Interfaces:**
- Consumes: `OllamaClient.running_models()` and `OllamaClient.unload()`.
- Produces: `ensure_ollama_models_unloaded(client: OllamaClient | None = None) -> None`.
- Behavior: enabled only when `OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD=1`; applies before non-Ollama `LOCAL_GPU` tool execution; raises `GpuGuardError` if a configured LLM remains loaded after unload/recheck.

- [ ] **Step 1: Write lifecycle and BaseTool integration tests**

```python
# tests/lib/test_gpu_guard.py
import pytest

from lib.gpu_guard import GpuGuardError, ensure_ollama_models_unloaded
from tools.base_tool import BaseTool, ToolResult, ToolRuntime


class FakeClient:
    def __init__(self, running_sequences):
        self.running_sequences = list(running_sequences)
        self.unloaded = []
    def running_models(self): return self.running_sequences.pop(0)
    def unload(self, model): self.unloaded.append(model)


def test_guard_unloads_configured_models(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD", "1")
    monkeypatch.setenv("OPENMONTAGE_ORCHESTRATOR_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b")
    client = FakeClient([[{"name": "gpt-oss:20b"}, {"name": "qwen3.5:9b"}], []])
    ensure_ollama_models_unloaded(client)
    assert client.unloaded == ["gpt-oss:20b", "qwen3.5:9b"]


def test_guard_blocks_when_model_remains(monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD", "1")
    client = FakeClient([[{"name": "gpt-oss:20b"}], [{"name": "gpt-oss:20b"}]])
    with pytest.raises(GpuGuardError, match="gpt-oss:20b"):
        ensure_ollama_models_unloaded(client)


def test_base_tool_guards_non_ollama_local_gpu(monkeypatch):
    calls = []
    monkeypatch.setenv("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD", "1")
    monkeypatch.setattr("lib.gpu_guard.ensure_ollama_models_unloaded", lambda: calls.append("guard"))

    class LocalGenerator(BaseTool):
        name = "local_generator_for_test"
        runtime = ToolRuntime.LOCAL_GPU
        provider = "comfyui"
        def execute(self, inputs):
            calls.append("execute")
            return ToolResult(success=True)

    assert LocalGenerator().execute({}).success
    assert calls == ["guard", "execute"]
```

- [ ] **Step 2: Run tests and verify the guard module is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_gpu_guard.py -v
```

Expected: collection fails for `lib.gpu_guard`.

- [ ] **Step 3: Implement the opt-in guard**

```python
# lib/gpu_guard.py
from __future__ import annotations

import os

from lib.providers.ollama import OllamaClient, OllamaError


class GpuGuardError(RuntimeError):
    pass


def ensure_ollama_models_unloaded(client: OllamaClient | None = None) -> None:
    if os.environ.get("OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD") != "1":
        return
    ollama = client or OllamaClient(timeout_seconds=15)
    configured = {
        os.environ.get("OPENMONTAGE_ORCHESTRATOR_MODEL", "gpt-oss:20b"),
        os.environ.get("OPENMONTAGE_VISION_MODEL", "qwen3.5:9b"),
    }
    try:
        running = {str(item.get("name") or item.get("model")) for item in ollama.running_models()}
        for model in sorted(configured & running):
            ollama.unload(model)
        remaining = {str(item.get("name") or item.get("model")) for item in ollama.running_models()}
    except OllamaError as exc:
        raise GpuGuardError(f"Cannot verify Ollama GPU state: {exc}") from exc
    blocked = sorted(configured & remaining)
    if blocked:
        raise GpuGuardError(f"Local GPU tool blocked; Ollama models remain loaded: {', '.join(blocked)}")
```

- [ ] **Step 4: Invoke the guard from BaseTool instrumentation**

In `_instrument_execute.wrapper`, immediately before `result = fn(...)`, add:

```python
            if (
                getattr(self, "runtime", None) == ToolRuntime.LOCAL_GPU
                and getattr(self, "provider", None) != "ollama"
            ):
                from lib.gpu_guard import ensure_ollama_models_unloaded
                ensure_ollama_models_unloaded()
```

Keep this inside the existing `try` so Backlot receives the normal error event when the guard blocks execution.

- [ ] **Step 5: Run guard and instrumentation regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_gpu_guard.py tests/contracts/test_backlot_contract.py -v
```

Expected: all tests pass; the guard runs before the fake local GPU tool and normal event instrumentation remains green.

- [ ] **Step 6: Commit Task 3**

```powershell
git add lib/gpu_guard.py tools/base_tool.py tests/lib/test_gpu_guard.py
git commit -m "feat: guard local GPU tools from loaded LLMs"
```

---

### Task 4: Pipeline and Skill Routing

**Files:**
- Modify: `pipeline_defs/talking-head.yaml`
- Modify: `pipeline_defs/clip-factory.yaml`
- Modify: `pipeline_defs/hybrid.yaml`
- Modify: `pipeline_defs/screen-demo.yaml`
- Modify: `pipeline_defs/podcast-repurpose.yaml`
- Modify: `pipeline_defs/cinematic.yaml`
- Modify: `pipeline_defs/localization-dub.yaml`
- Modify: `skills/creative/video-understand-usage.md`
- Modify: `.agents/skills/video-understand/SKILL.md`
- Modify: the matching seven `skills/pipelines/<pipeline>/scene-director.md` files.
- Create: `tests/contracts/test_ollama_vision_pipeline_routing.py`

**Interfaces:**
- Consumes: registered `ollama_vision_review` tool and existing `frame_sampler` output.
- Produces: optional, explicit visual review route in source-led `scene_plan` stages.
- Produces: director guidance requiring one to three representative frames per scene, at most 20 per call, deterministic metrics for measurable defects, artifact path under the project, and explicit degraded status when unavailable.

- [ ] **Step 1: Write manifest and director contract tests**

```python
# tests/contracts/test_ollama_vision_pipeline_routing.py
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PIPELINES = ["talking-head", "clip-factory", "hybrid", "screen-demo", "podcast-repurpose", "cinematic", "localization-dub"]


def test_source_led_scene_stages_offer_ollama_vision_review():
    for name in PIPELINES:
        manifest = yaml.safe_load((ROOT / "pipeline_defs" / f"{name}.yaml").read_text(encoding="utf-8"))
        stage = next(item for item in manifest["stages"] if item["name"] == "scene_plan")
        assert "ollama_vision_review" in stage.get("optional_tools", [])
        assert "ollama_vision_review" in stage.get("tools_available", [])


def test_scene_directors_define_bounded_semantic_review():
    for name in PIPELINES:
        text = (ROOT / "skills" / "pipelines" / name / "scene-director.md").read_text(encoding="utf-8")
        assert "ollama_vision_review" in text
        assert "20" in text
        assert "degraded" in text.lower()


def test_layer3_skill_documents_local_vision_model_lifecycle():
    text = (ROOT / ".agents" / "skills" / "video-understand" / "SKILL.md").read_text(encoding="utf-8")
    assert "qwen3.5:9b" in text
    assert "keep_alive" in text
    assert "20" in text
```

- [ ] **Step 2: Run the test and verify all seven pipelines fail the new requirement**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_ollama_vision_pipeline_routing.py -v
```

Expected: failures identify missing `ollama_vision_review` entries.

- [ ] **Step 3: Add the optional tool to each source-led scene stage**

For each of the seven manifests, add the same entry beside `frame_sampler`:

```yaml
    optional_tools:
      - frame_sampler
      - ollama_vision_review
    tools_available:
      - frame_sampler
      - ollama_vision_review
```

Preserve every existing tool in both lists and do not change required tools or human approval defaults.

- [ ] **Step 4: Add one shared routing section to the creative skill**

Append this content to `skills/creative/video-understand-usage.md`:

```markdown
## Local Ollama semantic review

Use `frame_sampler` first, then `ollama_vision_review`, when the edit decision depends on visible meaning: subject/action, eye closure, obstruction, continuity, duplicate shots, best-take selection, on-screen text, or aspect-ratio crop suitability.

- Sample one to three representative frames per scene.
- Send no more than 20 ordered frames in one review call.
- Write the result below `projects/<project-id>/artifacts/` and reference it from the canonical stage artifact.
- Keep blur, brightness, contrast, resolution, and duration checks deterministic; do not ask the vision model to estimate them.
- If the tool is unavailable, report the run as degraded. Do not silently swap to CLIP, BLIP, LLaVA, or a cloud model.
- Before use, read the tool's Layer 3 `video-understand` skill.
```

- [ ] **Step 5: Add Ollama/Qwen guidance to the Layer 3 skill**

Append this section to `.agents/skills/video-understand/SKILL.md`:

```markdown
## Semantic frame review with Ollama

For editing judgments that require image meaning, call OpenMontage's `ollama_vision_review` provider with the official `qwen3.5:9b` Ollama tag.

- Extract representative frames first; never submit a complete video as image data.
- Submit ordered batches of at most 20 images, normally one to three per scene.
- Request Ollama structured output with the tool's JSON schema.
- Keep the vision context at 8192 tokens; more context wastes VRAM for bounded frame review.
- Set `keep_alive: 0` and explicitly unload the model after the batch.
- Preserve input timestamps and scene IDs exactly in the response.
- Use deterministic FFmpeg/Python metrics for blur, brightness, contrast, resolution, and duration.
```

- [ ] **Step 6: Add pipeline-specific semantic-review instructions**

In each scene director's source-inspection section, add the shared bounded rules plus the pipeline-specific query:

```markdown
When `ollama_vision_review` is available, review the sampled frames in batches of at most 20 and store the JSON under `projects/<project-id>/artifacts/`. Use one to three frames per scene. If it is unavailable, mark visual understanding as degraded and do not silently substitute another vision provider.
```

Then add exactly these pipeline-specific purposes:

- `talking-head`: select expressive frames, detect closed eyes/obstruction, and evaluate 9:16 face-preserving crops.
- `clip-factory`: rank candidate hooks, reject visually repetitive clips, and verify clean visual boundaries.
- `hybrid`: verify source/support semantic alignment and identify crop risks.
- `screen-demo`: read visible UI state, verify action continuity, and check callout-safe crop regions.
- `podcast-repurpose`: rank speaker reactions and verify active-speaker framing.
- `cinematic`: rank source shots for visual interest, continuity, and target aspect ratio.
- `localization-dub`: identify on-screen text and frames whose visual meaning conflicts with localized wording.

- [ ] **Step 7: Run manifest, skill, and global schema tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_ollama_vision_pipeline_routing.py tests/contracts/test_phase0_contracts.py -v
```

Expected: all pass; YAML manifests remain schema-valid.

- [ ] **Step 8: Commit Task 4**

```powershell
git add pipeline_defs skills/creative/video-understand-usage.md skills/pipelines .agents/skills/video-understand/SKILL.md tests/contracts/test_ollama_vision_pipeline_routing.py
git commit -m "feat: route source pipelines through local vision review"
```

---

### Task 5: Windows Setup, 32K Profile, Preflight, and Launcher

**Files:**
- Create: `config/ollama/gpt-oss-20b-32k.Modelfile`
- Create: `scripts/__init__.py`
- Create: `scripts/local_agent_preflight.py`
- Create: `scripts/setup_local_agent.ps1`
- Create: `scripts/start_local_agent.ps1`
- Create: `tests/scripts/test_local_agent_preflight.py`

**Interfaces:**
- Produces: `PreflightReport` and `run_preflight(...) -> PreflightReport`.
- Produces: human-readable default output and machine-readable `--json` output.
- Produces: derived tag `openmontage-gpt-oss:20b-32k` whose weights reference `gpt-oss:20b` and whose `num_ctx` is 32768.
- Launcher exports `OLLAMA_BASE_URL`, `OPENMONTAGE_ORCHESTRATOR_MODEL`, `OPENMONTAGE_VISION_MODEL`, and `OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD=1`, then executes Codex from the repository root.

- [ ] **Step 1: Write preflight tests with injected command/model checks**

```python
# tests/scripts/test_local_agent_preflight.py
from scripts.local_agent_preflight import PreflightReport, run_preflight


class FakeClient:
    def health(self): return True
    def list_models(self): return {"gpt-oss:20b", "qwen3.5:9b", "openmontage-gpt-oss:20b-32k"}
    def model_num_ctx(self, tag): return 32768


def test_preflight_passes_with_commands_models_and_venv(tmp_path):
    (tmp_path / ".venv" / "Scripts").mkdir(parents=True)
    (tmp_path / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
    report = run_preflight(tmp_path, client=FakeClient(), which=lambda command: f"C:/{command}.exe")
    assert report.ok
    assert report.missing_commands == []
    assert report.missing_models == []
    assert report.profile_context_length == 32768


def test_preflight_reports_every_actionable_gap(tmp_path):
    class OfflineClient:
        def health(self): return False
        def list_models(self): return set()
        def model_num_ctx(self, tag): return None
    report = run_preflight(tmp_path, client=OfflineClient(), which=lambda command: None)
    assert not report.ok
    assert set(report.missing_commands) == {"ollama", "codex", "ffmpeg", "ffprobe"}
    assert "Start Ollama" in "\n".join(report.actions)
    assert "offline" in "\n".join(report.actions).lower()
    assert "ollama pull" not in "\n".join(report.actions).lower()
```

- [ ] **Step 2: Run the test and verify the preflight module is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/test_local_agent_preflight.py -v
```

Expected: collection fails for `scripts.local_agent_preflight`.

- [ ] **Step 3: Implement the data model, injected checks, and CLI output**

```python
# scripts/local_agent_preflight.py
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from lib.providers.ollama import OllamaClient

COMMANDS = ("ollama", "codex", "ffmpeg", "ffprobe")
MODELS = ("gpt-oss:20b", "qwen3.5:9b", "openmontage-gpt-oss:20b-32k")


@dataclass
class PreflightReport:
    ok: bool
    ollama_online: bool
    missing_commands: list[str]
    missing_models: list[str]
    profile_context_length: int | None
    venv_python: str | None
    actions: list[str]


def run_preflight(root: Path, *, client: OllamaClient | None = None, which: Callable[[str], str | None] = shutil.which) -> PreflightReport:
    missing_commands = [command for command in COMMANDS if not which(command)]
    ollama = client or OllamaClient(timeout_seconds=5)
    online = ollama.health()
    installed = ollama.list_models() if online else set()
    missing_models = [model for model in MODELS if model not in installed]
    profile_context_length = ollama.model_num_ctx("openmontage-gpt-oss:20b-32k") if online and "openmontage-gpt-oss:20b-32k" in installed else None
    venv = root / ".venv" / "Scripts" / "python.exe"
    actions = []
    if missing_commands: actions.append("Copy missing executables from approved offline installation media: " + ", ".join(missing_commands))
    if not online: actions.append("Start Ollama and verify http://127.0.0.1:11434/api/tags")
    if missing_models: actions.append("Import missing model artifacts from approved offline media: " + ", ".join(missing_models))
    if "openmontage-gpt-oss:20b-32k" in missing_models: actions.append("Run scripts\\setup_local_agent.ps1 -CreateProfile")
    elif profile_context_length != 32768: actions.append("Recreate the 32K profile: scripts\\setup_local_agent.ps1 -CreateProfile")
    if not venv.is_file(): actions.append("Create the repository .venv and install requirements.txt")
    ok = not missing_commands and online and not missing_models and profile_context_length == 32768 and venv.is_file()
    return PreflightReport(ok, online, missing_commands, missing_models, profile_context_length, str(venv) if venv.is_file() else None, actions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_preflight(args.root.resolve())
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print("Local OpenMontage agent preflight: " + ("PASSED" if report.ok else "BLOCKED"))
        for action in report.actions:
            print(f"  - {action}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Create an empty `scripts/__init__.py` so the module is testable and callable with `-m`.

- [ ] **Step 4: Add the fixed 32K derived model profile**

```text
# config/ollama/gpt-oss-20b-32k.Modelfile
FROM gpt-oss:20b
PARAMETER num_ctx 32768
```

The derived tag reuses the locally imported base weights; it exists so Codex reloads the model with the same bounded context after every vision-model swap.

- [ ] **Step 5: Add an explicit setup script**

```powershell
# scripts/setup_local_agent.ps1
[CmdletBinding()]
param([switch]$CreateProfile)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'Ollama is missing. Copy it from approved offline installation media.'
}
if ($CreateProfile) {
    $modelFile = Join-Path $repoRoot 'config\ollama\gpt-oss-20b-32k.Modelfile'
    & ollama create openmontage-gpt-oss:20b-32k -f $modelFile
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create openmontage-gpt-oss:20b-32k' }
}
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python is missing. Restore .venv from the approved offline wheelhouse or environment archive.'
}
& $python -m scripts.local_agent_preflight --root $repoRoot
exit $LASTEXITCODE
```

- [ ] **Step 6: Add the validated launcher**

```powershell
# scripts/start_local_agent.ps1
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CodexArgs)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Repository Python is missing. Run scripts\setup_local_agent.ps1 first.'
}
& $python -m scripts.local_agent_preflight --root $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Local agent preflight failed. Resolve the listed actions and retry.' }
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OPENMONTAGE_OFFLINE = '1'
$env:OPENMONTAGE_ORCHESTRATOR_MODEL = 'openmontage-gpt-oss:20b-32k'
$env:OPENMONTAGE_VISION_MODEL = 'qwen3.5:9b'
$env:OPENMONTAGE_ENFORCE_OLLAMA_GPU_GUARD = '1'
Push-Location $repoRoot
try {
    & codex --oss -m openmontage-gpt-oss:20b-32k @CodexArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
```

- [ ] **Step 7: Run preflight tests and PowerShell parser checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/test_local_agent_preflight.py -v
$tokens = $null; $errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\setup_local_agent.ps1), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$tokens = $null; $errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\start_local_agent.ps1), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
```

Expected: pytest passes and both parser commands return without errors.

- [ ] **Step 8: Commit Task 5**

```powershell
git add config/ollama scripts tests/scripts/test_local_agent_preflight.py
git commit -m "feat: add Windows launcher for local video agent"
```

---

### Task 6: Opt-In Two-Model Smoke Test and User Documentation

**Files:**
- Create: `tests/integration/test_local_llm_smoke.py`
- Modify: `README.md`
- Modify: `docs/PROVIDERS.md`

**Interfaces:**
- Consumes: live Ollama only when `OPENMONTAGE_LOCAL_LLM_SMOKE=1`.
- Produces: a local-only smoke test that validates qwen structured frame review, post-review unload, and orchestrator reload.
- Produces: copy-paste Windows setup, launch, editing prompt, troubleshooting, and uninstall commands.

- [ ] **Step 1: Write the opt-in smoke test**

```python
# tests/integration/test_local_llm_smoke.py
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from lib.providers.ollama import OllamaClient
from tools.analysis.ollama_vision import OllamaVisionReview


pytestmark = pytest.mark.skipif(
    os.environ.get("OPENMONTAGE_LOCAL_LLM_SMOKE") != "1",
    reason="set OPENMONTAGE_LOCAL_LLM_SMOKE=1 to run local Ollama integration",
)


def test_vision_unloads_then_orchestrator_reloads(tmp_path, monkeypatch):
    project = tmp_path / "projects" / "local-smoke"
    frame_dir = project / "assets" / "frames"
    frame_dir.mkdir(parents=True)
    paths = []
    for index, color in enumerate(("navy", "orange")):
        path = frame_dir / f"frame-{index}.png"
        image = Image.new("RGB", (640, 360), color)
        ImageDraw.Draw(image).text((40, 40), f"FRAME {index}", fill="white")
        image.save(path)
        paths.append(path)
    client = OllamaClient(timeout_seconds=180)
    tool = OllamaVisionReview(client)
    result = tool.execute({
        "frames": [{"path": str(path), "timestamp": float(index), "scene_id": f"s{index}"} for index, path in enumerate(paths)],
        "mode": "select",
        "output_path": str(project / "artifacts" / "visual-review.json"),
    })
    assert result.success, result.error
    assert len(result.data["frames"]) == 2
    assert "qwen3.5:9b" not in {item.get("name") for item in client.running_models()}
    orchestrator = os.environ.get("OPENMONTAGE_ORCHESTRATOR_MODEL", "openmontage-gpt-oss:20b-32k")
    structured = client.chat_json(
        model=orchestrator,
        prompt='Return {"ready": true} as JSON.',
        image_paths=[],
        schema={"type": "object", "additionalProperties": False, "required": ["ready"], "properties": {"ready": {"type": "boolean"}}},
        num_ctx=32768,
        keep_alive=0,
    )
    assert structured == {"ready": True}
```

- [ ] **Step 2: Run the smoke test in default skipped mode**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_local_llm_smoke.py -v
```

Expected: one skipped test with the opt-in reason; no Ollama call occurs.

- [ ] **Step 3: Replace the README “Coming soon” note with local setup**

Document these exact commands and explain that prerequisites must already be
present from approved offline media; the scripts perform no downloads:

```powershell
.\scripts\setup_local_agent.ps1 -CreateProfile
.\scripts\start_local_agent.ps1
```

Include this first-run prompt:

```text
Analyze my source video locally. Sample representative frames, use qwen3.5:9b
for semantic visual review, then propose an edit plan. Do not generate assets or
render until I approve the gated stages.
```

State that the agent uses `openmontage-gpt-oss:20b-32k`, a local 32K profile
derived from `gpt-oss:20b`, and that visual review swaps to `qwen3.5:9b` rather
than loading both models concurrently.

Link prominently to `docs/LOCAL_TEXT_EDITING_GUIDE.md` as the next step after
installation.

- [ ] **Step 4: Add provider and troubleshooting documentation**

In `docs/PROVIDERS.md`, add a `Local LLM orchestration and visual review`
section with:

- Ollama endpoint: `http://127.0.0.1:11434`;
- required tags and approximate purpose, not a promise of exact VRAM usage;
- `ollama list` and `ollama ps` diagnostics;
- `ollama stop <model>` manual recovery;
- the `OPENMONTAGE_*` environment variables exported by the launcher;
- the opt-in smoke command:

```powershell
$env:OPENMONTAGE_LOCAL_LLM_SMOKE='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_local_llm_smoke.py -v
```

- an explicit warning that every API/HYBRID/network-required tool and remote URL
  is blocked in offline mode;
- removal commands:

```powershell
ollama rm openmontage-gpt-oss:20b-32k
ollama rm qwen3.5:9b
ollama rm gpt-oss:20b
```

- [ ] **Step 5: Run focused and full regression verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_ollama_provider.py tests/lib/test_gpu_guard.py tests/tools/test_ollama_vision.py tests/scripts/test_local_agent_preflight.py tests/contracts/test_ollama_vision_pipeline_routing.py tests/integration/test_local_llm_smoke.py -v
.\.venv\Scripts\python.exe -m pytest tests/contracts -q
git diff --check
```

Expected: focused tests pass with the integration test skipped by default; all contract tests pass; `git diff --check` produces no output.

- [ ] **Step 6: Run the live local smoke test on the target machine**

Run:

```powershell
$env:OPENMONTAGE_LOCAL_LLM_SMOKE='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_local_llm_smoke.py -v -s
```

Expected: the vision review returns two schema-valid frame records, qwen is absent from `/api/ps` afterward, and the orchestrator returns `{"ready": true}` before unloading.

- [ ] **Step 7: Commit Task 6**

```powershell
git add README.md docs/PROVIDERS.md tests/integration/test_local_llm_smoke.py
git commit -m "docs: add local two-model agent workflow"
```

---

### Task 7: User Editing Handbook and Agent Editorial Playbook

**Files:**
- Create: `docs/LOCAL_TEXT_EDITING_GUIDE.md`
- Replace: `skills/creative/video-editing.md`
- Create: `skills/creative/references/editorial-principles.md`
- Modify: `skills/pipelines/talking-head/edit-director.md`
- Modify: `skills/pipelines/clip-factory/edit-director.md`
- Modify: `skills/pipelines/hybrid/edit-director.md`
- Modify: `skills/pipelines/screen-demo/edit-director.md`
- Modify: `skills/pipelines/podcast-repurpose/edit-director.md`
- Modify: `skills/pipelines/cinematic/edit-director.md`
- Modify: `skills/pipelines/localization-dub/edit-director.md`
- Create: `tests/contracts/test_local_editing_guidance.py`

**Interfaces:**
- Produces: a standalone operator path from source footage to approved local render.
- Produces: copyable request templates for seven source-led workflows and revisions.
- Produces: one shared editorial algorithm that every source-led edit director must read before writing `edit_decisions`.
- Produces: an attributed, paraphrased reference layer based on Murch, Pearlman, Reisz/Millar, Dmytryk, and Ondaatje, without reproducing protected text.
- Consumes: transcript, silence analysis, scene boundaries, deterministic quality metrics, and `ollama_vision_review` evidence.

- [ ] **Step 1: Write handbook and playbook contract tests**

```python
# tests/contracts/test_local_editing_guidance.py
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINES = [
    "talking-head", "clip-factory", "hybrid", "screen-demo",
    "podcast-repurpose", "cinematic", "localization-dub",
]


def test_user_handbook_covers_complete_local_workflow():
    text = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    required = [
        "## What works locally", "## Prepare source files", "## Start the agent",
        "## Write an effective editing request", "## Review and approve the edit",
        "## Complete examples", "### Talking-head cleanup", "### Podcast highlights",
        "### Short-form clips", "### Screen demo", "### Aspect-ratio variants",
        "### Subtitle-only localization", "## Request revisions",
        "## Unsupported in the minimal build", "## Troubleshooting",
    ]
    for heading in required:
        assert heading in text
    assert "gpt-oss:20b" in text
    assert "qwen3.5:9b" in text
    assert "projects/<project-id>/renders/" in text


def test_agent_playbook_contains_evidence_cut_audio_and_qa_contracts():
    text = (ROOT / "skills" / "creative" / "video-editing.md").read_text(encoding="utf-8")
    required = [
        "## Editorial contract", "## Evidence order", "## Build the narrative spine",
        "## Make keep/remove decisions", "## Cut safety", "## Pacing profiles",
        "## Reframing", "## Subtitles", "## Audio", "## QA passes",
        "edit_decisions", "word boundaries", "source master",
    ]
    for phrase in required:
        assert phrase in text


def test_editorial_method_attributes_requested_books_and_is_routed_from_playbook():
    playbook = (ROOT / "skills" / "creative" / "video-editing.md").read_text(encoding="utf-8")
    reference = (ROOT / "skills" / "creative" / "references" / "editorial-principles.md").read_text(encoding="utf-8")
    handbook = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    assert "skills/creative/references/editorial-principles.md" in playbook
    for phrase in [
        "Walter Murch", "In the Blink of an Eye", "Karen Pearlman",
        "Cutting Rhythms", "Karel Reisz", "Gavin Millar",
        "The Technique of Film Editing", "Edward Dmytryk", "On Film Editing",
        "Michael Ondaatje", "The Conversations",
    ]:
        assert phrase in reference
    for concept in [
        "emotion", "story", "rhythm", "eye trace", "timing", "pacing",
        "trajectory", "tension", "release", "positive reason", "reaction",
        "dramatic function", "whole-piece viewing",
    ]:
        assert concept in reference.lower()
    assert "## How editorial decisions are made" in handbook


def test_source_led_edit_directors_route_through_shared_playbook():
    for pipeline in PIPELINES:
        text = (ROOT / "skills" / "pipelines" / pipeline / "edit-director.md").read_text(encoding="utf-8")
        assert "skills/creative/video-editing.md" in text
        assert "editorial evidence" in text.lower()
```

- [ ] **Step 2: Run the contract and verify the missing handbook/routing failures**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_local_editing_guidance.py -v
```

Expected: the handbook test fails because the file is absent, the playbook test
fails on missing sections, and directors without the shared reference fail.

- [ ] **Step 3: Write the standalone user handbook**

Create `docs/LOCAL_TEXT_EDITING_GUIDE.md` with this exact top-level flow:

```markdown
# Local Text Editing Guide

## What works locally
## Prepare source files
## Start the agent
## Write an effective editing request
## How the local edit works
## How editorial decisions are made
## Review and approve the edit
## Complete examples
### Talking-head cleanup
### Podcast highlights
### Short-form clips
### Screen demo
### Aspect-ratio variants
### Subtitle-only localization
## Request revisions
## Find the output
## Unsupported in the minimal build
## Troubleshooting
```

The guide must give these concrete operator rules:

- keep original footage outside generated output folders and never overwrite it;
- launch with `.\scripts\start_local_agent.ps1` from the repository;
- identify source path, audience, platform, target duration, language, must-keep
  material, desired energy, subtitle choice, aspect ratio, and approval policy;
- require the agent to show its proposed narrative and cut list before rendering;
- explain that `gpt-oss:20b` plans the edit and `qwen3.5:9b` reviews sampled frames;
- explain every human gate in plain language and show revision syntax with exact
  timecodes or scene IDs;
- point to `projects/<project-id>/renders/` for deliverables;
- state that the minimal build cannot generate new voice, music, images, video,
  avatars, lip-sync, background removal, AI upscale, or face restoration.

Include this reusable request template:

```text
Edit <source path> for <audience/platform>.
Goal: <what the viewer should understand or do>.
Target: <duration> at <aspect ratio>.
Keep: <mandatory ideas, quotes, or moments>.
Remove: <pauses, false starts, tangents, or other constraints>.
Pacing: <calm, balanced, energetic>.
Subtitles: <language and enabled/disabled>.
Use only local tools and supplied media. Analyze the transcript and representative
frames, then show me the narrative outline and timecoded cut plan before rendering.
```

Each complete example must contain a realistic request, the pipeline it maps to,
what the agent will inspect, the approval the user will see, and the expected
deliverable. Do not include an example that depends on an excluded optional stack.

In `How editorial decisions are made`, explain the method without assuming film
school vocabulary: preserve the intended feeling and meaning first; cut only for
a positive reason; shape timing, pacing, movement, tension, and release; protect
reactions and necessary context; and review the complete piece after local fixes.
Attribute the five books by author and title, link to the bibliography in
`skills/creative/references/editorial-principles.md`, and state that the guide
paraphrases principles rather than reproducing the books.

- [ ] **Step 4: Replace the shared agent playbook with an evidence-driven workflow**

Keep `skills/creative/video-editing.md` below 500 lines and use imperative
instructions. At the top, require the agent to read
`skills/creative/references/editorial-principles.md` before consequential edit
decisions. Include these rules verbatim or equivalently:

```markdown
## Editorial contract

- Never overwrite or destructively modify the source master.
- Establish audience, platform, target duration, delivery promise, must-keep material, and approval policy before selecting cuts.
- Separate editorial judgment (what the piece should say) from mechanical execution (how FFmpeg/Remotion/HyperFrames realizes it).
- Cite transcript timecodes, scene IDs, frame-review evidence, or deterministic metrics for every consequential keep/remove decision.

## Evidence order

1. Inspect media metadata and source integrity.
2. Read transcript and word timestamps.
3. Read silence and scene boundaries.
4. Read deterministic picture/audio metrics.
5. Read `ollama_vision_review` only for semantic judgments.
6. Mark unavailable evidence as degraded; never pretend to have watched an unsampled moment.

## Build the narrative spine

Choose the hook, context, development, payoff, and optional call to action before refining individual cuts. For excerpts, preserve enough setup that the selected claim remains accurate and understandable.

## Make keep/remove decisions

Record source in/out, rationale, evidence, transition intent, and confidence. Keep the best complete delivery of repeated ideas. Remove false starts, redundant takes, off-goal tangents, and accidental dead air; preserve intentional emphasis, breaths, reactions, and meaning-changing context.

## Cut safety

- Cut dialogue at word or phoneme-safe boundaries, never mid-word.
- Retain 80-150 ms handles around speech unless inspection proves a tighter cut clean.
- Use 10-30 ms audio fades at hard boundaries to prevent clicks.
- Use J/L cuts of roughly 0.2-0.5 seconds only when they improve continuity.
- Re-encode exact cuts when stream-copy GOP boundaries would shift the requested timecode.
```

Define three pacing profiles: energetic short-form, balanced medium-form, and
calm long-form. Define reframing rules that preserve faces, gestures, UI state,
and on-screen text. Define subtitle rules for timing, reading speed, line breaks,
safe areas, and speaker labels. Define a web-delivery audio target of about
`-14 LUFS` integrated with peaks no higher than `-1 dBTP`, unless a platform
profile overrides it.

Define five mandatory QA passes:

1. story and factual continuity;
2. picture continuity, crop, and overlay safety;
3. speech intelligibility, clicks, sync, and loudness;
4. subtitle accuracy, timing, line breaks, and safe areas;
5. output duration, resolution, frame rate, codec, and file playback.

Finish with the exact required fields for `edit_decisions`: ordered keep/cut
segments, source paths, in/out timecodes, rationale/evidence, speed, transitions,
reframes, overlays, subtitles, audio treatment, warnings, QA results, and
approval state.

- [ ] **Step 5: Write the attributed editorial-principles reference**

Create `skills/creative/references/editorial-principles.md`. Keep it practical,
originally worded, and source-aware. Do not quote passages or reconstruct any
book chapter-by-chapter. For each work, provide:

1. the principle in a short paraphrase;
2. questions the agent must ask while reviewing footage;
3. how the principle changes `edit_decisions`;
4. failure modes and when another principle has priority.

Use this operational synthesis:

- Murch: evaluate candidate cuts in the order emotion, story, rhythm, eye trace,
  two-dimensional screen continuity, and three-dimensional spatial continuity;
  use the order to resolve conflicts, not as a numeric scoring formula. Look for
  thought/attention changes as candidate cut points.
- Pearlman: distinguish timing (when an event or cut occurs), pacing (the rate
  and density of events), and trajectory phrasing (how movement and energy develop
  across shots). Diagnose tension/release and physical, emotional, and event rhythm.
- Reisz/Millar: name the dramatic function of every scene and sequence before
  selecting a technique. Adapt the method to dialogue, action, documentary,
  montage, and sound rather than enforcing one universal cut pattern.
- Dmytryk: record the positive reason for every consequential cut; preserve the
  strongest performance and meaningful reaction; when smoothness conflicts with
  meaning, make the dramatically right cut and repair mechanics afterward.
- Ondaatje/Murch: edit by making and comparing versions, reviewing the whole
  piece after local changes, and treating picture, dialogue, music, and sound as
  one collaborative construction.

End with a conventional offline bibliography: author, title, publisher, and
edition, without web links. Clearly label any cross-book synthesis as the
OpenMontage operational interpretation. Do not claim exhaustive or page-specific
coverage unless the user supplies the relevant edition or excerpts as local files.

- [ ] **Step 6: Route every source-led edit director through the playbook**

Near the beginning of each of the seven `edit-director.md` files, add:

```markdown
## Shared editorial method

Read `skills/creative/video-editing.md` completely before making edit decisions.
Apply its editorial evidence order, cut-safety rules, pacing profile, and five QA
passes. Pipeline-specific instructions below refine that shared method; they do
not replace it. If transcript, scene, or visual evidence is unavailable, record
the edit as degraded instead of inventing support.
```

Do not alter existing pipeline-specific approval gates or canonical artifact names.

- [ ] **Step 7: Run guidance contracts and affected pipeline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_local_editing_guidance.py tests/contracts/test_phase0_contracts.py -v
```

Expected: all guidance contracts and global schema/manifest checks pass.

- [ ] **Step 8: Commit Task 7**

```powershell
git add docs/LOCAL_TEXT_EDITING_GUIDE.md skills/creative/video-editing.md skills/creative/references/editorial-principles.md skills/pipelines tests/contracts/test_local_editing_guidance.py
git commit -m "docs: add local editorial handbook and playbook"
```

---

## Final Verification

- [ ] Run all focused local-agent tests.
- [ ] Run the complete contract suite.
- [ ] Run the live two-model smoke test with opt-in enabled.
- [ ] Run `tests/contracts/test_local_editing_guidance.py` and manually follow one handbook example through the proposal gate without rendering.
- [ ] Run `git diff --check`.
- [ ] Run `git status --short` and confirm the user's pre-existing `remotion-composer/package-lock.json` modification remains untouched and unstaged.
- [ ] Review the final diff against `docs/superpowers/specs/2026-08-09-local-llm-video-agent-design.md` and confirm every acceptance criterion is covered.
