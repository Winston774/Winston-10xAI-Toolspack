import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { createStudio } from '../server/index.mjs';

test('選用本機 GPU 時，以聲音描述產生全新人聲', { skip: process.env.STUDIO_TEST_LOCAL_BREEZE !== '1' }, async t => {
  const root = path.resolve(os.tmpdir());
  const dataDir = await mkdtemp(path.join(root, 'studio-local-voice-test-'));
  const studio = createStudio({ dataDir });
  await new Promise(resolve => studio.server.listen(0, '127.0.0.1', resolve));
  t.after(async () => {
    await studio.close();
    if (path.dirname(dataDir) === root && path.basename(dataDir).startsWith('studio-local-voice-test-')) {
      await rm(dataDir, { recursive: true, force: true });
    }
  });
  const baseUrl = 'http://127.0.0.1:' + studio.server.address().port;
  async function request(route, body) {
    const options = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    const r = await fetch(baseUrl + route, options);
    const result = await r.json();
    assert.ok(r.ok, result.error);
    return result;
  }
  const { character } = await request('/api/characters', { name: '測試角色' });
  let { job } = await request('/api/jobs', { type: 'voice', characterId: character.id,
    provider: 'breeze', text: '你好，歡迎來到攝影棚。', voiceInstruction: '自然清晰的台灣華語女聲，語氣親切。' });
  const deadline = Date.now() + 15 * 60 * 1000;
  while (['queued', 'running'].includes(job.status) && Date.now() < deadline) {
    await delay(1500);
    ({ job } = await request('/api/jobs/' + job.id));
  }
  assert.equal(job.status, 'succeeded', job.error || job.progress);
  const media = await fetch(baseUrl + job.url);
  assert.ok(media.ok);
  const audio = Buffer.from(await media.arrayBuffer());
  assert.equal(audio.toString('ascii', 8, 12), 'WAVE');
  const sampleRate = audio.readUInt32LE(24);
  assert.equal(audio.readUInt16LE(22), 1);
  const bytesPerSecond = audio.readUInt32LE(28);
  const duration = audio.readUInt32LE(audio.indexOf(Buffer.from('data')) + 4) / bytesPerSecond;
  assert.ok(duration > 0.1 && duration < 60);
  t.diagnostic(`Breeze WAV ${sampleRate} Hz / mono / ${duration.toFixed(2)} s`);
});
