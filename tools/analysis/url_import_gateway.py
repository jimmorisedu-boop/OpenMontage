"""The sole short-lived outbound gateway for explicit public media URLs."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from lib.input_manifest import register_download
from lib.network_policy import validate_public_import_url
from scripts.portable_runtime_layout import resolve_layout
from tools.analysis.video_downloader import detect_platform
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _run(args, *, cwd: Path, env: dict[str, str], timeout: int):
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        else:
            process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


class URLImportGateway(BaseTool):
    name = "url_import_gateway"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "source_ingest"
    provider = "yt-dlp"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=4096, network_required=True)
    agent_skills = ["video-download"]
    side_effects = ["downloads the exact user-submitted public URL into project inputs/downloads"]
    input_schema = {
        "type": "object",
        "required": ["project_id", "url", "bulk_approved"],
        "properties": {
            "project_id": {"type": "string"},
            "url": {"type": "string"},
            "bulk_approved": {"type": "boolean"},
            "expected_item_count": {"type": ["integer", "null"]},
        },
    }

    def __init__(
        self,
        *,
        root: Path | None = None,
        pipeline_dir: Path | None = None,
        runner: Runner = _run,
        timeout_seconds: int = 1800,
    ) -> None:
        self.root = (root or Path(__file__).resolve().parents[2]).resolve()
        self.pipeline_dir = (pipeline_dir or self.root / "projects").resolve()
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _cleanup_partial(downloads: Path) -> None:
        for pattern in ("*.part", "*.partial", "*.ytdl"):
            for path in downloads.glob(pattern):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _environment(self, temp: Path, executable: Path, ffmpeg: Path) -> dict[str, str]:
        temp.mkdir(parents=True, exist_ok=True)
        environment = {
            key: os.environ[key]
            for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")
            if key in os.environ
        }
        environment.update(
            {
                "PATH": os.pathsep.join((str(executable.parent), str(ffmpeg.parent))),
                "TEMP": str(temp),
                "TMP": str(temp),
                "HOME": str(temp),
                "NO_COLOR": "1",
            }
        )
        return environment

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        project_id = str(inputs["project_id"])
        url = str(inputs["url"]).strip()
        validate_public_import_url(url)
        project = (self.pipeline_dir / project_id).resolve()
        downloads = (project / "inputs" / "downloads").resolve()
        if not (project / "project.json").is_file() or not downloads.is_dir():
            return ToolResult(success=False, error=f"OpenMontage project is not initialized: {project_id}")

        layout = resolve_layout(self.root)
        executable = Path(layout.ytdlp_exe)
        ffmpeg = Path(layout.ffmpeg_exe)
        if not executable.is_file() or not ffmpeg.is_file():
            return ToolResult(success=False, error="Pinned yt-dlp or FFmpeg artifact is missing; run portable setup")
        temp = Path(layout.temp_dir) / "url-import" / project_id
        environment = self._environment(temp, executable, ffmpeg)
        common = [str(executable), "--ignore-config", "--no-update", "--no-warnings"]
        metadata_args = common + [
            "--dump-single-json", "--skip-download", "--flat-playlist", "--playlist-end", "101", url,
        ]
        try:
            metadata_result = self.runner(
                metadata_args, cwd=downloads, env=environment, timeout=min(self.timeout_seconds, 120)
            )
            if metadata_result.returncode != 0:
                return ToolResult(success=False, error=f"URL metadata probe failed: {metadata_result.stderr.strip()}")
            metadata = json.loads(metadata_result.stdout)
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            self._cleanup_partial(downloads)
            return ToolResult(success=False, error=f"URL metadata probe failed: {exc}")

        entries = [entry for entry in metadata.get("entries", []) if entry] if isinstance(metadata, dict) else []
        count = len(entries) if entries else 1
        if count > 1 and not bool(inputs.get("bulk_approved")):
            return ToolResult(success=False, error=f"Bulk approval required for {count} playlist/profile items")
        expected = inputs.get("expected_item_count")
        if expected is not None and int(expected) != count:
            return ToolResult(success=False, error=f"Item-count mismatch: expected {expected}, discovered {count}")

        before = {path.resolve() for path in downloads.iterdir() if path.is_file()}
        playlist_flag = "--yes-playlist" if count > 1 else "--no-playlist"
        download_args = common + [
            playlist_flag,
            "--windows-filenames",
            "--restrict-filenames",
            "--merge-output-format", "mp4",
            "--ffmpeg-location", str(ffmpeg.parent),
            "--output", "%(id)s-%(title).80B.%(ext)s",
            "--print", "after_move:filepath",
            url,
        ]
        try:
            result = self.runner(
                download_args, cwd=downloads, env=environment, timeout=self.timeout_seconds
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"yt-dlp exited {result.returncode}")
        except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
            self._cleanup_partial(downloads)
            return ToolResult(success=False, error=f"Download failed: {exc}")

        self._cleanup_partial(downloads)
        output_lines = [Path(line.strip()).resolve() for line in result.stdout.splitlines() if line.strip()]
        candidates = [path for path in output_lines if path.is_file() and path.is_relative_to(downloads)]
        if not candidates:
            candidates = sorted(
                (path.resolve() for path in downloads.iterdir() if path.is_file() and path.resolve() not in before),
                key=str,
            )
        if len(candidates) != count:
            return ToolResult(success=False, error=f"Item-count mismatch after download: expected {count}, got {len(candidates)}")

        manifests = []
        for local_path in candidates:
            manifests.append(
                register_download(
                    project_id,
                    url,
                    local_path,
                    {
                        "provider": "yt-dlp",
                        "platform": detect_platform(url),
                        "metadata": metadata,
                        "resolved_url": metadata.get("webpage_url") or metadata.get("original_url") or url,
                    },
                    pipeline_dir=self.pipeline_dir,
                )
            )
        return ToolResult(
            success=True,
            data={"paths": [str(path) for path in candidates], "item_count": count, "metadata": metadata},
            artifacts=[str(path) for path in candidates],
            duration_seconds=round(time.monotonic() - started, 2),
        )
