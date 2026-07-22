import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

async function createHarness(options = {}) {
  const [source, shortcutSource, manifestSource] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../lib/shortcut-utils.js", import.meta.url), "utf8"),
    readFile(new URL("../manifest.json", import.meta.url), "utf8")
  ]);
  const manifest = JSON.parse(manifestSource);
  const hasAllUrls = options.hasAllUrls ?? manifest.host_permissions.includes("<all_urls>");
  let activeTabGranted = Boolean(options.activeTabGranted);
  const localStore = {
    gstGeminiApiKey: "test-key",
    gstGeminiModel: "gemini-3.5-flash-lite",
    gstThemeMode: "system",
    gstWordBank: [],
    ...(options.localStore || {})
  };
  const sessionStore = { ...(options.sessionStore || {}) };
  let activeTab = { id: 7, windowId: 2, title: "Fixture page", url: "https://example.com/" };
  let jobSequence = 0;
  let messageListener;
  let connectListener;
  let commandListener;
  let sidePanelOpenCount = 0;
  const tabMessages = [];
  const panelMessages = [];
  const captureVisibleCalls = [];
  const deferredCaptureCallbacks = [];
  const deferredGeminiRequests = [];
  const deferredSessionGets = [];

  const chrome = {
    runtime: {
      id: "test-extension",
      lastError: null,
      onInstalled: { addListener() {} },
      onConnect: { addListener(listener) { connectListener = listener; } },
      onMessage: { addListener(listener) { messageListener = listener; } },
      getURL(path) { return `chrome-extension://test-extension/${path}`; },
      openOptionsPage(callback) { callback(); }
    },
    commands: {
      onCommand: { addListener(listener) { commandListener = listener; } }
    },
    sidePanel: {
      async open() { sidePanelOpenCount += 1; }
    },
    windows: {
      WINDOW_ID_CURRENT: -2
    },
    tabs: {
      query(queryInfo, callback) {
        callback(Number.isInteger(queryInfo?.windowId) && queryInfo.windowId !== activeTab.windowId
          ? []
          : [{ ...activeTab }]);
      },
      sendMessage(tabId, message, options, callback) {
        tabMessages.push({ tabId, message, options });
        if (message.type === "PREPARE_FULL_VIEWPORT_CAPTURE") {
          callback({ ok: true, viewport: { width: 800, height: 600 } });
          return;
        }
        callback({ ok: true });
      },
      captureVisibleTab(windowId, imageOptions, callback) {
        captureVisibleCalls.push({ windowId, options: imageOptions, startedAt: Date.now() });
        if (options.deferCaptureVisibleTab) {
          deferredCaptureCallbacks.push(callback);
          return;
        }
        if (options.captureVisibleError) {
          chrome.runtime.lastError = { message: String(options.captureVisibleError) };
          callback(undefined);
          chrome.runtime.lastError = null;
          return;
        }
        if (!hasAllUrls && !activeTabGranted) {
          chrome.runtime.lastError = {
            message: "Either the '<all_urls>' or 'activeTab' permission is required."
          };
          callback(undefined);
          chrome.runtime.lastError = null;
          return;
        }
        callback("data:image/png;base64,AQID");
      }
    },
    storage: {
      local: createStorageArea(localStore),
      session: createStorageArea(sessionStore, {
        deferGet: Boolean(options.deferSessionGet),
        pendingGets: deferredSessionGets
      })
    }
  };

  const context = {
    AbortController,
    CaptureUtils: {
      MAX_IMAGE_BYTES: 10 * 1024 * 1024,
      MAX_REQUEST_BYTES: 20 * 1024 * 1024,
      parseDataUrl() { return options.fullCapture ? { mimeType: "image/png", byteLength: 3 } : null; },
      utf8ByteLength(value) { return String(value || "").length; },
      validateSelection() {
        if (options.regionCapture) {
          return {
            ok: true,
            rect: { left: 10, top: 20, right: 210, bottom: 120, width: 200, height: 100 },
            viewport: { width: 800, height: 600, scrollX: 0, scrollY: 0 }
          };
        }
        return options.fullCapture
          ? { ok: true, viewport: { width: 800, height: 600, scrollX: 0, scrollY: 0 } }
          : { ok: false };
      },
      computeCropRect() {
        return { x: 10, y: 20, width: 200, height: 100 };
      }
    },
    GeminiClient: {
      async requestStructured(requestOptions) {
        if (options.geminiError) {
          throw options.geminiError;
        }
        const isOcr = Boolean(requestOptions?.responseSchema?.properties?.has_text);
        if (isOcr && options.deferGemini) {
          return new Promise((resolve, reject) => {
            requestOptions.signal?.addEventListener("abort", () => {
              const error = new Error("superseded");
              error.code = "request_aborted";
              error.retryable = false;
              reject(error);
            }, { once: true });
            deferredGeminiRequests.push({ resolve, reject });
          });
        }
        if (isOcr) {
          return createOcrResponse();
        }
        return {
          data: { translation: "你好", partOfSpeech: "感嘆詞" },
          model: "gemini-3.5-flash-lite",
          usage: null
        };
      }
    },
    chrome,
    crypto: { randomUUID: () => `job-fixture-${++jobSequence}` },
    createImageBitmap: async () => ({ width: 800, height: 600, close() {} }),
    fetch: async () => ({ blob: async () => ({}) }),
    OffscreenCanvas: class {
      getContext() { return { drawImage() {} }; }
      async convertToBlob() {
        return {
          size: 3,
          type: "image/png",
          async arrayBuffer() { return Uint8Array.from([1, 2, 3]).buffer; }
        };
      }
    },
    btoa: (value) => Buffer.from(value, "binary").toString("base64"),
    importScripts() {},
    performance: { now: () => 10 },
    clearTimeout,
    setTimeout,
    TextEncoder
  };
  context.globalThis = context;
  vm.runInNewContext(shortcutSource, context);
  vm.runInNewContext(source, context);

  async function send(message, sender) {
    return new Promise((resolve, reject) => {
      const keepChannel = messageListener(message, sender, resolve);
      if (!keepChannel) {
        reject(new Error(`No route for ${message.type}`));
      }
    });
  }

  return {
    chrome,
    commandListener,
    localStore,
    sessionStore,
    get sidePanelOpenCount() {
      return sidePanelOpenCount;
    },
    panelMessages,
    tabMessages,
    captureVisibleCalls,
    async connectPanel(windowId = 2) {
      const messageListeners = [];
      const disconnectListeners = [];
      const port = {
        name: "gst-screen-text-panel",
        sender: {
          id: "test-extension",
          url: "chrome-extension://test-extension/sidepanel.html"
        },
        onDisconnect: { addListener(listener) { disconnectListeners.push(listener); } },
        onMessage: { addListener(listener) { messageListeners.push(listener); } },
        postMessage(message) { panelMessages.push(message); },
        disconnect() { disconnectListeners.forEach((listener) => listener()); }
      };
      connectListener(port);
      messageListeners.forEach((listener) => listener({ type: "PANEL_READY", windowId }));
      await new Promise((resolve) => setTimeout(resolve, 0));
      return port;
    },
    send,
    setActiveTab(tab) {
      activeTab = { ...tab };
    },
    grantActiveTab() {
      activeTabGranted = true;
    },
    resolveNextCapture(dataUrl = "data:image/png;base64,AQID") {
      const callback = deferredCaptureCallbacks.shift();
      if (!callback) {
        throw new Error("No deferred capture callback is waiting");
      }
      callback(dataUrl);
    },
    get pendingGeminiRequests() {
      return deferredGeminiRequests.length;
    },
    resolveNextGemini(result = createOcrResponse()) {
      const request = deferredGeminiRequests.shift();
      if (!request) {
        throw new Error("No deferred Gemini request is waiting");
      }
      request.resolve(result);
    },
    get pendingSessionGets() {
      return deferredSessionGets.length;
    },
    resolveNextSessionGet() {
      const resolveGet = deferredSessionGets.shift();
      if (!resolveGet) {
        throw new Error("No deferred session get is waiting");
      }
      resolveGet();
    }
  };
}

