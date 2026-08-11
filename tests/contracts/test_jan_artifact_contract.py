from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def test_jan_artifact_manifest_is_immutable_and_complete():
    data = json.loads(
        (ROOT / "config" / "runtime" / "artifacts.json").read_text(encoding="utf-8")
    )

    assert data["runtime_policy"] == "checksummed-only"
    jan = data["jan"]
    assert jan == {
        "tag": "v0.8.0",
        "commit": "042bf6dc0c9a0a93baf66c8fe5bc2654f095258e",
        "source_url": "https://github.com/janhq/jan/archive/refs/tags/v0.8.0.zip",
        "source_sha256": "d74fff3a692dc1f7cd38b03f9ecd277ac1119b37d02539e317df3d8cb626fd57",
        "portable_url": "https://github.com/jimmorisedu-boop/OpenMontage/releases/download/openmontage-jan-v0.8.0/OpenMontage-Jan-v0.8.0.exe",
        "portable_sha256": "cca5ce9c2043cbd7076e724e7ffa19086a4912f5e4343ea0a8623f06a5873276",
        "output": "runtime/jan/Jan.exe",
    }
    assert GIT_SHA.fullmatch(jan["commit"])
    assert SHA256.fullmatch(jan["source_sha256"])
    assert "latest" not in jan["source_url"].lower()


def test_jan_integration_contains_the_reproducible_inputs():
    required = [
        ROOT / "integrations" / "jan" / "LICENSE.upstream",
        ROOT / "integrations" / "jan" / "README.md",
        ROOT / "integrations" / "jan" / "patches" / "0001-openmontage-shell.patch",
        ROOT / "scripts" / "build_jan_portable.ps1",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert missing == []


def test_hosted_builder_produces_a_hashed_portable_executable():
    workflow_path = ROOT / ".github" / "workflows" / "build-portable-jan.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert workflow["permissions"]["contents"] == "write"
    job = workflow["jobs"]["build-portable-jan"]
    assert job["runs-on"] == "windows-latest"
    step_names = [step["name"] for step in job["steps"]]
    assert step_names == [
        "Checkout OpenMontage integration",
        "Checkout pinned Jan source",
        "Apply OpenMontage patch",
        "Configure Jan build tools",
        "Build Jan",
        "Test portable runtime patch",
        "Package portable executable",
        "Upload workflow artifact",
        "Publish portable release asset",
    ]
    configure = next(step for step in job["steps"] if step["name"] == "Configure Jan build tools")
    assert "corepack enable --install-directory" in configure["run"]
    assert "$env:GITHUB_PATH" in configure["run"]
    patch_step = next(step for step in job["steps"] if step["name"] == "Apply OpenMontage patch")
    assert patch_step["run"].count("git -C .jan-source apply --unidiff-zero") == 2


def test_build_helper_validates_the_hosted_build_contract():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "build_jan_portable.ps1"),
            "-ValidateOnly",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "valid"
    assert payload["builder"] == "github-actions"
    assert payload["workflow"] == ".github/workflows/build-portable-jan.yml"


def test_boundary_probe_accepts_an_empty_external_snapshot():
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "build_jan_portable.ps1"),
            "-ProbePortableBoundary",
            "-ProbeExecutable",
            str(Path(subprocess.__file__).parents[1] / "python.exe"),
            "-ProbeSeconds",
            "1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Portable Jan boundary probe passed." in result.stdout
