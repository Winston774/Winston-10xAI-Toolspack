"use strict";

const DEFAULT_MODEL = "gemini-3.1-flash-lite";
const SHORTCUT_KINDS = Object.freeze(["region", "viewport"]);
const SHORTCUT_DEFAULTS = Object.freeze({
  region: ShortcutUtils.DEFAULT_REGION_SHORTCUT,
  viewport: ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT
});

const elements = {};
const shortcutElements = {};
let captureShortcuts = {
  region: ShortcutUtils.normalizeShortcut(null, SHORTCUT_DEFAULTS.region),
  viewport: ShortcutUtils.normalizeShortcut(null, SHORTCUT_DEFAULTS.viewport)
};
let captureNoticeDismissed = false;
let shortcutRecordingKind = null;

document.addEventListener("DOMContentLoaded", init);

function init() {
  elements.apiKeyInput = document.querySelector("#apiKeyInput");
  elements.modelInput = document.querySelector("#modelInput");
  elements.keyStatus = document.querySelector("#keyStatus");
  elements.statusMessage = document.querySelector("#statusMessage");
  elements.saveButton = document.querySelector("#saveButton");
  elements.clearKeyButton = document.querySelector("#clearKeyButton");
  elements.testButton = document.querySelector("#testButton");
  elements.themeInputs = [...document.querySelectorAll('input[name="themeMode"]')];
  elements.themeStatus = document.querySelector("#themeStatus");
  elements.showCaptureNotice = document.querySelector("#showCaptureNotice");
  elements.captureSettingsStatus = document.querySelector("#captureSettingsStatus");

  for (const kind of SHORTCUT_KINDS) {
    const prefix = kind === "region" ? "region" : "viewport";
    shortcutElements[kind] = {
      enabled: document.querySelector(`#${prefix}ShortcutEnabled`),
      recorder: document.querySelector(`#${prefix}ShortcutRecorder`),
      preview: document.querySelector(`#${prefix}ShortcutPreview`),
      hint: document.querySelector(`#${prefix}ShortcutRecorderHint`),
      reset: document.querySelector(`#reset${prefix[0].toUpperCase()}${prefix.slice(1)}ShortcutButton`)
    };
  }

  elements.saveButton.addEventListener("click", saveSettings);
  elements.clearKeyButton.addEventListener("click", clearApiKey);
  elements.testButton.addEventListener("click", testTranslation);
  elements.themeInputs.forEach((input) => input.addEventListener("change", saveThemeMode));
  for (const kind of SHORTCUT_KINDS) {
    const controls = shortcutElements[kind];
    controls.enabled.addEventListener("change", () => handleShortcutEnabledChange(kind));
    controls.recorder.addEventListener("click", () => startShortcutRecording(kind));
    controls.recorder.addEventListener("keydown", (event) => handleShortcutRecordingKeydown(event, kind));
    controls.recorder.addEventListener("blur", () => stopShortcutRecording(kind));
    controls.reset.addEventListener("click", () => resetShortcut(kind));
  }
  elements.showCaptureNotice.addEventListener("change", handleCaptureNoticeChange);

  loadSettings();
}

async function loadSettings() {
  const response = await sendRuntimeMessage({ type: "GET_SETTINGS_STATUS" });
  if (!response?.ok) {
    setStatus("讀取設定失敗。", true);
    renderCaptureSettingsStatus("畫面擷取設定讀取失敗。", true);
    return;
  }

  elements.modelInput.value = response.model || DEFAULT_MODEL;
  renderKeyStatus(response.hasApiKey);
  renderThemeMode(response.themeMode || "system");
  captureShortcuts = {
    region: ShortcutUtils.normalizeShortcut(response.regionShortcut || response.captureShortcut, SHORTCUT_DEFAULTS.region),
    viewport: ShortcutUtils.normalizeShortcut(response.viewportShortcut, SHORTCUT_DEFAULTS.viewport)
  };
  captureNoticeDismissed = Boolean(response.captureNoticeDismissed);
  renderCaptureSettings();
}

