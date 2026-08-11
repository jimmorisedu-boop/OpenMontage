# Edit Director - Localization Dub Pipeline

## When To Use

Translate the scene plan and supplied subtitle kit into concrete timeline decisions for each language output while preserving source picture and sound.

## Shared editorial method

Read `skills/creative/video-editing.md` and its editorial evidence reference completely before writing `edit_decisions`. Apply the evidence order, positive-reason rule, cut safety, pacing profile, and five QA passes. Pipeline-specific rules refine this method. Record missing editorial evidence as degraded; use local files only.

## Process

### 1. Preserve Structure By Default

Keep the original scene order and timing. In the offline minimal build, adapt subtitle phrasing and timing without generating translated audio.

### 2. Apply The Chosen Dub Mode

Per deliverable, decide where to:

- keep original picture with new subtitles,
- replace only the audio,
- use lip-sync output,
- cover mismatch with graphics or B-roll.

### 3. Keep Language Variants Organized

Separate timeline decisions by locale so versioning stays clear all the way into compose and publish.

### 4. Use Metadata For Variant Control

Recommended metadata keys:

- `locale_timeline_map`
- `timing_adjustments`
- `coverage_sections`
- `subtitle_strategy_by_locale`

### 5. Quality Gate

- language variants are explicit,
- timing changes are recorded,
- coverage decisions are deliberate,
- the original structure is only changed where necessary.

## Common Pitfalls

- Forcing every language to match source timing exactly.
- Mixing locale-specific notes into one ambiguous edit list.
- Hiding sections where the dub treatment is visually weak.
