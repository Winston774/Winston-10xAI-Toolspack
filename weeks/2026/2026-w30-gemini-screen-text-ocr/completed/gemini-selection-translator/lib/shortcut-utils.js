"use strict";

(() => {
  const DEFAULT_REGION_SHORTCUT = Object.freeze({
    enabled: true,
    ctrl: false,
    alt: true,
    shift: true,
    meta: false,
    code: "KeyX"
  });

  const DEFAULT_VIEWPORT_SHORTCUT = Object.freeze({
    enabled: true,
    ctrl: false,
    alt: true,
    shift: true,
    meta: false,
    code: "KeyV"
  });

  const DEFAULT_SHORTCUT = DEFAULT_REGION_SHORTCUT;

  const KEY_LABELS = Object.freeze({
    Space: "Space",
    Comma: ",",
    Period: ".",
    Home: "Home",
    End: "End",
    PageUp: "Page Up",
    PageDown: "Page Down",
    Insert: "Insert",
    Delete: "Delete",
    ArrowUp: "↑",
    ArrowDown: "↓",
    ArrowLeft: "←",
    ArrowRight: "→"
  });

  function normalizeShortcut(value, fallback = DEFAULT_REGION_SHORTCUT) {
    const normalizedFallback = isValidShortcut(fallback)
      ? normalizeValidShortcut(fallback)
      : { ...DEFAULT_REGION_SHORTCUT };
    const enabled = value?.enabled !== false;
    if (!isValidShortcut(value)) {
      return { ...normalizedFallback, enabled };
    }
    return { ...normalizeValidShortcut(value), enabled };
  }

  function isValidShortcut(value) {
    const code = normalizeCode(value?.code);
    const ctrl = Boolean(value?.ctrl);
    const alt = Boolean(value?.alt);
    const meta = Boolean(value?.meta);
    return Boolean(code && (ctrl || alt || meta) && !(ctrl && alt));
  }

  function shortcutFromKeyboardEvent(event) {
    if (!event || event.repeat || event.isComposing || event.keyCode === 229 || event.getModifierState?.("AltGraph")) {
      return null;
    }
    const code = normalizeCode(event.code || codeFromKey(event.key));
    const ctrl = Boolean(event.ctrlKey);
    const alt = Boolean(event.altKey);
    const shift = Boolean(event.shiftKey);
    const meta = Boolean(event.metaKey);
    if (!code || (!ctrl && !alt && !meta) || (ctrl && alt)) {
      return null;
    }
    return { enabled: true, ctrl, alt, shift, meta, code };
  }

  function matchesKeyboardEvent(event, value) {
    const shortcut = normalizeShortcut(value);
    if (!shortcut.enabled || !event || event.repeat || event.isComposing || event.keyCode === 229 || event.getModifierState?.("AltGraph")) {
      return false;
    }
    return normalizeCode(event.code || codeFromKey(event.key)) === shortcut.code &&
      Boolean(event.ctrlKey) === shortcut.ctrl &&
      Boolean(event.altKey) === shortcut.alt &&
      Boolean(event.shiftKey) === shortcut.shift &&
      Boolean(event.metaKey) === shortcut.meta;
  }

  function formatShortcut(value) {
    const shortcut = normalizeShortcut(value);
    const labels = [];
    if (shortcut.ctrl) labels.push("Ctrl");
    if (shortcut.alt) labels.push("Alt");
    if (shortcut.shift) labels.push("Shift");
    if (shortcut.meta) labels.push("Meta");
    labels.push(labelForCode(shortcut.code));
    return labels.join(" + ");
  }

  function sameShortcut(left, right) {
    const first = normalizeShortcut(left);
    const second = normalizeShortcut(right);
    return first.code === second.code &&
      first.ctrl === second.ctrl &&
      first.alt === second.alt &&
      first.shift === second.shift &&
      first.meta === second.meta;
  }

  function normalizeValidShortcut(value) {
    return {
      ctrl: Boolean(value?.ctrl),
      alt: Boolean(value?.alt),
      shift: Boolean(value?.shift),
      meta: Boolean(value?.meta),
      code: normalizeCode(value?.code)
    };
  }

  function normalizeCode(value) {
    const code = String(value || "").trim();
    if (/^Key[A-Z]$/.test(code) || /^Digit[0-9]$/.test(code) || /^F(?:[1-9]|1[0-2])$/.test(code)) {
      return code;
    }
    return Object.prototype.hasOwnProperty.call(KEY_LABELS, code) ? code : "";
  }

  function labelForCode(code) {
    if (/^Key[A-Z]$/.test(code)) return code.slice(3);
    if (/^Digit[0-9]$/.test(code)) return code.slice(5);
    return KEY_LABELS[code] || code;
  }

  function codeFromKey(value) {
    const key = String(value || "");
    if (/^[a-z]$/i.test(key)) return `Key${key.toUpperCase()}`;
    if (/^[0-9]$/.test(key)) return `Digit${key}`;
    if (key === " ") return "Space";
    return key;
  }

  globalThis.ShortcutUtils = Object.freeze({
    DEFAULT_SHORTCUT,
    DEFAULT_REGION_SHORTCUT,
    DEFAULT_VIEWPORT_SHORTCUT,
    normalizeShortcut,
    isValidShortcut,
    shortcutFromKeyboardEvent,
    matchesKeyboardEvent,
    formatShortcut,
    sameShortcut
  });
})();
