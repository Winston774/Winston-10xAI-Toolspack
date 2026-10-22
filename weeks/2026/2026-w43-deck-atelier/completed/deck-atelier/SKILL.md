---
name: deck-atelier
description: Turn any source material — PDF papers, books (EPUB/MOBI), Word/PowerPoint/Excel files, web articles, YouTube links, local video or audio recordings — into a stage-ready presentation with design-consultancy polish (McKinsey-grade storyline, one of ten committed visual styles — Swiss grid, press poster, technical lab, Japanese magazine, Kinfolk, dopamine colour, glitch, Bauhaus geometric, postmodern Memphis, risograph — never the generic AI look — bespoke SVG diagrams and charts, speaker notes), then optionally choreograph it into an elegant motion deck (luxury-landing-page reveals, parallax slide transitions, shared-element "magic move", restrained ambient motion). Output is a single offline HTML deck with presenter console, in-browser editing and PDF export; slide count can be specified. Use this skill whenever the user wants slides, a deck, a presentation, a talk, a keynote, 簡報, 投影片, 報告, 上台, 講稿 or "make this into a presentation" from any material; when they ask to summarize a paper/book/video/recording for an audience; to add animation or transitions to a deck (動態簡報, 動畫, 轉場); or to edit, restyle, shorten or lengthen a deck made with it — even if they never say "HTML".
---

# Deck Atelier · 簡報工坊

Two crafts in one workflow:

- **Part 1 — Compose.** Source → storyline → a static deck that reads like a design consultancy's
  final client presentation: one message per slide, full-sentence action titles, a committed visual
  style with strong typography, diagrams drawn for this content, every number sourced.
- **Part 2 — Choreograph.** The same deck, with motion that feels like a fashion house's landing page:
  text that settles into place, diagrams that draw themselves, slides that hand over to each other
  with light parallax, objects that persist from one slide to the next. Never flashy.

The deck is one HTML file per variant (fonts embedded, works offline, 1920×1080 canvas scaled to any
screen). Presenters get keyboard/clicker control, builds, a presenter console with notes and timer,
an overview grid, ten visual styles each with light and dark themes (switchable live), and an edit
mode that saves back to the file.

The finished sample in `examples/attention/` (the "Attention Is All You Need" paper, 15 slides:
`deck.html`, its `storyline.md`, and `gen_figs.py` that generates its computed figures) is the quality
bar. When in doubt about how something should look or be marked up, open that `deck.html`. (Its
`<span class="nw">` wrappers predate automatic phrase breaks; new decks don't need them.)

## Deliverables

For a deck slug `<slug>` (kebab-case of the topic), everything lives in `decks/<slug>/`:

| File | What it is |
|---|---|
| `deck.html` | the editable source — the single file you write and edit |
| `engine/` | a copy of the runtime (atelier.css / atelier.js) the source links to |
| `source/` | ingested material: `source.md`, `manifest.json`, `pages/`, `figures/`, `frames/`, `chunks/` |
| `storyline.md` | the ghost deck: audience, governing thought, SCQA, slide-by-slide action titles |
| `dist/<slug>.html` | **Part 1**: static deck, single file, offline |
| `dist/<slug>-motion.html` | **Part 2**: motion deck, single file, offline |
| `dist/<slug>.pdf` | handout / backup (static, one slide per page) |
| `qa/` | screenshots, contact sheets and filmstrips from the QA loop |

## Settle the brief (ask only what you cannot infer)

| Setting | Default when the user doesn't say |
|---|---|
| Audience & occasion | educated non-specialists; a 15–20 minute talk |
| Language | the user's language. Traditional Chinese (Taiwan) keeps English technical terms (Transformer, Query) |
| Slide count | ≈ 1 slide per spoken minute; 12–16 for 20 minutes. If the user names a number, deliver exactly that number |
| Style | by the content's character, then the room — `swiss` (default), `press`, `lab`, `tokyo` 日式雜誌, `kinfolk`, `dopamine` 多巴胺, `glitch`, `geometric` 幾何抽象, `postmodern` 後現代, `riso` 孔版. Catalogue and how to choose: layouts.md §0. If the user named a style or a feel (「日系」「繽紛」「科技感」), map it; if the choice matters and they're around, show a gallery of candidates first |
| Theme | `light`; `dark` for dark rooms / LED walls |
| Motion | build Part 1 first; do Part 2 when asked, or when the request mentions motion/動態/animation |

If the request is clear enough to start, start. Put the assumptions you made in your final message.

## Workflow

Scripts live in this skill's `scripts/` folder (paths below are relative to the skill directory; run
them from the project root with the full path). They need Node 18+ and `uv`; snapshot/PDF need Chrome.

