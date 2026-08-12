from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from scripts.openmontage_chat.app import DesktopApi, create_app, parse_model_response


ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "scripts" / "openmontage_chat" / "ui"


def ui_source() -> str:
    paths = [*(UI / "src").rglob("*.ts"), *(UI / "src").rglob("*.tsx"), *(UI / "src").rglob("*.css")]
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(paths))


def test_modern_shell_is_built_from_typed_component_sources():
    package = (UI / "package.json").read_text(encoding="utf-8")
    source = ui_source()
    styles = (UI / "src" / "styles.css").read_text(encoding="utf-8")

    for dependency in [
        '"react"', '"radix-ui"', '"lucide-react"', '"motion"',
        '"react-resizable-panels"', '"vite-plugin-singlefile"',
    ]:
        assert dependency in package
    assert "PyWebViewApi" in source
    assert "ProjectRail" in source
    assert "StudioStage" in source
    assert "Inspector" in source
    assert "--type-title" in styles
    assert "--space-4" in styles


def test_chat_shell_exposes_one_fixed_product_identity(tmp_path: Path):
    client = TestClient(create_app(root=tmp_path))
    html = client.get("/").text

    assert "OpenMontage" in html
    assert "openmontage-gpt-oss:20b-32k" not in html
    assert "model-selector" not in html
    assert "assistant-selector" not in html
    assert "provider-selector" not in html
    assert "Добавить материалы" in html
    assert "pywebview" in html
    assert "pick_materials" in html
    assert "fetch(" not in html
    assert '<script src=' not in html
    assert '<script type="module"' not in html
    assert '<link rel="stylesheet"' not in html


def test_chat_shell_shows_compact_progress_and_collapsed_approach(tmp_path: Path):
    source = ui_source()

    assert "Как я подошёл к задаче" in source
    assert "<details" in source
    assert "entry.summary" in source
    assert "operationProgress" in source
    assert "operation_status" in source
    assert "цепочка рассуждений" not in source.lower()


def test_chat_shell_is_a_saved_project_product_with_action_cards(tmp_path: Path):
    source = ui_source()

    for marker in [
        "project-list", "project_root", "Открыть папку", "Новый монтаж",
        "question-card", "enhancement-card", "plan-card", "result-card",
        "Подтвердить и запустить", "Применить выбранное", "Пропустить", "Новая версия",
        "bridge.bootstrap()", "api.answer_questions", "api.approve_plan", "api.open_project_folder",
    ]:
        assert marker in source
    assert "model-selector" not in source
    assert "agent-selector" not in source
    assert "/home/user" not in source


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


def test_native_bridge_deletes_project_and_selects_a_safe_fallback(tmp_path: Path):
    api = DesktopApi(root=tmp_path, ollama_chat=lambda payload: {})
    first = api.create_project("Первый")
    second = api.create_project("Второй")

    result = api.delete_project(second["project_id"])

    assert result["deleted"]["recoverable"] is True
    assert result["active_project"]["project_id"] == first["project_id"]
    assert result["projects"] == result["active_project"]["projects"]


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
    source = ui_source()

    assert 'aria-live="polite"' in source
    assert 'aria-label="Режим работы"' in source
    assert 'id="prompt"' in source
    assert 'className="inline-error"' in source
    assert "alert(" not in source
    assert 'aria-busy' in source


def test_shell_uses_active_ids_custom_answers_and_truthful_operations(tmp_path: Path):
    source = ui_source()

    assert "question_set_id" in source
    assert "plan_id" in source
    assert "operation_id" in source
    assert "operation_status" in source
    assert "cancel_operation" in source
    assert "Другой ответ" in source
    assert "operation.progress_label" in source
    assert "api.open_artifact(activeId, artifact.artifact_id" in source


def test_shell_scopes_answers_to_project_and_disables_stale_cards(tmp_path: Path):
    source = ui_source()

    assert "setAnswers" in source
    assert 'entry.active === false' in source
    assert 'disabled={!ready}' in source
    assert 'disabled={entry.active === false}' in source


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


def test_shell_is_an_adaptive_three_region_director_studio(tmp_path: Path):
    source = ui_source()

    for marker in [
        'className="project-rail"', 'className="studio-stage"', 'className="inspector"',
        'aria-label="Предпросмотр монтажа"', 'aria-label="Обзор монтажа"', 'context-tabs',
        'value="assistant"', 'value="files"', '@media (max-width: 860px)',
        'prefers-reduced-transparency', 'prefers-contrast: more',
    ]:
        assert marker in source
    assert "model-selector" not in source
    assert "agent-selector" not in source
    assert "provider-selector" not in source


