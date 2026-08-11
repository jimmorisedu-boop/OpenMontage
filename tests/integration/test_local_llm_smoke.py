from __future__ import annotations

import os

import pytest
from PIL import Image

from lib.providers.ollama import OllamaClient
from tools.analysis.ollama_vision import OllamaVisionReview


pytestmark = pytest.mark.skipif(
    os.environ.get("OPENMONTAGE_LOCAL_LLM_SMOKE") != "1",
    reason="set OPENMONTAGE_LOCAL_LLM_SMOKE=1 to run the offline Ollama integration",
)


def test_vision_unloads_then_orchestrator_reloads(tmp_path):
    frame = tmp_path / "projects" / "smoke" / "assets" / "frames" / "frame.png"
    frame.parent.mkdir(parents=True)
    Image.new("RGB", (320, 180), "navy").save(frame)
    client = OllamaClient(timeout_seconds=180)
    result = OllamaVisionReview(client).execute({
        "frames": [{"path": str(frame), "timestamp": 0.0, "scene_id": "s0"}],
        "mode": "select",
        "output_path": str(tmp_path / "projects" / "smoke" / "artifacts" / "review.json"),
    })
    assert result.success, result.error
    assert "qwen3.5:9b" not in {item.get("name") for item in client.running_models()}
    answer = client.chat_json(
        model=os.environ.get("OPENMONTAGE_ORCHESTRATOR_MODEL", "openmontage-gpt-oss:20b-32k"),
        prompt='Return {"ready": true}.', image_paths=[],
        schema={"type": "object", "required": ["ready"], "properties": {"ready": {"type": "boolean"}}},
        num_ctx=32768, keep_alive=0,
    )
    assert answer == {"ready": True}
