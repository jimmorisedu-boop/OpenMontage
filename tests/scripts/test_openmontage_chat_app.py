from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from scripts.openmontage_chat.app import DesktopApi, create_app, parse_model_response


def test_chat_shell_exposes_one_fixed_product_identity(tmp_path: Path):
    client = TestClient(create_app(root=tmp_path))
    html = client.get("/").text

    assert "OpenMontage" in html
    assert "openmontage-gpt-oss:20b-32k" not in html
    assert "model-selector" not in html
    assert "assistant-selector" not in html
    assert "provider-selector" not in html
    assert "Добавить материалы" in html
    assert "window.pywebview.api.pick_materials" in html
    assert "fetch(" not in html


def test_chat_shell_shows_compact_progress_and_collapsed_approach(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    assert "Изучаю проект" in html
    assert "Выбираю инструменты" in html
    assert "Готовлю следующий шаг" in html
    assert "Как я подошёл к задаче" in html
    assert "node('details'" in html
    assert "textContent" in html
    assert "startProgress()" in html
    assert "stopProgress()" in html
    assert "fetch(" not in html
    assert "цепочка рассуждений" not in html.lower()


def test_chat_shell_is_a_saved_project_product_with_action_cards(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    for marker in [
        "projects-list", "project-path", "Открыть папку", "Новый монтаж",
        "question-card", "enhancement-card", "plan-card", "result-card",
        "Подтвердить и запустить", "Применить", "Пропустить", "Новая версия",
        "window.pywebview.api.bootstrap()", "window.pywebview.api.answer_questions",
        "window.pywebview.api.approve_plan", "window.pywebview.api.open_project_folder",
    ]:
        assert marker in html
    assert "model-selector" not in html
    assert "agent-selector" not in html
    assert "/home/user" not in html


def test_material_picker_keeps_local_paths_without_copying_binary(tmp_path: Path):
    source = tmp_path / "footage.mp4"
    source.write_bytes(b"video")
    client = TestClient(create_app(root=tmp_path))

    response = client.post("/api/materials", json={"paths": [str(source)]})

    assert response.status_code == 200
    material = response.json()["materials"][0]
    assert material["name"] == "footage.mp4"
    assert material["path"] == str(source.resolve())
    assert material["kind"] == "video"


def test_chat_api_always_uses_the_fixed_model(tmp_path: Path):
    calls = []

    def fake_chat(payload):
        calls.append(payload)
        return {"message": {"content": "Готово"}}

    client = TestClient(create_app(root=tmp_path, ollama_chat=fake_chat))
    response = client.post(
        "/api/chat",
        json={"message": "Разбери материал", "materials": [str(tmp_path / "a.mov")]},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Готово"
    assert calls[0]["model"] == "openmontage-gpt-oss:20b-32k"
    assert str(tmp_path / "a.mov") in calls[0]["messages"][-1]["content"]


def test_native_bridge_picks_materials_without_http(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    api = DesktopApi(root=tmp_path, file_picker=lambda: [str(source)])

    result = api.pick_materials()

    assert result["materials"][0]["path"] == str(source.resolve())
    assert result["materials"][0]["kind"] == "video"


def test_native_bridge_chats_without_fetch(tmp_path: Path):
    calls = []
    api = DesktopApi(
        root=tmp_path,
        ollama_chat=lambda payload: calls.append(payload) or {"message": {"content": "OK"}},
    )

    result = api.chat({"message": "Смонтируй", "materials": [str(tmp_path / "a.mov")]})

    assert result["answer"] == "OK"
    assert result["summary"] == []
    assert calls[0]["model"] == "openmontage-gpt-oss:20b-32k"


def test_product_bridge_creates_and_restores_saved_projects(tmp_path: Path):
    api = DesktopApi(root=tmp_path, ollama_chat=lambda payload: {})

    created = api.create_project("Клиентский ролик")
    boot = api.bootstrap()
    opened = api.open_project(created["project_id"])

    assert boot["active_project"]["project_id"] == created["project_id"]
    assert boot["projects"][0]["title"] == "Клиентский ролик"
    assert opened["project_root"].startswith(str(tmp_path / "projects"))


def test_product_bridge_registers_materials_in_active_project(tmp_path: Path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fixture")
    api = DesktopApi(root=tmp_path, file_picker=lambda: [str(clip)], ollama_chat=lambda payload: {})
    project = api.create_project("Материалы")

    result = api.pick_materials(project["project_id"])

    assert result["materials"][0]["path"] == str(clip.resolve())
    assert result["project"]["input_manifest"]["inputs"][0]["path"] == str(clip.resolve())


def test_model_response_extracts_a_bounded_approach_summary():
    result = parse_model_response(
        '```json\n{"answer":"Готово", "summary":["  Изучил темп  ", "", "Нашёл кульминацию", "Выстроил ритм", "Проверил переходы", "Лишнее"]}\n```'
    )

    assert result == {
        "answer": "Готово",
        "summary": ["Изучил темп", "Нашёл кульминацию", "Выстроил ритм", "Проверил переходы"],
    }


def test_model_response_preserves_plain_text_as_the_answer():
    assert parse_model_response("Обычный ответ модели") == {
        "answer": "Обычный ответ модели",
        "summary": [],
    }


def test_shell_has_accessible_live_status_and_inline_errors(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    assert 'aria-live="polite"' in html
    assert 'aria-label="Режим работы"' in html
    assert '<label for="prompt"' in html
    assert 'id="inline-error"' in html
    assert "alert(" not in html
    assert 'aria-busy' in html


def test_shell_uses_active_ids_custom_answers_and_truthful_operations(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    assert "question_set_id" in html
    assert "plan_id" in html
    assert "operation_id" in html
    assert "operation_status" in html
    assert "cancel_operation" in html
    assert "Другой ответ" in html
    assert "entry.status==='completed'?'✓'" in html
    assert "open_artifact(active.project_id,a.artifact_id)" in html


def test_shell_scopes_answers_to_project_and_disables_stale_cards(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    assert "answersByProject" in html
    assert "entry.active===false" in html
    assert "submit.disabled" in html
    assert "go.disabled" in html


def test_native_approval_returns_background_operation_and_enforces_mode(tmp_path: Path):
    api = DesktopApi(root=tmp_path, ollama_chat=lambda payload: {})
    project = api.create_project("Background")
    saved = api.store.save_plan(project["project_id"], {"pipeline": "fixture", "steps": []}, mode="confirm")
    api.orchestrator.approve_plan = lambda project_id, plan_id, mode, control: (time.sleep(0.08), {"project_id": project_id, "status": "ready"})[1]

    started = time.monotonic()
    response = api.approve_plan(project["project_id"], saved["plan_id"], "confirm")

    assert time.monotonic() - started < 0.05
    assert response["operation"]["status"] in {"queued", "running"}
    with pytest.raises(PermissionError, match="только чтение"):
        api.approve_plan(project["project_id"], saved["plan_id"], "read_only")


def test_auto_submit_starts_the_same_background_operation(tmp_path: Path):
    api = DesktopApi(root=tmp_path, ollama_chat=lambda payload: {})
    project = api.create_project("Auto")
    saved = api.store.save_plan(project["project_id"], {"pipeline": "fixture", "steps": []}, mode="auto")
    api.orchestrator.submit = lambda project_id, message, mode: api.store.load(project_id)
    calls = []
    api.approve_plan = lambda project_id, plan_id, mode: calls.append((project_id, plan_id, mode)) or {"project": api._project_state(project_id)}

    result = api.submit(project["project_id"], "Делай", "auto")

    assert calls == [(project["project_id"], saved["plan_id"], "auto")]
    assert result["project_id"] == project["project_id"]


def test_auto_submit_does_not_cross_manifest_human_gate(tmp_path: Path):
    api = DesktopApi(root=tmp_path, ollama_chat=lambda payload: {})
    project = api.create_project("Gate")
    saved = api.store.save_plan(project["project_id"], {
        "pipeline": "fixture", "steps": [],
        "stage_contract": {"human_approval_required": True},
    }, mode="auto")
    api.orchestrator.submit = lambda project_id, message, mode: api.store.load(project_id)
    calls = []
    api.approve_plan = lambda *args: calls.append(args)

    result = api.submit(project["project_id"], "Делай", "auto")

    assert calls == []
    assert result["status"] == "awaiting_approval"
    assert result["plan"]["plan_id"] == saved["plan_id"]


def test_chat_api_returns_structured_summary(tmp_path: Path):
    client = TestClient(create_app(
        root=tmp_path,
        ollama_chat=lambda payload: {"message": {"content": '{"answer":"План готов", "summary":["Проверил материал"]}'}},
    ))

    response = client.post("/api/chat", json={"message": "Составь план"})

    assert response.json()["answer"] == "План готов"
    assert response.json()["summary"] == ["Проверил материал"]
