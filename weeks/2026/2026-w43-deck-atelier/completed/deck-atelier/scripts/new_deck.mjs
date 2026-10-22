#!/usr/bin/env node
/* ============================================================================
   deck-atelier · new_deck.mjs — scaffold a deck folder.

     node scripts/new_deck.mjs decks/<slug> [--title "…"] [--subtitle "…"]
                               [--lang zh-Hant-TW] [--style swiss] [--theme light|dark] [--force]
     node scripts/new_deck.mjs --styles                         list the visual styles
     node scripts/new_deck.mjs decks/<slug> --update-engine     refresh engine/ only

   Writes decks/<slug>/deck.html (from assets/templates/starter.html), copies the
   runtime into decks/<slug>/engine/, and creates source/, assets/ and storyline.md.
   Each deck keeps its own engine copy, so later engine changes never break it.
   ========================================================================== */
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadStyles } from './styles.mjs';

const skill = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const argv = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  if (i < 0) return dflt;
  const v = argv[i + 1];
  return v && !v.startsWith('--') ? v : true;
};
const VALUE_FLAGS = new Set(['--title', '--subtitle', '--lang', '--theme', '--style']);
const STYLES = await loadStyles();
if (argv.includes('--styles')) {
  for (const [key, st] of Object.entries(STYLES)) console.log(`${key.padEnd(11)} ${st.name}${st.theme ? `  (prefers ${st.theme})` : ''}`);
  process.exit(0);
}
const dirArg = argv.find((a, i) => !a.startsWith('--') && !VALUE_FLAGS.has(argv[i - 1]));
if (!dirArg) {
  console.error('usage: node scripts/new_deck.mjs decks/<slug> [--title "…"] [--lang zh-Hant-TW] [--style <name>] [--theme light|dark] [--force] [--update-engine] · --styles lists the styles');
  process.exit(1);
}
const dir = path.resolve(dirArg);
const slug = path.basename(dir);
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

async function copyEngine() {
  const engine = path.join(dir, 'engine');
  const stat = await fs.lstat(engine).catch(() => null);
  if (stat?.isSymbolicLink()) await fs.unlink(engine);
  await fs.mkdir(engine, { recursive: true });
  for (const f of ['atelier.css', 'atelier.js']) {
    await fs.copyFile(path.join(skill, 'assets/engine', f), path.join(engine, f));
  }
  return engine;
}

if (argv.includes('--update-engine')) {
  const engine = await copyEngine();
  console.log(JSON.stringify({ updated: engine }, null, 2));
  process.exit(0);
}

const deckFile = path.join(dir, 'deck.html');
if (existsSync(deckFile) && !argv.includes('--force')) {
  console.error(`${deckFile} already exists — use --force to overwrite, or --update-engine to refresh the runtime only.`);
  process.exit(1);
}

const title = String(flag('title', slug.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())));
const subtitle = String(flag('subtitle', '一句話說明這場簡報為什麼值得聽'));
const lang = String(flag('lang', 'zh-Hant-TW'));
const style = String(flag('style', 'swiss'));
if (!STYLES[style]) {
  console.error(`unknown --style ${style} — one of: ${Object.keys(STYLES).join(', ')}`);
  process.exit(1);
}
const theme = String(flag('theme', STYLES[style].theme || 'light')).replace(/^ivory$/, 'light').replace(/^noir$/, 'dark');

await fs.mkdir(path.join(dir, 'source'), { recursive: true });
await fs.mkdir(path.join(dir, 'assets'), { recursive: true });
await copyEngine();

let html = await fs.readFile(path.join(skill, 'assets/templates/starter.html'), 'utf8');
html = html
  .replaceAll('{{TITLE}}', esc(title))
  .replaceAll('{{SUBTITLE}}', esc(subtitle))
  .replaceAll('{{LANG}}', esc(lang))
  .replaceAll('{{THEME}}', esc(theme))
  .replaceAll('{{STYLE}}', esc(style))
  .replaceAll('{{FONTS}}', STYLES[style].fonts.replace(/&/g, '&amp;'));
await fs.writeFile(deckFile, html);

const story = path.join(dir, 'storyline.md');
if (!existsSync(story)) {
  await fs.writeFile(story, `# ${title}
Audience: … · Occasion: … · Length: N slides / M minutes · Language: ${lang} · Style: ${style}
Governing thought: …
SCQA: S … / C … / Q … / A …

| # | Chapter | Action title | Layout | Exhibit / visual | Source |
|---|---|---|---|---|---|
| 1 | — | (cover) ${title} | cover | … | — |
| 2 | 摘要 | … | points ×3 | — | … |
`);
}

console.log(JSON.stringify({
  deck: deckFile,
  next: [
    `uv run ${path.join(skill, 'scripts/ingest.py')} <source> --out ${path.join(dir, 'source')}`,
    `write ${story}, then compose ${deckFile}`,
    `node ${path.join(skill, 'scripts/snapshot.mjs')} ${deckFile} --out ${path.join(dir, 'qa')} --check --slides 1-99`,
    `node ${path.join(skill, 'scripts/build.mjs')} ${deckFile}`,
  ],
}, null, 2));
