import test from 'node:test';
import assert from 'node:assert/strict';
import { CHUNK_BYTES, isSourcePage, isFacebookPage, isReceiverPage, validateMediaUrl, validateChunk, fetchVideo } from '../extension/policy.js';

const THREADS_PAGE = 'https://www.threads.com/@example/post/fixture';
const X_PAGE = 'https://x.com/example/status/123';
const THREADS_MEDIA = 'https://video.example.fbcdn.net/clip.mp4';
const X_MEDIA = 'https://video.twimg.com/clip.mp4';
// This is a small ftyp fixture for transport validation, not a playable video.
const MP4 = Uint8Array.from([0, 0, 0, 24, 102, 116, 121, 112, 105, 115, 111, 109, 0, 0, 0, 1, 105, 115, 111, 109, 109, 112, 52, 49]);

function responseFor(chunks, { status = 200, headers = {}, onCancel = () => {} } = {}) {
  let index = 0;
  return new Response(new ReadableStream({
    pull(controller) {
      if (index < chunks.length) controller.enqueue(chunks[index++]);
      else controller.close();
    },
    cancel: onCancel,
  }, { highWaterMark: 0 }), { status, headers });
}

const fetchResponse = (response) => async () => response;

test('only supported Facebook and Threads origins may read cached video bytes', () => {
  for (const host of ['www.facebook.com', 'threads.com', 'www.threads.com', 'threads.net', 'www.threads.net']) {
    assert.equal(isReceiverPage(`https://${host}/`), true, host);
    for (const url of [`https://${host}.attacker.invalid/`, `https://user@${host}/`, `https://${host}:8443/`, `http://${host}/`]) {
      assert.equal(isReceiverPage(url), false, url);
    }
  }
  for (const url of [X_PAGE, 'https://messenger.com/', 'https://business.facebook.com/', 'https://evilthreads.com/', 'not a URL']) {
    assert.equal(isReceiverPage(url), false, url);
  }
});

test('source and destination permissions reject lookalike hosts, credentials, ports and insecure URLs', () => {
  assert.equal(isSourcePage(THREADS_PAGE), true);
  assert.equal(isSourcePage(X_PAGE), true);
  assert.equal(isFacebookPage('https://www.facebook.com/'), true);
  for (const url of [
    'https://x.com.attacker.invalid/post',
    'https://threads.com.attacker.invalid/post',
    'https://evilthreads.com/post',
    'https://x.com@attacker.invalid/post',
    'https://user:password@x.com/post',
    'https://x.com:8443/post',
    'http://x.com/post',
    'not a URL',
  ]) assert.equal(isSourcePage(url), false, url);
  for (const url of ['https://www.facebook.com.attacker.invalid/', 'https://www.facebook.com:8443/', 'https://user@www.facebook.com/', 'http://www.facebook.com/']) {
    assert.equal(isFacebookPage(url), false, url);
  }
});

test('media hosts must belong to the selected source platform', () => {
  assert.equal(validateMediaUrl(THREADS_MEDIA, THREADS_PAGE), THREADS_MEDIA);
  assert.equal(validateMediaUrl(X_MEDIA, X_PAGE), X_MEDIA);
  assert.equal(validateMediaUrl('https://scontent.cdninstagram.com/video.mp4', THREADS_PAGE), 'https://scontent.cdninstagram.com/video.mp4');
  for (const url of ['https://video.twimg.com.attacker.invalid/v.mp4', 'https://eviltwimg.com/v.mp4', THREADS_MEDIA]) {
    assert.throws(() => validateMediaUrl(url, X_PAGE), /支援媒體主機/, url);
  }
  assert.throws(() => validateMediaUrl(X_MEDIA, THREADS_PAGE), /支援媒體主機/);
  assert.throws(() => validateMediaUrl(X_MEDIA, 'https://x.com.attacker.invalid/'), /來源頁面/);
});

test('blob, insecure, authenticated, custom-port, HLS and DASH media fail before fetching', async () => {
  for (const url of [
    'blob:https://x.com/1234',
    'http://video.twimg.com/v.mp4',
    'https://user:pass@video.twimg.com/v.mp4',
    'https://video.twimg.com:8443/v.mp4',
    'https://video.twimg.com/playlist.m3u8?token=fixture',
    'https://video.twimg.com/manifest.MPD',
    'https://video.twimg.com/path.m3u8/child',
  ]) {
    let requested = false;
    await assert.rejects(fetchVideo(url, X_PAGE, { fetchImpl: async () => { requested = true; throw new Error('unexpected fetch'); } }), /HTTPS|分段串流/);
    assert.equal(requested, false, url);
  }
});

test('signed query order and escaping are preserved while URL fragments are discarded', () => {
  const signed = 'https://video.twimg.com/v.mp4?token=A%2FB%2B%3D&sig=a+b&x=1&x=2&empty=';
  assert.equal(validateMediaUrl(`${signed}#ignored`, X_PAGE), signed);
});

