# Director Studio Shell Design

## Goal

Replace the chat-first OpenMontage window with a director-oriented workspace that makes the current media, edit shape, progress, questions, and outputs visible at the same time while preserving natural-language control.

## Approved direction

The approved visual combination is **C2 / P2 / T3**:

- C2: a large preview and a clear read-only edit timeline are the center of the workspace;
- P2: a permanent right rail switches between **Assistant** and **Files**;
- T3: project navigation and text-heavy surfaces are light, while preview and timeline use a dark editing canvas.

The product remains OpenMontage. It never exposes model, provider, or agent selectors.

## Information architecture

The desktop window has three permanent regions:

1. **Project rail** — compact project list, create action, active status, and local-processing trust signal.
2. **Director canvas** — project header, stage progress, media preview, read-only timeline, and output/version actions.
3. **Context rail** — Assistant and Files tabs. Assistant contains conversation, concise question/plan/result cards, operation status, and the command composer. Files contains grouped input materials, versions, and verified outputs.

At widths below 900 px the context rail becomes an in-layout tabbed panel beneath the preview. It must never cover the preview or timeline.

## Director canvas

The preview uses the latest verified playable media artifact when one exists. Before a result exists it shows an intentional empty state with material count and the next required action. Native playback controls remain available.

The timeline is descriptive rather than directly editable. It visualizes:

- plan steps when a plan exists;
- source materials when planning has not started;
- a simple audio lane when audio material is present;
- playhead progress while a playable result is previewed.

It is labelled as an edit overview so users do not mistake it for a full NLE. Direct edits happen through the Assistant.

## Assistant rail

Conversation cards remain durable and preserve existing backend IDs. Only the active question, enhancement, or plan card is actionable. Questions use concise choices plus a custom answer. Progress appears as one compact current operation, not repeated log spam. Completed operations collapse into history.

The composer is pinned at the bottom of the rail and accepts natural-language requests. Material attachment lives in the Files tab and in the empty-preview call to action, not beside every message.

## Files rail

Inputs are grouped by video, audio, image, and document with recognizable filenames and counts. Results show verified outputs with Play/Open actions. Versions show version ID, change note, and parent relationship. The exact project folder remains one click away.

## Visual system

- System UI font, compact optical heading tracking, and readable body leading.
- Warm off-white structural surfaces; near-black preview/timeline canvas.
- Coral is reserved for the current action and playhead.
- Green communicates verified output or completed stage.
- Borders and shadows are restrained; no gradients, decorative blobs, excessive pills, or emoji as primary controls.
- Motion is limited to short opacity/transform transitions and disabled under reduced-motion preferences.
- Reduced transparency and increased contrast preferences receive solid surfaces and stronger borders.

## Accessibility and behavior

- Semantic buttons, labelled tabs, labelled timeline and preview regions.
- Keyboard-visible focus, minimum 40 px primary targets, and no icon-only action without an accessible name.
- Live regions announce current operation and errors without repeating the full conversation.
- Inline error recovery replaces alerts.
- Buttons disable during duplicate-prone operations and stale cards remain visibly historical.

## Data and compatibility

No new remote dependency is introduced. The shell consumes the existing `DesktopApi` project payload and derives a view model from `conversation`, `brief`, `plan`, `input_manifest`, `artifacts_state`, `versions`, and `operations`. Existing projects without newer fields render with safe empty defaults.

Opening a preview remains ID-addressed through `open_artifact`; rendering the local media in the preview does not create new result records.

## Verification

- Static executable UI-contract tests cover the three-region studio, tabs, preview, timeline, files, modes, accessibility, and absence of model/agent controls.
- Existing bridge and orchestrator suites remain green.
- Full repository tests and portable preflight must pass.
- The final native WebView window is restarted and checked for a responding process.
