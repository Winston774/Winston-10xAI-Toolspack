#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.24",
#   "pymupdf4llm>=0.0.17",
#   "markitdown[docx,pptx,xlsx]>=0.1.1",
#   "opencc-python-reimplemented>=0.1.7",
# ]
# ///
"""
deck-atelier · ingest
Turn any source into a normalized Markdown digest that the storyline step can read.

  uv run scripts/ingest.py <source> [<source> ...] --out <deck>/source

Sources
  documents  .pdf .epub .mobi .fb2 .docx .pptx .xlsx .html .htm .md .txt
  web        http(s) URLs (articles) · YouTube URLs (one subtitle track: human subtitles in the spoken
             language first, else its speech-recognition captions, else transcription; plus keyframes)
  media      audio .mp3 .m4a .wav .aiff .flac .ogg · video .mp4 .mov .mkv .webm .m4v

--lang is the language SPOKEN in the recording (zh-TW = Mandarin, written in Taiwan Traditional), not
the language of the deck. An English talk for a Taiwanese audience: omit it (or --lang en).

Writes into --out (generated folders are replaced on every run)
  source.md       one Markdown file, front matter + text with <!-- page N --> or [hh:mm:ss] anchors,
                  chapter headings (book TOC, YouTube chapters); Project Gutenberg boilerplate removed
  pages/          PNG renders of document pages (short documents only — for figure hunting)
  figures/        images worth reusing: PDF rasters >= 360 px, EPUB images >= 300 px, EPUB cover
  frames/         video keyframes (scene changes + one every 45 s) named by timestamp, contact.jpg
  chunks/         ~N-word chunks for long sources (books, long talks) to digest in parallel
  translation-<lang>.md   YouTube only: a human translation in --lang, when one exists
  manifest.json   machine-readable summary: sizes, TOC, licence, transcript provenance, how to cite

Media needs ffmpeg on PATH (brew install ffmpeg). Transcription backends, first available wins:
mlx-whisper (Apple Silicon, via uvx) → whisper.cpp (whisper-cli) → faster-whisper (via uvx).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DOC_EXT = {".pdf", ".epub", ".mobi", ".fb2", ".xps", ".cbz"}
OFFICE_EXT = {".docx", ".pptx", ".xlsx", ".html", ".htm"}
TEXT_EXT = {".md", ".markdown", ".txt"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".aiff", ".aif", ".flac", ".ogg", ".opus", ".aac"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
YOUTUBE = re.compile(r"(youtube\.com/|youtu\.be/)", re.I)


def log(msg: str) -> None:
    print(f"· {msg}", file=sys.stderr)


def words_of(text: str) -> int:
    """Count words the way a reader would: CJK characters count one each, Latin by whitespace."""
    cjk = len(re.findall(r"[㐀-鿿豈-﫿]", text))
    latin = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))
    return cjk + latin


def stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


# ───────────────────────────── documents ─────────────────────────────

def docling_markdown(path: Path) -> str:
    """Convert with docling (MIT, heavier, better on complex layouts/tables). Runs via uvx, no install."""
    work = Path(tempfile.mkdtemp(prefix="docling-"))
    run(["uvx", "--from", "docling", "docling", str(path), "--to", "md", "--output", str(work)])
    md = next(work.glob("*.md")).read_text(encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    return md


def ingest_document(path: Path, out: Path, render_pages: int, engine: str = "pymupdf") -> dict:
    import pymupdf  # noqa: WPS433

    doc = pymupdf.open(path)
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    parts: list[str] = []

    toc = doc.get_toc(simple=True)
    if path.suffix.lower() == ".pdf" and engine == "docling":
        parts = [docling_markdown(path)]
    elif path.suffix.lower() == ".pdf":
        try:
            import pymupdf4llm

            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)
            for i, chunk in enumerate(chunks, start=1):
                parts.append(f"<!-- page {i} -->\n{chunk['text'].strip()}\n")
        except Exception as exc:  # pragma: no cover - layout fallback
            log(f"pymupdf4llm failed ({exc}); falling back to plain text")
            parts = [f"<!-- page {i} -->\n{p.get_text('text').strip()}\n" for i, p in enumerate(doc, start=1)]
    else:
        # Other page-based formats (XPS, CBZ): stitch pages, inject chapter headings from the TOC.
        starts = {}
        for level, title, page in toc:
            if page >= 1 and level <= 2:
                starts.setdefault(page, []).append(("#" * (level + 1)) + " " + title.strip())
        for i, page in enumerate(doc, start=1):
            head = "\n".join(starts.get(i, []))
            # one paragraph per text block (raw "text" mode keeps the renderer's line wraps)
            body = "\n\n".join(join_lines(b[4]) for b in page.get_text("blocks") if b[6] == 0 and b[4].strip())
            if head or body:
                parts.append(f"<!-- page {i} -->\n{head}\n{body}\n".replace("\n\n\n", "\n\n"))

    # Page renders help find vector figures (diagrams are rarely embedded rasters).
    pages_dir = out / "pages"
    rendered = 0
    if render_pages and doc.page_count and path.suffix.lower() == ".pdf":
        pages_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(doc, start=1):
            if i > render_pages:
                break
            page.get_pixmap(dpi=110).save(pages_dir / f"page-{i:03d}.png")
            rendered += 1

    # Embedded rasters worth reusing as imagery.
    fig_dir = out / "figures"
    figures = []
    seen = set()
    for pno, page in enumerate(doc, start=1):
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                data = doc.extract_image(xref)
            except Exception:
                continue
            w, h = data.get("width", 0), data.get("height", 0)
            if min(w, h) < 360:
                continue
            fig_dir.mkdir(parents=True, exist_ok=True)
            name = f"p{pno:03d}-x{xref}.{data.get('ext', 'png')}"
            (fig_dir / name).write_bytes(data["image"])
            figures.append({"file": f"figures/{name}", "page": pno, "width": w, "height": h})

    text = "\n".join(parts)
    heading = re.search(r"^#{1,2}\s+\**(.+?)\**\s*$", text, re.M)
    reflow = path.suffix.lower() != ".pdf"
    return {
        "kind": path.suffix.lower().lstrip("."),
        **({"page_numbers": "reflowed by the converter, not the printed edition: cite chapters"} if reflow else {}),
        "title": meta.get("title") or (heading.group(1).strip() if heading else path.stem),
        "author": meta.get("author", ""),
        "pages": doc.page_count,
        "toc": [{"level": l, "title": t, "page": p} for l, t, p in toc],
        "text": text,
        "assets": {"pages": rendered, "figures": figures},
    }


CJK = r"[　-〿㐀-鿿豈-﫿＀-￯]"


def join_lines(block: str) -> str:
    """Undo hard line wraps inside one paragraph: a space between Latin words, nothing between CJK."""
    lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
    out = lines[0] if lines else ""
    for l in lines[1:]:
        if out.endswith("-") and not out.endswith("--") and re.match(r"[a-z]", l):
            out = out[:-1] + l          # re-join a hyphenated word
        elif re.search(CJK + "$", out) and re.match(CJK, l):
            out += l
        else:
            out += " " + l
    return out


def unwrap_markdown(md: str) -> str:
    """Join soft-wrapped lines of plain paragraphs; leave headings, lists, tables, quotes, code alone."""
    blocks = re.split(r"\n\s*\n", md)
    keep = re.compile(r"^\s*(#|\||>|[-*+] |\d+[.)] |```|<!--|!\[)")
    return "\n\n".join(b if any(keep.match(l) for l in b.splitlines()) else join_lines(b) for b in blocks if b.strip())


GUTENBERG_START = re.compile(r"^.*\\?\*\\?\*\\?\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG E-?BOOK.*$", re.M | re.I)
GUTENBERG_END = re.compile(r"^.*\\?\*\\?\*\\?\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG E-?BOOK.*$", re.M | re.I)


def strip_boilerplate(text: str) -> tuple[str, dict]:
    """Remove Project Gutenberg's header and licence (≈ 3,500 words that are not the book); keep the
    edition facts from the header (editor, translator, release date) for the manifest."""
    facts = {}
    start, end = GUTENBERG_START.search(text), GUTENBERG_END.search(text)
    if start:
        for k, v in re.findall(r"\*\*(Title|Author|Editor|Translator|Illustrator|Release date|Original publication)\*\*\s*:\s*(.+)", text[:start.start()]):
            facts[k.lower()] = v.strip()
        text = text[start.end():]
    end = GUTENBERG_END.search(text)
    if end:
        text = text[:end.start()]
    return text.strip(), facts


_PAGEBREAK = re.compile(r"<(span|div|a|p)\b[^>]*(?:epub:type=\"pagebreak\"|role=\"doc-pagebreak\"|class=\"pagenum[^\"]*\")[^>]*?(?:/>|>.*?</\1>)", re.S)
_IMG = re.compile(r"<(?:img|image)\b[^>]*?(?:\bsrc|xlink:href|\bhref)=\"([^\"]+)\"[^>]*>", re.S)


def ingest_epub(path: Path, out: Path) -> dict:
    """EPUB in reading order (OPF spine) through markitdown's HTML converter: real paragraphs and
    headings, print-page anchors when the book carries page-break markers, figures saved where they
    appear, Project Gutenberg boilerplate removed."""
    import io
    import posixpath
    import zipfile
    from xml.etree import ElementTree as ET

    import pymupdf
    from markitdown import MarkItDown

    z = zipfile.ZipFile(path)
    opf_path = ET.fromstring(z.read("META-INF/container.xml")).find(".//{*}rootfile").get("full-path")
    opf = ET.fromstring(z.read(opf_path))
    base = posixpath.dirname(opf_path)
    items = {i.get("id"): i for i in opf.findall(".//{*}item")}
    dc = lambda tag: [e.text.strip() for e in opf.iter(f"{{http://purl.org/dc/elements/1.1/}}{tag}") if e.text]
    md = MarkItDown(enable_plugins=False)
    fig_dir = out / "figures"
    figures, seen, parts = [], {}, []

    def save_image(src: str, doc_dir: str, alt: str, role: str = "figure") -> str | None:
        name = posixpath.normpath(posixpath.join(doc_dir, src.split("#")[0]))
        if name in seen:
            return seen[name]
        try:
            data = z.read(name)
            pix = pymupdf.Pixmap(data)
            w, h = pix.width, pix.height
        except Exception:
            return None
        if max(w, h) < 300:          # rules, ornaments, drop caps
            return None
        fig_dir.mkdir(parents=True, exist_ok=True)
        file = f"figures/{role if role == 'cover' else f'fig-{len(figures) + 1:03d}'}{Path(name).suffix.lower()}"
        (out / file).write_bytes(data)
        figures.append({"file": file, "role": role, "alt": alt, "width": w, "height": h})
        seen[name] = file
        return file

    cover_id = next((m.get("content") for m in opf.findall(".//{*}meta") if m.get("name") == "cover"), None)
    cover = items.get(cover_id) if cover_id in items else \
        next((i for i in items.values() if "cover-image" in (i.get("properties") or "")), None)
    if cover is not None and cover.get("media-type", "").startswith("image/"):
        save_image(cover.get("href"), base, "cover", role="cover")

    for ref in opf.findall(".//{*}itemref"):
        item = items.get(ref.get("idref"))
        if item is None or item.get("media-type") not in ("application/xhtml+xml", "text/html"):
            continue
        href = posixpath.normpath(posixpath.join(base, item.get("href")))
        doc_dir = posixpath.dirname(href)
        html = z.read(href).decode("utf-8", "replace")

        def page_mark(m: re.Match) -> str:
            tag = m.group(0)
            n = (re.search(r"(?:title|aria-label)=\"(?:page\s*)?([\w.-]+)\"", tag, re.I)
                 or re.search(r"\[(?:Pg\.?|p\.)?\s*([\w.-]+)\]", tag)
                 or re.search(r"id=\"(?:page|pg|p)[_-]?([\w.-]+)\"", tag, re.I))
            return f" @@PAGE {n.group(1)}@@ " if n else " "

        def img_mark(m: re.Match) -> str:
            alt = re.search(r"\balt=\"([^\"]*)\"", m.group(0))
            file = save_image(m.group(1), doc_dir, alt.group(1).strip() if alt else "")
            return f"<p>@@FIG {file}|{alt.group(1).strip() if alt else ''}@@</p>" if file and "cover" not in file else ""

        html = _IMG.sub(img_mark, _PAGEBREAK.sub(page_mark, html))
        text = md.convert_stream(io.BytesIO(html.encode("utf-8")), file_extension=".html").text_content
        parts.append(text)

    text = "\n\n".join(parts)
    text, facts = strip_boilerplate(text)
    text = re.sub(r"\s*@@PAGE ([\w.-]+)@@\s*", lambda m: f"\n\n<!-- page {m.group(1)} -->\n\n", text)
    text = re.sub(r"@@FIG ([^|@]+)\|([^@]*)@@", lambda m: f"![{m.group(2) or 'figure'}]({m.group(1)})", text)
    text = unwrap_markdown(text)
    # where each figure sits: the nearest heading above it
    for f in figures:
        at = text.find(f"]({f['file']})")
        heads = re.findall(r"^#{1,6}\s+(.+)$", text[:max(at, 0)], re.M) if at >= 0 else []
        f["chapter"] = heads[-1].strip() if heads else ""
    printed = "<!-- page " in text

    toc = []
    nav = next((i for i in items.values() if "nav" in (i.get("properties") or "").split()), None)
    if nav is not None:
        doc = ET.fromstring(z.read(posixpath.normpath(posixpath.join(base, nav.get("href")))))
        def walk(ol, level):
            for li in ol.findall("{*}li"):
                a = li.find("{*}a") if li.find("{*}a") is not None else li.find("{*}span")
                if a is not None and "".join(a.itertext()).strip() and "GUTENBERG" not in "".join(a.itertext()).upper():
                    toc.append({"level": level, "title": " ".join("".join(a.itertext()).split())})
                sub = li.find("{*}ol")
                if sub is not None:
                    walk(sub, level + 1)
        toc_nav = next((n for n in doc.findall(".//{*}nav") if "toc" in (n.get("{http://www.idpf.org/2007/ops}type") or "")), None)
        if toc_nav is not None and toc_nav.find("{*}ol") is not None:
            walk(toc_nav.find("{*}ol"), 1)

    return {
        "kind": "epub",
        "title": (dc("title") or [path.stem])[0],
        "author": ", ".join(dc("creator")),
        **({"edition": facts} if facts else {}),
        "page_numbers": "printed edition (<!-- page N --> anchors)" if printed else "none in this EPUB: cite chapter titles",
        "toc": toc,
        "text": text,
        "assets": {"figures": figures},
    }


def ingest_office(src: str) -> dict:
    from markitdown import MarkItDown

    result = MarkItDown(enable_plugins=False).convert(src)
    title = getattr(result, "title", None) or Path(src.split("?")[0]).stem
    return {"kind": Path(src.split("?")[0]).suffix.lstrip(".") or "web", "title": title,
            "text": result.text_content, "assets": {}}


def ingest_text(path: Path) -> dict:
    return {"kind": "text", "title": path.stem, "text": path.read_text(encoding="utf-8", errors="replace"),
            "assets": {}}


# ───────────────────────────── media ─────────────────────────────

_FFMPEG: str | None = None


def need_ffmpeg() -> str:
    """ffmpeg from PATH, else the static binary bundled in the imageio-ffmpeg wheel (no install).
    The fallback is also linked as `ffmpeg` on PATH so transcription tools that shell out find it."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    exe = shutil.which("ffmpeg")
    if not exe and shutil.which("uvx"):
        try:
            out = subprocess.run(["uvx", "--from", "imageio-ffmpeg", "python", "-c",
                                  "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                                 check=True, text=True, capture_output=True).stdout.strip()
            shim = Path(tempfile.mkdtemp(prefix="ffmpeg-shim-"))
            (shim / "ffmpeg").symlink_to(out)
            os.environ["PATH"] = f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"
            exe = str(shim / "ffmpeg")
            log(f"using bundled ffmpeg from imageio-ffmpeg ({out})")
        except Exception as exc:
            log(f"imageio-ffmpeg fallback failed: {exc}")
    if not exe:
        sys.exit("ffmpeg is required for audio/video. Install it with:  brew install ffmpeg")
    _FFMPEG = exe
    return exe


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log(" ".join(cmd[:6]) + (" …" if len(cmd) > 6 else ""))
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)
    except subprocess.CalledProcessError as exc:
        tail = "\n".join(l for l in (exc.stderr or "").splitlines() if l.strip() and not l.startswith("WARNING"))[-600:]
        log(f"{' '.join(cmd[:3])} failed (exit {exc.returncode}): {tail or 'no output'}")
        raise


TRADITIONAL = {"zh-tw", "zh-hant", "zh-hant-tw", "tw", "zh-hk", "zh-hant-hk"}


def whisper_lang(lang: str | None) -> str | None:
    return "zh" if lang and lang.lower() in TRADITIONAL else lang


def to_traditional(segs: list[dict], lang: str | None) -> list[dict]:
    """Whisper writes Simplified Chinese for "zh"; convert to Taiwan Traditional with phrase mapping."""
    if not lang or lang.lower() not in TRADITIONAL:
        return segs
    from opencc import OpenCC

    cc = OpenCC("s2twp" if "tw" in lang.lower() else "s2hk")
    return [{**s, "text": cc.convert(s["text"])} for s in segs]


PROMPT_HINT = ""  # set from --prompt: names and jargon the recording uses


def transcribe(audio: Path, work: Path, lang: str | None, model: str | None) -> list[dict]:
    """Return [{start, end, text}] using the first transcription backend that works."""
    base = "以下是繁體中文的逐字稿。" if lang and lang.lower() in TRADITIONAL else ""
    prompt = " ".join(filter(None, [base, PROMPT_HINT])) or None
    segs = _transcribe(audio, work, whisper_lang(lang), model, prompt)
    return to_traditional(segs, lang)


def _transcribe(audio: Path, work: Path, lang: str | None, model: str | None, prompt: str | None) -> list[dict]:
    wav = work / "audio16k.wav"
    run([need_ffmpeg(), "-y", "-i", str(audio), "-ac", "1", "-ar", "16000", str(wav)])

    attempts = []
    if shutil.which("uvx") and sys.platform == "darwin":
        m = model or "mlx-community/whisper-large-v3-turbo"
        cmd = ["uvx", "--from", "mlx-whisper", "mlx_whisper", str(wav), "--model", m,
               "--output-format", "json", "--output-dir", str(work), "--verbose", "False"]
        if lang:
            cmd += ["--language", lang]
        if prompt:
            cmd += ["--initial-prompt", prompt]
        attempts.append(("mlx-whisper", cmd, work / "audio16k.json"))
    if shutil.which("whisper-cli"):
        m = model or str(Path.home() / ".cache/whisper.cpp/ggml-large-v3-turbo.bin")
        cmd = ["whisper-cli", "-m", m, "-f", str(wav), "-oj", "-of", str(work / "wcpp")]
        if lang:
            cmd += ["-l", lang]
        if prompt:
            cmd += ["--prompt", prompt]
        attempts.append(("whisper.cpp", cmd, work / "wcpp.json"))
    if shutil.which("uvx"):
        code = (
            "import json,sys;from faster_whisper import WhisperModel;"
            f"m=WhisperModel({(model or 'large-v3-turbo')!r},compute_type='int8');"
            f"segs,_=m.transcribe({str(wav)!r},language={lang!r},initial_prompt={prompt!r},vad_filter=True);"
            "json.dump({'segments':[{'start':s.start,'end':s.end,'text':s.text} for s in segs]},"
            f"open({str(work / 'fw.json')!r},'w'))"
        )
        attempts.append(("faster-whisper", ["uvx", "--from", "faster-whisper", "python", "-c", code],
                         work / "fw.json"))

    for name, cmd, result_path in attempts:
        try:
            run(cmd)
            data = json.loads(result_path.read_text())
            if "transcription" in data:  # whisper.cpp schema
                return [{"start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000,
                         "text": s["text"]} for s in data["transcription"]]
            return [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in data["segments"]]
        except Exception as exc:
            log(f"{name} unavailable or failed: {exc}")
    sys.exit("No transcription backend worked. On Apple Silicon:  brew install ffmpeg  (mlx-whisper then runs via uvx)")


def segments_to_markdown(segs: list[dict], para_seconds: float = 45, chapters: list[dict] | None = None) -> str:
    """Group segments into ~45 s paragraphs, each opened by an [hh:mm:ss] anchor for citation.
    Chapters become `## [hh:mm:ss] Title` headings and always start a new paragraph. Unpunctuated
    tracks (speech-recognition captions, Chinese subtitles) still break after 2 × para_seconds."""
    marks = sorted((c["start"], c["title"]) for c in chapters or [])
    out, buf, start, ci = [], [], None, 0

    def flush() -> None:
        nonlocal buf, start
        if buf:
            out.append(f"[{stamp(start or 0)}] " + " ".join(buf))
        buf, start = [], None

    for s in segs:
        while ci < len(marks) and s["start"] >= marks[ci][0] - 0.5:
            flush()
            out.append(f"## [{stamp(marks[ci][0])}] {marks[ci][1]}")
            ci += 1
        if start is None:
            start = s["start"]
        buf.append(s["text"].strip())
        elapsed = s["end"] - start
        if (elapsed >= para_seconds and re.search(r"[.!?。！？][\"'”’)）」]*$", buf[-1] or ".")) or elapsed >= 2 * para_seconds:
            flush()
    flush()
    return "\n\n".join(out)


def keyframes(video: Path, out: Path, max_frames: int = 36, every: float = 45) -> list[dict]:
    """Scene-change keyframes plus at least one frame every `every` seconds (static-camera talks have
    few cuts), thinned to max_frames and named by timestamp for citation. Writes frames/contact.jpg."""
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="frames-"))
    select = f"select='gt(scene,0.32)+isnan(prev_selected_t)+gte(t-prev_selected_t,{every})'"
    proc = subprocess.run(
        [need_ffmpeg(), "-hide_banner", "-i", str(video), "-an", "-vf",
         f"{select},scale='min(1600,iw)':-2,showinfo", "-vsync", "vfr", "-q:v", "3",
         str(tmp / "f-%05d.jpg")], text=True, capture_output=True)
    times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", proc.stderr)]
    files = sorted(tmp.glob("f-*.jpg"))
    if not files:
        log(f"no keyframes extracted: {proc.stderr[-300:]}")
    pairs = list(zip(files, times))
    if len(pairs) > max_frames:
        step = len(pairs) / max_frames
        pairs = [pairs[int(i * step)] for i in range(max_frames)]
    result = []
    for f, t in pairs:
        name = f"frame-{stamp(t).replace(':', '')}.jpg"
        if (frames_dir / name).exists():
            name = name.replace(".jpg", f"-{int(t * 1000) % 1000:03d}.jpg")
        shutil.move(str(f), frames_dir / name)
        result.append({"file": f"frames/{name}", "time": stamp(t)})
    shutil.rmtree(tmp, ignore_errors=True)
    if result:
        contact_sheet(result, out)
    return result


