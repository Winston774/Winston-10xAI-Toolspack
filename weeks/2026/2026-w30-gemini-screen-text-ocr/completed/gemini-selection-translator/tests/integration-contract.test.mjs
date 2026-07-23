import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("manifest exposes only the capture permissions and surfaces the integration needs", async () => {
  const manifest = JSON.parse(await readFile(new URL("../manifest.json", import.meta.url), "utf8"));
  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.minimum_chrome_version, "116");
  assert.deepEqual(manifest.permissions, ["activeTab", "sidePanel", "storage"]);
  assert.equal("commands" in manifest, false);
  assert.equal(manifest.side_panel.default_path, "sidepanel.html");
  assert.deepEqual(manifest.content_scripts[0].js, ["theme.js", "lib/shortcut-utils.js", "content.js"]);
  for (const forbidden of ["tabs", "scripting", "tabCapture", "desktopCapture", "clipboardWrite", "offscreen"]) {
    assert.equal(manifest.permissions.includes(forbidden), false);
  }
});

test("custom page shortcuts have persistent capture permission before any action click", async () => {
  const manifest = JSON.parse(await readFile(new URL("../manifest.json", import.meta.url), "utf8"));
  assert.deepEqual(manifest.host_permissions, ["<all_urls>"]);
  assert.equal("commands" in manifest, false);
  assert.deepEqual(manifest.content_scripts[0].matches, ["http://*/*", "https://*/*", "file:///*"]);
});

test("capture boundary keeps full screenshots and model output out of the content script", async () => {
  const [background, content, panel] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../content.js", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.js", import.meta.url), "utf8")
  ]);
  assert.match(background, /captureVisibleTab\(job\.windowId\)/);
  assert.match(background, /cropScreenshot\(screenshotDataUrl/);
  assert.match(background, /type: "CAPTURE_PREVIEW_READY"/);
  assert.match(content, /type: "CAPTURE_SELECTION_READY"/);
  assert.doesNotMatch(content, /captureVisibleTab|imageDataUrl|RUN_CAPTURE_OCR|x-goog-api-key/);
  assert.doesNotMatch(panel, /innerHTML\s*=/);
  assert.match(panel, /\.textContent\s*=/);
  assert.match(panel, /imageDataUrl: state\.crop\.dataUrl/);
});

test("capture preview ports accept only the trusted side panel document", async () => {
  const background = await readFile(new URL("../background.js", import.meta.url), "utf8");
  assert.match(background, /port\.sender\?\.id\s*!==\s*chrome\.runtime\.id/);
  assert.match(background, /senderUrl\s*!==\s*chrome\.runtime\.getURL\("sidepanel\.html"\)/);
  assert.match(background, /port\.disconnect\(\)/);
});

test("offers a keyboard-operable full viewport capture path", async () => {
  const [background, content, panelHtml, panelScript] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../content.js", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.html", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.js", import.meta.url), "utf8")
  ]);
  assert.match(panelHtml, /id="captureViewportButton"/);
  assert.match(panelScript, /type: "BEGIN_CAPTURE_INTENT"/);
  assert.match(panelScript, /captureMode/);
  assert.match(background, /async function beginFullViewportCapture/);
  assert.match(content, /PREPARE_FULL_VIEWPORT_CAPTURE/);
});

test("uses two configurable direct-capture shortcuts without Chrome shortcut settings", async () => {
  const [background, content, optionsHtml, optionsScript, panelHtml, panelScript] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../content.js", import.meta.url), "utf8"),
    readFile(new URL("../options.html", import.meta.url), "utf8"),
    readFile(new URL("../options.js", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.html", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.js", import.meta.url), "utf8")
  ]);
  assert.match(content, /ShortcutUtils\.matchesKeyboardEvent/);
  assert.match(content, /event\.isTrusted !== true/);
  assert.match(content, /isEditableTarget\(event\)/);
  assert.match(content, /stopImmediatePropagation\(\)/);
  assert.match(content, /type: "TRIGGER_CAPTURE_SHORTCUT"/);
  assert.match(content, /captureMode/);
  assert.match(content, /regionMatch/);
  assert.match(content, /viewportMatch/);
  assert.match(background, /chrome\.sidePanel\.open\(\{ windowId: tab\.windowId \}\)/);
  assert.match(background, /waitForPanelReady\(tab\.windowId\)/);
  assert.match(background, /beginRegionCapture\(job\)/);
  assert.match(background, /beginFullViewportCapture\(job\)/);
  assert.match(background, /replaceCaptureJob\(tab/);
  assert.match(optionsHtml, /id="regionShortcutEnabled"/);
  assert.match(optionsHtml, /id="regionShortcutRecorder"/);
  assert.match(optionsHtml, /id="resetRegionShortcutButton"/);
  assert.match(optionsHtml, /id="viewportShortcutEnabled"/);
  assert.match(optionsHtml, /id="viewportShortcutRecorder"/);
  assert.match(optionsHtml, /id="resetViewportShortcutButton"/);
  assert.match(optionsHtml, /Alt \+ Shift \+ X/);
  assert.match(optionsHtml, /Alt \+ Shift \+ V/);
  assert.match(optionsScript, /type: "SAVE_CAPTURE_SHORTCUT"/);
  assert.match(optionsScript, /shortcutKind: kind/);
  assert.doesNotMatch(panelHtml, /id="idleView"|READY|id="shortcutLabel"/);
  assert.match(panelHtml, /清除並重新開始/);
  assert.match(panelScript, /type: "RESET_CAPTURE_JOB"/);
  assert.doesNotMatch(panelScript, /type: "CANCEL_CAPTURE_JOB"/);
  assert.match(panelHtml, /lib\/shortcut-utils\.js/);
  assert.match(panelScript, /handlePanelShortcutKeydown/);
  assert.equal(panelScript.indexOf("connectPanel();") < panelScript.indexOf("await loadCapturePreferences();"), true);
  assert.doesNotMatch(`${background}\n${panelScript}`, /chrome\.commands|extensions\/shortcuts/);
});

