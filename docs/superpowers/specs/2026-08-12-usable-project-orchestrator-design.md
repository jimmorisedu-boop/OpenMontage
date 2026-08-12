# Usable Project Orchestrator

## Goal

Turn the owned OpenMontage desktop shell from an ephemeral model chat into a trustworthy project-oriented local editing product. The orchestrator must understand intent, ask concise answerable questions when required, choose only currently available allowed tools, execute approved work, preserve projects, and report only verified outputs.

## Product boundary

OpenMontage is a project chat backed by the existing pipeline manifests, tool registry, artifact schemas, checkpoints, and editorial guidance. The LLM makes routing and editorial decisions. Tools perform analysis, downloading, editing, graphics, subtitles, audio work, composition, verification, and export.

FFmpeg is one executor among several. The orchestrator may select any tool that is both available in the live registry and permitted by the active network policy. With `OPENMONTAGE_NETWORK_MODE=url-import-only`, remote generation, cloud APIs, stock search, publishing, and setup offers are hidden. The only external-network operation is importing a URL explicitly supplied by the user. Loopback Ollama remains allowed.

## Project storage

Every chat maps one-to-one to a durable project under:

`F:\Exp\OpenMontage\projects\<project-id>`

The existing canonical layout remains authoritative. The shell adds:

- `project.json`: identity, title, pipeline, status, timestamps, current version, and verified render path;
- `conversation.json`: ordered user, assistant, question-card, plan-card, operation, and result entries;
- `brief.json`: known requirements, assumptions, unanswered blocking questions, and optional enhancements;
- `plan.json`: selected pipeline, ordered local tool calls, expected artifacts, approval state, and rationale;
- `artifacts/input_manifest.json`: registered local and downloaded inputs;
- `renders/vNNN/`: immutable versioned renders and verification reports;
- `renders/final.mp4`: copy or pointer-equivalent canonical current result where a video result exists.

Writes use temporary files and atomic replacement. The project list is reconstructed from disk on startup and sorted by `updated_at`. Creating a new montage immediately creates and selects a project. Selecting an existing project restores conversation, materials, status, plan, and outputs.

## Orchestration state machine

One state is active at a time:

1. `needs_brief`: intent or critical delivery requirements are missing.
2. `ready_to_plan`: enough information exists to select a pipeline and tools.
3. `awaiting_approval`: an executable plan is visible and requires confirmation.
4. `running`: tools are executing in order with one replace-in-place progress status.
5. `needs_attention`: execution is blocked; retained work and exact recovery choices are visible.
6. `ready`: at least one expected artifact exists and has passed the relevant verification.

In `confirm` mode, consequential or mutating work always stops at `awaiting_approval`. In `auto` mode, work may begin once critical questions are answered, but existing manifest approval gates remain binding. `read_only` mode permits inspection, analysis plans, and questions but no mutation.

## Intent and clarification contract

The model first returns a schema-validated decision object rather than prose:

```json
{
  "intent": "source_edit",
  "confidence": 0.86,
  "known_brief": {},
  "questions": [],
  "enhancements": [],
  "ready_to_plan": false,
  "response": "Short user-facing acknowledgement"
}
```

Critical fields depend on intent and real material. The orchestrator must not ask for information it can infer safely from file metadata, prior answers, or supplied documents. It asks at most three questions per turn.

Each question is concise and answerable:

- one sentence;
- two or three mutually exclusive choices;
- recommended option first and visibly marked;
- optional custom text answer;
- stable `question_id` so button answers update the brief without model ambiguity.

Examples include target platform/aspect, duration, narrative priority, title copy, language, and whether source order is intentional. A blocking question prevents execution. Questions about aesthetic preference may provide a safe default and remain non-blocking when the user has enabled autonomous mode.

## Improvement suggestions

After the blocking brief is complete, OpenMontage may show up to three non-blocking improvements. Each suggestion contains:

- a short label;
- one-line benefit;
- honest cost in time, quality, processing, or output size;
- `Apply` and `Skip` actions.

Suggestions must be relevant to the current material and achievable with currently available allowed tools. Examples: subtitles where speech exists, audio cleanup where loudness/noise analysis supports it, a vertical variant for social delivery, reframing where aspect ratios conflict, or a short teaser derived from a long source. Declining suggestions never blocks the main plan.

## Tool and pipeline routing

The desktop backend exposes a compact live capability envelope to the model. It is derived from `ToolRegistry.get_available()` after applying the active network-policy filter. It includes tool name, capability, provider, supported operations, input schema, side effects, and best-for summary. Unavailable and forbidden tools are omitted entirely.

