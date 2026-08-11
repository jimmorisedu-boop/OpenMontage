# Portable Jan Chat Shell for OpenMontage

**Date:** 2026-08-12
**Status:** Approved design, awaiting written-spec review
**Target platform:** Windows 10/11, NVIDIA GPU with 16 GB VRAM and 64 GB system RAM

## Purpose

Replace the externally installed Codex Desktop application with a familiar,
standalone chat window that lives inside the OpenMontage folder. The finished
runtime must start from one BAT file, use the existing local Ollama models, run
OpenMontage tools autonomously under a user-selected permission policy, and
retain projects, conversations, settings, logs, and dependencies inside the
repository tree.

The selected shell is the Windows portable build of Jan. OpenMontage will use
Jan's existing chat, project, attachment, local-provider, and MCP features. We
will add only the integration needed to enforce OpenMontage's fixed models,
portable storage, network boundary, project lifecycle, and three permission
modes.

## Goals

- Launch a normal desktop chat window without installing Codex Desktop.
- Keep Jan, Ollama, model weights, FFmpeg, the URL downloader, Python runtime,
  MCP integration, settings, conversations, caches, and logs under the
  OpenMontage folder.
- Present one OpenMontage agent instead of a general model/provider selector.
- Use `openmontage-gpt-oss:20b-32k` for orchestration and `qwen3.5:9b` only for
  visual review.
- Accept heterogeneous local production materials, not only video.
- Allow an explicit public URL as input, download it locally, and return to
  local-only processing afterward.
- Provide per-conversation `Auto`, `Confirm`, and `Read only` permission modes.
- Preserve the repository's instruction-driven pipeline, checkpoint, review,
  and human creative-approval contracts.

## Non-goals

- Cloud inference, cloud storage, web search, browsing, publishing, or API-key
  setup.
- Automatic login to social networks or importing browser cookies in the first
  release.
- Circumventing DRM, paywalls, access controls, or platform restrictions.
- Guaranteeing that every social platform will remain downloadable after site
  changes. The downloader is replaceable and versioned for this reason.
- Building a video-editor timeline inside the chat application.
- Replacing the existing OpenMontage pipeline and tool implementations.

## User Experience

`START_OPENMONTAGE.bat` opens a standalone Jan window. The left rail contains
conversation history, the center contains the chat, and the composer accepts
text, local files, folders, and public URLs. A visible selector above the
composer shows the current permission mode.

A new production conversation creates an OpenMontage project under
`projects/<project-id>/`. The user can provide source footage, audio, images,
storyboards, scripts, notes, subtitles, edit data, reference documents, or a
mixed folder. The agent identifies each item's likely role and asks only when
an ambiguity materially changes the result.

The agent first analyzes the available material and proposes a comprehensible
editing plan. Major creative choices remain human approval gates in every
permission mode. During execution, the conversation displays the current
stage, active operation, progress, and recoverable errors. Transcripts,
storyboards, plans, previews, and final renders appear as local attachments in
the conversation.

Source media remains at its original location during normal work. A separate
`Collect project` action copies every material asset actually used, plus the
project state, conversation, settings, and deliverables, into a self-contained
export folder.

## Architecture

The runtime has five cooperating parts:

1. **Portable launcher** resolves paths relative to itself, applies the network
   and storage policy, starts repository-local services, runs preflight, and
   opens Jan.
2. **Jan portable shell** provides the familiar desktop chat interface. A
   minimal maintained integration patch adds the three-state permission selector
   and routes all Electron storage locations into `runtime/jan-data/`.
3. **Portable Ollama** serves only on `127.0.0.1:11434`, with cloud features
   disabled and one loaded model at a time.
4. **OpenMontage MCP server** exposes bounded project, analysis, pipeline,
   rendering, and packaging operations. It is the policy enforcement boundary;
   the model cannot bypass a selected permission mode by changing its prompt.
5. **URL import gateway** is the only component allowed outbound network access.
   It accepts only an explicit user-supplied public URL, writes the downloaded
   asset into the active project, records provenance, and exits.

Python remains responsible for tools, schemas, and persistence. Creative and
orchestration intelligence stays in the model and repository instructions. The
MCP server adapts existing OpenMontage tools; it does not implement a second
creative orchestrator.

## Portable Layout

