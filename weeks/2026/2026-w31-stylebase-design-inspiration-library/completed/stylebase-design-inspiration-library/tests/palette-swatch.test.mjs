import assert from "node:assert/strict";
import test from "node:test";

import {
  renderSwatchColor,
  safeHexColor,
} from "../public/palette-swatch.js";

test("palette swatches render validated colors without CSP-blocked inline styles", () => {
  const markup = renderSwatchColor("#FFFF10");

  assert.match(markup, /<rect[^>]+fill="#FFFF10"/);
  assert.doesNotMatch(markup, /\sstyle=/);
});

test("palette swatches replace malformed colors with the neutral fallback", () => {
  assert.equal(safeHexColor("#12345"), "#d7d7d2");
  assert.match(renderSwatchColor("red"), /fill="#d7d7d2"/);
});
