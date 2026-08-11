---
name: video-understand
description: |
  Understand video content fully offline using ffmpeg frame extraction, local transcription, and local Ollama semantic frame review. No URLs, API keys, or network providers.
  Use when: (1) Understanding what a video contains, (2) Transcribing video audio locally,
  (3) Extracting key frames for visual analysis, (4) Getting video content without API keys.
---

# video-understand

Understand video content locally using ffmpeg for frame extraction and Whisper for transcription. Fully offline, no API keys required.

## Offline contract

- Accept local paths only. Reject URLs and remote media.
- Use only software and model artifacts already present on disk.
- Never install, download, search, or call a cloud provider during production.
- Keep deterministic measurements out of the vision-model prompt.

## Prerequisites

- locally installed `ffmpeg` and `ffprobe` (required)
- locally installed transcription model (optional)
- local Ollama with `qwen3.5:9b` (optional semantic review)

## Commands

```bash
# Scene detection + transcribe (default)
python3 skills/video-understand/scripts/understand_video.py video.mp4

# Keyframe extraction
python3 skills/video-understand/scripts/understand_video.py video.mp4 -m keyframe

# Regular interval extraction
python3 skills/video-understand/scripts/understand_video.py video.mp4 -m interval

# Limit frames extracted
python3 skills/video-understand/scripts/understand_video.py video.mp4 --max-frames 10

# Use a larger Whisper model
python3 skills/video-understand/scripts/understand_video.py video.mp4 --whisper-model small

# Frames only, skip transcription
python3 skills/video-understand/scripts/understand_video.py video.mp4 --no-transcribe

# Quiet mode (JSON only, no progress)
python3 skills/video-understand/scripts/understand_video.py video.mp4 -q

# Output to file
python3 skills/video-understand/scripts/understand_video.py video.mp4 -o result.json
```

## CLI Options

| Flag | Description |
|------|-------------|
| `video` | Input video file (positional, required) |
| `-m, --mode` | Extraction mode: `scene` (default), `keyframe`, `interval` |
| `--max-frames` | Maximum frames to keep (default: 20) |
| `--whisper-model` | Whisper model size: tiny, base, small, medium, large (default: base) |
| `--no-transcribe` | Skip audio transcription, extract frames only |
| `-o, --output` | Write result JSON to file instead of stdout |
| `-q, --quiet` | Suppress progress messages, output only JSON |

## Extraction Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| `scene` | Detects scene changes via ffmpeg `select='gt(scene,0.3)'` | Most videos, varied content |
| `keyframe` | Extracts I-frames (codec keyframes) | Encoded video with natural keyframe placement |
| `interval` | Evenly spaced frames based on duration and max-frames | Fixed sampling, predictable output |

If `scene` mode detects no scene changes, it automatically falls back to `interval` mode.

## Output

The script outputs JSON to stdout (or file with `-o`). See `references/output-format.md` for the full schema.

```json
{
  "video": "video.mp4",
  "duration": 18.076,
  "resolution": {"width": 1224, "height": 1080},
  "mode": "scene",
  "frames": [
    {"path": "/abs/path/frame_0001.jpg", "timestamp": 0.0, "timestamp_formatted": "00:00"}
  ],
  "frame_count": 12,
  "transcript": [
    {"start": 0.0, "end": 2.5, "text": "Hello and welcome..."}
  ],
  "text": "Full transcript...",
  "note": "Use the Read tool to view frame images for visual understanding."
}
```

Use the local frame paths for visual inspection.

## Semantic frame review with Ollama

1. Extract representative frames first; never submit a complete video.
2. Submit one to three frames per scene and at most 20 images per request.
3. Call `ollama_vision_review` with `qwen3.5:9b`, structured JSON output, and an 8192-token context.
4. Preserve timestamps and scene IDs exactly.
5. Set `keep_alive: 0` and unload the model after every batch.
6. Store the result under `projects/<project-id>/artifacts/`.
7. Mark unavailable evidence degraded; never switch to a remote model.

## References

- `references/output-format.md` -- Full JSON output schema documentation
