"""Fail-closed permission and path enforcement for Jan MCP conversations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact


class PermissionDenied(RuntimeError):
    pass


class PermissionMode(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    READ_ONLY = "read-only"


class OperationKind(str, Enum):
    READ = "read"
    WRITE = "write"
    COMMAND = "command"
    DOWNLOAD = "download"
    RENDER = "render"
    DELETE = "delete"


@dataclass(frozen=True)
class PermissionContext:
    conversation_id: str
    project_id: str
    project_root: Path
    runtime_state_root: Path
    declared_inputs: tuple[Path, ...]


_DANGEROUS_COMMANDS = re.compile(
    r"(?:\brm\s+-rf\b|\bremove-item\b.*\b-recurse\b|\brmdir\s+/s\b|\bdel\s+/s\b|\bformat(?:\.com)?\b|\bgit\s+reset\s+--hard\b)",
    re.IGNORECASE,
)


def _state_path(ctx: PermissionContext) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", ctx.conversation_id)
    return ctx.runtime_state_root.resolve() / "conversations" / f"{safe}.json"


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def _load_state(ctx: PermissionContext) -> dict[str, Any]:
    path = _state_path(ctx)
    if not path.is_file():
        raise PermissionDenied("Conversation permission mode has not been initialized")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("conversation_id") != ctx.conversation_id or state.get("project_id") != ctx.project_id:
        raise PermissionDenied("Conversation permission state does not match this project")
    return state


def _append_decision(ctx: PermissionContext, mode: PermissionMode, revision: int) -> None:
    path = ctx.project_root.resolve() / "decision_log.json"
    if path.is_file():
        log = json.loads(path.read_text(encoding="utf-8"))
    else:
        log = {"version": "1.0", "project_id": ctx.project_id, "decisions": []}
    option_labels = {
        PermissionMode.AUTO: "Auto",
        PermissionMode.CONFIRM: "Confirm",
        PermissionMode.READ_ONLY: "Read only",
    }
    log["decisions"].append(
        {
            "decision_id": f"permission-{revision:04d}",
            "stage": "conversation",
            "category": "permission_policy",
            "subject": "Conversation permission mode",
            "options_considered": [
                {
                    "option_id": candidate.value,
                    "label": option_labels[candidate],
                    "score": 1.0 if candidate is mode else 0.5,
                    "reason": "User-selectable local operation boundary.",
                    **({} if candidate is mode else {"rejected_because": "Not selected for this revision."}),
                }
                for candidate in PermissionMode
            ],
            "selected": mode.value,
            "reason": f"Conversation permission mode changed to {option_labels[mode]}.",
            "user_visible": True,
            "user_approved": True,
            "confidence": 1.0,
        }
    )
    validate_artifact("decision_log", log)
    _atomic_json(path, log)


def set_permission_mode(ctx: PermissionContext, mode: PermissionMode) -> dict[str, Any]:
    path = _state_path(ctx)
    revision = 1
    if path.is_file():
        revision = int(json.loads(path.read_text(encoding="utf-8")).get("revision", 0)) + 1
    state = {
        "conversation_id": ctx.conversation_id,
        "project_id": ctx.project_id,
        "mode": mode.value,
        "revision": revision,
        "used_approval_nonces": [],
    }
    _atomic_json(path, state)
    _append_decision(ctx, mode, revision)
    return state


def _reject_unsafe_spelling(path: Path) -> None:
    raw = str(path)
    if raw.startswith(("\\\\", "//", "\\?\\", "\\.\\")):
        raise PermissionDenied(f"UNC and device paths are forbidden: {raw}")


def _resolve(path: Path) -> Path:
    _reject_unsafe_spelling(path)
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise PermissionDenied(f"Cannot safely resolve path: {path}") from exc


def _within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _resolved_targets(ctx: PermissionContext, targets: list[Path]) -> list[Path]:
    return [_resolve(Path(target)) for target in targets]


def _operation_hash(operation: OperationKind, targets: list[Path], command: str | None) -> str:
    canonical = json.dumps(
        {"operation": operation.value, "targets": sorted(str(path) for path in targets), "command": command},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _secret(ctx: PermissionContext) -> bytes:
    path = ctx.runtime_state_root.resolve() / ".permission-key"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(32))
    return path.read_bytes()


def mint_approval_token(
    ctx: PermissionContext,
    operation: OperationKind,
    targets: list[Path],
    *,
    ttl_seconds: int = 300,
    command: str | None = None,
) -> str:
    state = _load_state(ctx)
    resolved = _resolved_targets(ctx, targets)
    payload = {
        "conversation_id": ctx.conversation_id,
        "revision": state["revision"],
        "operation_hash": _operation_hash(operation, resolved, command),
        "expires_at": int(time.time()) + ttl_seconds,
        "nonce": secrets.token_hex(16),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(_secret(ctx), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def _decode_token(ctx: PermissionContext, token: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        raw = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        expected = hmac.new(_secret(ctx), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise PermissionDenied("Malformed or invalid approval token") from exc
    return payload


def _consume_approval(
    ctx: PermissionContext,
    state: dict[str, Any],
    token: str | None,
    operation: OperationKind,
    targets: list[Path],
    command: str | None,
) -> None:
    if not token:
        raise PermissionDenied("This operation requires explicit approval")
    payload = _decode_token(ctx, token)
    if payload.get("conversation_id") != ctx.conversation_id:
        raise PermissionDenied("Approval belongs to another conversation")
    if payload.get("revision") != state["revision"]:
        raise PermissionDenied("Approval token is stale after a mode revision")
    if int(payload.get("expires_at", 0)) < int(time.time()):
        raise PermissionDenied("Approval token has expired")
    expected_hash = _operation_hash(operation, targets, command)
    if payload.get("operation_hash") != expected_hash:
        raise PermissionDenied("Approval does not match this operation")
    nonce = payload.get("nonce")
    if nonce in state.get("used_approval_nonces", []):
        raise PermissionDenied("Approval token has already been used")
    state.setdefault("used_approval_nonces", []).append(nonce)
    _atomic_json(_state_path(ctx), state)


def authorize(
    ctx: PermissionContext,
    mode: PermissionMode,
    operation: OperationKind,
    targets: list[Path],
    approval_token: str | None = None,
    *,
    command: str | None = None,
) -> None:
    state = _load_state(ctx)
    if state["mode"] != mode.value:
        raise PermissionDenied("Requested permission mode is stale")
    if operation is OperationKind.COMMAND and command and _DANGEROUS_COMMANDS.search(command):
        raise PermissionDenied("dangerous command pattern is forbidden")

    resolved = _resolved_targets(ctx, targets)
    project = _resolve(ctx.project_root)
    runtime = _resolve(ctx.runtime_state_root)
    inputs = tuple(_resolve(path) for path in ctx.declared_inputs)
    for target in resolved:
        if operation is not OperationKind.READ and any(_within(target, source) for source in inputs):
            raise PermissionDenied(f"Cannot modify a source original: {target}")
        if operation is OperationKind.READ:
            if not (_within(target, project) or _within(target, runtime) or any(_within(target, source) for source in inputs)):
                raise PermissionDenied(f"Read target is outside declared boundaries: {target}")
        elif not (_within(target, project) or _within(target, runtime)):
            raise PermissionDenied(f"Mutation target is outside project/runtime boundaries: {target}")

    if operation is OperationKind.READ:
        return
    if mode is PermissionMode.READ_ONLY:
        raise PermissionDenied("read-only mode rejects mutating operations")
    if mode is PermissionMode.CONFIRM or operation is OperationKind.DELETE:
        _consume_approval(ctx, state, approval_token, operation, resolved, command)
