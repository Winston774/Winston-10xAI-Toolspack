# Ingest — getting any source into `source/`

```bash
uv run scripts/ingest.py <file-or-url> [more…] --out decks/<slug>/source [options]
```

`uv` resolves the script's Python dependencies on first run (PyMuPDF, pymupdf4llm, markitdown,
OpenCC) into a cache; nothing is installed globally. Media tools run through `uvx` the same way.
Every run rebuilds `source/` from scratch (old chunks, frames and figures are removed), so copy anything
you put on a slide into `decks/<slug>/assets/` first.

## What it accepts

| Source | How it is read |
|---|---|
| `.pdf` | pymupdf4llm → Markdown with `<!-- page N -->` anchors; tables kept; page renders in `pages/` (first 40 pages); embedded images ≥ 360 px in `figures/` |
| `.epub` | the book's reading order (OPF spine) through markitdown: real paragraphs and chapter headings; `<!-- page N -->` anchors only when the EPUB carries print-page markers; images ≥ 300 px in `figures/` (with their chapter and alt text), the cover as `figures/cover.*` |
| `.mobi .fb2` | PyMuPDF, one paragraph per text block, chapter headings from the table of contents; page numbers are the converter's, not the printed book's |
| `.docx .pptx .xlsx .html` | markitdown |
| `.md .txt` | as is |
| `https://…` article | markitdown fetches and converts |
| YouTube URL | yt-dlp, **one** subtitle track chosen from the video's metadata: human subtitles in the spoken language, else that language's speech-recognition captions — never machine-translated tracks; otherwise the audio is transcribed. Chapters become headings; licence, channel, upload date and the transcript's provenance go to the manifest; a ≤ 720p video stream yields keyframes |
| audio `.mp3 .m4a .wav .aiff .flac .ogg` | ffmpeg → 16 kHz WAV → Whisper, paragraphs with `[hh:mm:ss]` anchors |
| video `.mp4 .mov .mkv .webm` | as audio, plus keyframes in `frames/frame-hhmmss.jpg` (scene changes and at least one every 45 s, ≤ 36) and a contact sheet `frames/contact.jpg` |

Several sources in one call are combined into one `source.md`, each under its own heading. Project
Gutenberg's header and licence (≈ 3,500 words that are not the book) are removed from any source; the
edition facts they carry (editor, translator, release) go to the manifest under `edition`.

## Options

| Option | Use |
|---|---|
| `--lang zh-TW` | the language **spoken in the recording**, not the deck's language. Mandarin → **Traditional Chinese with Taiwan phrasing** (Whisper writes Simplified for `zh`; this adds a Traditional prompt and converts with OpenCC s2twp). Also `en`, `ja`, `zh` … An English talk for a Taiwanese audience: omit it (or `--lang en`) and translate while writing the deck. On YouTube a mismatching `--lang` is overridden by the video's own language (with a warning); a human translation in `--lang`, if the video has one, is saved as `translation-<code>.md` |
| `--prompt "Transformer, BLEU, 注意力"` | names and jargon the recording uses — fixes most mis-hearings |
| `--model …` | transcription model; default `mlx-community/whisper-large-v3-turbo` (Apple Silicon). `mlx-community/whisper-small` is a fast draft |
| `--no-frames` | YouTube: skip the video download that yields keyframes |
| `--pdf-engine docling` | MIT-licensed converter, slower, stronger on complex layouts/tables (default PyMuPDF is AGPL — fine for personal use) |
| `--render-pages 0` | skip page renders (very long PDFs) |
| `--chunk-words 9000` | chunk size for long sources |

## Outputs

`source.md` (front matter + text with page/timestamp anchors and chapter headings) · `manifest.json`
(words, reading minutes, per-source metadata, TOC, licence, `transcript` provenance, `page_numbers`,
assets) · `pages/` · `figures/` · `frames/` (+ `contact.jpg`) · `translation-<code>.md` · `chunks/` (only
when the source is long).

## Reading strategy

1. `manifest.json` first: size, structure (TOC or chapters), what assets exist, and how far to trust and
   how to cite the text:
   - `transcript.kind`: *manual subtitles* are reliable; *speech-recognition captions* are unpunctuated
     and mishear names — check every quote against the audio or a second source.
   - `page_numbers`: when it says there are none (most EPUBs), cite the chapter (「第三講」, “ch. 4”), never
     the anchor numbers of a converter.
   - `license`: decides whether frames and figures may go on slides and what the credit line says.
