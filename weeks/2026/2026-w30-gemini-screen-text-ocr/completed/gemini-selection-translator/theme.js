"use strict";

(() => {
  const STORAGE_KEY = "gstThemeMode";
  const VALID_MODES = new Set(["system", "light", "dark"]);
  const registeredRoots = new Set();
  let currentMode = "system";

  function normalize(mode) {
    return VALID_MODES.has(mode) ? mode : "system";
  }

  function applyToRoot(root, mode = currentMode) {
    if (!root) {
      return;
    }

    const nextMode = normalize(mode);
    root.dataset.nwTheme = nextMode;
    root.style.colorScheme = nextMode === "system" ? "light dark" : nextMode;
  }

  function applyToAll(mode) {
    currentMode = normalize(mode);
    registeredRoots.forEach((root) => applyToRoot(root, currentMode));
  }

  function register(root) {
    if (!root) {
      return;
    }

    registeredRoots.add(root);
    applyToRoot(root);
  }

  const isExtensionPage = location.protocol === "chrome-extension:";

  if (isExtensionPage) {
    chrome.storage.local.get({ [STORAGE_KEY]: "system" }, (result) => {
      applyToAll(result[STORAGE_KEY]);
    });

    chrome.storage.onChanged.addListener((changes, areaName) => {
      if (areaName === "local" && changes[STORAGE_KEY]) {
        applyToAll(changes[STORAGE_KEY].newValue);
      }
    });

    register(document.documentElement);
  } else {
    chrome.runtime.sendMessage({ type: "GET_THEME_MODE" }, (response) => {
      if (!chrome.runtime.lastError && response?.ok) {
        applyToAll(response.themeMode);
      }
    });

    chrome.runtime.onMessage.addListener((message) => {
      if (message?.type === "THEME_MODE_CHANGED") {
        applyToAll(message.themeMode);
      }
    });
  }

  globalThis.NoiseWinstonTheme = Object.freeze({
    key: STORAGE_KEY,
    normalize,
    register,
    getMode: () => currentMode
  });
})();