function createOcrResponse() {
  return {
    data: {
      has_text: true,
      source_language: "en",
      transcript: "hello",
      translation: "哈囉",
      unclear_segments: [],
      content_type: "plain"
    },
    model: "gemini-3.5-flash-lite",
    usage: null
  };
}

function createStorageArea(store, controls = {}) {
  return {
    async setAccessLevel() {},
    get(keys, callback) {
      const complete = () => {
        const result = {};
        if (Array.isArray(keys)) {
          for (const key of keys) result[key] = store[key];
        } else if (typeof keys === "object" && keys) {
          Object.assign(result, keys, store);
        } else if (typeof keys === "string") {
          result[keys] = store[keys];
        } else {
          Object.assign(result, store);
        }
        callback(result);
      };
      if (controls.deferGet) {
        controls.pendingGets.push(complete);
      } else {
        complete();
      }
    },
    set(items, callback) {
      Object.assign(store, items);
      callback();
    },
    remove(keys, callback) {
      for (const key of Array.isArray(keys) ? keys : [keys]) delete store[key];
      callback();
    }
  };
}

const extensionSender = {
  id: "test-extension",
  url: "chrome-extension://test-extension/popup.html"
};

const panelSender = {
  id: "test-extension",
  url: "chrome-extension://test-extension/sidepanel.html"
};

