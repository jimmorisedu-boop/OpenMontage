# Local LLM Video Agent Design

**Date:** 2026-08-09

**Status:** Approved for planning
**Target machine:** Windows, 16 GB VRAM, 64 GB system RAM

## Objective

Provide a fully local, text-driven OpenMontage agent without building a new
general-purpose agent framework. The first release uses Codex CLI as the
agent shell, Ollama as the inference server, `gpt-oss:20b` as the text
orchestrator, and `qwen3.5:9b` as a visual reviewer. A user starts the agent
from the repository and describes an edit in natural language; the agent then
follows the existing OpenMontage pipeline, skills, registry, artifact, review,
and checkpoint contracts.

## Scope

The MVP includes:

- a repeatable Windows setup and launcher for Codex CLI with local Ollama;
- a repository-local Codex profile/instruction layer for OpenMontage production;
- Ollama health, model-presence, and context-window preflight checks;
- `gpt-oss:20b` as the sole pipeline orchestrator;
- `qwen3.5:9b` as a provider-backed visual analysis tool;
- scene-guided frame sampling, semantic frame review, structured results, and caching;
- explicit sequential model loading for a 16 GB GPU;
- graceful degraded operation when visual analysis is unavailable;
- a user-facing local text-editing handbook with copyable commands and complete workflows;
- an agent-facing editorial playbook covering story, cut selection, pacing, reframing, audio, subtitles, and QA;
- automated contract and smoke tests that do not require paid APIs.

The MVP does not include:

- a chat panel embedded in Backlot;
- training, fine-tuning, or LoRA creation;
- direct ingestion of an entire video by the vision model;
- replacement of pipeline manifests, director skills, checkpoints, or approval gates;
- simultaneous residency of the orchestrator, vision model, and local generation model;
- unattended approval of paid generation calls or major creative decisions;
- installation of ComfyUI/WAN, Piper, ACE-Step, Real-ESRGAN, CodeFormer,
  rembg, Wav2Lip, SadTalker, or other optional local generation/enhancement stacks.

## Chosen Approach

### Ready-made agent shell

Use Codex CLI instead of implementing a Python orchestration loop. Codex owns
conversation state, repository navigation, shell execution, tool iteration,
and recovery. OpenMontage remains the domain control plane: `AGENT_GUIDE.md`,
pipeline manifests, director skills, the tool registry, schemas, and
checkpoints determine how production proceeds.

The launcher starts Codex from the repository root with the Ollama provider
and `gpt-oss:20b`. The initial target context is 32,768 tokens. The launcher
must fail with an actionable message when Ollama is unavailable, a required
model is missing, or the context configuration is below the supported floor.
It may offer the exact pull command, but it must not silently download a
multi-gigabyte model.

### Two-model routing

`gpt-oss:20b` performs all orchestration, planning, tool selection, artifact
writing, and user communication. It does not inspect images directly.

`qwen3.5:9b` performs bounded visual review. It receives representative frame
images plus a fixed editing-oriented prompt and returns schema-validated JSON.
The orchestrator consumes this compact result rather than raw image tokens.
The vision model never becomes a second autonomous agent and cannot call
production tools.

## Architecture

```text
User edit request
      |
      v
Codex CLI + gpt-oss:20b
      |
      +--> AGENT_GUIDE / pipeline manifest / stage director skills
      |
      +--> OpenMontage tool registry
                 |
                 +--> deterministic analysis (FFmpeg, ffprobe, metrics)
                 |
                 +--> frame_sampler (scene-guided representative frames)
                 |          |
                 |          v
                 |    Ollama vision provider + qwen3.5:9b
                 |          |
                 |          v
                 |    schema-validated visual_review JSON
                 |
                 +--> edit / compose / checkpoint tools
                            |
                            v
                 projects/<id>/renders/final.mp4
```

## Components

### 1. Local agent setup and launcher

A PowerShell setup command checks for Ollama, Node.js, Codex CLI, FFmpeg, the
repository virtual environment, and both model tags. It reports exact manual
installation or pull commands for missing dependencies. It does not modify
global configuration without showing the target and obtaining confirmation.

A PowerShell launcher:

1. resolves and verifies the OpenMontage repository root;
2. checks the Ollama API health endpoint;
3. verifies `gpt-oss:20b` and `qwen3.5:9b` are locally present;
4. verifies a context window of at least 32K for the Codex session;
5. starts Codex in the repository using the local model profile;
6. preserves Codex's normal approval behavior and OpenMontage's human gates.

