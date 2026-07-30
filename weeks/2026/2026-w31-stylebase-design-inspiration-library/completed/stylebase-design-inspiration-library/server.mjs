import { createReadStream, watch } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createCatalog } from "./src/db.mjs";
import {
  ensureLibraryDirectories,
  resolveAssetPath,
  saveUploadedImage,
  scanInbox,
} from "./src/library.mjs";
import {
  checkCodexAgent,
  runCodexAnalysis,
} from "./src/codex-agent.mjs";

const ROOT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(ROOT_DIR, "public");
const DATA_DIR = path.join(ROOT_DIR, "data");
const INBOX_DIR = path.join(ROOT_DIR, "library", "inbox");
const DB_PATH = path.join(DATA_DIR, "catalog.sqlite");
const HOST = "127.0.0.1";
const PORT = numberInRange(process.env.STYLEBASE_PORT, 4177, 1024, 65535);
const BODY_LIMIT = 42 * 1024 * 1024;
const VERSION = "1.0.0";

const STATIC_MIME = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".gif", "image/gif"],
  [".ico", "image/x-icon"],
]);

await ensureLibraryDirectories({ dataDir: DATA_DIR, inboxDir: INBOX_DIR });
const catalog = createCatalog(DB_PATH);

let scanInFlight = null;
let workerBusy = false;
let watcher = null;
let watcherTimer = null;
let providerCache = null;
let providerCacheAt = 0;

function numberInRange(value, fallback, min, max) {
  const number = Number(value);
  return Number.isFinite(number) && number >= min && number <= max
    ? Math.round(number)
    : fallback;
}

class ApiError extends Error {
  constructor(status, message, details = null) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function securityHeaders(contentType = null) {
  const headers = {
    "Cache-Control": "no-store",
    "Content-Security-Policy":
      "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
  };
  if (contentType) headers["Content-Type"] = contentType;
  return headers;
}

function sendJson(response, status, payload) {
  response.writeHead(
    status,
    securityHeaders("application/json; charset=utf-8"),
  );
  response.end(JSON.stringify(payload));
}

function sendEmpty(response, status = 204) {
  response.writeHead(status, securityHeaders());
  response.end();
}

async function readJsonBody(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > BODY_LIMIT) {
      throw new ApiError(413, "請求內容過大；單張圖片上限為 30 MB。");
    }
    chunks.push(chunk);
  }
  if (bytes === 0) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new ApiError(400, "JSON 格式不正確。");
  }
}

function safeAsset(asset) {
  if (!asset) return null;
  return {
    ...asset,
    mediaUrl: `/media/${encodeURIComponent(asset.id)}`,
  };
}

function safeSettings(settings) {
  return {
    codexModel: settings.codexModel || "",
    autoAnalyze: false,
    executionMode: "codex-agent",
    sandbox: "read-only",
    concurrency: 1,
    promptVersion: "stylebase-visual-v1",
  };
}

function getCodexConfiguration() {
  const settings = catalog.getSettings();
  return {
    executable:
      process.env.STYLEBASE_CODEX_EXECUTABLE ||
      settings.codexExecutable ||
      "codex",
    model:
      process.env.STYLEBASE_CODEX_MODEL || settings.codexModel || "",
    workingDirectory: ROOT_DIR,
    dataDirectory: DATA_DIR,
  };
}

async function getProviderStatus(force = false) {
  const now = Date.now();
  if (!force && providerCache && now - providerCacheAt < 15_000) {
    return providerCache;
  }
  providerCache = await checkCodexAgent(getCodexConfiguration());
  providerCacheAt = now;
  return providerCache;
}

async function performScan() {
  if (scanInFlight) return scanInFlight;
  scanInFlight = scanInbox({
    catalog,
    inboxDir: INBOX_DIR,
    autoAnalyze: false,
  }).finally(() => {
    scanInFlight = null;
  });
  return scanInFlight;
}

function scheduleScan() {
  clearTimeout(watcherTimer);
  watcherTimer = setTimeout(() => {
    performScan().catch((error) => {
      console.error(`[stylebase] scan failed: ${error.message}`);
    });
  }, 700);
}

