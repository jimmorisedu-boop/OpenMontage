# Modern Studio UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic desktop HTML shell with a polished component-based creative workspace while preserving every existing OpenMontage bridge contract.

**Architecture:** React owns presentation and local interaction state; the Python `DesktopApi` remains authoritative for projects and production state. Vite compiles the source tree to one self-contained HTML file consumed by pywebview and FastAPI tests.

**Tech Stack:** React, TypeScript, Vite, Radix UI, Lucide React, Motion, react-resizable-panels, Vitest, pytest.

## Global Constraints

- Runtime is portable and self-contained; no CDN or network access after build.
- No model, provider, or agent selection.
- Preserve `DesktopApi` method names and payload identities.
- Do not modify `remotion-composer/package-lock.json`.

---

### Task 1: Build system and typed bridge

**Files:** Create `scripts/openmontage_chat/ui/`; modify shell contract tests.

- [x] Add failing tests for component source, self-contained output, and forbidden selectors.
- [x] Configure TypeScript/Vite single-file production output.
- [x] Define project payload and pywebview bridge types.
- [x] Build and verify the generated shell is self-contained.

### Task 2: Workspace and design system

**Files:** Create `ui/src/styles.css`, `ui/src/components/Workspace.tsx`, `ProjectRail.tsx`, `Stage.tsx`, `Inspector.tsx`.

- [x] Add failing contracts for semantic regions, typography tokens, constrained layout, and collapse actions.
- [x] Implement the graphite design system and resizable/collapsible workspace.
- [x] Verify desktop and minimum-width behaviors.

### Task 3: Complete product workflows

**Files:** Create conversation, files, result, timeline, operation, and project-menu components.

- [x] Add failing contracts for every existing bridge action and durable card identity.
- [x] Implement questions, enhancements, plans, operations, results, files, versions, rename, and recoverable delete.
- [x] Verify keyboard navigation, live regions, and inline error recovery.

### Task 4: Delivery

- [x] Run frontend build and component tests.
- [x] Run focused Python suites and the full available repository regression (1,111 passed, 12 skipped; the separate MCP server suite requires the test-only `mcp` package in the system Python).
- [x] Run portable preflight.
- [x] Restart only the OpenMontage window and verify it responds.
- [x] Commit and push scoped files.
