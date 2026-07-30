import { beginPendingButtons } from "./button-state.js";
import {
  renderSwatchColor,
  safeHexColor as safeColor,
} from "./palette-swatch.js";

const state = {
  loading: true,
  error: null,
  assets: [],
  resultTotal: 0,
  libraryTotal: 0,
  stats: {},
  jobs: [],
  settings: {},
  provider: null,
  collections: [],
  paths: {},
  view: "library",
  activeCollectionId: null,
  selectedId: null,
  selectedIds: new Set(),
  lastAnchorId: null,
  query: "",
  discipline: "",
  status: "",
  sort: "newest",
  queueExpanded: false,
  searchTimer: null,
  pollTimer: null,
  syntheticAssets: [],
  inspectorReturnFocus: null,
  inspectorReturnAssetId: null,
};

const elements = {
  app: document.querySelector("#app"),
  workspace: document.querySelector("#workspace"),
  gallery: document.querySelector("#gallery"),
  collectionOverview: document.querySelector("#collection-overview"),
  collectionTable: document.querySelector("#collection-table"),
  loadingState: document.querySelector("#loading-state"),
  errorState: document.querySelector("#error-state"),
  errorMessage: document.querySelector("#error-message"),
  setupNotice: document.querySelector("#setup-notice"),
  inspector: document.querySelector("#inspector"),
  inspectorEmpty: document.querySelector("#inspector-empty"),
  inspectorContent: document.querySelector("#inspector-content"),
  resultSummary: document.querySelector("#result-summary"),
  viewTitle: document.querySelector("#view-title"),
  viewKicker: document.querySelector("#view-kicker"),
  searchForm: document.querySelector("#search-form"),
  searchInput: document.querySelector("#search-input"),
  disciplineFilter: document.querySelector("#discipline-filter"),
  statusFilter: document.querySelector("#status-filter"),
  sortSelect: document.querySelector("#sort-select"),
  clearFiltersButton: document.querySelector("#clear-filters-button"),
  importButton: document.querySelector("#import-button"),
  fileInput: document.querySelector("#file-input"),
  scanButton: document.querySelector("#scan-button"),
  recognizeButton: document.querySelector("#recognize-button"),
  retryLoadButton: document.querySelector("#retry-load-button"),
  primaryNav: document.querySelector("#primary-nav"),
  collectionNav: document.querySelector("#collection-nav"),
  newCollectionButton: document.querySelector("#new-collection-button"),
  collectionDialog: document.querySelector("#collection-dialog"),
  collectionForm: document.querySelector("#collection-form"),
  collectionName: document.querySelector("#collection-name"),
  settingsDialog: document.querySelector("#settings-dialog"),
  settingsForm: document.querySelector("#settings-form"),
  settingInboxPath: document.querySelector("#setting-inbox-path"),
  settingCodexModel: document.querySelector("#setting-codex-model"),
  codexReadiness: document.querySelector("#codex-readiness"),
  codexExecutionMode: document.querySelector("#codex-execution-mode"),
  codexPromptVersion: document.querySelector("#codex-prompt-version"),
  providerLedger: document.querySelector("#provider-ledger"),
  settingsStatusDot: document.querySelector("#settings-status-dot"),
  railStatus: document.querySelector("#rail-status"),
  countLibrary: document.querySelector("#count-library"),
  countInbox: document.querySelector("#count-inbox"),
  countCollections: document.querySelector("#count-collections"),
  countQueue: document.querySelector("#count-queue"),
  batchBar: document.querySelector("#batch-bar"),
  batchCount: document.querySelector("#batch-count"),
  batchAnalyzeButton: document.querySelector("#batch-analyze-button"),
  clearSelectionButton: document.querySelector("#clear-selection-button"),
  queueBar: document.querySelector("#queue-bar"),
  queueToggle: document.querySelector("#queue-toggle"),
  queueTrack: document.querySelector("#queue-track"),
  queueActiveCount: document.querySelector("#queue-active-count"),
  queueSummaryText: document.querySelector("#queue-summary-text"),
  retryNeedsSetupButton: document.querySelector("#retry-needs-setup-button"),
  liveRegion: document.querySelector("#live-region"),
};

const STATUS_LABELS = {
  discovered: "已偵測",
  imported: "已匯入",
  hashing: "建立索引",
  queued: "等待 Codex",
  pending: "等待 Codex",
  running: "Codex 辨識中",
  processing: "Codex 辨識中",
  analyzing: "Codex 辨識中",
  ready: "分析完成",
  complete: "分析完成",
  completed: "分析完成",
  needs_review: "待確認",
  needs_setup: "Codex 未就緒",
  failed: "分析失敗",
  missing: "原檔遺失",
  stale_analysis: "需更新",
  duplicate: "重複影像",
  synthetic: "合成示意",
};

const DNA_LABELS = {
  discipline: "領域",
  category: "類型",
  artifact: "產物",
  surface: "介面",
  style: "風格",
  lineage: "設計譜系",
  composition: "構圖",
  layout: "版面",
  grid: "網格",
  density: "密度",
  hierarchy: "層級",
  typography: "字體",
  color: "色彩",
  imagery: "影像",
  material: "材質",
  mood: "情緒",
  era: "年代",
  interaction: "互動",
};

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeMediaUrl(value) {
  const url = String(value ?? "").trim();
  if (
    url.startsWith("/") ||
    url.startsWith("data:image/") ||
    url.startsWith("blob:") ||
    url.startsWith("http://127.0.0.1") ||
    url.startsWith("http://localhost")
  ) {
    return url;
  }
  return "";
}

function parseMaybeJson(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (!trimmed || (!trimmed.startsWith("{") && !trimmed.startsWith("["))) {
    return value;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return value;
  }
}

function asObject(value) {
  const parsed = parseMaybeJson(value);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? parsed
    : {};
}

function asArray(value) {
  const parsed = parseMaybeJson(value);
  if (Array.isArray(parsed)) return parsed;
  if (parsed === undefined || parsed === null || parsed === "") return [];
  return [parsed];
}

function listFrom(payload, keys = []) {
  if (Array.isArray(payload)) return payload;
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

function finiteNumber(...values) {
  for (const value of values) {
    const number = Number(value);
    if (Number.isFinite(number)) return number;
  }
  return null;
}

function stripExtension(name) {
  return String(name || "").replace(/\.[^.]+$/, "");
}

function fileNameFromPath(value) {
  const parts = String(value || "").split(/[\\/]/);
  return parts.at(-1) || "";
}

function normalizeAsset(raw) {
  const asset = asObject(raw);
  const relativePath =
    asset.relativePath || asset.relative_path || asset.path || asset.filePath || "";
  const fileName =
    asset.fileName ||
    asset.filename ||
    asset.originalName ||
    fileNameFromPath(relativePath) ||
    `asset-${asset.id || ""}`;
  const width = finiteNumber(asset.width, asset.pixelWidth, asset.dimensions?.width);
  const height = finiteNumber(
    asset.height,
    asset.pixelHeight,
    asset.dimensions?.height,
  );
  const status =
    asset.analysisStatus ||
    asset.analysis_state ||
    asset.status ||
    asset.jobStatus ||
    (asset.analysis || asset.latestAnalysis ? "ready" : "discovered");

  return {
    ...asset,
    id: String(asset.id ?? asset.assetId ?? relativePath ?? ""),
    title: String(asset.title || stripExtension(fileName) || "未命名影像"),
    fileName,
    relativePath,
    mediaUrl: safeMediaUrl(asset.mediaUrl || asset.url || asset.thumbnailUrl),
    width,
    height,
    mimeType: asset.mimeType || asset.type || "",
    fileSize: finiteNumber(asset.fileSize, asset.size, asset.bytes),
    status: String(status || "discovered"),
    createdAt:
      asset.createdAt ||
      asset.created_at ||
      asset.importedAt ||
      asset.addedAt ||
      "",
    sourceUrl: asset.sourceUrl || asset.source_url || "",
    rightsNote: asset.rightsNote || asset.rights_note || "",
    notes: asset.notes || "",
    favorite: Boolean(asset.favorite),
    collectionIds: asArray(
      asset.collectionIds || asset.collection_ids || asset.collections,
    ).map((item) => String(item?.id ?? item)),
    hash: asset.sha256 || asset.hash || "",
    synthetic: Boolean(asset.synthetic),
  };
}

function normalizeCollection(raw) {
  const collection = asObject(raw);
  return {
    ...collection,
    id: String(collection.id ?? collection.collectionId ?? ""),
    name: String(collection.name || collection.title || "未命名收藏集"),
    itemCount:
      finiteNumber(
        collection.itemCount,
        collection.item_count,
        collection.count,
        collection.total,
      ) ?? asArray(collection.items).length,
  };
}

function normalizeJob(raw) {
  const job = asObject(raw);
  return {
    ...job,
    id: String(job.id ?? job.jobId ?? ""),
    assetId: String(job.assetId ?? job.asset_id ?? ""),
    status: String(job.state || job.status || "queued"),
    stage: String(job.stage || job.step || ""),
    progress: finiteNumber(job.progress, job.percent, job.percentage),
    error: String(
      job.error || job.errorMessage || job.lastError || job.last_error || job.message || "",
    ),
    createdAt: job.createdAt || job.created_at || "",
  };
}

function analysisRecord(asset) {
  const latest = asObject(
    asset.currentAnalysis ||
      asset.current_analysis ||
      asset.latestAnalysis ||
      asset.latest_analysis ||
      asset.analysisRecord,
  );
  let analysis =
    asset.analysis ??
    asset.analysisData ??
    asset.analysis_data ??
    latest.analysis ??
    latest.data ??
    {};
  analysis = parseMaybeJson(analysis);
  if (asObject(analysis).analysis) analysis = asObject(analysis).analysis;
  return {
    record: latest,
    data: asObject(analysis),
  };
}

function normalizePalette(value) {
  return asArray(value)
    .map((item) => {
      if (typeof item === "string") return { hex: safeColor(item), name: "" };
      const object = asObject(item);
      return {
        hex: safeColor(object.hex || object.value || object.color),
        name: String(object.name || object.role || ""),
      };
    })
    .slice(0, 8);
}

function readableValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => readableValue(item)).filter(Boolean).join("、");
  }
  if (value && typeof value === "object") {
    return Object.values(value)
      .map((item) => readableValue(item))
      .filter(Boolean)
      .join("、");
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value ?? "").trim();
}

