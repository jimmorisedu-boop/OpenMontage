# Offline Video Understanding

Use supplied local media only. Never fetch a URL, call a cloud vision service, or download a model during a run.

## Evidence split

- Use FFmpeg/Python for duration, resolution, frame rate, scene boundaries, silence, blur, brightness, contrast, and loudness.
- Use `frame_sampler` for representative local frames.
- Use `ollama_vision_review` with the locally installed `qwen3.5:9b` only when a decision depends on visible meaning: action, expression, obstruction, continuity, duplicate takes, visible text, or crop suitability.

## Semantic review procedure

1. Extract one to three representative frames per scene.
2. Submit at most 20 ordered frames per request.
3. Preserve timestamp and scene ID metadata.
4. Write JSON under `projects/<project-id>/artifacts/`.
5. Cite that JSON from the scene plan or edit decision.
6. Mark unsampled moments as unseen and unavailable review as degraded.
7. Never substitute CLIP, BLIP, LLaVA, a remote Ollama host, or a cloud provider.

For provider parameters and GPU lifecycle, read `.agents/skills/video-understand/SKILL.md`.
