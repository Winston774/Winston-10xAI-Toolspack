#!/usr/bin/env node
/* ============================================================================
   deck-atelier · snapshot.mjs — look at a deck the way an audience will.
   Drives headless Chrome over the DevTools protocol (no npm dependencies).

     node scripts/snapshot.mjs <deck.html> --out <dir> [options]

     (default)              one PNG per slide + sheet.png (contact sheet)
     --slides 1,4-6         only these slides
     --theme dark           render in another theme
     --style tokyo          render in another style (its fonts load from Google Fonts)
     --styles all           gallery: the chosen --slides in every style (or a list:
                            swiss,tokyo,riso) → <out>/<style>/… + gallery.png, one row per style
     --motion on|off        force motion mode (default: as authored)
     --film 7               filmstrip of the transition INTO slide 7
       --at 0,200,450,800,1600   …frozen at these milliseconds
     --steps                also capture every build step (motion decks)
     --check                layout lint: overflow, out-of-safe-area, tiny text, missing fonts
     --pdf <file.pdf>       print the deck (static, one slide per page)
     --width 1920           viewport (default 1920×1080)
     --no-phrase            render a source deck without the build's phrase breaks

   A source deck (not yet built) gets the phrase-aware CJK line breaks the build adds
   (scripts/phrase.mjs; without `uv` it says so and renders the source as is), so line
   counts match dist/. The phrased copy is a hidden .snapshot-<pid>-deck.html beside
   deck.html, so engine/ and assets/ links resolve; it is removed when the run ends.

   Requires Google Chrome / Chromium / Edge. Set CHROME_PATH to override.
   ========================================================================== */
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import { existsSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { PHRASE_CSS, deckLang, phraseBreaks } from './phrase.mjs';
import { loadStyles } from './styles.mjs';

const argv = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  if (i < 0) return dflt;
  const v = argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
};
const input = argv.find((a) => !a.startsWith('--') && /\.html?$/i.test(a));
if (!input) {
  console.error('usage: node scripts/snapshot.mjs <deck.html> --out <dir> [--slides 1,3-5] [--film N --at 0,300,900] [--steps] [--check] [--pdf out.pdf] [--no-phrase]');
  process.exit(1);
}
const outDir = path.resolve(flag('out', path.join(path.dirname(path.resolve(input)), 'snapshots')));
const VW = +flag('width', 1920);
const VH = Math.round((VW * 9) / 16);

function findChrome() {
  const c = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ].filter(Boolean);
  const hit = c.find((p) => existsSync(p));
  if (!hit) throw new Error('Chrome not found — install Google Chrome or set CHROME_PATH');
  return hit;
}

/* ── minimal CDP client ─────────────────────────────────────────────── */

async function launch() {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'atelier-chrome-'));
  const proc = spawn(findChrome(), [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--mute-audio',
    '--force-device-scale-factor=1', `--window-size=${VW},${VH}`, '--allow-file-access-from-files', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let buf = '';
    const t = setTimeout(() => reject(new Error('Chrome did not start')), 20000);
    proc.stderr.on('data', (d) => {
      buf += d;
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(t); resolve(m[1]); }
    });
  });
  const ws = new WebSocket(wsUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const pending = new Map();
  const listeners = new Set();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
    } else listeners.forEach((fn) => fn(msg));
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params, sessionId }));
  });
  const close = async () => {
    try { await send('Browser.close'); } catch { /* already closing */ }
    proc.kill();
    await fs.rm(profile, { recursive: true, force: true }).catch(() => {});
  };
  return { send, listeners, close };
}

