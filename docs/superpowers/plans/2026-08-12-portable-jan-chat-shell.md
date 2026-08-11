# Portable Jan Chat Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Codex Desktop with a movable, repository-local Jan chat window that exposes one OpenMontage agent, accepts mixed production inputs and explicit public URLs, and enforces `Auto`, `Confirm`, and `Read only` modes at the MCP boundary.

**Architecture:** A pinned Jan 0.8.0 Tauri build is patched and packaged into `runtime/jan/`; a repository-local launcher owns Jan, Ollama, and a Python STDIO MCP adapter. Existing OpenMontage tools, skills, pipelines, checkpoints, and artifacts remain authoritative. A centralized policy layer constrains paths and mutations, while a short-lived URL import gateway is the only outbound-capable production process.

**Tech Stack:** Windows PowerShell, batch, Jan 0.8.0 (React/TypeScript/Tauri), Python 3.11+, MCP Python SDK, Pydantic 2, FastAPI test client, Ollama, yt-dlp, FFmpeg/ffprobe, pytest, Vitest.

## Global Constraints

- Target Windows 10/11, NVIDIA GPU with 16 GB VRAM and 64 GB system RAM.
- Pin Jan source to tag `v0.8.0`; do not depend on a mutable `latest` artifact.
- Jan 0.8.0 is Tauri, not Electron. Route Tauri/WebView data, cache, logs, crash dumps, and temp paths under `runtime/`; bundle a fixed WebView2 runtime if the OS runtime cannot satisfy the black-box portability test.
- Keep one user-visible model: `openmontage-gpt-oss:20b-32k`. Keep `qwen3.5:9b` hidden and callable only through visual-review tooling.
- Set `OLLAMA_MAX_LOADED_MODELS=1`; unload the orchestration model before vision work and reload it afterward.
- Do not add a Python creative orchestrator. Python exposes bounded tools, persistence, policy, and transport only.
- Keep existing pipeline manifests, stage skills, checkpoint gates, reviewer rules, and editorial guidance authoritative.
- Local inputs are read-only references. Never overwrite, move, or delete source originals.
- In normal mode, outbound access is limited to a short-lived downloader for the exact user-submitted public URL. Strict air-gapped mode rejects URLs.
- No cloud inference, web search, browser cookies, authenticated/private-source import, DRM bypass, telemetry, automatic update, model hub, or remote MCP server.
- All OpenMontage-owned persistent state and bundled dependencies must live beneath the repository. Windows-created ephemeral OS files are allowed only when they are not application state.
- Preserve the user's unrelated `remotion-composer/package-lock.json` modification and never stage it with these tasks.

## File Map

- `config/runtime/artifacts.json` — pinned runtime artifact/source versions, URLs, hashes, and licenses.
- `integrations/jan/` — upstream attribution, reproducible Jan patch, profile template, and build notes.
- `scripts/build_jan_portable.ps1` — creates the patched Jan artifact beneath `runtime/build/`.
- `scripts/portable_runtime_layout.py` — single source of truth for all repository-local runtime paths.
- `lib/network_policy.py` — strict-offline and URL-import-only authorization.
- `lib/agent_permissions.py` — per-conversation permission and path enforcement.
- `lib/input_manifest.py` and `schemas/artifacts/input_manifest.schema.json` — mixed-input inventory and provenance.
- `tools/analysis/url_import_gateway.py` — explicit public-URL import boundary.
- `tools/publishers/project_collector.py` — self-contained used-material export.
- `scripts/openmontage_mcp/` — STDIO MCP adapter, permission context, progress, and tool mapping.
- `integrations/jan/patches/0001-openmontage-shell.patch` — mode selector, fixed assistant/model view, MCP context injection, and cloud-feature removal.
- `scripts/seed_jan_profile.py` — deterministic repository-local Jan profile.
- `scripts/start_openmontage.ps1`, `START_OPENMONTAGE.bat` — owned-process launcher and user entry point.
- `scripts/setup_portable_runtime.ps1`, `SETUP_PORTABLE_RUNTIME.bat` — one-time pinned downloads/build with checksums.
- `tests/` — unit, contract, integration, and opt-in Windows acceptance tests.

---

### Task 1: Pin and Prove a Portable Jan Artifact