The launcher is a convenience boundary, not an orchestrator. It must not
encode pipeline stage decisions.

### 2. Ollama client boundary

A small provider client under `lib/providers/` owns only Ollama transport:

- health and installed-model queries;
- multimodal chat requests;
- JSON response decoding;
- configurable request timeout;
- explicit model unload via `keep_alive: 0`;
- clear connection, timeout, model-missing, and malformed-response errors.

It has no OpenMontage stage logic and can be tested against a fake HTTP
server. No Ollama SDK dependency is required; the implementation uses the
existing HTTP dependency already available to the project.

### 3. Ollama visual analysis provider

A new `BaseTool` provider under `tools/analysis/` exposes bounded semantic
visual review through the existing `analysis` capability. It reuses
`frame_sampler` output rather than implementing another FFmpeg extractor.

Inputs:

- image paths and their timestamps;
- optional scene identifiers;
- review mode: `content`, `continuity`, `crop`, `select`, or `full`;
- target aspect ratio when crop review is requested;
- explicit output path under `projects/<project-id>/artifacts/`;
- model tag, defaulting to `qwen3.5:9b`.

The tool accepts at most 20 frames per request in the MVP. Pipelines should
normally select one to three representative frames per scene and split larger
reviews into batches. This bounds latency, VRAM pressure, and hallucination
risk.

The result contains:

- per-frame timestamp and scene identifier;
- concise content description;
- visible people, objects, actions, and on-screen text;
- semantic issues such as closed eyes, obstructed subject, or mismatched action;
- continuity relationship to adjacent frames;
- suitability and rationale for each supported target crop;
- duplicate or near-duplicate group identifiers;
- preferred-frame ranking where selection was requested;
- confidence per judgment;
- model tag, prompt/schema version, source hashes, and cache status.

All output is validated before success is returned. Malformed output receives
one constrained repair attempt. A second failure returns a failed `ToolResult`;
the provider must not invent missing fields in Python.

### 4. Deterministic visual metrics

Blur, brightness, contrast, resolution, duration, and similar measurable
properties remain deterministic Python/FFmpeg work. The existing quality
analysis is retained and can be composed with the semantic review. The vision
model is not asked to estimate values that local code can measure reliably.

### 5. Cache

Visual results are cached by:

```text
SHA256(frame bytes + model tag + review mode + target aspect ratio + prompt/schema version)
```

Cache entries are immutable JSON documents stored inside the active project's
artifact area so the run remains inspectable and portable. A cache hit avoids
loading the vision model. Changing the model or prompt/schema version produces
a new entry rather than overwriting previous evidence.

### 6. Editing guidance

The MVP ships two complementary instruction layers.

The user-facing handbook explains how to prepare source files, describe an
editing goal, choose a platform/duration, request transcript-led and
vision-led decisions, review the proposed cut, approve gated stages, and find
the final output. It includes complete examples for talking-head cleanup,
podcast highlights, short-form extraction, screen demos, aspect-ratio
variants, subtitle-only localization, and revision requests. Every example is
achievable with the minimal local stack and clearly labels unsupported voice,
music, image, and video generation.

The agent-facing editorial playbook defines a repeatable decision algorithm:

1. preserve the source and inspect media metadata;
2. establish audience, platform, duration, delivery promise, and non-negotiable content;
3. combine transcript, silence, scene, deterministic quality, and semantic frame evidence;
4. build the narrative spine before choosing individual cuts;
5. produce evidence-backed keep/remove decisions with exact timecodes and cut handles;
6. design pacing, reframing, subtitles, graphics, and audio without hiding source defects;
7. render a reviewable draft and run continuity, intelligibility, subtitle, crop, and technical QA;
8. record warnings and obtain required approval before final render.

The playbook distinguishes editorial judgment from mechanical execution and
prohibits destructive source edits, mid-word cuts, clipped phonemes, silent
story changes, unsupported generated assets, and unverifiable claims about
what is visible in the footage.

## GPU Lifecycle

The 16 GB GPU is treated as a single-model resource.

1. Codex completes an orchestrator turn with `gpt-oss:20b`.
2. Before a vision batch, the visual provider requests immediate unload of
   `gpt-oss:20b`.
3. Ollama loads `qwen3.5:9b`, performs the bounded review, and unloads it with
   `keep_alive: 0` after the response.
