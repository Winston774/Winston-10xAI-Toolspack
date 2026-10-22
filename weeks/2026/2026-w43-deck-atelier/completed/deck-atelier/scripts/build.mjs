#!/usr/bin/env node
/* ============================================================================
   deck-atelier · build.mjs — bundle a deck into one portable, offline HTML file.

     node scripts/build.mjs <deck.html> [--out <dir>] [--name <base>]
                            [--variants static,motion] [--no-fonts] [--no-phrase]

   What it does
     · phrase-aware line breaks for Chinese/Japanese text: <wbr> between phrases
       (BudouX, confirmed by ICU word boundaries) in titles, statements, leads,
       paragraphs, list items, labels… — the bundle only, deck.html is never touched
     · inlines local <link rel="stylesheet"> and <script src>
     · inlines local images (<img src>, SVG <image href>, style="url()") as data URIs
     · swaps the Google Fonts <link data-fonts> for embedded @font-face rules that
       contain only the glyphs this deck uses (CJK decks stay ~1–2 MB, not 20 MB);
       each rule claims only the characters Google's online CSS covers for that family
       (unicode-range), so a character the online font leaves to the next family in the
       stack falls through to it in the bundle too
     · writes <base>.html (data-motion="off", Part 1 static deck)
       and   <base>-motion.html (data-motion="on", Part 2 motion deck)

   Zero npm dependencies — Node 18+ (fetch, Intl.Segmenter). Fonts need network at
   build time only; offline, the build keeps the online <link> and says so. Phrase
   breaks (scripts/phrase.mjs) need `uv` to run phrase.py; without it the build skips
   them and says so.
   ========================================================================== */
import fs from 'node:fs/promises';
import path from 'node:path';
import { PHRASE_CSS, deckLang, phraseBreaks } from './phrase.mjs';

const argv = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  if (i < 0) return dflt;
  const v = argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
};
const input = argv.find((a) => !a.startsWith('--') && /\.html?$/i.test(a));
if (!input) {
  console.error('usage: node scripts/build.mjs <deck.html> [--out dir] [--name base] [--variants static,motion] [--no-fonts] [--no-phrase]');
  process.exit(1);
}