const contentSender = {
  id: "test-extension",
  frameId: 0,
  documentId: "document-fixture",
  tab: { id: 7, windowId: 2, title: "Fixture page", url: "https://example.com/" }
};

test("routes trusted settings requests and rejects content-script management requests", async () => {
  const harness = await createHarness();
  const settings = await harness.send({ type: "GET_SETTINGS_STATUS" }, extensionSender);
  assert.equal(settings.ok, true);
  assert.equal(settings.hasApiKey, true);
  assert.equal(settings.model, "gemini-3.5-flash-lite");

  const rejected = await harness.send({ type: "GET_SETTINGS_STATUS" }, contentSender);
  assert.equal(rejected.ok, false);
  assert.equal(rejected.code, "invalid_sender");
});

test("keeps the legacy translation response shape and background word decision", async () => {
  const harness = await createHarness();
  const translated = await harness.send({
    type: "TRANSLATE_SELECTION",
    text: "hello",
    isSingleWord: false,
    shouldStoreWord: false
  }, contentSender);

  assert.equal(translated.ok, true);
  assert.equal(translated.translation, "你好");
  assert.equal(translated.partOfSpeech, "感嘆詞");
  assert.equal(translated.savedWord, true);
  assert.equal(harness.localStore.gstWordBank.length, 1);
  assert.equal(harness.localStore.gstWordBank[0].normalized, "hello");
});

test("preserves only allowlisted Gemini diagnostic fields in extension responses", async () => {
  const geminiError = new Error("安全的本機說明");
  geminiError.code = "model_not_available";
  geminiError.retryable = false;
  geminiError.httpStatus = 404;
  geminiError.upstreamStatus = "NOT_FOUND";
  geminiError.upstreamReason = "MODEL_NOT_AVAILABLE";
  geminiError.rawBody = "must not escape";
  const harness = await createHarness({ geminiError });

  const result = await harness.send({ type: "TEST_GEMINI_CONNECTION" }, extensionSender);
  assert.deepEqual({ ...result }, {
    ok: false,
    code: "model_not_available",
    message: "安全的本機說明",
    retryable: false,
    httpStatus: 404,
    upstreamStatus: "NOT_FOUND",
    upstreamReason: "MODEL_NOT_AVAILABLE"
  });
  assert.equal("rawBody" in result, false);
});

