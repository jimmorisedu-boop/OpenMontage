from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.checkpoint import init_project
from lib.input_manifest import InputPriority, register_inputs
from tools.publishers.project_collector import ProjectCollector


def _fixture(tmp_path: Path):
    projects = tmp_path / "projects"
    project = init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=projects)
    used = tmp_path / "sources-a" / "clip.mp4"
    unused = tmp_path / "sources-b" / "clip.mp4"
    used.parent.mkdir()
    unused.parent.mkdir()
    used.write_bytes(b"used")
    unused.write_bytes(b"unused")
    manifest = register_inputs(
        "film", [str(used), str(unused)], priority=InputPriority.REFERENCE, pipeline_dir=projects
    )
    used_item = next(item for item in manifest["inputs"] if Path(item["path"]).read_bytes() == b"used")
    (project / "artifacts" / "edit_reference.json").write_text(
        json.dumps({"selected_input_id": used_item["id"]}), encoding="utf-8"
    )
    (project / "checkpoint_edit.json").write_text("{}", encoding="utf-8")
    (project / "renders" / "final.mp4").write_bytes(b"render")
    (project / "conversation.json").write_text('{"messages":[]}', encoding="utf-8")
    return projects, project, used, unused


def test_collects_canonical_state_deliverables_and_only_used_inputs(tmp_path):
    projects, project, used, unused = _fixture(tmp_path)
    destination = tmp_path / "export" / "film-portable"
    result = ProjectCollector(pipeline_dir=projects).execute(
        {"project_id": "film", "destination": str(destination), "include_conversation": True}
    )
    assert result.success, result.error
    assert (destination / "project.json").is_file()
    assert (destination / "checkpoint_edit.json").is_file()
    assert (destination / "renders" / "final.mp4").is_file()
    assert (destination / "conversation.json").is_file()
    copied_inputs = list((destination / "inputs").glob("*clip.mp4"))
    assert len(copied_inputs) == 1
    assert copied_inputs[0].read_bytes() == used.read_bytes()
    assert copied_inputs[0].read_bytes() != unused.read_bytes()
    collection = json.loads((destination / "collection_manifest.json").read_text("utf-8"))
    for entry in collection["files"]:
        path = destination / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_collision_safe_names_and_missing_source_warning(tmp_path):
    projects, project, used, unused = _fixture(tmp_path)
    manifest_path = project / "artifacts" / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    for item in manifest["inputs"]:
        (project / "artifacts" / f"use-{item['id']}.json").write_text(json.dumps({"input_id": item["id"]}), encoding="utf-8")
    unused.unlink()
    destination = tmp_path / "collected"
    result = ProjectCollector(pipeline_dir=projects).execute(
        {"project_id": "film", "destination": str(destination), "include_conversation": False}
    )
    assert result.success
    assert result.data["warnings"]
    assert len(list((destination / "inputs").glob("*clip.mp4"))) == 1
    assert not (destination / "conversation.json").exists()


def test_refuses_destination_inside_source_or_existing_nonempty_target(tmp_path):
    projects, project, used, unused = _fixture(tmp_path)
    collector = ProjectCollector(pipeline_dir=projects)
    inside = collector.execute({"project_id": "film", "destination": str(project / "export")})
    assert not inside.success
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    refused = collector.execute({"project_id": "film", "destination": str(existing)})
    assert not refused.success
    assert (existing / "keep.txt").read_text("utf-8") == "keep"