const src = path.resolve(input);
const srcDir = path.dirname(src);
const outDir = path.resolve(flag('out', path.join(srcDir, 'dist')));
const base = flag('name', path.basename(src).replace(/\.html?$/i, '').replace(/^deck$/, path.basename(srcDir)));
const variants = String(flag('variants', 'static,motion')).split(',').map((s) => s.trim()).filter(Boolean);
const withFonts = !argv.includes('--no-fonts');
const withPhrase = !argv.includes('--no-phrase');

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.mp4': 'video/mp4',
};
const isLocal = (u) => u && !/^(https?:|data:|blob:|#|mailto:|\/\/)/i.test(u);
const log = (...a) => console.error('·', ...a);

async function dataURI(file) {
  const buf = await fs.readFile(file);
  const mime = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
  return `data:${mime};base64,${buf.toString('base64')}`;
}

async function replaceAsync(str, re, fn) {
  const jobs = [];
  str.replace(re, (...m) => { jobs.push(fn(...m)); return m[0]; });
  const out = await Promise.all(jobs);
  let i = 0;
  return str.replace(re, () => out[i++]);
}

async function inlineCssUrls(css, dir) {
  return replaceAsync(css, /url\((['"]?)([^'")]+)\1\)/g, async (m, q, u) => {
    if (!isLocal(u)) return m;
    try { return `url("${await dataURI(path.resolve(dir, u))}")`; } catch { log(`missing asset ${u}`); return m; }
  });
}

/* ── collect the characters the audience will actually see ─────────────── */

function visibleText(html, extraJs) {
  const decode = (s) => s
    .replace(/&nbsp;/g, ' ').replace(/&ensp;|&emsp;|&thinsp;/g, ' ')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d));
  const body = html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ');
  const attrs = [...body.matchAll(/\s(?:data-(?:title|chapter-title|tracker|source|count)|alt|title|aria-label)="([^"]*)"/g)].map((m) => m[1]);
  const text = body.replace(/<[^>]+>/g, ' ');
  const cssContent = [...html.matchAll(/content:\s*"([^"]+)"/g)].map((m) => m[1]);
  const jsStrings = [...(extraJs || '').matchAll(/[ -⁯　-鿿＀-￯·—–…]+/g)].map((m) => m[0]);
  let ascii = '';
  for (let c = 32; c < 127; c++) ascii += String.fromCharCode(c);
  const all = decode([text, ...attrs, ...cssContent, ...jsStrings].join(' ')) + ascii + '“”‘’—–…·×÷−±≈→←↑↓√∞⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉ᵀ';
  // keep real spaces (U+0020, NBSP, en/em/thin spaces): without them the browser borrows a system font's space width
  return [...new Set([...all + ' \u00A0\u2002\u2003\u2009'].filter((c) => !/[\n\r\t\f\v]/.test(c)))].sort().join('');
}

function unicodeRange(chars) {
  const cps = [...new Set([...chars].map((c) => c.codePointAt(0)))].sort((a, b) => a - b);
  const parts = [];
  for (let i = 0; i < cps.length; i++) {
    let j = i;
    while (j + 1 < cps.length && cps[j + 1] === cps[j] + 1) j++;
    const hex = (n) => n.toString(16).toUpperCase();
    parts.push(i === j ? `U+${hex(cps[i])}` : `U+${hex(cps[i])}-${hex(cps[j])}`);
    i = j;
  }
  return parts.join(', ');
}

const parseRanges = (s) => [...s.matchAll(/U\+([0-9a-f?]+)(?:-([0-9a-f]+))?/gi)].map(([, a, z]) => a.includes('?')
  ? [parseInt(a.replace(/\?/g, '0'), 16), parseInt(a.replace(/\?/g, 'F'), 16)]
  : [parseInt(a, 16), parseInt(z ?? a, 16)]);
const covers = (ranges, ch) => { const cp = ch.codePointAt(0); return ranges.some(([a, z]) => cp >= a && cp <= z); };
const faceKey = (body) => `${body.match(/font-style:\s*([^;]+)/)?.[1].trim()} ${body.match(/font-weight:\s*([^;]+)/)?.[1].trim()}`;

// What Google's own CSS for a family serves each face (style + weight): the union of its unicode-range slices.
// A face without a range claims everything, like the descriptor's initial value.
async function onlineSlices(fam) {
  const q = new URL('https://fonts.googleapis.com/css2');
  q.searchParams.set('family', fam);
  const res = await fetch(q, { headers: { 'User-Agent': UA } });
  if (!res.ok) throw new Error(`${res.status} for ${fam}`);
  const faces = new Map();
  for (const [, body] of (await res.text()).matchAll(/@font-face\s*{([^}]*)}/g)) {
    const range = body.match(/unicode-range:\s*([^;]*)/)?.[1];
    const key = faceKey(body);
    faces.set(key, [...(faces.get(key) ?? []), ...(range ? parseRanges(range) : [[0, 0x10ffff]])]);
  }
  if (!faces.size) throw new Error(`no faces in Google's CSS for ${fam}`);
  return faces;
}

async function embedFonts(href, chars) {
  // One request per family keeps URLs short; long glyph sets are split into batches.
  // A family claims only the characters its online slices cover: whatever the online font leaves to the next
  // family in the stack (→ and the superscripts in Inter, CJK in the Latin faces) must fall through here too.
  const url = new URL(href.replace(/&amp;/g, '&'));
  const families = url.searchParams.getAll('family');
  const per = 700;
  const rules = [];
  let bytes = 0;
  for (const fam of families) {
    const online = await onlineSlices(fam);
    const reach = [...online.values()].flat();
    const mine = [...chars].filter((c) => covers(reach, c));
    if (!mine.length) { log(`font ${decodeURIComponent(fam)} skipped — none of the deck's glyphs are in its online slices`); continue; }
    for (let i = 0; i < mine.length; i += per) {
      const batch = mine.slice(i, i + per).join('');
      const q = new URL('https://fonts.googleapis.com/css2');
      q.searchParams.set('family', fam);
      q.searchParams.set('text', batch);
      q.searchParams.set('display', 'block');
      const res = await fetch(q, { headers: { 'User-Agent': UA } });
      if (!res.ok) throw new Error(`${res.status} for ${fam}`);
      const css = await replaceAsync(await res.text(), /@font-face\s*{([^}]*)}/g, async (m, body) => {
        const own = [...batch].filter((c) => covers(online.get(faceKey(body)) ?? reach, c)).join('');
        if (!own) return '';
        const inlined = await replaceAsync(body, /url\((https:\/\/fonts\.gstatic\.com[^)]+)\)/g, async (m2, u) => {
          const r = await fetch(u, { headers: { 'User-Agent': UA } });
          const buf = Buffer.from(await r.arrayBuffer());
          bytes += buf.length;
          return `url(data:font/woff2;base64,${buf.toString('base64')})`;
        });
        return `@font-face {${inlined.replace(/unicode-range:[^;]*;/, '').trimEnd()}\n  unicode-range: ${unicodeRange(own)};\n}`;
      });
      if (css.trim()) rules.push(css.trim());
    }
    log(`font ${decodeURIComponent(fam)} embedded`);
  }
  return { css: rules.join('\n'), bytes };
}