function normalizedAnalysis(asset) {
  const { record, data } = analysisRecord(asset);
  const coreVisualDna = asObject(
    data.visualDna ||
      data.visualDNA ||
      data.visual_dna ||
      data.classification ||
      data.styleProfile,
  );
  const visualDna = {
    discipline: data.designDomains || data.design_domains,
    artifact: data.artifactTypes || data.artifact_types,
    ...coreVisualDna,
    typography: data.typography,
    color: data.color
      ? [
          data.color.mode,
          data.color.temperature,
          data.color.saturation,
          data.color.contrast,
        ]
      : undefined,
    imagery: data.imagery,
    material: data.materials,
    interaction: data.interactionSignals || data.interaction_signals,
  };
  const prompts = asObject(
    data.promptKit || data.prompt_kit || data.prompts || data.prompt,
  );
  const description = readableValue(
    data.detailedDescription ||
      data.detailed_description ||
      data.description ||
      data.summary ||
      data.visualDescription ||
      data.visual_description ||
      data.caption,
  );
  const palette = normalizePalette(
    data.palette ||
      data.colors ||
      data.colorPalette ||
      data.color_palette ||
      data.color?.palette ||
      visualDna.palette,
  );
  const whyItWorks = asArray(
    data.whyItWorks ||
      data.why_it_works ||
      data.strengths ||
      data.designRationale,
  )
    .map(readableValue)
    .filter(Boolean);
  const recipe = asArray(
    data.implementationRecipe ||
      data.implementation_recipe ||
      data.recipe ||
      data.buildNotes,
  )
    .map(readableValue)
    .filter(Boolean);

  const visualPrompt = readableValue(
    prompts.imageGeneration ||
      prompts.image_generation ||
      prompts.visual ||
      prompts.visualPrompt ||
      prompts.visual_prompt ||
      prompts.image ||
      prompts.imagePrompt ||
      data.visualPrompt ||
      data.imagePrompt,
  );
  const implementationPrompt = readableValue(
    prompts.uiImplementation ||
      prompts.ui_implementation ||
      prompts.implementation ||
      prompts.implementationPrompt ||
      prompts.implementation_prompt ||
      prompts.ui ||
      data.implementationPrompt ||
      data.uiPrompt,
  );
  const designTokenPrompt = readableValue(
    prompts.designTokens ||
      prompts.design_tokens ||
      prompts.tokens ||
      data.designTokenPrompt,
  );
  const negativePrompt = readableValue(
    prompts.negative ||
      prompts.negativePrompt ||
      prompts.negative_prompt ||
      data.negativePrompt,
  );

  return {
    data,
    visualDna,
    description,
    palette,
    whyItWorks,
    recipe,
    prompts: {
      visual: visualPrompt,
      implementation: implementationPrompt,
      tokens: designTokenPrompt,
      negative: negativePrompt,
    },
    provider:
      record.provider ||
      asset.analysisProvider ||
      asset.analysis_provider ||
      data.provider ||
      "",
    model:
      record.model || asset.analysisModel || asset.analysis_model || data.model || "",
    promptVersion:
      record.promptVersion ||
      record.prompt_version ||
      data.promptVersion ||
      state.settings.promptVersion ||
      "",
    analyzedAt:
      record.createdAt ||
      record.created_at ||
      asset.analyzedAt ||
      asset.analyzed_at ||
      "",
    confidence: finiteNumber(
      data.confidence,
      record.confidence,
      asset.analysisConfidence,
    ),
  };
}

function stateLabel(value) {
  return STATUS_LABELS[value] || value || "未分類";
}

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("zh-Hant-TW").format(number)
    : "—";
}

function formatBytes(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) return "—";
  if (number < 1024) return `${number} B`;
  if (number < 1024 ** 2) return `${(number / 1024).toFixed(1)} KB`;
  return `${(number / 1024 ** 2).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-Hant-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusIsActive(status) {
  return ["queued", "pending", "running", "processing", "analyzing"].includes(
    status,
  );
}

function statusNeedsAttention(status) {
  return ["needs_review", "failed", "missing", "needs_setup"].includes(status);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  if (response.status === 204) return null;

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { message: text };
    }
  }

  if (!response.ok) {
    const message =
      payload?.error?.message ||
      payload?.error ||
      payload?.message ||
      `本地服務回傳 ${response.status}`;
    const error = new Error(String(message));
    error.status = response.status;
    error.details = payload?.details || payload?.error?.details || null;
    throw error;
  }

  return payload;
}

function studySvg(index, title, palette) {
  const [paper, ink, accent, muted] = palette;
  const variants = [
    `<rect x="44" y="44" width="712" height="512" fill="${paper}"/><rect x="380" y="88" width="328" height="292" fill="${muted}"/><path d="M390 380h318v124H390z" fill="${ink}"/><path d="M88 110h224v18H88zm0 36h166v8H88zm0 244h230v114H88z" fill="${accent}"/>`,
    `<rect width="800" height="600" fill="${ink}"/><text x="54" y="170" font-size="116" font-weight="800" fill="${paper}" font-family="Arial">FORM</text><text x="54" y="276" font-size="116" font-weight="800" fill="${paper}" font-family="Arial">FOLLOWS</text><path d="M54 330h690v5H54z" fill="${accent}"/><text x="56" y="380" font-size="22" fill="${muted}" font-family="Arial">${escapeHTML(title)}</text>`,
    `<rect width="800" height="600" fill="${paper}"/><circle cx="400" cy="285" r="172" fill="${muted}"/><rect x="334" y="118" width="132" height="316" fill="${accent}"/><rect x="352" y="150" width="96" height="244" fill="${ink}"/><path d="M84 520h632" stroke="${ink}" stroke-width="3"/>`,
    `<rect width="800" height="600" fill="${accent}"/><rect x="48" y="46" width="286" height="508" fill="${paper}"/><rect x="370" y="46" width="382" height="242" fill="${ink}"/><rect x="370" y="320" width="178" height="234" fill="${muted}"/><rect x="580" y="320" width="172" height="234" fill="${paper}"/>`,
    `<rect width="800" height="600" fill="${paper}"/><rect x="52" y="54" width="164" height="492" fill="${ink}"/><rect x="246" y="54" width="502" height="88" fill="${muted}"/><path d="M246 178h502v368H246z" fill="${accent}"/><path d="M284 488V302m84 186V260m84 228V352m84 136V214m84 274V332m84 156V278" stroke="${paper}" stroke-width="20"/>`,
    `<rect width="800" height="600" fill="${muted}"/><rect x="62" y="58" width="676" height="484" fill="${paper}"/><rect x="106" y="110" width="262" height="354" fill="${accent}"/><circle cx="520" cy="284" r="122" fill="${ink}"/><path d="M432 458h180" stroke="${ink}" stroke-width="10"/>`,
    `<rect width="800" height="600" fill="${ink}"/><rect x="48" y="52" width="704" height="496" fill="${paper}"/><path d="M48 194h704M288 52v496M520 194v354" stroke="${muted}" stroke-width="3"/><circle cx="640" cy="120" r="34" fill="${accent}"/><rect x="324" y="238" width="152" height="208" fill="${ink}"/>`,
    `<rect width="800" height="600" fill="${paper}"/><path d="M70 74h660v452H70z" fill="${muted}"/><path d="M70 74h396v452H70z" fill="${ink}"/><text x="108" y="244" font-size="86" font-weight="700" fill="${paper}" font-family="Arial">A—Z</text><rect x="506" y="118" width="174" height="174" fill="${accent}"/><path d="M506 326h174v12H506zm0 34h116v8H506z" fill="${ink}"/>`,
  ];
  const markup = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" role="img" aria-label="${escapeHTML(title)}">
      ${variants[index % variants.length]}
      <text x="54" y="574" font-size="14" fill="${index === 1 ? paper : ink}" font-family="Arial">SYNTHETIC STUDY ${String(index + 1).padStart(2, "0")} · STYLEBASE</text>
    </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(markup)}`;
}

