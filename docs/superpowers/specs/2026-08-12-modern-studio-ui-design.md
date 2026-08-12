# Modern Studio UI Design

## Product intent

OpenMontage should feel like a focused native creative application, not a web chat embedded in a window. The interface must make the current project, media result, next decision, files, and background work understandable without exposing implementation details such as models, providers, or agents.

## Approved autonomous direction

The shell becomes a component application built around one dominant visual hierarchy:

1. a compact project library for wayfinding;
2. a flexible stage for preview and project status;
3. a concise edit overview anchored below the stage;
4. an inspector with Assistant and Files workspaces.

Every region can resize and fully collapse. At constrained window widths, panels become temporary overlays instead of shrinking or covering the stage.

## Visual system

- Neutral graphite foundation with calibrated elevation, not flat black panels.
- One warm coral action color; semantic green, amber, and red only for state.
- System variable typography with a 12/13/15/20 px scale, optical heading tracking, and 1.35-1.55 line heights.
- An 8 px spacing grid with 4 px optical corrections.
- Thin separators, restrained shadows, 10-14 px radii, and no decorative gradients or excessive pills.
- Icons come from one Lucide set and always have accessible labels when icon-only.

## Interaction model

- Project actions use an accessible dropdown; destructive deletion uses an alert dialog.
- Inspector navigation uses accessible tabs.
- Panels use stable resizable groups, remember proportions, and expose explicit collapse controls.
- Motion is limited to short, interruptible opacity/transform feedback and respects reduced motion.
- Current background work is shown once in the inspector; errors are inline and recoverable.

## Technical architecture

- React + TypeScript + Vite development shell.
- Radix UI primitives for menus, dialogs, tooltips, and tabs.
- Lucide React for iconography.
- Motion for small state and layout transitions.
- react-resizable-panels for workspace sizing.
- Vite single-file build emits `scripts/openmontage_chat/index.html`; the portable runtime needs no Node, server, CDN, or internet.
- A typed pywebview bridge remains the only state mutation boundary.

## Acceptance criteria

- All existing project, conversation, question, plan, operation, artifact, version, and permission flows remain available.
- No model/provider/agent selectors appear.
- No HTTP `fetch` is used by the native shell.
- Built output is a self-contained HTML file.
- Usable at the native minimum window size without overlap or horizontal overflow.
- Full repository regression, JS build, portable preflight, and responding native process are verified.
