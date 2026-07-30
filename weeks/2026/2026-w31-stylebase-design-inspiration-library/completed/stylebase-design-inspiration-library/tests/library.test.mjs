import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  ensureLibraryDirectories,
  resolveAssetPath,
  saveUploadedImage,
  scanInbox,
} from "../src/library.mjs";

const ONE_PIXEL_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

test("saveUploadedImage and scanInbox import a valid PNG without auto-dispatch", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "stylebase-library-"));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  const dataDir = path.join(root, "data");
  const inboxDir = path.join(root, "inbox");
  await ensureLibraryDirectories({ dataDir, inboxDir });

  const records = new Map();
  let queued = 0;
  let seen = [];
  const catalog = {
    upsertAsset(record) {
      const existing = [...records.values()].find(
        (item) => item.sha256 === record.sha256,
      );
      if (existing) {
        return { asset: existing, isNew: false, isDuplicate: true };
      }
      const asset = {
        ...record,
        fileStatus: "active",
        analysisStatus: "pending",
      };
      records.set(record.id, asset);
      return { asset, isNew: true, isDuplicate: false };
    },
    enqueueAnalysis() {
      queued += 1;
    },
    markMissingExcept(paths) {
      seen = paths;
    },
  };

  const uploaded = await saveUploadedImage({
    inboxDir,
    name: "我的參考.png",
    type: "image/png",
    data: ONE_PIXEL_PNG,
  });
  assert.equal(uploaded.width, 1);
  assert.equal(uploaded.height, 1);
  assert.equal(uploaded.relativePath, "我的參考.png");

  const result = await scanInbox({
    catalog,
    inboxDir,
    autoAnalyze: false,
  });
  assert.equal(result.scanned, 1);
  assert.equal(result.imported, 1);
  assert.equal(result.queued, 0);
  assert.equal(queued, 0);
  assert.deepEqual(seen, ["我的參考.png"]);
  assert.equal([...records.values()][0].mimeType, "image/png");
});

test("saveUploadedImage rejects disguised non-image data", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "stylebase-library-"));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  await assert.rejects(
    saveUploadedImage({
      inboxDir: root,
      name: "not-an-image.png",
      type: "image/png",
      data: Buffer.from("not an image").toString("base64"),
    }),
    /不是支援的/,
  );
});

test("resolveAssetPath refuses traversal outside the inbox", () => {
  const inbox = path.resolve("D:/stylebase/library/inbox");
  assert.throws(
    () => resolveAssetPath(inbox, "../../outside.png"),
    /不在 Stylebase 圖片資料夾內/,
  );
});
