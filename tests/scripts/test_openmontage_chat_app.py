from pathlib import Path

from fastapi.testclient import TestClient

from scripts.openmontage_chat.app import DesktopApi, create_app


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
    assert calls[0]["model"] == "openmontage-gpt-oss:20b-32k"
