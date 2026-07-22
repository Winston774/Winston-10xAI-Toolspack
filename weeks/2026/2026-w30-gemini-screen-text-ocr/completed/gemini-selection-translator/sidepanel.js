"use strict";

const PANEL_PORT_NAME = "gst-screen-text-panel";
const state = {
  job: null,
  crop: null,
  result: null,
  model: "",
  latencyMs: null,
  lastError: null,
  translate: true,
  noticeDismissed: false,
  noticeAcknowledgedJobId: null,
  windowId: null,
  resetting: false,
  port: null,
  generation: 0,
  actionSequence: 0,
  regionShortcut: ShortcutUtils.normalizeShortcut(null, ShortcutUtils.DEFAULT_REGION_SHORTCUT),
  viewportShortcut: ShortcutUtils.normalizeShortcut(null, ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT)
};

const elements = {};
const viewIds = ["pendingView", "selectingView", "previewView", "runningView", "resultView", "errorView"];

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindElements();
  bindEvents();
  connectPanel();
  render();
  await loadCapturePreferences();
  render();
}

function bindElements() {
  for (const id of viewIds) {
    elements[id] = document.querySelector(`#${id}`);
  }
  const ids = [
    "settingsButton", "pageTitle", "pendingDisclosureSlot", "previewDisclosureSlot", "captureDisclosure", "consentCheckbox",
    "startSelectionButton", "captureViewportButton", "pendingNote", "selectingTitle", "selectingDescription",
    "cancelSelectionButton", "cropMeta", "cropPreview",
    "redoPreviewButton", "runOcrButton", "discardPreviewButton", "languagePill", "noTextNotice",
    "transcriptBlock", "transcriptText", "copyTranscriptButton", "translationBlock", "translationText",
    "copyTranslationButton", "unclearBlock", "unclearList", "resultMeta", "newSelectionButton",
    "finishButton", "copyStatus", "errorTitle", "errorMessage", "retryOcrButton", "retrySelectionButton",
    "errorSettingsButton", "dismissErrorButton"
  ];
  for (const id of ids) {
    elements[id] = document.querySelector(`#${id}`);
  }
}

function bindEvents() {
  elements.settingsButton.addEventListener("click", openSettings);
  elements.errorSettingsButton.addEventListener("click", openSettings);
  elements.consentCheckbox.addEventListener("change", handleConsentChange);
  elements.startSelectionButton.addEventListener("click", startSelection);
  elements.captureViewportButton.addEventListener("click", captureFullViewport);
  elements.cancelSelectionButton.addEventListener("click", resetJobToPending);
  elements.redoPreviewButton.addEventListener("click", startSelection);
  elements.retrySelectionButton.addEventListener("click", startSelection);
  elements.newSelectionButton.addEventListener("click", startSelection);
  elements.runOcrButton.addEventListener("click", runOcr);
  elements.retryOcrButton.addEventListener("click", runOcr);
  elements.discardPreviewButton.addEventListener("click", resetJobToPending);
  elements.dismissErrorButton.addEventListener("click", resetJobToPending);
  elements.finishButton.addEventListener("click", resetJobToPending);
  elements.copyTranscriptButton.addEventListener("click", () => copyText(elements.transcriptText.value, "原文已複製"));
  elements.copyTranslationButton.addEventListener("click", () => copyText(elements.translationText.value, "譯文已複製"));
  window.addEventListener("keydown", handlePanelShortcutKeydown, true);
  document.querySelectorAll('input[name="ocrMode"]').forEach((input) => {
    input.addEventListener("change", () => {
      state.translate = document.querySelector('input[name="ocrMode"]:checked')?.value !== "transcribe";
    });
  });
}

