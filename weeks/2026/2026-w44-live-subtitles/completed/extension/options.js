import { targetLanguageLabel } from './lib/languages.js';

const $ = id => document.getElementById(id);
const keyInput = $('gemini-api-key');
let savedKey = '';
let targetLanguage = 'zh-Hant';
let busy = false;
let loaded = false;

function errorText(error) { return error?.message || (typeof error === 'string' ? error : '操作未完成，請重試。'); }
async function request(type, extra = {}) {
  const result = await chrome.runtime.sendMessage({ type, ...extra });
  if (!result?.ok) throw new Error(errorText(result?.error || '擴充功能未回應，請重新開啟設定頁。'));
  return result;
}
function showMessage(message = '', kind = '') {
  $('status-message').textContent = message;
  $('status-message').classList.toggle('is-error', kind === 'error');
  $('status-message').classList.toggle('is-success', kind === 'success');
}
function render() {
  const typed = keyInput.value.trim();
  $('key-status').textContent = !loaded ? '載入中' : savedKey ? 'API key 已設定' : '尚未設定 API key';
  if (loaded) $('key-status').dataset.state = savedKey ? 'ready' : 'idle';
  $('save-key').disabled = busy || !loaded || !typed || typed === savedKey;
  $('check-gemini').disabled = busy || !loaded || !typed;
  $('clear-key').disabled = busy || !loaded || !savedKey;
  keyInput.disabled = busy || !loaded;
}
async function load() {
  const { config } = await request('GET_STATUS');
  savedKey = config?.geminiApiKey || '';
  targetLanguage = config?.targetLanguage || targetLanguage;
  keyInput.value = savedKey;
  loaded = true;
  render();
}
async function run(task) {
  busy = true; render();
  try { await task(); }
  catch (error) { showMessage(errorText(error), 'error'); }
  finally { busy = false; render(); }
}
async function saveKey(value) {
  const { config } = await request('UPDATE_CONFIG', { config: { geminiApiKey: value } });
  savedKey = config.geminiApiKey;
  targetLanguage = config.targetLanguage;
  keyInput.value = savedKey;
}

$('save-key').addEventListener('click', () => run(async () => {
  await saveKey(keyInput.value);
  showMessage('API key 已儲存。回到發出聲音的分頁即可開始字幕。', 'success');
}));
$('check-gemini').addEventListener('click', () => run(async () => {
  showMessage('正在連接 Gemini…');
  if (keyInput.value.trim() !== savedKey) await saveKey(keyInput.value);
  try { await request('CHECK_GEMINI', { config: { geminiApiKey: savedKey } }); }
  catch (error) { keyInput.setAttribute('aria-invalid', 'true'); throw error; }
  showMessage(`Gemini 連線成功，目標為${targetLanguageLabel(targetLanguage)}。測試連線沒有傳送音訊。`, 'success');
}));
$('clear-key').addEventListener('click', () => run(async () => {
  await saveKey('');
  showMessage('API key 已清除。需要字幕時再貼上新的金鑰。', 'success');
}));
$('toggle-key').addEventListener('click', () => {
  const visible = keyInput.type === 'password';
  keyInput.type = visible ? 'text' : 'password';
  $('toggle-key').textContent = visible ? '隱藏' : '顯示';
  $('toggle-key').setAttribute('aria-pressed', String(visible));
  $('toggle-key').setAttribute('aria-label', visible ? '隱藏 Gemini API key' : '顯示 Gemini API key');
});
keyInput.addEventListener('input', () => { keyInput.removeAttribute('aria-invalid'); showMessage(); render(); });

render();
load().catch(error => showMessage(errorText(error), 'error'));
