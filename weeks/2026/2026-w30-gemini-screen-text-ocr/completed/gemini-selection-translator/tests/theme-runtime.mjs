import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

test("defaults to system and applies storage changes to registered roots", async () => {
  const source = await readFile(new URL("../theme.js", import.meta.url), "utf8");
  const documentRoot = { dataset: {}, style: {} };
  let storageListener;

  const context = {
    chrome: {
      storage: {
        local: {
          get(defaults, callback) {
            callback(defaults);
          }
        },
        onChanged: {
          addListener(listener) {
            storageListener = listener;
          }
        }
      }
    },
    document: { documentElement: documentRoot },
    location: { protocol: "chrome-extension:" }
  };
  context.globalThis = context;

  vm.runInNewContext(source, context);

  assert.equal(documentRoot.dataset.nwTheme, "system");
  assert.equal(documentRoot.style.colorScheme, "light dark");

  const contentRoot = { dataset: {}, style: {} };
  context.NoiseWinstonTheme.register(contentRoot);
  storageListener({ gstThemeMode: { newValue: "dark" } }, "local");

  assert.equal(documentRoot.dataset.nwTheme, "dark");
  assert.equal(contentRoot.dataset.nwTheme, "dark");
  assert.equal(contentRoot.style.colorScheme, "dark");
});

test("content roots receive only theme mode through background messaging", async () => {
  const source = await readFile(new URL("../theme.js", import.meta.url), "utf8");
  let runtimeListener;
  const context = {
    chrome: {
      runtime: {
        lastError: null,
        sendMessage(message, callback) {
          assert.equal(message.type, "GET_THEME_MODE");
          callback({ ok: true, themeMode: "dark" });
        },
        onMessage: {
          addListener(listener) {
            runtimeListener = listener;
          }
        }
      }
    },
    document: { documentElement: { dataset: {}, style: {} } },
    location: { protocol: "https:" }
  };
  context.globalThis = context;

  vm.runInNewContext(source, context);
  const contentRoot = { dataset: {}, style: {} };
  context.NoiseWinstonTheme.register(contentRoot);
  assert.equal(contentRoot.dataset.nwTheme, "dark");

  runtimeListener({ type: "THEME_MODE_CHANGED", themeMode: "light" });
  assert.equal(contentRoot.dataset.nwTheme, "light");
  assert.equal(contentRoot.style.colorScheme, "light");
});
