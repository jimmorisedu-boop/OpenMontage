from __future__ import annotations

import json
from pathlib import Path

from lib.checkpoint import init_project
from lib.input_manifest import InputPriority, register_download, register_inputs
from schemas.artifacts import validate_artifact


def _project(tmp_path: Path) -> Path:
    return init_project(
        "mixed", title="Mixed", pipeline_type="cinematic", pipeline_dir=tmp_path / "projects"
    )


def test_registers_mixed_files_and_preserves_unknown_formats(tmp_path):
    project = _project(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    names = [
        "footage.mp4", "voice.wav", "storyboard.png", "script.docx", "brief.pdf",
        "notes.txt", "captions.srt", "captions.vtt", "cut.edl", "timeline.xml",
        "logging.csv", "mystery.xyz",
    ]
    for name in names:
        (source / name).write_bytes(name.encode())

    manifest = register_inputs(
        "mixed", [str(source)], priority=InputPriority.REFERENCE, pipeline_dir=tmp_path / "projects"
    )
    validate_artifact("input_manifest", manifest)

    assert [Path(item["path"]).name for item in manifest["inputs"]] == sorted(names)
    by_name = {Path(item["path"]).name: item for item in manifest["inputs"]}
    assert by_name["footage.mp4"]["media_type"] == "video"
    assert by_name["voice.wav"]["media_type"] == "audio"
    assert by_name["storyboard.png"]["role"] == "storyboard"
    assert by_name["script.docx"]["role"] == "script"
    assert by_name["captions.srt"]["media_type"] == "subtitle"
    assert by_name["cut.edl"]["media_type"] == "edit-data"
    assert by_name["mystery.xyz"]["interpretation_status"] == "unsupported"
    assert all(item["priority"] == "reference" for item in manifest["inputs"])
    assert all(Path(item["path"]).is_absolute() for item in manifest["inputs"])
    assert all(item["relationships"] == [] for item in manifest["inputs"])
    assert all((source / name).read_bytes() == name.encode() for name in names)
    assert (project / "artifacts" / "input_manifest.json").is_file()


def test_registration_is_stable_and_does_not_duplicate_inputs(tmp_path):
    _project(tmp_path)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    first = register_inputs(
        "mixed", [str(source)], priority=InputPriority.REQUIRED, pipeline_dir=tmp_path / "projects"
    )
    second = register_inputs(
        "mixed", [str(source)], priority=InputPriority.REQUIRED, pipeline_dir=tmp_path / "projects"
    )
    assert first["inputs"][0]["id"] == second["inputs"][0]["id"]
    assert len(second["inputs"]) == 1


def test_register_download_records_url_checksum_and_metadata(tmp_path):
    project = _project(tmp_path)
    downloaded = project / "inputs" / "downloads" / "public.mp4"
    downloaded.write_bytes(b"downloaded")
    manifest = register_download(
        "mixed",
        "https://example.com/public.mp4",
        downloaded,
        {"redirect_url": "https://cdn.example.com/public.mp4", "extractor": "fixture"},
        pipeline_dir=tmp_path / "projects",
    )
    item = manifest["inputs"][0]
    assert item["source_kind"] == "download"
    assert item["source_url"] == "https://example.com/public.mp4"
    assert len(item["sha256"]) == 64
    assert item["provenance"]["extractor"] == "fixture"


def test_init_project_creates_input_layout_and_valid_empty_manifest(tmp_path):
    project = _project(tmp_path)
    assert (project / "inputs" / "downloads").is_dir()
    assert (project / "inputs" / "derivatives").is_dir()
    manifest = json.loads((project / "artifacts" / "input_manifest.json").read_text("utf-8"))
    validate_artifact("input_manifest", manifest)
    assert manifest == {"version": "1.0", "project_id": "mixed", "inputs": []}