function connectPanel() {
  const port = chrome.runtime.connect({ name: PANEL_PORT_NAME });
  state.port = port;
  port.onMessage.addListener(handlePortMessage);
  port.onDisconnect.addListener(() => {
    if (state.port === port) {
      state.port = null;
      window.setTimeout(connectPanel, 300);
    }
  });
  chrome.windows.getCurrent((windowInfo) => {
    if (chrome.runtime.lastError) {
      port.postMessage({ type: "PANEL_READY", windowId: null });
      return;
    }
    state.windowId = Number.isInteger(windowInfo?.id) ? windowInfo.id : null;
    port.postMessage({ type: "PANEL_READY", windowId: state.windowId });
  });
}

function handlePortMessage(message) {
  if (!message || typeof message.type !== "string") {
    return;
  }

  if (message.type === "CAPTURE_SHORTCUTS_CHANGED") {
    state.regionShortcut = ShortcutUtils.normalizeShortcut(
      message.regionShortcut,
      ShortcutUtils.DEFAULT_REGION_SHORTCUT
    );
    state.viewportShortcut = ShortcutUtils.normalizeShortcut(
      message.viewportShortcut,
      ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT
    );
    return;
  }

  if (message.type === "CAPTURE_JOB_STATE") {
    if (!adoptPanelJob(message.job || null, message.generation)) {
      return;
    }
    if (!state.job) {
      resetTransientState();
    } else if (["preview", "result"].includes(state.job.state) && !state.crop) {
      state.lastError = {
        code: "preview_expired",
        message: "裁切預覽只保留在面板記憶體中；面板重新載入後需要再框選一次。"
      };
    } else if (state.job.error) {
      state.lastError = state.job.error;
    }
    render();
    return;
  }

  if (message.type === "CAPTURE_PREVIEW_READY") {
    if (!adoptPanelJob(message.job, message.job?.generation)) {
      return;
    }
    state.crop = message.crop;
    state.result = null;
    state.lastError = null;
    render();
    return;
  }

  if (message.type === "CAPTURE_SELECTION_CANCELLED") {
    if (!adoptPanelJob(message.job, message.job?.generation)) {
      return;
    }
    state.lastError = null;
    elements.pendingNote.textContent = "已取消框選，圖片沒有送出。";
    render();
    return;
  }

  if (message.type === "CAPTURE_JOB_ERROR") {
    if (!adoptPanelJob(message.job, message.job?.generation)) {
      return;
    }
    state.lastError = message.error || message.job?.error || null;
    render();
    return;
  }

  if (message.type === "CAPTURE_OCR_RESULT") {
    if (!adoptPanelJob(message.job, message.job?.generation)) {
      return;
    }
    applyResult(message);
    return;
  }

  if (message.type === "CAPTURE_NOTICE_CHANGED") {
    state.noticeDismissed = Boolean(message.captureNoticeDismissed);
    if (!state.noticeDismissed) {
      state.noticeAcknowledgedJobId = null;
    }
    render();
  }
}

function adoptPanelJob(job, messageGeneration = 0) {
  const nextGeneration = Number(job?.generation ?? messageGeneration) || 0;
  if (nextGeneration < state.generation) {
    return false;
  }
  if (
    job &&
    state.job &&
    nextGeneration === state.generation &&
    job.id !== state.job.id
  ) {
    return false;
  }

  const changedJob = Boolean(job && state.job?.id !== job.id);
  const clearedJob = Boolean(!job && state.job);
  if (changedJob) {
    clearTransientResult();
    state.lastError = null;
    state.noticeAcknowledgedJobId = null;
  }
  if (changedJob || clearedJob) {
    state.actionSequence += 1;
  }
  state.resetting = false;
  state.generation = Math.max(state.generation, nextGeneration);
  state.job = job || null;
  return true;
}