function createSyntheticStudies() {
  const definitions = [
    {
      title: "校準建築／首頁",
      discipline: "web",
      palette: ["#f1f0ea", "#161817", "#135dff", "#b8b9b4"],
      description: "以寬幅建築影像、低密度導覽與克制字級建立安靜但明確的首頁層級。",
      style: "極簡、建築、編輯",
      composition: "非對稱分割、影像主導、寬留白",
    },
    {
      title: "模組字體／海報",
      discipline: "brand",
      palette: ["#f4f0e8", "#111111", "#dc3328", "#858681"],
      description: "巨幅無襯線字體與校樣紅線構成單一視覺承諾，適合作為品牌宣言。",
      style: "字體主導、現代主義",
      composition: "滿版字級、嚴格基線、單點訊號色",
    },
    {
      title: "靜物材質／品牌",
      discipline: "brand",
      palette: ["#eee9df", "#1e211f", "#8d6f47", "#c7c1b7"],
      description: "中性棚拍、觸感材質與少量標籤，讓產品本身成為品牌識別的證據。",
      style: "靜物攝影、自然材質",
      composition: "中心聚焦、低對比背景、尺度留白",
    },
    {
      title: "流動狀態／概念",
      discipline: "concept",
      palette: ["#fff5e9", "#171717", "#ef4d23", "#684cff"],
      description: "高飽和場域與分欄節奏用來表達運動、音樂或文化活動的動態性。",
      style: "文化海報、動態模糊",
      composition: "互補色衝突、分割欄位、大字短句",
    },
    {
      title: "資料層級／UI",
      discipline: "ui",
      palette: ["#f5f6f2", "#171918", "#135dff", "#9ca7b8"],
      description: "窄索引配合寬資料區，使用明確基線與單一藍色表示可操作狀態。",
      style: "工具介面、資訊設計",
      composition: "側欄索引、水平讀序、數據層級",
    },
    {
      title: "包裝比例／產品",
      discipline: "product",
      palette: ["#eee6d8", "#201f1b", "#a66d35", "#b9b1a4"],
      description: "以幾何容器、低彩度紙材與比例對照建立可靠的產品敘事。",
      style: "包裝、材質研究",
      composition: "中心物件、比例對照、低密度註記",
    },
    {
      title: "深色架構／網頁",
      discipline: "web",
      palette: ["#f4f1e9", "#171918", "#6b735f", "#a8a69e"],
      description: "深色框架與亮色內容頁形成場域切換，焦點留給案例本身而非介面裝飾。",
      style: "作品集、深色框架",
      composition: "框中框、案例聚焦、低彩度",
    },
    {
      title: "介面圖譜／品牌",
      discipline: "brand",
      palette: ["#f7f4ec", "#111111", "#135dff", "#b9b8b0"],
      description: "將識別元素依比例、字級與應用場景編成一張可實作的品牌圖譜。",
      style: "品牌規範、系統化",
      composition: "模組網格、比例標記、可追溯編號",
    },
  ];

  return definitions.map((item, index) => ({
    id: `synthetic-${index + 1}`,
    title: item.title,
    fileName: `synthetic-study-${index + 1}.svg`,
    mediaUrl: studySvg(index, item.title, item.palette),
    width: 800,
    height: 600,
    mimeType: "image/svg+xml",
    status: "synthetic",
    discipline: item.discipline,
    synthetic: true,
    analysis: {
      description: item.description,
      visualDna: {
        discipline: item.discipline,
        style: item.style,
        composition: item.composition,
        density: index % 2 === 0 ? "克制／低至中密度" : "聚焦／中密度",
        typography: "清楚字級階層、用途導向",
      },
      palette: item.palette,
      whyItWorks: [
        "主視覺與文字層級只有一個明確焦點",
        "色彩角色固定，不以裝飾取代內容",
        "構圖可直接轉譯成響應式網格",
      ],
      implementationRecipe: [
        "先定義主內容與索引區的比例",
        "以單一訊號色標記狀態與主要操作",
        "在小螢幕保持原本閱讀順序，再折疊次要資訊",
      ],
      promptKit: {
        visual: `${item.title}，${item.style}，${item.composition}，中性色基底，單一訊號色，真實內容主導，無玻璃特效、無霓虹、無通用儀表板卡片。`,
        implementation: `以語意化 HTML、CSS Grid 與可存取控制元件實作「${item.title}」方向；保留${item.composition}，圖片優先，狀態以單一校準色表達。`,
        negative: "漸層光球、玻璃擬態、霓虹描邊、卡片套卡片、巨大標題、無意義 AI 分數",
      },
    },
  }));
}

function providerObject() {
  if (Array.isArray(state.provider)) {
    return (
      state.provider.find((item) =>
        /codex/i.test(String(item?.id || item?.name || item?.provider || "")),
      ) || state.provider[0] || null
    );
  }
  return state.provider && typeof state.provider === "object"
    ? state.provider
    : null;
}

function codexReadiness() {
  const provider = providerObject();
  if (!provider) return null;
  if (typeof provider.ready === "boolean") return provider.ready;
  if (typeof provider.available === "boolean") return provider.available;
  if (typeof provider.configured === "boolean") return provider.configured;
  const status = String(provider.status || provider.state || "").toLowerCase();
  if (["ready", "available", "connected", "ok"].includes(status)) return true;
  if (
    ["needs_setup", "unavailable", "missing", "error", "auth_required"].includes(
      status,
    )
  ) {
    return false;
  }
  return null;
}

async function loadBootstrap({ preserveSelection = true } = {}) {
  state.loading = true;
  state.error = null;
  renderLoading();

  try {
    const bootstrap = await api("/api/bootstrap");
    const rawAssets = listFrom(bootstrap?.assets, ["items", "assets", "data"]);
    const rawJobs = listFrom(bootstrap?.jobs, ["items", "jobs", "data"]);

    state.assets = rawAssets.map(normalizeAsset);
    state.resultTotal =
      finiteNumber(bootstrap?.assets?.total, bootstrap?.assets?.count) ??
      state.assets.length;
    state.libraryTotal =
      finiteNumber(
        bootstrap?.stats?.assets,
        bootstrap?.stats?.assetCount,
        bootstrap?.assets?.total,
      ) ?? state.assets.length;
    state.stats = asObject(bootstrap?.stats);
    state.jobs = rawJobs.map(normalizeJob);
    state.settings = asObject(bootstrap?.settings);
    state.provider = bootstrap?.provider ?? bootstrap?.providers ?? null;
    state.collections = listFrom(bootstrap?.collections, [
      "items",
      "collections",
      "data",
    ]).map(normalizeCollection);
    state.paths = asObject(bootstrap?.paths);
    state.loading = false;
    elements.railStatus.textContent = "本地連線";

    if (
      preserveSelection &&
      state.selectedId &&
      !state.assets.some((asset) => asset.id === state.selectedId)
    ) {
      closeInspector();
    }

    renderAll();
  } catch (error) {
    state.loading = false;
    state.error = error;
    elements.railStatus.textContent = "連線失敗";
    renderLoading();
  }
}

function renderLoading() {
  elements.loadingState.hidden = !state.loading;
  elements.errorState.hidden = !state.error;
  elements.gallery.hidden = state.loading || Boolean(state.error);
  elements.collectionOverview.hidden = true;

  if (state.error) {
    elements.errorMessage.textContent =
      state.error.message || "請確認本地服務仍在執行，再重新載入。";
    elements.resultSummary.textContent = "本地資料庫無法連線";
  }
}

function activeJobs() {
  return state.jobs.filter((job) => statusIsActive(job.status));
}

function inboxAssets() {
  return state.assets.filter(
    (asset) =>
      statusNeedsAttention(asset.status) ||
      ["discovered", "imported", "queued", "pending"].includes(asset.status),
  );
}

const DISCIPLINE_ALIASES = {
  web: [
    "web",
    "website",
    "landing page",
    "ecommerce",
    "網頁",
    "網站",
    "著陸頁",
    "電商",
  ],
  ui: [
    "ui",
    "ux",
    "interface",
    "app",
    "dashboard",
    "介面",
    "儀表板",
    "應用程式",
  ],
  product: ["product", "industrial", "packaging", "產品", "工業設計", "包裝", "物件"],
  brand: [
    "brand",
    "branding",
    "identity",
    "logo",
    "品牌",
    "識別",
    "標誌",
    "視覺識別",
  ],
  concept: [
    "concept",
    "editorial",
    "campaign",
    "poster",
    "art direction",
    "概念",
    "編輯",
    "活動視覺",
    "海報",
    "藝術指導",
  ],
};