test("creates a session-backed capture job only for the current active tab", async () => {
  const harness = await createHarness();
  const created = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 7,
    windowId: 2
  }, extensionSender);
  assert.equal(created.ok, true);
  assert.equal(created.job.id, "job-fixture-1");
  assert.equal(created.job.state, "pending");
  assert.equal(harness.sessionStore.gstCaptureJob.tabId, 7);

  const panelState = await harness.send({ type: "GET_CAPTURE_JOB" }, panelSender);
  assert.equal(panelState.ok, true);
  assert.equal(panelState.job.windowId, 2);

  const stale = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 99,
    windowId: 2
  }, extensionSender);
  assert.equal(stale.ok, false);
  assert.equal(stale.code, "active_tab_changed");
});

test("a capture started in another window supersedes the old job", async () => {
  const harness = await createHarness();
  const first = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 7,
    windowId: 2
  }, extensionSender);
  assert.equal(first.ok, true);
  harness.sessionStore.gstCaptureJob.state = "running";

  harness.setActiveTab({
    id: 8,
    windowId: 3,
    title: "Second window",
    url: "https://example.org/"
  });
  const second = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 8,
    windowId: 3
  }, extensionSender);

  assert.equal(second.ok, true);
  assert.equal(second.job.id, "job-fixture-2");
  assert.equal(second.job.windowId, 3);
  assert.equal(harness.sessionStore.gstCaptureJob.id, "job-fixture-2");
});

test("simultaneous toolbar launches reject the stale invocation and keep only the latest", async () => {
  const harness = await createHarness();
  const firstRequest = harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 7,
    windowId: 2
  }, extensionSender);

  harness.setActiveTab({
    id: 8,
    windowId: 3,
    title: "Second window",
    url: "https://example.org/"
  });
  const secondRequest = harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 8,
    windowId: 3
  }, extensionSender);

  const [first, second] = await Promise.all([firstRequest, secondRequest]);
  assert.equal(first.ok, false);
  assert.equal(first.code, "stale_capture_job");
  assert.equal(second.ok, true);
  assert.equal(second.job.id, "job-fixture-1");
  assert.equal(harness.sessionStore.gstCaptureJob.id, second.job.id);
  assert.equal(harness.sessionStore.gstCaptureJob.windowId, 3);
});

test("stores region, viewport, and notice preferences independently", async () => {
  const harness = await createHarness();
  const initial = await harness.send({ type: "GET_CAPTURE_PREFERENCES" }, contentSender);
  assert.equal(initial.ok, true);
  assert.equal(initial.regionShortcut.enabled, true);
  assert.equal(initial.regionShortcut.code, "KeyX");
  assert.equal(initial.viewportShortcut.enabled, true);
  assert.equal(initial.viewportShortcut.code, "KeyV");
  assert.equal(initial.captureNoticeDismissed, false);

  const region = await harness.send({
    type: "SAVE_CAPTURE_SHORTCUT",
    shortcutKind: "region",
    captureShortcut: {
      enabled: false,
      ctrl: true,
      alt: false,
      shift: true,
      meta: false,
      code: "KeyK"
    }
  }, extensionSender);
  assert.equal(region.ok, true);
  assert.equal(harness.localStore.gstCaptureShortcut.code, "KeyK");
  assert.equal("gstCaptureViewportShortcut" in harness.localStore, false);
  assert.equal("gstCaptureNoticeDismissed" in harness.localStore, false);

  const viewport = await harness.send({
    type: "SAVE_CAPTURE_SHORTCUT",
    shortcutKind: "viewport",
    captureShortcut: {
      enabled: true,
      ctrl: false,
      alt: true,
      shift: true,
      meta: false,
      code: "KeyP"
    }
  }, extensionSender);
  assert.equal(viewport.ok, true);
  assert.equal(harness.localStore.gstCaptureShortcut.code, "KeyK");
  assert.equal(harness.localStore.gstCaptureViewportShortcut.code, "KeyP");

  const notice = await harness.send({
    type: "SAVE_CAPTURE_NOTICE_PREFERENCE",
    captureNoticeDismissed: true
  }, extensionSender);
  assert.equal(notice.ok, true);
  assert.equal(harness.localStore.gstCaptureShortcut.code, "KeyK");
  assert.equal(harness.localStore.gstCaptureViewportShortcut.code, "KeyP");
  assert.equal(harness.localStore.gstCaptureNoticeDismissed, true);
});

