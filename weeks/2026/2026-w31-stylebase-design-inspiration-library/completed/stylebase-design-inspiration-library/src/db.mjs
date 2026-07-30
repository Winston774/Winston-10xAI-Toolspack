import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

const DEFAULT_LIMIT = 48;
const MAX_LIMIT = 200;
const JOB_STATES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
  "needs_setup",
]);
const FAILURE_STATES = new Set(["failed", "needs_setup"]);
const DEFAULT_SETTINGS = Object.freeze({
  provider: "codex",
  autoAnalyze: false,
  codexExecutable: null,
  codexModel: null,
  agentSandbox: "read-only",
  concurrency: 1,
});

const ASSET_SELECT = `
  SELECT
    a.*,
    an.id AS analysis_id,
    an.version AS analysis_version,
    an.provider AS analysis_provider,
    an.model AS analysis_model,
    an.summary AS analysis_summary,
    an.detail AS analysis_detail,
    an.tags_json AS analysis_tags_json,
    an.prompts_json AS analysis_prompts_json,
    an.analysis_json AS analysis_json,
    an.raw_json AS analysis_raw_json,
    an.created_at AS analysis_created_at
  FROM assets a
  LEFT JOIN analyses an
    ON an.asset_id = a.id
   AND an.is_current = 1
`;

function isPlainObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype ||
      Object.getPrototypeOf(value) === null)
  );
}

function pick(object, ...keys) {
  for (const key of keys) {
    if (Object.hasOwn(object, key)) {
      return object[key];
    }
  }
  return undefined;
}

function requirePlainObject(value, label) {
  if (!isPlainObject(value)) {
    throw new TypeError(`${label} must be a plain object.`);
  }
  return value;
}

function requiredString(value, label, maxLength = 10_000) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError(`${label} must be a non-empty string.`);
  }
  const normalized = value.trim();
  if (normalized.length > maxLength) {
    throw new RangeError(`${label} must be at most ${maxLength} characters.`);
  }
  return normalized;
}

function optionalString(value, label, maxLength = 100_000) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  if (typeof value !== "string") {
    throw new TypeError(`${label} must be a string or null.`);
  }
  const normalized = value.trim();
  if (normalized.length > maxLength) {
    throw new RangeError(`${label} must be at most ${maxLength} characters.`);
  }
  return normalized === "" ? null : normalized;
}

function nonNegativeNumber(value, label, fallback = 0) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    throw new TypeError(`${label} must be a non-negative finite number.`);
  }
  return number;
}

function optionalPositiveInteger(value, label) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) {
    throw new TypeError(`${label} must be a positive integer or null.`);
  }
  return number;
}

function positiveId(value, label) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number <= 0) {
    throw new TypeError(`${label} must be a positive integer.`);
  }
  return number;
}

function paginationInteger(value, fallback, maximum = Number.MAX_SAFE_INTEGER) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 0) {
    throw new TypeError("Pagination values must be non-negative integers.");
  }
  return Math.min(number, maximum);
}

function booleanValue(value, label) {
  if (value === true || value === false) {
    return value;
  }
  if (value === 1 || value === "1" || value === "true") {
    return true;
  }
  if (value === 0 || value === "0" || value === "false") {
    return false;
  }
  throw new TypeError(`${label} must be a boolean.`);
}

function normalizeRelativePath(value) {
  const input = requiredString(value, "relativePath", 2_048).replaceAll("\\", "/");
  const normalized = input.replace(/^\.\/+/, "").replace(/\/+/g, "/");
  const segments = normalized.split("/");
  if (
    normalized.startsWith("/") ||
    /^[A-Za-z]:\//.test(normalized) ||
    segments.some((segment) => segment === ".." || segment === "")
  ) {
    throw new TypeError("relativePath must be a safe relative path.");
  }
  return normalized;
}

function normalizeSha256(value) {
  const sha256 = requiredString(value, "sha256", 64).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(sha256)) {
    throw new TypeError("sha256 must be a 64-character hexadecimal digest.");
  }
  return sha256;
}

function sourceDomain(sourceUrl) {
  if (!sourceUrl) {
    return null;
  }
  try {
    return new URL(sourceUrl).hostname.toLowerCase().replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}

function jsonStringify(value, label) {
  try {
    const serialized = JSON.stringify(value);
    if (serialized === undefined) {
      throw new TypeError();
    }
    return serialized;
  } catch (error) {
    throw new TypeError(`${label} must be JSON-serializable.`, { cause: error });
  }
}

function jsonParse(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return JSON.parse(value);
}

function flattenText(value, output = []) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed) {
      output.push(trimmed);
    }
  } else if (Array.isArray(value)) {
    for (const item of value) {
      flattenText(item, output);
    }
  } else if (isPlainObject(value)) {
    for (const item of Object.values(value)) {
      flattenText(item, output);
    }
  } else if (typeof value === "number" || typeof value === "boolean") {
    output.push(String(value));
  }
  return output;
}