function disciplineTextMatches(text, term) {
  if (/^[a-z0-9]+$/i.test(term)) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?:^|[^a-z0-9])${escaped}(?:$|[^a-z0-9])`, "i").test(
      text,
    );
  }
  return text.includes(term);
}

function assetDisciplines(asset) {
  const analysis = normalizedAnalysis(asset);
  const source = [
    asset.discipline,
    analysis.visualDna.discipline,
    analysis.data.designDomains,
    analysis.data.design_domains,
    analysis.data.discipline,
    analysis.data.category,
  ]
    .map(readableValue)
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return Object.entries(DISCIPLINE_ALIASES)
    .filter(([, terms]) =>
      terms.some((term) => disciplineTextMatches(source, term)),
    )
    .map(([discipline]) => discipline);
}

function filteredAssets() {
  let assets = [...state.assets];
  if (state.view === "inbox") assets = inboxAssets();
  if (state.discipline) {
    assets = assets.filter((asset) =>
      assetDisciplines(asset).includes(state.discipline),
    );
  }
  if (state.status) {
    assets = assets.filter((asset) => asset.status === state.status);
  }

  if (state.sort === "title") {
    assets.sort((a, b) => a.title.localeCompare(b.title, "zh-Hant"));
  } else if (state.sort === "status") {
    assets.sort((a, b) => a.status.localeCompare(b.status));
  } else {
    assets.sort((a, b) => {
      const aTime = new Date(a.createdAt || 0).getTime();
      const bTime = new Date(b.createdAt || 0).getTime();
      return bTime - aTime;
    });
  }
  return assets;
}

function activeCollection() {
  return (
    state.collections.find(
      (collection) => collection.id === state.activeCollectionId,
    ) || null
  );
}

function renderAll() {
  renderLoading();
  renderViewHeading();
  renderCounts();
  renderProviderState();
  renderCollectionNav();
  renderGallery();
  renderInspector();
  renderBatchBar();
  renderQueue();
  renderSettings();
  updateNavState();
}

function renderViewHeading() {
  if (state.view === "collections") {
    elements.viewKicker.textContent = "策展索引";
    elements.viewTitle.textContent = "收藏集";
    elements.resultSummary.textContent = `${formatNumber(
      state.collections.length,
    )} 個收藏集`;
    return;
  }

  const collection = activeCollection();
  if (collection) {
    elements.viewKicker.textContent = "收藏集";
    elements.viewTitle.textContent = collection.name;
  } else if (state.view === "inbox") {
    elements.viewKicker.textContent = "待確認與待分析";
    elements.viewTitle.textContent = "待整理";
  } else {
    elements.viewKicker.textContent = "視覺索引";
    elements.viewTitle.textContent = "素材庫";
  }
}

function renderCounts() {
  const jobsActive = activeJobs().length;
  const inboxCount =
    finiteNumber(
      state.stats.inbox,
      state.stats.needsReview,
      state.stats.needs_review,
    ) ?? inboxAssets().length;

  elements.countLibrary.textContent = formatNumber(state.libraryTotal);
  elements.countInbox.textContent = formatNumber(inboxCount);
  elements.countCollections.textContent = formatNumber(state.collections.length);
  elements.countQueue.textContent = formatNumber(jobsActive);
}

function renderProviderState() {
  const ready = codexReadiness();
  elements.setupNotice.hidden = ready !== false;
  elements.settingsStatusDot.classList.toggle("is-ready", ready === true);
  elements.settingsStatusDot.classList.toggle("needs-setup", ready === false);
  elements.settingsStatusDot.setAttribute(
    "aria-label",
    ready === true
      ? "Codex Agent 已就緒"
      : ready === false
        ? "Codex Agent 尚未就緒"
        : "Codex Agent 狀態未知",
  );
}

function updateNavState() {
  elements.primaryNav.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === state.view && !state.activeCollectionId;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

function renderCollectionNav() {
  if (!state.collections.length) {
    elements.collectionNav.innerHTML =
      '<p class="rail-footnote">尚未建立收藏集</p>';
    return;
  }

  elements.collectionNav.innerHTML = state.collections
    .slice(0, 12)
    .map(
      (collection) => `
        <button
          class="collection-link ${collection.id === state.activeCollectionId ? "is-active" : ""}"
          type="button"
          data-collection-id="${escapeHTML(collection.id)}"
        >
          <span>${escapeHTML(collection.name)}</span>
          <small>${formatNumber(collection.itemCount)}</small>
        </button>`,
    )
    .join("");
}

function renderCollectionOverview() {
  elements.gallery.hidden = true;
  elements.collectionOverview.hidden = false;

  if (!state.collections.length) {
    elements.collectionTable.innerHTML = `
      <div class="empty-library-panel">
        <div>
          <h2>尚未建立收藏集</h2>
          <p>將研究中的方向整理成收藏集，之後可從影像檢視器加入素材。</p>
          <button class="button button--primary" type="button" data-action="new-collection">新增收藏集</button>
        </div>
      </div>`;
    return;
  }

  elements.collectionTable.innerHTML = state.collections
    .map(
      (collection) => `
        <div class="collection-row">
          <strong>${escapeHTML(collection.name)}</strong>
          <output>${formatNumber(collection.itemCount)} 張</output>
          <button class="button button--quiet" type="button" data-collection-id="${escapeHTML(collection.id)}">
            開啟索引
          </button>
        </div>`,
    )
    .join("");
}

function renderGallery() {
  if (state.loading || state.error) return;
  if (state.view === "collections") {
    renderCollectionOverview();
    return;
  }

  elements.collectionOverview.hidden = true;
  elements.gallery.hidden = false;
  const assets = filteredAssets();
  const apiLibraryEmpty = state.libraryTotal === 0;
  const useSynthetic =
    apiLibraryEmpty &&
    state.view === "library" &&
    !state.activeCollectionId &&
    !state.query &&
    !state.discipline &&
    !state.status;
  const renderedAssets = useSynthetic ? state.syntheticAssets : assets;

  const contextLabel = state.activeCollectionId
    ? activeCollection()?.name || "收藏集"
    : state.view === "inbox"
      ? "待整理"
      : "素材庫";
  elements.resultSummary.textContent = useSynthetic
    ? "資料庫目前為空 · 顯示 8 張合成介面研究"
    : `${contextLabel} · ${formatNumber(assets.length)} 張影像`;

  if (!renderedAssets.length) {
    elements.gallery.innerHTML = `
      <div class="empty-library-panel">
        <div>
          <h2>${apiLibraryEmpty ? "素材庫目前為空" : "沒有符合條件的影像"}</h2>
          <p>${
            apiLibraryEmpty
              ? "匯入影像，或把圖片放入監看資料夾後執行掃描。"
              : "調整搜尋字詞或清除篩選條件；資料不會因為沒有結果而被移除。"
          }</p>
          ${
            apiLibraryEmpty
              ? '<button class="button button--primary" type="button" data-action="import">匯入第一張影像</button>'
              : '<button class="button button--quiet" type="button" data-action="clear-filters">清除條件</button>'
          }
        </div>
      </div>`;
    return;
  }

  const syntheticIntro = useSynthetic
    ? `
      <div class="synthetic-intro">
        <p><strong>合成介面研究</strong>這些 inline SVG 只在 API 素材庫為空時出現，不會寫入資料庫或送交 Codex。</p>
        <button class="button button--primary" type="button" data-action="import">匯入真實影像</button>
      </div>`
    : "";

  elements.gallery.innerHTML =
    syntheticIntro +
    renderedAssets
      .map((asset, index) => renderAssetCard(asset, index, renderedAssets.length))
      .join("");
}

function renderAssetCard(asset, index, total) {
  const current = asset.id === state.selectedId;
  const batchSelected = state.selectedIds.has(asset.id);
  const dimensions =
    asset.width && asset.height ? `${asset.width} × ${asset.height}` : "尺寸未記錄";
  const imageUrl = safeMediaUrl(asset.mediaUrl);
  const stateBadge = asset.synthetic
    ? '<span class="synthetic-flag">合成示意</span>'
    : `<span class="asset-state" data-state="${escapeHTML(asset.status)}">${escapeHTML(
        stateLabel(asset.status),
      )}</span>`;
  const selectionButton = asset.synthetic
    ? ""
    : `
      <button
        class="asset-select-toggle"
        type="button"
        data-batch-id="${escapeHTML(asset.id)}"
        aria-label="${batchSelected ? "從批次移除" : "加入批次"}：${escapeHTML(asset.title)}"
        aria-pressed="${batchSelected}"
      >
        <svg class="icon" aria-hidden="true"><use href="#icon-check"></use></svg>
      </button>`;

  return `
    <figure
      class="asset-card ${current ? "is-selected is-loupe" : ""} ${batchSelected ? "is-batch-selected" : ""}"
      data-asset-id="${escapeHTML(asset.id)}"
      data-registration="${String(index + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}"
    >
      ${stateBadge}
      ${selectionButton}
      <button
        class="asset-open"
        type="button"
        data-open-asset="${escapeHTML(asset.id)}"
        aria-label="檢視 ${escapeHTML(asset.title)}"
        aria-pressed="${current}"
      >
        ${
          imageUrl
            ? `<img src="${escapeHTML(imageUrl)}" alt="${escapeHTML(asset.title)}" ${
                index < 5 ? 'fetchpriority="high"' : 'loading="lazy"'
              } decoding="async" />`
            : `<span class="queue-placeholder-thumb" aria-hidden="true"></span>`
        }
      </button>
      <figcaption class="asset-caption">
        <strong>${escapeHTML(asset.title)}</strong>
        <span>${escapeHTML(dimensions)}</span>
      </figcaption>
      <span class="proof-mark proof-mark--tl" aria-hidden="true"></span>
      <span class="proof-mark proof-mark--tr" aria-hidden="true"></span>
      <span class="proof-mark proof-mark--br" aria-hidden="true"></span>
      <span class="proof-mark proof-mark--bl" aria-hidden="true"></span>
    </figure>`;
}

function assetById(id) {
  return (
    state.assets.find((asset) => asset.id === id) ||
    state.syntheticAssets.find((asset) => asset.id === id) ||
    null
  );
}

function visualDnaRows(visualDna, data) {
  const source =
    Object.keys(visualDna).length > 0
      ? visualDna
      : {
          discipline: data.discipline,
          style: data.style,
          composition: data.composition,
          typography: data.typography,
          mood: data.mood,
        };
  const entries = Object.entries(source)
    .map(([key, value]) => [key, readableValue(value)])
    .filter(([, value]) => value)
    .slice(0, 12);

  if (!entries.length) return "";
  return `
    <dl class="dna-list">
      ${entries
        .map(
          ([key, value]) => `
            <div>
              <dt>${escapeHTML(DNA_LABELS[key] || key)}</dt>
              <dd>${escapeHTML(value)}</dd>
            </div>`,
        )
        .join("")}
    </dl>`;
}

function renderPalette(palette) {
  if (!palette.length) return '<p class="analysis-empty">尚未擷取色票。</p>';
  return `
    <div class="palette">
      ${palette
        .map(
          (swatch) => `
            <div class="swatch" title="${escapeHTML(
              swatch.name || swatch.hex,
            )}">
              ${renderSwatchColor(swatch.hex)}
              <code>${escapeHTML(swatch.hex)}</code>
            </div>`,
        )
        .join("")}
    </div>`;
}

function renderList(items, className, fallback) {
  if (!items.length) return `<p class="analysis-empty">${escapeHTML(fallback)}</p>`;
  return `<ol class="${className}">${items
    .map((item) => `<li>${escapeHTML(item)}</li>`)
    .join("")}</ol>`;
}

function renderPromptBlock(label, key, value) {
  if (!value) {
    return `
      <div class="prompt-block">
        <div class="prompt-label"><span>${escapeHTML(label)}</span></div>
        <p class="analysis-empty">尚未產生這組提示詞。</p>
      </div>`;
  }
  return `
    <div class="prompt-block">
      <div class="prompt-label">
        <span>${escapeHTML(label)}</span>
        <button class="prompt-copy" type="button" data-copy-prompt="${escapeHTML(key)}">
          <svg class="icon" aria-hidden="true"><use href="#icon-copy"></use></svg>
          複製
        </button>
      </div>
      <pre class="prompt-text">${escapeHTML(value)}</pre>
    </div>`;
}

function collectionContainsAsset(collection, asset) {
  if (asset.collectionIds.includes(collection.id)) return true;
  const ids = asArray(collection.assetIds || collection.asset_ids).map(String);
  if (ids.includes(asset.id)) return true;
  return asArray(collection.items).some(
    (item) => String(item?.assetId ?? item?.id ?? item) === asset.id,
  );
}

function renderCollectionControls(asset) {
  if (!state.collections.length) {
    return `
      <div class="collection-control">
        <p>尚未建立收藏集。</p>
        <button class="text-button" type="button" data-action="new-collection">新增收藏集</button>
      </div>`;
  }

  const memberships = state.collections.filter((collection) =>
    collectionContainsAsset(collection, asset),
  );
  return `
    <div class="collection-control">
      <label class="sr-only" for="inspector-collection-select">選擇收藏集</label>
      <select id="inspector-collection-select">
        <option value="">選擇收藏集…</option>
        ${state.collections
          .map(
            (collection) =>
              `<option value="${escapeHTML(collection.id)}">${escapeHTML(
                collection.name,
              )}</option>`,
          )
          .join("")}
      </select>
      <button class="button button--quiet" type="button" data-add-to-collection="${escapeHTML(
        asset.id,
      )}">加入</button>
    </div>
    ${
      memberships.length
        ? `<div class="metadata-actions">${memberships
            .map(
              (collection) => `
                <button
                  class="text-button"
                  type="button"
                  data-remove-collection="${escapeHTML(collection.id)}"
                  data-asset-id="${escapeHTML(asset.id)}"
                >移出 ${escapeHTML(collection.name)}</button>`,
            )
            .join("")}</div>`
        : ""
    }`;
}

function renderInspector() {
  const asset = assetById(state.selectedId);
  if (!asset) {
    elements.inspectorEmpty.hidden = false;
    elements.inspectorContent.hidden = true;
    elements.inspectorContent.innerHTML = "";
    document.body.classList.remove("is-inspector-open");
    elements.inspector.removeAttribute("role");
    elements.inspector.removeAttribute("aria-modal");
    elements.inspector.setAttribute("aria-label", "影像詳細檢視");
    updateAnalyzeControls();
    return;
  }

  const analysis = normalizedAnalysis(asset);
  const hasAnalysis =
    Boolean(analysis.description) ||
    Object.keys(analysis.visualDna).length > 0 ||
    analysis.palette.length > 0;
  const imageUrl = safeMediaUrl(asset.mediaUrl);
  const dimensions =
    asset.width && asset.height ? `${asset.width} × ${asset.height}` : "—";
  const confidence =
    analysis.confidence === null
      ? "—"
      : `${Math.round(
          analysis.confidence <= 1
            ? analysis.confidence * 100
            : analysis.confidence,
        )}%`;
  const inQueue =
    statusIsActive(asset.status) ||
    state.jobs.some(
      (job) => job.assetId === asset.id && statusIsActive(job.status),
    );

  elements.inspectorEmpty.hidden = true;
  elements.inspectorContent.hidden = false;
  document.body.classList.add("is-inspector-open");
  if (isMobileInspector()) {
    elements.inspector.setAttribute("role", "dialog");
    elements.inspector.setAttribute("aria-modal", "true");
    elements.inspector.setAttribute(
      "aria-label",
      `影像詳細檢視：${asset.title}`,
    );
  } else {
    elements.inspector.removeAttribute("role");
    elements.inspector.removeAttribute("aria-modal");
    elements.inspector.setAttribute("aria-label", "影像詳細檢視");
  }

  elements.inspectorContent.innerHTML = `
    <div class="inspector-top">
      <div class="inspector-title">
        <p>${escapeHTML(stateLabel(asset.status))}</p>
        <h2>${escapeHTML(asset.title)}</h2>
      </div>
      <button class="icon-button" type="button" data-close-inspector aria-label="關閉詳細檢視">
        <svg class="icon" aria-hidden="true"><use href="#icon-close"></use></svg>
      </button>
    </div>

    ${
      asset.synthetic
        ? '<p class="synthetic-disclosure">合成介面研究：只在 API 素材庫為空時顯示，不會儲存、編輯或送交 Codex。</p>'
        : ""
    }

    <figure class="inspector-preview">
      ${
        imageUrl
          ? `<img src="${escapeHTML(imageUrl)}" alt="${escapeHTML(asset.title)}" />`
          : '<span class="queue-placeholder-thumb" aria-hidden="true"></span>'
      }
      <figcaption>
        <span>${escapeHTML(asset.fileName)}</span>
        <span>${escapeHTML(dimensions)} · ${escapeHTML(
          asset.mimeType || "格式未記錄",
        )}</span>
      </figcaption>
    </figure>

    ${
      !asset.synthetic
        ? `
      <div class="inspector-actions">
        <button
          class="button button--primary"
          type="button"
          data-analyze-id="${escapeHTML(asset.id)}"
          ${inQueue ? "disabled" : ""}
        >${inQueue ? "已在 Codex 佇列" : "送交 Codex"}</button>
        <span>${escapeHTML(analysis.provider || "codex")} · 信心度 ${escapeHTML(
          confidence,
        )}</span>
        <small class="codex-disclosure">
          按下後會將此影像傳送至 Codex 服務分析；單純匯入不會上傳。
        </small>
      </div>`
        : ""
    }

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>Visual DNA</h3>
        <span class="section-index">A01</span>
      </div>
      ${
        hasAnalysis
          ? `
            <p class="analysis-summary">${escapeHTML(
              analysis.description || "Codex 已完成結構化分析。",
            )}</p>
            ${visualDnaRows(analysis.visualDna, analysis.data)}
          `
          : `
            <div class="analysis-empty">
              <strong>尚未建立 Visual DNA</strong>
              選取「送交 Codex」後，這裡會顯示可編輯的視覺分類與描述。
            </div>`
      }
    </section>

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>色票</h3>
        <span class="section-index">A02</span>
      </div>
      ${renderPalette(analysis.palette)}
    </section>

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>為何有效</h3>
        <span class="section-index">A03</span>
      </div>
      ${renderList(analysis.whyItWorks, "evidence-list", "尚未產生設計判讀。")}
    </section>

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>實作 recipe</h3>
        <span class="section-index">A04</span>
      </div>
      ${renderList(analysis.recipe, "recipe-list", "尚未產生實作步驟。")}
    </section>

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>Prompt Kit</h3>
        <span class="section-index">A05</span>
      </div>
      ${renderPromptBlock("視覺提示詞", "visual", analysis.prompts.visual)}
      ${renderPromptBlock(
        "UI 實作 brief",
        "implementation",
        analysis.prompts.implementation,
      )}
      ${renderPromptBlock(
        "Design token 提示詞",
        "tokens",
        analysis.prompts.tokens,
      )}
      ${renderPromptBlock(
        "負面條件",
        "negative",
        analysis.prompts.negative,
      )}
    </section>

    <section class="inspector-section">
      <div class="inspector-section-heading">
        <h3>來源與分析證據</h3>
        <span class="section-index">A06</span>
      </div>
      <dl class="provenance-list">
        <div><dt>相對路徑</dt><dd>${escapeHTML(asset.relativePath || "—")}</dd></div>
        <div><dt>檔案大小</dt><dd>${escapeHTML(formatBytes(asset.fileSize))}</dd></div>
        <div><dt>雜湊</dt><dd>${escapeHTML(asset.hash || "—")}</dd></div>
        <div><dt>Codex 模型</dt><dd>${escapeHTML(analysis.model || "—")}</dd></div>
        <div><dt>Prompt 版</dt><dd>${escapeHTML(analysis.promptVersion || "—")}</dd></div>
        <div><dt>分析時間</dt><dd>${escapeHTML(formatDate(analysis.analyzedAt))}</dd></div>
      </dl>
    </section>

    ${
      asset.synthetic
        ? ""
        : `
      <section class="inspector-section">
        <div class="inspector-section-heading">
          <h3>收藏集</h3>
          <span class="section-index">A07</span>
        </div>
        ${renderCollectionControls(asset)}
      </section>

      <section class="inspector-section">
        <div class="inspector-section-heading">
          <h3>編輯 metadata</h3>
          <span class="section-index">A08</span>
        </div>
        <form class="metadata-form" data-metadata-form="${escapeHTML(asset.id)}">
          <label class="field">
            <span>標題</span>
            <input name="title" maxlength="180" value="${escapeHTML(asset.title)}" />
          </label>
          <label class="field">
            <span>來源 URL</span>
            <input name="sourceUrl" type="url" value="${escapeHTML(asset.sourceUrl)}" placeholder="https://" />
          </label>
          <label class="field">
            <span>權利備註</span>
            <textarea name="rightsNote" placeholder="授權、作者、用途限制…">${escapeHTML(
              asset.rightsNote,
            )}</textarea>
          </label>
          <label class="field">
            <span>人工筆記</span>
            <textarea name="notes" placeholder="可重用的版面或實作觀察…">${escapeHTML(
              asset.notes,
            )}</textarea>
          </label>
          <div class="metadata-actions">
            <button class="button button--primary" type="submit">儲存 metadata</button>
          </div>
        </form>
      </section>`
    }`;

  updateAnalyzeControls();
}

function currentAnalyzeIds() {
  const batch = [...state.selectedIds].filter((id) => !assetById(id)?.synthetic);
  if (batch.length) return batch;
  const current = assetById(state.selectedId);
  return current && !current.synthetic ? [current.id] : [];
}

function updateAnalyzeControls() {
  const ids = currentAnalyzeIds();
  elements.recognizeButton.disabled = ids.length === 0;
  elements.recognizeButton.title =
    ids.length > 0
      ? `將 ${ids.length} 張影像送交 Codex`
      : "請先選取一張真實影像";
}

function renderBatchBar() {
  const count = state.selectedIds.size;
  elements.batchBar.hidden = count === 0;
  elements.batchCount.textContent = `已選 ${formatNumber(count)} 張`;
  elements.batchAnalyzeButton.disabled = count === 0;
  updateAnalyzeControls();
}

function jobAsset(job) {
  return assetById(job.assetId);
}

function jobProgress(job) {
  if (job.progress === null) return null;
  const value = job.progress <= 1 ? job.progress * 100 : job.progress;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function renderQueue() {
  const jobs = [...state.jobs].sort((a, b) => {
    const rank = (job) =>
      statusIsActive(job.status) ? 0 : statusNeedsAttention(job.status) ? 1 : 2;
    return rank(a) - rank(b);
  });
  const active = activeJobs();
  const needsSetup = jobs.some((job) => job.status === "needs_setup");

  elements.queueActiveCount.textContent = String(active.length).padStart(2, "0");
  elements.queueSummaryText.textContent = active.length
    ? `${active.length} 項執行或等待中 · 同時工作數 1`
    : jobs.length
      ? `最近 ${jobs.length} 項工作`
      : "尚無工作";
  elements.retryNeedsSetupButton.hidden = !needsSetup;
  elements.queueToggle.setAttribute("aria-expanded", String(state.queueExpanded));
  elements.app.classList.toggle("is-queue-expanded", state.queueExpanded);

  if (!jobs.length) {
    elements.queueTrack.innerHTML =
      '<p class="queue-empty">選取影像並按「送交 Codex」，工作會出現在這裡。</p>';
    renderCounts();
    return;
  }

  elements.queueTrack.innerHTML = jobs
    .map((job) => {
      const asset = jobAsset(job);
      const progress = jobProgress(job);
      const indeterminate = progress === null && statusIsActive(job.status);
      const stage = job.stage || stateLabel(job.status);
      const imageUrl = safeMediaUrl(asset?.mediaUrl);
      return `
        <article class="queue-job" data-status="${escapeHTML(job.status)}">
          ${
            imageUrl
              ? `<img src="${escapeHTML(imageUrl)}" alt="" loading="lazy" />`
              : '<span class="queue-placeholder-thumb" aria-hidden="true"></span>'
          }
          <div class="queue-job-info">
            <strong>${escapeHTML(asset?.title || `影像 ${job.assetId || "—"}`)}</strong>
            <div class="job-meta">
              <span>${escapeHTML(stage)}</span>
              <span>${progress === null ? "" : `${progress}%`}</span>
            </div>
            <div class="job-progress ${indeterminate ? "is-indeterminate" : ""}" aria-label="${escapeHTML(
              stage,
            )}">
              <span style="--progress:${progress === null ? 28 : progress}%"></span>
            </div>
            ${
              job.error
                ? `<p class="job-error">${escapeHTML(job.error)}</p>`
                : ""
            }
          </div>
        </article>`;
    })
    .join("");

  renderCounts();
}

function renderSettings() {
  const provider = providerObject() || {};
  const ready = codexReadiness();
  elements.settingInboxPath.textContent =
    state.paths.inbox || state.paths.inboxDirectory || "由本地服務管理";
  elements.settingCodexModel.value = state.settings.codexModel || "";
  elements.codexReadiness.textContent =
    ready === true
      ? `已就緒${provider.version ? ` · ${provider.version}` : ""}`
      : ready === false
        ? "未就緒 · 請確認 Codex CLI 已安裝並登入"
        : "狀態未知";
  elements.codexReadiness.classList.toggle("is-ready", ready === true);
  elements.codexReadiness.classList.toggle("needs-setup", ready === false);
  elements.codexExecutionMode.textContent =
    provider.execution ||
    provider.executionMode ||
    (state.settings.executionMode === "codex-agent"
      ? "本地 Codex Agent"
      : state.settings.executionMode) ||
    "本地 Codex Agent";
  elements.codexPromptVersion.textContent =
    state.settings.promptVersion || provider.promptVersion || "—";
}

async function refreshAssets({ selectId = null } = {}) {
  const params = new URLSearchParams({
    limit: "200",
    sort: state.sort,
  });
  if (state.query) params.set("query", state.query);
  if (state.status) params.set("status", state.status);
  if (state.activeCollectionId) {
    params.set("collectionId", state.activeCollectionId);
  }

  const result = await api(`/api/assets?${params.toString()}`);
  state.assets = listFrom(result, ["items", "assets", "data"]).map(normalizeAsset);
  const selectionStillExists =
    !state.selectedId || Boolean(assetById(state.selectedId));
  if (!selectionStillExists) state.selectedId = null;
  state.resultTotal =
    finiteNumber(result?.total, result?.count) ?? state.assets.length;
  if (!state.query && !state.status && !state.activeCollectionId) {
    state.libraryTotal = state.resultTotal;
  }
  renderAll();
  if (selectId) await selectAsset(selectId, { scroll: true });
}

async function refreshJobs() {
  try {
    const result = await api("/api/jobs?limit=80");
    const previousStatuses = new Map(
      state.jobs.map((job) => [job.id, job.status]),
    );
    const nextJobs = listFrom(result, ["items", "jobs", "data"]).map(
      normalizeJob,
    );
    const reachedTerminalState = nextJobs.some((job) => {
      const previousStatus = previousStatuses.get(job.id);
      return previousStatus !== job.status && !statusIsActive(job.status);
    });
    state.jobs = nextJobs;
    if (reachedTerminalState) {
      await refreshAssets({ selectId: state.selectedId });
      return;
    }
    renderQueue();
    renderInspector();
  } catch (error) {
    console.warn("Unable to refresh jobs", error);
  }
}

async function refreshCollections() {
  const result = await api("/api/collections");
  state.collections = listFrom(result, ["items", "collections", "data"]).map(
    normalizeCollection,
  );
  renderCollectionNav();
  renderCollectionOverview();
  renderCounts();
  renderInspector();
}

async function refreshProvider() {
  try {
    state.provider = await api("/api/providers");
    renderProviderState();
    renderSettings();
  } catch (error) {
    state.provider = { ready: false, message: error.message };
    renderProviderState();
    renderSettings();
  }
}

async function selectAsset(id, { scroll = false } = {}) {
  const initial = assetById(id);
  if (!initial) return;
  const shouldMoveFocus = state.selectedId !== id && isMobileInspector();
  if (shouldMoveFocus) {
    state.inspectorReturnFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    state.inspectorReturnAssetId = id;
  }
  state.selectedId = id;
  state.lastAnchorId = id;
  renderGallery();
  renderInspector();
  renderBatchBar();

  if (!initial.synthetic) {
    try {
      const detail = normalizeAsset(
        await api(`/api/assets/${encodeURIComponent(id)}`),
      );
      const index = state.assets.findIndex((asset) => asset.id === id);
      if (index >= 0) state.assets[index] = detail;
      renderInspector();
    } catch (error) {
      notify(`無法讀取完整 metadata：${error.message}`, "error");
    }
  }

  if (scroll) {
    requestAnimationFrame(() => {
      const card = elements.gallery.querySelector(
        `[data-asset-id="${CSS.escape(id)}"]`,
      );
      card?.scrollIntoView({ block: "nearest", inline: "nearest" });
    });
  }

  if (shouldMoveFocus) {
    requestAnimationFrame(() => {
      elements.inspector
        .querySelector("[data-close-inspector]")
        ?.focus({ preventScroll: true });
    });
  }
}

function closeInspector() {
  const returnFocus = state.inspectorReturnFocus;
  const returnAssetId = state.inspectorReturnAssetId || state.selectedId;
  state.inspectorReturnFocus = null;
  state.inspectorReturnAssetId = null;
  state.selectedId = null;
  renderGallery();
  renderInspector();
  renderBatchBar();
  if (returnFocus || returnAssetId) {
    requestAnimationFrame(() => {
      if (returnFocus instanceof HTMLElement && returnFocus.isConnected) {
        returnFocus.focus({ preventScroll: true });
        return;
      }
      const assetButton = returnAssetId
        ? elements.gallery.querySelector(
            `[data-open-asset="${CSS.escape(returnAssetId)}"]`,
          )
        : null;
      if (assetButton instanceof HTMLElement) {
        assetButton.focus({ preventScroll: true });
      } else {
        elements.workspace.focus({ preventScroll: true });
      }
    });
  }
}

function isMobileInspector() {
  return window.matchMedia("(max-width: 920px)").matches;
}

function trapMobileInspectorFocus(event) {
  if (
    event.key !== "Tab" ||
    !state.selectedId ||
    !isMobileInspector() ||
    !document.body.classList.contains("is-inspector-open")
  ) {
    return false;
  }

  const focusable = [
    ...elements.inspector.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((element) => element.getClientRects().length > 0);
  if (!focusable.length) return false;

  const first = focusable[0];
  const last = focusable.at(-1);
  if (!elements.inspector.contains(document.activeElement)) {
    event.preventDefault();
    first.focus();
    return true;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
    return true;
  }
  if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
    return true;
  }
  return false;
}

function toggleBatch(id) {
  const asset = assetById(id);
  if (!asset || asset.synthetic) return;
  if (state.selectedIds.has(id)) state.selectedIds.delete(id);
  else state.selectedIds.add(id);
  state.lastAnchorId = id;
  renderGallery();
  renderBatchBar();
}

function selectBatchRange(targetId) {
  const assets = filteredAssets().filter((asset) => !asset.synthetic);
  const start = assets.findIndex((asset) => asset.id === state.lastAnchorId);
  const end = assets.findIndex((asset) => asset.id === targetId);
  if (start < 0 || end < 0) {
    toggleBatch(targetId);
    return;
  }
  const [from, to] = start < end ? [start, end] : [end, start];
  for (const asset of assets.slice(from, to + 1)) {
    state.selectedIds.add(asset.id);
  }
  state.lastAnchorId = targetId;
  renderGallery();
  renderBatchBar();
}

async function analyzeAssets(ids) {
  const uniqueIds = [...new Set(ids)].filter((id) => !assetById(id)?.synthetic);
  if (!uniqueIds.length) return;

  const buttons = [
    elements.recognizeButton,
    elements.batchAnalyzeButton,
    ...document.querySelectorAll("[data-analyze-id]"),
  ];
  const restoreButtons = beginPendingButtons(buttons);

  try {
    let queued = 0;
    const errors = [];
    for (const id of uniqueIds) {
      try {
        await api(`/api/assets/${encodeURIComponent(id)}/analyze`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        queued += 1;
      } catch (error) {
        errors.push(`${assetById(id)?.title || id}：${error.message}`);
      }
    }

    state.queueExpanded = true;
    await Promise.allSettled([refreshJobs(), refreshAssets()]);
    if (queued) {
      notify(`${queued} 張影像已送交 Codex，佇列同時工作數為 1。`);
    }
    if (errors.length) {
      notify(`有 ${errors.length} 張未能排入佇列：${errors[0]}`, "error");
    }
  } finally {
    restoreButtons();
    renderInspector();
    renderBatchBar();
  }
}

function readFileDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () =>
      reject(reader.error || new Error("無法讀取檔案")),
    );
    reader.readAsDataURL(file);
  });
}

async function importFiles(files) {
  const validFiles = [...files].filter((file) => file.type.startsWith("image/"));
  if (!validFiles.length) {
    notify("沒有可匯入的影像檔案。", "error");
    return;
  }

  elements.importButton.disabled = true;
  const original = elements.importButton.innerHTML;
  elements.importButton.textContent = `匯入 0 / ${validFiles.length}`;
  let imported = 0;
  let lastAssetId = null;
  const errors = [];

  for (const file of validFiles) {
    try {
      const data = await readFileDataUrl(file);
      const payload = await api("/api/import", {
        method: "POST",
        body: JSON.stringify({
          name: stripExtension(file.name),
          type: file.type,
          data,
          sourceUrl: "",
          rightsNote: "",
        }),
      });
      imported += 1;
      lastAssetId = String(payload?.asset?.id || lastAssetId || "");
      elements.importButton.textContent = `匯入 ${imported} / ${validFiles.length}`;
    } catch (error) {
      errors.push(`${file.name}：${error.message}`);
    }
  }

  elements.importButton.disabled = false;
  elements.importButton.innerHTML = original;
  elements.fileInput.value = "";
  await loadBootstrap({ preserveSelection: false });
  if (lastAssetId) await selectAsset(lastAssetId, { scroll: true });

  if (imported) {
    notify(
      `${imported} 張影像已匯入並選取；確認後按「送交 Codex」開始辨識。`,
    );
  }
  if (errors.length) {
    notify(`有 ${errors.length} 張未匯入：${errors[0]}`, "error");
  }
}

async function scanFolder() {
  const original = elements.scanButton.innerHTML;
  elements.scanButton.disabled = true;
  elements.scanButton.textContent = "掃描中…";
  try {
    const result = await api("/api/scan", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await loadBootstrap();
    notify(
      `掃描完成：${formatNumber(result?.scanned ?? 0)} 個檔案，新增 ${formatNumber(
        result?.imported ?? 0,
      )} 張，重複 ${formatNumber(result?.duplicates ?? 0)} 張。`,
    );
  } catch (error) {
    notify(`掃描失敗：${error.message}`, "error");
  } finally {
    elements.scanButton.disabled = false;
    elements.scanButton.innerHTML = original;
  }
}

async function saveMetadata(form) {
  const id = form.dataset.metadataForm;
  const submit = form.querySelector('[type="submit"]');
  const original = submit.textContent;
  submit.disabled = true;
  submit.textContent = "儲存中…";
  const data = new FormData(form);
  try {
    const updated = normalizeAsset(
      await api(`/api/assets/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: String(data.get("title") || "").trim(),
          sourceUrl: String(data.get("sourceUrl") || "").trim(),
          rightsNote: String(data.get("rightsNote") || "").trim(),
          notes: String(data.get("notes") || "").trim(),
        }),
      }),
    );
    const index = state.assets.findIndex((asset) => asset.id === id);
    if (index >= 0) state.assets[index] = updated;
    renderGallery();
    renderInspector();
    notify("Metadata 已儲存。");
  } catch (error) {
    notify(`Metadata 儲存失敗：${error.message}`, "error");
    submit.disabled = false;
    submit.textContent = original;
  }
}

