from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_seed_profile_is_relocatable_and_local_only(tmp_path: Path):
    portable_root = tmp_path / "OpenMontage Portable"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "seed_jan_profile.py"),
            "--root",
            str(portable_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    data = portable_root / "runtime" / "jan-data" / "data"

    assistant = json.loads(
        (data / "assistants" / "openmontage" / "assistant.json").read_text(
            encoding="utf-8"
        )
    )
    mcp = json.loads((data / "mcp_config.json").read_text(encoding="utf-8"))
    profile = json.loads((data / "openmontage_profile.json").read_text(encoding="utf-8"))

    assert report["data_root"] == str(data.resolve())
    assert assistant["id"] == "openmontage"
    assert assistant["model"] == "openmontage-gpt-oss:20b-32k"
    assert "AGENT_GUIDE.md" in assistant["instructions"]
    assert "pipeline" in assistant["instructions"].lower()
    assert "Walter Murch" in assistant["instructions"]

    assert list(mcp["mcpServers"]) == ["OpenMontage"]
    server = mcp["mcpServers"]["OpenMontage"]
    assert server["command"] == "runtime/python/python.exe"
    assert server["args"] == ["-m", "scripts.openmontage_mcp.server"]
    assert server["env"]["OPENMONTAGE_ROOT"] == "."
    assert server["env"]["OPENMONTAGE_NETWORK_MODE"] == "url-import-only"
    assert mcp["mcpSettings"]["enableSmartToolRouting"] is False

    assert profile["provider"]["base_url"] == "http://127.0.0.1:11434/v1"
    assert profile["provider"]["api_key"] == "ollama-local"
    assert [model["id"] for model in profile["provider"]["models"]] == [
        "openmontage-gpt-oss:20b-32k"
    ]
    assert profile["vision_model"] == "qwen3.5:9b"
    assert profile["vision_model_visible"] is False
    serialized = json.dumps({"assistant": assistant, "mcp": mcp, "profile": profile})
    assert str(portable_root.resolve()) not in serialized
    assert "https://" not in serialized


def test_seed_profile_is_idempotent(tmp_path: Path):
    portable_root = tmp_path / "portable"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "seed_jan_profile.py"),
        "--root",
        str(portable_root),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {
        path.relative_to(portable_root): path.read_bytes()
        for path in portable_root.rglob("*")
        if path.is_file()
    }
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {
        path.relative_to(portable_root): path.read_bytes()
        for path in portable_root.rglob("*")
        if path.is_file()
    }
    assert second == first

