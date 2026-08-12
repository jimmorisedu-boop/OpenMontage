import json
from pathlib import Path

import pytest

from scripts.openmontage_chat.project_store import ProjectStore


def test_project_store_creates_canonical_durable_project(tmp_path: Path):
    store = ProjectStore(tmp_path, media_probe=lambda path: {"duration": 2.5, "streams": ["video"]})

    state = store.create("Мой ролик")

    project = tmp_path / "projects" / state["project_id"]
    assert project.is_dir()
    assert state["title"] == "Мой ролик"
    assert state["status"] == "needs_brief"
    assert state["project_root"] == str(project.resolve())
    assert (project / "conversation.json").is_file()
    assert (project / "brief.json").is_file()
    assert (project / "artifacts" / "input_manifest.json").is_file()


def test_project_store_restores_conversation_and_lists_latest_first(tmp_path: Path):
    store = ProjectStore(tmp_path)
    first = store.create("Первый")
    second = store.create("Второй")
    store.append_entry(first["project_id"], {"role": "user", "type": "text", "text": "Привет"})

    restored = ProjectStore(tmp_path).load(first["project_id"])
    listed = ProjectStore(tmp_path).list()

    assert restored["conversation"][-1]["text"] == "Привет"
    assert listed[0]["project_id"] == first["project_id"]
    assert {item["project_id"] for item in listed} == {first["project_id"], second["project_id"]}


def test_project_store_persists_brief_plan_and_versions(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Версии")
    project_id = state["project_id"]

    store.update_brief(project_id, {"platform": "YouTube", "duration": "60s"})
    store.save_plan(project_id, {"pipeline": "talking-head", "steps": []})
    version = store.create_version(project_id)
    restored = store.load(project_id)

    assert restored["brief"]["known"]["platform"] == "YouTube"
    assert restored["plan"]["pipeline"] == "talking-head"
    assert version["number"] == 1
    assert Path(version["renders_dir"]).name == "v001"


def test_verified_artifact_must_exist_inside_active_project(tmp_path: Path):
    store = ProjectStore(tmp_path, media_probe=lambda path: {"duration": 1.0, "streams": ["video"]})
    state = store.create("Проверка")
    project = Path(state["project_root"])
    render = project / "renders" / "v001" / "preview.mp4"
    render.parent.mkdir(parents=True)
    render.write_bytes(b"fixture")

    verified = store.verify_artifact(state["project_id"], render)

    assert verified["verified"] is True
    assert verified["path"] == str(render.resolve())
    assert store.load(state["project_id"])["status"] == "ready"
    with pytest.raises(ValueError, match="outside"):
        store.verify_artifact(state["project_id"], tmp_path / "outside.mp4")
    with pytest.raises(FileNotFoundError):
        store.verify_artifact(state["project_id"], project / "renders" / "missing.mp4")


def test_json_state_is_written_atomically_without_temp_files(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Atomic")
    store.set_status(state["project_id"], "running")

    project = Path(state["project_root"])
    json.loads((project / "project.json").read_text(encoding="utf-8"))
    assert not list(project.rglob("*.tmp"))
