from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_primary_guidance_uses_the_owned_jan_shell():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    combined = readme + guide
    assert "START_OPENMONTAGE.bat" in combined
    assert "SETUP_PORTABLE_RUNTIME.bat" in combined
    assert "OpenMontage Local" in combined
    assert "Auto" in guide and "Confirm" in guide and "Read-only" in guide
    assert "раскадров" in guide
    assert "сценар" in guide
    assert "публичную ссылку" in guide


def test_editorial_sources_are_attributed_and_paraphrased():
    guide = (ROOT / "docs" / "LOCAL_TEXT_EDITING_GUIDE.md").read_text(encoding="utf-8")
    required = [
        "Уолтера Мёрча",
        "Карен Перлман",
        "Карелом Райсом",
        "Гэвином Милларом",
        "Эдварда Дмитрика",
        "Майкла Ондаатже",
        "атрибутированные пересказы",
    ]
    for marker in required:
        assert marker in guide


def test_legacy_launcher_only_redirects_to_the_new_entrypoint():
    legacy = (ROOT / "START_OFFLINE_EDITOR.bat").read_text(encoding="utf-8")
    assert "START_OPENMONTAGE.bat" in legacy
    assert "strict offline" not in legacy.lower()
