#!/usr/bin/env node
/* ============================================================================
   deck-atelier · set_style.mjs — switch a deck to another visual style.

     node scripts/set_style.mjs decks/<slug>/deck.html --style tokyo [--theme light|dark]
     node scripts/set_style.mjs --list

   Sets <html data-style> (and data-theme when given, or when the style prefers a
   theme), and rewrites the <link data-fonts> to that style's typefaces — keeping any
   family the deck added itself. Refreshes the deck's engine/ copy when it predates the
   style. Then re-run QA: widths differ between styles.
   ========================================================================== */
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { loadStyles, fontHref, familyParams, skillDir } from './styles.mjs';

const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf(`--${name}`);
  return i < 0 ? undefined : argv[i + 1];
};
const styles = await loadStyles();

if (argv.includes('--list')) {
  for (const [key, s] of Object.entries(styles)) console.log(`${key.padEnd(11)} ${s.name}${s.theme ? `  (prefers ${s.theme})` : ''}`);
  process.exit(0);
}

const file = argv.find((a, i) => !a.startsWith('--') && !['--style', '--theme'].includes(argv[i - 1]));
const style = flag('style');
if (!file || !style) {
  console.error('usage: node scripts/set_style.mjs <deck.html> --style <name> [--theme light|dark]   ·   --list');
  process.exit(1);
}
if (!styles[style]) {
  console.error(`unknown style "${style}" — one of: ${Object.keys(styles).join(', ')}`);
  process.exit(1);
}

const deck = path.resolve(file);
let html = await fs.readFile(deck, 'utf8');
const theme = flag('theme') || styles[style].theme;

html = html.replace(/<html\b([^>]*)>/i, (m, attrs) => {
  let a = attrs.replace(/\sdata-style="[^"]*"/, '');
  if (theme) a = a.replace(/\sdata-theme="[^"]*"/, '');
  a = a.replace(/(\slang="[^"]*")/, `$1 data-style="${style}"${theme ? ` data-theme="${theme}"` : ''}`);
  if (!/data-style=/.test(a)) a += ` data-style="${style}"${theme ? ` data-theme="${theme}"` : ''}`;
  return `<html${a}>`;
});

// fonts: the new style's families + whatever the deck added that no style provides
// (compared by family name; Instrument Serif and Inter belong to the pre-style engine)
const nameOf = (f) => f.split(':')[0];
const known = new Set([...Object.values(styles).flatMap((s) => familyParams(s.fonts).map(nameOf)), 'Instrument Serif', 'Inter']);
const link = html.match(/<link\b[^>]*\bdata-fonts\b[^>]*>/i)?.[0];
const extra = link ? familyParams(link.match(/href="([^"]+)"/i)?.[1] || '').filter((f) => !known.has(nameOf(f))) : [];
const spec = [styles[style].fonts, ...extra.map((f) => `family=${encodeURIComponent(f).replace(/%20/g, '+').replace(/%3A/gi, ':').replace(/%2C/gi, ',').replace(/%40/gi, '@').replace(/%3B/gi, ';')}`)].join('&');
const newLink = `<link rel="stylesheet" data-fonts href="${fontHref(spec, { html: true })}">`;
html = link ? html.replace(link, newLink) : html.replace(/(<link\b[^>]*engine\/atelier\.css[^>]*>)/i, `${newLink}\n$1`);
await fs.writeFile(deck, html);

// the deck's own engine copy must know the style
const engineCss = path.join(path.dirname(deck), 'engine/atelier.css');
let engine = 'not found (deck links the skill engine directly?)';
if (existsSync(engineCss)) {
  const css = await fs.readFile(engineCss, 'utf8');
  if (css.includes(`[data-style="${style}"]`)) engine = 'already has the style';
  else {
    for (const f of ['atelier.css', 'atelier.js']) await fs.copyFile(path.join(skillDir, 'assets/engine', f), path.join(path.dirname(engineCss), f));
    engine = 'refreshed from the skill (it predated this style)';
  }
}

console.log(JSON.stringify({ deck, style, name: styles[style].name, theme: theme || '(unchanged)', extraFamilies: extra, engine,
  next: `node ${path.join(skillDir, 'scripts/snapshot.mjs')} ${deck} --out ${path.join(path.dirname(deck), 'qa')} --check --slides 1-99` }, null, 2));
