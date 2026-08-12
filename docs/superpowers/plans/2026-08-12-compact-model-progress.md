# Compact Model Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show restrained replace-in-place progress and an optional collapsed approach summary without exposing model chain-of-thought.

**Architecture:** Extend the Python chat bridge with a bounded response parser that accepts a final answer plus two to four short summary items, while preserving plain-text fallback. Extend the existing owned HTML shell with one timer-driven status element and a safely constructed collapsed `details` element inside assistant responses.

**Tech Stack:** Python 3.12, FastAPI compatibility layer, pywebview/WebView2, vanilla HTML/CSS/JavaScript, pytest.

## Global Constraints

- Never display raw chain-of-thought, hidden prompts, tokens, provider details, stack traces, or model logs.
- Render model content through DOM text nodes, never generated `innerHTML`.
- Keep one fixed model and no model, provider, or agent selector.
- Replace progress text in place; do not append progress messages or invent percentages.
- Preserve plain-text model-response compatibility.

---

### Task 1: Bounded response contract

**Files:**
- Modify: `scripts/openmontage_chat/app.py`
- Test: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Consumes: Ollama response `{"message": {"content": str}}`.
- Produces: `parse_model_response(content: str) -> dict[str, object]` with `answer: str` and `summary: list[str]`.

- [ ] **Step 1: Write failing parser and bridge tests**

Add tests asserting that a fenced or unfenced JSON object with `answer` and `summary` is parsed, summaries are stripped and capped at four, and unstructured text becomes the answer with an empty summary.

- [ ] **Step 2: Verify RED**

Run `python -m pytest -q --import-mode=importlib tests/scripts/test_openmontage_chat_app.py` and confirm failure because structured parsing is absent.

- [ ] **Step 3: Implement the bounded parser and prompt contract**

Add a private extraction helper using `json.loads`, fall back to the entire content, and return the parsed result from both `DesktopApi.chat` and `/api/chat`. Tell the model to return only a JSON object containing a final answer and two to four short approach conclusions, explicitly excluding hidden reasoning.

- [ ] **Step 4: Verify GREEN**

Run the focused test file and confirm all tests pass.

### Task 2: Compact shell presentation

**Files:**
- Modify: `scripts/openmontage_chat/index.html`
- Test: `tests/scripts/test_openmontage_chat_app.py`

**Interfaces:**
- Consumes: bridge result `{answer: string, summary: string[]}`.
- Produces: one replace-in-place progress line and optional collapsed `details.approach` element.

- [ ] **Step 1: Write failing shell-contract tests**

Assert the HTML contains fixed progress labels, a `details`/`summary` control labelled `Как я подошёл к задаче`, safe `textContent` rendering, and no `fetch`, raw reasoning label, or progress-message append.

- [ ] **Step 2: Verify RED**

Run the focused test and confirm it fails because progress cycling and approach summary are absent.

- [ ] **Step 3: Implement the minimal shell behavior**

Add `startProgress`, `stopProgress`, and `addAssistant` helpers. Cycle three labels every few seconds in the existing status element, clear the timer in `finally`, and construct collapsed summary items with `createElement` plus `textContent`.

- [ ] **Step 4: Verify GREEN**

Run focused tests and confirm all pass.

### Task 3: Product verification and live launch

**Files:**
- Verify: `scripts/openmontage_chat/app.py`
- Verify: `scripts/openmontage_chat/index.html`
- Verify: `START_OPENMONTAGE.bat`

**Interfaces:**
- Consumes: installed portable Python, WebView2 shell, Ollama models.
- Produces: a responding `OpenMontage` native window.

- [ ] **Step 1: Run focused chat and launcher tests**

Run the chat, launcher, portable launcher, and preflight test modules.

- [ ] **Step 2: Run the full repository suite**

Run `python -m pytest -q --import-mode=importlib` and require zero failures.

- [ ] **Step 3: Run portable preflight**

Run `runtime/python/python.exe -m scripts.openmontage_preflight --root F:\Exp\OpenMontage` and require `PASSED`.

- [ ] **Step 4: Restart the owned window and inspect it**

Close only the currently owned OpenMontage desktop process, relaunch `START_OPENMONTAGE.bat`, and verify a responding process whose main window title is `OpenMontage`.

- [ ] **Step 5: Commit and push scoped changes**

Stage only the app, shell, tests, spec, and plan; preserve unrelated user changes such as `remotion-composer/package-lock.json`; commit and push to `fork/codex/portable-jan-shell`.