```text
OpenMontage/
|-- START_OPENMONTAGE.bat
|-- SETUP_PORTABLE_RUNTIME.bat
|-- runtime/
|   |-- jan/
|   |   `-- Jan.exe
|   |-- jan-data/
|   |   |-- conversations/
|   |   |-- settings/
|   |   |-- cache/
|   |   |-- logs/
|   |   `-- crash-dumps/
|   |-- ollama/
|   |-- models/
|   |-- ffmpeg/
|   |-- downloader/
|   |-- state/
|   `-- logs/
|-- scripts/
|   `-- openmontage_mcp/
`-- projects/
```

The launcher sets or passes every supported Jan/Electron data, cache, session,
log, and crash-dump path before the application starts. A portable-runtime test
captures filesystem changes and fails if the application writes persistent
state to `%APPDATA%`, `%LOCALAPPDATA%`, the user profile, or system folders.
Temporary operating-system files that Windows itself creates are not considered
OpenMontage state, but the launched processes must use a repository-local temp
directory whenever they honor `TEMP`/`TMP`.

## Jan Integration

The setup process obtains a pinned, checksummed Windows portable Jan release and
stores it in `runtime/jan/`. The repository retains the upstream license and
attribution. The integration is reproducible: either a small source patch is
built into the pinned shell or an equivalent supported Jan configuration is
applied, but the delivered artifact must satisfy the same black-box tests.

The seeded Jan profile contains:

- one custom OpenAI-compatible provider at `http://127.0.0.1:11434/v1`;
- only `openmontage-gpt-oss:20b-32k` exposed to chat;
- one OpenMontage assistant with bootstrap instructions to read and follow the
  repository's `AGENT_GUIDE.md`, pipeline manifests, and stage skills;
- one local STDIO MCP connection using the repository Python runtime;
- no cloud providers, web search, remote tools, model hub, telemetry, or
  automatic updates;
- the OpenMontage repository as the initial workspace;
- a visible per-conversation permission selector.

`qwen3.5:9b` is not shown in Jan's model picker. Visual-analysis MCP operations
route to it internally and unload it before returning control to the
orchestrator model. `OLLAMA_MAX_LOADED_MODELS=1` and the existing GPU guard
prevent both models from occupying VRAM simultaneously.

## Input Model

An input is a production-material set. Supported categories include:

- video and camera originals;
- audio, narration, room tone, music, and sound effects;
- images, illustrations, visual references, and storyboards;
- scripts, briefs, notes, and explanations in plain text, Markdown, DOCX, or
  PDF;
- subtitles and transcripts such as SRT and VTT;
- edit and timing data such as EDL, XML, CSV, and timecode notes;
- folders containing any mixture of the above;
- explicit public URLs resolved through the URL import gateway.

Every accepted input is recorded in
`projects/<project-id>/artifacts/input_manifest.json` with at least:

- stable input identifier;
- original local path or source URL;
- detected media/document type;
- inferred production role;
- technical metadata when available;
- relationships to other inputs;
- priority: required, reference, or optional;
- local working path for downloaded or generated derivatives;
- provenance and checksum when downloaded.

Local inputs are referenced rather than copied. Unsupported formats remain in
the manifest and are reported as unavailable for automatic interpretation; they
are never silently discarded.

## URL Import Exception

The former strict air-gapped policy cannot truthfully describe a workflow that
downloads URLs. The launcher therefore uses a new explicit policy, conceptually
`url-import-only`, rather than setting strict `OPENMONTAGE_OFFLINE=1` for the
whole process.

Under this policy:

- the chat and model may not search, browse, or fetch arbitrary pages;
- only a URL explicitly submitted by the user may enter the import gateway;
- a pinned portable downloader and FFmpeg download into
  `projects/<project-id>/inputs/downloads/`;
- redirects and media/CDN hosts required by that submitted URL are allowed only
  inside the short-lived downloader process;
- playlists, channels, profiles, and other potentially bulk inputs require an
  explicit confirmation with an estimated item count;
- the gateway records the original URL, resolved metadata, download time,
  tool version, output path, and checksum;
- after success or failure, the downloader exits and no other component gains
  outbound access;
- private or authenticated sources, browser-cookie import, and DRM bypass are
  excluded from the first release.

The runtime may be switched to true strict air-gapped mode, in which URL inputs
are rejected and all other local functions continue to work.

## Permission Modes

The selected mode belongs to a conversation and is stored in both Jan's local
conversation state and the OpenMontage project decision log.

### Auto

The agent may read declared inputs and create proxies, transcripts, analyses,
plans, project artifacts, previews, and renders without per-action prompts. It
may write only under the active project and approved runtime state locations.
It must ask before deletion, moving an original, modifying an external file,
bulk URL import, destructive cleanup, or another irreversible/high-impact
operation. Original source media is never overwritten.

### Confirm

Reads and non-mutating inspection proceed without prompts. Every command,
write, pipeline execution, download, and render requires approval in the chat
before the MCP server performs it.

### Read only

The MCP server exposes analysis and recommendation operations only. Mutating
filesystem, command, download, and render capabilities are absent from the
model's tool list and rejected again at the policy boundary if invoked through
stale conversation state.

### Invariants

