import json

from PIL import Image

from tools.analysis.ollama_vision import OllamaVisionReview


class FakeClient:
    def __init__(self): self.calls = 0; self.unloaded = []
    def health(self): return True
    def list_models(self): return {"qwen3.5:9b"}
    def unload(self, model): self.unloaded.append(model)
    def chat_json(self, **kwargs):
        self.calls += 1
        return {
            "frames": [{
                "timestamp": float(index), "scene_id": f"s{index}",
                "description": "colored frame", "issues": [], "confidence": 0.9,
            } for index, _ in enumerate(kwargs["image_paths"])],
            "summary": "usable",
        }


def test_review_writes_provenance_and_uses_cache(tmp_path):
    frames = []
    for index, color in enumerate(("navy", "orange")):
        path = tmp_path / f"frame-{index}.png"
        Image.new("RGB", (32, 32), color).save(path)
        frames.append({"path": str(path), "timestamp": float(index), "scene_id": f"s{index}"})
    output = tmp_path / "projects" / "demo" / "artifacts" / "review.json"
    client = FakeClient()
    tool = OllamaVisionReview(client)
    first = tool.execute({"frames": frames, "mode": "select", "output_path": str(output)})
    second = tool.execute({"frames": frames, "mode": "select", "output_path": str(output)})
    assert first.success and second.success
    assert client.calls == 1
    assert second.data["provenance"]["cache_status"] == "hit"
    assert json.loads(output.read_text(encoding="utf-8"))["summary"] == "usable"


def test_review_rejects_more_than_twenty_frames(tmp_path):
    result = OllamaVisionReview(FakeClient()).execute({
        "frames": [{"path": str(tmp_path / "x")} for _ in range(21)],
        "mode": "full", "output_path": str(tmp_path / "out.json"),
    })
    assert not result.success
