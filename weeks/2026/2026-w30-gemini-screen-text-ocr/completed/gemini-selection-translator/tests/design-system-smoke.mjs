import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("uses the Noise Winston token layer and shared theme runtime on every extension surface", async () => {
  const [manifestSource, tokens, theme, popup, options, sidepanel, popupCss, sidepanelCss, optionsJs, content, background] = await Promise.all([
    readFile(new URL("../manifest.json", import.meta.url), "utf8"),
    readFile(new URL("../design-system.css", import.meta.url), "utf8"),
    readFile(new URL("../theme.js", import.meta.url), "utf8"),
    readFile(new URL("../popup.html", import.meta.url), "utf8"),
    readFile(new URL("../options.html", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.html", import.meta.url), "utf8"),
    readFile(new URL("../popup.css", import.meta.url), "utf8"),
    readFile(new URL("../sidepanel.css", import.meta.url), "utf8"),
    readFile(new URL("../options.js", import.meta.url), "utf8"),
    readFile(new URL("../content.js", import.meta.url), "utf8"),
    readFile(new URL("../background.js", import.meta.url), "utf8"),
  ]);
  const manifest = JSON.parse(manifestSource);

  assert.deepEqual(manifest.content_scripts[0].css, ["design-system.css", "content.css"]);
  assert.deepEqual(manifest.content_scripts[0].js, ["theme.js", "lib/shortcut-utils.js", "content.js"]);
  assert.equal(manifest.version, "0.6.2");
  assert.deepEqual(manifest.web_accessible_resources, [
    {
      resources: ["icons/icon-32.png"],
      matches: ["http://*/*", "https://*/*", "file:///*"]
    }
  ]);
  assert.match(tokens, /--nw-canvas:\s*#F1EFE7/);
  assert.match(tokens, /--nw-canvas:\s*#0D0F12/);
  assert.match(tokens, /--nw-purple:\s*#8550FF/);
  assert.match(tokens, /\[data-nw-theme="light"\]/);
  assert.match(tokens, /\[data-nw-theme="dark"\]/);
  assert.match(theme, /gstThemeMode/);
  assert.match(theme, /let currentMode = "system"/);
  assert.match(popup, /NOISE WINSTON \/ LAB 002/);
  assert.match(options, /SETTINGS \/ TRANSLATION/);
  assert.match(options, /value="system" checked/);
  assert.match(options, /value="light"/);
  assert.match(options, /value="dark"/);
  assert.match(options, /id="regionShortcutRecorder"/);
  assert.match(options, /id="viewportShortcutRecorder"/);
  assert.match(options, /id="showCaptureNotice"/);
  assert.match(sidepanel, /NOISE WINSTON \/ SCREEN TEXT/);
  assert.match(sidepanel, /design-system\.css/);
  assert.match(sidepanel, /theme\.js/);
  assert.match(popupCss, /var\(--nw-purple\)/);
  assert.match(sidepanelCss, /var\(--nw-purple\)/);
  assert.match(sidepanelCss, /var\(--nw-lime\)/);
  assert.doesNotMatch(optionsJs, /style\.color/);
  assert.match(content, /chrome\.runtime\.getURL\("icons\/icon-32\.png"\)/);
  assert.match(content, /NoiseWinstonTheme\?\.register\(root\)/);
  assert.match(background, /case "SAVE_THEME_MODE"/);
  assert.match(background, /const DEFAULT_THEME_MODE = "system"/);
});
