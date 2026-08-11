from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PIPELINES = ["talking-head", "clip-factory", "hybrid", "screen-demo", "podcast-repurpose", "cinematic", "localization-dub"]


def test_source_pipelines_offer_local_vision_review():
    for name in PIPELINES:
        manifest = yaml.safe_load((ROOT / "pipeline_defs" / f"{name}.yaml").read_text(encoding="utf-8"))
        scene = next(stage for stage in manifest["stages"] if stage["name"] == "scene_plan")
        assert "ollama_vision_review" in scene["optional_tools"]
        assert "ollama_vision_review" in scene["tools_available"]


def test_scene_directors_require_bounded_offline_review():
    for name in PIPELINES:
        text = (ROOT / "skills" / "pipelines" / name / "scene-director.md").read_text(encoding="utf-8")
        assert "ollama_vision_review" in text
        assert "20" in text
        assert "remote substitute" in text
