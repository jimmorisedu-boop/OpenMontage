from __future__ import annotations

import argparse
import json
from pathlib import Path


VISIBLE_MODEL = "openmontage-gpt-oss:20b-32k"
VISION_MODEL = "qwen3.5:9b"

ASSISTANT_INSTRUCTIONS = """You are OpenMontage, a fully local video-editing agent.
Reply in the language of the user's latest message. Work only inside the portable
OpenMontage root and through the supplied OpenMontage MCP tools.

Before production work, read AGENT_GUIDE.md, select and read the applicable
pipeline manifest, run preflight, and follow every stage, quality gate,
checkpoint, approval, provenance, and decision-log contract. Accept mixed input:
video, audio, images, storyboard, screenplay, subtitles, edit files, folders,
notes, explanations, and public URLs. A URL may be used only by the controlled
import tool to create a local input; all later work is local.

For editing judgment, read skills/creative/references/editorial-principles.md.
Apply its attributed paraphrases: Walter Murch prioritizes emotion, story and
rhythm; Karen Pearlman distinguishes timing, pacing and embodied trajectory;
Karel Reisz and Gavin Millar relate technique to dramatic function; Edward
Dmytryk requires a positive reason for consequential cuts and protects
performance; Michael Ondaatje's conversations with Murch support comparing
versions and repeatedly reviewing the whole. Turn these principles into clear,
specific editing instructions with timecodes and reasons. Never reproduce book
passages or imply that you consulted book text unavailable in the repository.

The visible orchestration model is fixed. The hidden vision reviewer is an
internal OpenMontage implementation detail: do not offer it as a chat model.
Respect the conversation permission mode (Auto, Confirm, or Read-only) and never
claim a write succeeded until the tool result confirms it.
"""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def seed(root: Path) -> dict[str, str]:
    root = root.resolve()
    data = root / "runtime" / "jan-data" / "data"
    assistant_path = data / "assistants" / "openmontage" / "assistant.json"
    mcp_path = data / "mcp_config.json"
    profile_path = data / "openmontage_profile.json"

    assistant = {
        "id": "openmontage",
        "name": "OpenMontage",
        "description": "Локальный ассистент по монтажу и видеопроизводству",
        "avatar": "🎬",
        "model": VISIBLE_MODEL,
        "instructions": ASSISTANT_INSTRUCTIONS,
        "parameters": {
            "temperature": 0.6,
            "top_p": 0.9,
            "repeat_penalty": 1.08,
        },
    }
    mcp = {
        "mcpServers": {
            "OpenMontage": {
                "command": "runtime/python/python.exe",
                "args": ["-m", "scripts.openmontage_mcp.server"],
                "env": {
                    "OPENMONTAGE_ROOT": ".",
                    "OPENMONTAGE_NETWORK_MODE": "url-import-only",
                    "PYTHONNOUSERSITE": "1",
                },
                "active": True,
                "official": True,
            }
        },
        "mcpSettings": {
            "toolCallTimeoutSeconds": 300,
            "baseRestartDelayMs": 1000,
            "maxRestartDelayMs": 30000,
            "backoffMultiplier": 2.0,
            "enableSmartToolRouting": False,
            "useLightweightRouterModel": False,
            "routerModelProvider": "",
            "routerModelId": "",
        },
    }
    profile = {
        "schema_version": 1,
        "provider": {
            "active": True,
            "provider": "openmontage-ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key": "ollama-local",
            "settings": [],
            "models": [
                {
                    "id": VISIBLE_MODEL,
                    "name": "OpenMontage Local",
                    "displayName": "OpenMontage Local",
                    "capabilities": ["tools"],
                }
            ],
        },
        "assistant_id": "openmontage",
        "vision_model": VISION_MODEL,
        "vision_model_visible": False,
        "permission_mode_default": "confirm",
    }

    _write_json(assistant_path, assistant)
    _write_json(mcp_path, mcp)
    _write_json(profile_path, profile)
    return {
        "data_root": str(data.resolve()),
        "assistant": str(assistant_path.resolve()),
        "mcp_config": str(mcp_path.resolve()),
        "profile": str(profile_path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the portable Jan profile")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    print(json.dumps(seed(args.root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