function render() {
  let view = state.lastError ? "errorView" : "pendingView";
  if (state.job && !state.lastError) {
    if (state.lastError || state.job.state === "error") {
      view = "errorView";
    } else if (state.job.state === "pending") {
      view = "pendingView";
    } else if (["selecting", "capturing"].includes(state.job.state)) {
      view = "selectingView";
    } else if (state.job.state === "preview") {
      view = state.crop ? "previewView" : "errorView";
    } else if (state.job.state === "running") {
      view = "runningView";
    } else if (state.job.state === "result") {
      view = state.result ? "resultView" : "errorView";
    }
  }

  for (const id of viewIds) {
    elements[id].hidden = id !== view;
  }

  if (view === "pendingView") {
    elements.pageTitle.textContent = state.job?.pageTitle || "正在準備";
    const acknowledgedForCurrentJob = state.noticeAcknowledgedJobId === state.job?.id;
    const canCapture = Boolean(state.job) && !state.resetting && (state.noticeDismissed || acknowledgedForCurrentJob);
    renderDisclosure(elements.pendingDisclosureSlot, acknowledgedForCurrentJob);
    elements.startSelectionButton.disabled = !canCapture;
    elements.captureViewportButton.disabled = !canCapture;
    if (!state.job || state.resetting) {
      elements.pendingNote.textContent = "正在準備目前分頁…";
    } else if (elements.pendingNote.textContent === "正在準備目前分頁…") {
      elements.pendingNote.textContent = "";
    }
  } else if (view === "selectingView") {
    const isViewport = state.job?.captureMode === "viewport";
    elements.selectingTitle.textContent = isViewport ? "正在擷取完整可視區" : "請在網頁上拖曳框選";
    elements.selectingDescription.textContent = isViewport
      ? "請保持目前分頁與縮放不變；完成後會先顯示預覽，不會直接送出。"
      : "放開滑鼠後會自動裁切；按 Esc 可取消。框選期間不要捲動、縮放或切換分頁。";
  } else if (view === "previewView") {
    const acknowledgedForCurrentJob = state.noticeAcknowledgedJobId === state.job?.id;
    renderDisclosure(elements.previewDisclosureSlot, acknowledgedForCurrentJob);
    elements.runOcrButton.disabled = !(state.noticeDismissed || acknowledgedForCurrentJob);
    renderPreview();
  } else if (view === "resultView") {
    renderResult();
  } else if (view === "errorView") {
    renderError();
  }
}

function renderDisclosure(slot, acknowledgedForCurrentJob) {
  if (elements.captureDisclosure.parentElement !== slot) {
    slot.appendChild(elements.captureDisclosure);
  }
  elements.captureDisclosure.hidden = state.noticeDismissed;
  elements.consentCheckbox.checked = acknowledgedForCurrentJob;
}

function renderPreview() {
  if (!state.crop) {
    return;
  }
  elements.cropPreview.src = state.crop.dataUrl;
  elements.cropMeta.textContent = `${state.crop.width} × ${state.crop.height} · ${formatBytes(state.crop.byteLength)}`;
}

function renderResult() {
  const result = state.result;
  if (!result) {
    return;
  }
  elements.languagePill.textContent = languageLabel(result.sourceLanguage);
  elements.noTextNotice.hidden = result.hasText;
  elements.transcriptBlock.hidden = !result.hasText;
  elements.transcriptText.value = result.transcript || "";
  elements.translationBlock.hidden = !result.translation;
  elements.translationText.value = result.translation || "";
  elements.unclearBlock.hidden = !result.unclearSegments?.length;
  elements.unclearList.textContent = "";
  for (const segment of result.unclearSegments || []) {
    const item = document.createElement("li");
    item.textContent = segment;
    elements.unclearList.appendChild(item);
  }
  const details = [state.model, contentTypeLabel(result.contentType)];
  if (Number.isFinite(state.latencyMs)) {
    details.push(`${(state.latencyMs / 1000).toFixed(1)} 秒`);
  }
  elements.resultMeta.textContent = details.filter(Boolean).join(" · ");
}

