"use strict";

(() => {
  if (window.__geminiSelectionTranslatorLoaded) {
    return;
  }
  window.__geminiSelectionTranslatorLoaded = true;

  const translationCache = new Map();
  const state = {
    selectedText: "",
    selectedRect: null,
    isSingleWord: false,
    shouldStoreWord: false,
    pinned: false,
    closeTimer: null,
    selectionTimer: null,
    requestId: 0
  };

  const captureState = {
    active: false,
    dragging: false,
    jobId: null,
    pointerId: null,
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
    initialViewport: null,
    initialScrollX: 0,
    initialScrollY: 0,
    initialUrl: "",
    generation: 0,
    pendingJobId: null,
    pendingGeneration: 0,
    startSequence: 0,
    lastViewportChangeAt: Date.now(),
    verification: null,
    verificationTimer: null
  };

  const shortcutState = {
    region: ShortcutUtils.normalizeShortcut(null, ShortcutUtils.DEFAULT_REGION_SHORTCUT),
    viewport: ShortcutUtils.normalizeShortcut(null, ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT),
    ready: false
  };

  const root = document.createElement("div");
  root.id = "gst-root";
  root.innerHTML = [
    '<button id="gst-translate-icon" type="button" aria-label="翻譯選取文字"><img src="' + chrome.runtime.getURL("icons/icon-32.png") + '" alt=""></button>',
    '<section id="gst-popover" role="dialog" aria-live="polite" hidden>',
    '  <div class="gst-popover-header">',
    '    <p id="gst-title">翻譯</p>',
    '    <div class="gst-actions">',
    '      <button id="gst-pin-button" class="gst-small-button" type="button">釘選</button>',
    '      <button id="gst-close-button" class="gst-small-button" type="button">關閉</button>',
    "    </div>",
    "  </div>",
    '  <div id="gst-body"></div>',
    '  <p id="gst-meta"></p>',
    '  <button id="gst-open-options" class="gst-link-button" type="button" hidden>開啟設定</button>',
    "</section>",
    '<div id="gst-capture-layer" tabindex="-1" role="application" aria-label="框選要辨識的畫面文字" hidden>',
    '  <div id="gst-capture-instruction">',
    "    <strong>拖曳框選要辨識的文字</strong>",
    "    <span>放開滑鼠完成 · Esc 取消 · 請先暫停影片</span>",
    "  </div>",
    '  <div id="gst-capture-rect" hidden><span id="gst-capture-size"></span></div>',
    "</div>"
  ].join("");
  document.documentElement.appendChild(root);
  globalThis.NoiseWinstonTheme?.register(root);

  const icon = root.querySelector("#gst-translate-icon");
  const popover = root.querySelector("#gst-popover");
  const title = root.querySelector("#gst-title");
  const body = root.querySelector("#gst-body");
  const meta = root.querySelector("#gst-meta");
  const pinButton = root.querySelector("#gst-pin-button");
  const closeButton = root.querySelector("#gst-close-button");
  const optionsButton = root.querySelector("#gst-open-options");
  const captureLayer = root.querySelector("#gst-capture-layer");
  const captureInstruction = root.querySelector("#gst-capture-instruction");
  const captureRect = root.querySelector("#gst-capture-rect");
  const captureSize = root.querySelector("#gst-capture-size");

  document.addEventListener("mouseup", scheduleSelectionSync, true);
  document.addEventListener("keyup", scheduleSelectionSync, true);
  document.addEventListener("selectionchange", scheduleSelectionSync, true);
  document.addEventListener("mousedown", handleOutsidePointer, true);
  window.addEventListener("scroll", handleViewportMove, true);
  window.addEventListener("resize", handleViewportMove, true);
  document.addEventListener("visibilitychange", handleVisibilityChange, true);
  window.addEventListener("keydown", handleCaptureKeydown, true);
  loadCapturePreferences();

  captureLayer.addEventListener("pointerdown", handleCapturePointerDown);
  captureLayer.addEventListener("pointermove", handleCapturePointerMove);
  captureLayer.addEventListener("pointerup", handleCapturePointerUp);
  captureLayer.addEventListener("pointercancel", () => cancelCapture("pointer_cancelled"));

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "START_CAPTURE_SELECTION") {
      startCapture(message.jobId, message.generation).then(sendResponse);
      return true;
    }

    if (message?.type === "PREPARE_FULL_VIEWPORT_CAPTURE") {
      prepareFullViewportCapture(message.jobId, message.generation).then(sendResponse);
      return true;
    }

    if (message?.type === "VERIFY_CAPTURE_DOCUMENT") {
      sendResponse(verifyCaptureDocument(message));
      return false;
    }

    if (message?.type === "CANCEL_CAPTURE_SELECTION") {
      if (
        !message.jobId ||
        message.jobId === captureState.jobId ||
        message.jobId === captureState.pendingJobId ||
        message.jobId === captureState.verification?.jobId
      ) {
        cancelCapture("cancelled_by_panel", false);
      }
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "GEMINI_SETTINGS_CHANGED") {
      translationCache.clear();
      sendResponse({ ok: true });
      return false;
    }

    if (message?.type === "CAPTURE_SHORTCUTS_CHANGED") {
      shortcutState.region = ShortcutUtils.normalizeShortcut(
        message.regionShortcut,
        ShortcutUtils.DEFAULT_REGION_SHORTCUT
      );
      shortcutState.viewport = ShortcutUtils.normalizeShortcut(
        message.viewportShortcut,
        ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT
      );
      shortcutState.ready = true;
      sendResponse({ ok: true });
      return false;
    }

    return false;
  });

  icon.addEventListener("mouseenter", showTranslation);
  icon.addEventListener("focus", showTranslation);
  icon.addEventListener("click", showTranslation);
  icon.addEventListener("mouseleave", scheduleClose);
  popover.addEventListener("mouseenter", cancelClose);
  popover.addEventListener("mouseleave", scheduleClose);

  pinButton.addEventListener("click", () => {
    state.pinned = !state.pinned;
    pinButton.classList.toggle("gst-active", state.pinned);
    pinButton.textContent = state.pinned ? "已釘選" : "釘選";
    cancelClose();
  });

  closeButton.addEventListener("click", () => {
    state.pinned = false;
    hidePopover();
    hideIcon();
  });

  optionsButton.addEventListener("click", () => {
    sendRuntimeMessage({ type: "OPEN_OPTIONS" });
  });

  function scheduleSelectionSync() {
    if (captureState.active) {
      return;
    }
    if (state.pinned && !popover.hidden) {
      return;
    }

    window.clearTimeout(state.selectionTimer);
    state.selectionTimer = window.setTimeout(syncSelection, 80);
  }

  function syncSelection() {
    const details = readSelection();
    if (!details) {
      if (!state.pinned) {
        hidePopover();
        hideIcon();
      }
      return;
    }

    if (details.text === state.selectedText && icon.classList.contains("gst-visible")) {
      return;
    }

    state.selectedText = details.text;
    state.selectedRect = details.rect;
    state.isSingleWord = isSingleWord(details.text);
    state.shouldStoreWord =
      state.isSingleWord && !isMostlyChinese(details.text) && hasMeaningfulCharacter(details.text);
    state.pinned = false;
    pinButton.classList.remove("gst-active");
    pinButton.textContent = "釘選";

    hidePopover();
    positionIcon(details.rect);
    icon.classList.add("gst-visible");
  }

  function readSelection() {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return null;
    }

    const text = selection.toString().replace(/\u00a0/g, " ").trim();
    if (!text) {
      return null;
    }

    const range = selection.getRangeAt(0);
    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
    const rect = rects[rects.length - 1] || range.getBoundingClientRect();
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      return null;
    }

    return {
      text,
      rect
    };
  }

  function positionIcon(rect) {
    const left = clamp(rect.right + 8, 8, window.innerWidth - 38);
    const top = clamp(rect.bottom + 6, 8, window.innerHeight - 38);
    icon.style.left = `${left}px`;
    icon.style.top = `${top}px`;
  }

  function showTranslation() {
    if (!state.selectedText) {
      return;
    }

    cancelClose();
    positionPopover();

    const cached = translationCache.get(state.selectedText);
    if (cached) {
      renderTranslation(cached, true);
      return;
    }

    renderLoading();
    const requestId = ++state.requestId;

    sendRuntimeMessage({
      type: "TRANSLATE_SELECTION",
      text: state.selectedText,
      isSingleWord: state.isSingleWord,
      shouldStoreWord: state.shouldStoreWord
    }).then((response) => {
      if (requestId !== state.requestId) {
        return;
      }

      if (!response || !response.ok) {
        renderError(response);
        return;
      }

      translationCache.set(state.selectedText, response);
      renderTranslation(response, false);
    });
  }

  function renderLoading() {
    title.textContent = "翻譯中";
    body.textContent = "";
    body.classList.add("gst-loading");
    meta.textContent = "";
    optionsButton.hidden = true;
    popover.hidden = false;
    window.requestAnimationFrame(positionPopover);
  }

  function renderTranslation(response, fromCache) {
    body.classList.remove("gst-loading");
    title.textContent = response.savedWord ? "翻譯，已存入單字庫" : "翻譯";
    body.textContent = response.translation || "";

    const metaParts = [];
    if (response.partOfSpeech) {
      metaParts.push(response.partOfSpeech);
    }
    if (fromCache) {
      metaParts.push("本頁快取");
    }
    if (response.model) {
      metaParts.push(response.model);
    }
    meta.textContent = metaParts.join(" · ");
    optionsButton.hidden = true;
    popover.hidden = false;
    window.requestAnimationFrame(positionPopover);
  }

  function renderError(response) {
    const code = response?.code || "unexpected_error";
    body.classList.remove("gst-loading");
    title.textContent = "無法翻譯";
    body.textContent = response?.message || "發生未知錯誤。";
    meta.textContent = code === "missing_api_key" ? "Key 會存於此瀏覽器的 Extension storage；它不是秘密保管庫。" : "";
    optionsButton.hidden = code !== "missing_api_key";
    popover.hidden = false;
    window.requestAnimationFrame(positionPopover);
  }

  function positionPopover() {
    if (popover.hidden) {
      return;
    }

    const iconRect = icon.getBoundingClientRect();
    const width = popover.offsetWidth || 360;
    const height = popover.offsetHeight || 180;
    let left = iconRect.right + 8;
    let top = iconRect.bottom + 8;

    if (left + width > window.innerWidth - 12) {
      left = iconRect.left - width - 8;
    }
    if (left < 12) {
      left = 12;
    }
    if (top + height > window.innerHeight - 12) {
      top = Math.max(12, window.innerHeight - height - 12);
    }

    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
  }

  function scheduleClose() {
    if (state.pinned) {
      return;
    }

    cancelClose();
    state.closeTimer = window.setTimeout(() => {
      if (!state.pinned) {
        hidePopover();
      }
    }, 260);
  }

  function cancelClose() {
    window.clearTimeout(state.closeTimer);
    state.closeTimer = null;
  }

  function hidePopover() {
    cancelClose();
    popover.hidden = true;
    body.classList.remove("gst-loading");
    optionsButton.hidden = true;
  }

  function hideIcon() {
    icon.classList.remove("gst-visible");
    state.selectedText = "";
    state.selectedRect = null;
  }

  function handleOutsidePointer(event) {
    if (captureState.active) {
      return;
    }
    if (root.contains(event.target)) {
      return;
    }

    if (!state.pinned) {
      hidePopover();
    }
  }

  function handleViewportMove() {
    captureState.lastViewportChangeAt = Date.now();
    if (captureState.active) {
      if (captureState.dragging) {
        cancelCapture("viewport_changed");
      } else {
        captureState.initialViewport = {
          width: window.innerWidth,
          height: window.innerHeight
        };
        captureState.initialScrollX = window.scrollX;
        captureState.initialScrollY = window.scrollY;
        captureState.initialUrl = location.href;
        captureState.pointerId = null;
        captureRect.hidden = true;
        captureLayer.classList.remove("gst-dragging");
      }
      return;
    }
    if (state.pinned) {
      positionPopover();
      return;
    }

    hidePopover();
    hideIcon();
  }

  async function startCapture(jobId, generation = 0) {
    const normalizedJobId = String(jobId || "").trim();
    if (!normalizedJobId) {
      return {
        ok: false,
        code: "invalid_capture_job",
        message: "框選工作識別碼不正確。"
      };
    }

    if (captureState.active || captureState.pendingJobId || captureState.verification) {
      cancelCapture("restarted", false);
    }

    clearVerification();
    hidePopover();
    hideIcon();
    window.getSelection()?.removeAllRanges();

    const sequence = ++captureState.startSequence;
    captureState.pendingJobId = normalizedJobId;
    captureState.pendingGeneration = Number(generation) || 0;
    const stable = await waitForStableCaptureViewport(sequence, normalizedJobId);
    if (!stable) {
      const stale = captureState.startSequence !== sequence || captureState.pendingJobId !== normalizedJobId;
      if (!stale) {
        captureState.pendingJobId = null;
        captureState.pendingGeneration = 0;
      }
      return {
        ok: false,
        code: stale ? "stale_capture_job" : "document_changed",
        message: stale ? "這次框選已由較新的操作取代。" : "頁面尚未穩定，請再試一次。"
      };
    }

    captureState.pendingJobId = null;
    captureState.pendingGeneration = 0;

    captureState.active = true;
    captureState.dragging = false;
    captureState.jobId = normalizedJobId;
    captureState.generation = Number(generation) || 0;
    captureState.pointerId = null;
    captureState.initialViewport = {
      width: window.innerWidth,
      height: window.innerHeight
    };
    captureState.initialScrollX = window.scrollX;
    captureState.initialScrollY = window.scrollY;
    captureState.initialUrl = location.href;

    captureInstruction.querySelector("strong").textContent = "拖曳框選要辨識的文字";
    captureInstruction.querySelector("span").textContent = "放開滑鼠完成 · Esc 取消 · 請先暫停影片";
    captureRect.hidden = true;
    captureLayer.classList.remove("gst-dragging");
    captureLayer.hidden = false;
    root.classList.add("gst-capture-active");
    captureLayer.focus({ preventScroll: true });

    return { ok: true };
  }

  async function prepareFullViewportCapture(jobId, generation = 0) {
    const normalizedJobId = String(jobId || "").trim();
    if (!normalizedJobId) {
      return {
        ok: false,
        code: "invalid_capture_job",
        message: "畫面擷取工作識別碼不正確。"
      };
    }

    if (captureState.active || captureState.pendingJobId || captureState.verification) {
      cancelCapture("viewport_capture", false);
    }
    clearVerification();
    hidePopover();
    hideIcon();
    window.getSelection()?.removeAllRanges();

    const sequence = ++captureState.startSequence;
    captureState.pendingJobId = normalizedJobId;
    captureState.pendingGeneration = Number(generation) || 0;
    const stable = await waitForStableCaptureViewport(sequence, normalizedJobId);
    if (!stable) {
      const stale = captureState.startSequence !== sequence || captureState.pendingJobId !== normalizedJobId;
      if (!stale) {
        captureState.pendingJobId = null;
        captureState.pendingGeneration = 0;
      }
      return {
        ok: false,
        code: stale ? "stale_capture_job" : "document_changed",
        message: stale ? "這次擷取已由較新的操作取代。" : "頁面尚未穩定，請再試一次。"
      };
    }
    captureState.pendingJobId = null;
    captureState.pendingGeneration = 0;

    const verification = {
      jobId: normalizedJobId,
      generation: Number(generation) || 0,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      url: location.href
    };
    captureState.verification = verification;

    await nextTwoAnimationFrames();
    if (captureState.startSequence !== sequence) {
      return {
        ok: false,
        code: "stale_capture_job",
        message: "這次擷取已由較新的操作取代。"
      };
    }
    if (!verificationStillValid(verification)) {
      clearVerification();
      return {
        ok: false,
        code: "document_changed",
        message: "頁面、縮放或可視範圍已變更，請再試一次。"
      };
    }

    scheduleVerificationClear(verification, 30000);
    return {
      ok: true,
      viewport: { ...verification.viewport }
    };
  }

  function handleCapturePointerDown(event) {
    if (!captureState.active || !event.isPrimary || event.button !== 0) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    captureState.dragging = true;
    captureState.pointerId = event.pointerId;
    captureState.startX = clamp(event.clientX, 0, window.innerWidth);
    captureState.startY = clamp(event.clientY, 0, window.innerHeight);
    captureState.endX = captureState.startX;
    captureState.endY = captureState.startY;
    captureLayer.setPointerCapture(event.pointerId);
    captureLayer.classList.add("gst-dragging");
    captureRect.hidden = false;
    renderCaptureRect();
  }

  function handleCapturePointerMove(event) {
    if (!captureState.active || !captureState.dragging || event.pointerId !== captureState.pointerId) {
      return;
    }
    event.preventDefault();
    captureState.endX = clamp(event.clientX, 0, window.innerWidth);
    captureState.endY = clamp(event.clientY, 0, window.innerHeight);
    renderCaptureRect();
  }

  function handleCapturePointerUp(event) {
    if (!captureState.active || !captureState.dragging || event.pointerId !== captureState.pointerId) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    captureState.endX = clamp(event.clientX, 0, window.innerWidth);
    captureState.endY = clamp(event.clientY, 0, window.innerHeight);
    captureState.dragging = false;
    if (captureLayer.hasPointerCapture(event.pointerId)) {
      captureLayer.releasePointerCapture(event.pointerId);
    }

    const rect = currentCaptureRect();
    if (rect.width < 16 || rect.height < 16) {
      captureState.pointerId = null;
      captureLayer.classList.remove("gst-dragging");
      captureRect.hidden = true;
      captureInstruction.querySelector("strong").textContent = "範圍太小，請重新框選";
      captureInstruction.querySelector("span").textContent = "至少需要 16 × 16 像素 · Esc 取消";
      return;
    }

    finishCapture(rect);
  }

  async function finishCapture(rect) {
    const jobId = captureState.jobId;
    const verification = {
      jobId,
      generation: captureState.generation,
      viewport: { ...captureState.initialViewport },
      scrollX: captureState.initialScrollX,
      scrollY: captureState.initialScrollY,
      url: captureState.initialUrl
    };

    captureState.active = false;
    captureState.dragging = false;
    captureState.pointerId = null;
    captureState.jobId = null;
    captureState.verification = verification;
    captureLayer.hidden = true;
    captureLayer.classList.remove("gst-dragging");
    captureRect.hidden = true;
    root.classList.remove("gst-capture-active");

    await nextTwoAnimationFrames();
    if (!verificationStillValid(verification)) {
      sendRuntimeMessage({
        type: "CAPTURE_SELECTION_CANCELLED",
        jobId,
        generation: verification.generation,
        reason: "document_changed"
      });
      clearVerification(verification);
      return;
    }

    sendRuntimeMessage({
      type: "CAPTURE_SELECTION_READY",
      jobId,
      generation: verification.generation,
      rect,
      viewport: verification.viewport
    }).finally(() => {
      scheduleVerificationClear(verification, 3000);
    });
  }

  function cancelCapture(reason, notify = true) {
    const jobId = captureState.jobId || captureState.pendingJobId || captureState.verification?.jobId;
    const generation = captureState.generation || captureState.pendingGeneration || captureState.verification?.generation || 0;
    const wasActive = captureState.active;
    captureState.startSequence += 1;
    captureState.active = false;
    captureState.dragging = false;
    captureState.jobId = null;
    captureState.generation = 0;
    captureState.pendingJobId = null;
    captureState.pendingGeneration = 0;
    captureState.pointerId = null;
    captureLayer.hidden = true;
    captureLayer.classList.remove("gst-dragging");
    captureRect.hidden = true;
    root.classList.remove("gst-capture-active");
    clearVerification();

    if (notify && jobId && wasActive) {
      sendRuntimeMessage({
        type: "CAPTURE_SELECTION_CANCELLED",
        jobId,
        generation,
        reason: String(reason || "cancelled")
      });
    }
  }

  function verifyCaptureDocument(message) {
    const verification = captureState.verification;
    const expected = message?.viewport;
    const sameViewport =
      Number(expected?.width) === window.innerWidth &&
      Number(expected?.height) === window.innerHeight;

    return {
      ok: Boolean(
        verification &&
        verification.jobId === message?.jobId &&
        (!Number.isInteger(Number(message?.generation)) || Number(message.generation) === Number(verification.generation || 0)) &&
        verificationStillValid(verification) &&
        sameViewport
      )
    };
  }

  function verificationStillValid(verification) {
    return Boolean(
      verification &&
      document.visibilityState === "visible" &&
      location.href === verification.url &&
      window.innerWidth === verification.viewport.width &&
      window.innerHeight === verification.viewport.height &&
      window.scrollX === verification.scrollX &&
      window.scrollY === verification.scrollY
    );
  }

  function clearVerification(expected = null) {
    if (
      expected &&
      (
        captureState.verification?.jobId !== expected.jobId ||
        Number(captureState.verification?.generation || 0) !== Number(expected.generation || 0)
      )
    ) {
      return;
    }
    window.clearTimeout(captureState.verificationTimer);
    captureState.verificationTimer = null;
    captureState.verification = null;
  }

  function scheduleVerificationClear(verification, timeoutMs) {
    if (
      captureState.verification?.jobId !== verification?.jobId ||
      Number(captureState.verification?.generation || 0) !== Number(verification?.generation || 0)
    ) {
      return;
    }
    window.clearTimeout(captureState.verificationTimer);
    captureState.verificationTimer = window.setTimeout(() => clearVerification(verification), timeoutMs);
  }

  function renderCaptureRect() {
    const rect = currentCaptureRect();
    captureRect.style.left = `${rect.left}px`;
    captureRect.style.top = `${rect.top}px`;
    captureRect.style.width = `${rect.width}px`;
    captureRect.style.height = `${rect.height}px`;
    captureSize.textContent = `${Math.round(rect.width)} × ${Math.round(rect.height)}`;
  }

  function currentCaptureRect() {
    const left = Math.min(captureState.startX, captureState.endX);
    const top = Math.min(captureState.startY, captureState.endY);
    const right = Math.max(captureState.startX, captureState.endX);
    const bottom = Math.max(captureState.startY, captureState.endY);
    return {
      left,
      top,
      right,
      bottom,
      width: right - left,
      height: bottom - top
    };
  }

  function handleCaptureKeydown(event) {
    if ((captureState.active || captureState.pendingJobId) && event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancelCapture("escape");
      return;
    }

    if (
      !shortcutState.ready ||
      event.isTrusted !== true ||
      isEditableTarget(event)
    ) {
      return;
    }

    const regionMatch = ShortcutUtils.matchesKeyboardEvent(event, shortcutState.region);
    const viewportMatch = ShortcutUtils.matchesKeyboardEvent(event, shortcutState.viewport);
    if (regionMatch === viewportMatch) {
      return;
    }
    const captureMode = regionMatch ? "region" : "viewport";

    event.preventDefault();
    event.stopImmediatePropagation();
    if (captureState.active || captureState.pendingJobId || captureState.verification) {
      cancelCapture("shortcut_restarted", false);
    }
    sendRuntimeMessage({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode }).catch(() => undefined);
  }

  async function loadCapturePreferences() {
    const response = await sendRuntimeMessage({ type: "GET_CAPTURE_PREFERENCES" });
    if (response?.ok) {
      shortcutState.region = ShortcutUtils.normalizeShortcut(
        response.regionShortcut || response.captureShortcut,
        ShortcutUtils.DEFAULT_REGION_SHORTCUT
      );
      shortcutState.viewport = ShortcutUtils.normalizeShortcut(
        response.viewportShortcut,
        ShortcutUtils.DEFAULT_VIEWPORT_SHORTCUT
      );
      shortcutState.ready = true;
    }
  }

  function isEditableTarget(event) {
    if (String(document.designMode || "").toLowerCase() === "on") {
      return true;
    }
    const path = event.composedPath?.() || [event.target];
    return path.some((target) => {
      if (!target || typeof target.matches !== "function") {
        return false;
      }
      return Boolean(
        target.isContentEditable ||
        target.matches('input, textarea, select, [role="textbox"], [contenteditable]:not([contenteditable="false"])')
      );
    });
  }

  function handleVisibilityChange() {
    if ((captureState.active || captureState.pendingJobId) && document.visibilityState !== "visible") {
      cancelCapture("tab_hidden");
    }
  }

  function nextTwoAnimationFrames() {
    return new Promise((resolve) => {
      window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
    });
  }

  async function waitForStableCaptureViewport(sequence, jobId) {
    const deadline = Date.now() + 1400;
    while (Date.now() < deadline) {
      if (
        captureState.startSequence !== sequence ||
        captureState.pendingJobId !== jobId ||
        document.visibilityState !== "visible"
      ) {
        return false;
      }

      if (Date.now() - captureState.lastViewportChangeAt >= 160) {
        const before = captureViewportSnapshot();
        await nextTwoAnimationFrames();
        const after = captureViewportSnapshot();
        if (
          captureState.startSequence === sequence &&
          captureState.pendingJobId === jobId &&
          document.visibilityState === "visible" &&
          sameCaptureViewport(before, after) &&
          Date.now() - captureState.lastViewportChangeAt >= 160
        ) {
          return true;
        }
      }

      await new Promise((resolve) => window.setTimeout(resolve, 40));
    }
    return false;
  }

  function captureViewportSnapshot() {
    return {
      width: window.innerWidth,
      height: window.innerHeight,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      url: location.href
    };
  }

  function sameCaptureViewport(left, right) {
    return left.width === right.width &&
      left.height === right.height &&
      left.scrollX === right.scrollX &&
      left.scrollY === right.scrollY &&
      left.url === right.url;
  }

  function isSingleWord(text) {
    return Boolean(text && !/\s/.test(text.trim()));
  }

  function hasMeaningfulCharacter(text) {
    return /[\p{L}\p{N}]/u.test(text);
  }

  function isMostlyChinese(text) {
    const compact = text.replace(/\s/g, "");
    if (!compact) {
      return false;
    }

    let chineseCount = 0;
    for (const char of compact) {
      const code = char.codePointAt(0);
      if (
        (code >= 0x3400 && code <= 0x4dbf) ||
        (code >= 0x4e00 && code <= 0x9fff) ||
        (code >= 0xf900 && code <= 0xfaff)
      ) {
        chineseCount += 1;
      }
    }

    return chineseCount / compact.length >= 0.5;
  }

  function sendRuntimeMessage(message) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (response) => {
        const error = chrome.runtime.lastError;
        if (error) {
          resolve({
            ok: false,
            code: "runtime_error",
            message: error.message
          });
          return;
        }
        resolve(response);
      });
    });
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }
})();
