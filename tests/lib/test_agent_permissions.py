from __future__ import annotations

from pathlib import Path

import pytest

from lib.agent_permissions import (
    OperationKind,
    PermissionContext,
    PermissionDenied,
    PermissionMode,
    authorize,
    mint_approval_token,
    set_permission_mode,
)


def _context(tmp_path: Path) -> PermissionContext:
    project = tmp_path / "projects" / "film"
    runtime = tmp_path / "runtime" / "state"
    source = tmp_path / "external" / "source.mp4"
    project.mkdir(parents=True)
    runtime.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original")
    return PermissionContext("chat-1", "film", project, runtime, (source,))


@pytest.mark.parametrize("mode", list(PermissionMode))
def test_all_modes_allow_declared_input_reads(tmp_path, mode):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, mode)
    authorize(ctx, mode, OperationKind.READ, [ctx.declared_inputs[0]])


def test_read_only_rejects_every_mutation(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.READ_ONLY)
    for operation in [OperationKind.WRITE, OperationKind.COMMAND, OperationKind.DOWNLOAD, OperationKind.RENDER, OperationKind.DELETE]:
        with pytest.raises(PermissionDenied, match="read-only"):
            authorize(ctx, PermissionMode.READ_ONLY, operation, [ctx.project_root / "out.mp4"])


def test_auto_allows_project_work_but_never_overwrites_sources(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.AUTO)
    authorize(ctx, PermissionMode.AUTO, OperationKind.WRITE, [ctx.project_root / "notes.txt"])
    authorize(ctx, PermissionMode.AUTO, OperationKind.RENDER, [ctx.project_root / "renders" / "final.mp4"])
    authorize(ctx, PermissionMode.AUTO, OperationKind.WRITE, [ctx.runtime_state_root / "job.json"])
    with pytest.raises(PermissionDenied, match="source original"):
        authorize(ctx, PermissionMode.AUTO, OperationKind.WRITE, [ctx.declared_inputs[0]])
    with pytest.raises(PermissionDenied, match="approval"):
        authorize(ctx, PermissionMode.AUTO, OperationKind.DELETE, [ctx.project_root / "draft.txt"])


def test_confirm_requires_single_use_operation_bound_token(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.CONFIRM)
    target = ctx.project_root / "render.mp4"
    with pytest.raises(PermissionDenied, match="approval"):
        authorize(ctx, PermissionMode.CONFIRM, OperationKind.RENDER, [target])
    token = mint_approval_token(ctx, OperationKind.RENDER, [target], ttl_seconds=60)
    authorize(ctx, PermissionMode.CONFIRM, OperationKind.RENDER, [target], approval_token=token)
    with pytest.raises(PermissionDenied, match="used"):
        authorize(ctx, PermissionMode.CONFIRM, OperationKind.RENDER, [target], approval_token=token)


def test_mode_revision_invalidates_existing_approval(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.CONFIRM)
    target = ctx.project_root / "out.txt"
    token = mint_approval_token(ctx, OperationKind.WRITE, [target])
    set_permission_mode(ctx, PermissionMode.AUTO)
    set_permission_mode(ctx, PermissionMode.CONFIRM)
    with pytest.raises(PermissionDenied, match="stale"):
        authorize(ctx, PermissionMode.CONFIRM, OperationKind.WRITE, [target], approval_token=token)


@pytest.mark.parametrize("raw", [r"\\server\share\file", r"\\?\C:\device-path"])
def test_rejects_unc_and_device_paths(tmp_path, raw):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.AUTO)
    with pytest.raises(PermissionDenied):
        authorize(ctx, PermissionMode.AUTO, OperationKind.READ, [Path(raw)])


def test_rejects_traversal_external_writes_and_symlink_escape(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.AUTO)
    outside = tmp_path / "outside.txt"
    with pytest.raises(PermissionDenied, match="outside"):
        authorize(ctx, PermissionMode.AUTO, OperationKind.WRITE, [ctx.project_root / ".." / ".." / "outside.txt"])
    link = ctx.project_root / "escape"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(PermissionDenied, match="outside"):
        authorize(ctx, PermissionMode.AUTO, OperationKind.WRITE, [link / "escaped.txt"])


def test_rejects_dangerous_commands_even_in_auto(tmp_path):
    ctx = _context(tmp_path)
    set_permission_mode(ctx, PermissionMode.AUTO)
    with pytest.raises(PermissionDenied, match="dangerous command"):
        authorize(ctx, PermissionMode.AUTO, OperationKind.COMMAND, [ctx.project_root], command="rm -rf /")


def test_mode_changes_are_revisioned_and_appended_to_decision_log(tmp_path):
    ctx = _context(tmp_path)
    first = set_permission_mode(ctx, PermissionMode.CONFIRM)
    second = set_permission_mode(ctx, PermissionMode.READ_ONLY)
    assert (first["revision"], second["revision"]) == (1, 2)
    decisions = __import__("json").loads((ctx.project_root / "decision_log.json").read_text("utf-8"))["decisions"]
    assert [item["category"] for item in decisions] == ["permission_policy", "permission_policy"]
    assert {item["subject"] for item in decisions} == {"Conversation permission mode"}