function renderError() {
  const error = state.lastError || state.job?.error || {
    code: "unexpected_error",
    message: "發生未知錯誤。"
  };
  const authError = ["missing_api_key", "auth_error"].includes(error.code);
  elements.errorTitle.textContent = errorTitle(error.code);
  elements.errorMessage.textContent = error.message || "發生未知錯誤。";
  elements.errorSettingsButton.hidden = !authError;
  elements.retryOcrButton.hidden = !state.crop || ["preview_expired", "image_too_large", "request_too_large"].includes(error.code);
  elements.retrySelectionButton.textContent = state.crop ? "改用新的框選範圍" : "重新框選";
}

async function handleConsentChange() {
  if (!elements.consentCheckbox.checked || !state.job?.id) {
    return;
  }
  state.noticeAcknowledgedJobId = state.job.id;
  render();
  const response = await sendRuntimeMessage({ type: "DISMISS_CAPTURE_NOTICE" });
  if (!response?.ok) {
    state.noticeAcknowledgedJobId = null;
    elements.pendingNote.textContent = response?.message || "無法儲存提示設定，請再試一次。";
    render();
  }
}

async function loadCapturePreferences() {
  const response = await sendRuntimeMessage({ type: "GET_CAPTURE_PREFERENCES" });
  if (!response?.ok) {
    return;
  }
  state.noticeDismissed = Boolean(response.captureNoticeDismissed);
  state.regionShortcut = ShortcutUtils.normalizeShortcut(
    response.regionShortcut || response.captureShortcut,
    ShortcutUtils.DEFAULT_REGION_SHORTCUT
  );
  state.viewportShortcut = ShortcutUtils.normalizeShortcut(
    response.viewportShortcut,
    ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT
  );
}

function startSelection() {
  return beginCaptureIntent("region", "panel_button");
}

function captureFullViewport() {
  return beginCaptureIntent("viewport", "panel_button");
}

async function beginCaptureIntent(captureMode, source) {
  if (!Number.isInteger(state.windowId)) {
    state.lastError = {
      code: "active_tab_missing",
      message: "找不到目前的瀏覽器視窗，請重新開啟面板。"
    };
    render();
    return;
  }

  const actionSequence = ++state.actionSequence;
  state.resetting = false;
  state.crop = null;
  elements.cropPreview.removeAttribute("src");
  state.result = null;
  state.lastError = null;
  elements.pendingNote.textContent = "";
  if (state.job) {
    state.job = {
      ...state.job,
      state: captureMode === "viewport" ? "capturing" : "selecting",
      captureMode,
      error: null
    };
  }
  render();

  const response = await sendRuntimeMessage({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode,
    windowId: state.windowId,
    source
  });
  if (state.actionSequence !== actionSequence) {
    return;
  }
  if (response?.ok && response.job) {
    state.job = response.job;
    state.generation = Math.max(state.generation, Number(response.job.generation) || 0);
    render();
  } else if (!response?.ok) {
    if (response.code === "stale_capture_job") {
      return;
    }
    if (state.job) {
      state.job = { ...state.job, state: "error", error: response };
    }
    state.lastError = response;
    render();
  }
}

