import { readdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
async function walk(url) {
  const result = [];
  for (const entry of await readdir(url, { withFileTypes: true })) {
    if (['dist', 'node_modules', '.git'].includes(entry.name)) continue;
    const child = new URL(entry.name + (entry.isDirectory() ? '/' : ''), url);
    if (entry.isDirectory()) result.push(...await walk(child));
    else if (/\.(mjs|js)$/.test(entry.name)) result.push(fileURLToPath(child));
  }
  return result;
}
function run(args) {
  const result = spawnSync(process.execPath, args, { cwd: root, stdio: 'inherit' });
  if (result.error || result.status !== 0) process.exit(result.status || 1);
}
const files = await walk(new URL('../', import.meta.url));
for (const file of files) run(['--check', file]);
console.log(`Syntax: ${files.length} files passed`);
run(['--test', 'tests/privacy.test.mjs', 'tests/relay-runtime.test.mjs', 'tests/package.test.mjs']);