def contact_sheet(frames: list[dict], out: Path, cols: int = 6, tile: int = 300) -> None:
    """One image with every keyframe and its timestamp, so choosing frames takes one look."""
    import pymupdf

    first = pymupdf.Pixmap(str(out / frames[0]["file"]))
    th, pad, cap = round(tile * first.height / first.width), 14, 24
    rows = -(-len(frames) // cols)
    doc = pymupdf.open()
    page = doc.new_page(width=cols * tile + (cols + 1) * pad, height=rows * (th + cap) + (rows + 1) * pad)
    page.draw_rect(page.rect, color=None, fill=(0.16, 0.16, 0.15))
    for i, f in enumerate(frames):
        r, c = divmod(i, cols)
        x, y = pad + c * (tile + pad), pad + r * (th + cap + pad)
        page.insert_image(pymupdf.Rect(x, y, x + tile, y + th), filename=str(out / f["file"]))
        page.insert_text((x, y + th + 17), f"{f['time']}  {Path(f['file']).name}", fontsize=12, color=(0.82, 0.8, 0.76))
    page.get_pixmap(dpi=96).save(out / "frames" / "contact.jpg", jpg_quality=82)


def media_duration(path: Path) -> float:
    """Length of a media file in seconds, read from ffmpeg's header dump (0 if unknown)."""
    proc = subprocess.run([need_ffmpeg(), "-hide_banner", "-i", str(path)], text=True, capture_output=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def ingest_media(path: Path, out: Path, lang: str | None, model: str | None) -> dict:
    work = Path(tempfile.mkdtemp(prefix="ingest-"))
    segs = transcribe(path, work, lang, model)
    frames = keyframes(path, out) if path.suffix.lower() in VIDEO_EXT else []
    duration = media_duration(path) or (segs[-1]["end"] if segs else 0)
    shutil.rmtree(work, ignore_errors=True)
    return {"kind": "video" if frames else "audio", "title": path.stem, "duration": stamp(duration),
            "transcript": {"kind": "transcribed", "lang": lang or "auto"},
            "text": segments_to_markdown(segs), "assets": {"frames": frames}}


_CUE = re.compile(r"(\d+):(\d+):(\d+)[.,](\d+)\s+-->\s+(\d+):(\d+):(\d+)[.,](\d+)[^\n]*")


def parse_vtt(vtt: str) -> list[dict]:
    """WebVTT → segments. Skips cue settings (`align:start position:0%`) and, for speech-recognition
    captions, the rolling lines each cue repeats from the previous one."""
    import html

    segs, prev = [], []
    for block in re.split(r"\n\s*\n", vtt.replace("\r\n", "\n")):
        m = _CUE.search(block)
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        lines = [html.unescape(re.sub(r"<[^>]+>", "", l)).strip() for l in block[m.end():].split("\n")]
        lines = [l for l in lines if l]
        new = [l for l in lines if l not in prev]
        if lines:
            prev = lines
        if not new:
            continue
        segs.append({"start": h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                     "end": h2 * 3600 + m2 * 60 + s2 + ms2 / 1000, "text": " ".join(new)})
    return segs


YTDLP = ["uvx", "--from", "yt-dlp[default,curl-cffi]", "yt-dlp"]


def ytdlp() -> list[str]:
    """yt-dlp with Node as its JavaScript runtime (YouTube challenges need one)."""
    return YTDLP + (["--js-runtimes", "node"] if shutil.which("node") else [])


def lang_base(code: str | None) -> str:
    return (code or "").lower().replace("_", "-").split("-")[0]


def is_traditional(code: str | None) -> bool:
    c = (code or "").lower()
    return c in TRADITIONAL or any(t in c for t in ("hant", "-tw", "-hk"))


def pick_subtitles(info: dict, lang: str | None) -> tuple[str | None, str | None, str | None]:
    """→ (track, kind, spoken). Human subtitles in the spoken language first, then that language's
    speech-recognition captions. Machine-translated caption tracks are never used as the transcript."""
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat"}
    auto = info.get("automatic_captions") or {}
    orig = next((k[:-5] for k in auto if k.endswith("-orig")), None)
    spoken = info.get("language") or orig
    if spoken and lang and lang_base(spoken) != lang_base(lang):
        log(f"the video is in '{spoken}' but --lang is '{lang}'. --lang names the language spoken in the recording; "
            f"using the '{spoken}' track — write the deck in the audience's language yourself")
    want = lang_base(spoken or lang)
    cands = [k for k in manual if want and lang_base(k) == want]
    if not want and manual:   # language unknown: one human track is surely it; among several, English is likeliest
        cands = list(manual) if len(manual) == 1 else (["en"] if "en" in manual else sorted(manual)[:1])
        log(f"the video does not say its language; using human subtitles '{cands[0]}' — pass --lang to choose")
    # 'en' before 'en-GB'; for Chinese, the script the user asked for first
    cands.sort(key=lambda k: (is_traditional(k) != is_traditional(lang), len(k)) if want == "zh" else (len(k), k))
    if cands:
        return cands[0], "manual", spoken or cands[0]
    for k in [f"{spoken}-orig", spoken] if spoken else [k for k in auto if k.endswith("-orig")]:
        if k in auto:
            return k, "auto", spoken or k[:-5]
    return None, None, spoken


def fetch_subs(url: str, track: str, kind: str, work: Path, tag: str) -> Path | None:
    """Download exactly one subtitle track (asking for many trips YouTube's rate limit), with retries."""
    import time

    for attempt, pause in enumerate([0, 6, 20]):
        time.sleep(pause)
        try:
            run(ytdlp() + ["--skip-download", "--write-subs" if kind == "manual" else "--write-auto-subs",
                         "--sub-langs", re.escape(track), "--sub-format", "vtt/best", "--convert-subs", "vtt",
                         "-o", str(work / tag), url])
        except subprocess.CalledProcessError as exc:
            if "429" not in (exc.stderr or "") or attempt == 2:
                return None
            log("YouTube rate-limited the subtitle request (HTTP 429); retrying")
            continue
        return next(iter(sorted(work.glob(f"{tag}*.vtt"))), None)
    return None


def ingest_youtube(url: str, out: Path, lang: str | None, model: str | None, frames: bool = True) -> dict:
    work = Path(tempfile.mkdtemp(prefix="yt-"))
    info = json.loads(run(ytdlp() + ["--dump-single-json", "--skip-download", "--no-playlist", url]).stdout)
    chapters = [{"start": c.get("start_time", 0),
                 "title": ("Opening" if i == 0 else f"Part {i + 1}") if re.match(r"<Untitled Chapter \d+>", c.get("title", "")) else c.get("title", "")}
                for i, c in enumerate(info.get("chapters") or [])]
    track, kind, spoken = pick_subtitles(info, lang)
    segs, transcript = [], {}
    if track:
        vtt = fetch_subs(url, track, kind, work, "subs")
        if vtt:
            segs = parse_vtt(vtt.read_text(encoding="utf-8", errors="replace"))
            if lang_base(track) == "zh" and is_traditional(lang):
                segs = to_traditional(segs, lang)
            transcript = {"kind": "manual subtitles" if kind == "manual" else "speech-recognition captions (unpunctuated, may mishear names)",
                          "track": track}
            # TED/Amara subtitles open with a credit cue ("Translator: … Reviewer: …"): keep it out of the talk.
            if segs and re.match(r"(Translator|Transcriber|Transcription)\s*:", segs[0]["text"]) and "Reviewer" in segs[0]["text"]:
                transcript["credit"] = segs.pop(0)["text"]
            log(f"using {kind} subtitles '{track}' ({len(segs)} cues)")
        # A human translation in the language the user asked for is worth keeping beside the original.
        human = [k for k in (info.get("subtitles") or {}) if lang and lang_base(k) == lang_base(lang) and k != track]
        if human and lang_base(lang) != lang_base(track):
            human.sort(key=lambda k: (is_traditional(k) != is_traditional(lang), len(k)))
            tv = fetch_subs(url, human[0], "manual", work, "trans")
            if tv:
                (out / f"translation-{human[0]}.md").write_text(
                    f"# {info.get('title', url)} — human subtitles ({human[0]})\n\n"
                    + segments_to_markdown(parse_vtt(tv.read_text(encoding='utf-8', errors='replace')), chapters=chapters) + "\n",
                    encoding="utf-8")
                transcript["translation"] = f"translation-{human[0]}.md"
    if not segs:
        log("no usable subtitles; downloading the audio track for transcription")
        run(ytdlp() + ["-f", "ba[ext=m4a]/ba/b", "-o", str(work / "audio.%(ext)s"), url])
        tl = lang if lang and (not spoken or lang_base(lang) == lang_base(spoken)) else spoken
        segs = transcribe(next(work.glob("audio.*")), work, tl, model)
        transcript = {"kind": "transcribed", "lang": tl or "auto"}
    keys = []
    if frames:  # frames are a bonus; the transcript is the deliverable. YouTube sometimes answers a
        import time  # stream request with a transient 403 — wait and try another delivery (DASH → HLS).
        for pause, fmt in [(0, "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/b"),
                           (8, "bv*[protocol=m3u8_native][height<=720]/b[protocol=m3u8_native][height<=720]")]:
            time.sleep(pause)
            try:
                run(ytdlp() + ["-f", fmt, "-o", str(work / "video.%(ext)s"), url])
                keys = keyframes(next(work.glob("video.*")), out)
                break
            except Exception as exc:
                for f in work.glob("video.*"):
                    f.unlink(missing_ok=True)
                log(f"video for keyframes unavailable ({exc.__class__.__name__}); {'retrying' if pause == 0 else 'skipping keyframes'}")
    shutil.rmtree(work, ignore_errors=True)
    desc = (info.get("description") or "").strip()
    return {"kind": "youtube", "title": info.get("title", url), "author": info.get("uploader", ""),
            "channel": info.get("channel", ""), "duration": stamp(info.get("duration") or 0), "origin_url": url,
            "uploaded": info.get("upload_date", ""), "license": info.get("license") or "standard YouTube licence",
            "language": spoken or "", "transcript": transcript,
            "description": desc[:900] + (" …" if len(desc) > 900 else ""),
            "toc": [{"level": 1, "title": c["title"], "time": stamp(c["start"])} for c in chapters],
            "text": segments_to_markdown(segs, chapters=chapters), "assets": {"frames": keys}}


# ───────────────────────────── output ─────────────────────────────

def chunk(text: str, limit: int) -> list[str]:
    """Split on page/heading/paragraph boundaries into ~limit-word chunks. A chunk never ends on a
    heading (it moves to the next chunk), and a chunk that starts mid-chapter opens with a
    `<!-- continues: … -->` line naming the chapter, the last page/timestamp anchor before it."""
    blocks = [b for b in re.split(r"(?=\n<!-- page [\w.-]+ -->)|(?=\n#{1,6} )|\n\n", text) if b.strip()]
    is_head = lambda b: re.match(r"\s*#{1,6} ", b) is not None
    chunks, buf, n, heads, where = [], [], 0, {}, ""

    def context() -> str:
        path = " › ".join(heads[k] for k in sorted(heads))
        return f"<!-- continues: {path}{' · ' + where if where else ''} -->" if path or where else ""

    opening = ""
    for b in blocks:
        w = words_of(b)
        if buf and n + w > limit and not is_head(b):
            tail = []
            while buf and is_head(buf[-1]):           # keep headings with the text they introduce
                tail.insert(0, buf.pop())
            if buf:
                chunks.append("\n\n".join(([opening] if opening else []) + buf).strip())
                opening = "" if tail else context()
                buf, n = tail, sum(words_of(t) for t in tail)
        m = re.match(r"\s*(#{1,6}) (.+)", b)
        if m:
            level = len(m.group(1))
            heads = {k: v for k, v in heads.items() if k < level}
            heads[level] = m.group(2).strip()
        a = re.findall(r"<!-- page ([\w.-]+) -->|^\[(\d\d:\d\d:\d\d)\]", b, re.M)
        if a:
            where = "p. " + a[-1][0] if a[-1][0] else a[-1][1]
        buf.append(b)
        n += w
    if buf:
        chunks.append("\n\n".join(([opening] if opening else []) + buf).strip())
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="files or URLs")
    ap.add_argument("--out", required=True, type=Path, help="output folder, e.g. decks/<name>/source")
    ap.add_argument("--lang", default=None,
                    help="spoken language, e.g. en, ja, zh; zh-TW / zh-Hant gives Traditional Chinese (Taiwan phrasing)")
    ap.add_argument("--model", default=None, help="override the transcription model")
    ap.add_argument("--prompt", default="", help="vocabulary hint for transcription, e.g. 'Transformer, attention, BLEU'")
    ap.add_argument("--render-pages", type=int, default=40, help="render at most N PDF pages to PNG (0 = off)")
    ap.add_argument("--chunk-words", type=int, default=9000, help="chunk size for long sources")
    ap.add_argument("--no-frames", action="store_true", help="YouTube: skip the video download that yields keyframes")
    ap.add_argument("--pdf-engine", choices=["pymupdf", "docling"], default="pymupdf",
                    help="pymupdf (fast; AGPL) or docling (MIT; slower, stronger on tables/complex layouts)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for stale in ("chunks", "frames", "figures", "pages"):   # generated folders: a re-run replaces them
        shutil.rmtree(args.out / stale, ignore_errors=True)
    global PROMPT_HINT
    PROMPT_HINT = args.prompt

    docs = []
    for src in args.sources:
        p = Path(src)
        ext = p.suffix.lower()
        log(f"ingesting {src}")
        if src.startswith(("http://", "https://")):
            item = (ingest_youtube(src, args.out, args.lang, args.model, frames=not args.no_frames)
                    if YOUTUBE.search(src) else ingest_office(src))
            item.setdefault("origin_url", src)
        elif not p.exists():
            sys.exit(f"not found: {src}")
        elif ext == ".epub":
            item = ingest_epub(p, args.out)
        elif ext in DOC_EXT:
            item = ingest_document(p, args.out, args.render_pages, args.pdf_engine)
        elif ext in OFFICE_EXT:
            item = ingest_office(str(p))
        elif ext in TEXT_EXT:
            item = ingest_text(p)
        elif ext in AUDIO_EXT | VIDEO_EXT:
            item = ingest_media(p, args.out, args.lang, args.model)
        else:
            sys.exit(f"unsupported source type: {src}")
        item["text"], facts = strip_boilerplate(item["text"])
        if facts:
            item.setdefault("edition", facts)
        item["origin"] = src
        docs.append(item)

    today = dt.date.today().isoformat()
    sections, total_words = [], 0
    for d in docs:
        words = words_of(d["text"])
        total_words += words
        d["words"] = words
        head = [f"# {d['title']}", ""]
        facts = {k: d.get(k) for k in ("kind", "author", "pages", "page_numbers", "duration", "license", "origin") if d.get(k)}
        if d.get("transcript"):
            t = d["transcript"]
            facts["transcript"] = t.get("kind", "") + (f" · track {t['track']}" if t.get("track") else "") + \
                (f" · human translation in {t['translation']}" if t.get("translation") else "")
        head += [f"> {k}: {v}" for k, v in facts.items()] + [f"> words: {words:,}", ""]
        sections.append("\n".join(head) + "\n" + d["text"].strip() + "\n")

    front = ["---", f"title: {docs[0]['title'] if len(docs) == 1 else 'Combined sources'}",
             f"sources: {len(docs)}", f"words: {total_words}", f"ingested: {today}", "---", ""]
    body = "\n".join(front) + "\n\n".join(sections)
    (args.out / "source.md").write_text(body, encoding="utf-8")

    chunk_files = []
    if total_words > args.chunk_words * 1.6:
        cdir = args.out / "chunks"
        cdir.mkdir(exist_ok=True)
        for i, c in enumerate(chunk(body, args.chunk_words), start=1):
            f = cdir / f"chunk-{i:02d}.md"
            f.write_text(c, encoding="utf-8")
            chunk_files.append(str(f.relative_to(args.out)))

    manifest = {
        "ingested": today,
        "words": total_words,
        "reading_minutes": round(total_words / 250),
        "sources": [{k: v for k, v in d.items() if k != "text"} for d in docs],
        "chunks": chunk_files,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_md": str(args.out / "source.md"), "words": total_words,
                      "chunks": len(chunk_files),
                      "pages_rendered": sum(d["assets"].get("pages", 0) for d in docs),
                      "figures": sum(len(d["assets"].get("figures", [])) for d in docs),
                      "frames": sum(len(d["assets"].get("frames", [])) for d in docs)}, indent=2))


if __name__ == "__main__":
    main()