async function createCollection(name) {
  const result = await api("/api/collections", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  state.collections.push(normalizeCollection(result));
  await refreshCollections();
}

async function addToCollection(assetId, collectionId) {
  if (!collectionId) {
    notify("請先選擇收藏集。", "error");
    return;
  }
  await api(`/api/collections/${encodeURIComponent(collectionId)}/items`, {
    method: "POST",
    body: JSON.stringify({ assetId }),
  });
  const asset = assetById(assetId);
  if (asset && !asset.collectionIds.includes(collectionId)) {
    asset.collectionIds.push(collectionId);
  }
  await refreshCollections();
  notify("影像已加入收藏集。");
}

async function removeFromCollection(assetId, collectionId) {
  await api(
    `/api/collections/${encodeURIComponent(collectionId)}/items/${encodeURIComponent(
      assetId,
    )}`,
    { method: "DELETE" },
  );
  const asset = assetById(assetId);
  if (asset) {
    asset.collectionIds = asset.collectionIds.filter((id) => id !== collectionId);
  }
  await refreshCollections();
  notify("影像已移出收藏集。");
}

async function openCollection(id) {
  state.view = "library";
  state.activeCollectionId = id;
  state.selectedId = null;
  await refreshAssets();
  elements.workspace.scrollTo({ top: 0, behavior: "smooth" });
}

function clearFilters() {
  state.query = "";
  state.discipline = "";
  state.status = "";
  state.sort = "newest";
  elements.searchInput.value = "";
  elements.disciplineFilter.value = "";
  elements.statusFilter.value = "";
  elements.sortSelect.value = "newest";
  refreshAssets().catch((error) =>
    notify(`無法清除條件：${error.message}`, "error"),
  );
}

function showDialog(dialog) {
  if (!dialog.open) dialog.showModal();
}

function closeDialog(dialog) {
  if (dialog?.open) dialog.close();
}

async function openSettings() {
  renderSettings();
  showDialog(elements.settingsDialog);
  await refreshProvider();
}

async function copyPrompt(key) {
  const asset = assetById(state.selectedId);
  if (!asset) return;
  const prompt = normalizedAnalysis(asset).prompts[key];
  if (!prompt) return;
  try {
    await navigator.clipboard.writeText(prompt);
    notify("提示詞已複製到剪貼簿。");
  } catch (error) {
    notify(`無法複製提示詞：${error.message}`, "error");
  }
}

let liveRegionTimer = null;
function notify(message, type = "info") {
  window.clearTimeout(liveRegionTimer);
  elements.liveRegion.textContent = String(message);
  elements.liveRegion.classList.toggle("is-error", type === "error");
  elements.liveRegion.classList.add("is-visible");
  liveRegionTimer = window.setTimeout(() => {
    elements.liveRegion.classList.remove("is-visible");
  }, type === "error" ? 7000 : 4200);
}

function moveSelection(direction) {
  if (!state.selectedId) return;
  const assets =
    state.libraryTotal === 0 ? state.syntheticAssets : filteredAssets();
  const currentIndex = assets.findIndex((asset) => asset.id === state.selectedId);
  if (currentIndex < 0) return;
  const nextIndex = Math.max(
    0,
    Math.min(assets.length - 1, currentIndex + direction),
  );
  if (nextIndex !== currentIndex) {
    selectAsset(assets[nextIndex].id, { scroll: true });
  }
}

function isTypingTarget(target) {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target?.isContentEditable
  );
}

