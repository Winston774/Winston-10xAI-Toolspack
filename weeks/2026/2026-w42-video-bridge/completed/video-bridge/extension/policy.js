export const MAX_BYTES = 150 * 1024 * 1024;
export const CHUNK_BYTES = 256 * 1024;
export const MARKER_PREFIX = 'video-bridge:';
const SOURCE_HOSTS = new Set(['x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'threads.com', 'www.threads.com', 'threads.net', 'www.threads.net']);
export function isSourcePage(value) {
  try { const url = new URL(value); return url.protocol === 'https:' && SOURCE_HOSTS.has(url.hostname) && !url.port && !url.username && !url.password; } catch { return false; }
}
export function isFacebookPage(value) {
  try { const url = new URL(value); return url.protocol === 'https:' && url.hostname === 'www.facebook.com' && !url.port && !url.username && !url.password; } catch { return false; }
}
export function isReceiverPage(value) {
  if (isFacebookPage(value)) return true;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['threads.com', 'www.threads.com', 'threads.net', 'www.threads.net'].includes(url.hostname) && !url.port && !url.username && !url.password;
  } catch { return false; }
}
export function validateMediaUrl(value, sourcePage) {
  if (!isSourcePage(sourcePage)) throw new Error('來源頁面不在支援範圍。');
  let url;
  try { url = new URL(value); } catch { throw new Error('找不到有效的影片網址。'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.port) throw new Error('目前僅支援 HTTPS 的直接影片網址；blob 與分段串流尚未支援。');
  const source = new URL(sourcePage).hostname;
  const domains = source.includes('threads.') ? ['cdninstagram.com', 'fbcdn.net'] : ['twimg.com'];
  if (!domains.some(domain => url.hostname === domain || url.hostname.endsWith('.' + domain))) throw new Error('影片不在來源平台的支援媒體主機上。');
  if (/\.(?:m3u8|mpd)(?:$|\/)/i.test(url.pathname)) throw new Error('這支影片使用分段串流，目前尚未支援。');
  url.hash = '';
  return url.href;
}
export function canonicalPage(value) {
  const url = new URL(value); return url.origin + url.pathname;
}
export function validateChunk(offset, length, size) {
  if (!Number.isSafeInteger(offset) || offset < 0 || offset > size || !Number.isSafeInteger(length) || length < 1 || length > CHUNK_BYTES) throw new Error('影片分塊讀取參數無效。');
}
export function isMp4Header(bytes) {
  return bytes.length >= 12 && String.fromCharCode(...bytes.slice(4, 8)) === 'ftyp';
}
export async function fetchVideo(value, sourcePage, { fetchImpl = fetch, maxBytes = MAX_BYTES, onProgress = () => {} } = {}) {
  const url = validateMediaUrl(value, sourcePage);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  let reader;
  try {
    // Reject redirects instead of fetching an unvalidated destination with a signed URL.
    const response = await fetchImpl(url, { credentials: 'omit', redirect: 'error', cache: 'no-store', signal: controller.signal });
    if (response.status !== 200) throw new Error(`影片下載失敗（HTTP ${response.status}），請重新整理來源頁面再試。`);
    const header = response.headers.get('content-length');
    const expected = header === null ? null : Number(header);
    if (expected !== null && (!Number.isSafeInteger(expected) || expected <= 0 || expected > maxBytes)) throw new Error('影片為空或超過第一版的 150 MiB 上限。');
    if (!response.body) throw new Error('沒有取得影片資料。');
    reader = response.body.getReader();
    const chunks = []; let total = 0; let nextReport = 0;
    while (true) {
      const { value: part, done } = await reader.read();
      if (done) break;
      total += part.byteLength;
      if (total > maxBytes) throw new Error('影片超過第一版的 150 MiB 上限。');
      chunks.push(part);
      if (Date.now() >= nextReport) { onProgress(total, expected); nextReport = Date.now() + 1000; }
    }
    if (!total || (expected !== null && !response.headers.get('content-encoding') && total !== expected)) throw new Error('影片下載不完整，請再試一次。');
    const blob = new Blob(chunks, { type: 'video/mp4' });
    if (!isMp4Header(new Uint8Array(await blob.slice(0, 16).arrayBuffer()))) throw new Error('取得的資料不是支援的 MP4 檔案，可能是串流清單或失效頁面。');
    return blob;
  } catch (error) {
    controller.abort();
    if (reader) await reader.cancel().catch(() => {});
    if (error.name === 'AbortError') throw new Error('下載逾時，請重新整理影片頁面後再試。');
    if (error instanceof TypeError) throw new Error('無法取得影片。媒體網址可能已失效、需要登入資訊，或主機拒絕請求。');
    throw error;
  } finally { clearTimeout(timeout); }
}
