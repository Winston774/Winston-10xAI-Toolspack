"use strict";

const ui = Object.fromEntries([
  "status-dot", "status-text", "empty-state", "clip-panel", "clip-name", "clip-details",
  "source-link", "clip-time", "copy-button", "download-button", "clear-button",
  "error-message", "action-message", "theme-mode",
].map((id) => [id, document.getElementById(id)]));

let pendingAction = false;
let fetchingStatus = false;
let latestStatus = null;
let actionError = "";

function message(element, text) {
  element.textContent = text || "";
  element.hidden = !text;
}

function errorText(error) {
  if (!error) return "";
  return typeof error === "string" ? error : error.message || "操作失敗，請稍後重試。";
}

function formatSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "大小未知";
  const mib = bytes / (1024 * 1024);
  return mib >= 1 ? `${mib.toFixed(1)} MiB` : `${Math.max(1, Math.ceil(bytes / 1024))} KiB`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = String(total % 60).padStart(2, "0");
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${remainder}` : `${minutes}:${remainder}`;
}

function updateActions() {
  const disabled = pendingAction || Boolean(latestStatus?.busy) || !latestStatus?.clip;
  for (const id of ["copy-button", "download-button", "clear-button"]) ui[id].disabled = disabled;
}

function renderStatus(status) {
  if (latestStatus?.clip?.id !== status.clip?.id) actionError = "";
  latestStatus = status;
  const clip = status.clip;
  const busy = Boolean(status.busy);
  const error = errorText(status.lastError);
  ui["status-text"].textContent = busy ? "正在準備影片…" : clip ? "影片已備妥" : "尚未暫存影片";
  ui["status-dot"].dataset.state = busy ? "busy" : clip ? "ready" : error ? "error" : "empty";
  ui["empty-state"].hidden = Boolean(clip);
  ui["clip-panel"].hidden = !clip;
  message(ui["error-message"], actionError || error);
  if (clip) {
    ui["clip-name"].textContent = clip.name || "已複製影片.mp4";
    const dimensions = Number.isFinite(clip.width) && Number.isFinite(clip.height) && clip.width > 0 && clip.height > 0
      ? `${clip.width} × ${clip.height}` : "";
    ui["clip-details"].textContent = [formatSize(clip.size), formatDuration(clip.duration), dimensions].filter(Boolean).join(" · ");
    let sourceUrl;
    try {
      const parsed = new URL(clip.sourceUrl);
      if (["http:", "https:"].includes(parsed.protocol)) sourceUrl = parsed.href;
    } catch { /* Missing source URLs do not prevent the clip from being used. */ }
    ui["source-link"].hidden = !sourceUrl;
    if (sourceUrl) ui["source-link"].href = sourceUrl;
    else ui["source-link"].removeAttribute("href");
    const created = clip.createdAt ? new Date(clip.createdAt) : null;
    const validDate = created && Number.isFinite(created.getTime());
    ui["clip-time"].textContent = validDate ? created.toLocaleString("zh-TW", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }) : "";
    if (validDate) ui["clip-time"].dateTime = created.toISOString();
    else ui["clip-time"].removeAttribute("datetime");
  }
  updateActions();
}

async function request(type) {
  const response = await chrome.runtime.sendMessage({ type });
  if (!response?.ok) throw new Error(errorText(response?.error || response?.lastError) || "無法完成操作，請稍後重試。");
  return response;
}

async function refreshStatus() {
  if (fetchingStatus) return;
  fetchingStatus = true;
  try {
    renderStatus(await request("VC_GET_STATUS"));
  } catch (error) {
    ui["status-dot"].dataset.state = "error";
    ui["status-text"].textContent = "暫時無法讀取狀態";
    message(ui["error-message"], errorText(error));
  } finally {
    fetchingStatus = false;
  }
}

async function runAction(type, successText) {
  if (pendingAction) return;
  pendingAction = true;
  actionError = "";
  updateActions();
  message(ui["action-message"], "");
  message(ui["error-message"], "");
  try {
    await request(type);
    await refreshStatus();
    message(ui["action-message"], successText);
  } catch (error) {
    actionError = errorText(error);
    message(ui["action-message"], "");
    message(ui["error-message"], actionError);
  } finally {
    pendingAction = false;
    updateActions();
  }
}

ui["copy-button"].addEventListener("click", () => runAction("VC_COPY_MARKER", "已準備好。回到 Threads 或 Facebook 發文框按 Ctrl＋V。"));
ui["download-button"].addEventListener("click", () => runAction("VC_DOWNLOAD", "已交給 Chrome 下載，請查看下載項目。"));
ui["clear-button"].addEventListener("click", () => runAction("VC_CLEAR", "已清除暫存影片。"));

// theme.js applies the stored mode and follows storage changes; this control only reads and writes it.
const theme = globalThis.NoiseWinstonTheme;
chrome.storage.local.get({ [theme.key]: "system" }, (items) => { ui["theme-mode"].value = theme.normalize(items[theme.key]); });
ui["theme-mode"].addEventListener("change", () => {
  void chrome.storage.local.set({ [theme.key]: theme.normalize(ui["theme-mode"].value) });
});

void refreshStatus();
const pollTimer = setInterval(() => { if (!pendingAction) void refreshStatus(); }, 2000);
window.addEventListener("pagehide", () => clearInterval(pollTimer), { once: true });