async function processNextJob() {
  if (workerBusy) return;
  const job = catalog.claimNextJob();
  if (!job) return;
  workerBusy = true;

  try {
    const asset = catalog.getAsset(job.assetId);
    if (!asset) throw new Error("找不到這筆圖片紀錄。");
    if (asset.fileStatus === "missing") {
      throw new Error("原始圖片已不在 library/inbox；請放回檔案後重新掃描。");
    }

    const filePath = resolveAssetPath(INBOX_DIR, asset.relativePath);
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) throw new Error("原始圖片不是可讀取的檔案。");

    const result = await runCodexAnalysis({
      imagePath: filePath,
      mimeType: asset.mimeType,
      configuration: getCodexConfiguration(),
    });

    catalog.saveAnalysis(asset.id, {
      provider: "codex",
      model: result.model || getCodexConfiguration().model || "signed-in-default",
      analysis: result.analysis,
      raw: result.raw,
    });
    catalog.completeJob(job.id);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const state =
      error?.code === "CODEX_UNAVAILABLE" ||
      error?.code === "CODEX_AUTH_REQUIRED" ||
      error?.code === "CODEX_CONFIGURATION"
        ? "needs_setup"
        : "failed";
    catalog.failJob(job.id, state, message);
  } finally {
    workerBusy = false;
  }
}

