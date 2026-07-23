import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

async function loadCaptureUtils() {
  const source = await readFile(new URL("../lib/capture-utils.js", import.meta.url), "utf8");
  const context = { TextEncoder };
  context.globalThis = context;
  vm.runInNewContext(source, context);
  return context.CaptureUtils;
}

test("normalizes reverse-direction selections", async () => {
  const utils = await loadCaptureUtils();
  assert.deepEqual(
    { ...utils.normalizeSelection(320, 210, 80, 40) },
    { left: 80, top: 40, right: 320, bottom: 210, width: 240, height: 170 }
  );
});

test("rejects tiny rectangles and clamps valid bounds", async () => {
  const utils = await loadCaptureUtils();
  const tiny = utils.validateSelection(
    { left: 5, top: 5, right: 15, bottom: 14, width: 10, height: 9 },
    { width: 100, height: 80 }
  );
  assert.equal(tiny.ok, false);
  assert.equal(tiny.code, "selection_too_small");

  const valid = utils.validateSelection(
    { left: -4, top: -2, right: 70, bottom: 60, width: 74, height: 62 },
    { width: 64, height: 48 }
  );
  assert.equal(valid.ok, true);
  assert.deepEqual({ ...valid.rect }, { left: 0, top: 0, right: 64, bottom: 48, width: 64, height: 48 });
});

test("maps CSS viewport coordinates to real screenshot pixels", async () => {
  const utils = await loadCaptureUtils();
  const crop = utils.computeCropRect(
    { left: 100.4, top: 50.2, right: 400.1, bottom: 200.4, width: 299.7, height: 150.2 },
    { width: 1000, height: 500 },
    { width: 1250, height: 625 }
  );
  assert.equal(crop.x, 125);
  assert.equal(crop.y, 62);
  assert.equal(crop.width, 376);
  assert.equal(crop.height, 189);
  assert.equal(crop.scaleX, 1.25);
  assert.equal(crop.scaleY, 1.25);
});

test("uses independent X/Y scale instead of devicePixelRatio", async () => {
  const utils = await loadCaptureUtils();
  const crop = utils.computeCropRect(
    { left: 10, top: 10, right: 90, bottom: 90, width: 80, height: 80 },
    { width: 100, height: 100 },
    { width: 150, height: 125 }
  );
  assert.deepEqual(
    { x: crop.x, y: crop.y, width: crop.width, height: crop.height },
    { x: 15, y: 12, width: 120, height: 101 }
  );
});

test("parses only supported base64 image data URLs and counts bytes", async () => {
  const utils = await loadCaptureUtils();
  const parsed = utils.parseDataUrl("data:image/png;base64,AQIDBA==");
  assert.equal(parsed.mimeType, "image/png");
  assert.equal(parsed.byteLength, 4);
  assert.equal(utils.parseDataUrl("data:image/svg+xml;base64,PHN2Zz4="), null);
});
