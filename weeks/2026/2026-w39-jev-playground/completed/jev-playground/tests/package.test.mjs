import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

test('portable build works without personal hosting metadata and serves only allowed assets', async () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const temporary = await mkdtemp(join(tmpdir(), 'w39-jev-build-'));
  try {
    const built = spawnSync(process.execPath, ['scripts/build.mjs', '--out', temporary], { cwd: root, encoding: 'utf8' });
    assert.equal(built.status, 0, built.stderr);
    assert.deepEqual((await readdir(temporary)).sort(), ['index.js', 'package.json']);
    const content = await readFile(join(temporary, 'index.js'), 'utf8');
    assert.doesNotMatch(content, /appgprj_|TYPESAFE_API_KEY|gmail-1000|D:\\\\Codex/);
    const { default: worker } = await import(pathToFileURL(join(temporary, 'index.js')).href);
    for (const path of ['/', '/styles.css', '/app.js', '/session.mjs', '/lib/engine.mjs', '/lib/brain.mjs', '/favicon.svg']) {
      const response = await worker.fetch(new Request('http://127.0.0.1:4321' + path));
      assert.equal(response.status, 200);
      assert.equal(response.headers.get('cache-control'), 'no-store');
    }
    for (const path of ['/.env', '/.openai/hosting.json', '/package.json', '/tests/privacy.test.mjs']) {
      assert.equal((await worker.fetch(new Request('http://127.0.0.1:4321' + path))).status, 404);
    }
    const { createSession } = await import('../public/session.mjs');
    const session = createSession({ previewDelayMs: 0, fetchImpl: () => { throw new Error('No network allowed'); } });
    const before = await session.request('/api/state');
    await session.request('/api/step', { mode: 'preview', version: before.game.version });
    assert.equal((await session.request('/api/state')).game.pieces, 1);
    assert.equal(session.export().sessionStats.calls, 0);
    session.dispose();
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});
