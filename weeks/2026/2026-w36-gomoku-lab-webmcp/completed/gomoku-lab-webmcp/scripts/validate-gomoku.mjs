import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const htmlUrl = new URL('../public/gomoku.html', import.meta.url);
const pageUrl = new URL('../app/page.tsx', import.meta.url);
const html = await readFile(htmlUrl, 'utf8');
const page = await readFile(pageUrl, 'utf8');

const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
  .map((match) => match[1])
  .filter((source) => source.trim().length > 0);

assert.ok(scripts.length > 0, 'public/gomoku.html must contain an inline script');
for (const [index, source] of scripts.entries()) {
  new vm.Script(source, { filename: `gomoku-inline-${index + 1}.js` });
}

const expectedTools = [
  'get_board_state',
  'highlight_cells',
  'draw_variation',
  'clear_analysis',
  'publish_agent_decision',
  'place_stone',
  'request_new_game',
  'get_audit_log',
];

for (const tool of expectedTools) {
  assert.match(html, new RegExp(`name:['"]${tool}['"]`), `missing tool: ${tool}`);
}

const toolDefinitions = html.match(/defineTool\(\{name:/g) ?? [];
assert.equal(toolDefinitions.length, expectedTools.length, 'unexpected WebMCP tool count');
assert.match(html, /document\.modelContext\.registerTool/, 'missing native WebMCP registration');
assert.match(html, /decision\.expectedVersion!==state\.version/, 'place_stone must reject stale decisions');
assert.match(html, /decision\.row!==args\.row\|\|decision\.col!==args\.col/, 'place_stone must match the published move');
assert.match(page, /redirect\(['"]\/gomoku\.html['"]\)/, 'homepage must redirect to the standalone board');

console.log(`Gomoku contract validation passed: ${expectedTools.length} tools, ${scripts.length} inline script(s).`);
