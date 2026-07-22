import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

async function loadShortcutUtils() {
  const source = await readFile(new URL("../lib/shortcut-utils.js", import.meta.url), "utf8");
  const context = {};
  context.globalThis = context;
  vm.runInNewContext(source, context);
  return context.ShortcutUtils;
}

function keyboardEvent(overrides = {}) {
  return {
    code: "KeyX",
    key: "x",
    ctrlKey: false,
    altKey: true,
    shiftKey: true,
    metaKey: false,
    repeat: false,
    isComposing: false,
    keyCode: 88,
    getModifierState: () => false,
    ...overrides
  };
}

test("defaults to distinct enabled region and viewport shortcuts", async () => {
  const utils = await loadShortcutUtils();
  const region = utils.normalizeShortcut(null, utils.DEFAULT_REGION_SHORTCUT);
  const viewport = utils.normalizeShortcut(null, utils.DEFAULT_VIEWPORT_SHORTCUT);
  assert.deepEqual({ ...region }, {
    enabled: true,
    ctrl: false,
    alt: true,
    shift: true,
    meta: false,
    code: "KeyX"
  });
  assert.equal(utils.formatShortcut(region), "Alt + Shift + X");
  assert.equal(utils.formatShortcut(viewport), "Alt + Shift + V");
  assert.equal(utils.sameShortcut(region, viewport), false);
});

test("records valid combinations and rejects unsafe or incomplete combinations", async () => {
  const utils = await loadShortcutUtils();
  const recorded = utils.shortcutFromKeyboardEvent(keyboardEvent({ code: "KeyK", key: "k" }));
  assert.equal(utils.formatShortcut(recorded), "Alt + Shift + K");
  assert.equal(utils.shortcutFromKeyboardEvent(keyboardEvent({ altKey: false, shiftKey: true })), null);
  assert.equal(utils.shortcutFromKeyboardEvent(keyboardEvent({ ctrlKey: true, altKey: true })), null);
  assert.equal(utils.shortcutFromKeyboardEvent(keyboardEvent({ getModifierState: (name) => name === "AltGraph" })), null);
  assert.equal(utils.shortcutFromKeyboardEvent(keyboardEvent({ code: "Escape", key: "Escape" })), null);
});

test("matches the physical key and every modifier exactly", async () => {
  const utils = await loadShortcutUtils();
  const shortcut = utils.normalizeShortcut(utils.DEFAULT_SHORTCUT);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent(), shortcut), true);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent({ ctrlKey: true }), shortcut), false);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent({ shiftKey: false }), shortcut), false);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent({ code: "KeyY" }), shortcut), false);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent({ repeat: true }), shortcut), false);
  assert.equal(utils.matchesKeyboardEvent(keyboardEvent(), { ...shortcut, enabled: false }), false);
});

test("normalizes corrupt storage while explicitly validating new settings", async () => {
  const utils = await loadShortcutUtils();
  assert.equal(utils.isValidShortcut({ enabled: true, code: "KeyQ", alt: true }), true);
  assert.equal(utils.isValidShortcut({ enabled: true, code: "KeyQ", shift: true }), false);
  assert.equal(utils.isValidShortcut({ enabled: true, code: "Unknown", alt: true }), false);
  const normalized = utils.normalizeShortcut({ enabled: false, code: "Unknown", alt: true });
  assert.equal(normalized.enabled, false);
  assert.equal(utils.formatShortcut(normalized), "Alt + Shift + X");
  const viewport = utils.normalizeShortcut(null, utils.DEFAULT_VIEWPORT_SHORTCUT);
  assert.equal(utils.formatShortcut(viewport), "Alt + Shift + V");
  assert.equal(utils.sameShortcut(viewport, { ...viewport, enabled: false }), true);
});