**Files:**
- Create: `config/runtime/artifacts.json`
- Create: `integrations/jan/README.md`
- Create: `integrations/jan/LICENSE.upstream`
- Create: `integrations/jan/patches/0001-openmontage-shell.patch`
- Create: `scripts/build_jan_portable.ps1`
- Create: `tests/contracts/test_jan_artifact_contract.py`

**Interfaces:**
- Pin Jan source tag, commit, source archive SHA-256, setup/build-tool artifacts, and license.
- Produce `runtime/jan/Jan.exe` without installing Jan globally.
- Fail before later integration work if the artifact writes persistent application state outside the repository.

- [ ] **Step 1: Write the artifact contract test**

```python
# tests/contracts/test_jan_artifact_contract.py
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_jan_artifact_manifest_is_pinned_and_complete():
    data = json.loads((ROOT / "config/runtime/artifacts.json").read_text("utf-8"))
    jan = data["jan"]
    assert jan["tag"] == "v0.8.0"
    assert len(jan["commit"]) == 40
    assert len(jan["source_sha256"]) == 64
    assert jan["source_url"].endswith("/archive/refs/tags/v0.8.0.zip")
    assert data["runtime_policy"] == "checksummed-only"

def test_jan_integration_has_license_patch_and_build_recipe():
    for path in [
        "integrations/jan/LICENSE.upstream",
        "integrations/jan/patches/0001-openmontage-shell.patch",
        "scripts/build_jan_portable.ps1",
    ]:
        assert (ROOT / path).is_file(), path
```

- [ ] **Step 2: Run the test and observe missing files**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_jan_artifact_contract.py -v
```

Expected: failure because the manifest and integration files do not exist.

- [ ] **Step 3: Add the pinned artifact manifest**

Use a JSON shape with no mutable URLs:

```json
{
  "runtime_policy": "checksummed-only",
  "jan": {
    "tag": "v0.8.0",
    "commit": "042bf6dc0c9a0a93baf66c8fe5bc2654f095258e",
    "source_url": "https://github.com/janhq/jan/archive/refs/tags/v0.8.0.zip",
    "source_sha256": "d74fff3a692dc1f7cd38b03f9ecd277ac1119b37d02539e317df3d8cb626fd57",
    "output": "runtime/jan/Jan.exe"
  }
}
```

The values above are pinned to the official `v0.8.0` tag and its downloaded source archive. The contract must reject brackets, `latest`, blank hashes, and non-HTTPS URLs.

- [ ] **Step 4: Add the reproducible build script**

`scripts/build_jan_portable.ps1` must:

1. resolve the repository from `$PSScriptRoot`;
2. read `config/runtime/artifacts.json`;
3. download only missing pinned artifacts into `runtime/downloads/`;
4. verify SHA-256 before extraction;
5. place Node/Yarn/Rust build tools under `runtime/build-tools/`;
6. apply `integrations/jan/patches/0001-openmontage-shell.patch` with `git apply --check` then `git apply`;
7. build the Tauri Windows executable with repository-local caches and `TEMP`/`TMP`;
8. copy executable, fixed WebView2 runtime if required, license, and build manifest to `runtime/jan/`;
9. never invoke an installer, registry mutation, shortcut creation, or user-profile package cache.

- [ ] **Step 5: Add a portable-boundary probe**

Add `-ProbePortableBoundary` to the script. It snapshots Jan-related paths under `%APPDATA%`, `%LOCALAPPDATA%`, `%USERPROFILE%`, launches the built shell with a disposable local data directory, closes it, and fails on new persistent Jan-owned files. Keep this opt-in because it starts a real window.

- [ ] **Step 6: Run the contract and build probe**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_jan_artifact_contract.py -v
.\scripts\build_jan_portable.ps1
.\scripts\build_jan_portable.ps1 -ProbePortableBoundary
```

Expected: `runtime/jan/Jan.exe` exists; the boundary probe reports no external persistent state. If this gate fails, stop implementation and report the exact external paths before proceeding.

- [ ] **Step 7: Commit Task 1**

```powershell
git add config/runtime/artifacts.json integrations/jan scripts/build_jan_portable.ps1 tests/contracts/test_jan_artifact_contract.py
git commit -m "build: pin portable Jan shell"
```

---

### Task 2: Replace the Boolean Offline Flag with an Explicit Network Policy

