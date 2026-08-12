from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any


class ContextViolation(RuntimeError):
    pass


class ContextStore:
    def __init__(self, state_root: Path) -> None:
        self.root = state_root.resolve() / "mcp-contexts"

    def _path(self, conversation_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", conversation_id)
        return self.root / f"{safe}.json"

    def bootstrap(self, project_id: str, hidden: dict[str, Any], revision: int) -> dict[str, Any]:
        conversation_id = str(hidden.get("conversation_id", ""))
        if not conversation_id or int(hidden.get("thread_revision", -1)) != 0 or not hidden.get("nonce"):
            raise ContextViolation("Malformed Jan bootstrap context")
        record = {
            "conversation_id": conversation_id,
            "project_id": project_id,
            "thread_revision": revision,
            "nonce": secrets.token_urlsafe(32),
        }
        self.write(record)
        return dict(record)

    def write(self, record: dict[str, Any]) -> None:
        path = self._path(record["conversation_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        temporary.replace(path)

    def validate(self, hidden: dict[str, Any]) -> dict[str, Any]:
        conversation_id = str(hidden.get("conversation_id", ""))
        path = self._path(conversation_id)
        if not path.is_file():
            raise ContextViolation("Unknown conversation context")
        record = json.loads(path.read_text(encoding="utf-8"))
        for key in ("conversation_id", "thread_revision", "nonce"):
            if hidden.get(key) != record.get(key):
                raise ContextViolation(f"Stale or malformed hidden context field: {key}")
        return record

