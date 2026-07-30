import assert from "node:assert/strict";
import test from "node:test";

import { beginPendingButtons } from "../public/button-state.js";

function createButton({ disabled = false, innerHTML, isConnected = true }) {
  let html = innerHTML;
  let text = "";
  return {
    disabled,
    isConnected,
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
    },
    get textContent() {
      return text;
    },
    set textContent(value) {
      text = value;
      html = "";
    },
  };
}

test("pending buttons restore their original markup and enabled state", () => {
  const button = createButton({
    innerHTML: '<svg aria-hidden="true"></svg><span>送交 Codex</span>',
  });

  const restore = beginPendingButtons([button]);
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, "送交中…");
  assert.equal(button.innerHTML, "");

  restore();
  assert.equal(button.disabled, false);
  assert.equal(
    button.innerHTML,
    '<svg aria-hidden="true"></svg><span>送交 Codex</span>',
  );
});
