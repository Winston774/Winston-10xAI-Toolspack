import { createHash, randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, open, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

const MIME_BY_EXTENSION = new Map([
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".png", "image/png"],
  [".webp", "image/webp"],
  [".gif", "image/gif"],
]);

const EXTENSION_BY_MIME = new Map([
  ["image/jpeg", ".jpg"],
  ["image/png", ".png"],
  ["image/webp", ".webp"],
  ["image/gif", ".gif"],
]);

const MAX_UPLOAD_BYTES = 30 * 1024 * 1024;

export async function ensureLibraryDirectories({ dataDir, inboxDir }) {
  await Promise.all([
    mkdir(dataDir, { recursive: true }),
    mkdir(inboxDir, { recursive: true }),
  ]);
}

function toPosixRelative(root, absolutePath) {
  return path.relative(root, absolutePath).split(path.sep).join("/");
}

function ensureInside(root, candidate) {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = path.resolve(candidate);
  if (
    resolvedCandidate !== resolvedRoot &&
    !resolvedCandidate.startsWith(`${resolvedRoot}${path.sep}`)
  ) {
    throw new Error("檔案路徑不在 Stylebase 圖片資料夾內。");
  }
  return resolvedCandidate;
}

async function walkImages(root) {
  const files = [];

  async function walk(current) {
    const entries = await readdir(current, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const absolutePath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(absolutePath);
        continue;
      }
      if (!entry.isFile()) continue;
      if (MIME_BY_EXTENSION.has(path.extname(entry.name).toLowerCase())) {
        files.push(absolutePath);
      }
    }
  }

  await walk(root);
  return files.sort((a, b) => a.localeCompare(b));
}