async function saveThemeMode(event) {
  const themeMode = event.target.value;
  const response = await sendRuntimeMessage({ type: "SAVE_THEME_MODE", themeMode });

  if (!response?.ok) {
    renderThemeStatus(response?.message || "外觀模式儲存失敗。", true);
    loadSettings();
    return;
  }

  renderThemeMode(response.themeMode);
  renderThemeStatus("外觀模式已同步。", false);
}

function renderThemeMode(themeMode) {
  const normalized = globalThis.NoiseWinstonTheme?.normalize(themeMode) || "system";
  elements.themeInputs.forEach((input) => {
    input.checked = input.value === normalized;
  });
}

function renderThemeStatus(message, isError) {
  elements.themeStatus.textContent = message;
  elements.themeStatus.classList.toggle("is-error", isError);
  elements.themeStatus.classList.toggle("is-success", !isError && Boolean(message));
}

async function saveSettings() {
  const apiKey = elements.apiKeyInput.value.trim();
  const model = elements.modelInput.value.trim() || DEFAULT_MODEL;

  const response = await sendRuntimeMessage({
    type: "SAVE_SETTINGS",
    apiKey,
    model
  });

  if (!response?.ok) {
    setStatus(response?.message || "儲存失敗。", true);
    return;
  }

  elements.apiKeyInput.value = "";
  elements.modelInput.value = response.model || model;
  renderKeyStatus(response.hasApiKey);
  setStatus("設定已儲存。", false);
}

async function clearApiKey() {
  const response = await sendRuntimeMessage({ type: "CLEAR_API_KEY" });
  if (!response?.ok) {
    setStatus(response?.message || "清除失敗。", true);
    return;
  }

  elements.apiKeyInput.value = "";
  renderKeyStatus(false);
  setStatus("API key 已清除。", false);
}

async function testTranslation() {
  setStatus("測試中...", false);
  const response = await sendRuntimeMessage({ type: "TEST_GEMINI_CONNECTION" });

  if (!response?.ok) {
    setStatus(response?.message || "測試失敗。", true);
    return;
  }

  setStatus(`測試成功：${response.translation}`, false);
}

async function handleShortcutEnabledChange(kind) {
  captureShortcuts[kind] = {
    ...captureShortcuts[kind],
    enabled: shortcutElements[kind].enabled.checked
  };
  stopShortcutRecording();
  renderCaptureSettings();
  const label = shortcutKindLabel(kind);
  await persistCaptureShortcut(
    kind,
    captureShortcuts[kind].enabled ? `${label}快捷鍵已啟用。` : `${label}快捷鍵已停用。`
  );
}

function startShortcutRecording(kind) {
  if (!captureShortcuts[kind].enabled) {
    return;
  }
  stopShortcutRecording();
  shortcutRecordingKind = kind;
  shortcutElements[kind].recorder.classList.add("is-recording");
  shortcutElements[kind].hint.textContent = "請按新的組合鍵，Esc 取消";
  renderCaptureSettingsStatus(`正在錄製${shortcutKindLabel(kind)}快捷鍵；請按下至少包含 Ctrl、Alt 或 Meta 的組合鍵。`, false);
}

async function handleShortcutRecordingKeydown(event, kind) {
  if (shortcutRecordingKind !== kind) {
    return;
  }

  if (event.key === "Tab") {
    stopShortcutRecording(kind);
    return;
  }

  event.preventDefault();
  event.stopPropagation();

  if (event.key === "Escape") {
    stopShortcutRecording(kind);
    renderCaptureSettingsStatus("已取消錄製。", false);
    return;
  }

  const nextShortcut = ShortcutUtils.shortcutFromKeyboardEvent(event);
  if (!nextShortcut) {
    const message = event.ctrlKey && event.altKey
      ? "為避免 AltGraph 誤觸，請不要同時使用 Ctrl 與 Alt。"
      : "請加入 Ctrl、Alt 或 Meta，並搭配英文字母、數字、F1–F12 或導覽鍵。";
    renderCaptureSettingsStatus(message, true);
    return;
  }

  captureShortcuts[kind] = { ...nextShortcut, enabled: true };
  stopShortcutRecording(kind);
  renderCaptureSettings();
  await persistCaptureShortcut(
    kind,
    `${shortcutKindLabel(kind)}快捷鍵已改為 ${ShortcutUtils.formatShortcut(captureShortcuts[kind])}。`
  );
}