test("new capture intents supersede stale work across every extension surface", async () => {
  const [background, content, panel] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../content.js", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.js", import.meta.url), "utf8")
  ]);
  assert.match(background, /replaceExisting: true/);
  assert.match(background, /assertCaptureJobCurrent/);
  assert.match(background, /captureGeneration/);
  assert.match(background, /captureVisibleQueue/);
  assert.match(background, /captureAbortControllers/);
  assert.match(background, /activeOcrJobIds/);
  assert.match(background, /captureJobRestorePromise/);
  assert.match(background, /abandonCaptureIntent/);
  assert.match(background, /signal: abortController\.signal/);
  assert.match(background, /captureAbortControllers\.get\(job\.id\)\?\.abort\(\)/);
  const panelReadySnapshot = background.match(/async function getCaptureJobForPanelWindow[\s\S]*?\n}/)?.[0] || "";
  assert.doesNotMatch(panelReadySnapshot, /getActiveTab|replaceCaptureJob|createCaptureJob/);
  assert.match(background, /CAPTURE_VISIBLE_MIN_INTERVAL_MS = 550/);
  assert.match(background, /CONTENT_MESSAGE_TIMEOUT_MS/);
  assert.doesNotMatch(background, /shortcutLaunchQueue|capture_busy", "目前的畫面擷取/);
  assert.doesNotMatch(content, /addEventListener\("blur"/);
  assert.doesNotMatch(content, /shortcutState\.pending/);
  assert.match(content, /waitForStableCaptureViewport/);
  assert.match(content, /captureState\.dragging/);
  assert.match(content, /cancelCapture\("shortcut_restarted", false\)/);
  assert.match(panel, /actionSequence/);
  assert.match(panel, /adoptPanelJob/);
  assert.match(panel, /const actionSequence = \+\+state\.actionSequence;[\s\S]*state\.actionSequence !== actionSequence/);
  assert.match(panel, /\["request_aborted", "stale_capture_job"\]/);
  assert.match(panel, /source: "panel_shortcut"|"panel_shortcut"/);
});

test("persists the combined acknowledgement and can restore the capture notice", async () => {
  const [background, optionsHtml, optionsScript, panelHtml, panelScript] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../options.html", import.meta.url), "utf8"),
    readFile(new URL("../options.js", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.html", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.js", import.meta.url), "utf8")
  ]);
  assert.match(panelHtml, /我已瞭解，下次不需要再顯示/);
  assert.match(panelHtml, /id="captureDisclosure"/);
  assert.match(panelHtml, /id="previewDisclosureSlot"/);
  assert.match(panelScript, /type: "DISMISS_CAPTURE_NOTICE"/);
  assert.match(panelScript, /elements\.captureDisclosure\.hidden = state\.noticeDismissed/);
  assert.match(panelScript, /elements\.runOcrButton\.disabled/);
  assert.match(panelScript, /renderDisclosure\(elements\.previewDisclosureSlot/);
  assert.match(optionsHtml, /id="showCaptureNotice"/);
  assert.match(optionsScript, /type: "SAVE_CAPTURE_NOTICE_PREFERENCE"/);
  assert.match(background, /gstCaptureNoticeDismissed/);
});

test("no runtime surface uses a colored left-side accent rule", async () => {
  const cssFiles = ["design-system.css", "content.css", "popup.css", "options.css", "sidepanel.css"];
  const sources = await Promise.all(cssFiles.map((file) => readFile(new URL(`../${file}`, import.meta.url), "utf8")));
  for (let index = 0; index < sources.length; index += 1) {
    assert.doesNotMatch(sources[index], /\bborder-(?:left|inline-start)\s*:/i, cssFiles[index]);
  }
});

test("translation and OCR share the generateContent adapter and safe compatibility path", async () => {
  const [background, client] = await Promise.all([
    readFile(new URL("../background.js", import.meta.url), "utf8"),
    readFile(new URL("../lib/gemini-client.js", import.meta.url), "utf8")
  ]);
  assert.match(background, /importScripts\("lib\/gemini-client\.js", "lib\/capture-utils\.js", "lib\/shortcut-utils\.js"\)/);
  assert.equal((background.match(/GeminiClient\.requestStructured/g) || []).length >= 3, true);
  assert.match(client, /\/v1beta\/models/);
  assert.match(client, /:generateContent/);
  assert.doesNotMatch(client, /\/v1\/interactions/);
  assert.match(client, /"x-goog-api-key": apiKey/);
  assert.doesNotMatch(client, /\?key=/);
  assert.match(client, /body\.store = false/);
  assert.match(client, /responseMimeType: "application\/json"/);
  assert.match(client, /responseJsonSchema/);
  assert.match(client, /shouldUseCompatibilityBody/);
  assert.doesNotMatch(client, /responseFormat|thinkingConfig|thinking_level/);
  assert.match(background, /setAccessLevel\(\{ accessLevel: "TRUSTED_CONTEXTS" \}\)/);
});