async function handleApi(request, response, url) {
  const method = request.method || "GET";
  const pathname = url.pathname;

  if (method === "GET" && pathname === "/api/bootstrap") {
    const [provider] = await Promise.all([getProviderStatus()]);
    const assets = catalog.listAssets({
      limit: 80,
      offset: 0,
      sort: "newest",
    });
    sendJson(response, 200, {
      version: VERSION,
      stats: catalog.getStats(),
      assets: {
        ...assets,
        items: assets.items.map(safeAsset),
      },
      jobs: catalog.listJobs({ limit: 30, offset: 0 }),
      settings: safeSettings(catalog.getSettings()),
      provider,
      facets: catalog.getFacets(),
      collections: catalog.listCollections(),
      paths: {
        inbox: INBOX_DIR,
        database: DB_PATH,
      },
    });
    return true;
  }

  if (method === "GET" && pathname === "/api/assets") {
    const filters = {
      query: url.searchParams.get("query") || "",
      status: url.searchParams.get("status") || "",
      domain: url.searchParams.get("domain") || "",
      favorite: url.searchParams.get("favorite") || "",
      collectionId: url.searchParams.get("collectionId") || "",
      sort: url.searchParams.get("sort") || "newest",
      limit: numberInRange(url.searchParams.get("limit"), 80, 1, 200),
      offset: numberInRange(url.searchParams.get("offset"), 0, 0, 1_000_000),
    };
    const result = catalog.listAssets(filters);
    sendJson(response, 200, {
      ...result,
      items: result.items.map(safeAsset),
    });
    return true;
  }

  if (method === "POST" && pathname === "/api/import") {
    const body = await readJsonBody(request);
    const uploaded = await saveUploadedImage({
      inboxDir: INBOX_DIR,
      name: body.name,
      type: body.type,
      data: body.data,
    });
    const scan = await performScan();
    let asset = catalog.getAssetByRelativePath(uploaded.relativePath);
    if (asset && (body.sourceUrl || body.rightsNote)) {
      asset = catalog.updateAsset(asset.id, {
        sourceUrl: body.sourceUrl || "",
        rightsNote: body.rightsNote || "",
      });
    }
    sendJson(response, 201, {
      asset: safeAsset(asset),
      scan,
    });
    return true;
  }

  if (method === "POST" && pathname === "/api/scan") {
    sendJson(response, 200, await performScan());
    return true;
  }

  if (method === "GET" && pathname === "/api/jobs") {
    sendJson(response, 200, {
      ...catalog.listJobs({
        state: url.searchParams.get("state") || "",
        limit: numberInRange(url.searchParams.get("limit"), 80, 1, 200),
        offset: numberInRange(url.searchParams.get("offset"), 0, 0, 1_000_000),
      }),
      workerBusy,
    });
    return true;
  }

  if (method === "POST" && pathname === "/api/jobs/retry-needs-setup") {
    const count = catalog.retryNeedsSetup();
    providerCache = null;
    sendJson(response, 200, { retried: count });
    return true;
  }

  if (method === "GET" && pathname === "/api/settings") {
    sendJson(response, 200, safeSettings(catalog.getSettings()));
    return true;
  }

  if (method === "PATCH" && pathname === "/api/settings") {
    const body = await readJsonBody(request);
    const model = String(body.codexModel ?? "").trim();
    if (model && !/^[a-zA-Z0-9._:/-]{1,120}$/.test(model)) {
      throw new ApiError(400, "Codex 模型名稱含有不支援的字元。");
    }
    const settings = catalog.updateSettings({ codexModel: model });
    providerCache = null;
    sendJson(response, 200, safeSettings(settings));
    return true;
  }

  if (method === "GET" && pathname === "/api/providers") {
    sendJson(response, 200, await getProviderStatus(true));
    return true;
  }

  if (method === "GET" && pathname === "/api/facets") {
    sendJson(response, 200, catalog.getFacets());
    return true;
  }

  if (method === "GET" && pathname === "/api/collections") {
    sendJson(response, 200, catalog.listCollections());
    return true;
  }

  if (method === "POST" && pathname === "/api/collections") {
    const body = await readJsonBody(request);
    const name = String(body.name || "").trim();
    if (name.length < 1 || name.length > 80) {
      throw new ApiError(400, "收藏集名稱需為 1–80 個字元。");
    }
    sendJson(response, 201, catalog.createCollection(name));
    return true;
  }

  const assetMatch = pathname.match(/^\/api\/assets\/([^/]+)$/);
  if (assetMatch) {
    const id = decodeURIComponent(assetMatch[1]);
    if (method === "GET") {
      const asset = catalog.getAsset(id);
      if (!asset) throw new ApiError(404, "找不到這筆圖片。");
      sendJson(response, 200, safeAsset(asset));
      return true;
    }
    if (method === "PATCH") {
      const body = await readJsonBody(request);
      const allowed = {};
      for (const key of [
        "title",
        "notes",
        "sourceUrl",
        "rightsNote",
        "favorite",
      ]) {
        if (Object.hasOwn(body, key)) allowed[key] = body[key];
      }
      const asset = catalog.updateAsset(id, allowed);
      if (!asset) throw new ApiError(404, "找不到這筆圖片。");
      sendJson(response, 200, safeAsset(asset));
      return true;
    }
  }

  const analyzeMatch = pathname.match(
    /^\/api\/assets\/([^/]+)\/analyze$/,
  );
  if (method === "POST" && analyzeMatch) {
    const id = decodeURIComponent(analyzeMatch[1]);
    if (!catalog.getAsset(id)) throw new ApiError(404, "找不到這筆圖片。");
    const job = catalog.enqueueAnalysis(id, "codex");
    sendJson(response, 202, job);
    return true;
  }

  const retryMatch = pathname.match(/^\/api\/jobs\/([^/]+)\/retry$/);
  if (method === "POST" && retryMatch) {
    const job = catalog.retryJob(decodeURIComponent(retryMatch[1]));
    if (!job) throw new ApiError(404, "找不到這筆分析工作。");
    sendJson(response, 200, job);
    return true;
  }

  const collectionMatch = pathname.match(/^\/api\/collections\/([^/]+)$/);
  if (method === "GET" && collectionMatch) {
    const collection = catalog.getCollection(
      decodeURIComponent(collectionMatch[1]),
    );
    if (!collection) throw new ApiError(404, "找不到這個收藏集。");
    collection.items = collection.items.map(safeAsset);
    sendJson(response, 200, collection);
    return true;
  }

  const collectionItemsMatch = pathname.match(
    /^\/api\/collections\/([^/]+)\/items$/,
  );
  if (method === "POST" && collectionItemsMatch) {
    const body = await readJsonBody(request);
    const item = catalog.addCollectionItem(
      decodeURIComponent(collectionItemsMatch[1]),
      String(body.assetId || ""),
    );
    sendJson(response, 201, item);
    return true;
  }

  const collectionItemMatch = pathname.match(
    /^\/api\/collections\/([^/]+)\/items\/([^/]+)$/,
  );
  if (method === "DELETE" && collectionItemMatch) {
    catalog.removeCollectionItem(
      decodeURIComponent(collectionItemMatch[1]),
      decodeURIComponent(collectionItemMatch[2]),
    );
    sendEmpty(response);
    return true;
  }

  return false;
}

