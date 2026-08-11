# Evidence-Driven Offline Video Editing

Read `skills/creative/references/editorial-principles.md` before consequential edit decisions. Use only local files and local tools.

## When to Use

Use this method whenever supplied footage is trimmed, reordered, reframed, subtitled, mixed, or prepared for local delivery.

## Editorial contract

- Never overwrite or destructively modify the source master.
- Establish audience, platform, target duration, delivery promise, must-keep material, and approval policy before selecting cuts.
- Separate editorial judgment from mechanical execution.
- Cite transcript timecodes, scene IDs, frame-review evidence, or deterministic metrics for every consequential keep/remove decision.
- Never fetch media, research, fonts, music, images, or references from the internet.

## Evidence order

1. Inspect source integrity and metadata.
2. Read transcript and word timestamps.
3. Read silence and scene boundaries.
4. Read deterministic picture/audio metrics.
5. Read `ollama_vision_review` only for semantic judgments.
6. Mark missing evidence degraded; never claim to have watched an unsampled moment.

## Build the narrative spine

Define hook, context, development, payoff, and optional call to action before refining cuts. Preserve enough setup that every excerpt remains accurate. State the intended viewer feeling and scene purpose.

## Make keep/remove decisions

Record source in/out, positive reason, evidence, transition intent, confidence, and effect on emotion/story/rhythm. Keep the strongest complete delivery of repeated ideas. Remove false starts, redundant takes, off-goal tangents, and accidental dead air. Preserve intentional emphasis, breaths, reactions, and meaning-changing context.

## Resolve competing cuts

Prefer, in order: intended emotion, story clarity, rhythm, eye trace, two-dimensional screen continuity, then three-dimensional spatial continuity. Treat this as a conflict-resolution order, not a numerical score. Repair lower-order continuity after choosing the dramatically right cut.

## Cut safety

- Cut dialogue at word or phoneme-safe boundaries, never mid-word.
- Retain 80-150 ms speech handles unless inspection proves a tighter cut clean.
- Add 10-30 ms audio fades at hard boundaries to prevent clicks.
- Use J/L cuts around 0.2-0.5 seconds only when they improve continuity.
- Re-encode exact cuts when GOP boundaries would move the requested timecode.
- Keep meaningful reactions when they reveal comprehension, doubt, surprise, or conflict.

## Pacing profiles

- Energetic short-form: compress setup, increase event density, retain only pauses that create emphasis; do not damage intelligibility.
- Balanced medium-form: alternate information density with short recovery beats; keep natural sentence rhythm.
- Calm long-form: preserve performance, context, and reflection; remove only errors, repetition, accidental silence, and off-goal material.

Shape timing, pacing, and movement trajectory separately. After local changes, watch the full sequence to evaluate tension and release.

## Reframing

Keep faces, gestures, active UI state, and on-screen text inside safe areas. Avoid crop changes during meaningful movement. For vertical variants, verify sampled frames rather than assuming a centered crop works.

## Subtitles

Time captions to speech, break lines at semantic boundaries, keep readable line lengths, respect safe areas, and label speakers only when needed. Never let a subtitle contradict visible text or remove meaning-changing context.

## Audio

Prioritize intelligible speech and room-tone continuity. For ordinary web files, target about -14 LUFS integrated and peaks no higher than -1 dBTP unless the requested platform profile says otherwise. Use only supplied local audio; do not generate or fetch music, voice, or sound effects.

## QA passes

1. Story: verify factual and emotional continuity and the delivery promise.
2. Picture: verify continuity, eye trace, crop, overlays, and reactions.
3. Audio: verify speech, clicks, sync, room tone, and loudness.
4. Subtitles: verify text, timing, line breaks, speakers, and safe areas.
5. Delivery: verify duration, resolution, frame rate, codec, and playback.

Review the whole piece after every group of local fixes; do not approve from isolated cut points alone.

## Quality Checklist

- [ ] Every consequential cut has local editorial evidence and a positive reason.
- [ ] Speech, reactions, factual context, crops, subtitles, and audio pass review.
- [ ] The complete file plays with the requested duration, format, and pacing.
- [ ] No URL, remote provider, generated asset, or source-master overwrite was used.

## Required edit_decisions fields

Include ordered keep/cut segments, source paths, in/out timecodes, rationale and evidence, speed, transitions, reframes, overlays, subtitles, audio treatment, warnings, QA results, and approval state. Keep source master paths distinct from generated outputs.