function handlePanelShortcutKeydown(event) {
  if (event.isTrusted !== true) {
    return;
  }
  const regionMatch = ShortcutUtils.matchesKeyboardEvent(event, state.regionShortcut);
  const viewportMatch = ShortcutUtils.matchesKeyboardEvent(event, state.viewportShortcut);
  if (regionMatch === viewportMatch) {
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  beginCaptureIntent(regionMatch ? "region" : "viewport", "panel_shortcut");
}

async function runOcr() {
  const acknowledgedForCurrentJob = state.noticeAcknowledgedJobId === state.job?.id;
  if (!state.noticeDismissed && !acknowledgedForCurrentJob) {
    render();
    return;
  }
  if (!state.job || !state.crop) {
    state.lastError = {
      code: "preview_expired",
      message: "裁切預覽已經清除，請重新框選。"
    };
    render();
    return;
  }
  const jobId = state.job.id;
  const actionSequence = ++state.actionSequence;
  state.lastError = null;
  state.job = { ...state.job, state: "running" };
  render();
  const response = await sendRuntimeMessage({
    type: "RUN_CAPTURE_OCR",
    jobId,
    imageDataUrl: state.crop.dataUrl,
    translate: state.translate
  });
  if (state.actionSequence !== actionSequence || state.job?.id !== jobId) {
    return;
  }
  if (response?.ok) {
    applyResult(response);
  } else {
    if (["request_aborted", "stale_capture_job"].includes(response?.code)) {
      return;
    }
    state.job = { ...state.job, state: "error", error: response };
    state.lastError = response;
    render();
  }
}

function applyResult(message) {
  if (!message?.result) {
    return;
  }
  state.job = message.job || { ...state.job, state: "result" };
  state.result = message.result;
  state.crop = null;
  elements.cropPreview.removeAttribute("src");
  state.model = message.model || "";
  state.latencyMs = Number(message.latencyMs);
  state.lastError = null;
  render();
}

async function resetJobToPending() {
  if (state.resetting) {
    return;
  }
  const actionSequence = ++state.actionSequence;
  const jobId = state.job?.id;
  state.resetting = true;
  clearTransientResult();
  if (state.job) {
    state.job = {
      ...state.job,
      state: "pending",
      captureMode: null,
      error: null
    };
  }
  render();
  const response = await sendRuntimeMessage({
    type: "RESET_CAPTURE_JOB",
    jobId,
    windowId: state.windowId
  });
  if (state.actionSequence !== actionSequence) {
    return;
  }
  state.resetting = false;
  if (response?.ok && response.job) {
    state.job = response.job;
    state.generation = Math.max(state.generation, Number(response.job.generation) || 0);
    elements.pendingNote.textContent = "";
  } else {
    state.job = response?.job || state.job;
    state.lastError = response || {
      code: "active_tab_missing",
      message: "無法準備目前分頁，請重新開啟面板。"
    };
  }
  render();
}

function resetTransientState() {
  clearTransientResult();
  state.job = null;
  state.noticeAcknowledgedJobId = null;
}

function clearTransientResult() {
  if (elements.cropPreview) {
    elements.cropPreview.removeAttribute("src");
  }
  state.crop = null;
  state.result = null;
  state.model = "";
  state.latencyMs = null;
  state.lastError = null;
  elements.copyStatus.textContent = "";
}

async function copyText(text, successMessage) {
  if (!text) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    elements.copyStatus.textContent = successMessage;
  } catch (error) {
    elements.copyStatus.textContent = "無法存取剪貼簿，請手動選取文字複製。";
  }
}

function openSettings() {
  sendRuntimeMessage({ type: "OPEN_OPTIONS" });
}

function sendRuntimeMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        resolve({ ok: false, code: "runtime_error", message: error.message });
        return;
      }
      resolve(response);
    });
  });
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function languageLabel(value) {
  if (!value || value === "und") {
    return "語言未知";
  }
  if (value === "mul") {
    return "多語混合";
  }
  return value;
}

function contentTypeLabel(value) {
  const labels = {
    plain: "一般文字",
    table: "表格",
    code: "程式碼",
    formula: "數學式",
    mixed: "混合內容"
  };
  return labels[value] || "";
}

function errorTitle(code) {
  if (code === "missing_api_key") return "尚未連接 Gemini";
  if (code === "auth_error") return "API Key 無效或權限不足";
  if (code === "rate_limited") return "Gemini 目前額度或速率受限";
  if (["timeout", "service_unavailable", "network_unavailable"].includes(code)) return "Gemini 暫時無法回應";
  if (["tab_changed", "document_changed"].includes(code)) return "頁面已經變更";
  if (code === "unsupported_page") return "這個頁面不支援框選";
  if (code === "preview_expired") return "裁切預覽已清除";
  return "無法完成這次處理";
}