test("rejects invalid shortcut data instead of silently storing the default", async () => {
  const harness = await createHarness();
  const result = await harness.send({
    type: "SAVE_CAPTURE_SHORTCUT",
    shortcutKind: "region",
    captureShortcut: { enabled: true, shift: true, code: "KeyQ" }
  }, extensionSender);
  assert.equal(result.ok, false);
  assert.equal(result.code, "invalid_shortcut");
  assert.equal("gstCaptureShortcut" in harness.localStore, false);
});

test("rejects two enabled capture shortcuts with the same key combination", async () => {
  const harness = await createHarness();
  const result = await harness.send({
    type: "SAVE_CAPTURE_SHORTCUT",
    shortcutKind: "viewport",
    captureShortcut: {
      enabled: true,
      ctrl: false,
      alt: true,
      shift: true,
      meta: false,
      code: "KeyX"
    }
  }, extensionSender);
  assert.equal(result.ok, false);
  assert.equal(result.code, "shortcut_conflict");
  assert.equal("gstCaptureViewportShortcut" in harness.localStore, false);
});

test("an upgraded region shortcut on V keeps priority over the new viewport default", async () => {
  const harness = await createHarness({
    localStore: {
      gstCaptureShortcut: {
        enabled: true,
        ctrl: false,
        alt: true,
        shift: true,
        meta: false,
        code: "KeyV"
      }
    }
  });
  const preferences = await harness.send({ type: "GET_CAPTURE_PREFERENCES" }, contentSender);
  assert.equal(preferences.regionShortcut.code, "KeyV");
  assert.equal(preferences.regionShortcut.enabled, true);
  assert.equal(preferences.viewportShortcut.code, "KeyV");
  assert.equal(preferences.viewportShortcut.enabled, false);
});

test("a first cold region shortcut waits for the panel and directly starts selection", async () => {
  const harness = await createHarness({ regionCapture: true });
  const resultPromise = harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "region" }, contentSender);
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(harness.tabMessages.some(({ message }) => message.type === "START_CAPTURE_SELECTION"), false);
  await harness.connectPanel(2);
  const result = await resultPromise;
  assert.equal(result.ok, true);
  assert.equal(result.job.state, "selecting");
  assert.equal(result.job.source, "shortcut_region");
  assert.equal(harness.sidePanelOpenCount, 1);
  assert.equal(harness.sessionStore.gstCaptureJob.state, "selecting");
  assert.equal(harness.tabMessages.some(({ message }) => message.type === "START_CAPTURE_SELECTION"), true);

  const completed = await harness.send({
    type: "CAPTURE_SELECTION_READY",
    jobId: result.job.id,
    generation: result.job.generation,
    rect: { left: 10, top: 20, right: 210, bottom: 120, width: 200, height: 100 },
    viewport: { width: 800, height: 600, scrollX: 0, scrollY: 0 }
  }, contentSender);
  assert.equal(completed.ok, true);
  assert.equal(harness.sessionStore.gstCaptureJob.state, "preview");
});

test("a newer region shortcut replaces an active selection with a fresh job", async () => {
  const harness = await createHarness();
  await harness.connectPanel(2);
  const first = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "region" }, contentSender);
  const second = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "region" }, contentSender);

  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.notEqual(second.job.id, first.job.id);
  assert.equal(second.job.generation > first.job.generation, true);
  assert.equal(second.job.state, "selecting");
  assert.equal(harness.sessionStore.gstCaptureJob.id, second.job.id);
  assert.equal(harness.tabMessages.some(({ message }) => (
    message.type === "CANCEL_CAPTURE_SELECTION" && message.jobId === first.job.id
  )), true);
});

