# OpenMontage Orchestrator Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current chat shell into a safe, resumable pipeline product whose UI reflects authoritative backend state and whose outputs are completely verified.

**Architecture:** `ProjectStore` persists immutable IDs, lifecycle events, versions, expected artifacts, and operation records. `LocalOrchestrator` performs compact two-stage capability routing, validates a selected pipeline against its manifest, and delegates execution to a resumable stage runner that uses canonical checkpoints. The native API returns quickly for long work, while the WebView polls operation state and renders only active cards.

**Tech Stack:** Python 3.12, existing pipeline/checkpoint/tool registry, Ollama loopback API, pywebview/WebView2, vanilla HTML/CSS/JavaScript, pytest.

## Global Constraints

- Keep all project mutations under `projects/<project-id>/` and preserve explicit read-only source inputs.
- `read_only` is enforced by Python, never inferred from UI state.
- Plans, question sets, operations, artifacts, and versions have stable IDs; stale actions fail closed.
- Pipeline manifest order, stage tools, director-skill references, canonical artifacts, and human gates are authoritative.
- Long work returns an operation ID immediately and is cancellable/resumable.
- A project is ready only when every declared required artifact verifies.
- Never expose chain-of-thought; show only short progress and approach summaries.
- Do not modify `remotion-composer/package-lock.json`.

---

### Task 1: Authoritative project state

**Files:**
- Modify: `scripts/openmontage_chat/project_store.py`
- Modify: `tests/scripts/test_openmontage_project_store.py`

**Interfaces:**
- Produces: active question sets, ID-addressed plans/artifacts, operation/event records, expected-artifact verification, and structured versions.

- [ ] Add failing tests for stale question/plan rejection, complete artifact sets, read-only artifact lookup, and version snapshots.
- [ ] Run focused tests and confirm the expected failures.
- [ ] Implement minimal persistence APIs and migrations for existing projects.
- [ ] Run focused tests and keep them green.

### Task 2: Manifest-bound planning and stages

**Files:**
- Modify: `scripts/openmontage_chat/orchestrator.py`
- Modify: `tests/scripts/test_openmontage_orchestrator.py`

**Interfaces:**
- Consumes: pipeline manifests through `lib.pipeline_loader`.
- Produces: stage-scoped executable plans with `plan_id`, expected artifacts, director contract, and manifest gates.

- [ ] Add failing tests for pipeline order, stage tool restrictions, next-stage selection, gate enforcement, and full artifact verification.
- [ ] Confirm RED.
- [ ] Implement compact routing plus manifest/stage validation and checkpoint transitions.
- [ ] Confirm GREEN.

### Task 3: Background operations and authoritative permissions

**Files:**
- Create: `scripts/openmontage_chat/operation_manager.py`
- Modify: `scripts/openmontage_chat/app.py`
- Modify: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Produces: `approve_plan(project_id, plan_id, mode) -> operation`, `operation_status`, `cancel_operation`, and `resume_operation`.

- [ ] Add failing API tests proving immediate return, backend read-only rejection, cancellation, and restart recovery.
- [ ] Confirm RED.
- [ ] Implement persisted worker lifecycle and idempotent APIs.
- [ ] Confirm GREEN.

### Task 4: Honest and accessible project UI

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Modify: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Consumes: active lifecycle objects and operation status payloads.
- Produces: inactive historical cards, per-question custom answers, truthful operation states, inline errors, accessible labels/status announcements, version history, and output controls.

- [ ] Add failing executable UI contract tests for each behavior.
- [ ] Confirm RED.
- [ ] Implement the minimal DOM/state changes without model or agent selectors.
- [ ] Confirm GREEN.

### Task 5: Verification and delivery

**Files:**
- Modify documentation only where launcher or recovery behavior changed.

- [ ] Run focused project/orchestrator/chat suites.
- [ ] Run full `pytest -q --import-mode=importlib`.
- [ ] Run offline portable preflight.
- [ ] Run a real resumable fixture operation and verify its complete output set.
- [ ] Restart only the owned OpenMontage process and verify the updated window responds.
- [ ] Commit only scoped changes and push `codex/orchestrator-remediation`.