### 0 · Scaffold

```bash
node scripts/new_deck.mjs decks/<slug> --title "Deck title" --lang zh-Hant-TW --style swiss
```

Creates `deck.html` from the starter (with that style's fonts), copies the engine, makes `source/`.
`--styles` lists the styles. A style can change later with `scripts/set_style.mjs`, but every slide
is designed and QA'd in one style — re-run QA after a switch.

To let the user choose by eye, render their deck (or the starter) in several styles at once:

```bash
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa/styles --styles all --slides 1,2,6
```

`qa/styles/gallery.png` has one row per style (needs internet: each style's fonts load from Google
Fonts). Show it to the user and let them pick.

### 1 · Ingest → `source/`

```bash
uv run scripts/ingest.py <file-or-url> [more…] --out decks/<slug>/source
```

PDFs, EPUB/MOBI, DOCX/PPTX/XLSX/HTML, web URLs, YouTube (subtitles first), audio and video
(transcribed with timestamps; video and YouTube also yield keyframes). `--lang` is the language
*spoken in the recording* (`zh-TW` for Mandarin), not the deck's: for an English talk going into a
Chinese deck, leave it out. Read `references/ingest.md` for options, the long-source protocol, and
troubleshooting. Then read `source/manifest.json` (it says how far to trust the transcript and how to
cite: pages, timestamps, or chapters when an EPUB has no page numbers) and `source.md`. For short
documents also look at a few `pages/*.png` — figures in papers are usually vector drawings that only
show up in page renders; for video, `frames/contact.jpg` shows every keyframe at once. Copy what you use
into `assets/` — re-running ingest rebuilds `source/`.

**Long sources** (a `chunks/` folder appears — books, hour-long talks): digest the chunks in parallel
with subagents running a smaller, faster model (for example Sonnet), one chunk each, using the prompt in
`references/ingest.md`. Keep the storyline, writing and design work for yourself — that is where
judgment matters.

### 2 · Distill

Before any slide exists, extract into your notes: the governing thought (the one sentence the audience
should leave with), the 3–5 claims that support it, the evidence for each (numbers *with units and
page/timestamp references*), memorable quotes, the figures worth redrawing, and the terms the audience
needs defined. Verify every number against the source text; do not round in ways that change claims.

### 3 · Storyline → `storyline.md`

Write the ghost deck: one line per slide = its action title, plus the layout and the visual you
intend. Reading the titles alone, top to bottom, must tell the whole story. Method, title rules,
how to plan exactly N slides, and source-type templates (paper, book, talk, report) are in
`references/narrative.md` — read it every time; it is the difference between a summary and a talk.

If the user is around and the deck is substantial, show them the ghost deck before composing. A
two-minute check here saves an hour of rework.

### 4 · Compose → `deck.html` (Part 1)

- Commit to the style (layouts.md §0) and stay inside its voice. Deck-specific CSS uses role tokens
  (`var(--f-head)`, `var(--w-fig)`, `var(--accent)`, `var(--bar)`…), never font names or hex values,
  so the slide renders in every style and theme.
- Pick each slide's layout from `references/layouts.md` (cover, statement, summary points, agenda,
  split text+figure, exhibit, formula, comparison table, stats, timeline, quote, closing). Vary them —
  a deck where every slide has the same skeleton reads as a template.
- Draw visuals as inline SVG with the diagram vocabulary in `references/diagrams.md`. A diagram built
  for *this* idea beats any stock image. Charts follow the exhibit rules there (one highlighted series,
  direct labels, hairline grid, source line). Repetitive geometry (heatmaps, waves, arcs, scatter
  coordinates) is generated by a small script into `<!--gen:name--><!--/gen-->` regions — see
  diagrams.md.
- Images only when they carry meaning (a person, a place, an artifact, a frame from the talk);
  sourcing and credit rules are in diagrams.md.
- Every slide gets `<aside class="notes">`: what to say in 2–4 short paragraphs, `（下一步）` /
  "(next)" where a build advances, and a time hint.
- Every data or quoted slide gets a `<p class="source">` line.
- Typography for Chinese: write plain text. The build makes line breaks phrase-aware on its own
  (BudouX phrases confirmed by ICU word boundaries → `<wbr>`), so words like 注意力 never split
  across lines. Reach for `<span class="nw">…</span>` only as a manual override where a break still
  lands badly; avoid widows (1–3 characters alone on a last line). Details in layouts.md.

