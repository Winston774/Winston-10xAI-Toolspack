# Video Method Notes

Source video: `https://www.youtube.com/watch?v=XeTAlZiIWHE`

The video has English auto-generated captions. I used them only to confirm the implementation approach and did not store the full verbatim transcript in this repository.

## Confirmed Method

- Treat the editor as a Claude Code project folder, not as a single monolithic application.
- Use the same seven steps for every job: intake, rough cut, graphics, second pass, captions, background music, export.
- Keep raw clips under `projects/<job>/raw` and promote finished files to `outputs/<job>.final.mp4`.
- Use external engines where they are strongest: WhisperX for transcription, FFmpeg for media operations, HyperFrames-style manifests for graphics, and optional tools for caption retrieval.
- Make format variants preset-driven. In the screenshot and transcript, the meaningful differences are graphics and caption behavior.
- Keep presets locked so each job repeats the same house style.

## Implemented Here

- `agent-video init` creates the job folder.
- `agent-video run` executes the seven-step pipeline.
- `agent-video fetch-subtitles` writes a summary by default and requires an ownership flag before writing full VTT captions.
- `skills-lock.json`, `skills/*/SKILL.md`, and `agent_video_editor/presets` mirror the method shown in the video.