**Files:**
- Create: `lib/network_policy.py`
- Modify: `lib/offline_guard.py`
- Modify: `tools/base_tool.py`
- Modify: `tools/tool_registry.py`
- Create: `tests/lib/test_network_policy.py`
- Modify: `tests/lib/test_offline_guard.py`

**Interfaces:**

```python
class NetworkMode(str, Enum):
    STRICT_OFFLINE = "strict-offline"
    URL_IMPORT_ONLY = "url-import-only"

@dataclass(frozen=True)
class NetworkRequest:
    component: str
    submitted_url: str | None = None

def authorize_network(request: NetworkRequest, mode: NetworkMode | None = None) -> None: ...
```

- [ ] **Step 1: Write failing policy tests**

Test that loopback always works, strict mode rejects all remote URLs, URL-import-only permits only `component="url_import_gateway"` with the explicit submitted HTTP(S) URL, and every other tool remains rejected. Also test that `file:`, UNC, credentials-in-URL, localhost, private IPs, and non-HTTP schemes are rejected by the import gateway.

- [ ] **Step 2: Run the tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_network_policy.py tests/lib/test_offline_guard.py -v
```

Expected: import failure for `lib.network_policy`.

- [ ] **Step 3: Implement the policy and compatibility bridge**

Read `OPENMONTAGE_NETWORK_MODE`; map legacy `OPENMONTAGE_OFFLINE=1` to `strict-offline`. Keep `offline_guard.py` as a compatibility facade so existing tools retain fail-closed behavior. The registry must continue hiding API/HYBRID tools in both modes except the explicit URL gateway in `url-import-only`.

- [ ] **Step 4: Run policy and registry regressions**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_network_policy.py tests/lib/test_offline_guard.py tests/contracts/test_offline_mode_contract.py -v
```

- [ ] **Step 5: Commit Task 2**

```powershell
git add lib/network_policy.py lib/offline_guard.py tools/base_tool.py tools/tool_registry.py tests/lib/test_network_policy.py tests/lib/test_offline_guard.py
git commit -m "feat: add URL-import-only network policy"
```

---

### Task 3: Expand the Portable Runtime Layout and Preflight

**Files:**
- Modify: `scripts/portable_runtime_layout.py`
- Create: `scripts/openmontage_preflight.py`
- Modify: `tests/scripts/test_portable_runtime_layout.py`
- Create: `tests/scripts/test_openmontage_preflight.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class PortableLayout:
    root: Path
    jan_exe: Path
    jan_data: Path
    python_exe: Path
    ollama_exe: Path
    models_dir: Path
    ffmpeg_exe: Path
    ffprobe_exe: Path
    ytdlp_exe: Path
    state_dir: Path
    temp_dir: Path
    logs_dir: Path
```

- [ ] **Step 1: Change layout tests to remove `codex_integration` and require every new path**
- [ ] **Step 2: Add preflight tests with injected command/model/service probes**

Verify actionable errors for missing Jan, Python environment, MCP SDK, Ollama, FFmpeg, downloader, model tags, incorrect context profile, non-loopback Ollama, and an unwritable runtime directory.

- [ ] **Step 3: Implement layout and preflight JSON/human output**

The preflight result is:

```python
{"status": "passed|blocked", "checks": [{"id": str, "ok": bool, "message": str, "remedy": str}]}
```

Do not suggest installing Codex or choosing alternate models.

- [ ] **Step 4: Run focused tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/test_portable_runtime_layout.py tests/scripts/test_openmontage_preflight.py -v
git add scripts/portable_runtime_layout.py scripts/openmontage_preflight.py tests/scripts
git commit -m "feat: define portable Jan runtime preflight"
```

---

### Task 4: Add the Mixed-Input Manifest and Project Layout

**Files:**
- Create: `schemas/artifacts/input_manifest.schema.json`
- Modify: `schemas/artifacts/__init__.py`
- Create: `lib/input_manifest.py`
- Modify: `lib/checkpoint.py`
- Create: `tests/lib/test_input_manifest.py`
- Modify: `tests/lib/test_checkpoint.py`

**Interfaces:**

```python
class InputPriority(str, Enum):
    REQUIRED = "required"
    REFERENCE = "reference"
    OPTIONAL = "optional"

