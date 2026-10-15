import test, { before, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

const SOURCE_PAGE = 'https://x.com/example/status/123';
const MEDIA_URL = 'https://video.twimg.com/clip.mp4';
const EXTENSION_ID = 'video-bridge-test';
const POPUP_URL = `chrome-extension://${EXTENSION_ID}/popup.html`;
const OFFSCREEN_URL = `chrome-extension://${EXTENSION_ID}/offscreen.html`;

const state = {
  contexts: [],
  createdMenus: [],
  removedMenus: 0,
  installed: null,
  startup: null,
  contextClick: null,
  message: null,
  downloadChanged: null,
  offscreenMessages: [],
  offscreenHandler: async () => ({ ok: true }),
  tabsMessages: [],
  tabCandidate: { ok: true, pageUrl: SOURCE_PAGE, url: MEDIA_URL },
  xPageResponse: () => ({ ok: false, error: 'not found' }),
  downloadCalls: [],
  downloadState: 'in_progress',
  downloadSearchImpl: async () => [{ state: state.downloadState }],
  failDownloadSession: false,
  downloadId: 1,
  downloadImpl: async () => state.downloadId++,
  badges: [],
  session: new Map(),
  metadata: null,
  clip: null,
};

function resetState() {
  state.contexts = [];
  state.createdMenus = [];
  state.removedMenus = 0;
  state.offscreenMessages = [];
  state.offscreenHandler = async message => {
    if (message.type === 'VC_OFF_PREPARE') {
      const clip = { id: `clip-${state.downloadId}`, name: 'x.mp4', size: 4, mime: 'video/mp4' };
      state.metadata = clip;
      state.clip = { ...clip, blob: new Blob([Uint8Array.of(0, 1, 2, 3)]) };
      return { ok: true, clip, warning: null };
    }
    if (message.type === 'VC_OFF_DOWNLOAD') return { ok: true, url: `blob:download-${message.id}`, name: 'x.mp4' };
    return { ok: true };
  };
  state.tabsMessages = [];
  state.tabCandidate = { ok: true, pageUrl: SOURCE_PAGE, url: MEDIA_URL };
  state.xPageResponse = () => ({ ok: false, error: 'not found' });
  state.downloadCalls = [];
  state.downloadState = 'in_progress';
  state.downloadSearchImpl = async () => [{ state: state.downloadState }];
  state.failDownloadSession = false;
  state.downloadId = 1;
  state.downloadImpl = async () => state.downloadId++;
  state.badges = [];
  state.session.clear();
  state.metadata = null;
  state.clip = null;
}

function makeEvent() {
  let listener;
  return {
    addListener(callback) { listener = callback; },
    get listener() { return listener; },
  };
}

function installChromeMock() {
  const onInstalled = makeEvent();
  const onStartup = makeEvent();
  const onContextClicked = makeEvent();
  const onMessage = makeEvent();
  const onDownloadChanged = makeEvent();
  state.installed = onInstalled;
  state.startup = onStartup;
  state.contextClick = onContextClicked;
  state.message = onMessage;
  state.downloadChanged = onDownloadChanged;

  const session = {
    async get(key) {
      if (typeof key === 'string') return { [key]: state.session.get(key) };
      if (key && typeof key === 'object') return Object.fromEntries(Object.keys(key).map(name => [name, state.session.get(name) ?? key[name]]));
      return Object.fromEntries(state.session);
    },
    async set(values) {
      if (state.failDownloadSession && Object.keys(values).some(key => key.startsWith('download:'))) throw new Error('session unavailable');
      for (const [key, value] of Object.entries(values)) state.session.set(key, value);
    },
    async remove(key) { state.session.delete(key); },
  };

  globalThis.chrome = {
    runtime: {
      id: EXTENSION_ID,
      getURL(name) { return `chrome-extension://${EXTENSION_ID}/${name}`; },
      async getContexts() { return state.contexts; },
      async sendMessage(message) {
        if (message?.target !== 'offscreen') return undefined;
        state.offscreenMessages.push(message);
        return state.offscreenHandler(message);
      },
      onInstalled,
      onStartup,
      onMessage,
    },
    offscreen: { async createDocument() { state.contexts = [{ contextType: 'OFFSCREEN_DOCUMENT', documentUrl: OFFSCREEN_URL }]; } },
    contextMenus: {
      onClicked: onContextClicked,
      async removeAll() { state.removedMenus++; state.createdMenus = []; },
      create(menu) { state.createdMenus.push({ ...menu }); },
    },
    storage: { session },
    tabs: {
      async sendMessage(tabId, message) {
        state.tabsMessages.push({ tabId, message });
        if (message.type === 'VC_GET_SOURCE') return state.tabCandidate;
        if (message.type === 'VC_RESOLVE_X_PAGE') return state.xPageResponse(message);
        return { ok: true };
      },
      async query() { return [{ id: 101 }]; },
    },
    action: {
      async setBadgeText(details) { state.badges.push({ type: 'text', ...details }); },
      async setBadgeBackgroundColor(details) { state.badges.push({ type: 'color', ...details }); },
    },
    downloads: {
      onChanged: onDownloadChanged,
      async download(details) { state.downloadCalls.push(details); return state.downloadImpl(details); },
      async search(details) { return state.downloadSearchImpl(details); },
    },
  };
}

function installIndexedDbMock() {
  const db = {
    createObjectStore() {},
    transaction() {
      const transaction = { oncomplete: null, onerror: null, onabort: null };
      const store = {
        get(key) {
          const request = { result: key === 'metadata' ? state.metadata : key === 'current' ? state.clip : undefined };
          setTimeout(() => transaction.oncomplete?.(), 0);
          return request;
        },
        put(value, key) {
          if (key === 'metadata') state.metadata = value;
          if (key === 'current') state.clip = value;
          setTimeout(() => transaction.oncomplete?.(), 0);
          return { result: key };
        },
        clear() {
          state.metadata = null;
          state.clip = null;
          setTimeout(() => transaction.oncomplete?.(), 0);
          return { result: undefined };
        },
      };
      transaction.objectStore = () => store;
      return transaction;
    },
  };
  globalThis.indexedDB = {
    open() {
      const request = { result: db, onupgradeneeded: null, onsuccess: null, onerror: null };
      setTimeout(() => {
        request.onupgradeneeded?.({ target: { result: { createObjectStore() {} } } });
        request.onsuccess?.();
      }, 0);
      return request;
    },
  };
}

async function invokeMessage(message, sender) {
  return new Promise(resolve => state.message.listener(message, sender, resolve));
}

const popupSender = { id: EXTENSION_ID, url: POPUP_URL };
const sourceTab = { id: 101 };
const sourceClick = { menuItemId: 'video-bridge-copy', pageUrl: SOURCE_PAGE, frameId: 0 };

before(async () => {
  installChromeMock();
  installIndexedDbMock();
  await import('../extension/background.js?background-test');
});

beforeEach(() => {
  resetState();
});

test('registers copy and download-and-copy context menu entries', async () => {
  await state.installed.listener();
  assert.deepEqual(state.createdMenus.map(menu => [menu.id, menu.title]), [
    ['video-bridge-copy', '複製影片・影片接力'],
    ['video-bridge-download-copy', '下載並複製影片・影片接力'],
  ]);
  assert.equal(state.createdMenus[1].contexts.includes('video'), true);
});

test('copy entry prepares the clip and does not start a download', async () => {
  await state.contextClick.listener(sourceClick, sourceTab);
  assert.deepEqual(state.offscreenMessages.map(message => message.type), ['VC_OFF_PREPARE']);
  assert.equal(state.downloadCalls.length, 0);
  assert.ok(state.tabsMessages.some(({ message }) => message.state === 'ready' && message.message.includes('Threads 或 Facebook')));
});

test('download-and-copy entry uses the prepared clip id and saveAs false', async () => {
  await state.contextClick.listener({ ...sourceClick, menuItemId: 'video-bridge-download-copy' }, sourceTab);
  const download = state.downloadCalls.at(-1);
  assert.equal(download.saveAs, false);
  assert.equal(download.url, 'blob:download-clip-1');
  const offscreenDownload = state.offscreenMessages.find(message => message.type === 'VC_OFF_DOWNLOAD');
  assert.deepEqual(offscreenDownload, { target: 'offscreen', type: 'VC_OFF_DOWNLOAD', id: 'clip-1' });
  assert.ok(state.tabsMessages.some(({ message }) => message.state === 'ready' && message.message.includes('已交給 Chrome 下載')));
});

test('direct download keeps the job busy until Chrome accepts the request', async () => {
  let handoff;
  state.downloadImpl = async () => new Promise(resolve => { handoff = resolve; });
  const operation = state.contextClick.listener({ ...sourceClick, menuItemId: 'video-bridge-download-copy' }, sourceTab);
  await new Promise(resolve => setTimeout(resolve, 0));
  const blocked = await invokeMessage({ type: 'VC_CLEAR' }, popupSender);
  assert.equal(blocked.ok, false);
  assert.match(blocked.error, /仍在處理/);
  const blockedDownload = await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(blockedDownload.ok, false);
  assert.match(blockedDownload.error, /仍在處理/);
  assert.equal(state.downloadCalls.length, 1);
  handoff(22);
  await operation;
  const { job } = await chrome.storage.session.get('job');
  assert.equal(job.busy, false);
});

test('context menu copy lock blocks an overlapping operation', async () => {
  let releasePrepare;
  state.offscreenHandler = async message => {
    if (message.type === 'VC_OFF_PREPARE') {
      state.metadata = { id: 'locked-clip', name: 'x.mp4', size: 4 };
      state.clip = { ...state.metadata, blob: new Blob([Uint8Array.of(0)]) };
      return new Promise(resolve => { releasePrepare = () => resolve({ ok: true, clip: state.metadata, warning: null }); });
    }
    return { ok: true };
  };
  const first = state.contextClick.listener(sourceClick, sourceTab);
  await new Promise(resolve => setTimeout(resolve, 0));
  await state.contextClick.listener(sourceClick, sourceTab);
  assert.ok(state.tabsMessages.some(({ message }) => message.state === 'working' && message.message.includes('上一支影片')));
  releasePrepare();
  await first;
});

test('download start failure leaves cache and marker available for paste or another save', async () => {
  let markerCopied = false;
  state.offscreenHandler = async message => {
    if (message.type === 'VC_OFF_PREPARE') {
      markerCopied = true;
      state.metadata = { id: 'failed-download', name: 'x.mp4', size: 4 };
      state.clip = { ...state.metadata, blob: new Blob([Uint8Array.of(0)]) };
      return { ok: true, clip: state.metadata, warning: null };
    }
    if (message.type === 'VC_OFF_DOWNLOAD') return { ok: true, url: 'blob:failed', name: 'x.mp4' };
    return { ok: true };
  };
  state.downloadImpl = async () => { throw new Error('download rejected'); };
  await state.contextClick.listener({ ...sourceClick, menuItemId: 'video-bridge-download-copy' }, sourceTab);
  assert.equal(markerCopied, true);
  assert.deepEqual(state.metadata, { id: 'failed-download', name: 'x.mp4', size: 4 });
  assert.ok(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE' && message.url === 'blob:failed'));
  const status = await invokeMessage({ type: 'VC_GET_STATUS' }, popupSender);
  assert.equal(status.clip.id, 'failed-download');
  assert.match(status.lastError, /仍已備妥，可貼上或再次另存/);
});

test('popup download keeps saveAs true while using the current clip id', async () => {
  state.metadata = { id: 'popup-clip', name: 'x.mp4', size: 4 };
  state.downloadId = 88;
  const result = await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(result.ok, true);
  assert.equal(state.downloadCalls[0].saveAs, true);
  assert.deepEqual(state.offscreenMessages[0], { target: 'offscreen', type: 'VC_OFF_DOWNLOAD', id: 'popup-clip' });
});

test('search failure after Chrome accepts the download keeps the Blob URL alive', async () => {
  state.metadata = { id: 'search-failure', name: 'x.mp4', size: 4 };
  state.downloadId = 11;
  state.downloadSearchImpl = async () => { throw new Error('search unavailable'); };
  const result = await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(result.ok, true);
  assert.equal(result.state, 'in_progress');
  assert.match(result.warning, /無法確認下載狀態/);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(state.session.get('download:11'), 'blob:download-search-failure');
  assert.equal(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE'), false);
});

test('session persistence failure after handoff does not revoke the active Blob URL', async () => {
  state.metadata = { id: 'session-failure', name: 'x.mp4', size: 4 };
  state.downloadId = 12;
  state.failDownloadSession = true;
  const result = await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(result.ok, true);
  assert.equal(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE'), false);
  await state.downloadChanged.listener({ id: 12, state: { current: 'interrupted' } });
  assert.ok(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE' && message.url === 'blob:download-session-failure'));
});

test('an onChanged event that arrives before URL registration is reconciled by the unique id', async () => {
  state.metadata = { id: 'event-before-registration', name: 'x.mp4', size: 4 };
  state.downloadId = 13;
  state.downloadState = 'interrupted';
  state.downloadImpl = async () => {
    await state.downloadChanged.listener({ id: 13, state: { current: 'interrupted' } });
    return 13;
  };
  const result = await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(result.ok, false);
  assert.match(result.error, /仍已備妥/);
  assert.ok(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE' && message.url === 'blob:download-event-before-registration'));
});

test('trusted receiver can read chunks while an untrusted sender is rejected', async () => {
  const bytes = Uint8Array.of(1, 2, 3, 4);
  state.clip = { id: 'chunk-clip', size: bytes.length, blob: new Blob([bytes]) };
  const accepted = await invokeMessage({ type: 'VC_READ_CHUNK', id: 'chunk-clip', offset: 0, length: 4 }, {
    id: EXTENSION_ID, tab: { id: 101 }, frameId: 0, url: 'https://www.facebook.com/'
  });
  assert.equal(accepted.ok, true);
  const threadsAccepted = await invokeMessage({ type: 'VC_READ_CHUNK', id: 'chunk-clip', offset: 0, length: 4 }, {
    id: EXTENSION_ID, tab: { id: 102 }, frameId: 0, url: 'https://www.threads.com/'
  });
  assert.equal(threadsAccepted.ok, true);
  const rejected = await invokeMessage({ type: 'VC_READ_CHUNK', id: 'chunk-clip', offset: 0, length: 4 }, {
    id: 'other-extension', tab: { id: 101 }, frameId: 0, url: 'https://www.facebook.com/'
  });
  assert.equal(rejected.ok, false);
  assert.match(rejected.error, /無法讀取影片快取/);
});

test('completion, interruption and session fallback revoke download object URLs', async () => {
  state.metadata = { id: 'popup-clip', name: 'x.mp4', size: 4 };
  state.session.set('job', { busy: false, tabId: 101, lastError: null });
  state.downloadId = 7;
  await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  assert.equal(state.session.get('download:7'), 'blob:download-popup-clip');
  await state.downloadChanged.listener({ id: 7, state: { current: 'complete' } });
  assert.equal(state.session.has('download:7'), false);
  assert.ok(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE' && message.url === 'blob:download-popup-clip'));

  state.session.set('download:91', 'blob:worker-restarted');
  await state.downloadChanged.listener({ id: 91, state: { current: 'interrupted' } });
  assert.equal(state.session.has('download:91'), false);
  assert.ok(state.offscreenMessages.some(message => message.type === 'VC_OFF_REVOKE' && message.url === 'blob:worker-restarted'));

  state.downloadId = 8;
  await invokeMessage({ type: 'VC_DOWNLOAD' }, popupSender);
  await state.downloadChanged.listener({ id: 8, state: { current: 'interrupted' } });
  const { job } = await chrome.storage.session.get('job');
  assert.match(job.lastError, /下載已中斷/);
  assert.equal(job.busy, false);
});

test('X embed data without the selected video falls back to the source tab post page by poster', async () => {
  const realFetch = globalThis.fetch;
  const poster = 'https://pbs.twimg.com/amplify_video_thumb/2074085545349689344/img/cover.jpg';
  const pageMp4 = 'https://video.twimg.com/amplify_video/2074085545349689344/vid/avc1/1080x1080/page.mp4?tag=28';
  globalThis.fetch = async () => new Response(JSON.stringify({ id_str: '123', mediaDetails: [] }), { status: 200 });
  try {
    state.tabCandidate = { ok: true, pageUrl: SOURCE_PAGE, url: 'blob:https://x.com/article', xPostUrl: 'https://x.com/example/status/123', poster };
    state.xPageResponse = message => {
      assert.deepEqual(message, { type: 'VC_RESOLVE_X_PAGE', postUrl: 'https://x.com/example/status/123', poster });
      return { ok: true, url: pageMp4, pageUrl: 'https://x.com/example/status/123' };
    };
    await state.contextClick.listener(sourceClick, sourceTab);
    const prepare = state.offscreenMessages.find(message => message.type === 'VC_OFF_PREPARE');
    assert.equal(prepare.candidate.url, pageMp4);
    assert.equal(prepare.candidate.pageUrl, 'https://x.com/example/status/123');

    resetState();
    state.tabCandidate = { ok: true, pageUrl: SOURCE_PAGE, url: 'blob:https://x.com/article', xPostUrl: 'https://x.com/example/status/123', poster };
    await state.contextClick.listener(sourceClick, sourceTab);
    assert.equal(state.offscreenMessages.length, 0);
    assert.ok(state.tabsMessages.some(({ message }) => message.state === 'error' && /沒有可取得的 MP4/.test(message.message)));
  } finally {
    globalThis.fetch = realFetch;
  }
});