### 5 · QA loop (static)

```bash
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa --check --slides 1-99
```

Prints a layout lint (overflow, outside safe area, tiny text, fonts not loaded) and writes one PNG per
slide plus `qa/sheet.png`. Fix every lint issue, then *look* at the sheet and at each slide at full
size — the lint cannot see awkward line breaks, crowded labels or weak hierarchy. Iterate until a
design director would sign it off. Checklist in `references/qa.md`. Chinese line breaks here match
the build's: the snapshot renders a temporary copy of `deck.html` with the same phrase breaks (needs
`uv`; a `phrase` entry in the report confirms they ran), so judge breaks and overflow right here.

### 6 · Build

```bash
node scripts/build.mjs decks/<slug>/deck.html
node scripts/snapshot.mjs decks/<slug>/dist/<slug>.html --out decks/<slug>/qa/pdf --pdf decks/<slug>/dist/<slug>.pdf --slides 1
```

Build inlines the engine, images and a glyph-subset of the Google Fonts actually used (~1 MB for a
CJK deck), adds phrase-aware line breaks to CJK text (needs `uv`; `--no-phrase` skips them; the log
line `phrase breaks: N <wbr> …` confirms they ran), and writes the static and motion variants. Run
the lint once more on `dist/<slug>.html` with `--slides 1-99` and look at the line breaks there.

### 7 · Choreograph (Part 2)

Add motion as *annotations* in `deck.html` — the static build ignores them, so one source serves both
parts. Grammar, default timings, recipes and the restraint rules are in `references/motion.md`:

- builds: `data-step="1|2|3"` on the elements a click should reveal (and `.slide[data-at="k"]` CSS
  for emphasis that follows the build)
- continuity: the same `data-morph="key"` on an element in consecutive slides makes it glide across
- diagrams: `data-draw` / `data-pop` / `data-fade` with millisecond offsets to sequence an SVG
- rhythm: `data-tone="invert"` slides arrive with a curtain wipe; `data-transition` overrides
- life: at most one meaningful `data-ambient` loop on a slide (drift, breathe, a sequence light)

Verify with filmstrips, then rebuild:

```bash
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa/film --film <N> --at 0,160,360,620,950,1500
node scripts/snapshot.mjs decks/<slug>/deck.html --out decks/<slug>/qa/steps --steps --slides <N>
```

### 8 · Deliver

Tell the user, briefly: where the files are, how to present (open `dist/<slug>-motion.html` or
`dist/<slug>.html` in Chrome, press F for fullscreen, S for the presenter console), how to edit, and
which assumptions you made (audience, length, illustrative values, anything you could not verify).

## Editing and resizing

- **Small text edits by the user**: press E in the browser, click any text, edit, ⌘S / Ctrl+S. Chrome
  and Edge save in place (on the first save they ask which file); other browsers download a copy.
  Editing the *source* `deck.html` (served or opened locally) is best; then rebuild. In a built deck,
  an element whose text is edited drops its phrase breaks (it wraps per character) until rebuilt.
