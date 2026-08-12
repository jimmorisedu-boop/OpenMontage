import time
from pathlib import Path

from scripts.openmontage_chat.operation_manager import OperationCancelled, OperationManager


def test_operation_returns_immediately_and_persists_completion(tmp_path: Path):
    manager = OperationManager(tmp_path)
    started = time.monotonic()
    operation = manager.start("project", "plan", lambda control: (time.sleep(0.08), {"status": "ready"})[1])

    assert time.monotonic() - started < 0.05
    assert operation["status"] in {"queued", "running"}
    deadline = time.monotonic() + 2
    while manager.get(operation["operation_id"])["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)
    restored = OperationManager(tmp_path).get(operation["operation_id"])
    assert restored["status"] == "completed"
    assert restored["result"]["status"] == "ready"


def test_cancel_is_cooperative_and_survives_restart(tmp_path: Path):
    manager = OperationManager(tmp_path)

    def work(control):
        while True:
            control.raise_if_cancelled()
            time.sleep(0.01)

    operation = manager.start("project", "plan", work)
    manager.cancel(operation["operation_id"])
    deadline = time.monotonic() + 2
    while manager.get(operation["operation_id"])["status"] not in {"cancelled", "failed"} and time.monotonic() < deadline:
        time.sleep(0.01)

    assert OperationManager(tmp_path).get(operation["operation_id"])["status"] == "cancelled"


def test_running_operation_is_recoverable_after_process_restart(tmp_path: Path):
    state = tmp_path / "operations.json"
    state.write_text('{"version":"1.0","operations":[{"operation_id":"op","project_id":"p","plan_id":"x","status":"running"}]}', encoding="utf-8")

    operation = OperationManager(tmp_path).get("op")

    assert operation["status"] == "interrupted"
    assert operation["can_resume"] is True


def test_interrupted_operation_can_resume_with_same_identity(tmp_path: Path):
    manager = OperationManager(tmp_path)
    manager.path.write_text('{"version":"1.0","operations":[{"operation_id":"op","project_id":"p","plan_id":"x","status":"interrupted","can_resume":true}]}', encoding="utf-8")

    resumed = manager.resume("op", lambda control: {"status": "ready"})
    deadline = time.monotonic() + 2
    while manager.get(resumed["operation_id"])["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)

    assert manager.get("op")["status"] == "completed"
