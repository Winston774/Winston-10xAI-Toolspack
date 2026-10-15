import { getClip, getMeta, clearClip } from './db.js';
import { isSourcePage, isReceiverPage, validateMediaUrl, validateChunk } from './policy.js';
import { resolveXSource } from './x-resolver.js';
const MENU_COPY = 'video-bridge-copy';
const MENU_DOWNLOAD_COPY = 'video-bridge-download-copy';
const DOWNLOAD_INTERRUPTED = '下載已中斷；影片仍已備妥，可貼上或再次另存。';
const DOWNLOAD_FAILURE = '下載失敗；影片仍已備妥，可貼上或再次另存。';
let creating;
let copyLock = false;
let jobQueue = Promise.resolve();
const downloadUrls = new Map();
const downloadRegistrations = new Map();
const downloadStates = new Map();
const downloadPending = new Map();
async function ensureOffscreen() {
  if (creating) return creating;
  creating = (async () => {
    const documentUrl = chrome.runtime.getURL('offscreen.html');
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'], documentUrls: [documentUrl] });
    if (!contexts.length) await chrome.offscreen.createDocument({ url: 'offscreen.html', reasons: ['CLIPBOARD', 'BLOBS'], justification: '暫存影片、讀取影片中繼資料並寫入貼上識別碼。' });
  })();
  try { await creating; } finally { creating = null; }
}
async function offscreen(type, data = {}) {
  await ensureOffscreen();
  const result = await chrome.runtime.sendMessage({ target: 'offscreen', type, ...data });
  if (!result?.ok) throw new Error(result?.error || '影片背景處理沒有回應。');
  return result;
}
function updateJob(updater) {
  const operation = jobQueue.then(async () => {
    const { job } = await chrome.storage.session.get('job');
    const next = updater(job);
    if (next) await chrome.storage.session.set({ job: { ...next, updatedAt: Date.now() } });
    return next;
  });
  jobQueue = operation.catch(() => {});
  return operation;
}
function setJob(job) { return updateJob(() => job); }
async function getJob() {
  const { job } = await chrome.storage.session.get('job');
  if (job?.busy && Date.now() - job.updatedAt > 240000) return { busy: false, lastError: '上一個影片處理已中斷，請重新複製。' };
  return job || { busy: false, lastError: null };
}
async function notify(tabId, state, message) {
  if (Number.isInteger(tabId)) await chrome.tabs.sendMessage(tabId, { type: 'VC_STATUS', state, message }).catch(() => {});
}
async function refreshReceivers() {
  // IDs are available without the tabs permission. Only our own installed
  // content scripts can receive these messages; no page URLs are inspected.
  const tabs = await chrome.tabs.query({});
  await Promise.allSettled(tabs.filter(tab => Number.isInteger(tab.id)).map(tab => chrome.tabs.sendMessage(tab.id, { type: 'VC_STATUS' })));
}
async function badge(text, color) { await chrome.action.setBadgeText({ text }); await chrome.action.setBadgeBackgroundColor({ color }); }
async function registerMenu() {
  await chrome.contextMenus.removeAll();
  const documentUrlPatterns = ['https://x.com/*', 'https://www.x.com/*', 'https://twitter.com/*', 'https://www.twitter.com/*', 'https://*.threads.com/*', 'https://*.threads.net/*'];
  chrome.contextMenus.create({ id: MENU_COPY, title: '複製影片・影片接力', contexts: ['video', 'page'], documentUrlPatterns });
  chrome.contextMenus.create({ id: MENU_DOWNLOAD_COPY, title: '下載並複製影片・影片接力', contexts: ['video', 'page'], documentUrlPatterns });
}
async function resolveSource(tabId, frameId, candidate) {
  try {
    return await resolveXSource(candidate);
  } catch (error) {
    // X 公開 embed 資料沒有這支影片時（例如 X 文章內的影片），改由來源分頁讀取貼文頁面，
    // 依封面的媒體 ID 取出同一支影片的 MP4。
    const postUrls = [...new Set([candidate.xPostUrl, candidate.xPageUrl].filter(Boolean))];
    if (!candidate.poster || !postUrls.length) throw error;
    for (const postUrl of postUrls) {
      let page;
      try { page = await chrome.tabs.sendMessage(tabId, { type: 'VC_RESOLVE_X_PAGE', postUrl, poster: candidate.poster }, { frameId }); }
      catch { continue; }
      if (page?.ok) return resolveXSource({ url: page.url, pageUrl: page.pageUrl, title: candidate.title });
    }
    throw error;
  }
}
chrome.runtime.onInstalled.addListener(() => registerMenu());
chrome.runtime.onStartup.addListener(() => registerMenu());
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const sourcePage = info.pageUrl;
  const directDownload = info.menuItemId === MENU_DOWNLOAD_COPY;
  if (info.menuItemId !== MENU_COPY && !directDownload || !Number.isInteger(tab?.id) || !isSourcePage(sourcePage)) return;
  if (copyLock) { await notify(tab.id, 'working', '上一支影片仍在處理中。'); return; }
  copyLock = true;
  try {
    if ((await getJob()).busy) { await notify(tab.id, 'working', '上一支影片仍在處理中。'); return; }
    await setJob({ busy: true, lastError: null, tabId: tab.id, progress: null });
    await badge('…', '#475569');
    await notify(tab.id, 'working', '正在取得影片，完成後即可前往 Threads 或 Facebook 貼上。');
    let candidate;
    try { candidate = await chrome.tabs.sendMessage(tab.id, { type: 'VC_GET_SOURCE' }, { frameId: info.frameId || 0 }); }
    catch { throw new Error('請重新整理這個來源分頁，再對影片按右鍵。'); }
    if (!candidate?.ok) throw new Error(candidate?.error || '請直接對影片或影片所在貼文按右鍵。');
    if (!isSourcePage(candidate.pageUrl) || new URL(candidate.pageUrl).origin !== new URL(sourcePage).origin) throw new Error('影片來源與目前分頁不一致。');
    candidate = await resolveSource(tab.id, info.frameId || 0, candidate);
    validateMediaUrl(candidate.url, candidate.pageUrl);
    const result = await offscreen('VC_OFF_PREPARE', { candidate });
    if (directDownload) {
      const download = await downloadCurrentClip(result.clip?.id, false);
      await updateJob(current => {
        if (!current) return null;
        if (current.downloadId !== download.downloadId && (download.state === 'in_progress' || !current.busy)) return null;
        return {
          ...current,
          busy: false,
          lastError: result.warning,
          tabId: tab.id,
          downloadId: download.state === 'in_progress' ? download.downloadId : null,
        };
      });
      await badge('1', '#15803d');
      await notify(tab.id, 'ready', result.warning || '影片已交給 Chrome 下載；可到 Threads 或 Facebook 貼上。');
    } else {
      await setJob({ busy: false, lastError: result.warning, tabId: tab.id, downloadId: null });
      await badge('1', '#15803d');
      await notify(tab.id, 'ready', result.warning || '影片已備妥。到 Threads 或 Facebook 發文框按 Ctrl＋V，或按「插入已複製影片」。');
    }
    await refreshReceivers();
  } catch (error) {
    await updateJob(current => ({ ...(current || {}), busy: false, lastError: error.message, tabId: current?.tabId ?? tab.id, downloadId: null }));
    await badge('!', '#b45309');
    await notify(tab.id, 'error', error.message);
    await refreshReceivers();
  } finally { copyLock = false; }
});
function trustedSender(sender) {
  if (sender.id !== chrome.runtime.id) return '';
  if (!sender.tab && sender.url === chrome.runtime.getURL('popup.html')) return 'popup';
  if (!sender.tab && sender.url === chrome.runtime.getURL('offscreen.html')) return 'offscreen';
  if (sender.tab && sender.frameId === 0 && isReceiverPage(sender.url)) return 'receiver';
  return '';
}
async function handle(message, sender) {
  const role = trustedSender(sender);
  if (!role) throw new Error('此頁面無法讀取影片快取。');
  if (role === 'offscreen') {
    if (message.type !== 'VC_PROGRESS' && message.type !== 'VC_HEARTBEAT') throw new Error('未知背景訊息。');
    const job = await updateJob(current => current?.busy ? { ...current, progress: message.type === 'VC_PROGRESS' ? { loaded: message.loaded, total: message.total } : current.progress } : null);
    if (job) {
      if (message.type === 'VC_PROGRESS') await notify(job.tabId, 'working', `正在取得影片：${(message.loaded / 1048576).toFixed(1)} MiB${message.total ? ' / ' + (message.total / 1048576).toFixed(1) + ' MiB' : ''}`);
    }
    return { ok: true };
  }
  if (message.type === 'VC_GET_STATUS') return { ok: true, clip: await getMeta() || null, ...await getJob() };
  if (message.type === 'VC_READ_CHUNK' && role === 'receiver') {
    const clip = await getClip();
    if (!clip || clip.id !== message.id) throw new Error('影片快取已更新，請重新插入。');
    validateChunk(message.offset, message.length, clip.size);
    const bytes = new Uint8Array(await clip.blob.slice(message.offset, message.offset + message.length).arrayBuffer());
    let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return { ok: true, base64: btoa(binary), eof: message.offset + bytes.length >= clip.size, total: clip.size };
  }
  if (role !== 'popup') throw new Error('請從影片接力面板執行此操作。');
  if (message.type === 'VC_COPY_MARKER') return offscreen('VC_OFF_COPY');
  if (message.type === 'VC_CLEAR') {
    if ((await getJob()).busy) throw new Error('影片仍在處理中，完成後才能清除。');
    await clearClip(); await setJob({ busy: false, lastError: null }); await badge('', '#475569'); await refreshReceivers(); return { ok: true };
  }
  if (message.type === 'VC_DOWNLOAD') {
    const { busy } = await getJob();
    if (busy) throw new Error('影片仍在處理中，完成後才能另存。');
    const clip = await getMeta();
    if (!clip) throw new Error('沒有可另存的影片。');
    return downloadCurrentClip(clip.id, true);
  }
  throw new Error('未知操作。');
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.target === 'offscreen' || !message?.type?.startsWith('VC_')) return;
  handle(message, sender).then(sendResponse, error => sendResponse({ ok: false, error: error.message }));
  return true;
});
async function releaseDownload(id) {
  const registration = downloadRegistrations.get(id);
  if (registration) await registration.catch(() => {});
  const key = 'download:' + id;
  const url = downloadUrls.get(id) || (await chrome.storage.session.get(key))[key];
  if (url) {
    await offscreen('VC_OFF_REVOKE', { url }).catch(() => {});
    downloadUrls.delete(id);
    await chrome.storage.session.remove(key).catch(() => {});
  }
  downloadRegistrations.delete(id);
}