async function serveMedia(response, id) {
  const asset = catalog.getAsset(id);
  if (!asset) throw new ApiError(404, "找不到圖片。");
  if (asset.fileStatus === "missing") {
    throw new ApiError(410, "原始圖片已移動或不存在。");
  }
  const filePath = resolveAssetPath(INBOX_DIR, asset.relativePath);
  const fileStat = await stat(filePath);
  response.writeHead(200, {
    ...securityHeaders(asset.mimeType || "application/octet-stream"),
    "Cache-Control": "private, max-age=300",
    "Content-Length": fileStat.size,
  });
  createReadStream(filePath).pipe(response);
}

async function serveStatic(response, pathname) {
  const relative = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
  const candidate = path.resolve(PUBLIC_DIR, relative);
  const publicRoot = path.resolve(PUBLIC_DIR);
  if (
    candidate !== publicRoot &&
    !candidate.startsWith(`${publicRoot}${path.sep}`)
  ) {
    throw new ApiError(403, "不允許存取這個路徑。");
  }

  let filePath = candidate;
  try {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) throw new Error("not-file");
  } catch {
    filePath = path.join(PUBLIC_DIR, "index.html");
  }
  const extension = path.extname(filePath).toLowerCase();
  const content = await readFile(filePath);
  response.writeHead(
    200,
    securityHeaders(STATIC_MIME.get(extension) || "application/octet-stream"),
  );
  response.end(content);
}

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://${HOST}:${PORT}`);
    if (url.pathname.startsWith("/api/")) {
      const handled = await handleApi(request, response, url);
      if (!handled) throw new ApiError(404, "找不到這個 API。");
      return;
    }
    if (url.pathname.startsWith("/media/")) {
      await serveMedia(
        response,
        decodeURIComponent(url.pathname.slice("/media/".length)),
      );
      return;
    }
    if ((request.method || "GET") !== "GET") {
      throw new ApiError(405, "此路徑不支援這個動作。");
    }
    await serveStatic(response, decodeURIComponent(url.pathname));
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    const message =
      error instanceof ApiError
        ? error.message
        : "Stylebase 處理請求時發生未預期的錯誤。";
    if (status >= 500) console.error(error);
    if (!response.headersSent) {
      sendJson(response, status, {
        error: message,
        details: error instanceof ApiError ? error.details : null,
      });
    } else {
      response.destroy(error);
    }
  }
});

await performScan();

try {
  watcher = watch(INBOX_DIR, { recursive: true }, scheduleScan);
  watcher.on("error", (error) => {
    console.error(`[stylebase] folder watcher stopped: ${error.message}`);
  });
} catch (error) {
  console.error(`[stylebase] folder watcher unavailable: ${error.message}`);
}

const workerTimer = setInterval(() => {
  processNextJob().catch((error) => console.error(error));
}, 800);

server.listen(PORT, HOST, () => {
  console.log("");
  console.log(`STYLEBASE ${VERSION}`);
  console.log(`Local URL  http://${HOST}:${PORT}`);
  console.log(`Inbox      ${INBOX_DIR}`);
  console.log(`Database   ${DB_PATH}`);
  console.log("");
});

function shutdown() {
  clearInterval(workerTimer);
  clearTimeout(watcherTimer);
  watcher?.close();
  server.close(() => {
    catalog.close();
    process.exit(0);
  });
}

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
