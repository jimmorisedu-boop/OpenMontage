from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIPELINES = ["talking-head", "clip-factory", "hybrid", "screen-demo", "podcast-repurpose", "cinematic", "localization-dub"]


def test_handbook_covers_portable_local_workflow_and_examples():
    text = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    for phrase in [
        "Установка и запуск", "Что можно подавать на вход",
        "Как поставить хорошую задачу", "Как OpenMontage принимает монтажные решения",
        "Рекомендуемый порядок работы", "Устранение проблем",
        "projects/<project-id>/renders/", "openmontage-gpt-oss:20b-32k", "qwen3.5:9b",
        "раскадровку", "публичную ссылку", "Confirm", "Read-only",
    ]:
        assert phrase in text
    assert "обращаются только к локальным ресурсам" in text


def test_playbook_routes_to_requested_books_and_complete_qa():
    playbook = (ROOT / "skills" / "creative" / "video-editing.md").read_text(encoding="utf-8")
    reference = (ROOT / "skills" / "creative" / "references" / "editorial-principles.md").read_text(encoding="utf-8")
    assert "skills/creative/references/editorial-principles.md" in playbook
    for phrase in ["Editorial contract", "Evidence order", "positive reason", "Cut safety", "Pacing profiles", "Reframing", "Subtitles", "Audio", "QA passes", "edit_decisions"]:
        assert phrase in playbook
    for phrase in ["Walter Murch", "Karen Pearlman", "Karel Reisz", "Gavin Millar", "Edward Dmytryk", "Michael Ondaatje"]:
        assert phrase in reference


def test_source_edit_directors_use_shared_editorial_evidence():
    for name in PIPELINES:
        text = (ROOT / "skills" / "pipelines" / name / "edit-director.md").read_text(encoding="utf-8")
        assert "skills/creative/video-editing.md" in text
        assert "editorial evidence" in text
