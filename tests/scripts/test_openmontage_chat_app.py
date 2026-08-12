from pathlib import Path

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
    assert 'accept="video/*,audio/*,image/*,.pdf,.doc,.docx,.txt,.md,.rtf,.csv,.xlsx,.pptx,.srt,.vtt,.ass,.json,.xml,.edl,.fcpxml,.aaf"' in html


def test_chat_shell_shows_compact_progress_and_collapsed_approach(tmp_path: Path):
    html = TestClient(create_app(root=tmp_path)).get("/").text

    assert "Изучаю материалы" in html
    assert "Собираю структуру" in html
    assert "Готовлю ответ" in html
    assert "Как я подошёл к задаче" in html
    assert "document.createElement('details')" in html
    assert "item.textContent=" in html
    assert "startProgress()" in html
    assert "stopProgress()" in html
    assert "fetch(" not in html
    assert "цепочка рассуждений" not in html.lower()


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


def test_chat_api_returns_structured_summary(tmp_path: Path):
    client = TestClient(create_app(
        root=tmp_path,
        ollama_chat=lambda payload: {"message": {"content": '{"answer":"План готов", "summary":["Проверил материал"]}'}},
    ))

    response = client.post("/api/chat", json={"message": "Составь план"})

    assert response.json()["answer"] == "План готов"
    assert response.json()["summary"] == ["Проверил материал"]
