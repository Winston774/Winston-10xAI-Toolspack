import test from 'node:test';
import assert from 'node:assert/strict';
import { createWorker } from '../worker.mjs';

function incoming() {
  const origin = 'https://playground.example';
  return new Request(`${origin}/api/jev`, { method: 'POST', headers: { origin, authorization: 'Bearer TEST_ONLY_INVALID_RUNTIME_KEY', 'content-type': 'application/json' }, body: JSON.stringify({ model: 'jev-latest', state: { board: Array(20).fill('..........') }, questions: { sense: { type: 'noul', instructions: 'Assess board', criteria: { true: 'yes', false: 'no' } } } }) });
}

test('relay uses the redirect mode supported by Cloudflare fetch', async () => {
  const worker = createWorker({}, async (_url, options) => {
    // Cloudflare rejects redirect:error before any network request is sent.
    if (!['follow', 'manual'].includes(options.redirect)) throw new TypeError('Invalid redirect value: error is unsupported at the edge');
    assert.equal(options.redirect, 'manual', 'visitor credentials must never follow upstream redirects');
    return new Response(null, { status: 401 });
  });
  const response = await worker.fetch(incoming());
  assert.equal(response.status, 401, 'invalid credentials must reach provider authentication, not a relay runtime failure');
  assert.deepEqual(await response.json(), { error: 'JEV_REQUEST_FAILED' });
});

test('upstream redirects are rejected without forwarding credentials or exposing Location', async () => {
  const calls = [];
  const response = await createWorker({}, async (url, options) => {
    calls.push({ url, redirect: options.redirect });
    return new Response(null, { status: 302, headers: { location: 'https://untrusted.example/collect' } });
  }).fetch(incoming());
  assert.deepEqual(calls, [{ url: 'https://api.typesafe.ai/v1/systemone', redirect: 'manual' }]);
  assert.equal(response.status, 502); assert.equal(response.headers.has('location'), false);
  assert.deepEqual(await response.json(), { error: 'JEV_REQUEST_FAILED' });
});

test('relay forwards requests when Cloudflare incoming Request.signal is unavailable', async t => {
  const nativeTimeout = globalThis.setTimeout, timers = [];
  t.mock.method(globalThis, 'setTimeout', (...args) => { const timer = nativeTimeout(...args); timers.push(timer); return timer; });
  const request = incoming(); Object.defineProperty(request, 'signal', { value: undefined });
  let calls = 0;
  try {
    const response = await createWorker({}, async (_url, options) => {
      calls++; assert.ok(options.signal instanceof AbortSignal);
      return new Response(null, { status: 401 });
    }).fetch(request);
    assert.equal(response.status, 401, 'must reach upstream auth instead of throwing a relay 502');
    assert.equal(calls, 1);
    assert.deepEqual(await response.json(), { error: 'JEV_REQUEST_FAILED' });
  } finally { for (const timer of timers) clearTimeout(timer); }
});

test('supported incoming cancellation still aborts the upstream request', async () => {
  const request = incoming(), aborter = new AbortController();
  Object.defineProperty(request, 'signal', { value: aborter.signal });
  let started; const entered = new Promise(resolve => { started = resolve; });
  let upstreamSignal;
  const task = createWorker({}, async (_url, options) => {
    upstreamSignal = options.signal; started();
    return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }));
  }).fetch(request);
  await entered; aborter.abort();
  assert.equal((await task).status, 502); assert.equal(upstreamSignal.aborted, true);
});