function firstText(object, keys) {
  for (const key of keys) {
    const value = object[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function analysisSearchFields(analysis) {
  const summary = firstText(analysis, [
    "summary",
    "overview",
    "shortDescription",
    "styleSummary",
  ]);
  const detail = firstText(analysis, [
    "detail",
    "detailedDescription",
    "description",
    "visualAnalysis",
  ]);
  const tags =
    pick(
      analysis,
      "tags",
      "styleTags",
      "keywords",
      "categories",
      "designCategories",
    ) ?? [];
  const prompts =
    pick(
      analysis,
      "prompts",
      "prompt",
      "generatedPrompts",
      "recreationPrompt",
    ) ?? [];
  return {
    summary,
    detail,
    tags,
    prompts,
    tagsText: flattenText(tags).join(" "),
    promptsText: flattenText(prompts).join(" "),
  };
}

function safeFtsQuery(value) {
  if (value === undefined || value === null || String(value).trim() === "") {
    return null;
  }
  const tokens =
    String(value)
      .normalize("NFKC")
      .match(/[\p{L}\p{N}]+(?:[-_][\p{L}\p{N}]+)*/gu) ?? [];
  const unique = [...new Set(tokens.map((token) => token.toLocaleLowerCase()))].slice(
    0,
    16,
  );
  if (unique.length === 0) {
    return "";
  }
  return unique
    .map((token) => `"${token.replaceAll('"', '""')}"*`)
    .join(" AND ");
}

function normalizeFilterList(value) {
  if (value === undefined || value === null || value === "") {
    return [];
  }
  const values = Array.isArray(value) ? value : String(value).split(",");
  return [
    ...new Set(
      values
        .map((item) => String(item).trim())
        .filter(Boolean)
        .slice(0, 50),
    ),
  ];
}

function placeholders(count) {
  return Array.from({ length: count }, () => "?").join(", ");
}

function currentTimestamp() {
  return new Date().toISOString();
}

function analysisFromRow(row) {
  if (!row || row.analysis_id === null || row.analysis_id === undefined) {
    return null;
  }
  return {
    id: row.analysis_id,
    version: row.analysis_version,
    provider: row.analysis_provider,
    model: row.analysis_model,
    summary: row.analysis_summary,
    detail: row.analysis_detail,
    tags: jsonParse(row.analysis_tags_json, []),
    prompts: jsonParse(row.analysis_prompts_json, []),
    analysis: jsonParse(row.analysis_json, {}),
    raw: jsonParse(row.analysis_raw_json, null),
    createdAt: row.analysis_created_at,
  };
}

function assetFromRow(row) {
  if (!row) {
    return null;
  }
  return {
    id: row.id,
    sha256: row.sha256,
    relativePath: row.relative_path,
    fileName: row.file_name,
    mimeType: row.mime_type,
    width: row.width,
    height: row.height,
    dimensions:
      row.width !== null || row.height !== null
        ? { width: row.width, height: row.height }
        : null,
    fileSize: row.file_size,
    mtimeMs: row.mtime_ms,
    sourceUrl: row.source_url,
    sourceDomain: row.source_domain,
    rightsNote: row.rights_note,
    title: row.title,
    notes: row.notes,
    favorite: Boolean(row.favorite),
    fileStatus: row.file_status,
    analysisStatus: row.analysis_status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    currentAnalysis: analysisFromRow(row),
  };
}

function jobFromRow(row) {
  if (!row) {
    return null;
  }
  return {
    id: row.id,
    assetId: row.asset_id,
    provider: row.provider,
    state: row.state,
    attempts: row.attempts,
    lastError: row.last_error,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    startedAt: row.started_at,
    completedAt: row.completed_at,
    asset:
      row.file_name === undefined
        ? undefined
        : {
            id: row.asset_id,
            fileName: row.file_name,
            relativePath: row.relative_path,
            title: row.title,
            mimeType: row.mime_type,
            fileStatus: row.file_status,
            analysisStatus: row.analysis_status,
          },
  };
}

function collectionFromRow(row) {
  if (!row) {
    return null;
  }
  return {
    id: row.id,
    name: row.name,
    itemCount: Number(row.item_count ?? 0),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export function createCatalog(dbPath) {
  if (typeof dbPath !== "string" || dbPath.trim() === "") {
    throw new TypeError("dbPath must be a non-empty string.");
  }

  if (dbPath !== ":memory:" && !dbPath.startsWith("file:")) {
    mkdirSync(dirname(resolve(dbPath)), { recursive: true });
  }

  const db = new DatabaseSync(dbPath);
  let closed = false;

  db.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;
    PRAGMA busy_timeout = 5000;
    PRAGMA synchronous = NORMAL;

    CREATE TABLE IF NOT EXISTS assets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sha256 TEXT NOT NULL UNIQUE,
      relative_path TEXT NOT NULL COLLATE NOCASE,
      file_name TEXT NOT NULL,
      mime_type TEXT NOT NULL,
      width INTEGER,
      height INTEGER,
      file_size INTEGER NOT NULL DEFAULT 0,
      mtime_ms REAL NOT NULL DEFAULT 0,
      source_url TEXT,
      source_domain TEXT COLLATE NOCASE,
      rights_note TEXT,
      title TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
      file_status TEXT NOT NULL DEFAULT 'available',
      analysis_status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS assets_relative_path_idx
      ON assets(relative_path);
    CREATE INDEX IF NOT EXISTS assets_status_idx
      ON assets(file_status, analysis_status);
    CREATE INDEX IF NOT EXISTS assets_domain_idx
      ON assets(source_domain);
    CREATE INDEX IF NOT EXISTS assets_updated_idx
      ON assets(updated_at DESC);

    CREATE TABLE IF NOT EXISTS analyses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
      version INTEGER NOT NULL,
      provider TEXT NOT NULL,
      model TEXT,
      summary TEXT NOT NULL DEFAULT '',
      detail TEXT NOT NULL DEFAULT '',
      tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
      prompts_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(prompts_json)),
      analysis_json TEXT NOT NULL CHECK (json_valid(analysis_json)),
      raw_json TEXT CHECK (raw_json IS NULL OR json_valid(raw_json)),
      is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
      created_at TEXT NOT NULL,
      UNIQUE(asset_id, version)
    );

    CREATE UNIQUE INDEX IF NOT EXISTS analyses_one_current_idx
      ON analyses(asset_id)
      WHERE is_current = 1;
    CREATE INDEX IF NOT EXISTS analyses_asset_version_idx
      ON analyses(asset_id, version DESC);

    CREATE TABLE IF NOT EXISTS jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
      provider TEXT NOT NULL DEFAULT 'codex',
      state TEXT NOT NULL DEFAULT 'queued',
      attempts INTEGER NOT NULL DEFAULT 0,
      last_error TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      started_at TEXT,
      completed_at TEXT
    );

    CREATE INDEX IF NOT EXISTS jobs_state_created_idx
      ON jobs(state, created_at, id);
    CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active_asset_idx
      ON jobs(asset_id)
      WHERE state IN ('queued', 'processing', 'needs_setup');

    CREATE TABLE IF NOT EXISTS settings (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      data_json TEXT NOT NULL CHECK (json_valid(data_json)),
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS collections (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL COLLATE NOCASE UNIQUE,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS collection_items (
      collection_id INTEGER NOT NULL
        REFERENCES collections(id) ON DELETE CASCADE,
      asset_id INTEGER NOT NULL
        REFERENCES assets(id) ON DELETE CASCADE,
      added_at TEXT NOT NULL,
      PRIMARY KEY(collection_id, asset_id)
    );

    CREATE INDEX IF NOT EXISTS collection_items_asset_idx
      ON collection_items(asset_id, collection_id);

    CREATE VIRTUAL TABLE IF NOT EXISTS asset_search USING fts5(
      asset_id UNINDEXED,
      title,
      file_name,
      summary,
      detail,
      tags,
      prompts,
      tokenize = 'unicode61 remove_diacritics 2'
    );

    CREATE TRIGGER IF NOT EXISTS assets_delete_search
    AFTER DELETE ON assets
    BEGIN
      DELETE FROM asset_search WHERE asset_id = OLD.id;
    END;

    PRAGMA user_version = 1;
  `);

  db.prepare(`
    INSERT OR IGNORE INTO settings(id, data_json, updated_at)
    VALUES(1, ?, ?)
  `).run(JSON.stringify(DEFAULT_SETTINGS), currentTimestamp());

  function transaction(callback) {
    db.exec("BEGIN IMMEDIATE");
    try {
      const result = callback();
      db.exec("COMMIT");
      return result;
    } catch (error) {
      try {
        db.exec("ROLLBACK");
      } catch {
        // Preserve the original database error.
      }
      throw error;
    }
  }

  function requireAssetRow(assetId) {
    const id = positiveId(assetId, "assetId");
    const row = db.prepare("SELECT * FROM assets WHERE id = ?").get(id);
    if (!row) {
      throw new Error(`Asset not found: ${id}.`);
    }
    return row;
  }

  function requireJobRow(jobId) {
    const id = positiveId(jobId, "jobId");
    const row = db.prepare("SELECT * FROM jobs WHERE id = ?").get(id);
    if (!row) {
      throw new Error(`Job not found: ${id}.`);
    }
    return row;
  }

  function requireCollectionRow(collectionId) {
    const id = positiveId(collectionId, "collectionId");
    const row = db.prepare("SELECT * FROM collections WHERE id = ?").get(id);
    if (!row) {
      throw new Error(`Collection not found: ${id}.`);
    }
    return row;
  }

  function syncSearch(assetId) {
    const row = db
      .prepare(`
        SELECT
          a.id,
          a.title,
          a.file_name,
          an.summary,
          an.detail,
          an.tags_json,
          an.prompts_json
        FROM assets a
        LEFT JOIN analyses an
          ON an.asset_id = a.id
         AND an.is_current = 1
        WHERE a.id = ?
      `)
      .get(assetId);

    db.prepare("DELETE FROM asset_search WHERE asset_id = ?").run(assetId);
    if (!row) {
      return;
    }

    db.prepare(`
      INSERT INTO asset_search(
        asset_id,
        title,
        file_name,
        summary,
        detail,
        tags,
        prompts
      )
      VALUES(?, ?, ?, ?, ?, ?, ?)
    `).run(
      row.id,
      row.title ?? "",
      row.file_name ?? "",
      row.summary ?? "",
      row.detail ?? "",
      flattenText(jsonParse(row.tags_json, [])).join(" "),
      flattenText(jsonParse(row.prompts_json, [])).join(" "),
    );
  }

  function selectAssetById(assetId) {
    const id = positiveId(assetId, "assetId");
    return db.prepare(`${ASSET_SELECT} WHERE a.id = ?`).get(id);
  }

  function assetCollections(assetId) {
    return db
      .prepare(`
        SELECT c.id, c.name, c.created_at, c.updated_at
        FROM collections c
        INNER JOIN collection_items ci ON ci.collection_id = c.id
        WHERE ci.asset_id = ?
        ORDER BY c.name COLLATE NOCASE ASC
      `)
      .all(assetId)
      .map((row) => ({
        id: row.id,
        name: row.name,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
      }));
  }

  function getAsset(assetId) {
    const row = selectAssetById(assetId);
    if (!row) {
      return null;
    }
    return {
      ...assetFromRow(row),
      collections: assetCollections(row.id),
    };
  }

  function getAssetByRelativePath(relativePath) {
    const normalized = normalizeRelativePath(relativePath);
    const row = db
      .prepare(`
        ${ASSET_SELECT}
        WHERE a.relative_path = ? COLLATE NOCASE
        ORDER BY (a.file_status = 'available') DESC, a.updated_at DESC, a.id DESC
        LIMIT 1
      `)
      .get(normalized);
    if (!row) {
      return null;
    }
    return {
      ...assetFromRow(row),
      collections: assetCollections(row.id),
    };
  }

  function getStats() {
    const assets = db
      .prepare(`
        SELECT
          COUNT(*) AS total_assets,
          COALESCE(SUM(file_status = 'available'), 0) AS available_assets,
          COALESCE(SUM(file_status = 'missing'), 0) AS missing_assets,
          COALESCE(SUM(favorite = 1), 0) AS favorite_assets,
          COALESCE(SUM(analysis_status = 'complete'), 0) AS analyzed_assets,
          COALESCE(SUM(analysis_status = 'pending'), 0) AS pending_assets,
          COALESCE(SUM(analysis_status = 'queued'), 0) AS queued_assets,
          COALESCE(SUM(analysis_status = 'processing'), 0) AS processing_assets,
          COALESCE(SUM(analysis_status = 'failed'), 0) AS failed_assets,
          COALESCE(SUM(analysis_status = 'needs_setup'), 0) AS needs_setup_assets,
          COALESCE(SUM(file_size), 0) AS storage_bytes
        FROM assets
      `)
      .get();
    const jobs = db
      .prepare(`
        SELECT
          COALESCE(SUM(state = 'queued'), 0) AS queued_jobs,
          COALESCE(SUM(state = 'processing'), 0) AS processing_jobs,
          COALESCE(SUM(state = 'failed'), 0) AS failed_jobs,
          COALESCE(SUM(state = 'needs_setup'), 0) AS needs_setup_jobs
        FROM jobs
      `)
      .get();
    const collectionCount = db
      .prepare("SELECT COUNT(*) AS count FROM collections")
      .get().count;

    return {
      totalAssets: Number(assets.total_assets),
      availableAssets: Number(assets.available_assets),
      missingAssets: Number(assets.missing_assets),
      favoriteAssets: Number(assets.favorite_assets),
      analyzedAssets: Number(assets.analyzed_assets),
      pendingAssets: Number(assets.pending_assets),
      queuedAssets: Number(assets.queued_assets),
      processingAssets: Number(assets.processing_assets),
      failedAssets: Number(assets.failed_assets),
      needsSetupAssets: Number(assets.needs_setup_assets),
      storageBytes: Number(assets.storage_bytes),
      queuedJobs: Number(jobs.queued_jobs),
      processingJobs: Number(jobs.processing_jobs),
      failedJobs: Number(jobs.failed_jobs),
      needsSetupJobs: Number(jobs.needs_setup_jobs),
      collections: Number(collectionCount),
    };
  }

  function upsertAsset(record) {
    requirePlainObject(record, "record");
    const sha256 = normalizeSha256(pick(record, "sha256"));
    const relativePath = normalizeRelativePath(
      pick(record, "relativePath", "relative_path"),
    );
    const fileName =
      optionalString(pick(record, "fileName", "file_name"), "fileName", 512) ??
      relativePath.split("/").at(-1);
    const mimeType =
      optionalString(pick(record, "mimeType", "mime_type"), "mimeType", 255) ??
      "application/octet-stream";
    const dimensions = pick(record, "dimensions");
    const width = optionalPositiveInteger(
      pick(record, "width") ?? (isPlainObject(dimensions) ? dimensions.width : null),
      "width",
    );
    const height = optionalPositiveInteger(
      pick(record, "height") ??
        (isPlainObject(dimensions) ? dimensions.height : null),
      "height",
    );
    const fileSize = nonNegativeNumber(
      pick(record, "fileSize", "file_size"),
      "fileSize",
    );
    const mtimeMs = nonNegativeNumber(
      pick(record, "mtimeMs", "mtime_ms"),
      "mtimeMs",
    );
    const sourceUrl = optionalString(
      pick(record, "sourceUrl", "source_url"),
      "sourceUrl",
      8_192,
    );
    const rightsNote = optionalString(
      pick(record, "rightsNote", "rights_note"),
      "rightsNote",
      20_000,
    );
    const title =
      optionalString(pick(record, "title"), "title", 1_000) ?? "";
    const notes =
      optionalString(pick(record, "notes"), "notes", 100_000) ?? "";
    const now = currentTimestamp();

    return transaction(() => {
      const existing = db
        .prepare("SELECT * FROM assets WHERE sha256 = ?")
        .get(sha256);

      if (existing) {
        const isDuplicate =
          existing.relative_path.toLocaleLowerCase() !==
          relativePath.toLocaleLowerCase();
        db.prepare(`
          UPDATE assets
          SET file_status = 'missing',
              updated_at = ?
          WHERE relative_path = ? COLLATE NOCASE
            AND id <> ?
            AND file_status <> 'missing'
        `).run(now, relativePath, existing.id);

        db.prepare(`
          UPDATE assets
          SET relative_path = ?,
              file_name = ?,
              mime_type = ?,
              width = COALESCE(?, width),
              height = COALESCE(?, height),
              file_size = ?,
              mtime_ms = ?,
              file_status = 'available',
              updated_at = ?
          WHERE id = ?
        `).run(
          relativePath,
          fileName,
          mimeType,
          width,
          height,
          fileSize,
          mtimeMs,
          now,
          existing.id,
        );
        syncSearch(existing.id);
        return { asset: getAsset(existing.id), isNew: false, isDuplicate };
      }

      db.prepare(`
        UPDATE assets
        SET file_status = 'missing',
            updated_at = ?
        WHERE relative_path = ? COLLATE NOCASE
          AND file_status <> 'missing'
      `).run(now, relativePath);

      const result = db.prepare(`
        INSERT INTO assets(
          sha256,
          relative_path,
          file_name,
          mime_type,
          width,
          height,
          file_size,
          mtime_ms,
          source_url,
          source_domain,
          rights_note,
          title,
          notes,
          favorite,
          file_status,
          analysis_status,
          created_at,
          updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'available', 'pending', ?, ?)
      `).run(
        sha256,
        relativePath,
        fileName,
        mimeType,
        width,
        height,
        fileSize,
        mtimeMs,
        sourceUrl,
        sourceDomain(sourceUrl),
        rightsNote,
        title,
        notes,
        now,
        now,
      );
      const id = Number(result.lastInsertRowid);
      syncSearch(id);
      return { asset: getAsset(id), isNew: true, isDuplicate: false };
    });
  }

  function markMissingExcept(relativePaths) {
    if (!Array.isArray(relativePaths)) {
      throw new TypeError("relativePaths must be an array.");
    }
    const normalizedPaths = [
      ...new Set(relativePaths.map((value) => normalizeRelativePath(value))),
    ];
    const now = currentTimestamp();

    return transaction(() => {
      db.exec(`
        CREATE TEMP TABLE IF NOT EXISTS current_scan_paths (
          relative_path TEXT PRIMARY KEY COLLATE NOCASE
        );
        DELETE FROM current_scan_paths;
      `);
      const insertPath = db.prepare(`
        INSERT OR IGNORE INTO current_scan_paths(relative_path)
        VALUES(?)
      `);
      for (const relativePath of normalizedPaths) {
        insertPath.run(relativePath);
      }
      const result = db.prepare(`
        UPDATE assets
        SET file_status = 'missing',
            updated_at = ?
        WHERE file_status <> 'missing'
          AND NOT EXISTS (
            SELECT 1
            FROM current_scan_paths scan
            WHERE scan.relative_path = assets.relative_path COLLATE NOCASE
          )
      `).run(now);
      return { markedMissing: Number(result.changes) };
    });
  }

  function listAssets(filters = {}) {
    requirePlainObject(filters, "filters");
    const limit = paginationInteger(filters.limit, DEFAULT_LIMIT, MAX_LIMIT);
    const offset = paginationInteger(filters.offset, 0);
    const where = [];
    const parameters = [];
    const ftsQuery = safeFtsQuery(filters.query);

    if (ftsQuery === "") {
      where.push("0 = 1");
    } else if (ftsQuery !== null) {
      where.push(`
        EXISTS (
          SELECT 1
          FROM asset_search
          WHERE asset_search.asset_id = a.id
            AND asset_search MATCH ?
        )
      `);
      parameters.push(ftsQuery);
    }

    const statuses = normalizeFilterList(filters.status);
    if (statuses.length > 0) {
      const statusPlaceholders = placeholders(statuses.length);
      where.push(`(
        a.analysis_status IN (${statusPlaceholders})
        OR a.file_status IN (${statusPlaceholders})
      )`);
      parameters.push(...statuses, ...statuses);
    }

    const analysisStatuses = normalizeFilterList(
      pick(filters, "analysisStatus", "analysis_status"),
    );
    if (analysisStatuses.length > 0) {
      where.push(`a.analysis_status IN (${placeholders(analysisStatuses.length)})`);
      parameters.push(...analysisStatuses);
    }

    const fileStatuses = normalizeFilterList(
      pick(filters, "fileStatus", "file_status"),
    );
    if (fileStatuses.length > 0) {
      where.push(`a.file_status IN (${placeholders(fileStatuses.length)})`);
      parameters.push(...fileStatuses);
    }

    const domains = normalizeFilterList(filters.domain).map((value) =>
      value.toLowerCase().replace(/^www\./, ""),
    );
    if (domains.length > 0) {
      where.push(`LOWER(a.source_domain) IN (${placeholders(domains.length)})`);
      parameters.push(...domains);
    }

    if (filters.favorite !== undefined && filters.favorite !== null && filters.favorite !== "") {
      where.push("a.favorite = ?");
      parameters.push(booleanValue(filters.favorite, "favorite") ? 1 : 0);
    }

    if (
      filters.collectionId !== undefined &&
      filters.collectionId !== null &&
      filters.collectionId !== ""
    ) {
      const collectionId = positiveId(filters.collectionId, "collectionId");
      where.push(`
        EXISTS (
          SELECT 1
          FROM collection_items ci
          WHERE ci.asset_id = a.id
            AND ci.collection_id = ?
        )
      `);
      parameters.push(collectionId);
    }

    const whereSql = where.length > 0 ? `WHERE ${where.join(" AND ")}` : "";
    const sortMap = {
      newest: "a.created_at DESC, a.id DESC",
      oldest: "a.created_at ASC, a.id ASC",
      updated: "a.updated_at DESC, a.id DESC",
      name: "a.file_name COLLATE NOCASE ASC, a.id ASC",
      name_desc: "a.file_name COLLATE NOCASE DESC, a.id DESC",
      size: "a.file_size DESC, a.id DESC",
      size_asc: "a.file_size ASC, a.id ASC",
      favorite: "a.favorite DESC, a.updated_at DESC, a.id DESC",
      modified: "a.mtime_ms DESC, a.id DESC",
    };
    const sort = sortMap[filters.sort] ?? sortMap.updated;
    const total = db
      .prepare(`SELECT COUNT(*) AS count FROM assets a ${whereSql}`)
      .get(...parameters).count;
    const rows = db
      .prepare(`
        ${ASSET_SELECT}
        ${whereSql}
        ORDER BY ${sort}
        LIMIT ? OFFSET ?
      `)
      .all(...parameters, limit, offset);

    return {
      items: rows.map(assetFromRow),
      total: Number(total),
      limit,
      offset,
    };
  }

  function updateAsset(assetId, patch) {
    const id = positiveId(assetId, "assetId");
    requireAssetRow(id);
    requirePlainObject(patch, "patch");
    const assignments = [];
    const parameters = [];

    if (Object.hasOwn(patch, "title")) {
      assignments.push("title = ?");
      parameters.push(optionalString(patch.title, "title", 1_000) ?? "");
    }
    if (Object.hasOwn(patch, "notes")) {
      assignments.push("notes = ?");
      parameters.push(optionalString(patch.notes, "notes", 100_000) ?? "");
    }
    if (Object.hasOwn(patch, "favorite")) {
      assignments.push("favorite = ?");
      parameters.push(booleanValue(patch.favorite, "favorite") ? 1 : 0);
    }

    const hasSourceUrl =
      Object.hasOwn(patch, "sourceUrl") || Object.hasOwn(patch, "source_url");
    if (hasSourceUrl) {
      const sourceUrl = optionalString(
        pick(patch, "sourceUrl", "source_url"),
        "sourceUrl",
        8_192,
      );
      assignments.push("source_url = ?", "source_domain = ?");
      parameters.push(sourceUrl, sourceDomain(sourceUrl));
    }

    const hasRightsNote =
      Object.hasOwn(patch, "rightsNote") || Object.hasOwn(patch, "rights_note");
    if (hasRightsNote) {
      assignments.push("rights_note = ?");
      parameters.push(
        optionalString(
          pick(patch, "rightsNote", "rights_note"),
          "rightsNote",
          20_000,
        ),
      );
    }

    if (assignments.length === 0) {
      return getAsset(id);
    }

    assignments.push("updated_at = ?");
    parameters.push(currentTimestamp(), id);
    db.prepare(`
      UPDATE assets
      SET ${assignments.join(", ")}
      WHERE id = ?
    `).run(...parameters);
    syncSearch(id);
    return getAsset(id);
  }

  function setFavorite(assetId, value) {
    const id = positiveId(assetId, "assetId");
    requireAssetRow(id);
    const favorite = booleanValue(value, "value");
    db.prepare(`
      UPDATE assets
      SET favorite = ?,
          updated_at = ?
      WHERE id = ?
    `).run(favorite ? 1 : 0, currentTimestamp(), id);
    return getAsset(id);
  }

  function saveAnalysis(
    assetId,
    { provider = "codex", model = null, analysis, raw = null } = {},
  ) {
    const id = positiveId(assetId, "assetId");
    requireAssetRow(id);
    const normalizedProvider = requiredString(provider, "provider", 100);
    const normalizedModel = optionalString(model, "model", 500);
    requirePlainObject(analysis, "analysis");
    const analysisJson = jsonStringify(analysis, "analysis");
    const rawJson = raw === undefined || raw === null ? null : jsonStringify(raw, "raw");
    const fields = analysisSearchFields(analysis);
    const tagsJson = jsonStringify(fields.tags, "analysis tags");
    const promptsJson = jsonStringify(fields.prompts, "analysis prompts");
    const now = currentTimestamp();

    const analysisId = transaction(() => {
      const version =
        Number(
          db
            .prepare(`
              SELECT COALESCE(MAX(version), 0) + 1 AS version
              FROM analyses
              WHERE asset_id = ?
            `)
            .get(id).version,
        ) || 1;
      db.prepare(`
        UPDATE analyses
        SET is_current = 0
        WHERE asset_id = ?
          AND is_current = 1
      `).run(id);
      const result = db.prepare(`
        INSERT INTO analyses(
          asset_id,
          version,
          provider,
          model,
          summary,
          detail,
          tags_json,
          prompts_json,
          analysis_json,
          raw_json,
          is_current,
          created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
      `).run(
        id,
        version,
        normalizedProvider,
        normalizedModel,
        fields.summary,
        fields.detail,
        tagsJson,
        promptsJson,
        analysisJson,
        rawJson,
        now,
      );
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'complete',
            updated_at = ?
        WHERE id = ?
      `).run(now, id);
      syncSearch(id);
      return Number(result.lastInsertRowid);
    });

    const row = db
      .prepare(`
        SELECT
          id AS analysis_id,
          version AS analysis_version,
          provider AS analysis_provider,
          model AS analysis_model,
          summary AS analysis_summary,
          detail AS analysis_detail,
          tags_json AS analysis_tags_json,
          prompts_json AS analysis_prompts_json,
          analysis_json,
          raw_json AS analysis_raw_json,
          created_at AS analysis_created_at
        FROM analyses
        WHERE id = ?
      `)
      .get(analysisId);
    return analysisFromRow(row);
  }

  function enqueueAnalysis(assetId, provider = "codex") {
    const asset = requireAssetRow(assetId);
    if (asset.file_status !== "available") {
      throw new Error(`Cannot enqueue missing asset: ${asset.id}.`);
    }
    const normalizedProvider = requiredString(provider, "provider", 100);
    const existing = db
      .prepare(`
        SELECT *
        FROM jobs
        WHERE asset_id = ?
          AND state IN ('queued', 'processing', 'needs_setup')
        ORDER BY id DESC
        LIMIT 1
      `)
      .get(asset.id);
    if (existing) {
      return jobFromRow(existing);
    }

    const now = currentTimestamp();
    const result = transaction(() => {
      const insert = db.prepare(`
        INSERT INTO jobs(
          asset_id,
          provider,
          state,
          attempts,
          created_at,
          updated_at
        )
        VALUES(?, ?, 'queued', 0, ?, ?)
      `).run(asset.id, normalizedProvider, now, now);
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'queued',
            updated_at = ?
        WHERE id = ?
      `).run(now, asset.id);
      return Number(insert.lastInsertRowid);
    });
    return jobFromRow(db.prepare("SELECT * FROM jobs WHERE id = ?").get(result));
  }

  function claimNextJob() {
    const job = transaction(() => {
      const queued = db
        .prepare(`
          SELECT j.*
          FROM jobs j
          INNER JOIN assets a ON a.id = j.asset_id
          WHERE j.state = 'queued'
            AND a.file_status = 'available'
          ORDER BY j.created_at ASC, j.id ASC
          LIMIT 1
        `)
        .get();
      if (!queued) {
        return null;
      }
      const now = currentTimestamp();
      const claimed = db.prepare(`
        UPDATE jobs
        SET state = 'processing',
            attempts = attempts + 1,
            last_error = NULL,
            started_at = ?,
            completed_at = NULL,
            updated_at = ?
        WHERE id = ?
          AND state = 'queued'
      `).run(now, now, queued.id);
      if (Number(claimed.changes) !== 1) {
        return null;
      }
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'processing',
            updated_at = ?
        WHERE id = ?
      `).run(now, queued.asset_id);
      return db.prepare("SELECT * FROM jobs WHERE id = ?").get(queued.id);
    });

    if (!job) {
      return null;
    }
    return {
      ...jobFromRow(job),
      asset: getAsset(job.asset_id),
    };
  }

  function completeJob(jobId) {
    const job = requireJobRow(jobId);
    if (job.state === "completed") {
      return jobFromRow(job);
    }
    if (job.state !== "processing") {
      throw new Error(`Job ${job.id} is not processing.`);
    }
    const now = currentTimestamp();
    transaction(() => {
      db.prepare(`
        UPDATE jobs
        SET state = 'completed',
            last_error = NULL,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
      `).run(now, now, job.id);
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'complete',
            updated_at = ?
        WHERE id = ?
      `).run(now, job.asset_id);
    });
    return jobFromRow(db.prepare("SELECT * FROM jobs WHERE id = ?").get(job.id));
  }

  function failJob(jobId, state, error) {
    const job = requireJobRow(jobId);
    if (!FAILURE_STATES.has(state)) {
      throw new TypeError("state must be either 'failed' or 'needs_setup'.");
    }
    const message =
      optionalString(
        error instanceof Error ? error.message : error,
        "error",
        20_000,
      ) ?? "Analysis failed without an error message.";
    const now = currentTimestamp();
    transaction(() => {
      db.prepare(`
        UPDATE jobs
        SET state = ?,
            last_error = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
      `).run(state, message, state === "failed" ? now : null, now, job.id);
      db.prepare(`
        UPDATE assets
        SET analysis_status = ?,
            updated_at = ?
        WHERE id = ?
      `).run(state, now, job.asset_id);
    });
    return jobFromRow(db.prepare("SELECT * FROM jobs WHERE id = ?").get(job.id));
  }

  function listJobs(filters = {}) {
    requirePlainObject(filters, "filters");
    const limit = paginationInteger(filters.limit, DEFAULT_LIMIT, MAX_LIMIT);
    const offset = paginationInteger(filters.offset, 0);
    const where = [];
    const parameters = [];
    const states = normalizeFilterList(filters.state);
    if (states.length > 0) {
      for (const state of states) {
        if (!JOB_STATES.has(state)) {
          throw new TypeError(`Unknown job state: ${state}.`);
        }
      }
      where.push(`j.state IN (${placeholders(states.length)})`);
      parameters.push(...states);
    }
    const providers = normalizeFilterList(filters.provider);
    if (providers.length > 0) {
      where.push(`j.provider IN (${placeholders(providers.length)})`);
      parameters.push(...providers);
    }
    if (filters.assetId !== undefined && filters.assetId !== null && filters.assetId !== "") {
      where.push("j.asset_id = ?");
      parameters.push(positiveId(filters.assetId, "assetId"));
    }
    const whereSql = where.length > 0 ? `WHERE ${where.join(" AND ")}` : "";
    const sortMap = {
      oldest: "j.created_at ASC, j.id ASC",
      newest: "j.created_at DESC, j.id DESC",
      updated: "j.updated_at DESC, j.id DESC",
    };
    const sort = sortMap[filters.sort] ?? sortMap.newest;
    const total = db
      .prepare(`SELECT COUNT(*) AS count FROM jobs j ${whereSql}`)
      .get(...parameters).count;
    const rows = db
      .prepare(`
        SELECT
          j.*,
          a.file_name,
          a.relative_path,
          a.title,
          a.mime_type,
          a.file_status,
          a.analysis_status
        FROM jobs j
        INNER JOIN assets a ON a.id = j.asset_id
        ${whereSql}
        ORDER BY ${sort}
        LIMIT ? OFFSET ?
      `)
      .all(...parameters, limit, offset);
    return {
      items: rows.map(jobFromRow),
      total: Number(total),
      limit,
      offset,
    };
  }

  function retryJob(jobId) {
    const job = requireJobRow(jobId);
    if (job.state !== "failed" && job.state !== "needs_setup") {
      throw new Error(`Job ${job.id} is not retryable from state '${job.state}'.`);
    }
    const asset = requireAssetRow(job.asset_id);
    if (asset.file_status !== "available") {
      throw new Error(`Cannot retry job for missing asset: ${asset.id}.`);
    }
    const now = currentTimestamp();
    transaction(() => {
      db.prepare(`
        UPDATE jobs
        SET state = 'queued',
            last_error = NULL,
            started_at = NULL,
            completed_at = NULL,
            updated_at = ?
        WHERE id = ?
      `).run(now, job.id);
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'queued',
            updated_at = ?
        WHERE id = ?
      `).run(now, job.asset_id);
    });
    return jobFromRow(db.prepare("SELECT * FROM jobs WHERE id = ?").get(job.id));
  }

  function retryNeedsSetup() {
    const now = currentTimestamp();
    return transaction(() => {
      db.prepare(`
        UPDATE assets
        SET analysis_status = 'queued',
            updated_at = ?
        WHERE id IN (
          SELECT asset_id
          FROM jobs
          WHERE state = 'needs_setup'
        )
          AND file_status = 'available'
      `).run(now);
      const result = db.prepare(`
        UPDATE jobs
        SET state = 'queued',
            last_error = NULL,
            started_at = NULL,
            completed_at = NULL,
            updated_at = ?
        WHERE state = 'needs_setup'
          AND asset_id IN (
            SELECT id
            FROM assets
            WHERE file_status = 'available'
          )
      `).run(now);
      return Number(result.changes);
    });
  }

  function getSettings() {
    const row = db.prepare("SELECT data_json FROM settings WHERE id = 1").get();
    return {
      ...DEFAULT_SETTINGS,
      ...jsonParse(row?.data_json, {}),
    };
  }

  function updateSettings(patch) {
    requirePlainObject(patch, "patch");
    for (const key of Object.keys(patch)) {
      if (/(api.?key|token|secret|password|credential)/i.test(key)) {
        throw new Error(`Sensitive setting '${key}' cannot be stored in SQLite.`);
      }
    }
    if (Object.hasOwn(patch, "provider") && patch.provider !== "codex") {
      throw new TypeError("provider must be 'codex'.");
    }
    if (Object.hasOwn(patch, "autoAnalyze")) {
      booleanValue(patch.autoAnalyze, "autoAnalyze");
    }
    if (
      Object.hasOwn(patch, "codexExecutable") &&
      patch.codexExecutable !== null
    ) {
      optionalString(patch.codexExecutable, "codexExecutable", 4_096);
    }
    if (Object.hasOwn(patch, "codexModel") && patch.codexModel !== null) {
      optionalString(patch.codexModel, "codexModel", 500);
    }
    if (
      Object.hasOwn(patch, "agentSandbox") &&
      patch.agentSandbox !== "read-only"
    ) {
      throw new TypeError("agentSandbox must remain 'read-only'.");
    }
    if (
      Object.hasOwn(patch, "concurrency") &&
      Number(patch.concurrency) !== 1
    ) {
      throw new TypeError("concurrency must remain 1.");
    }

    const normalizedPatch = { ...patch };
    if (Object.hasOwn(normalizedPatch, "autoAnalyze")) {
      normalizedPatch.autoAnalyze = booleanValue(
        normalizedPatch.autoAnalyze,
        "autoAnalyze",
      );
    }
    if (Object.hasOwn(normalizedPatch, "codexExecutable")) {
      normalizedPatch.codexExecutable = optionalString(
        normalizedPatch.codexExecutable,
        "codexExecutable",
        4_096,
      );
    }
    if (Object.hasOwn(normalizedPatch, "codexModel")) {
      normalizedPatch.codexModel = optionalString(
        normalizedPatch.codexModel,
        "codexModel",
        500,
      );
    }
    if (Object.hasOwn(normalizedPatch, "concurrency")) {
      normalizedPatch.concurrency = 1;
    }

    const settings = {
      ...getSettings(),
      ...normalizedPatch,
      provider: "codex",
      agentSandbox: "read-only",
      concurrency: 1,
    };
    db.prepare(`
      UPDATE settings
      SET data_json = ?,
          updated_at = ?
      WHERE id = 1
    `).run(jsonStringify(settings, "settings"), currentTimestamp());
    return settings;
  }

  function listCollections() {
    return db
      .prepare(`
        SELECT
          c.id,
          c.name,
          c.created_at,
          c.updated_at,
          COUNT(ci.asset_id) AS item_count
        FROM collections c
        LEFT JOIN collection_items ci ON ci.collection_id = c.id
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE ASC
      `)
      .all()
      .map(collectionFromRow);
  }

  function createCollection(name) {
    const normalizedName = requiredString(name, "name", 120);
    const now = currentTimestamp();
    try {
      const result = db.prepare(`
        INSERT INTO collections(name, created_at, updated_at)
        VALUES(?, ?, ?)
      `).run(normalizedName, now, now);
      return collectionFromRow(
        db
          .prepare(`
            SELECT id, name, created_at, updated_at, 0 AS item_count
            FROM collections
            WHERE id = ?
          `)
          .get(Number(result.lastInsertRowid)),
      );
    } catch (error) {
      if (
        error?.code === "ERR_SQLITE_ERROR" &&
        /UNIQUE constraint failed: collections\.name/i.test(error.message)
      ) {
        throw new Error(`Collection already exists: ${normalizedName}.`, {
          cause: error,
        });
      }
      throw error;
    }
  }

  function getCollection(collectionId) {
    const id = positiveId(collectionId, "collectionId");
    const collection = db
      .prepare("SELECT * FROM collections WHERE id = ?")
      .get(id);
    if (!collection) {
      return null;
    }
    const rows = db
      .prepare(`
        ${ASSET_SELECT}
        INNER JOIN collection_items ci ON ci.asset_id = a.id
        WHERE ci.collection_id = ?
        ORDER BY ci.added_at DESC, a.id DESC
      `)
      .all(collection.id);
    return {
      id: collection.id,
      name: collection.name,
      itemCount: rows.length,
      createdAt: collection.created_at,
      updatedAt: collection.updated_at,
      items: rows.map(assetFromRow),
    };
  }

  function addCollectionItem(collectionId, assetId) {
    const collection = requireCollectionRow(collectionId);
    const asset = requireAssetRow(assetId);
    const now = currentTimestamp();
    transaction(() => {
      db.prepare(`
        INSERT OR IGNORE INTO collection_items(collection_id, asset_id, added_at)
        VALUES(?, ?, ?)
      `).run(collection.id, asset.id, now);
      db.prepare(`
        UPDATE collections
        SET updated_at = ?
        WHERE id = ?
      `).run(now, collection.id);
    });
    return getCollection(collection.id);
  }

  function removeCollectionItem(collectionId, assetId) {
    const collection = requireCollectionRow(collectionId);
    const asset = requireAssetRow(assetId);
    const now = currentTimestamp();
    const result = transaction(() => {
      const deleted = db.prepare(`
        DELETE FROM collection_items
        WHERE collection_id = ?
          AND asset_id = ?
      `).run(collection.id, asset.id);
      if (Number(deleted.changes) > 0) {
        db.prepare(`
          UPDATE collections
          SET updated_at = ?
          WHERE id = ?
        `).run(now, collection.id);
      }
      return Number(deleted.changes);
    });
    return { removed: result > 0, collection: getCollection(collection.id) };
  }

  function getFacets() {
    const analysisStatuses = db
      .prepare(`
        SELECT analysis_status AS value, COUNT(*) AS count
        FROM assets
        GROUP BY analysis_status
        ORDER BY count DESC, value ASC
      `)
      .all()
      .map((row) => ({ value: row.value, count: Number(row.count) }));
    const fileStatuses = db
      .prepare(`
        SELECT file_status AS value, COUNT(*) AS count
        FROM assets
        GROUP BY file_status
        ORDER BY count DESC, value ASC
      `)
      .all()
      .map((row) => ({ value: row.value, count: Number(row.count) }));
    const domains = db
      .prepare(`
        SELECT source_domain AS value, COUNT(*) AS count
        FROM assets
        WHERE source_domain IS NOT NULL
          AND source_domain <> ''
        GROUP BY source_domain
        ORDER BY count DESC, value COLLATE NOCASE ASC
      `)
      .all()
      .map((row) => ({ value: row.value, count: Number(row.count) }));
    const tagCounts = new Map();
    const tagRows = db
      .prepare(`
        SELECT tags_json
        FROM analyses
        WHERE is_current = 1
      `)
      .all();
    for (const row of tagRows) {
      const tags = [
        ...new Set(flattenText(jsonParse(row.tags_json, [])).map((tag) => tag.trim())),
      ].filter(Boolean);
      for (const tag of tags) {
        tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1);
      }
    }
    const tags = [...tagCounts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((left, right) => right.count - left.count || left.value.localeCompare(right.value));

    return {
      analysisStatuses,
      fileStatuses,
      domains,
      tags,
      collections: listCollections(),
    };
  }

  function close() {
    if (!closed) {
      db.close();
      closed = true;
    }
  }

  return Object.freeze({
    close,
    getStats,
    upsertAsset,
    markMissingExcept,
    listAssets,
    getAsset,
    getAssetByRelativePath,
    updateAsset,
    setFavorite,
    saveAnalysis,
    enqueueAnalysis,
    claimNextJob,
    completeJob,
    failJob,
    listJobs,
    retryJob,
    retryNeedsSetup,
    getSettings,
    updateSettings,
    listCollections,
    createCollection,
    getCollection,
    addCollectionItem,
    removeCollectionItem,
    getFacets,
  });
}
