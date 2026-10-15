import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

const source = (await readFile(new URL('../extension/offscreen.js', import.meta.url), 'utf8')).replace(/^import .*;\r?\n/gm, '');

function harness() {
  let listener;
  const clip = { id: 'current', name: 'current.mp4', blob: new Blob(['fixture']) };
  const created = [], revoked = [];
  const root = 'chrome-extension://fixture/';
  const context = vm.createContext({
    getClip: async () => clip,
    URL: {
      createObjectURL(blob) { created.push(blob); return `blob:fixture/${created.length}`; },
      revokeObjectURL(url) { revoked.push(url); },
    },
    chrome: { runtime: { id: 'fixture', getURL: name => root + name, onMessage: { addListener(fn) { listener = fn; } } } },
  });
  vm.runInContext(source, context);
  const request = message => new Promise(resolve => listener({ target: 'offscreen', ...message }, { id: 'fixture', url: root + 'background.js' }, resolve));
  return { request, clip, created, revoked };
}

test('download request bound to an older clip cannot silently save the replacement', async () => {
  const h = harness();
  const result = await h.request({ type: 'VC_OFF_DOWNLOAD', id: 'older' });
  assert.equal(result.ok, false);
  assert.match(result.error, /快取已更新/);
  assert.equal(h.created.length, 0);
  assert.equal(h.clip.id, 'current');
});

test('separate downloads retain independent URLs and release only their own blob', async () => {
  const h = harness();
  const first = await h.request({ type: 'VC_OFF_DOWNLOAD', id: 'current' });
  const second = await h.request({ type: 'VC_OFF_DOWNLOAD', id: 'current' });
  assert.equal(first.ok, true);
  assert.equal(first.name, 'current.mp4');
  assert.notEqual(first.url, second.url);
  assert.deepEqual(h.revoked, []);
  await h.request({ type: 'VC_OFF_REVOKE', url: first.url });
  await h.request({ type: 'VC_OFF_REVOKE', url: first.url });
  await h.request({ type: 'VC_OFF_REVOKE', url: 'blob:unknown' });
  assert.deepEqual(h.revoked, [first.url]);
  await h.request({ type: 'VC_OFF_REVOKE', url: second.url });
  assert.deepEqual(h.revoked, [first.url, second.url]);
  assert.equal(h.clip.id, 'current');
});
