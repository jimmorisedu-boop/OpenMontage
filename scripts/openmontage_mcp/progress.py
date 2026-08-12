from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperationStore:
    operations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def start(self, attempted: str) -> str:
        operation_id = secrets.token_hex(12)
        self.operations[operation_id] = {"operation_id": operation_id, "attempted": attempted, "status": "running"}
        return operation_id

    def finish(self, operation_id: str, result: dict[str, Any]) -> None:
        self.operations[operation_id] = {
            **self.operations[operation_id],
            "status": "completed" if result.get("ok") else "failed",
            "result": result,
        }

    def get(self, operation_id: str) -> dict[str, Any]:
        return self.operations.get(operation_id, {"operation_id": operation_id, "status": "unknown"})

    def cancel(self, operation_id: str) -> bool:
        item = self.operations.get(operation_id)
        if not item or item["status"] != "running":
            return False
        item["status"] = "cancelled"
        return True

