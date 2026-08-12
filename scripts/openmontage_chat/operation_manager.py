from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationCancelled(RuntimeError):
    pass


class OperationControl:
    def __init__(self, manager: "OperationManager", operation_id: str) -> None:
        self.manager = manager
        self.operation_id = operation_id

    def raise_if_cancelled(self) -> None:
        if self.manager.get(self.operation_id).get("cancel_requested"):
            raise OperationCancelled("Operation cancelled")

    def progress(self, label: str, *, current: int | None = None, total: int | None = None) -> None:
        changes: dict[str, Any] = {"progress_label": label}
        if current is not None:
            changes["current"] = current
        if total is not None:
            changes["total"] = total
        self.manager.update(self.operation_id, **changes)


class OperationManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / "operations.json"
        self._lock = threading.RLock()
        if not self.path.is_file():
            self._write({"version": "1.0", "operations": []})
        state = self._read()
        changed = False
        for operation in state["operations"]:
            if operation.get("status") in {"queued", "running", "cancelling"}:
                operation.update(status="interrupted", can_resume=True, updated_at=_now())
                changed = True
        if changed:
            self._write(state)

    def _read(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, state: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def get(self, operation_id: str) -> dict[str, Any]:
        for operation in self._read()["operations"]:
            if operation.get("operation_id") == operation_id:
                return operation
        raise KeyError("Operation not found")

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        values = self._read()["operations"]
        return [item for item in values if not project_id or item.get("project_id") == project_id]

    def update(self, operation_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            for operation in state["operations"]:
                if operation.get("operation_id") == operation_id:
                    operation.update(changes, updated_at=_now())
                    self._write(state)
                    return operation.copy()
        raise KeyError("Operation not found")

    def start(self, project_id: str, plan_id: str, work: Callable[[OperationControl], dict[str, Any]]) -> dict[str, Any]:
        operation_id = uuid.uuid4().hex
        operation = {
            "operation_id": operation_id, "project_id": project_id, "plan_id": plan_id,
            "status": "queued", "cancel_requested": False, "can_resume": False,
            "created_at": _now(), "updated_at": _now(),
        }
        with self._lock:
            state = self._read()
            state["operations"].append(operation)
            self._write(state)

        self._launch(operation_id, work)
        return self.get(operation_id)

    def _launch(self, operation_id: str, work: Callable[[OperationControl], dict[str, Any]]) -> None:
        def runner() -> None:
            self.update(operation_id, status="running")
            try:
                result = work(OperationControl(self, operation_id))
                self.update(operation_id, status="completed", result=result, can_resume=False)
            except OperationCancelled:
                self.update(operation_id, status="cancelled", can_resume=True)
            except Exception as exc:
                self.update(operation_id, status="failed", error=str(exc), can_resume=True)

        threading.Thread(target=runner, name=f"openmontage-{operation_id[:8]}", daemon=True).start()

    def resume(self, operation_id: str, work: Callable[[OperationControl], dict[str, Any]]) -> dict[str, Any]:
        operation = self.get(operation_id)
        if operation.get("status") not in {"interrupted", "cancelled", "failed"}:
            raise ValueError("Operation cannot be resumed")
        self.update(operation_id, status="queued", cancel_requested=False, can_resume=False, error=None)
        self._launch(operation_id, work)
        return self.get(operation_id)

    def cancel(self, operation_id: str) -> dict[str, Any]:
        operation = self.get(operation_id)
        if operation.get("status") not in {"queued", "running"}:
            return operation
        return self.update(operation_id, status="cancelling", cancel_requested=True)