for (const priorState of ["pending", "selecting", "capturing", "preview", "running", "result", "error"]) {
  test(`a new viewport intent supersedes an existing ${priorState} job`, async () => {
    const harness = await createHarness({ fullCapture: true });
    await harness.connectPanel(2);
    const existing = await harness.send({
      type: "OPEN_CAPTURE_PANEL",
      tabId: 7,
      windowId: 2
    }, extensionSender);
    const oldJobId = existing.job.id;
    harness.sessionStore.gstCaptureJob.state = priorState;

    const next = await harness.send({
      type: "TRIGGER_CAPTURE_SHORTCUT",
      captureMode: "viewport"
    }, contentSender);

    assert.equal(next.ok, true);
    assert.equal(next.job.state, "preview");
    assert.notEqual(next.job.id, oldJobId);
    assert.equal(harness.sessionStore.gstCaptureJob.id, next.job.id);
  });
}

test("a trusted viewport shortcut waits for the panel and delivers a preview", async () => {
  const harness = await createHarness({ fullCapture: true });
  const resultPromise = harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "viewport" }, contentSender);
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(harness.tabMessages.some(({ message }) => message.type === "PREPARE_FULL_VIEWPORT_CAPTURE"), false);
  await harness.connectPanel(2);
  const result = await resultPromise;
  assert.equal(result.ok, true);
  assert.equal(result.job.state, "preview");
  assert.equal(result.job.source, "shortcut_viewport");
  assert.equal(harness.sessionStore.gstCaptureJob.state, "preview");
  assert.equal(harness.panelMessages.some((message) => message.type === "CAPTURE_PREVIEW_READY"), true);
});

test("a cold capture permission failure returns a specific reload instruction", async () => {
  const harness = await createHarness({
    fullCapture: true,
    hasAllUrls: false
  });
  const resultPromise = harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "viewport" }, contentSender);
  await harness.connectPanel(2);
  const result = await resultPromise;

  assert.equal(result.ok, false);
  assert.equal(result.code, "capture_permission_missing");
  assert.match(result.message, /chrome:\/\/extensions/);
  assert.equal(harness.sessionStore.gstCaptureJob.state, "error");
  assert.equal(harness.sessionStore.gstCaptureJob.error.code, "capture_permission_missing");

  harness.grantActiveTab();
  const recovered = await harness.send({
    type: "TRIGGER_CAPTURE_SHORTCUT",
    captureMode: "viewport"
  }, contentSender);
  assert.equal(recovered.ok, true);
  assert.equal(recovered.job.state, "preview");
});

test("a region shortcut supersedes an in-flight viewport capture without waiting", async () => {
  const harness = await createHarness({ fullCapture: true, deferCaptureVisibleTab: true });
  await harness.connectPanel(2);
  const viewportPromise = harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "viewport" }, contentSender);
  await waitFor(() => harness.captureVisibleCalls.length === 1);

  const region = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "region" }, contentSender);
  assert.equal(region.ok, true);
  assert.equal(region.job.state, "selecting");
  assert.equal(harness.sessionStore.gstCaptureJob.id, region.job.id);

  harness.resolveNextCapture();
  const staleViewport = await viewportPromise;
  assert.equal(staleViewport.ok, false);
  assert.equal(staleViewport.code, "stale_capture_job");
  assert.equal(harness.sessionStore.gstCaptureJob.id, region.job.id);
  assert.equal(harness.panelMessages.some((message) => (
    message.type === "CAPTURE_PREVIEW_READY" && message.job?.id !== region.job.id
  )), false);
});

test("panel capture intent always binds to the currently active tab", async () => {
  const harness = await createHarness();
  await harness.connectPanel(2);
  harness.setActiveTab({
    id: 8,
    windowId: 2,
    title: "New active page",
    url: "https://example.org/"
  });

  const result = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "region",
    windowId: 2,
    source: "panel_button"
  }, panelSender);

  assert.equal(result.ok, true);
  assert.equal(result.job.tabId, 8);
  assert.equal(result.job.state, "selecting");
  assert.equal(harness.sessionStore.gstCaptureJob.tabId, 8);
});