- Major creative decisions and existing pipeline human gates still require
  approval in every mode.
- Dangerous command patterns are denied independently of mode.
- External source paths are read-only unless a separate explicit operation is
  approved.
- A mode change is visible, persisted, and appended to the audit log.
- The permission decision is enforced by the MCP layer, not merely by system
  prompt text or UI state.

## Project and Conversation State

Starting production in a new conversation creates the standard OpenMontage
project layout and `project.json`. Conversation metadata stores the associated
project identifier. Canonical artifacts and checkpoints remain the source of
truth for pipeline progress; the chat is a human-facing view, not a replacement
for project state.

Long operations report structured progress events to Jan. Each completed unit
updates the relevant checkpoint. Reopening a conversation reconstructs its
status from project artifacts and resumes from the latest valid checkpoint
rather than repeating completed analysis or rendering work.

## Startup and Shutdown

`START_OPENMONTAGE.bat` performs these steps:

1. Resolve and validate the repository root without relying on the current
   working directory.
2. Configure repository-local data, cache, temp, log, model, and service paths.
3. Start portable Ollama on loopback if the launcher does not already own a
   healthy instance.
4. Verify the fixed model tags and required context profile.
5. Verify FFmpeg, ffprobe, URL downloader, Python environment, Jan, and the MCP
   server.
6. Start Jan with the seeded OpenMontage profile and wait for MCP readiness.
7. Display actionable startup errors without closing the console immediately.

When the Jan window closes, the launcher stops the MCP and Ollama processes it
started. It does not terminate an Ollama or other process that was already
running and not owned by this launcher.

## Error Handling

Failures appear as structured chat cards containing the attempted operation,
failure category, retained work, next safe actions, and a recommended action.
The UI offers `Retry` and, when valid, `Resume from checkpoint`.

Missing local artifacts block only affected capabilities. No cloud or network
provider substitutes for an unavailable local operation. Unsupported input
formats remain listed in the input manifest. Partial downloads use temporary
names and never masquerade as complete media. Failed or interrupted operations
leave enough state for diagnosis and safe resumption.

Technical logs record timestamps, operation identifiers, tool versions, exit
codes, durations, and paths. They do not duplicate scenario text, full chat
content, authentication material, or media contents.

## Security and Privacy Boundaries

- Ollama, MCP, and local helper services bind only to loopback.
- The URL import gateway is the only outbound-capable process under the
  `url-import-only` policy.
- Jan's cloud providers, web search, telemetry, automatic update, and remote
  tool discovery are disabled.
- MCP resolves and validates absolute paths before mutating operations.
- Project writes are constrained to the active project and declared runtime
  state roots.
- Source files outside the project are read-only by default.
- The launcher and MCP server keep an append-only technical and decision audit
  trail without storing secrets.

## Verification Strategy

Automated contract and integration tests must cover:

- launch without Codex Desktop or Codex CLI installed;
- launch from a path containing spaces and from a non-system drive;
- no persistent Jan/OpenMontage state outside the repository;
- fixed visible orchestrator model and hidden visual model;
- actual loopback inference through both models, one loaded at a time;
- all three permission modes, including enforcement against stale or malicious
  tool calls;
- creation and recovery of project/conversation associations;
- ingestion of video, audio, images, PDF, DOCX, text, storyboard, subtitles,
  edit data, and mixed folders;
- unsupported-format preservation and clear degraded reporting;
- public URL download through a controlled local test server and subsequent
  local-only processing;
- rejection of URL input under strict air-gapped mode;
- bulk URL confirmation behavior;
- interrupted download, analysis, and render recovery;
- source-original immutability;
- project collection with only actually used source assets;
- graceful shutdown and process ownership;
- an end-to-end montage smoke test producing a playable local video.

Manual acceptance on the target Windows machine must verify that the interface
opens as a standalone window, attachments and progress are understandable,
permission changes are visible, errors are actionable, and the complete folder
can be moved to another path and relaunched without reconfiguration.

## Migration

The existing portable Ollama, model, FFmpeg, and provider work is retained.
`START_OFFLINE_EDITOR.bat` is superseded by `START_OPENMONTAGE.bat` after the new
launcher passes acceptance tests. Codex Desktop integration and its preflight
requirement are removed. Existing local editing guidance is updated to describe
Jan, heterogeneous inputs, permission modes, URL-import-only policy, and project
collection.

## Acceptance Criteria

The feature is complete when a user can move the OpenMontage folder to another
Windows path, double-click `START_OPENMONTAGE.bat`, open the familiar chat
window without Codex installed, attach a mixed production package or submit a
public URL, approve an editing plan, produce a local render under any permission
mode, close the application cleanly, and reopen the conversation with all
project state intact and no persistent OpenMontage/Jan state outside the folder.
