# Usable Project Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ephemeral chat with durable project conversations, concise clarification and improvement cards, live local-tool planning, approval-gated execution, and verified results.

**Architecture:** `ProjectStore` owns atomic project state under `projects/`. `LocalOrchestrator` supplies the fixed model with project context and a policy-filtered live tool envelope, validates its structured decisions, and executes approved plans through `ToolAdapter`. The native bridge exposes product actions to a rebuilt WebView shell; model prose never directly changes execution state.

**Tech Stack:** Python 3.12, Ollama HTTP API, existing OpenMontage registry/pipelines/tools, pywebview/WebView2, vanilla HTML/CSS/JavaScript, pytest.

## Global Constraints

- Remote tools are hidden in `url-import-only`; only explicit user URL import may use external network.
- At most three concise questions and three optional enhancements are shown per turn.
- A project becomes ready only after backend artifact verification.
- Every mutation and output remains inside the active project except declared read-only source inputs.
- No raw chain-of-thought, invented media observations, or invented file paths.
- Preserve `remotion-composer/package-lock.json` unchanged.

---

### Task 1: Durable project store

**Files:**
- Create: `scripts/openmontage_chat/project_store.py`
- Test: `tests/scripts/test_openmontage_project_store.py`

**Interfaces:**
- Produces: `ProjectStore.create`, `list`, `load`, `append_entry`, `update_brief`, `save_plan`, `set_status`, and `verify_artifact`.

- [ ] Write failing tests for canonical layout, atomic persistence, restoration, versioning, and rejection of outside/missing artifacts.
- [ ] Run the focused test and verify RED.
- [ ] Implement the minimal store using `init_project`, JSON temp-file replacement, safe IDs, and FFprobe-backed media verification.
- [ ] Run the focused test and verify GREEN.

### Task 2: Structured local orchestrator

**Files:**
- Create: `scripts/openmontage_chat/orchestrator.py`
- Modify: `scripts/openmontage_chat/app.py`
- Test: `tests/scripts/test_openmontage_orchestrator.py`

**Interfaces:**
- Produces: policy-filtered capability envelope, `submit`, `approve_plan`, bounded decision parser, and project-state responses.

- [ ] Write failing tests for question/enhancement limits, forbidden-tool omission, plan validation, approval gating, tool execution, and verified completion.
- [ ] Run focused tests and verify RED.
- [ ] Implement the model instruction contract, one repair attempt, live registry envelope, plan validation, and sequential `ToolAdapter` execution.
- [ ] Run focused tests and verify GREEN.

### Task 3: Native project bridge

**Files:**
- Modify: `scripts/openmontage_chat/desktop.py`
- Modify: `scripts/openmontage_chat/app.py`
- Test: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Produces: `bootstrap`, `create_project`, `open_project`, `rename_project`, project-aware material registration, `submit`, `answer_questions`, `set_enhancements`, `approve_plan`, `open_project_folder`, `open_artifact`, and `create_version`.

- [ ] Add failing bridge contract tests.
- [ ] Verify RED.
- [ ] Wire `ProjectStore` and `LocalOrchestrator`; convert exceptions to actionable product responses.
- [ ] Verify GREEN.

### Task 4: Usable desktop shell

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Test: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Consumes: project-state bridge payloads.
- Produces: saved-project sidebar, exact folder header, question/enhancement/plan/result cards, and native actions.

- [ ] Add failing UI contract tests for all card types, saved projects, folder visibility, approval, safe text rendering, and absence of model/agent selectors.
- [ ] Verify RED.
- [ ] Implement a restrained accessible shell using DOM construction and replace-in-place progress.
- [ ] Verify GREEN.

### Task 5: Verification and handoff

**Files:**
- Verify all files above and launcher/preflight contracts.

- [ ] Run focused project/orchestrator/chat/launcher suites.
- [ ] Run full `pytest -q --import-mode=importlib`.
- [ ] Run portable preflight.
- [ ] Execute an end-to-end fixture plan and verify restoration.
- [ ] Restart only the owned OpenMontage process and leave the responding updated window open.
- [ ] Commit scoped changes and push `fork/codex/portable-jan-shell`.