test("a manual region selection completes cropping for its fresh job", async () => {
  const harness = await createHarness({ regionCapture: true });
  await harness.connectPanel(2);
  const started = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "region",
    windowId: 2,
    source: "panel_button"
  }, panelSender);

  const completed = await harness.send({
    type: "CAPTURE_SELECTION_READY",
    jobId: started.job.id,
    generation: started.job.generation,
    rect: { left: 10, top: 20, right: 210, bottom: 120, width: 200, height: 100 },
    viewport: { width: 800, height: 600, scrollX: 0, scrollY: 0 }
  }, contentSender);

  assert.equal(completed.ok, true);
  assert.equal(harness.sessionStore.gstCaptureJob.state, "preview");
  const preview = harness.panelMessages.find((message) => (
    message.type === "CAPTURE_PREVIEW_READY" && message.job?.id === started.job.id
  ));
  assert.equal(preview.crop.width, 200);
  assert.equal(preview.crop.height, 100);
});

test("visible-tab captures are spaced below Chrome's two-per-second limit", async () => {
  const harness = await createHarness({ fullCapture: true });
  await harness.connectPanel(2);
  const first = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "viewport" }, contentSender);
  const second = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "viewport" }, contentSender);

  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.equal(harness.captureVisibleCalls.length, 2);
  assert.equal(harness.captureVisibleCalls[1].startedAt - harness.captureVisibleCalls[0].startedAt >= 500, true);
  assert.equal(harness.sessionStore.gstCaptureJob.id, second.job.id);
});

test("a latest toolbar intent that loses its active tab abandons the older job cleanly", async () => {
  const harness = await createHarness();
  await harness.connectPanel(2);
  const existing = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 7,
    windowId: 2
  }, extensionSender);
  assert.equal(existing.ok, true);

  const failed = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 99,
    windowId: 2
  }, extensionSender);

  assert.equal(failed.ok, false);
  assert.equal(failed.code, "active_tab_changed");
  assert.equal("gstCaptureJob" in harness.sessionStore, false);
  assert.equal(harness.panelMessages.some((message) => (
    message.type === "CAPTURE_JOB_STATE" && message.job === null && message.generation === existing.job.generation
  )), true);

  const recovered = await harness.send({
    type: "OPEN_CAPTURE_PANEL",
    tabId: 7,
    windowId: 2
  }, extensionSender);
  assert.equal(recovered.ok, true);
  assert.notEqual(recovered.job.id, existing.job.id);
});

test("panel readiness is read-only and reset returns to a new pending job", async () => {
  const harness = await createHarness();
  await harness.connectPanel(2);
  const first = await harness.send({ type: "GET_CAPTURE_JOB" }, panelSender);
  assert.equal(first.ok, true);
  assert.equal(first.job, null);

  const selection = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "region",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  assert.equal(selection.ok, true);
  assert.equal(selection.job.state, "selecting");

  const reset = await harness.send({
    type: "RESET_CAPTURE_JOB",
    jobId: selection.job.id,
    windowId: 2
  }, panelSender);
  assert.equal(reset.ok, true);
  assert.equal(reset.job.state, "pending");
  assert.notEqual(reset.job.id, selection.job.id);
  assert.equal(harness.sessionStore.gstCaptureJob.id, reset.job.id);
});

test("cold panel readiness and a shortcut share one session restore without reviving stale state", async () => {
  const oldJob = {
    id: "stored-old-job",
    generation: 4,
    intentId: 0,
    tabId: 7,
    windowId: 2,
    pageTitle: "Stored page",
    source: "toolbar",
    captureMode: null,
    state: "result",
    createdAt: "2026-07-22T00:00:00.000Z",
    error: null
  };
  const harness = await createHarness({
    deferSessionGet: true,
    sessionStore: { gstCaptureJob: oldJob }
  });
  await harness.connectPanel(2);
  const shortcutPromise = harness.send({
    type: "TRIGGER_CAPTURE_SHORTCUT",
    captureMode: "region"
  }, contentSender);

  await waitFor(() => harness.pendingSessionGets === 1);
  assert.equal(harness.pendingSessionGets, 1);
  harness.resolveNextSessionGet();
  const shortcut = await shortcutPromise;

  assert.equal(shortcut.ok, true);
  assert.equal(shortcut.job.state, "selecting");
  assert.equal(shortcut.job.generation, 5);
  assert.notEqual(shortcut.job.id, oldJob.id);
  assert.equal(harness.sessionStore.gstCaptureJob.id, shortcut.job.id);
});