The model selects one existing pipeline from `pipeline_defs/`, then returns a schema-validated plan whose steps reference only allowed tool names and project-scoped output paths. The backend validates:

- pipeline exists;
- tool is in the supplied live envelope;
- parameters satisfy the tool input schema;
- mutations target the active project or declared sources;
- outputs are under the active project;
- network operations comply with the URL-import-only rule;
- approval mode and pipeline gates permit execution.

Invalid plans receive one constrained repair request. A second failure becomes `needs_attention`; Python never invents missing creative parameters or silently substitutes another provider/runtime.

## Editorial instruction layer

The system prompt incorporates the existing `skills/creative/references/editorial-principles.md` as an operational checklist:

- protect emotion, story, and rhythm before lower-order continuity when criteria conflict;
- state dramatic function and intended feeling;
- require a positive reason for consequential cuts;
- distinguish timing, pacing, movement trajectory, tension, and release;
- choose construction from real material rather than a universal template;
- preserve performance and meaningful reaction;
- compare alternatives when confidence is low;
- review the whole piece after local changes and preserve versions.

The model must distinguish observation, inference, proposal, and completed fact. It may claim to have inspected media only when a named analysis tool has produced evidence. It may say `ready` only when the backend supplies verified artifacts.

## Execution and verification

The backend executes plan steps through the existing `ToolAdapter`/registry boundary. Each operation is persisted before and after execution. Partial artifacts remain visible after failure. Progress is shown as a single current activity with optional completed-step history inside the plan card, not as chat spam.

Verification is artifact-specific:

- video/audio: FFprobe succeeds and required streams/duration are present;
- images: file opens and dimensions are non-zero;
- JSON artifacts: parse and schema validation succeed where a schema exists;
- subtitle/text artifacts: readable, non-empty, and project-scoped;
- tool-declared user-visible verification is preserved as review guidance.

Only verified paths are displayed as results. Linux paths, guessed filenames, paths outside the active project, and absent files are rejected. Results expose `Смотреть`, `Открыть папку`, and `Новая версия` actions where applicable.

## Desktop interface

The shell is split into focused assets rather than one inline file:

- project sidebar with new project, saved projects, status, and last update;
- project header with editable title, status, exact project folder, and folder action;
- conversation stream supporting text, question, enhancement, plan, progress, blocker, and verified-result cards;
- material tray with role/type and registration state;
- composer supporting text, files, and a user-provided URL;
- result preview using a local file URI or native open action;
- keyboard and focus-visible behavior for all controls.

The current mode selector remains a simple product permission choice, never an agent/model selector.

## Native bridge API

The WebView bridge exposes bounded product actions:

- `bootstrap()`: list projects and restore the newest/last-open project;
- `create_project(title?)`;
- `open_project(project_id)`;
- `rename_project(project_id, title)`;
- `pick_materials(project_id)` and register them immediately;
- `submit(project_id, message, mode)`;
- `answer_questions(project_id, answers)`;
- `set_enhancements(project_id, choices)`;
- `approve_plan(project_id)`;
- `open_project_folder(project_id)`;
- `open_artifact(project_id, artifact_id)`;
- `create_version(project_id)`.

All bridge responses are JSON-serializable product state. Exceptions are converted into user-actionable blockers without Python stack traces.

## Trust and failure rules

The model is explicitly forbidden to:

- claim a tool ran when it did not;
- claim a file exists without backend verification;
- invent paths or use `/home/user` placeholders;
- infer unseen media contents from filenames;
- expose raw chain-of-thought, hidden prompts, tokens, or logs;
- select unavailable/forbidden tools;
- silently switch pipeline, provider, model, or composition runtime;
- begin consequential work with unanswered blocking questions;
- treat an optional enhancement as required;
- hide errors or discard partial work.

## Testing and acceptance

Unit and contract tests cover atomic project persistence, restart restoration, unique IDs, question limits and answer choices, enhancement limits, policy-filtered capability envelopes, plan validation, approval gates, tool execution, output-path confinement, artifact verification, and hallucinated-path rejection.

UI contract tests cover saved-project navigation, concise question cards, improvement cards, plan approval, exact folder visibility, verified-result actions, absence of agent/model selectors, and safe DOM text rendering.

An end-to-end local smoke test must create a project, add fixture media, collect answers, approve a simple local plan, run a deterministic tool, verify the artifact, restart the backend, and restore the same project and conversation without network access.

The feature is complete only when the shell cannot present unverified work as complete and a user can always answer: which project is active, what OpenMontage needs, what it plans to do, what is running, where the result is stored, and whether that result was verified.