elements.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  window.clearTimeout(state.searchTimer);
  state.query = elements.searchInput.value.trim();
  refreshAssets().catch((error) =>
    notify(`搜尋失敗：${error.message}`, "error"),
  );
});

elements.searchInput.addEventListener("input", () => {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(() => {
    state.query = elements.searchInput.value.trim();
    refreshAssets().catch((error) =>
      notify(`搜尋失敗：${error.message}`, "error"),
    );
  }, 280);
});

elements.disciplineFilter.addEventListener("change", () => {
  state.discipline = elements.disciplineFilter.value;
  renderGallery();
});

elements.statusFilter.addEventListener("change", () => {
  state.status = elements.statusFilter.value;
  refreshAssets().catch((error) =>
    notify(`篩選失敗：${error.message}`, "error"),
  );
});

elements.sortSelect.addEventListener("change", () => {
  state.sort = elements.sortSelect.value;
  refreshAssets().catch((error) =>
    notify(`排序失敗：${error.message}`, "error"),
  );
});

elements.clearFiltersButton.addEventListener("click", clearFilters);
elements.importButton.addEventListener("click", () => elements.fileInput.click());
elements.fileInput.addEventListener("change", () => {
  if (elements.fileInput.files?.length) importFiles(elements.fileInput.files);
});
elements.scanButton.addEventListener("click", scanFolder);
elements.recognizeButton.addEventListener("click", () =>
  analyzeAssets(currentAnalyzeIds()),
);
elements.batchAnalyzeButton.addEventListener("click", () =>
  analyzeAssets([...state.selectedIds]),
);
elements.clearSelectionButton.addEventListener("click", () => {
  state.selectedIds.clear();
  renderGallery();
  renderBatchBar();
});
elements.retryLoadButton.addEventListener("click", () =>
  loadBootstrap({ preserveSelection: false }),
);
elements.queueToggle.addEventListener("click", () => {
  state.queueExpanded = !state.queueExpanded;
  renderQueue();
});
elements.newCollectionButton.addEventListener("click", () => {
  elements.collectionForm.reset();
  showDialog(elements.collectionDialog);
  requestAnimationFrame(() => elements.collectionName.focus());
});

