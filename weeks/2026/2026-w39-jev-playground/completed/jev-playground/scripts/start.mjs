import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const major = Number(process.versions.node.split('.')[0]);
const minor = Number(process.versions.node.split('.')[1]);
if (major < 20 || (major === 20 && minor < 3)) {
  console.error('Node.js 20.3 or newer is required.'); process.exit(1);
}
const build = spawnSync(process.execPath, [fileURLToPath(new URL('build.mjs', import.meta.url))], { stdio: 'inherit' });
if (build.error || build.status !== 0) process.exit(build.status || 1);
await import('./preview.mjs');
