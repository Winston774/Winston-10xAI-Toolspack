import { fetchVideo, canonicalPage, MARKER_PREFIX } from './policy.js';
import { getClip, putClip } from './db.js';
let processing = false;
const objectUrls = new Set();
function copyText(text) {
  const textarea = document.createElement('textarea');
  textarea.value = text; document.body.append(textarea); textarea.select();
  let copied = false;
  try { copied = document.execCommand('copy'); } finally { textarea.remove(); }
  if (!copied) throw new Error('剪貼簿寫入失敗。請開啟 Threads 或 Facebook 發文框，使用「插入已複製影片」。');
}
async function inspectVideo(blob) {
  const url = URL.createObjectURL(blob); const video = document.createElement('video');
  video.muted = true; video.preload = 'metadata';
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => finish(new Error('影片中繼資料讀取逾時。')), 15000);
      const finish = error => {
        clearTimeout(timer); video.onloadedmetadata = null; video.onerror = null;
        if (error) reject(error);
        else if (!Number.isFinite(video.duration) || video.duration <= 0 || !video.videoWidth || !video.videoHeight) reject(new Error('影片缺少有效時長或畫面。'));
        else resolve({ duration: video.duration, width: video.videoWidth, height: video.videoHeight });
      };
      video.onloadedmetadata = () => finish();
      video.onerror = () => finish(new Error('Chrome 無法讀取這支 MP4，可能是不完整檔案或不支援的編碼。'));
      video.src = url;
    });
  } finally { video.removeAttribute('src'); video.load(); URL.revokeObjectURL(url); }
}
async function handle(message) {
  if (message.type === 'VC_OFF_COPY') {
    const clip = await getClip(); if (!clip) throw new Error('請先複製一支影片。');
    copyText(MARKER_PREFIX + clip.id); return { ok: true };
  }
  if (message.type === 'VC_OFF_DOWNLOAD') {
    const clip = await getClip(); if (!clip) throw new Error('沒有可另存的影片。');
    if (message.id !== undefined && clip.id !== message.id) throw new Error('影片快取已更新，請從面板確認影片後再下載。');
    const url = URL.createObjectURL(clip.blob); objectUrls.add(url);
    // Keep the URL until downloads.onChanged reports complete/interrupted.
    return { ok: true, url, name: clip.name };
  }
  if (message.type === 'VC_OFF_REVOKE') {
    if (objectUrls.delete(message.url)) URL.revokeObjectURL(message.url);
    return { ok: true };
  }
  if (message.type !== 'VC_OFF_PREPARE') throw new Error('未知背景操作。');
  if (processing) throw new Error('上一支影片仍在處理中。');
  processing = true;
  const heartbeat = setInterval(() => chrome.runtime.sendMessage({ type: 'VC_HEARTBEAT' }).catch(() => {}), 20000);
  try {
    const { candidate } = message;
    const blob = await fetchVideo(candidate.url, candidate.pageUrl, { onProgress: (loaded, total) => {
      chrome.runtime.sendMessage({ type: 'VC_PROGRESS', loaded, total }).catch(() => {});
    } });
    const media = await inspectVideo(blob);
    const id = crypto.randomUUID();
    const platform = new URL(candidate.pageUrl).hostname.includes('threads') ? 'threads' : 'x';
    const clip = { id, name: `${platform}-${new Date().toISOString().replace(/[:.]/g, '-')}.mp4`, size: blob.size, mime: blob.type, ...media, sourceUrl: canonicalPage(candidate.pageUrl), createdAt: Date.now(), blob };
    // Replace only after the complete new video has passed container/metadata checks.
    await putClip(clip);
    let warning = null;
    try { copyText(MARKER_PREFIX + id); } catch (error) { warning = error.message; }
    const { blob: omitted, ...metadata } = clip;
    return { ok: true, clip: metadata, warning };
  } finally { clearInterval(heartbeat); processing = false; }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL('background.js') && sender.url && !sender.url.startsWith(chrome.runtime.getURL(''))) return;
  if (message?.target !== 'offscreen') return;
  handle(message).then(sendResponse, error => sendResponse({ ok: false, error: error.message }));
  return true;
});