def register_inputs(project_id: str, paths: list[str], *, priority: InputPriority) -> dict: ...
def register_download(project_id: str, source_url: str, local_path: Path, metadata: dict) -> dict: ...
```

- [ ] **Step 1: Write failing tests for video, audio, image, PDF, DOCX, text, SRT/VTT, EDL/XML/CSV, mixed folders, and unknown formats**

Assert stable IDs, normalized absolute paths, inferred type/role, priority, technical metadata, relationships, checksum/provenance for downloads, and preservation of unsupported files with `interpretation_status="unsupported"`.

- [ ] **Step 2: Extend `init_project()`**

Create `inputs/downloads/`, `inputs/derivatives/`, and an empty schema-valid `artifacts/input_manifest.json` while preserving the existing project structure.

- [ ] **Step 3: Implement deterministic detection and atomic writes**

Use extension/MIME plus ffprobe for media. Never copy local source inputs. Write via a temporary sibling and `Path.replace()`.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_input_manifest.py tests/lib/test_checkpoint.py tests/contracts -q
git add schemas/artifacts lib/input_manifest.py lib/checkpoint.py tests/lib/test_input_manifest.py tests/lib/test_checkpoint.py
git commit -m "feat: register heterogeneous project inputs"
```

---

### Task 5: Enforce Conversation Permission Modes and Path Boundaries

**Files:**
- Create: `lib/agent_permissions.py`
- Create: `tests/lib/test_agent_permissions.py`

**Interfaces:**

```python
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

def authorize(ctx: PermissionContext, mode: PermissionMode, operation: OperationKind,
              targets: list[Path], approval_token: str | None = None) -> None: ...
```

- [ ] **Step 1: Write a complete decision-table test**

Cover all three modes, project writes, runtime-state writes, external-input reads, external writes, stale mode revisions, approval-token replay, deletion, source overwrite, path traversal, symlink/junction escape, device paths, UNC paths, and dangerous command patterns.

- [ ] **Step 2: Implement fail-closed authorization**

Persist mode records in `runtime/state/conversations/<id>.json` with monotonically increasing revision. Mint single-use HMAC approval tokens containing conversation, operation hash, mode revision, and expiry. Resolve every target before authorization; deny links that escape allowed roots.

- [ ] **Step 3: Append mode changes to `decision_log`**

Reuse a stable `(category, subject)` pair: `permission_policy` / `Conversation permission mode`. Do not mutate earlier entries.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/lib/test_agent_permissions.py -v
git add lib/agent_permissions.py tests/lib/test_agent_permissions.py
git commit -m "feat: enforce conversation permission modes"
```

---

### Task 6: Implement the URL Import Gateway

**Files:**
- Create: `tools/analysis/url_import_gateway.py`
- Modify: `tools/analysis/video_downloader.py`
- Create: `tests/tools/test_url_import_gateway.py`

**Interfaces:**

```python
class URLImportGateway(BaseTool):
    name = "url_import_gateway"
    network_required = True

# params
{"project_id": str, "url": str, "bulk_approved": bool, "expected_item_count": int | None}
```

- [ ] **Step 1: Write tests around an injected subprocess runner and a local HTTP fixture**

Verify exact-URL authorization, output under `inputs/downloads/`, `.partial` handling, provenance/checksum, playlist/profile/channel confirmation, item-count mismatch, timeout/cancel cleanup, redirect metadata, and rejection in strict-offline mode.

- [ ] **Step 2: Refactor the existing downloader into reusable argument/result parsing**

Invoke only the pinned `runtime/downloader/yt-dlp.exe`; never `pip install`, PATH yt-dlp, browser-cookie import, or shell interpolation. Pass explicit FFmpeg location and safe filename template.

- [ ] **Step 3: Implement short-lived process isolation**

Create a minimal environment, local temp directory, process-group ownership, bounded timeout, structured log, and atomic final rename. Register success through `register_download()`.

- [ ] **Step 4: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/tools/test_url_import_gateway.py tests/lib/test_network_policy.py -v
git add tools/analysis/url_import_gateway.py tools/analysis/video_downloader.py tests/tools/test_url_import_gateway.py
git commit -m "feat: add controlled public URL import"
```

---

### Task 7: Add the Project Collector

**Files:**
- Create: `tools/publishers/project_collector.py`
- Create: `tests/tools/test_project_collector.py`

**Interfaces:**