def test_shell_derives_preview_and_read_only_timeline_from_project_state(tmp_path: Path):
    source = ui_source()

    for marker in [
        "playableArtifact", "StudioStage", "Timeline", "segments",
        "artifacts_state", "verified_artifact", "plan.steps", "input_manifest",
        "preview-video", "empty-stage", "playhead", "audio-wave",
        "Обзор монтажа", "формируется из плана",
    ]:
        assert marker in source


def test_shell_context_rail_groups_assistant_files_results_and_versions(tmp_path: Path):
    source = ui_source()

    for marker in [
        "setTab", "Conversation", "FileLibrary", "groupMaterials", "allArtifacts", "composer",
        "Помощник", "Файлы", "Исходники", "Результаты", "Версии",
        "api.open_artifact", "api.open_project_folder",
    ]:
        assert marker in source


def test_shell_keeps_questions_operations_and_errors_compact_in_assistant(tmp_path: Path):
    source = ui_source()
    conversation = (UI / "src" / "components" / "Conversation.tsx").read_text(encoding="utf-8")

    for marker in [
        "OperationCard", "QuestionCard", "PlanCard", "ResultCard",
        "aria-live=\"polite\"", "role=\"alert\"", "entry.active === false",
        "operation_status", "cancel_operation", "resume_operation",
    ]:
        assert marker in source
    assert "alert(" not in source
    # An expression-bodied effect can expose scrollIntoView()'s host return
    # value as a React cleanup and crash when the panel tree unmounts.
    assert 'useEffect(() => endRef.current?.scrollIntoView' not in conversation


def test_shell_explains_project_progress_and_recovers_preview_failures(tmp_path: Path):
    source = ui_source()

    for marker in [
        'className="stage-meter"', "STAGES", "status.stage",
        "previewFailed", "onError", "Предпросмотр недоступен",
        'aria-label="Режим работы"', 'aria-label="Задача или правка"',
        'meta name="theme-color"', "color-scheme: dark",
    ]:
        assert marker in source or marker in TestClient(create_app(root=tmp_path)).get("/").text


def test_shell_keeps_compact_questions_submittable_and_files_actionable(tmp_path: Path):
    source = ui_source()

    for marker in [
        "questions", "questions.every", "MaterialGroup",
        "parent_version_id", "playableArtifact", "Смотреть", "material-group",
        'aria-label="Раздел инспектора"', "Tabs.Trigger", "timeline-segment",
    ]:
        assert marker in source
    assert 'class="assistant-stream"' not in source


def test_shell_exposes_project_actions_and_persistent_workspace_splitters(tmp_path: Path):
    source = ui_source()

    for marker in [
        "DropdownMenu", "Переименовать", "AlertDialog", "api.delete_project", "Удалить проект",
        "Group", "Panel", "Separator", "usePanelRef", "defaultSize", "minSize", "maxSize",
        "localStorage.setItem", "resetLayout", "Сбросить расположение",
    ]:
        assert marker in source


def test_shell_collapses_panels_and_clamps_layout_for_windowed_mode(tmp_path: Path):
    source = ui_source()

    for marker in [
        "leftRef.current?.collapse", "rightRef.current?.collapse", "timelineRef.current?.collapse",
        "leftOpen", "rightOpen", "timelineOpen", "window.innerWidth",
        'window.addEventListener("resize"', "compact-window", "aria-expanded",
        "Показать проекты", "Скрыть помощника", "Показать обзор монтажа",
    ]:
        assert marker in source
    assert "minmax(0,1fr)" in source
    assert "mobile-sheet" in source


def test_shell_uses_a_complete_apple_inspired_dark_material_system(tmp_path: Path):
    styles = (UI / "src" / "styles.css").read_text(encoding="utf-8")

    for marker in [
        "color-scheme: dark", "--surface-1: #121214", "--surface-2: #171719",
        "--surface-3: #1e1e21", "--text: #f4f4f5", "--text-2: #b5b5bb",
        "--line: rgba(255,255,255,.075)", ".project-rail", ".message", ".composer",
        ".dialog-card", "prefers-reduced-transparency: reduce",
    ]:
        assert marker in styles


def test_chat_api_returns_structured_summary(tmp_path: Path):
    client = TestClient(create_app(
        root=tmp_path,
        ollama_chat=lambda payload: {"message": {"content": '{"answer":"План готов", "summary":["Проверил материал"]}'}},
    ))

    response = client.post("/api/chat", json={"message": "Составь план"})

    assert response.json()["answer"] == "План готов"
    assert response.json()["summary"] == ["Проверил материал"]