async function resetShortcut(kind) {
  captureShortcuts[kind] = ShortcutUtils.normalizeShortcut(null, SHORTCUT_DEFAULTS[kind]);
  stopShortcutRecording();
  renderCaptureSettings();
  await persistCaptureShortcut(
    kind,
    `已恢復${shortcutKindLabel(kind)}預設快捷鍵 ${ShortcutUtils.formatShortcut(captureShortcuts[kind])}，並開啟快捷鍵功能。`
  );
}

async function persistCaptureShortcut(kind, successMessage) {
  const response = await sendRuntimeMessage({
    type: "SAVE_CAPTURE_SHORTCUT",
    shortcutKind: kind,
    captureShortcut: captureShortcuts[kind]
  });
  if (!response?.ok) {
    renderCaptureSettingsStatus(response?.message || "快捷鍵儲存失敗。", true);
    await loadSettings();
    return;
  }
  captureShortcuts = {
    region: ShortcutUtils.normalizeShortcut(response.regionShortcut, SHORTCUT_DEFAULTS.region),
    viewport: ShortcutUtils.normalizeShortcut(response.viewportShortcut, SHORTCUT_DEFAULTS.viewport)
  };
  renderCaptureSettings();
  renderCaptureSettingsStatus(successMessage, false);
}

async function handleCaptureNoticeChange() {
  captureNoticeDismissed = !elements.showCaptureNotice.checked;
  const response = await sendRuntimeMessage({
    type: "SAVE_CAPTURE_NOTICE_PREFERENCE",
    captureNoticeDismissed
  });
  if (!response?.ok) {
    renderCaptureSettingsStatus(response?.message || "提示設定儲存失敗。", true);
    await loadSettings();
    return;
  }
  captureNoticeDismissed = Boolean(response.captureNoticeDismissed);
  renderCaptureSettings();
  renderCaptureSettingsStatus(
    captureNoticeDismissed ? "之後不再顯示截圖與傳送範圍提醒。" : "截圖與傳送範圍提醒已重新開啟。",
    false
  );
}

function stopShortcutRecording(kind = null) {
  if (kind && shortcutRecordingKind !== kind) {
    return;
  }
  shortcutRecordingKind = null;
  for (const shortcutKind of SHORTCUT_KINDS) {
    shortcutElements[shortcutKind].recorder.classList.remove("is-recording");
    shortcutElements[shortcutKind].hint.textContent = "點一下，再按新的組合鍵";
  }
}

function renderCaptureSettings() {
  for (const kind of SHORTCUT_KINDS) {
    const controls = shortcutElements[kind];
    controls.enabled.checked = captureShortcuts[kind].enabled;
    controls.preview.textContent = ShortcutUtils.formatShortcut(captureShortcuts[kind]);
    controls.recorder.disabled = !captureShortcuts[kind].enabled;
  }
  elements.showCaptureNotice.checked = !captureNoticeDismissed;
}

function shortcutKindLabel(kind) {
  return kind === "viewport" ? "完整可視區" : "直接框選";
}

function renderCaptureSettingsStatus(message, isError) {
  elements.captureSettingsStatus.textContent = message;
  elements.captureSettingsStatus.classList.toggle("is-error", isError);
  elements.captureSettingsStatus.classList.toggle("is-success", !isError && Boolean(message));
}

function renderKeyStatus(hasApiKey) {
  elements.keyStatus.textContent = hasApiKey ? "API key 已設定" : "尚未設定 API key";
}

function setStatus(message, isError) {
  elements.statusMessage.textContent = message;
  elements.statusMessage.classList.toggle("is-error", isError);
  elements.statusMessage.classList.toggle("is-success", !isError && Boolean(message));
}

function sendRuntimeMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        resolve({
          ok: false,
          message: error.message
        });
        return;
      }
      resolve(response);
    });
  });
}