```python
# params
{"project_id": str, "destination": str, "include_conversation": bool = True}
# result
{"bundle_root": str, "copied_inputs": list[str], "manifest": str, "warnings": list[str]}
```

- [ ] **Step 1: Write tests for used-only input collection**

Include canonical artifacts, checkpoints/history, project settings, selected conversation export, deliverables, and only input IDs referenced from artifacts/decision logs. Verify checksums, collision-safe names, missing-source warnings, destination refusal inside source project, and no mutation of originals.

- [ ] **Step 2: Implement staging then atomic publish**

Copy into `<destination>.partial`, write `collection_manifest.json`, verify hashes, then rename. Reject existing non-empty destinations unless an explicit approved replacement operation is supplied.

- [ ] **Step 3: Run tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/tools/test_project_collector.py -v
git add tools/publishers/project_collector.py tests/tools/test_project_collector.py
git commit -m "feat: collect self-contained OpenMontage projects"
```

---

### Task 8: Build the OpenMontage STDIO MCP Adapter

**Files:**
- Modify: `requirements.txt`
- Create: `scripts/openmontage_mcp/__init__.py`
- Create: `scripts/openmontage_mcp/server.py`
- Create: `scripts/openmontage_mcp/context.py`
- Create: `scripts/openmontage_mcp/tool_adapter.py`
- Create: `scripts/openmontage_mcp/progress.py`
- Create: `tests/scripts/openmontage_mcp/test_server.py`
- Create: `tests/scripts/openmontage_mcp/test_tool_adapter.py`

**Interfaces:**

Expose bounded tools:

```text
bootstrap_conversation, set_permission_mode, register_inputs,
import_public_url, inspect_project, list_available_tools, run_openmontage_tool,
collect_project, get_operation_status, cancel_operation
```

Every mutating call receives hidden Jan-injected `_openmontage_context` containing `conversation_id`, `thread_revision`, and a nonce. The adapter looks up project/mode server-side; it never trusts a model-supplied path root or permission mode.

- [ ] **Step 1: Add `mcp>=1.12,<2` and write in-memory STDIO client tests**

Verify initialize/list/call, read-only tool-list filtering, confirm-mode approval responses, stale/malformed hidden context rejection, exception-to-structured-error mapping, cancellation, and no network listener.

- [ ] **Step 2: Implement thin adapters over existing registry/tool contracts**

`run_openmontage_tool` must discover through `ToolRegistry`, check policy, call `.execute(params)`, translate `ToolResult`, and stream structured progress. It must not select pipelines, make creative decisions, or bypass human checkpoints.

- [ ] **Step 3: Add structured result/error shapes**

```python
{"ok": False, "operation_id": str, "category": "approval_required|blocked|tool_error",
 "attempted": str, "retained_work": list[str], "next_actions": list[str],
 "recommended_action": str}
```

- [ ] **Step 4: Run MCP tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/openmontage_mcp -v
git add requirements.txt scripts/openmontage_mcp tests/scripts/openmontage_mcp
git commit -m "feat: expose bounded OpenMontage MCP tools"
```

---

### Task 9: Patch Jan for the OpenMontage Chat Experience

**Files:**
- Complete: `integrations/jan/patches/0001-openmontage-shell.patch`
- Create: `integrations/jan/profile/openmontage-assistant.json`
- Create: `integrations/jan/profile/mcp-server.json`
- Create: `integrations/jan/profile/provider.json`
- Create: `scripts/seed_jan_profile.py`
- Create: `tests/scripts/test_seed_jan_profile.py`
- Add upstream tests through patch: `web-app/src/containers/__tests__/OpenMontagePermissionSelector.test.tsx`

**Patch targets in Jan v0.8.0:**

- `web-app/src/containers/ChatInput.tsx` — render the selector beside the composer.
- `web-app/src/stores/openmontage-permission-store.ts` — per-thread mode/revision state.
- `web-app/src/services/mcp/*` — inject signed thread context into OpenMontage MCP calls.
- settings/provider/model UI — hide generic provider/model choice and cloud/MCP discovery in OpenMontage build.
- Tauri configuration/capabilities — repository-local paths, disabled updater/telemetry, no remote navigation.

- [ ] **Step 1: Write seed-profile tests**

Assert one Ollama-compatible provider at `http://127.0.0.1:11434/v1`, one visible model, one assistant, one local STDIO MCP command using `runtime/python/python.exe`, no remote providers/tools, no auto-update/telemetry, and idempotent relocation-safe output.