test("late panel readiness cannot replace a newer preview in another window", async () => {
  const harness = await createHarness({ fullCapture: true });
  await harness.connectPanel(2);
  const preview = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "viewport",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  assert.equal(preview.ok, true, JSON.stringify(preview));
  assert.equal(preview.job.state, "preview");

  await harness.connectPanel(3);

  assert.equal(harness.sessionStore.gstCaptureJob.id, preview.job.id);
  assert.equal(harness.sessionStore.gstCaptureJob.state, "preview");
  const lastPanelState = harness.panelMessages.filter((message) => message.type === "CAPTURE_JOB_STATE").at(-1);
  assert.equal(lastPanelState.job, null);
  assert.equal(lastPanelState.generation, preview.job.generation);
});

test("the same preview cannot launch two concurrent Gemini OCR requests", async () => {
  const harness = await createHarness({ fullCapture: true, deferGemini: true });
  await harness.connectPanel(2);
  const preview = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "viewport",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  assert.equal(preview.ok, true);

  const request = {
    type: "RUN_CAPTURE_OCR",
    jobId: preview.job.id,
    imageDataUrl: "data:image/png;base64,AQID",
    translate: true
  };
  const firstPromise = harness.send(request, panelSender);
  const secondPromise = harness.send(request, panelSender);
  const second = await secondPromise;

  assert.equal(second.ok, false);
  assert.equal(second.code, "ocr_in_progress");
  await waitFor(() => harness.pendingGeminiRequests === 1);
  harness.resolveNextGemini();
  const first = await firstPromise;
  assert.equal(first.ok, true, JSON.stringify(first));
  assert.equal(first.result.transcript, "hello");
});

test("a failed latest panel intent aborts the old OCR and permits a later recovery", async () => {
  const harness = await createHarness({ fullCapture: true, deferGemini: true });
  await harness.connectPanel(2);
  const preview = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "viewport",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  const ocrPromise = harness.send({
    type: "RUN_CAPTURE_OCR",
    jobId: preview.job.id,
    imageDataUrl: "data:image/png;base64,AQID",
    translate: true
  }, panelSender);
  await waitFor(() => harness.pendingGeminiRequests === 1);

  harness.setActiveTab({
    id: 8,
    windowId: 3,
    title: "Other window",
    url: "https://example.org/"
  });
  const failed = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "region",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  const oldOcr = await ocrPromise;

  assert.equal(failed.ok, false);
  assert.equal(failed.code, "active_tab_missing");
  assert.equal(oldOcr.ok, false);
  assert.equal(oldOcr.code, "request_aborted");
  assert.equal("gstCaptureJob" in harness.sessionStore, false);

  harness.setActiveTab({
    id: 9,
    windowId: 2,
    title: "Recovered page",
    url: "https://example.net/"
  });
  const recovered = await harness.send({
    type: "BEGIN_CAPTURE_INTENT",
    captureMode: "region",
    windowId: 2,
    source: "panel_button"
  }, panelSender);
  assert.equal(recovered.ok, true);
  assert.equal(recovered.job.state, "selecting");
  assert.equal(recovered.job.tabId, 9);
});

test("shortcut capture mode is allowlisted", async () => {
  const harness = await createHarness();
  const result = await harness.send({ type: "TRIGGER_CAPTURE_SHORTCUT", captureMode: "document" }, contentSender);
  assert.equal(result.ok, false);
  assert.equal(result.code, "invalid_capture_mode");
  assert.equal(harness.sidePanelOpenCount, 0);
});

async function waitFor(predicate, timeoutMs = 1000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("Timed out waiting for test condition");
}
