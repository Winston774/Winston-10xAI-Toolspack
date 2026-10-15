(() => {
  "use strict";
  const platform = location.hostname === "www.facebook.com" ? "Facebook"
    : ["threads.com", "www.threads.com", "threads.net", "www.threads.net"].includes(location.hostname) ? "Threads" : null;
  if (!platform || globalThis.__videoBridgeSocialLoaded) return;
  globalThis.__videoBridgeSocialLoaded = true;

  const CHUNK_BYTES = 256 * 1024;
  const MAX_FILE_BYTES = 150 * 1024 * 1024;
  const MARKER_PREFIX = "video-bridge:";
  const EXCLUDED_COMPOSER = /留言|評論|回覆|回復|訊息|消息|comment|repl(?:y|ies)|message|chat/i;
  const POST_COMPOSER = /新貼文|新串文|新增串文|建立貼文|發佈貼文|發表貼文|撰寫貼文|在想些什麼|有什麼新鮮事|create\s+(?:a\s+)?post|new\s+(?:post|thread)|start\s+(?:a\s+)?thread|what[’']?s\s+on\s+your\s+mind|what[’']?s\s+new/i;
  const inserted = new WeakMap();
  let clip = null;
  let backgroundBusy = false;
  let importing = false;
  let activeComposer = null;
  let refreshPromise = null;
  let uiTimer;
  let toastTimer;
  let controlHost;
  let insertButton;
  let toastHost;
  let toastText;

  function isVisible(element) {
    if (!element?.isConnected || element.hidden || element.closest("[hidden],[aria-hidden='true'],[inert]")) return false;
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden" && style.visibility !== "collapse";
  }

  function labels(element) {
    const referenced = (element.getAttribute("aria-labelledby") || "").split(/\s+/)
      .filter(Boolean).map((id) => document.getElementById(id)?.textContent || "");
    return [element.getAttribute("aria-label"), element.getAttribute("data-placeholder"), element.getAttribute("placeholder"), ...referenced].filter(Boolean).join(" ");
  }

  function editableFields(dialog) {
    return [...dialog.querySelectorAll("[contenteditable='true'],[role='textbox'],textarea")].filter((editor) => {
      const nativeEditable = editor.tagName === "TEXTAREA" || (editor.tagName === "INPUT" && ["text", "search", "url", "email", "tel"].includes(editor.type));
      return isVisible(editor) && editor.closest("[role='dialog']") === dialog
        && (editor.isContentEditable || nativeEditable) && !editor.disabled && !editor.readOnly
        && editor.getAttribute("aria-readonly") !== "true" && editor.getAttribute("aria-disabled") !== "true";
    });
  }

  function isPostComposer(dialog, editor) {
    const title = [labels(dialog), ...[...dialog.querySelectorAll("h1,h2,h3,[role='heading']")]
      .filter((heading) => isVisible(heading) && heading.closest("[role='dialog']") === dialog).map((heading) => heading.textContent || "")].join(" ");
    const editorLabel = labels(editor);
    return !EXCLUDED_COMPOSER.test(title) && !EXCLUDED_COMPOSER.test(editorLabel) && POST_COMPOSER.test(`${title} ${editorLabel}`);
  }

  function visibleEditorDialogs() {
    return [...document.querySelectorAll("[role='dialog']")].filter((dialog) => isVisible(dialog) && editableFields(dialog).length > 0);
  }

  function videoInputs(dialog) {
    return [...dialog.querySelectorAll("input[type='file']")].filter((input) => {
      if (input.disabled || input.getAttribute("aria-disabled") === "true" || input.closest("[role='dialog']") !== dialog
        || input.parentElement?.closest("[hidden],[aria-hidden='true'],[inert]")) return false;
      const accept = input.accept.trim().toLowerCase();
      return !accept || accept.split(",").some((part) => /^(video\/[^\s]+|\.(?:mp4|m4v|mov|webm))$/.test(part.trim()));
    });
  }

  function captureComposer(dialog) {
    if (!(dialog instanceof Element) || !dialog.matches("[role='dialog']") || !isVisible(dialog)) {
      throw new Error("原本的發文視窗已關閉，請重新開啟後再插入影片。");
    }
    const dialogs = visibleEditorDialogs();
    if (dialogs.length !== 1 || dialogs[0] !== dialog) throw new Error(`請保留一個 ${platform} 發文視窗，再插入影片。`);
    const editors = editableFields(dialog);
    if (editors.length !== 1) throw new Error("發文視窗內有多個輸入區，無法安全判斷，請重新開啟發文視窗。");
    if (!isPostComposer(dialog, editors[0])) throw new Error(`請開啟 ${platform} 的新貼文視窗，再插入影片。`);
    const inputs = videoInputs(dialog);
    if (!inputs.length) {
      const action = platform === "Threads" ? "附加影音內容" : "相片／影片";
      throw new Error(`找不到影片附件欄位，請先點發文框內的「${action}」，再按「插入已複製影片」。`);
    }
    if (inputs.length !== 1) throw new Error("發文框內有多個附件欄位，無法安全判斷，請重新開啟發文視窗後重試。");
    return { dialog, editor: editors[0], input: inputs[0] };
  }

  function assertCurrentComposer(composer) {
    if (composer.invalidated) throw new Error("原本的發文視窗已變更或關閉，請在目前的發文視窗重新插入影片。");
    const current = captureComposer(composer.dialog);
    if (current.editor !== composer.editor || current.input !== composer.input) {
      throw new Error("發文輸入區已變更，請在目前的發文視窗重新插入影片。");
    }
  }

  // Noise Winston Extension Kit: colours come from noise-winston/tokens.css, which the
  // manifest injects into the page; the host carries [data-nw-root] so tokens resolve on it.
  const TOAST_CSS = ":host{all:initial;position:fixed;right:20px;top:20px;z-index:2147483647;pointer-events:none;max-width:min(380px,calc(100vw - 40px))}:host([hidden]){display:none!important}div{display:flex;align-items:flex-start;gap:10px;padding:11px 16px 11px 14px;border-radius:12px;background:var(--nw-surface-raised,#fff);color:var(--nw-text,#111);box-shadow:var(--nw-shadow-raised,0 0 0 1px rgba(17,17,17,.08),0 14px 36px rgba(17,17,17,.14));font:500 13px/1.55 var(--nw-font-body,system-ui,sans-serif);-webkit-font-smoothing:antialiased;overflow-wrap:anywhere;animation:nw-in 180ms cubic-bezier(.16,1,.3,1)}div::before{content:\"\";flex:0 0 auto;width:7px;height:7px;margin-top:7px;border-radius:50%;background:var(--nw-action,#7432FF)}div[data-state=working]::before{animation:nw-pulse 1.2s ease-in-out infinite}div[data-state=ready]::before{background:var(--nw-success,#18A76B)}div[data-state=error]::before{background:var(--nw-error,#DB1B1B)}@keyframes nw-in{from{opacity:0;transform:translateY(-4px)}}@keyframes nw-pulse{50%{opacity:.35}}@media (prefers-reduced-motion:reduce){div,div::before{animation:none!important}}";
  const CONTROL_CSS = ":host{all:initial;position:fixed;right:24px;bottom:24px;z-index:2147483646}:host([hidden]){display:none!important}button{display:inline-flex;align-items:center;gap:10px;min-height:44px;padding:0 20px 0 16px;border:0;border-radius:999px;background:var(--nw-action,#7432FF);color:var(--nw-on-action,#fff);font:600 14px/1 var(--nw-font-body,system-ui,sans-serif);-webkit-font-smoothing:antialiased;cursor:pointer;box-shadow:0 1px 2px rgba(17,17,17,.2),0 12px 32px rgba(17,17,17,.24);transition:background-color 120ms cubic-bezier(.2,0,0,1)}button::before{content:\"\";flex:0 0 auto;width:8px;height:8px;border-radius:50%;background:var(--nw-result,#DFF813)}button:hover:not(:disabled){background:var(--nw-action-hover,#5B20E6)}button:active:not(:disabled){transform:translateY(1px)}button:focus-visible{outline:2px solid var(--nw-focus,#1877F2);outline-offset:3px}button:disabled{cursor:progress;opacity:.82}button:disabled::before{background:var(--nw-on-action,#fff);animation:nw-pulse 1.2s ease-in-out infinite}@keyframes nw-pulse{50%{opacity:.35}}@media (prefers-reduced-motion:reduce){button::before{animation:none!important}}";

  // state: "working" | "ready" | "error"; true is accepted as "error".
  function showToast(message, state = "working") {
    if (state === true) state = "error";
    if (!toastHost?.isConnected) {
      toastHost = document.createElement("div");
      toastHost.setAttribute("data-video-bridge-toast", "");
      toastHost.setAttribute("data-nw-root", "");
      const shadow = toastHost.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = TOAST_CSS;
      toastText = document.createElement("div");
      toastText.setAttribute("role", "status");
      toastText.setAttribute("aria-live", "polite");
      shadow.append(style, toastText);
      document.documentElement.append(toastHost);
      globalThis.NoiseWinstonTheme?.register(toastHost);
    }
    toastText.textContent = String(message).slice(0, 350);
    toastText.dataset.state = state;
    toastHost.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastHost.hidden = true; }, state === "error" ? 8000 : 5000);
  }

  async function request(message) {
    try {
      const result = await chrome.runtime.sendMessage(message);
      if (!result?.ok) throw new Error(result?.error || "外掛沒有回應，請重新載入頁面後再試。");
      return result;
    } catch (error) {
      if (/Extension context invalidated/i.test(error.message || "")) throw new Error(`外掛已更新，請重新載入 ${platform} 頁面後再試。`);
      throw error;
    }
  }

  async function refreshStatus() {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const result = await request({ type: "VC_GET_STATUS" });
      clip = result.clip || null;
      backgroundBusy = Boolean(result.busy);
      updateControl();
      return result;
    })();
    try { return await refreshPromise; }
    finally { refreshPromise = null; }
  }

  function ensureControl() {
    if (controlHost?.isConnected) return;
    controlHost = document.createElement("div");
    controlHost.setAttribute("data-video-bridge-control", "");
    controlHost.setAttribute("data-nw-root", "");
    const shadow = controlHost.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = CONTROL_CSS;
    insertButton = document.createElement("button");
    insertButton.type = "button";
    insertButton.addEventListener("click", (event) => {
      if (!event.isTrusted) return;
      const dialogs = visibleEditorDialogs();
      if (dialogs.length !== 1) { showToast(`請保留一個 ${platform} 發文視窗，再插入影片。`, true); return; }
      void importClip(dialogs[0]);
    });
    shadow.append(style, insertButton);
    document.documentElement.append(controlHost);
    globalThis.NoiseWinstonTheme?.register(controlHost);
  }

  function updateControl() {
    const dialogs = visibleEditorDialogs();
    const editors = dialogs.length === 1 ? editableFields(dialogs[0]) : [];
    if (!clip || editors.length !== 1 || !isPostComposer(dialogs[0], editors[0])) {
      if (controlHost && !controlHost.hidden) controlHost.hidden = true;
      return;
    }
    ensureControl();
    if (controlHost.hidden) controlHost.hidden = false;
    insertButton.disabled = importing || backgroundBusy;
    const label = importing ? "正在插入影片…" : backgroundBusy ? "正在準備影片…" : `插入已複製影片至 ${platform}`;
    if (insertButton.textContent !== label) insertButton.textContent = label;
    const title = `將${clip.name ? `「${clip.name}」` : "已複製影片"}加入目前的 ${platform} 發文視窗`;
    if (insertButton.title !== title) insertButton.title = title;
  }

  async function readClipFile(metadata, checkComposer) {
    if (!metadata || typeof metadata.id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(metadata.id)
      || !Number.isSafeInteger(metadata.size) || metadata.size <= 0 || metadata.size > MAX_FILE_BYTES) {
      throw new Error("暫存影片資訊無效或超過 150 MiB，請重新複製影片。");
    }
    const parts = [];
    let offset = 0;
    while (offset < metadata.size) {
      checkComposer();
      const length = Math.min(CHUNK_BYTES, metadata.size - offset);
      const result = await request({ type: "VC_READ_CHUNK", id: metadata.id, offset, length });
      checkComposer();
      if (result.total !== metadata.size || typeof result.base64 !== "string") throw new Error("暫存影片已變更，請重新複製後再貼上。");
      if (result.base64.length !== 4 * Math.ceil(length / 3) || !/^[A-Za-z0-9+/]*={0,2}$/.test(result.base64)) throw new Error("影片資料不完整，請重新複製後再貼上。");
      const binary = atob(result.base64);
      if (binary.length !== length) throw new Error("影片資料不完整，請重新複製後再貼上。");
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
      parts.push(bytes);
      offset += bytes.length;
      if (result.eof !== (offset === metadata.size)) throw new Error("影片資料長度不一致，請重新複製後再貼上。");
    }
    return new File(parts, metadata.name || "copied-video.mp4", { type: metadata.mime || "video/mp4", lastModified: metadata.createdAt || Date.now() });
  }

  function sameFile(first, second) {
    return first.name === second.name && first.size === second.size && first.type === second.type;
  }

  function attachFileToComposer(composer, file) {
    assertCurrentComposer(composer);
    const input = composer.input;
    const accept = input.accept.trim().toLowerCase();
    if (accept && !accept.split(",").some((part) => {
      const token = part.trim();
      return token === file.type.toLowerCase() || (token === "video/*" && file.type.startsWith("video/"))
        || (token.startsWith(".") && file.name.toLowerCase().endsWith(token));
    })) throw new Error("目前的附件欄位不支援這種影片格式，請重新開啟發文視窗。");
    const existing = [...(input.files || [])];
    if (existing.some((item) => sameFile(item, file))) throw new Error(`這支影片已在附件欄位中，請確認 ${platform} 的附件預覽。`);
    if (existing.length && !input.multiple) throw new Error("這個附件欄位已有檔案，請先確認或移除原附件，再插入影片。");
    const transfer = new DataTransfer();
    for (const item of existing) transfer.items.add(item);
    transfer.items.add(file);
    input.files = transfer.files;
    if (![...input.files].some((item) => sameFile(item, file))) throw new Error(`${platform} 未接受影片檔案，請重新開啟發文視窗後再試。`);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return { name: file.name, size: file.size };
  }

  async function importClip(dialog, marker) {
    if (importing) { showToast("正在插入影片，請稍候。"); return; }
    importing = true;
    updateControl();
    try {
      const composer = captureComposer(dialog);
      activeComposer = composer;
      const status = await refreshStatus();
      assertCurrentComposer(composer);
      if (status.busy) throw new Error("影片仍在準備中，請等候「影片已備妥」後再貼上。");
      const selected = status.clip;
      if (!selected) throw new Error("尚未複製影片，請先到 Threads 或 X 在影片上按右鍵複製。");
      if (marker !== undefined && marker !== MARKER_PREFIX + selected.id) {
        throw new Error("剪貼簿對應的影片已過期，請重新複製影片，或按「插入已複製影片」使用目前暫存影片。");
      }
      if (inserted.get(dialog)?.has(selected.id)) throw new Error("這個發文視窗已插入此影片，請確認附件預覽。若已移除，請重開發文視窗後再試。");
      showToast("正在讀取並插入影片…");
      const file = await readClipFile(selected, () => assertCurrentComposer(composer));
      attachFileToComposer(composer, file);
      if (!inserted.has(dialog)) inserted.set(dialog, new Set());
      inserted.get(dialog).add(selected.id);
      showToast(`已交給 ${platform}，請確認附件預覽與上傳完成，再自行發佈。`, "ready");
    } catch (error) {
      showToast(error.message || "插入影片失敗，請重新複製後再試。", true);
    } finally {
      activeComposer = null;
      importing = false;
      updateControl();
    }
  }

  document.addEventListener("paste", (event) => {
    if (!event.isTrusted || !event.clipboardData || event.clipboardData.files.length > 0 || !(event.target instanceof Element)) return;
    const marker = event.clipboardData.getData("text/plain");
    if (!/^video-bridge:[A-Za-z0-9_-]{1,128}$/.test(marker)) return;
    const dialog = event.target.closest("[role='dialog']");
    if (!dialog || !isVisible(dialog)) return;
    const dialogs = visibleEditorDialogs();
    const editors = editableFields(dialog);
    if (dialogs.length !== 1 || dialogs[0] !== dialog || editors.length !== 1 || !isPostComposer(dialog, editors[0])) return;
    if (editors[0] !== event.target && !editors[0].contains(event.target)) return;
    // 先同步攔截專用標記，再向外掛確認目前影片。一般文字與檔案貼上保持原有行為。
    event.preventDefault();
    event.stopImmediatePropagation();
    void importClip(dialog, marker);
  }, true);

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "VC_STATUS") return;
    // Threads also loads source-content.js, which already shows source-job status.
    if (message.message && platform === "Facebook") showToast(message.message, ["ready", "error"].includes(message.state) ? message.state : "working");
    void refreshStatus().catch(() => {});
  });

  new MutationObserver((records) => {
    if (activeComposer) {
      const tracked = [activeComposer.dialog, activeComposer.editor, activeComposer.input];
      for (const record of records) {
        const removedTrackedNode = record.type === "childList" && [...record.removedNodes].some((node) =>
          tracked.some((element) => node === element || node.contains?.(element)));
        const changedAvailability = record.type === "attributes"
          && ["hidden", "aria-hidden", "inert", "role", "contenteditable", "aria-readonly", "aria-disabled", "disabled", "readonly"].includes(record.attributeName)
          && tracked.some((element) => record.target === element || record.target.contains(element));
        // 即使平台在同一次更新中關閉後重開並沿用 DOM，也保留原匯入失效狀態。
        if (removedTrackedNode || changedAvailability) activeComposer.invalidated = true;
      }
      try { assertCurrentComposer(activeComposer); }
      catch { activeComposer.invalidated = true; }
    }
    clearTimeout(uiTimer);
    uiTimer = setTimeout(updateControl, 120);
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true,
    attributeFilter: ["hidden", "aria-hidden", "role", "contenteditable", "aria-label", "aria-labelledby", "aria-readonly", "aria-disabled", "disabled", "readonly", "inert", "style", "class"] });
  window.addEventListener("focus", () => { void refreshStatus().catch(() => {}); });
  void refreshStatus().catch(() => {});
})();