4. The next Codex turn reloads `gpt-oss:20b`; conversation state remains in
   the Codex process.
5. Before ComfyUI or another local GPU generation tool starts, both configured
   LLM tags are explicitly unloaded.

Model switching adds latency but prevents out-of-memory failures. The system
must never assume that 64 GB system RAM makes concurrent GPU residency safe.
If unloading fails, local GPU generation is blocked with a clear error rather
than attempted optimistically.

## Pipeline Integration

Visual review is an analysis capability, not a new pipeline stage. A relevant
stage director may call it after scene detection/frame sampling and before an
edit or asset approval decision. Canonical artifacts reference the resulting
JSON path and summarize material findings; they do not embed base64 images.

The provider follows normal registry discovery. Preflight reports it as
available only when Ollama responds and the configured vision model is present.
If unavailable, the run is explicitly marked degraded and continues only with
deterministic analysis where the selected pipeline permits that fallback.
There is no silent swap to CLIP, BLIP, LLaVA, or a cloud vision provider.

## Error Handling

- **Ollama unavailable:** launcher/tool fails with the checked URL and startup
  guidance.
- **Model missing:** report the exact missing tag and `ollama pull` command;
  do not auto-download.
- **Insufficient context:** launcher refuses to start the production profile
  below 32K.
- **Malformed vision JSON:** perform one schema-guided repair, then fail.
- **Frame unreadable:** fail that frame with its path and continue only when
  the requested review can remain complete; otherwise fail the batch.
- **Model unload failure:** block the next local GPU consumer and report the
  loaded models.
- **Vision unavailable mid-run:** record degraded status and ask before making
  any consequential fallback or provider change.

## Safety and Governance

- Local LLM inference sends no prompts, scripts, or frames to a cloud LLM.
- Domain-specific cloud generation tools remain governed by their existing
  provider declarations, cost estimates, and approval gates.
- The launcher does not disable Codex sandboxing or approvals globally.
- OpenMontage's human checkpoints remain binding.
- Every visual result records source hashes and model/prompt versions.
- Generated media and artifacts stay under `projects/<project-id>/`.

## Testing Strategy

### Unit tests

- Ollama client health, model listing, chat, timeout, malformed JSON, and unload;
- visual-review input and output schema validation;
- cache-key stability and invalidation;
- model lifecycle ordering;
- launcher dependency and path checks where logic can be isolated.

All HTTP unit tests use fakes and require neither Ollama nor a GPU.

### Contract tests

- registry discovers the visual provider with correct capability, runtime,
  dependencies, schemas, side effects, and install instructions;
- successful artifacts stay under the project workspace;
- unavailable Ollama/model states produce `UNAVAILABLE`, not false-positive
  availability;
- existing phase-zero and tool contract suites remain green.

### Opt-in local smoke test

When both models are installed, a marked integration test:

1. checks Ollama health;
2. analyzes two fixture frames with `qwen3.5:9b`;
3. validates the returned JSON;
4. confirms the vision model is unloaded afterward;
5. performs a short `gpt-oss:20b` structured response to verify reload.

The smoke test is skipped by default in CI and makes no paid or cloud calls.

## Acceptance Criteria

The MVP is complete when:

1. a Windows user can install the two Ollama model tags, run one repository
   launcher, and enter a natural-language editing request in Codex;
2. Codex follows the existing OpenMontage pipeline and approval contracts;
3. a pipeline can sample project frames and obtain schema-valid semantic review
   from `qwen3.5:9b` through the registered analysis provider;
4. the visual result is cached, provenance-recorded, and consumable by the
   orchestrator without raw image context;
5. the orchestrator and vision model are demonstrably loaded sequentially;
6. a local GPU generation step is blocked unless both LLM models are unloaded;
7. missing local components yield actionable errors or an explicitly degraded
   path, never a silent cloud/provider substitution;
8. relevant unit and contract tests pass, and the opt-in two-model smoke test
   passes on the target machine.
9. a new user can follow the local editing handbook from source-file placement
   to approved render without reading repository architecture documentation;
10. every source-led edit director routes agents through the shared editorial
    playbook, and contract tests verify the required workflow and QA sections.

## Future Extensions

After the CLI workflow is proven, the same provider and artifacts may be
exposed through a Backlot chat panel. That UI should invoke the established
agent boundary rather than duplicate orchestration logic. Direct temporal
video models, alternate vision providers, automatic shot comparison, and
fine-tuned edit-ranking models remain separate follow-on projects.