- **Edits through you**: change `deck.html` directly, re-run QA on the touched slides, rebuild.
- **Different slide count**: re-plan in `storyline.md` first (narrative.md → "Planning exactly N
  slides"), then add, merge or retire slides. Never hit a number by shrinking fonts or cramming.
- **Restyle**: `node scripts/set_style.mjs decks/<slug>/deck.html --style tokyo [--theme dark]`
  switches `data-style`, the font link and (if needed) the deck's engine copy; then re-run QA and
  rebuild. Y / T preview styles and themes live. For a different accent, set it in the deck's
  `<style>` block (layouts.md §1). Styles and tokens live in `engine/atelier.css`, the style
  registry (names, fonts, preferred theme) at the top of `engine/atelier.js`.
- **Old decks** (made before the styles existed: cream paper, serif, `data-theme="ivory"`) keep
  their own engine copy and look as they did. To move one to the new look: `new_deck.mjs <dir>
  --update-engine`, swap its font `<link>` for the starter's, add `data-style`, and replace
  `var(--f-display)` / `var(--f-serif)` italics in its `<style>` with role tokens (layouts.md §2).

## Presenter controls (tell the user)

| Key | Action |
|---|---|
| → ↓ Space PgDn, click | next build / next slide (clickers work) |
| ← ↑ PgUp | previous build / previous slide |
| number + Enter | jump to slide |
| G or Esc | overview grid |
| F | fullscreen |
| S | presenter console in a new window: current + next slide, notes, timer (R resets) |
| M | motion on/off (Part 2 ↔ Part 1 behaviour, live) |
| T | light / dark theme |
| Y / Shift+Y | next / previous of the ten styles (preview; the file keeps its own `data-style`) |
| E | edit text; ⌘S / Ctrl+S saves |
| B or . | black screen |
| ? | shortcut help |

For presenting from a local file, Chrome or Edge is recommended. `?motion=off`, `?theme=dark`,
`?style=tokyo` and `#7` in the URL also work.

## Why it looks designed — and not machine-made (keep these when improvising)

- **One idea per slide, stated as a sentence.** Titles carry the argument; the body proves it.
- **A committed style.** Each of the ten styles has a palette, a type pairing and a few signature
  devices (swiss's colour fields, press's highlighter, tokyo's vertical running head and 傍點,
  dopamine's colour dots, glitch's RGB split, riso's misregistration…). Pick one per deck and push
  it; a half-committed style reads as a template. Don't mix two styles' devices on one deck.
- **Contrast in scale and weight.** Huge bold figures next to small labels; heavy structural rules
  (`--bar`) above hairline details. Hierarchy comes from size and weight, not from decoration.
- **One accent, used only for the point**; ink and greys for everything else. Colour fields
  (inverted slides) mark chapter turns.
- **Bespoke exhibits.** Draw the mechanism itself (arcs between words, a heatmap per head, the actual
  architecture) rather than generic icons. Label directly; cite sources.
- **Rhythm.** Alternate dense evidence slides with breathing slides (a statement, a chapter turn on a
  colour field). Change layout family every one or two slides.
- **Motion with intent.** Every movement either reveals in reading order, shows causality, or keeps an
  object's identity across slides. If it does none of these, cut it.

**Avoid the default "AI deck" look** — the user will recognise it instantly:
- warm cream / beige paper with a terracotta, clay or coral accent (an AI assistant's own palette);
- light serif display type, italic serif glosses and numerals (Instrument Serif, Playfair, Fraunces,
  Noto Serif TC everywhere) as a default rather than a chosen style, small tracked uppercase labels
  with a thin accent dash before each;
- generic SaaS: purple–blue gradients, soft rounded cards with drop shadows, glassmorphism, emoji or
  stock icons, Inter for everything;
- decoration standing in for hierarchy: badges, pills and boxes around text that needs none.
If a slide drifts toward any of these, return to the style's own tokens and signatures.

## Files in this skill

| Path | Read when |
|---|---|
| [references/narrative.md](references/narrative.md) | every deck — storyline, titles, copy rules, planning N slides |
| [references/layouts.md](references/layouts.md) | composing — choosing a style, design tokens, layout catalog with markup, CJK typography |
| [references/diagrams.md](references/diagrams.md) | drawing diagrams/charts, generating SVG, finding and crediting images |
| [references/motion.md](references/motion.md) | Part 2 — attribute grammar, timings, recipes, anti-patterns |
| [references/ingest.md](references/ingest.md) | any non-trivial source, long sources, media, troubleshooting |
| [references/qa.md](references/qa.md) | before calling any deck done |
| `scripts/new_deck.mjs` | scaffold a deck folder |
| `scripts/ingest.py` | sources → `source/` (uv resolves its dependencies) |
| `scripts/set_style.mjs` | switch a deck's style (attribute, font link, engine copy); `--list` |
| `scripts/styles.mjs` | reads the style registry from the engine (used by the other scripts) |
| `scripts/build.mjs` | `deck.html` → single-file static + motion decks with subset fonts and phrase-aware CJK line breaks |
| `scripts/phrase.mjs` | the phrase-break pass shared by `build.mjs` and `snapshot.mjs` (not run by hand) |
| `scripts/phrase.py` | BudouX phrase boundaries for `phrase.mjs` (called through `uv`; not run by hand) |
| `scripts/snapshot.mjs` | screenshots, contact sheet, lint, filmstrips, build steps, PDF; `--style` / `--styles` galleries |
| `assets/engine/` | the runtime: `atelier.css` (design system: ten styles × light / dark) and `atelier.js` (presentation engine + style registry) |
| `assets/templates/starter.html` | starting point copied by `new_deck.mjs` |
| `examples/attention/` | the reference deck: source markup, storyline, figure generator |