/* ── main ─────────────────────────────────────────────────────────────── */

let html = await fs.readFile(src, 'utf8');

// phrase breaks first, while the markup is still small (nothing inlined yet)
let phrase = null;
if (withPhrase) {
  try {
    const r = phraseBreaks(html, deckLang(html));
    html = r.html;
    phrase = { model: r.model, elements: r.elements, breaks: r.breaks, glue: r.glue };
    if (r.elements) log(`phrase breaks: ${r.breaks} <wbr> + ${r.glue} glued in ${r.elements} elements (BudouX ${r.model} ∩ ICU words)`);
  } catch (e) {
    log(`phrase breaks skipped (${e.message}) — Chinese lines may break inside words; install uv, or pass --no-phrase to silence this`);
  }
}

// stylesheets
html = await replaceAsync(html, /<link\b[^>]*rel=["']stylesheet["'][^>]*>/gi, async (tag) => {
  const href = tag.match(/href=["']([^"']+)["']/i)?.[1];
  if (!isLocal(href)) return tag;
  const file = path.resolve(srcDir, href);
  const css = await inlineCssUrls(await fs.readFile(file, 'utf8'), path.dirname(file));
  return `<style data-inlined="${path.basename(href)}">\n${css}\n</style>`;
});
// a deck whose engine copy predates phrase breaks still gets the one rule they need
if (phrase?.elements && !html.includes('[data-phrase="auto"]')) {
  html = html.replace(/<\/head>/i, `<style data-phrase-css>${PHRASE_CSS}</style>\n</head>`);
  log('engine/atelier.css predates phrase breaks — added the rule to the bundle; refresh it with new_deck.mjs --update-engine');
}

// scripts
let engineJs = '';
html = await replaceAsync(html, /<script\b([^>]*)\bsrc=["']([^"']+)["']([^>]*)><\/script>/gi, async (tag, a, href, b) => {
  if (!isLocal(href)) return tag;
  const js = await fs.readFile(path.resolve(srcDir, href), 'utf8');
  engineJs += js;
  return `<script data-inlined="${path.basename(href)}"${a}${b}>\n${js.replace(/<\/script/gi, '<\\/script')}\n</script>`;
});

// images and media
html = await replaceAsync(html, /(<(?:img|source|video)\b[^>]*\bsrc=|<image\b[^>]*\b(?:xlink:)?href=)(["'])([^"']+)\2/gi, async (m, pre, q, u) => {
  if (!isLocal(u)) return m;
  try { return `${pre}${q}${await dataURI(path.resolve(srcDir, u))}${q}`; } catch { log(`missing asset ${u}`); return m; }
});
html = await replaceAsync(html, /style="([^"]*url\([^"]*)"/gi, async (m, style) => `style="${await inlineCssUrls(style, srcDir)}"`);

// fonts
let fontBytes = 0;
const fontLink = html.match(/<link\b[^>]*\bdata-fonts\b[^>]*>/i)?.[0];
if (fontLink && withFonts) {
  const href = fontLink.match(/href=["']([^"']+)["']/i)?.[1];
  const chars = visibleText(html, engineJs);
  try {
    const { css, bytes } = await embedFonts(href, chars);
    fontBytes = bytes;
    html = html.replace(fontLink, `<style data-fonts-embedded>\n${css}\n</style>`)
      .replace(/<link\b[^>]*rel=["']preconnect["'][^>]*>\s*/gi, '');
    log(`${[...chars].length} glyphs · ${(bytes / 1024).toFixed(0)} KB of fonts embedded`);
  } catch (e) {
    log(`could not embed fonts (${e.message}); keeping the online <link> — the deck needs internet for its typefaces`);
  }
}

await fs.mkdir(outDir, { recursive: true });
const setMotion = (h, v) => h.replace(/<html\b([^>]*)>/i, (m, attrs) => `<html${attrs.replace(/\sdata-motion="[^"]*"/, '')} data-motion="${v}">`);
const written = [];
for (const v of variants) {
  const name = v === 'motion' ? `${base}-motion.html` : `${base}.html`;
  const file = path.join(outDir, name);
  await fs.writeFile(file, setMotion(html, v === 'motion' ? 'on' : 'off'));
  const { size } = await fs.stat(file);
  written.push({ variant: v, file, kb: Math.round(size / 1024) });
}
console.log(JSON.stringify({ written, fontsKB: Math.round(fontBytes / 1024), phrase }, null, 2));
