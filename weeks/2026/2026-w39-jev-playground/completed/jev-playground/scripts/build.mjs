import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';
const project = new URL('../', import.meta.url);
const index = process.argv.indexOf('--out');
if (index !== -1 && !process.argv[index + 1]) throw new Error('--out requires a directory');
const output = index === -1 ? fileURLToPath(new URL('dist/server/', project)) : resolve(process.argv[index + 1]);
const files = { 'index.html': 'text/html', 'styles.css': 'text/css', 'app.js': 'text/javascript', 'session.mjs': 'text/javascript', 'lib/engine.mjs': 'text/javascript', 'lib/brain.mjs': 'text/javascript', 'favicon.svg': 'image/svg+xml' };
const assets = {};
for (const [name, type] of Object.entries(files)) {
  assets[name === 'index.html' ? '/' : `/${name}`] = { type: `${type}; charset=utf-8`, body: await readFile(new URL(`public/${name}`, project), 'utf8') };
}
const source = await readFile(new URL('worker.mjs', project), 'utf8');
await mkdir(output, { recursive: true });
await writeFile(join(output, 'index.js'), `const ASSETS = ${JSON.stringify(assets)};\n${source}\nexport default createWorker(ASSETS);\n`);
await writeFile(join(output, 'package.json'), '{"type":"module"}\n');
console.log(`Built ${Object.keys(assets).length} public assets and stateless Jev relay: ${output}`);
