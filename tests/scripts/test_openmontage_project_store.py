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


def test_project_delete_moves_workspace_to_recoverable_trash(tmp_path: Path):
    store = ProjectStore(tmp_path)
    first = store.create("Первый")
    second = store.create("Второй")

    removed = store.delete(first["project_id"])

    assert removed["deleted"] is True
    assert removed["recoverable"] is True
    assert Path(removed["trash_path"]).is_dir()
    assert not Path(first["project_root"]).exists()
    assert [item["project_id"] for item in store.list()] == [second["project_id"]]
    with pytest.raises(FileNotFoundError):
        store.delete(first["project_id"])


def test_question_sets_and_plans_have_active_ids_and_reject_stale_actions(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Lifecycle")
    project_id = state["project_id"]
    first = store.set_questions(project_id, [{"question_id": "format", "text": "Формат?", "choices": [{"value": "wide", "label": "16:9"}, {"value": "short", "label": "9:16"}]}])
    second = store.set_questions(project_id, [{"question_id": "pace", "text": "Темп?", "choices": [{"value": "fast", "label": "Быстро"}, {"value": "calm", "label": "Спокойно"}]}])

    with pytest.raises(ValueError, match="устарел"):
        store.answer_questions(project_id, first["question_set_id"], {"format": "wide"})
    with pytest.raises(ValueError, match="все обязательные"):
        store.answer_questions(project_id, second["question_set_id"], {})
    store.answer_questions(project_id, second["question_set_id"], {"pace": "fast"})

    plan1 = store.save_plan(project_id, {"pipeline": "talking-head", "steps": []}, mode="confirm")
    plan2 = store.save_plan(project_id, {"pipeline": "talking-head", "steps": []}, mode="confirm")
    with pytest.raises(ValueError, match="устарел"):
        store.require_active_plan(project_id, plan1["plan_id"], mode="confirm")
    assert store.require_active_plan(project_id, plan2["plan_id"], mode="confirm")["plan_id"] == plan2["plan_id"]
    with pytest.raises(PermissionError, match="только чтение"):
        store.require_active_plan(project_id, plan2["plan_id"], mode="read_only")


def test_complete_expected_artifact_set_is_required_and_open_is_read_only(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Deliverables")
    project_id = state["project_id"]
    project = Path(state["project_root"])
    video = project / "renders" / "final.mp4"
    report = project / "artifacts" / "render_report.json"
    video.write_bytes(b"video")
    report.write_text('{"ok": true}', encoding="utf-8")
    store.media_probe = lambda path: {"duration": 1.0, "streams": ["video"]}

    store.set_expected_artifacts(project_id, [
        {"key": "video", "path": str(video), "required": True},
        {"key": "report", "path": str(report), "required": True},
    ])
    video.unlink()
    result = store.verify_expected_artifacts(project_id)
    assert result["ready"] is False
    assert store.load(project_id)["status"] == "needs_attention"

    video.write_bytes(b"video")
    result = store.verify_expected_artifacts(project_id)
    assert result["ready"] is True
    before = len(store.load(project_id)["conversation"])
    artifact = store.get_artifact(project_id, result["artifacts"][0]["artifact_id"])
    assert Path(artifact["path"]).is_file()
    assert len(store.load(project_id)["conversation"]) == before


def test_version_is_a_snapshot_with_parent_and_change_note(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Versions")
    first = store.create_version(state["project_id"], change_note="Первый монтаж")
    second = store.create_version(state["project_id"], change_note="Сделать короче")

    assert first["version_id"] == "v001"
    assert second["parent_version_id"] == "v001"
    assert second["change_note"] == "Сделать короче"
    assert store.load(state["project_id"])["versions"][-1] == second


def test_resolving_question_or_plan_deactivates_its_conversation_card(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Cards")
    questions = store.set_questions(state["project_id"], [{"question_id": "q", "text": "Q", "choices": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]}])
    store.append_entry(state["project_id"], {"role": "assistant", "type": "questions", **questions})
    store.answer_questions(state["project_id"], questions["question_set_id"], {"q": "a"})
    plan = store.save_plan(state["project_id"], {"pipeline": "x", "steps": []})
    store.append_entry(state["project_id"], {"role": "assistant", "type": "plan", "plan": plan})
    store.resolve_plan(state["project_id"], plan["plan_id"], "running")

    cards = store.load(state["project_id"])["conversation"]
    assert next(item for item in cards if item["type"] == "questions")["active"] is False
    assert next(item for item in cards if item["type"] == "plan")["active"] is False
