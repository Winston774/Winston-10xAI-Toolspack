let database;
function openDB() {
  if (!database) database = new Promise((resolve, reject) => {
    const request = indexedDB.open('video-bridge', 1);
    request.onupgradeneeded = () => { request.result.createObjectStore('clip'); };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => { database = null; reject(request.error); };
  });
  return database;
}
async function run(mode, operation) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('clip', mode);
    const request = operation(tx.objectStore('clip'));
    tx.oncomplete = () => resolve(request?.result);
    tx.onerror = () => reject(tx.error || request?.error);
    tx.onabort = () => reject(tx.error || new Error('影片快取寫入失敗。'));
  });
}
export function getClip() { return run('readonly', store => store.get('current')); }
export function getMeta() { return run('readonly', store => store.get('metadata')); }
export function putClip(clip) {
  const { blob, ...meta } = clip;
  return run('readwrite', store => { store.put(clip, 'current'); return store.put(meta, 'metadata'); });
}
export function clearClip() { return run('readwrite', store => store.clear()); }