async function openPage(cdp, url, height = VH) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const s = (m, p) => cdp.send(m, p, sessionId);
  await s('Page.enable');
  await s('Runtime.enable');
  await s('Emulation.setDeviceMetricsOverride', { width: VW, height, deviceScaleFactor: 1, mobile: false });
  const loaded = new Promise((r) => {
    const fn = (msg) => { if (msg.sessionId === sessionId && msg.method === 'Page.loadEventFired') { cdp.listeners.delete(fn); r(); } };
    cdp.listeners.add(fn);
  });
  await s('Page.navigate', { url });
  await loaded;
  const evaluate = async (expression) => {
    const r = await s('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  await evaluate(`new Promise((res) => { const t0 = Date.now(); (function wait() {
    if (window.atelier && document.fonts.status === 'loaded') return res(true);
    if (Date.now() - t0 > 15000) return res(false); setTimeout(wait, 60); })(); })`);
  await evaluate(`(async () => { await (atelier.ready || true); atelier.overview(true); await document.fonts.ready; atelier.overview(false); atelier.go(0, { instant: true }); atelier.settle();
    await document.fonts.ready; await new Promise((r) => setTimeout(r, 300)); return true; })()`);
  const shot = async (file, clip) => {
    const { data } = await s('Page.captureScreenshot', { format: 'png', ...(clip ? { clip: { ...clip, scale: 1 }, captureBeyondViewport: true } : {}) });
    await fs.writeFile(file, Buffer.from(data, 'base64'));
    return file;
  };
  return { s, evaluate, shot, sessionId };
}

const frames = 'new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 30))))';

function parseList(spec, n) {
  if (!spec || spec === true) return [...Array(n).keys()];
  const out = new Set();
  for (const part of String(spec).split(',')) {
    const [a, b] = part.split('-').map((x) => +x);
    for (let i = a; i <= (b || a); i++) if (i >= 1 && i <= n) out.add(i - 1);
  }
  return [...out].sort((x, y) => x - y);
}

async function sheet(cdp, files, file, cols = 4) {
  const cellW = Math.floor((1920 - 48 * 2 - 24 * (cols - 1)) / cols);
  const rows = Math.ceil(files.length / cols);
  const h = 48 * 2 + rows * Math.round((cellW * 9) / 16) + (rows - 1) * 40 + rows * 18;
  const html = `<!doctype html><meta charset=utf-8><style>body{margin:0;background:#2a2926;padding:48px;display:grid;
    grid-template-columns:repeat(${cols},${cellW}px);gap:22px 24px;font:13px/1 -apple-system,sans-serif;color:#aaa}
    figure{margin:0}img{width:100%;display:block}figcaption{margin-top:6px}</style>` +
    files.map((f) => `<figure><img src="${pathToFileURL(f).href}"><figcaption>${path.basename(f)}</figcaption></figure>`).join('');
  const tmp = path.join(path.dirname(file), '.sheet.html');
  await fs.writeFile(tmp, html);
  const page = await openPageRaw(cdp, pathToFileURL(tmp).href, h);
  await page.shot(file, { x: 0, y: 0, width: 1920, height: h });
  await fs.rm(tmp, { force: true });
  return file;
}

async function gallerySheet(cdp, rows, file) {
  const cols = Math.max(...rows.map((r) => r.files.length));
  const cellW = Math.floor((1920 - 48 * 2 - 20 * (cols - 1)) / cols);
  const cellH = Math.round((cellW * 9) / 16);
  const h = 48 * 2 + rows.length * (cellH + 52) + (rows.length - 1) * 18;
  const html = `<!doctype html><meta charset=utf-8><style>body{margin:0;background:#1f1f1f;padding:48px;font:600 18px/1 -apple-system,sans-serif;color:#ddd}
    section{margin-bottom:18px}h2{margin:0 0 12px;font:inherit;letter-spacing:.02em}h2 small{margin-left:12px;color:#888;font-weight:400}
    .row{display:grid;grid-template-columns:repeat(${cols},${cellW}px);gap:20px}img{width:100%;display:block}</style>` +
    rows.map((r) => `<section><h2>${r.label}<small>${r.key}</small></h2><div class="row">${r.files.map((f) => `<img src="${pathToFileURL(f).href}">`).join('')}</div></section>`).join('');
  const tmp = path.join(path.dirname(file), '.gallery.html');
  await fs.writeFile(tmp, html);
  const page = await openPageRaw(cdp, pathToFileURL(tmp).href, h);
  await new Promise((r) => setTimeout(r, 400));
  await page.shot(file, { x: 0, y: 0, width: 1920, height: h });
  await fs.rm(tmp, { force: true });
  return file;
}

async function openPageRaw(cdp, url, height) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const s = (m, p) => cdp.send(m, p, sessionId);
  await s('Page.enable');
  await s('Emulation.setDeviceMetricsOverride', { width: 1920, height, deviceScaleFactor: 1, mobile: false });
  const loaded = new Promise((r) => {
    const fn = (msg) => { if (msg.sessionId === sessionId && msg.method === 'Page.loadEventFired') { cdp.listeners.delete(fn); r(); } };
    cdp.listeners.add(fn);
  });
  await s('Page.navigate', { url });
  await loaded;
  return {
    shot: async (file, clip) => {
      const { data } = await s('Page.captureScreenshot', { format: 'png', clip: { ...clip, scale: 1 }, captureBeyondViewport: true });
      await fs.writeFile(file, Buffer.from(data, 'base64'));
    },
  };
}

/* ── layout lint, evaluated inside the page ───────────────────────── */

const LINT = `(() => {
  const res = { fonts: {}, slides: [] };
  const faces = [...document.fonts];
  for (const fam of new Set(faces.map((f) => f.family.replace(/["']/g, '')))) {
    const mine = faces.filter((f) => f.family.replace(/["']/g, '') === fam);
    res.fonts[fam] = mine.some((f) => f.status === 'loaded') ? 'loaded' : mine.some((f) => f.status === 'error') ? 'ERROR' : 'not used';
  }
  const slides = [...document.querySelectorAll('.deck > .slide')];
  slides.forEach((s, i) => {
    atelier.go(i, { instant: true, step: 'all' }); atelier.settle();
    const sr = s.getBoundingClientRect(); const k = sr.width / 1920; const issues = [];
    const leafText = [...s.querySelectorAll('*')].filter((el) => !el.closest('.chrome, .notes, [data-bleed]') &&
      [...el.childNodes].some((n) => n.nodeType === 3 && n.data.trim()) && !el.closest('.source'));
    for (const el of leafText) {
      const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
      const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
      const x0 = (r.left - sr.left) / k, y0 = (r.top - sr.top) / k, x1 = (r.right - sr.left) / k, y1 = (r.bottom - sr.top) / k;
      const label = (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : el.tagName.toLowerCase()) + ' “' + el.textContent.trim().slice(0, 18) + '”';
      if (x0 < 56 || x1 > 1864 || y0 < 96 || y1 > 1012) issues.push('outside safe area: ' + label + ' [' + [x0, y0, x1, y1].map(Math.round).join(',') + ']');
      const fs = parseFloat(cs.fontSize) * (el.closest('svg') ? (el.closest('svg').getBoundingClientRect().width / k) / (el.closest('svg').viewBox.baseVal.width || 1920) : 1);
      if (fs < 13) issues.push('tiny text (' + fs.toFixed(1) + 'px): ' + label);
    }
    for (const el of s.querySelectorAll('.body, .figure, .points > li, .takeaway, .title')) {
      if (el.scrollHeight > el.clientHeight + 2 && getComputedStyle(el).overflow !== 'visible') issues.push('content overflows ' + el.className);
    }
    const body = s.querySelector('.body');
    if (body) { const b = body.getBoundingClientRect(); const kids = [...body.querySelectorAll('*')].map((e) => e.getBoundingClientRect().bottom);
      const maxB = Math.max(b.top, ...kids); if ((maxB - sr.top) / k > 1000) issues.push('body content runs into the footer (bottom ' + Math.round((maxB - sr.top) / k) + 'px)'); }
    const words = s.innerText.replace(/\\s+/g, '').length;
    res.slides.push({ slide: i + 1, chars: words, issues });
  });
  atelier.go(0, { instant: true });
  return res;
})()`;

/* ── phrase breaks for a source deck ──────────────────────────────── */

// The build adds phrase-aware CJK line breaks to the bundle only; give a source deck the same,
// so its Chinese lines wrap (and the lint measures them) the way dist/ will. Returns null for a
// built deck (data-inlined styles) or when there is nothing to add.
async function phraseSource(file) {
  const html = await fs.readFile(file, 'utf8');
  if (/<style\b[^>]*\bdata-inlined\b/i.test(html)) return null;
  const r = phraseBreaks(html, deckLang(html));
  if (!r.elements) return null;
  // an engine copy that predates phrase breaks lacks their CSS rule: add it, as the build does
  const sheets = await Promise.all([...html.matchAll(/<link\b[^>]*rel=["']stylesheet["'][^>]*>/gi)]
    .map((m) => m[0].match(/href=["']([^"']+)["']/i)?.[1])
    .filter((u) => u && !/^(https?:|data:|blob:|#|mailto:|\/\/)/i.test(u))
    .map((u) => fs.readFile(path.resolve(path.dirname(file), u), 'utf8').catch(() => '')));
  const ruled = [html, ...sheets].some((s) => s.includes('[data-phrase="auto"]'));
  return {
    html: ruled ? r.html : r.html.replace(/<\/head>/i, `<style data-phrase-css>${PHRASE_CSS}</style>\n</head>`),
    phrase: { model: r.model, elements: r.elements, breaks: r.breaks, glue: r.glue },
  };
}

/* ── main ─────────────────────────────────────────────────────────── */

const cdp = await launch();
let tmp = null; // the phrased copy of a source deck; removed on exit, on error and on Ctrl-C
try {
  await fs.mkdir(outDir, { recursive: true });
  const report = { out: outDir, files: [] };
  let deck = path.resolve(input);
  if (!argv.includes('--no-phrase')) {
    try {
      const p = await phraseSource(deck);
      if (p) {
        tmp = path.join(path.dirname(deck), `.snapshot-${process.pid}-${path.basename(deck)}`);
        for (const sig of ['SIGINT', 'SIGTERM']) process.once(sig, () => { rmSync(tmp, { force: true }); process.exit(128 + os.constants.signals[sig]); });
        await fs.writeFile(tmp, p.html);
        deck = tmp;
        report.phrase = p.phrase;
      }
    } catch (e) {
      console.error(`· phrase breaks skipped (${e.message}) — showing the source as is, where Chinese lines may break inside words; install uv, or pass --no-phrase to silence this`);
    }
  }
  const fileUrl = pathToFileURL(deck).href;
  const q = new URLSearchParams({ quiet: '1' });
  if (flag('theme')) q.set('theme', flag('theme'));
  if (flag('style')) q.set('style', flag('style'));
  if (flag('motion')) q.set('motion', flag('motion'));

  if (flag('styles')) {
    const registry = await loadStyles();
    const keys = flag('styles') === 'all' || flag('styles') === true ? Object.keys(registry) : String(flag('styles')).split(',');
    const rows = [];
    for (const key of keys) {
      if (!registry[key]) { console.error(`· unknown style ${key}`); continue; }
      const sq = new URLSearchParams(q);
      sq.set('style', key);
      if (!flag('theme') && registry[key].theme) sq.set('theme', registry[key].theme);   // show a style in its home theme
      const page = await openPage(cdp, `${fileUrl}?${sq}#1`);
      const n = await page.evaluate('atelier.count');
      const dir = path.join(outDir, key);
      await fs.mkdir(dir, { recursive: true });
      const files = [];
      for (const i of parseList(flag('slides') || '1-4', n)) {
        await page.evaluate(`atelier.go(${i}, { instant: true, step: 'all' }), atelier.settle(), true`);
        await page.evaluate(frames);
        files.push(await page.shot(path.join(dir, `slide-${String(i + 1).padStart(2, '0')}.png`)));
      }
      rows.push({ key, label: registry[key].name, files });
      report.files.push(...files);
    }
    report.gallery = await gallerySheet(cdp, rows, path.join(outDir, 'gallery.png'));
    console.log(JSON.stringify(report, null, 2));
    process.exitCode = 0;
  } else {

    if (flag('pdf')) {
      const pq = new URLSearchParams(q);
      pq.set('motion', 'off');
      const page = await openPage(cdp, `${fileUrl}?${pq}#1`);
      // Lay out every slide once so each face/weight the print needs is fetched before printing.
      await page.evaluate(`(async () => { atelier.overview(true); await document.fonts.ready;
        await Promise.all([...document.fonts].filter((f) => f.status !== 'unloaded' || /data:/.test(f.src || '')).map((f) => f.load().catch(() => {})));
        await document.fonts.ready; await new Promise((r) => setTimeout(r, 300)); atelier.overview(false); atelier.go(0, { instant: true }); atelier.settle(); return true; })()`);
      const { data } = await page.s('Page.printToPDF', { printBackground: true, preferCSSPageSize: true });
      const pdf = path.resolve(flag('pdf'));
      await fs.writeFile(pdf, Buffer.from(data, 'base64'));
      report.pdf = pdf;
    }

    const page = await openPage(cdp, `${fileUrl}?${q}#1`);
    const n = await page.evaluate('atelier.count');
    await page.evaluate('atelier.settle(), true');

    if (argv.includes('--check')) {
      report.check = await page.evaluate(LINT);
    }

    const film = flag('film');
    if (film) {
      const k = +film - 1;
      const times = String(flag('at', '0,180,420,750,1200,2200')).split(',').map(Number);
      await page.evaluate(`atelier.setMotion(true, { quiet: true }), atelier.go(${Math.max(0, k - 1)}, { instant: true, step: 'all' }), atelier.settle(), true`);
      await page.evaluate(frames);
      await page.evaluate(`atelier.go(${k}), true`);
      const shots = [];
      for (const t of times) {
        await page.evaluate(`atelier.freezeAt(${t}), true`);
        await page.evaluate(frames);
        shots.push(await page.shot(path.join(outDir, `film-${String(k + 1).padStart(2, '0')}-${String(t).padStart(4, '0')}ms.png`)));
      }
      await page.evaluate('atelier.resume(), atelier.settle(), true');
      report.files.push(...shots);
      report.filmSheet = await sheet(cdp, shots, path.join(outDir, `film-${String(k + 1).padStart(2, '0')}.png`), Math.min(3, shots.length));
    } else if (!argv.includes('--check') || flag('slides')) {
      const list = parseList(flag('slides'), n);
      const shots = [];
      for (const i of list) {
        if (argv.includes('--steps')) {
          const max = await page.evaluate(`atelier.maxStep(${i})`);
          for (let st = 0; st <= max; st++) {
            await page.evaluate(`atelier.go(${i}, { instant: true, step: ${st} }), atelier.settle(), true`);
            await page.evaluate(frames);
            shots.push(await page.shot(path.join(outDir, `slide-${String(i + 1).padStart(2, '0')}${max ? `-step${st}` : ''}.png`)));
          }
        } else {
          await page.evaluate(`atelier.go(${i}, { instant: true, step: 'all' }), atelier.settle(), true`);
          await page.evaluate(frames);
          shots.push(await page.shot(path.join(outDir, `slide-${String(i + 1).padStart(2, '0')}.png`)));
        }
      }
      report.files.push(...shots);
      if (shots.length > 1) report.sheet = await sheet(cdp, shots, path.join(outDir, 'sheet.png'), shots.length > 9 ? 4 : 3);
    }
    console.log(JSON.stringify(report, null, 2));
  }
} finally {
  await cdp.close();
  if (tmp) await fs.rm(tmp, { force: true });
}
