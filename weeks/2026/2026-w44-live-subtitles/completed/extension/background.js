import { DEFAULT_CONFIG, normalizeConfig, newSession, acceptsResult, advanceRevision, recordCue, tabMediaKey } from './lib/session.js';
import { checkGeminiConnection } from './lib/gemini-live.js';

let config = { ...DEFAULT_CONFIG };
let themeMode = 'system';
let session = null;
let command = Promise.resolve();
let writes = Promise.resolve();
let startAttempt = 0;
const ready = Promise.all([
  chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' }),
  chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' }),
]).then(() => Promise.all([chrome.storage.local.get('config'), chrome.storage.session.get('session'), chrome.storage.local.get('themeMode')])).then(async ([saved, runtime, appearance]) => {
  try { config = normalizeConfig(saved.config); } catch { /* Defaults recover invalid saved settings. */ }
  themeMode = normalizeTheme(appearance.themeMode);
  session = runtime.session || null;
  if (session) delete session.config;
  // Persist only the supported settings, removing legacy pairing fields on upgrade.
  await chrome.storage.local.set({ config });
  await chrome.storage.session.set({ session });
});
const publicStyle = value => ({ fontSize: value.fontSize, position: value.position, targetLanguage: value.targetLanguage });
// The appearance mode is written by theme.js controls; the page renderer cannot read trusted storage.
function normalizeTheme(value) { return ['light', 'dark'].includes(value) ? value : 'system'; }
const publicSession = () => session && Object.fromEntries(Object.entries(session).filter(([key]) => key !== 'config'));
function persist() {
  const snapshot = session && structuredClone(session);
  writes = writes.catch(() => {}).then(() => chrome.storage.session.set({ session: snapshot }));
  return writes;
}
function content(type, extra = {}, target = session) {
  if (!target) return Promise.resolve();
  return chrome.tabs.sendMessage(target.tabId, { type, sessionId: target.id, revision: target.revision, ...extra }).catch(() => {});
}
function offscreen(type, extra = {}) {
  return chrome.runtime.sendMessage({ target: 'offscreen', type, ...extra });
}
async function status(state, message) {
  if (!session) return;
  session.state = state;
  session.message = message;
  await Promise.all([persist(), content('SUBTITLE_STATUS', { state, message })]);
}
async function ensureOffscreen() {
  const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
  if (!contexts.length) await chrome.offscreen.createDocument({ url: 'offscreen.html', reasons: ['USER_MEDIA'], justification: '取得使用者啟動的目前分頁音訊，產生雙語字幕。' });
}
async function stop(message = '字幕已停止。', failed = false) {
  if (!session) return;
  const current = session;
  current.state = failed ? 'error' : 'stopped';
  current.message = message;
  await Promise.all([
    offscreen('CAPTURE_STOP', { sessionId: current.id }).catch(() => {}),
    content('SUBTITLE_STOP', {}, current), persist()
  ]);
}
async function checkGemini(input) {
  const selected = normalizeConfig({ ...config, ...input });
  if (!selected.geminiApiKey) throw new Error('請先填入 Gemini API key。');
  return checkGeminiConnection(selected.geminiApiKey, { targetLanguage: selected.targetLanguage });
}
function clockFrom(value) {
  const time = Number(value.time), rate = Number(value.playbackRate);
  if (!Number.isFinite(time) || time < 0 || !Number.isFinite(rate) || rate <= 0 || rate > 4) return null;
  return { time, playbackRate: rate, paused: Boolean(value.paused), adPlaying: Boolean(value.adPlaying), wallTime: Date.now() };
}
async function start(input) {
  const attempt = ++startAttempt;
  const requireActiveAttempt = () => { if (attempt !== startAttempt) throw new Error('已取消啟動字幕。'); };
  // The popup sends language and display choices; the key comes from the settings page.
  const selected = normalizeConfig({ ...config, ...input });
  if (!selected.geminiApiKey) throw new Error('請先到設定頁填入 Gemini API key。');
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const mediaKey = tabMediaKey(tab?.url);
  if (!tab?.id || !mediaKey) throw new Error('請在播放聲音的網站分頁按「開始字幕」。瀏覽器內部頁面、擴充功能頁面與桌面軟體無法擷取。');
  try {
    // The renderer's shadow root reads --nw-* tokens through its [data-nw-root] host.
    await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ['noise-winston/tokens.css'] });
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['lib/cue-store.js', 'content.js'] });
  }
  catch { throw new Error('無法在此頁顯示字幕。請在一般網站分頁點擊擴充功能圖示，允許存取此分頁後重試。'); }
  const media = await chrome.tabs.sendMessage(tab.id, { type: 'SUBTITLE_PING' });
  requireActiveAttempt();
  if (!media?.ok || media.mediaKey !== mediaKey || !clockFrom(media)) throw new Error('分頁尚未準備好，請等頁面載入後重試。');
  await stop();
  requireActiveAttempt();
  config = selected;
  await chrome.storage.local.set({ config });
  requireActiveAttempt();
  session = newSession({ tabId: tab.id, mediaKey, captureMode: media.captureMode === 'tab' ? 'tab' : 'youtube', config: selected });
  await persist();
  try {
    await ensureOffscreen();
    requireActiveAttempt();
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
    requireActiveAttempt();
    const initialized = await content('SUBTITLE_INIT', { config: publicStyle(config), themeMode, captureMode: session.captureMode });
    if (!initialized?.ok) throw new Error('字幕介面未能啟動，請重新整理分頁後重試。');
    requireActiveAttempt();
    const result = await offscreen('CAPTURE_START', { sessionId: session.id, revision: session.revision, streamId, config: selected, clock: clockFrom(media) });
    requireActiveAttempt();
    if (!result?.ok) throw new Error(result?.error || '分頁收音未啟動。');
    await status('listening', 'Gemini 已連線。此分頁播放的語音會自動辨識並翻譯。');
    requireActiveAttempt();
  } catch (error) {
    if (attempt !== startAttempt) return { ok: false, error: '已取消啟動字幕。' };
    await stop(`無法啟動收音：${error.message}`, true);
    throw error;
  }
  return { ok: true, session: publicSession() };
}
async function mediaState(message) {
  if (message.mediaKey !== session.mediaKey || message.reason === 'video-change') { startAttempt++; return stop('頁面已切換，請在新頁面重新開始字幕。'); }
  if (message.reason === 'ended') {
    await offscreen('CAPTURE_FINISH', { sessionId: session.id }).catch(() => {});
    return;
  }
  const clock = clockFrom(message);
  if (!clock) return;
  if (['seek', 'rate', 'ad'].includes(message.reason)) {
    session = advanceRevision(session);
    await Promise.all([persist(), content('SUBTITLE_CLEAR')]);
  }
  await offscreen('CAPTURE_CLOCK', { sessionId: session.id, revision: session.revision, clock }).catch(() => {});
}
async function handle(message, sender) {
  await ready;
  if (sender.id !== chrome.runtime.id) return { ok: false, error: '無法驗證訊息來源。' };
  const fromPopup = sender.url === chrome.runtime.getURL('popup.html');
  const fromSettings = sender.url === chrome.runtime.getURL('options.html');
  const fromOffscreen = sender.url === chrome.runtime.getURL('offscreen.html');
  const fromSessionTab = sender.tab?.id === session?.tabId && sender.frameId === 0;
  const fromVideo = fromSessionTab && tabMediaKey(sender.url) === session?.mediaKey;
  if (fromOffscreen) {
    if (!acceptsResult(session, message)) return { ok: false };
    if (message.type === 'CAPTURE_CUE') {
      if (!recordCue(session, message.cue)) return { ok: false };
      await content('SUBTITLE_CUE', { cue: message.cue });
      await persist();
    } else if (message.type === 'CAPTURE_STATUS') await status(message.state, message.message);
    else if (message.type === 'CAPTURE_ERROR') { startAttempt++; await stop(message.message || '音訊處理失敗，請重新開始。', true); }
    else if (message.type === 'CAPTURE_FINISHED') {
      // The renderer retires the last cue after its reading time; history remains available.
      await status('stopped', '影片已結束，最後一段字幕處理完成。');
    }
    return { ok: true };
  }
  if (fromSessionTab && message.type === 'MEDIA_STATE' && message.sessionId === session?.id && !['stopped','error'].includes(session?.state) &&
      (fromVideo || message.reason === 'video-change')) {
    await mediaState(message);
    return { ok: true };
  }
  if (message.type === 'STOP' && (fromPopup || fromSessionTab)) { startAttempt++; await stop(); return { ok: true }; }
  if (message.type === 'START' && fromPopup) return start(message.config);
  if (!fromPopup && !fromSettings) return { ok: false, error: '此操作僅供擴充功能控制面板使用。' };
  switch (message.type) {
    case 'GET_STATUS': return { ok: true, session: publicSession(), config };
    case 'CHECK_GEMINI': return { ok: true, health: await checkGemini(message.config) };
    case 'UPDATE_CONFIG': {
      // Popup and settings each send only the fields they own.
      const next = normalizeConfig({ ...config, ...message.config });
      if (session && !['stopped', 'error'].includes(session.state) &&
          (next.targetLanguage !== session.targetLanguage || next.geminiApiKey !== config.geminiApiKey)) {
        throw new Error('請先停止字幕，再更換目標語言或 Gemini API key。');
    }
      config = next;
      await chrome.storage.local.set({ config });
      await content('UPDATE_STYLE', { config: publicStyle(config), themeMode });
      return { ok: true, config };
      }
    default: return { ok: false, error: '不支援的操作。' };
  }
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (!message || message.target === 'offscreen') return false;
  const execute = () => handle(message, sender);
  const serialized = ['START','UPDATE_CONFIG','MEDIA_STATE'].includes(message.type);
  const task = serialized ? (command = command.catch(() => {}).then(execute)) : execute();
  task.then(respond, error => respond({ ok: false, error: error.message || '操作失敗，請重試。' }));
  return true;
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.themeMode) return;
  void ready.then(async () => {
    themeMode = normalizeTheme(changes.themeMode.newValue);
    if (session && !['stopped', 'error'].includes(session.state)) await content('UPDATE_STYLE', { config: publicStyle(config), themeMode });
  });
});
chrome.tabs.onRemoved.addListener(tabId => { void ready.then(async () => { if (session?.tabId === tabId) { startAttempt++; await stop('收音分頁已關閉。'); } }); });
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.url || change.status === 'loading') void ready.then(async () => {
    await ready;
    if (session?.tabId === tabId && (change.status === 'loading' || (change.url && tabMediaKey(change.url) !== session.mediaKey))) {
      startAttempt++;
      await stop('頁面已重新載入或切換，請重新開始字幕。');
    }
  });
});