test('fetch returns complete MP4 bytes across uneven chunks without credentials or redirects', async () => {
  const progress = [];
  const signed = `${X_MEDIA}?signature=test%2Fvalue%3D&other=a+b`;
  let request;
  const blob = await fetchVideo(signed, X_PAGE, {
    fetchImpl: async (url, options) => {
      request = { url, options };
      return responseFor([MP4.slice(0, 3), MP4.slice(3, 9), MP4.slice(9)], { headers: { 'content-length': String(MP4.length), 'content-type': 'application/octet-stream' } });
    },
    onProgress: (bytes, expected) => progress.push({ bytes, expected }),
  });
  assert.equal(request.url, signed);
  assert.equal(request.options.credentials, 'omit');
  assert.equal(request.options.redirect, 'error');
  assert.equal(request.options.cache, 'no-store');
  assert.equal(request.options.signal.aborted, false);
  assert.equal(blob.type, 'video/mp4');
  assert.equal(blob.size, MP4.length);
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), MP4);
  assert.ok(progress.length >= 1);
  assert.equal(progress[0].expected, MP4.length);
});

test('HTML served as video/mp4 is rejected instead of cached as a video', async () => {
  const html = new TextEncoder().encode('<html><body>Login required</body></html>');
  await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(responseFor([html], { headers: { 'content-type': 'video/mp4' } })) }), /MP4/);
});

for (const status of [206, 403]) {
  test(`HTTP ${status} is rejected even when the response contains an MP4 header`, async () => {
    await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(responseFor([MP4], { status })) }), new RegExp(`HTTP ${status}`));
  });
}

test('truncated and surplus bodies both fail Content-Length integrity checks', async () => {
  for (const length of [MP4.length - 1, MP4.length + 1]) {
    await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(responseFor([MP4], { headers: { 'content-length': String(length) } })) }), /下載不完整/);
  }
});

test('invalid or over-limit Content-Length is rejected before reading the body', async () => {
  for (const length of ['0', '-1', 'abc', '1.5', '9007199254740992', '25']) {
    let reads = 0;
    const body = new ReadableStream({ pull(controller) { reads++; controller.enqueue(MP4); controller.close(); } }, { highWaterMark: 0 });
    await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { maxBytes: MP4.length, fetchImpl: fetchResponse(new Response(body, { headers: { 'content-length': length } })) }), /上限/);
    assert.equal(reads, 0, length);
  }
});

test('an exact-cap stream succeeds without Content-Length', async () => {
  const blob = await fetchVideo(X_MEDIA, X_PAGE, { maxBytes: MP4.length, fetchImpl: fetchResponse(responseFor([MP4.slice(0, 12), MP4.slice(12)])) });
  assert.deepEqual(new Uint8Array(await blob.arrayBuffer()), MP4);
});

test('a stream exceeding the cap aborts and cancels even with absent or underreported length', async () => {
  for (const headers of [{}, { 'content-length': String(MP4.length) }]) {
    let cancelled = false;
    let signal;
    const response = responseFor([MP4, Uint8Array.of(1)], { headers, onCancel: () => { cancelled = true; } });
    await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, {
      maxBytes: MP4.length,
      fetchImpl: async (_url, options) => { signal = options.signal; return response; },
    }), /上限/);
    assert.equal(signal.aborted, true);
    assert.equal(cancelled, true);
  }
});

test('empty responses and bodies missing altogether produce actionable errors', async () => {
  await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(responseFor([])) }), /下載不完整/);
  await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(new Response(null)) }), /沒有取得影片資料/);
});

test('network failures become a user-facing error and abort the request', async () => {
  let signal;
  await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: async (_url, options) => {
    signal = options.signal;
    throw new TypeError('Failed to fetch');
  } }), /無法取得影片/);
  assert.equal(signal.aborted, true);
});

test('a disconnected body cancels the reader and reports an actionable failure', async () => {
  let cancelled = false;
  const response = {
    status: 200,
    headers: new Headers(),
    body: { getReader: () => ({
      read: async () => { throw new TypeError('Connection reset'); },
      cancel: async () => { cancelled = true; },
    }) },
  };
  await assert.rejects(fetchVideo(X_MEDIA, X_PAGE, { fetchImpl: fetchResponse(response) }), /無法取得影片/);
  assert.equal(cancelled, true);
});

test('chunk requests accept bounded reads and reject oversized or non-integer requests', () => {
  assert.doesNotThrow(() => validateChunk(0, CHUNK_BYTES, CHUNK_BYTES * 2));
  assert.doesNotThrow(() => validateChunk(CHUNK_BYTES, 1, CHUNK_BYTES + 1));
  for (const [offset, length, size] of [
    [-1, 1, 10], [11, 1, 10], [0.5, 1, 10], [NaN, 1, 10], [Infinity, 1, 10],
    ['0', 1, 10], [0, 0, 10], [0, -1, 10], [0, 1.5, 10], [0, NaN, 10],
    [0, Infinity, 10], [0, '1', 10], [0, CHUNK_BYTES + 1, CHUNK_BYTES * 2],
    [Number.MAX_SAFE_INTEGER + 1, 1, Number.MAX_SAFE_INTEGER + 1],
  ]) assert.throws(() => validateChunk(offset, length, size), /分塊讀取參數/);
});