- [ ] **Step 2: Add Jan component/store tests in the patch**

Test labels `Auto`, `Confirm`, `Read only`; per-thread persistence; visible revision changes; bootstrap default `Confirm`; no selector state leakage between threads; hidden context injection on every OpenMontage MCP call; and omission of mutating tools in read-only mode.

- [ ] **Step 3: Implement the Jan patch**

Use Jan's existing `currentThreadId` from `ChatInput.tsx`. Store display state locally, but treat the MCP server response as authoritative. Mode changes call `set_permission_mode`; on failure revert the selector and show the structured error. Do not rely on prompt text for enforcement.

- [ ] **Step 4: Seed the repository-local profile**

Write only beneath `runtime/jan-data/`. The assistant bootstrap message must instruct the model to read `AGENT_GUIDE.md`, use pipeline/stage skills, retain gates, and route visual review through the hidden qwen tool.

- [ ] **Step 5: Run Python and Jan tests, rebuild, and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/test_seed_jan_profile.py -v
.\scripts\build_jan_portable.ps1 -RunTests
git add integrations/jan scripts/seed_jan_profile.py tests/scripts/test_seed_jan_profile.py
git commit -m "feat: tailor Jan as the OpenMontage chat shell"
```

---

### Task 10: Replace Setup and Startup with Owned Portable Processes

**Files:**
- Create: `scripts/start_openmontage.ps1`
- Create: `START_OPENMONTAGE.bat`
- Modify: `scripts/setup_portable_runtime.ps1`
- Modify: `SETUP_PORTABLE_RUNTIME.bat`
- Modify: `.gitignore`
- Create: `tests/scripts/test_start_openmontage.py`
- Create: `tests/contracts/test_portable_launcher_contract.py`

**Interfaces:**
- `START_OPENMONTAGE.bat` is the normal entry point.
- Launcher returns Jan's non-zero exit code, retains logs, and pauses with an actionable error.
- A process ledger in `runtime/state/processes/<launcher-id>.json` records PID, start time, executable path, and ownership.

- [ ] **Step 1: Write launcher contracts**

Assert no `codex` string or requirement, all resolved paths derive from the BAT/PowerShell location, loopback Ollama, local data/cache/temp/log environment, preflight before launch, MCP readiness, and finally-block cleanup of owned processes only.

- [ ] **Step 2: Implement setup**

Download only artifacts from `config/runtime/artifacts.json`, verify every hash, install the local Python environment, build/copy Jan, place Ollama/FFmpeg/yt-dlp/models under `runtime/`, create the 32K profile, and seed Jan. Never add PATH entries or write user-level config.

- [ ] **Step 3: Implement startup/shutdown**

Start Ollama only if no healthy approved loopback instance exists. Start MCP as Jan-configured STDIO or supervised child. Start Jan and wait. On exit, stop only processes whose PID, creation time, and executable path match the ledger.

- [ ] **Step 4: Run launcher tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/scripts/test_start_openmontage.py tests/contracts/test_portable_launcher_contract.py -v
git add scripts/start_openmontage.ps1 START_OPENMONTAGE.bat scripts/setup_portable_runtime.ps1 SETUP_PORTABLE_RUNTIME.bat .gitignore tests/scripts/test_start_openmontage.py tests/contracts/test_portable_launcher_contract.py
git commit -m "feat: launch portable OpenMontage chat"
```

---

### Task 11: Migrate Documentation and Remove Codex Requirements

**Files:**
- Modify: `README.md`
- Modify: `docs/LOCAL_TEXT_EDITING_GUIDE.md`
- Modify: `docs/PROVIDERS.md`
- Modify: `scripts/local_agent_preflight.py`
- Modify: `tests/contracts/test_offline_mode_contract.py`
- Create: `tests/contracts/test_jan_user_guidance.py`
- Supersede: `START_OFFLINE_EDITOR.bat`
- Supersede: `scripts/start_local_agent.ps1`

- [ ] **Step 1: Write documentation contracts**

Require setup/start instructions, one visible model, hidden vision model, three modes, mixed inputs, URL exception, strict-offline switch, public-source limitations, project collection, relocation, checkpoint recovery, and troubleshooting. Reject instructions requiring Codex, global installs, API keys, cloud tools, or model choice.