elements.collectionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = elements.collectionName.value.trim();
  if (!name) return;
  const submit = elements.collectionForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    await createCollection(name);
    closeDialog(elements.collectionDialog);
    elements.collectionForm.reset();
    notify(`已建立收藏集「${name}」。`);
  } catch (error) {
    notify(`無法建立收藏集：${error.message}`, "error");
  } finally {
    submit.disabled = false;
  }
});

elements.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = elements.settingsForm.querySelector('[type="submit"]');
  submit.disabled = true;
  const original = submit.textContent;
  submit.textContent = "儲存中…";
  try {
    state.settings = asObject(
      await api("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({
          codexModel: elements.settingCodexModel.value.trim(),
        }),
      }),
    );
    await refreshProvider();
    closeDialog(elements.settingsDialog);
    notify("Codex 設定已儲存。");
  } catch (error) {
    notify(`設定儲存失敗：${error.message}`, "error");
  } finally {
    submit.disabled = false;
    submit.textContent = original;
  }
});

elements.retryNeedsSetupButton.addEventListener("click", async () => {
  const button = elements.retryNeedsSetupButton;
  button.disabled = true;
  try {
    const result = await api("/api/jobs/retry-needs-setup", {
      method: "POST",
      body: JSON.stringify({}),
    });
    await Promise.allSettled([refreshProvider(), refreshJobs()]);
    notify(`已將 ${formatNumber(result?.retried ?? 0)} 項工作重新排入 Codex 佇列。`);
  } catch (error) {
    notify(`無法重試工作：${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-metadata-form]");
  if (!form) return;
  event.preventDefault();
  saveMetadata(form);
});

document.addEventListener("click", async (event) => {
  const target = event.target;
  const openAssetButton = target.closest("[data-open-asset]");
  if (openAssetButton) {
    const id = openAssetButton.dataset.openAsset;
    if (event.shiftKey) selectBatchRange(id);
    else if (event.ctrlKey || event.metaKey) toggleBatch(id);
    await selectAsset(id);
    return;
  }

  const batchButton = target.closest("[data-batch-id]");
  if (batchButton) {
    toggleBatch(batchButton.dataset.batchId);
    return;
  }

  const collectionButton = target.closest("[data-collection-id]");
  if (collectionButton) {
    await openCollection(collectionButton.dataset.collectionId);
    return;
  }

  const actionTarget = target.closest("[data-action]");
  if (actionTarget) {
    const action = actionTarget.dataset.action;
    if (action === "queue") {
      state.queueExpanded = true;
      renderQueue();
      elements.queueBar.scrollIntoView({ block: "end" });
    } else if (action === "settings") {
      await openSettings();
    } else if (action === "new-collection") {
      elements.collectionForm.reset();
      showDialog(elements.collectionDialog);
      requestAnimationFrame(() => elements.collectionName.focus());
    } else if (action === "import") {
      elements.fileInput.click();
    } else if (action === "clear-filters") {
      clearFilters();
    }
    return;
  }

  const viewButton = target.closest("[data-view]");
  if (viewButton) {
    state.view = viewButton.dataset.view;
    state.activeCollectionId = null;
    state.selectedId = null;
    if (state.view === "collections") renderAll();
    else {
      await refreshAssets();
      closeInspector();
    }
    elements.workspace.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  if (target.closest("[data-close-inspector]")) {
    closeInspector();
    return;
  }

  const analyzeButton = target.closest("[data-analyze-id]");
  if (analyzeButton) {
    await analyzeAssets([analyzeButton.dataset.analyzeId]);
    return;
  }

  const copyButton = target.closest("[data-copy-prompt]");
  if (copyButton) {
    await copyPrompt(copyButton.dataset.copyPrompt);
    return;
  }

  const addCollectionButton = target.closest("[data-add-to-collection]");
  if (addCollectionButton) {
    const select = document.querySelector("#inspector-collection-select");
    try {
      await addToCollection(
        addCollectionButton.dataset.addToCollection,
        select?.value || "",
      );
    } catch (error) {
      notify(`無法加入收藏集：${error.message}`, "error");
    }
    return;
  }

  const removeCollectionButton = target.closest("[data-remove-collection]");
  if (removeCollectionButton) {
    try {
      await removeFromCollection(
        removeCollectionButton.dataset.assetId,
        removeCollectionButton.dataset.removeCollection,
      );
    } catch (error) {
      notify(`無法移出收藏集：${error.message}`, "error");
    }
    return;
  }

  const closeDialogButton = target.closest("[data-close-dialog]");
  if (closeDialogButton) {
    closeDialog(closeDialogButton.closest("dialog"));
  }
});

document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement)) return;
    image.alt = `${image.alt || "影像"}（無法讀取）`;
    image.hidden = true;
    const placeholder = document.createElement("span");
    placeholder.className = "queue-placeholder-thumb";
    placeholder.setAttribute("aria-hidden", "true");
    image.after(placeholder);
  },
  true,
);

document.addEventListener("keydown", (event) => {
  if (trapMobileInspectorFocus(event)) return;
  if (event.key === "/" && !isTypingTarget(event.target)) {
    event.preventDefault();
    elements.searchInput.focus();
    return;
  }
  if (event.key === "Escape" && state.selectedId) {
    closeInspector();
    return;
  }
  if (isTypingTarget(event.target) || document.querySelector("dialog[open]")) {
    return;
  }
  if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
    event.preventDefault();
    moveSelection(-1);
  } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
    event.preventDefault();
    moveSelection(1);
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  } else if (!state.pollTimer) {
    refreshJobs();
    state.pollTimer = window.setInterval(refreshJobs, 5500);
  }
});

state.syntheticAssets = createSyntheticStudies().map(normalizeAsset);
loadBootstrap({ preserveSelection: false });
state.pollTimer = window.setInterval(refreshJobs, 5500);
