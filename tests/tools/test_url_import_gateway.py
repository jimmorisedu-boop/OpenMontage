from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lib.checkpoint import init_project
from lib.network_policy import NetworkViolation
from tools.analysis.url_import_gateway import URLImportGateway


class FakeRunner:
    def __init__(self, root: Path, metadata: dict | None = None, *, fail: Exception | None = None):
        self.root = root
        self.metadata = metadata or {"id": "v1", "title": "Public clip", "webpage_url": "https://example.com/v"}
        self.fail = fail
        self.calls = []

    def __call__(self, args, *, cwd, env, timeout):
        self.calls.append((list(args), Path(cwd), dict(env), timeout))
        if len(self.calls) == 1:
            return subprocess.CompletedProcess(args, 0, json.dumps(self.metadata), "")
        if self.fail:
            partial = Path(cwd) / "unfinished.mp4.part"
            partial.write_bytes(b"partial")
            raise self.fail
        output = Path(cwd) / "v1-Public_clip.mp4"
        output.write_bytes(b"video")
        return subprocess.CompletedProcess(args, 0, str(output) + "\n", "")


def _setup(tmp_path: Path):
    projects = tmp_path / "projects"
    init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=projects)
    for relative in ["runtime/downloader/yt-dlp.exe", "runtime/ffmpeg/ffmpeg.exe"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    return projects


def test_import_uses_only_pinned_binaries_and_registers_provenance(tmp_path, monkeypatch):
    projects = _setup(tmp_path)
    runner = FakeRunner(tmp_path)
    gateway = URLImportGateway(root=tmp_path, pipeline_dir=projects, runner=runner)
    monkeypatch.setenv("OPENMONTAGE_NETWORK_MODE", "url-import-only")
    monkeypatch.delenv("OPENMONTAGE_OFFLINE", raising=False)

    result = gateway.execute({"project_id": "film", "url": "https://example.com/v", "bulk_approved": False})
    assert result.success, result.error
    assert len(runner.calls) == 2
    for args, cwd, env, timeout in runner.calls:
        assert Path(args[0]) == tmp_path / "runtime" / "downloader" / "yt-dlp.exe"
        assert "--ignore-config" in args
        assert "--no-update" in args
        assert not any("cookie" in arg.lower() for arg in args)
        assert cwd == projects / "film" / "inputs" / "downloads"
        assert env["TEMP"].startswith(str(tmp_path / "runtime" / "temp"))
    manifest = json.loads((projects / "film" / "artifacts" / "input_manifest.json").read_text("utf-8"))
    item = manifest["inputs"][0]
    assert item["source_url"] == "https://example.com/v"
    assert len(item["sha256"]) == 64
    assert item["provenance"]["metadata"]["title"] == "Public clip"


def test_playlist_requires_explicit_bulk_approval_and_count(tmp_path, monkeypatch):
    projects = _setup(tmp_path)
    metadata = {"_type": "playlist", "entries": [{"id": "1"}, {"id": "2"}]}
    monkeypatch.setenv("OPENMONTAGE_NETWORK_MODE", "url-import-only")
    gateway = URLImportGateway(root=tmp_path, pipeline_dir=projects, runner=FakeRunner(tmp_path, metadata))
    blocked = gateway.execute({"project_id": "film", "url": "https://example.com/list", "bulk_approved": False})
    assert not blocked.success
    assert "bulk approval" in blocked.error.lower()
    gateway = URLImportGateway(root=tmp_path, pipeline_dir=projects, runner=FakeRunner(tmp_path, metadata))
    mismatch = gateway.execute({
        "project_id": "film", "url": "https://example.com/list", "bulk_approved": True, "expected_item_count": 3,
    })
    assert not mismatch.success
    assert "item-count mismatch" in mismatch.error.lower()


def test_timeout_removes_partial_files(tmp_path, monkeypatch):
    projects = _setup(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_NETWORK_MODE", "url-import-only")
    gateway = URLImportGateway(
        root=tmp_path,
        pipeline_dir=projects,
        runner=FakeRunner(tmp_path, fail=subprocess.TimeoutExpired("yt-dlp", 1)),
    )
    result = gateway.execute({"project_id": "film", "url": "https://example.com/v", "bulk_approved": False})
    assert not result.success
    assert not list((projects / "film" / "inputs" / "downloads").glob("*.part"))


def test_strict_offline_rejects_gateway_before_runner(tmp_path, monkeypatch):
    projects = _setup(tmp_path)
    runner = FakeRunner(tmp_path)
    gateway = URLImportGateway(root=tmp_path, pipeline_dir=projects, runner=runner)
    monkeypatch.setenv("OPENMONTAGE_OFFLINE", "1")
    with pytest.raises(NetworkViolation):
        gateway.execute({"project_id": "film", "url": "https://example.com/v", "bulk_approved": False})
    assert runner.calls == []