async function sha256File(filePath) {
  const hash = createHash("sha256");
  return new Promise((resolve, reject) => {
    const stream = createReadStream(filePath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

async function readPrefix(filePath, length = 96 * 1024) {
  const handle = await open(filePath, "r");
  try {
    const buffer = Buffer.alloc(length);
    const { bytesRead } = await handle.read(buffer, 0, length, 0);
    return buffer.subarray(0, bytesRead);
  } finally {
    await handle.close();
  }
}

function isPng(buffer) {
  return (
    buffer.length >= 24 &&
    buffer[0] === 0x89 &&
    buffer.subarray(1, 4).toString("ascii") === "PNG"
  );
}

function isGif(buffer) {
  return (
    buffer.length >= 10 &&
    (buffer.subarray(0, 6).toString("ascii") === "GIF87a" ||
      buffer.subarray(0, 6).toString("ascii") === "GIF89a")
  );
}

function isJpeg(buffer) {
  return buffer.length >= 4 && buffer[0] === 0xff && buffer[1] === 0xd8;
}

function isWebp(buffer) {
  return (
    buffer.length >= 16 &&
    buffer.subarray(0, 4).toString("ascii") === "RIFF" &&
    buffer.subarray(8, 12).toString("ascii") === "WEBP"
  );
}

function dimensionsFromJpeg(buffer) {
  let offset = 2;
  const sofMarkers = new Set([
    0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce,
    0xcf,
  ]);

  while (offset + 9 < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    const marker = buffer[offset + 1];
    if (marker === 0xd8 || marker === 0xd9) {
      offset += 2;
      continue;
    }
    const segmentLength = buffer.readUInt16BE(offset + 2);
    if (segmentLength < 2 || offset + segmentLength + 2 > buffer.length) break;
    if (sofMarkers.has(marker)) {
      return {
        width: buffer.readUInt16BE(offset + 7),
        height: buffer.readUInt16BE(offset + 5),
      };
    }
    offset += segmentLength + 2;
  }
  return { width: null, height: null };
}

function dimensionsFromWebp(buffer) {
  if (buffer.length < 30) return { width: null, height: null };
  const chunk = buffer.subarray(12, 16).toString("ascii");
  if (chunk === "VP8X" && buffer.length >= 30) {
    return {
      width: 1 + buffer.readUIntLE(24, 3),
      height: 1 + buffer.readUIntLE(27, 3),
    };
  }
  if (chunk === "VP8L" && buffer.length >= 25 && buffer[20] === 0x2f) {
    const bits = buffer.readUInt32LE(21);
    return {
      width: (bits & 0x3fff) + 1,
      height: ((bits >> 14) & 0x3fff) + 1,
    };
  }
  if (chunk === "VP8 " && buffer.length >= 30) {
    const start = buffer.indexOf(Buffer.from([0x9d, 0x01, 0x2a]), 20);
    if (start >= 0 && start + 7 <= buffer.length) {
      return {
        width: buffer.readUInt16LE(start + 3) & 0x3fff,
        height: buffer.readUInt16LE(start + 5) & 0x3fff,
      };
    }
  }
  return { width: null, height: null };
}

function inspectBuffer(buffer, declaredMime = "") {
  let mimeType;
  let dimensions = { width: null, height: null };

  if (isPng(buffer)) {
    mimeType = "image/png";
    dimensions = {
      width: buffer.readUInt32BE(16),
      height: buffer.readUInt32BE(20),
    };
  } else if (isGif(buffer)) {
    mimeType = "image/gif";
    dimensions = {
      width: buffer.readUInt16LE(6),
      height: buffer.readUInt16LE(8),
    };
  } else if (isJpeg(buffer)) {
    mimeType = "image/jpeg";
    dimensions = dimensionsFromJpeg(buffer);
  } else if (isWebp(buffer)) {
    mimeType = "image/webp";
    dimensions = dimensionsFromWebp(buffer);
  } else {
    throw new Error("檔案內容不是支援的 JPG、PNG、WebP 或 GIF 圖片。");
  }

  if (declaredMime && declaredMime !== mimeType) {
    throw new Error(`圖片格式與檔案宣告不一致（偵測為 ${mimeType}）。`);
  }

  return { mimeType, ...dimensions };
}

function sanitizeBaseName(fileName) {
  const raw = path.basename(fileName, path.extname(fileName));
  const safe = raw
    .normalize("NFKC")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, " ")
    .replace(/[. ]+$/g, "")
    .slice(0, 120);
  return safe || "stylebase-image";
}

export async function saveUploadedImage({
  inboxDir,
  name,
  type,
  data,
}) {
  if (typeof data !== "string" || data.length === 0) {
    throw new Error("沒有收到圖片資料。");
  }
  const base64 = data.includes(",") ? data.slice(data.indexOf(",") + 1) : data;
  const buffer = Buffer.from(base64, "base64");
  if (buffer.length === 0) throw new Error("圖片資料無法解碼。");
  if (buffer.length > MAX_UPLOAD_BYTES) {
    throw new Error("單張圖片不可超過 30 MB。");
  }

  const inspected = inspectBuffer(buffer, type || "");
  const extension = EXTENSION_BY_MIME.get(inspected.mimeType);
  const baseName = sanitizeBaseName(name || "stylebase-image");
  let destination = path.join(inboxDir, `${baseName}${extension}`);
  let suffix = 2;
  while (true) {
    try {
      await stat(destination);
      destination = path.join(inboxDir, `${baseName}-${suffix}${extension}`);
      suffix += 1;
    } catch (error) {
      if (error.code === "ENOENT") break;
      throw error;
    }
  }

  await writeFile(destination, buffer, { flag: "wx" });
  return {
    absolutePath: destination,
    relativePath: toPosixRelative(inboxDir, destination),
    ...inspected,
  };
}

export async function scanInbox({
  catalog,
  inboxDir,
  autoAnalyze = true,
}) {
  const files = await walkImages(inboxDir);
  const seen = [];
  const result = {
    scanned: files.length,
    imported: 0,
    duplicates: 0,
    queued: 0,
    invalid: [],
  };

  for (const absolutePath of files) {
    const relativePath = toPosixRelative(inboxDir, absolutePath);
    seen.push(relativePath);
    try {
      const fileStat = await stat(absolutePath);
      const extensionMime = MIME_BY_EXTENSION.get(
        path.extname(absolutePath).toLowerCase(),
      );
      const prefix = await readPrefix(absolutePath);
      const inspected = inspectBuffer(prefix, extensionMime);
      const sha256 = await sha256File(absolutePath);
      const { asset, isNew, isDuplicate } = catalog.upsertAsset({
        id: randomUUID(),
        sha256,
        relativePath,
        fileName: path.basename(absolutePath),
        mimeType: inspected.mimeType,
        width: inspected.width,
        height: inspected.height,
        fileSize: fileStat.size,
        mtimeMs: Math.round(fileStat.mtimeMs),
      });

      if (isNew) {
        result.imported += 1;
        if (autoAnalyze) {
          catalog.enqueueAnalysis(asset.id);
          result.queued += 1;
        }
      } else if (isDuplicate) {
        result.duplicates += 1;
      }
    } catch (error) {
      result.invalid.push({
        file: relativePath,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  catalog.markMissingExcept(seen);
  return result;
}

export function resolveAssetPath(inboxDir, relativePath) {
  const normalized = String(relativePath || "").split("/").join(path.sep);
  return ensureInside(inboxDir, path.join(inboxDir, normalized));
}
