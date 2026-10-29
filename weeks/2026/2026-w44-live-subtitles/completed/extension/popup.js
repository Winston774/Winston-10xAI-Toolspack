import { TARGET_LANGUAGES, DEFAULT_TARGET_LANGUAGE, targetLanguageLabel } from './lib/languages.js';

const $ = id => document.getElementById(id);
// The API key is edited on the settings page; the popup only sends display and language choices.
const fields = { targetLanguage: $('target-language'), fontSize: $('font-size'), position: $('position') };
for (const language of TARGET_LANGUAGES) {
  const option = document.createElement('option');
  option.value = language.code;
  option.textContent = `${language.label} · ${language.code}`;
  fields.targetLanguage.append(option);
}
fields.targetLanguage.value = DEFAULT_TARGET_LANGUAGE;
const titles = { idle: '準備開始', starting: '正在準備', listening: '正在聆聽', processing: '正在辨識與翻譯', error: '需要處理', stopped: '字幕已停止' };
const dots = { starting: 'busy', listening: 'ready', processing: 'ready', error: 'error' };
let session = null;
let busy = false;
let loaded = false;
let hasKey = false;
let saveTimer;

function showError(message = '') { $('error').textContent = message; $('error').hidden = !message; }
function errorText(error) { return error?.message || (typeof error === 'string' ? error : '操作未完成，請重試。'); }
function readConfig() { return { targetLanguage: fields.targetLanguage.value, fontSize: Number(fields.fontSize.value), position: fields.position.value }; }
async function request(type, extra = {}) {
  const result = await chrome.runtime.sendMessage({ type, ...extra });
  if (!result?.ok) throw new Error(errorText(result?.error || '擴充功能未回應，請重新開啟。'));
  return result;
}
function buttons() {
  const active = ['starting', 'listening', 'processing'].includes(session?.state);
  $('start').disabled = busy || !loaded || !hasKey || active;
  $('stop').disabled = !session?.id || ['idle', 'stopped'].includes(session?.state);
  fields.targetLanguage.disabled = active || busy;
}
function renderSetup() {
  $('setup-warning').hidden = !loaded || hasKey;
  $('summary').textContent = !loaded ? '載入中' : hasKey ? `自動辨識 → ${targetLanguageLabel(fields.targetLanguage.value)}` : '尚未設定 Gemini API key';
}
function renderSession(value) {
  session = value ?? null;
  const state = session?.state ?? 'idle';
  $('session-title').textContent = titles[state] || '字幕待命';
  if (dots[state]) $('session-title').dataset.state = dots[state];
  else delete $('session-title').dataset.state;
  $('session-message').textContent = session?.message || ({
    idle: '開啟影片、直播或網頁會議，翻譯此分頁的聲音。',
    starting: '正在連接分頁音訊與 Gemini，請稍候。',
    listening: '請在此分頁播放聲音，字幕會跟隨語音更新。',
    processing: '正在辨識這段語音並翻譯成目標語言。',
    stopped: '已結束本次字幕。播放聲音後可再次開始。',
    error: '請到設定頁檢查 Gemini API key 與網路連線後重試。',
  }[state] || '');
  $('segment-count').textContent = `${Number(session?.segments) || 0} 段`;
  buttons();
}
async function refresh(initial = false) {
  const data = await request('GET_STATUS');
  if (initial && data.config) {
    for (const [name, input] of Object.entries(fields)) if (data.config[name] !== undefined) input.value = data.config[name];
    $('font-value').value = fields.fontSize.value;
  }
  hasKey = Boolean(data.config?.geminiApiKey);
  loaded = true;
  renderSetup();
  renderSession(data.session);
}
async function save() { if (loaded) await request('UPDATE_CONFIG', { config: readConfig() }); }
async function act(type) {
  busy = true; buttons(); showError(); clearTimeout(saveTimer);
  try {
    if (type === 'START' && !hasKey) throw new Error('請先到設定頁填入 Gemini API key，之後即可直接開始字幕。');
    const pending = request(type, type === 'START' ? { config: readConfig() } : {});
    // Poll while opening the stream so Stop remains available during startup.
    if (type === 'START') void refresh().catch(() => {});
    await pending;
    await refresh();
  } catch (error) { showError(errorText(error)); }
  finally { busy = false; buttons(); }
}
$('start').addEventListener('click', () => act('START'));
$('stop').addEventListener('click', () => act('STOP'));
$('settings-button').addEventListener('click', async () => {
  try { await chrome.runtime.openOptionsPage(); }
  catch (error) { showError(errorText(error)); }
});
for (const input of Object.values(fields)) {
  input.addEventListener('input', () => {
    $('font-value').value = fields.fontSize.value;
    renderSetup();
    clearTimeout(saveTimer);
    if (loaded) saveTimer = setTimeout(() => save().then(() => showError()).catch(error => showError(errorText(error))), 500);
  });
}

// theme.js applies the stored mode and follows storage changes; this control only reads and writes it.
const theme = globalThis.NoiseWinstonTheme;
chrome.storage.local.get({ [theme.key]: 'system' }, items => { $('theme-mode').value = theme.normalize(items[theme.key]); });
$('theme-mode').addEventListener('change', () => {
  void chrome.storage.local.set({ [theme.key]: theme.normalize($('theme-mode').value) });
});

const poll = setInterval(() => { if (loaded) refresh().catch(() => {}); }, 1000);
window.addEventListener('pagehide', () => { clearInterval(poll); clearTimeout(saveTimer); });
buttons();
refresh(true).catch(error => showError(errorText(error)));