2. Short sources (< ~15k words): read `source.md` whole. Look at 2–4 page renders that hold figures
   or tables — vector figures only appear there. For video, open `frames/contact.jpg` once: it shows
   every keyframe with its timestamp.
3. Long sources: digest in parallel (below), then read your digests, then go back to the original
   for the exact numbers and quotes you will put on slides.
4. Cite as you go: page anchors (`p. 8`), timestamps (`[00:12:31]`) or chapters for every claim you keep.

## Long-source protocol (books, long recordings)

When `chunks/` exists, spawn one subagent per chunk (in parallel; a smaller, faster model such as
Sonnet is ideal for this — keep storyline and design for the main model). A chunk that starts
mid-chapter opens with a `<!-- continues: chapter › section · last anchor -->` line, so each agent knows
where it is. Prompt:

```
Read <absolute path to chunk-NN.md>. It is part NN of MM of <title> by <author>.
Anchor every item to a page number or timestamp when the text has them, otherwise to the chapter
heading it falls under; the chunk's first line says where it starts.
Return markdown, ≤ 600 words:
1. Main claims of this part (one sentence each, with anchors).
2. Evidence: numbers (with units and anchors), named examples, experiments or studies.
3. 2–4 quotable lines (verbatim, ≤ 30 words, with anchors).
4. Terms a general audience would need defined.
5. Figures/tables worth redrawing (anchors; describe them if the images are missing).
Do not interpret beyond the text. Do not write files.
```

Save each result to `decks/<slug>/source/digest/chunk-NN.md`, then synthesise. If an agent stops early
(rate limit, timeout), resume that same agent instead of starting a new one — its reading is kept.

## Media notes

- **ffmpeg**: used from PATH if present (`brew install ffmpeg`); otherwise the script borrows the
  static binary inside the `imageio-ffmpeg` wheel automatically — no install needed.
- **Transcription backends**, first that works: mlx-whisper (Apple Silicon, via uvx) → whisper.cpp
  (`whisper-cli`, if installed with its model at `~/.cache/whisper.cpp/ggml-large-v3-turbo.bin`) →
  faster-whisper (CPU, via uvx). The first run downloads the model (large-v3-turbo ≈ 1.6 GB).
- **YouTube** runs `uvx --from "yt-dlp[default,curl-cffi]" yt-dlp` with Node as its JavaScript runtime.
  It asks for exactly one subtitle track: requesting many (YouTube offers ~150 machine translations)
  trips HTTP 429 and loses the good track too. TED/TEDx subtitle credits (“Translator: … Reviewer: …”)
  are moved out of the text into `transcript.credit`.
- **Keyframes** of a single-camera talk mostly show the speaker; scene detection alone may find only
  the title cards, so the script also takes one frame every 45 s. A 480p video gives 854 px frames:
  frame them in a split, never full-bleed.
- Speaker names are not detected. If the talk has several speakers, say so in the storyline and
  attribute quotes carefully.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No transcription backend worked` | check network for the first model download; try `--model mlx-community/whisper-small`; or `brew install ffmpeg whisper-cpp` |
| Garbled CJK in a PDF | it is a scanned PDF — use `--pdf-engine docling` (OCR) |
| Wrong reading order (multi-column) | `--pdf-engine docling` |
| YouTube "sign in to confirm" | the video is age/region-restricted; ask the user for a local file |
| YouTube HTTP 429 on subtitles | the script retries twice; if it still fails, wait a few minutes and re-run (or `--no-frames` to make fewer requests) |
| `keyframes skipped` / HTTP 403 on the video stream | transient throttling after repeated downloads: the script retries with an HLS stream; if both fail, the transcript is still complete — re-run later for frames |
| Transcript in Simplified Chinese | pass `--lang zh-TW` (Mandarin recordings only) |
| Transcript of an English talk came out as Chinese | `--lang` names the spoken language — drop `--lang zh-TW` |
| EPUB citations look like `p. 87` | EPUBs have no printed pages unless the manifest says so — cite chapters |
