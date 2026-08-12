# Director Studio Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved C2/P2/T3 OpenMontage director studio in the existing native WebView shell.

**Architecture:** A single dependency-free shell derives a presentation model from the authoritative project payload. The director canvas owns preview and timeline; the right rail owns assistant/files tabs and the composer. Existing Python bridge contracts remain authoritative and only gain narrowly required read-only media support if browser playback requires it.

**Tech Stack:** pywebview/WebView2, vanilla HTML/CSS/JavaScript, existing Python `DesktopApi`, pytest.

## Global Constraints

- Preserve all existing project, question, plan, operation, artifact, and permission contracts.
- Do not expose model, agent, or provider selection.
- Do not add network dependencies or package installs.
- Keep `remotion-composer/package-lock.json` untouched.
- Keep `.superpowers/` mockups out of commits.

---

### Task 1: Studio structure and visual system

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Modify: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Consumes: existing project payload.
- Produces: project rail, director canvas, context rail, adaptive T3 theme.

- [ ] Write failing contract tests for semantic regions, Assistant/Files tabs, dark canvas, responsive layout, and forbidden selectors.
- [ ] Run focused tests and verify RED.
- [ ] Implement semantic HTML/CSS and shell state with safe DOM construction.
- [ ] Run focused tests and verify GREEN.

### Task 2: Preview and timeline

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Modify: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Produces: latest playable verified preview, intentional empty state, plan/source timeline, audio lane, and playhead.

- [ ] Write failing behavioral contract tests for preview selection, timeline derivation, media events, and empty state.
- [ ] Verify RED.
- [ ] Implement read-only preview and edit overview using current project data.
- [ ] Verify GREEN.

### Task 3: Assistant and Files workflows

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Modify: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Produces: compact durable conversation, active action cards, operation card, pinned composer, grouped files, outputs, and versions.

- [ ] Write failing tests for tabs, actions, grouped materials, versions, output controls, and inline errors.
- [ ] Verify RED.
- [ ] Implement the workflows without changing backend authority.
- [ ] Verify GREEN.

### Task 4: Verification and delivery

**Files:**
- Verify all scoped files and launcher contracts.

- [ ] Run focused chat/orchestrator/project suites.
- [ ] Run full `pytest -q --import-mode=importlib`.
- [ ] Run portable preflight.
- [ ] Restart only the OpenMontage WebView process and confirm it responds.
- [ ] Commit and push the scoped design changes.