function rememberDownloadState(id, state) {
  downloadStates.set(id, state);
}

function readDownloadState(id) { return downloadStates.get(id) || null; }

function clearDownloadState(id) {
  downloadStates.delete(id);
}

async function isTrackedDownload(id) {
  if (downloadPending.has(id) || downloadRegistrations.has(id) || downloadUrls.has(id)) return true;
  const key = 'download:' + id;
  const stored = await chrome.storage.session.get(key);
  return Boolean(stored[key]);
}

function registerDownload(id, url) {
  // Register in memory before yielding. An onChanged event can arrive as soon
  // as downloads.download resolves, and releaseDownload waits for this write.
  downloadUrls.set(id, url);
  const registration = Promise.resolve()
    .then(() => chrome.storage.session.set({ ['download:' + id]: url }));
  downloadRegistrations.set(id, registration);
  void registration.catch(() => {});
}

async function downloadCurrentClip(expectedClipId, saveAs) {
  const result = await offscreen('VC_OFF_DOWNLOAD', { id: expectedClipId });
  let downloadId;
  try {
    downloadId = await chrome.downloads.download({ url: result.url, filename: result.name, saveAs });
  } catch {
    await offscreen('VC_OFF_REVOKE', { url: result.url }).catch(() => {});
    await updateJob(current => current ? { ...current, busy: false, downloadId: null, lastError: DOWNLOAD_FAILURE } : null).catch(() => {});
    throw new Error(DOWNLOAD_FAILURE);
  }

  downloadPending.set(downloadId, true);
  registerDownload(downloadId, result.url);
  let download;
  let stateUnknown = false;
  try {
    [download] = await chrome.downloads.search({ id: downloadId });
  } catch (error) {
    stateUnknown = true;
  }

  const knownState = readDownloadState(downloadId);
  const state = knownState || (stateUnknown ? 'in_progress' : download?.state || 'in_progress');
  if (state === 'interrupted') {
    await releaseDownload(downloadId);
    clearDownloadState(downloadId);
    downloadPending.delete(downloadId);
    await updateJob(current => current ? { ...current, busy: false, downloadId: null, lastError: DOWNLOAD_INTERRUPTED } : null).catch(() => {});
    throw new Error(DOWNLOAD_FAILURE);
  }
  if (state === 'complete') {
    await releaseDownload(downloadId);
    clearDownloadState(downloadId);
    downloadPending.delete(downloadId);
    await updateJob(current => current && (current.downloadId === downloadId || current.busy)
      ? { ...current, busy: false, downloadId: null }
      : null);
    return { ok: true, downloadId, state };
  }

  await updateJob(current => current ? { ...current, downloadId } : null);
  downloadPending.delete(downloadId);
  return {
    ok: true,
    downloadId,
    state: 'in_progress',
    warning: stateUnknown ? '影片已交給 Chrome 下載，但目前無法確認下載狀態。' : null,
  };
}
chrome.downloads.onChanged.addListener(async delta => {
  const state = delta.state?.current;
  if (!['complete', 'interrupted'].includes(state)) return;
  if (!await isTrackedDownload(delta.id)) return;
  rememberDownloadState(delta.id, state);
  await releaseDownload(delta.id);
  const updated = await updateJob(current => {
    if (!current || current.downloadId !== delta.id) return null;
    if (state === 'complete') return { ...current, downloadId: null };
    return { ...current, busy: false, downloadId: null, lastError: DOWNLOAD_INTERRUPTED };
  });
  if (!updated) {
    if (!downloadPending.has(delta.id)) clearDownloadState(delta.id);
    return;
  }
  clearDownloadState(delta.id);
  downloadPending.delete(delta.id);
  if (state === 'complete') {
    return;
  }
  await notify(updated.tabId, 'error', DOWNLOAD_INTERRUPTED);
  await refreshReceivers();
});
