---
name: rough-cut
description: Build the first clean edit from raw footage.
---

Use WhisperX when available to transcribe the raw clip. Remove filler words, long silences, repeated starts, and dead air before touching graphics. Produce:

- `projects/<job>/work/02-rough-cut.mp4`
- `projects/<job>/work/rough-cut-plan.json`
- `projects/<job>/scripts/edit-script.md`

If WhisperX or FFmpeg is missing, create the plan and pass media through so the next step can continue.
