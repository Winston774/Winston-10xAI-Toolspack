"use strict";

// Noise Winston Extension Kit theme runtime. Writes data-nw-theme on the popup root and on the
// page UI hosts the content scripts register; the mode lives in chrome.storage.local.
(() => {
  // Both content-script entries match Threads, so this file can be injected twice into one world.
  if (globalThis.NoiseWinstonTheme) return;

  const STORAGE_KEY = "themeMode";
  const VALID_MODES = new Set(["system", "light", "dark"]);
  const registeredRoots = new Set();
  let currentMode = "system";

  function normalize(mode) {
    return VALID_MODES.has(mode) ? mode : "system";
  }

  function applyToRoot(root, mode = currentMode) {
    if (!root) return;
    const nextMode = normalize(mode);
    root.dataset.nwTheme = nextMode;
    root.style.colorScheme = nextMode === "system" ? "light dark" : nextMode;
  }

  function applyToAll(mode) {
    currentMode = normalize(mode);
    registeredRoots.forEach((root) => {
      if (root.isConnected === false) {
        registeredRoots.delete(root);
        return;
      }
      applyToRoot(root, currentMode);
    });
  }

  function register(root) {
    if (!root) return;
    registeredRoots.add(root);
    applyToRoot(root);
  }

  chrome.storage.local.get({ [STORAGE_KEY]: "system" }, (result) => {
    applyToAll(result[STORAGE_KEY]);
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes[STORAGE_KEY]) {
      applyToAll(changes[STORAGE_KEY].newValue);
    }
  });

  if (location.protocol === "chrome-extension:") {
    register(document.documentElement);
  }

  globalThis.NoiseWinstonTheme = Object.freeze({
    key: STORAGE_KEY,
    normalize,
    register,
    getMode: () => currentMode
  });
})();
