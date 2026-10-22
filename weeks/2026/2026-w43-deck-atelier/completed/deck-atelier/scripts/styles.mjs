/* ============================================================================
   deck-atelier · styles.mjs — the style registry, shared by the scripts.

   The registry lives in assets/engine/atelier.js (the browser needs it for Y / ?style=),
   between the `registry` comment markers, as JSON. This module reads it so
   new_deck.mjs, set_style.mjs and snapshot.mjs never keep a second copy.
   ========================================================================== */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const skillDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export async function loadStyles(engineJs = path.join(skillDir, 'assets/engine/atelier.js')) {
  const js = await fs.readFile(engineJs, 'utf8');
  const m = js.match(/\/\*registry\*\/([\s\S]*?)\/\*\/registry\*\//);
  if (!m) throw new Error(`no style registry in ${engineJs}`);
  return JSON.parse(m[1]);
}

/** Google Fonts stylesheet URL for a registry `fonts` spec (HTML-escaped when `html`). */
export function fontHref(spec, { html = false } = {}) {
  const url = `https://fonts.googleapis.com/css2?${spec}&display=swap`;
  return html ? url.replace(/&/g, '&amp;') : url;
}

/** The `family=…` parameters of a spec or of a Google Fonts URL, decoded. */
export function familyParams(specOrUrl) {
  const q = specOrUrl.replace(/&amp;/g, '&').replace(/^[^?]*\?/, '');
  return new URLSearchParams(q).getAll('family');
}