- [ ] **Step 2: Update the editing handbook**

Preserve the existing paraphrased editorial principles and book bibliography. Add examples for storyboard + script + footage, explanation notes, subtitle/edit-data input, a public URL, and `Collect project`. Explain each permission mode in operator language.

- [ ] **Step 3: Turn old launchers into migration shims**

They should print that they are superseded and delegate to `START_OPENMONTAGE.bat`; do not retain a Codex preflight path.

- [ ] **Step 4: Run documentation contracts and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_jan_user_guidance.py tests/contracts/test_offline_mode_contract.py tests/contracts/test_local_editing_guidance.py -v
git add README.md docs scripts/local_agent_preflight.py START_OFFLINE_EDITOR.bat scripts/start_local_agent.ps1 tests/contracts
git commit -m "docs: migrate local workflow from Codex to Jan"
```

---

### Task 12: End-to-End Portability and Montage Acceptance

**Files:**
- Create: `tests/integration/test_openmontage_mcp_smoke.py`
- Create: `tests/integration/test_url_import_smoke.py`
- Create: `tests/integration/test_portable_jan_windows.py`
- Create: `tests/integration/test_openmontage_montage_e2e.py`

- [ ] **Step 1: Add default-safe integration markers**

Real Jan/Ollama tests run only with `OPENMONTAGE_PORTABLE_SMOKE=1`; the local HTTP URL fixture requires no internet. Default CI verifies collection/skip behavior without opening windows or loading models.

- [ ] **Step 2: Test the MCP lifecycle**

Bootstrap a conversation/project; register mixed inputs; change all modes; verify confirm approval; reject a malicious stale call; reconstruct status from checkpoints after restart.

- [ ] **Step 3: Test the URL gateway**

Serve sample media from a local HTTP server, import it, terminate one transfer midway, resume safely, verify provenance/hash, then prove subsequent analysis opens only the local file and makes no network request.

- [ ] **Step 4: Test the real portable shell**

Copy the repository/runtime to a path containing spaces on a non-system drive, start Jan, confirm fixed model/assistant/MCP/selector, close, move again, reopen conversation, and compare external-state snapshots.

- [ ] **Step 5: Run a local montage smoke**

Use tiny generated fixtures plus script/storyboard notes; approve the edit plan; render through the existing FFmpeg pipeline; verify playable video with ffprobe, source hashes unchanged, qwen/orchestrator sequential residency, and successful collection.

- [ ] **Step 6: Run the full verification suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/contracts tests/lib tests/scripts tests/tools -q
.\.venv\Scripts\python.exe -m pytest tests/integration/test_openmontage_mcp_smoke.py tests/integration/test_url_import_smoke.py -v
$env:OPENMONTAGE_PORTABLE_SMOKE='1'
.\.venv\Scripts\python.exe -m pytest tests/integration/test_portable_jan_windows.py tests/integration/test_openmontage_montage_e2e.py -v -s
git diff --check
git status --short
```

- [ ] **Step 7: Confirm final acceptance manually**

Double-click `START_OPENMONTAGE.bat`; attach a mixed production package; submit a public URL; switch each mode; approve a plan; render; collect; close; move the folder; reopen; verify no Codex dependency and no Jan/OpenMontage persistent state outside the folder.

- [ ] **Step 8: Commit Task 12**

```powershell
git add tests/integration
git commit -m "test: verify portable Jan montage workflow"
```

---

## Final Review Checklist

- [ ] Compare the final implementation with every acceptance criterion in `docs/superpowers/specs/2026-08-12-jan-portable-chat-shell-design.md`.
- [ ] Confirm the implementation identifies Jan as Tauri and does not rely on Electron-only flags.
- [ ] Confirm only `openmontage-gpt-oss:20b-32k` is visible and `qwen3.5:9b` remains an internal visual tool.
- [ ] Confirm the MCP layer, not the prompt or UI alone, rejects unauthorized operations.
- [ ] Confirm strict-offline and URL-import-only modes both pass their respective contracts.
- [ ] Confirm sources remain unchanged and collected bundles contain only used inputs.
- [ ] Confirm all application state, logs, caches, models, dependencies, and temp paths are beneath the moved repository.
- [ ] Confirm `remotion-composer/package-lock.json` remains untouched and unstaged.
