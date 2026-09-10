import { request, connect, upload, download } from "./api.js";
import {
  $,
  $$,
  esc,
  icon,
  field,
  clock,
  shortTime,
  total,
  duration,
  mappedCaptions,
} from "./utils.js";
import { Preview } from "./preview.js";
import { Timeline } from "./timeline.js";
import { panelHTML, inspectorHTML } from "./panels.js";
import { AgentWorkspace } from "./agent-workspace.js";
import { transcriptRows, selectedCharacters, copyClips } from "./transcript-edit.js";
import { clipAtPlayhead, playheadShortcut } from "./playhead-edit.js";

const state = {
  project: null,
  mode: "media",
  mediaId: null,
  selected: null,
  selectedIds: [],
  selectedType: "clip",
  smartTab: "settings",
  inspectorTab: "basic",
  plan: null,
  checked: new Set(),
  busy: false,
  time: 0,
  doctor: null,
  observationRange: null,
  skipCutConfirm: localStorage.getItem("shijian-skip-caption-cut-confirm") === "true",
  smartOptions: {
    threshold_db: -35,
    min_silence: 0.5,
    keep_pause: 0.2,
    detect_fillers: true,
    detect_repeats: true,
  },
};
let preview, timeline, pollTimer, modalCallback;
let clipClipboard = null;
const modes = [
  ["media", "folder", "素材"],
  ["smart", "cut", "智能剪口播"],
  ["captions", "captions", "字幕"],
  ["audio", "audio", "音訊"],
  ["text", "text", "文字"],
  ["effects", "sliders", "調色"],
  ["agent", "agent", "Agent"],
];
const apiPath = (suffix = "") => `/projects/${state.project.id}${suffix}`;

function toast(message, error = false) {
  const el = document.createElement("div");
  el.className = `toast ${error ? "error" : ""}`;
  el.innerHTML = `${icon(error ? "help" : "check", 18)}<span>${esc(message)}</span><button aria-label="關閉通知">${icon("close", 14)}</button>`;
  el.querySelector("button").onclick = () => el.remove();
  $("#toasts").append(el);
  setTimeout(() => el.remove(), error ? 14000 : 4500);
}
function status(message, progress) {
  const el = $("#work-status");
  if (el) el.textContent = message;
  const bar = $("#job-progress");
  if (bar) {
    bar.hidden = progress === undefined;
    if (progress !== undefined) bar.value = progress;
  }
}
function dialog(title, body, cls = "") {
  preview?.pause();
  const d = $("#dialog");
  d.className = cls;
  d.innerHTML = `<div class="dialog-heading"><h2 id="dialog-title">${title}</h2><button class="icon-button" data-action="close-dialog" aria-label="關閉視窗">${icon("close", 19)}</button></div><div class="dialog-body">${body}</div>`;
  d.setAttribute("aria-labelledby", "dialog-title");
  if (!d.open) d.showModal();
  return d;
}
function closeDialog() {
  for (const n of $$("video,audio", $("#dialog"))) n.pause();
  $("#dialog").close();
  modalCallback = null;
}
function formData(form) {
  const result = {};
  for (const [key, value] of new FormData(form)) {
    const input = form.elements.namedItem(key);
    result[key] =
      input.type === "number" || input.type === "range" ? Number(value) : value;
  }
  for (const el of $$("input[type=checkbox]", form))
    result[el.name] = el.checked;
  return result;
}
async function guarded(fn) {
  if (state.busy) {
    toast("目前工作正在處理，完成後即可繼續修改。");
    return;
  }
  state.busy = true;
  document.body.classList.add("working");
  try {
    return await fn();
  } catch (e) {
    toast(e.message, true);
    status("操作未完成");
    if (e.status === 409 && state.project) {
      const fresh = await request(apiPath());
      accept(fresh);
    }
  } finally {
    state.busy = false;
    document.body.classList.remove("working");
  }
}
async function edit(action, params = {}, message) {
  const result = await request(apiPath("/edit"), {
    expected_version: state.project.version,
    action,
    params,
  });
  accept(result);
  if (result.warnings?.length) toast(result.warnings.map(w => typeof w === "string" ? w : w.message || w.code).join("\n"), true);
  if (message) toast(message);
  return result;
}
function accept(project) {
  state.project = project;
  state.selectedIds = state.selectedIds.filter(id => project.clips.some(c => c.id === id));
  if (state.selectedType === "clip") state.selected = state.selectedIds[0] || null;
  if (!project.media.some((m) => m.id === state.mediaId))
    state.mediaId =
      project.media.find((m) => m.kind === "video")?.id ||
      project.media[0]?.id ||
      null;
  if (
    state.plan &&
    state.plan.base_version !== undefined &&
    state.plan.base_version !== project.version
  )
    state.plan = null;
  localStorage.setItem("shijian-project", project.id);
  renderPanels();
  preview.setProject(project);
  timeline.setProject(project, state.selected, state.selectedIds);
  updateHeader();
  status("已儲存至本機");
  agentWorkspace?.publish(true);
}
function updateHeader() {
  const p = state.project;
  $("#project-name").textContent = p.name;
  $("#version-label").textContent = `v${p.version}`;
  $("#project-meta").textContent = `${p.width} × ${p.height} · ${p.fps} fps`;
  $("#undo-button").disabled = !p.history?.undo_count;
  $("#redo-button").disabled = !p.history?.redo_count;
  $("#total-time").textContent = clock(total(p), true);
  $("#export-button").disabled = !p.clips.length;
}
function renderPanels() {
  if (!state.project) return;
  $("#side-panel").innerHTML = panelHTML(state.mode, state.project, state);
  $("#inspector").innerHTML = inspectorHTML(state.project, state);
  $$(".rail-button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === state.mode);
    b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode));
  });
  $("#workspace").classList.toggle(
    "speech-mode",
    state.mode === "smart" || state.mode === "captions",
  );
  bindPanelEvents();
  if (state.mode === "agent") refreshEvents();
}
function select(id, type = "clip") {
  state.selected = id;
  state.selectedType = type;
  state.selectedIds = type === "clip" && id ? [id] : [];
  timeline.selected = id;
  timeline.setSelection(state.selectedIds);
  $("#inspector").innerHTML = inspectorHTML(state.project, state);
  if (type === "clip") {
    const c = state.project.clips.find((c) => c.id === id);
    if (c) {
      state.mediaId = c.media_id;
      if (["smart", "captions"].includes(state.mode)) renderPanels();
    }
  }
  if (window.innerWidth < 1080) $("#inspector").classList.add("mobile-open");
}
function selectMany(ids) {
  state.selectedIds = [...new Set(ids)].filter(id => state.project.clips.some(c => c.id === id));
  if (state.selectedIds.length === 1) return select(state.selectedIds[0]);
  state.selected = state.selectedIds[0] || null;
  state.selectedType = "clip";
  timeline.setSelection(state.selectedIds);
  $("#inspector").innerHTML = inspectorHTML(state.project, state);
  if (state.selectedIds.length && window.innerWidth < 1080) $("#inspector").classList.add("mobile-open");
}
function seek(t) {
  preview.seek(t);
}
function seekCaption(id) {
  const row = transcriptRows(state.project).find(c => c.id === id);
  if (!row) return;
  preview.pause();
  seek(row.start);
  timeline?.revealTime(row.start);
}
function trimAtPlayhead(side) {
  return guarded(async () => {
    preview.pause();
    const at = state.time, clip = clipAtPlayhead(state.project, at);
    if (!clip) throw new Error("請把播放頭移到主影片片段內部再修剪。");
    const ripple = $("#ripple-delete").checked;
    await edit("clip_trim_at", { clip_id: clip.id, at, side, ripple },
      side === "before" ? "已剪除目前片段在播放頭之前的內容，可一次復原" : "已剪除目前片段在播放頭之後的內容，可一次復原");
    seek(side === "before" && ripple ? clip.offset : at);
    timeline?.revealTime(state.time);
    timeline?.rebaseScrub();
  });
}
function cutTranscript(row, selection = null) {
  if (!row) return;
  const version = state.project.version, projectId = state.project.id;
  const params = { caption_id: row.source_caption_id, clip_id: row.clip_id, text: row.text,
    ...(selection ? { selection } : {}) };
  const run = () => guarded(async () => {
    if (state.project.id !== projectId || state.project.version !== version)
      throw new Error("專案已更新，請重新選取要剪除的詞句。");
    const skip = $("#skip-caption-cut-confirm")?.checked;
    const result = await edit("caption_cut", params, "已剪除詞句與對應影片，可用 Ctrl＋Z 復原");
    if (skip) {
      state.skipCutConfirm = true;
      localStorage.setItem("shijian-skip-caption-cut-confirm", "true");
      renderPanels();
    }
    closeDialog();
    return result;
  });
  if (state.skipCutConfirm) return run();
  const selected = selection ? Array.from(row.text).slice(selection.start, selection.end).join("") : row.text;
  dialog("剪除詞句", `<p class="quote">${esc(selected)}</p><p>剪除目前這段中的對應影片，後方內容與其他軌道會同步前移，可用 Ctrl＋Z 復原。</p>${selection ? '<p class="hint">字內切點依詞級時間估算，剪後可播放確認。</p>' : ''}<label class="check-row"><input id="skip-caption-cut-confirm" type="checkbox"><span>之後不要再跳出這個視窗</span></label><button class="button primary full" data-action="confirm-caption-cut">剪除詞句與影片</button>`);
  actions["confirm-caption-cut"] = run;
}
function onTime(t) {
  state.time = t;
  timeline?.setTime(t);
  const text = $("#current-time");
  if (text) text.textContent = clock(t, true);
  const slider = $("#seek-slider");
  if (slider) {
    slider.max = Math.max(0.1, total(state.project));
    slider.value = t;
  }
}

async function home() {
  clearInterval(pollTimer);
  timeline?.dispose();
  preview?.destroy();
  preview = null;
  timeline = null;
  state.project = null;
  state.observationRange = null;
  agentWorkspace?.publish(true);
  const data = await request("/projects");
  $("#app").innerHTML =
    `<div class="home-shell"><header class="home-header"><div class="brand"><b>迅剪</b><span>LOCAL STUDIO</span></div><span class="local-indicator"><span class="status-dot"></span>你的素材，留在你的電腦</span><button class="icon-button" data-action="doctor" aria-label="檢查本機環境">${icon("sliders", 19)}</button></header><main class="project-home"><div class="home-intro"><span class="section-label">本地剪輯工作台</span><h1>把想說的，<br>剪成好故事。</h1><p>從一段口播開始。精剪停頓、校正字幕，<br>在同一張時間軸上，完成你的作品。</p><button class="button primary large" data-action="new-project">${icon("plus", 20)}建立新專案</button><div class="home-shortcuts"><span>${icon("cut", 17)}智能剪口播</span><span>${icon("captions", 17)}繁體中文字幕</span><span>${icon("agent", 17)}MCP 入口</span></div></div><section class="project-list"><div class="project-list-heading"><h2>最近的專案</h2><span>${data.projects.length} 個專案</span></div>${data.projects.length ? data.projects.map((p) => `<button class="project-item" data-open-project="${esc(p.id)}"><span class="project-cover">${icon("film", 27)}</span><span><strong>${esc(p.name)}</strong><small>${new Date(p.updated_at).toLocaleString("zh-TW")} · ${p.width || 1920} × ${p.height || 1080}</small></span>${icon("chevron", 18)}</button>`).join("") : `<div class="no-projects">${icon("folder", 38)}<h3>你的第一部作品，從這裡開始</h3><p>建立專案後即可匯入影片。<br>所有修改會自動儲存至本機。</p></div>`}<div class="home-footnote"><span class="status-dot"></span>無需登入 · 本機儲存 · 可復原剪輯</div></section></main><footer class="home-footer">迅剪 Local Studio <span>專注創作，保留掌控。</span></footer></div>`;
}
function newProject() {
  dialog(
    "建立新專案",
    `<form id="new-project-form">${field("專案名稱", "name", "未命名專案", 'required maxlength="200" autocomplete="off"')}<label class="field"><span>畫面比例</span><select name="resolution"><option value="1920,1080">橫式 16:9 · YouTube／課程</option><option value="1080,1920">直式 9:16 · Reels／Shorts</option><option value="1080,1080">方形 1:1 · 社群影片</option></select></label><p class="hint">之後可在專案設定調整。</p><button class="button primary full spaced">建立並開始剪輯</button></form>`,
  );
}
async function openProject(id) {
  timeline?.dispose();
  state.selected = null;
  state.selectedIds = [];
  state.observationRange = null;
  state.plan = null;
  state.checked.clear();
  state.mode = "media";
  preview?.destroy();
  const p = await request(`/projects/${id}`);
  state.project = p;
  $("#app").innerHTML =
    `<div class="editor-shell"><header class="topbar"><button class="brand brand-button" data-action="home" title="返回專案首頁"><b>迅剪</b></button><div class="top-divider"></div><button class="project-title" data-action="rename" title="重新命名專案"><span id="project-name"></span>${icon("chevron", 12)}</button><span class="saved-indicator">${icon("check", 14)}已儲存 <span id="version-label"></span></span><div class="top-spacer"></div><button id="undo-button" class="icon-button" data-action="undo" title="復原 Ctrl+Z" aria-label="復原">${icon("undo", 18)}</button><button id="redo-button" class="icon-button" data-action="redo" title="重做 Ctrl+Shift+Z" aria-label="重做">${icon("redo", 18)}</button><div class="top-divider"></div><button class="button ghost mcp-button" data-mode="agent">${icon("agent", 17)}MCP</button><button class="icon-button" data-action="help" title="操作說明" aria-label="操作說明">${icon("help", 19)}</button><button id="export-button" class="button primary" data-action="export">${icon("download", 17)}匯出</button></header><main id="workspace" class="workspace"><nav class="tool-rail" aria-label="剪輯工具">${modes.map(([key, glyph, label]) => `<button class="rail-button ${key === state.mode ? "active" : ""}" data-mode="${key}" aria-pressed="${key === state.mode}">${icon(glyph, 22)}<span>${label}</span></button>`).join("")}<div class="rail-spacer"></div><button class="rail-button" data-action="doctor">${icon("sliders", 20)}<span>環境</span></button></nav><aside id="side-panel" class="side-panel"></aside><section class="preview-panel" aria-label="影片預覽"><div class="preview-toolbar"><h2>播放器</h2><span id="project-meta"></span><button class="icon-button inspector-toggle" data-action="toggle-inspector" aria-label="切換屬性面板">${icon("sliders", 17)}</button></div><div class="preview-viewport"><div id="preview-stage" class="preview-stage"><div id="preview-empty" class="preview-empty">${icon("film", 38)}<h3>預覽你的下一部作品</h3><p>先匯入素材，再加入時間軸</p><button class="button" data-action="import">${icon("plus", 16)}匯入素材</button></div></div></div><div class="player-controls"><div class="time-display"><strong id="current-time">00:00:00.000</strong><span>／</span><span id="total-time">00:00:00.000</span></div><div class="transport"><button class="icon-button" data-action="start" aria-label="返回開頭" title="返回開頭">${icon("prev", 18)}</button><button id="play-button" class="play-button" data-action="play" aria-label="播放／暫停" title="播放／暫停（空白鍵）">${icon("play", 22)}</button><button class="icon-button" data-action="end" aria-label="跳至結尾" title="跳至結尾">${icon("next", 18)}</button></div><button class="icon-button" data-action="fullscreen" title="全螢幕預覽" aria-label="全螢幕預覽">${icon("fit", 18)}</button></div><input id="seek-slider" class="seek-slider" type="range" min="0" max="1" step="any" value="0" aria-label="播放位置"></section><aside id="inspector" class="inspector"></aside></main><section class="timeline-section" aria-label="剪輯時間軸"><div class="timeline-toolbar"><div class="toolbar-group"><button class="icon-button" data-action="split" title="在播放頭分割（S）" aria-label="分割片段">${icon("cut", 18)}</button><button class="icon-button" data-action="duplicate" title="複製片段" aria-label="複製片段">${icon("copy", 18)}</button><button class="icon-button" data-action="delete" title="刪除選取片段（Delete）" aria-label="刪除片段">${icon("trash", 18)}</button><div class="top-divider"></div><label class="inline-check"><input id="ripple-delete" type="checkbox">連動刪除</label><label class="inline-check"><input id="snap-toggle" type="checkbox" checked>吸附</label></div><span class="timeline-help">拖曳移動 · 邊緣修剪 · S 分割</span><div class="toolbar-group zoom-controls">${icon("zoom", 16)}<input id="zoom-slider" type="range" min="15" max="180" value="55" aria-label="時間軸縮放"><button class="icon-button" data-action="fit-timeline" title="符合時間軸寬度" aria-label="符合時間軸寬度">${icon("fit", 17)}</button></div></div><div id="timeline"></div></section><footer class="statusbar"><span class="status-dot"></span><span id="work-status">已儲存至本機</span><progress id="job-progress" aria-label="背景工作進度" max="100" hidden></progress><div class="top-spacer"></div><button class="text-button" data-action="jobs">${icon("download", 13)}工作紀錄</button><span>繁體中文</span><span>本機模式</span></footer></div>`;
  preview = new Preview($("#preview-stage"), onTime, (playing) => {
    const b = $("#play-button");
    if (b) b.innerHTML = icon(playing ? "pause" : "play", 22);
  });
  timeline = new Timeline($("#timeline"), {
    onSeek: seek,
    onSelect: select,
    onSelectMany: selectMany,
    onMoveMany: (ids, delta) => guarded(() => edit("clip_move_many", { clip_ids: ids, delta }, `已移動 ${ids.length} 段，可一次復原`)),
    onTrim: (c, edge, delta) =>
      guarded(() => {
        const speed = c.speed || 1;
        const changes =
          edge === "start"
            ? { start: c.start + delta * speed, offset: c.offset + delta }
            : { end: c.end + delta * speed };
        return edit("clip_update", { clip_id: c.id, changes });
      }),
    onAdd: (id, track, offset) => guarded(() => addMedia(id, track, offset)),
  });
  $("#seek-slider").oninput = (e) => seek(+e.target.value);
  $("#zoom-slider").oninput = (e) => timeline.setZoom(+e.target.value);
  $("#snap-toggle").onchange = (e) => (timeline.snapping = e.target.checked);
  $('[data-action="duplicate"]').title = "複製選取片段（Ctrl＋C）";
  $('[data-action="duplicate"]').insertAdjacentHTML("afterend", '<button class="icon-button" data-action="paste" title="貼至播放位置（Ctrl＋V）" aria-label="貼上片段">'+icon("paste",18)+'</button>');
  $("#ripple-delete").checked = true;
  $("#snap-toggle").closest("label").insertAdjacentHTML("afterend", '<label class="inline-check" title="從軌道空白處拖拉框選；也可按住 Shift 暫時框選"><input id="marquee-toggle" type="checkbox" checked>框選</label><span id="timeline-selection-count" class="selection-count" aria-live="polite"></span>');
  $("#marquee-toggle").onchange = e => {
    timeline.marqueeMode = e.target.checked;
    timeline.root.classList.toggle("marquee-mode", e.target.checked);
  };
  $(".timeline-toolbar > .timeline-help").textContent = "空白處拖拉播放頭 · Shift 拖曳框選 · Ctrl 點選增減";
  accept(p);
  clearInterval(pollTimer);
  pollTimer = setInterval(syncExternal, 3500);
}
async function syncExternal() {
  if (
    !state.project ||
    state.busy ||
    $("#dialog").open ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
  )
    return;
  try {
    const p = await request(apiPath());
    if (p.version !== state.project.version) {
      accept(p);
      toast("已同步 Agent 或另一個視窗的修改。");
    }
    if (state.mode === "agent") refreshEvents();
  } catch {
    status("本機服務連線中斷，正在重試…");
  }
}
async function addMedia(id, track, offset) {
  const m = state.project.media.find((m) => m.id === id);
  track = track || (m.kind === "audio" ? "audio" : "video");
  offset =
    offset ??
    Math.max(
      0,
      ...state.project.clips
        .filter((c) => c.track === track)
        .map((c) => c.offset + duration(c)),
    );
  const p = await edit(
    "clip_add",
    {
      media_id: id,
      track,
      start: 0,
      end: m.kind === "image" ? 5 : m.duration,
      offset,
    },
    "已加入時間軸",
  );
  select(p.clips.at(-1).id);
}
async function importFiles(files) {
  await guarded(async () => {
    for (const file of files) {
      status(`正在匯入 ${file.name}`, 0);
      const p = await upload(state.project, file, (n) =>
        status(`正在複製 ${file.name}`, n * 100),
      );
      accept(p);
    }
    toast(`已匯入 ${files.length} 個素材；點選＋加入時間軸。`);
  });
}
function bindPanelEvents() {
  const panel = $("#side-panel");
  $("#source-media")?.addEventListener("change", (e) => {
    if (state.busy) {
      e.target.value = state.mediaId;
      return toast("請等待目前工作完成。");
    }
    state.mediaId = e.target.value;
    state.plan = null;
    state.checked.clear();
    renderPanels();
  });
  $("#media-search")?.addEventListener("input", (e) =>
    $$("[data-name]", panel).forEach(
      (el) =>
        (el.hidden = !el.dataset.name.includes(e.target.value.toLowerCase())),
    ),
  );
  $("#caption-search")?.addEventListener("input", (e) =>
    $$("[data-caption-row]", panel).forEach(
      (el) =>
        (el.hidden = !el.dataset.text.includes(e.target.value.toLowerCase())),
    ),
  );
  $$("[draggable]", panel).forEach(
    (el) =>
      (el.ondragstart = (e) =>
        e.dataTransfer.setData("application/x-editor-media", el.dataset.media)),
  );
  panel.ondragover = (e) => {
    if (e.dataTransfer.types.includes("Files")) {
      e.preventDefault();
      panel.classList.add("file-hover");
    }
  };
  panel.ondragleave = (e) => {
    if (!panel.contains(e.relatedTarget)) panel.classList.remove("file-hover");
  };
  panel.ondrop = (e) => {
    e.preventDefault();
    panel.classList.remove("file-hover");
    if (e.dataTransfer.files.length) importFiles([...e.dataTransfer.files]);
  };
  $$("[data-candidate]", panel).forEach(
    (el) =>
      (el.onchange = () => {
        el.checked
          ? state.checked.add(el.dataset.candidate)
          : state.checked.delete(el.dataset.candidate);
        renderPanels();
      }),
  );
  $("#select-all-cuts")?.addEventListener("change", (e) => {
    state.checked = new Set(
      e.target.checked ? state.plan.candidates.map((c) => c.id) : [],
    );
    renderPanels();
  });
}

async function waitJob(job, label) {
  const projectId = state.project.id;
  localStorage.setItem("shijian-last-job", job.id);
  while (job.status === "queued" || job.status === "running") {
    status(job.message || label, job.progress || 0);
    const bar = $("#export-progress");
    if (bar) {
      bar.value = job.progress || 0;
      $("#export-status").textContent = job.message || label;
    }
    await new Promise((r) => setTimeout(r, 850));
    job = await request(`/jobs/${job.id}`);
  }
  status(job.status === "succeeded" ? "工作已完成" : "工作失敗");
  if (job.status === "failed")
    throw new Error(job.error?.message || "背景工作未完成");
  return job.result;
}
function sourceDialog(mediaId, start = 0, end) {
  const m = state.project.media.find((m) => m.id === mediaId);
  if (!m) return;
  const d = dialog(
    "來源素材預覽",
    `${m.kind === "image" ? `<img class="source-viewer" src="${esc(m.url)}" alt="${esc(m.name)}">` : `<${m.kind === "audio" ? "audio" : "video"} id="source-player" class="source-viewer" controls preload="metadata" src="${esc(m.url)}"></${m.kind === "audio" ? "audio" : "video"}>`}<p class="hint">${esc(m.name)} · ${shortTime(start)}${end !== undefined ? ` — ${shortTime(end)}` : ""} · 原始素材</p>`,
    "wide-dialog",
  );
  const v = $("#source-player");
  if (v) {
    const ready = () => {
      v.currentTime = start;
      v.play().catch(() => {});
    };
    v.addEventListener("loadedmetadata", ready, { once: true });
    if (end !== undefined)
      v.ontimeupdate = () => {
        if (v.currentTime >= end) v.pause();
      };
  }
}
function transcribeDialog() {
  if (!state.mediaId) return toast("請先匯入口播素材。", true);
  dialog(
    "本機語音辨識",
    `<form id="transcribe-form"><p>使用本機 Whisper 模型產生時間戳記與逐字稿。影片不會上傳。</p>${field("本機模型目錄（留空自動尋找）", "model_path", "", 'placeholder=".local-editor/models/faster-whisper-small"')}<div class="field-pair"><label class="field"><span>語言</span><select name="language"><option value="zh">中文</option><option value="en">英文</option><option value="auto">自動偵測</option></select></label><label class="field"><span>運算裝置</span><select name="device"><option value="cpu">CPU · int8</option><option value="cuda">NVIDIA GPU · CUDA</option></select></label></div><p class="note">首次請執行 scripts/setup-local-asr.ps1 安裝模型。辨識後仍需人工校正人名、專有名詞與口語內容。</p><button class="button primary full spaced">${icon("captions", 16)}開始辨識</button></form>`,
  );
}
function exportDialog() {
  if (!state.project.clips.length) return toast("請先把素材加入時間軸。");
  dialog(
    "匯出影片",
    `<form id="export-form"><div class="export-summary">${icon("film", 32)}<div><strong>${esc(state.project.name)}</strong><span>${clock(total(state.project))} · ${state.project.clips.length} 個片段</span></div></div><label class="field"><span>解析度</span><select name="resolution"><option value="original">專案尺寸 · ${state.project.width} × ${state.project.height}</option><option value="720">720p · 較小檔案</option><option value="1080">1080p · Full HD</option></select></label><label class="field"><span>畫質</span><select name="crf"><option value="20">高畫質（CRF 20）</option><option value="23">標準（CRF 23）</option><option value="28">精簡（CRF 28）</option></select></label><label class="check-row"><input type="checkbox" name="burn_captions" checked><span>將字幕燒錄至影片<small>文字標題也會一併輸出</small></span></label><p class="hint">H.264 / AAC · MP4 · ${state.project.fps} fps<br>匯出到本機專案資料夾，可在完成後下載。</p><button class="button primary full spaced">${icon("download", 17)}開始匯出</button></form>`,
  );
}
async function refreshEvents() {
  agentWorkspace?.refresh();
  try {
    const result = await request("/events");
    const el = $("#event-list");
    if (el)
      el.innerHTML =
        result.events
          .slice(0, 8)
          .map(
            (e) =>
              `<div class="event-row"><span class="badge">${esc(e.actor)}</span><span>${esc(e.action)}</span><small>${new Date(e.time * 1000).toLocaleTimeString("zh-TW")}</small></div>`,
          )
          .join("") || '<p class="hint">尚無操作紀錄。</p>';
  } catch {}
}
async function doctorDialog() {
  dialog("本機環境", "<p>正在檢查 FFmpeg 與語音模型…</p>");
  try {
    const d = await request("/doctor");
    state.doctor = d;
    $("#dialog .dialog-body").innerHTML =
      `<div class="doctor-list">${["ffmpeg", "ffprobe"].map((k) => `<div class="doctor-row"><b>${k}</b><span class="${d[k]?.available ? "ok" : "error-text"}">${d[k]?.available ? "可使用" : "未就緒"}</span></div>`).join("")}<div class="doctor-row"><b>語音辨識引擎</b><span>${d.transcription?.available ? "已安裝" : "尚未安裝"}</span></div><div class="doctor-row"><b>本機語音模型</b><span>${d.transcription?.model_ready ? "已就緒" : "請執行模型安裝腳本"}</span></div></div><p class="hint">${esc(d.transcription?.note || "辨識模型保持離線載入。")}</p><h3 class="section-label">資料位置</h3><pre class="code-block">${esc(d.data_dir)}</pre><p class="note">模型安裝：在專案目錄執行 scripts/setup-local-asr.ps1。<br>FFmpeg 缺少時請安裝後重新啟動本地工作台。</p>`;
  } catch (e) {
    $("#dialog .dialog-body").textContent = e.message;
  }
}

const actions = {
  home: () => home(),
  "new-project": newProject,
  "close-dialog": closeDialog,
  rename: () =>
    dialog(
      "重新命名專案",
      `<form id="rename-form">${field("專案名稱", "name", state.project.name, 'required maxlength="200"')}<button class="button primary full">儲存名稱</button></form>`,
    ),
  import: () => $("#media-input").click(),
  "import-path": () =>
    dialog(
      "從本機路徑匯入",
      `<form id="path-form">${field("影片、音訊或圖片的完整路徑", "path", "", 'required placeholder="D:\\影片\\口播.mp4"')}<p class="hint">會建立本機副本，原始素材保持完整。</p><button class="button primary full">匯入素材</button></form>`,
    ),
  undo: () => guarded(() => edit("undo", {}, "已復原上一個操作")),
  redo: () => guarded(() => edit("redo", {}, "已重做操作")),
  play: () => preview.toggle(),
  start: () => seek(0),
  end: () => seek(total(state.project)),
  fullscreen: () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else
      $(".preview-panel")
        .requestFullscreen()
        .catch(() => toast("此瀏覽器不支援全螢幕預覽。"));
  },
  split: () =>
    guarded(async () => {
      preview.pause();
      const c = clipAtPlayhead(state.project, state.time);
      if (!c) throw new Error("請把播放頭移到片段內部再分割。");
      await edit(
        "clip_split",
        { clip_id: c.id, at: state.time },
        "已在播放頭分割片段",
      );
    }),
  "trim-before": () => trimAtPlayhead("before"),
  "trim-after": () => trimAtPlayhead("after"),
  duplicate: () =>
    guarded(async () => {
      const copied = copyClips(state.project, state.selectedIds);
      if (!copied) throw new Error("請先選取時間軸片段。");
      clipClipboard = copied;
      toast(`已複製 ${copied.clips.length} 段，移動播放頭後按 Ctrl＋V 貼上`);
    }),
  paste: () => guarded(async () => {
    if (!clipClipboard || clipClipboard.projectId !== state.project.id)
      throw new Error("請先複製目前專案中的片段。");
    const oldIds = new Set(state.project.clips.map(c => c.id));
    const at = state.time;
    const result = await edit("clip_paste", { at, clips: clipClipboard.clips }, "已貼至播放位置並推移後方片段，可一次復原");
    const copies = result.clips.slice(-clipClipboard.clips.length);
    selectMany(copies.filter(c => !oldIds.has(c.id)).map(c => c.id));
  }),
  "reset-caption-confirm": () => {
    state.skipCutConfirm = false;
    localStorage.removeItem("shijian-skip-caption-cut-confirm");
    renderPanels();
    toast("已恢復剪除確認視窗");
  },
  delete: () =>
    guarded(async () => {
      if (state.selectedIds.length > 1) {
        await edit("clip_delete_many", { clip_ids: [...state.selectedIds], ripple: $("#ripple-delete").checked }, "已刪除整組片段，可一次復原");
        selectMany([]);
        return;
      }
      if (!state.selected) throw new Error("請先選取片段或文字。");
      if (state.project.titles.some((t) => t.id === state.selected))
        await edit("title_delete", { title_id: state.selected }, "已刪除文字");
      else if (state.project.captions.some((c) => c.id === state.selected))
        await edit(
          "caption_delete",
          { caption_id: state.selected },
          "已刪除字幕",
        );
      else
        await edit(
          "clip_delete",
          { clip_id: state.selected, ripple: $("#ripple-delete").checked },
          "已刪除片段，可復原",
        );
      state.selected = null;
      selectMany([]);
      renderPanels();
    }),
  "clear-selection": () => {
    selectMany([]);
    renderPanels();
  },
  "toggle-inspector": () => $("#inspector").classList.toggle("mobile-open"),
  "fit-timeline": () => {
    const available = $("#timeline").clientWidth - 150;
    timeline.setZoom(
      Math.max(
        15,
        Math.min(180, available / Math.max(10, total(state.project) + 2)),
      ),
    );
    $("#zoom-slider").value = timeline.zoom;
  },
  transcribe: transcribeDialog,
  "apply-cuts": () =>
    guarded(async () => {
      if (!state.plan) throw new Error("剪輯建議已過期，請重新分析。");
      const id = state.plan.id || state.plan.plan_id;
      await agentWorkspace.prepareOperations([{ action: "smart_cut_apply", params: {
        plan_id: id, candidate_ids: [...state.checked],
      }}], "智能剪口播：套用已選取候選，保留未選取內容。");
    }),
  "import-captions": () => {
    if (!state.mediaId) return toast("請先選擇字幕對應的素材。", true);
    dialog(
      "匯入字幕",
      `<form id="paste-captions-form"><button type="button" class="button full" data-action="choose-caption-file">${icon("folder", 16)}選擇 SRT／VTT 檔案</button><p class="hint">或直接貼上字幕內容：</p><label class="field"><span>SRT／WebVTT</span><textarea name="text" rows="8" required placeholder="1\n00:00:00,000 --> 00:00:02,000\n輸入繁體中文字幕"></textarea></label><button class="button primary full">匯入貼上的字幕</button></form>`,
    );
  },
  "choose-caption-file": () => {
    closeDialog();
    $("#caption-input").click();
  },
  "add-caption": () => {
    if (!state.mediaId) return toast("請先匯入並選擇素材。", true);
    dialog(
      "新增字幕",
      `<form id="add-caption-form"><div class="field-pair">${field("來源開始（秒）", "start", 0, 'type="number" min="0" step="any" required')}${field("來源結束（秒）", "end", 1, 'type="number" min="0" step="any" required')}</div><label class="field"><span>內容</span><textarea name="text" rows="3" required placeholder="輸入字幕內容"></textarea></label><button class="button primary full">新增字幕</button></form>`,
    );
  },
  "replace-captions": () =>
    dialog(
      "尋找與取代",
      `<form id="replace-form">${field("尋找文字", "find", "", "required")}${field("取代為", "replacement", "")}<p class="hint">只修改目前素材的字幕文字，時間戳記保持不變。</p><button class="button primary full">全部取代</button></form>`,
    ),
  "export-captions": () =>
    dialog(
      "匯出字幕",
      `<form id="caption-export-form"><label class="field"><span>格式</span><select name="format"><option value="srt">SRT · 通用字幕</option><option value="vtt">WebVTT · 網頁字幕</option><option value="txt">TXT · 純文字稿</option></select></label><p class="hint">依目前時間軸重新對齊。素材需先加入主影片軌。</p><button class="button primary full">下載字幕</button></form>`,
    ),
  "add-title": () => titleDialog(),
  export: exportDialog,
  doctor: doctorDialog,
  "mcp-config": () => {
    const config = {
      mcpServers: {
        "local-editor": {
          command: "C:/path/to/xunjian-local-video-editor/.venv/Scripts/python.exe",
          args: ["-m", "local_editor", "mcp", "--url", location.origin],
        },
      },
    };
    dialog(
      "連接 MCP",
      `<p>先啟動本地工作台，再把以下設定加入 Claude Code 的 .mcp.json。Codex 設定範例見 docs/local-editor-mcp.md。</p><pre class="code-block">${esc(JSON.stringify(config, null, 2))}</pre><button class="button primary full" data-action="download-mcp-config">下載 .mcp.json 範例</button>`,
    );
    modalCallback = () =>
      download(
        JSON.stringify(config, null, 2),
        "local-editor.mcp.json",
        "application/json",
      );
  },
  "download-mcp-config": () => modalCallback?.(),
  jobs: async () => {
    const r = await request(`/jobs?project_id=${state.project.id}`);
    dialog(
      "工作紀錄",
      r.jobs.length
        ? r.jobs
            .map(
              (j) =>
                `<div class="job-row"><strong>${{ export: "影片匯出", transcribe: "語音辨識", smart_cut: "智能剪口播", "smart-cut": "智能剪口播" }[j.kind] || esc(j.kind)}</strong><span>${{ succeeded: "已完成", running: "執行中", queued: "排隊中", failed: "未完成" }[j.status]}</span>${j.result?.url ? `<a class="text-button" href="${esc(j.result.url)}" download>下載影片</a>` : ""}${j.error ? `<p class="error-text">${esc(j.error.message)}</p>` : ""}</div>`,
            )
            .join("")
        : "<p>尚無背景工作。完成的匯出會保留在這裡。</p>",
    );
  },
  help: () =>
    dialog(
      "剪輯操作說明",
      `<ol class="help-steps"><li><b>匯入素材：</b>支援影片、圖片與音訊；點＋或拖入時間軸。</li><li><b>精剪口播：</b>選擇素材，調整靜音門檻，分析後試聽、勾選並套用。</li><li><b>字幕校正：</b>語音辨識或匯入 SRT／VTT，可修文、改時間與刪文剪片。</li><li><b>編輯畫面：</b>選取片段後，在右側修剪、變速、調色、調音量；拖到 V2 可疊加。</li><li><b>匯出：</b>選擇解析度與字幕燒錄，取得本機 MP4。</li></ol><div class="shortcut-list"><span>播放／暫停<kbd>Space</kbd></span><span>播放頭分割<kbd>S</kbd></span><span>剪除片段前段<kbd>Q</kbd></span><span>剪除片段後段<kbd>W</kbd></span><span>刪除選取<kbd>Delete</kbd></span><span>復原<kbd>Ctrl Z</kbd></span><span>重做<kbd>Ctrl Shift Z</kbd></span><span>逐影格移動<kbd>← →</kbd></span></div><p class="note">瀏覽器預覽為互動近似；正式畫面、混音與字幕由 FFmpeg 匯出。未支援的進階能力與後續架構見專案文件。</p>`,
    ),
};
function titleDialog(preset) {
  dialog(
    "新增文字",
    `<form id="add-title-form">${field("文字內容", "text", preset === "lower" ? "讓每一句話，都剛剛好。" : "你的下一個故事", "required")}<div class="field-pair">${field("開始（秒）", "start", state.time.toFixed(2), 'type="number" min="0" step="any"')}${field("結束（秒）", "end", Math.max(state.time + 0.5, Math.min(state.time + 3, total(state.project) || 3)).toFixed(2), 'type="number" min="0" step="any"')}</div><input type="hidden" name="preset" value="${preset || "heading"}"><button class="button primary full">加入時間軸</button></form>`,
  );
}

document.addEventListener("focusin", (e) => {
  if (state.project && e.target.matches("[data-caption-text]")) seekCaption(e.target.dataset.captionText);
});
document.addEventListener("click", async (e) => {
  const row = e.target.closest("[data-caption-row]");
  if (row && !e.target.closest("button,a")) seekCaption(row.dataset.captionRow);
  const el = e.target.closest("button,a");
  if (!el) return;
  try {
    if (el.dataset.action) {
      if (
        state.busy &&
        [
          "home",
          "new-project",
          "rename",
          "import-path",
          "import-captions",
          "transcribe",
          "export",
        ].includes(el.dataset.action)
      )
        return toast("請等待目前工作完成。");
      await actions[el.dataset.action]?.();
      return;
    }
    if (el.dataset.mode) {
      state.mode = el.dataset.mode;
      if (
        ["smart", "captions"].includes(state.mode) &&
        !state.project.media.some(
          (m) => m.id === state.mediaId && m.kind !== "image",
        )
      )
        state.mediaId =
          state.project.media.find((m) => m.kind === "video")?.id ||
          state.project.media.find((m) => m.kind === "audio")?.id ||
          null;
      renderPanels();
      return;
    }
    if (el.dataset.openProject) {
      if (state.busy) return toast("請等待目前工作完成後再切換專案。");
      await openProject(el.dataset.openProject);
      return;
    }
    if (el.dataset.smartTab) {
      state.smartTab = el.dataset.smartTab;
      renderPanels();
      return;
    }
    if (el.dataset.inspectorTab) {
      state.inspectorTab = el.dataset.inspectorTab;
      $("#inspector").innerHTML = inspectorHTML(state.project, state);
      return;
    }
    if (el.dataset.add) {
      await guarded(() => addMedia(el.dataset.add));
      return;
    }
    if (el.dataset.preview) {
      state.mediaId = el.dataset.preview;
      sourceDialog(el.dataset.preview);
      return;
    }
    if (el.dataset.audition) {
      const c = state.plan.candidates.find((c) => c.id === el.dataset.audition);
      sourceDialog(
        c.media_id || state.mediaId,
        Math.max(0, c.start - 0.25),
        c.end + 0.25,
      );
      return;
    }
    if (el.dataset.captionSeek) {
      seekCaption(el.dataset.captionSeek);
      return;
    }
    if (el.dataset.captionEdit) {
      select(el.dataset.captionEdit, "caption");
      return;
    }
    if (el.dataset.captionCut) {
      cutTranscript(transcriptRows(state.project).find(c => c.id === el.dataset.captionCut));
      return;
    }
    if (el.dataset.captionSelection) {
      const id = el.dataset.captionSelection;
      const input = $$("[data-caption-text]").find(n => n.dataset.captionText === id);
      const selection = selectedCharacters(input.value, input.selectionStart, input.selectionEnd);
      if (!selection) return toast("請先用滑鼠選取要剪除的文字。");
      cutTranscript(transcriptRows(state.project).find(c => c.id === id), selection);
      return;
    }
    if (el.dataset.titlePreset) {
      titleDialog(el.dataset.titlePreset);
      return;
    }
    if (el.dataset.selectTitle) {
      select(el.dataset.selectTitle, "title");
      return;
    }
    if (el.dataset.filter) {
      await guarded(() => {
        if (!state.project.clips.some((c) => c.id === state.selected))
          throw new Error("先選取時間軸片段，再套用調色。");
        const [brightness, contrast, saturation] = el.dataset.filter
          .split(",")
          .map(Number);
        return edit(
          "clip_update",
          {
            clip_id: state.selected,
            changes: { brightness, contrast, saturation },
          },
          "調色已套用，可在屬性微調",
        );
      });
    }
  } catch (err) {
    toast(err.message, true);
  }
});

document.addEventListener("submit", async (e) => {
  if (["agent-brief-form", "agent-range-form", "evidence-review-form"].includes(e.target.id)) return;
  e.preventDefault();
  const form = e.target;
  const data = formData(form);
  await guarded(async () => {
    switch (form.id) {
      case "new-project-form": {
        const [width, height] = data.resolution.split(",").map(Number);
        const p = await request("/projects", {
          name: data.name,
          width,
          height,
        });
        closeDialog();
        await openProject(p.id);
        break;
      }
      case "rename-form":
        await edit("rename", { name: data.name });
        closeDialog();
        break;
      case "paste-captions-form": {
        const p = await request(apiPath("/captions/import"), {
          expected_version: state.project.version,
          media_id: state.mediaId,
          text: data.text,
          format: data.text.trimStart().startsWith("WEBVTT") ? "vtt" : "srt",
        });
        closeDialog();
        accept(p);
        state.mode = "captions";
        renderPanels();
        toast("字幕已匯入");
        break;
      }
      case "path-form": {
        status("正在分析與複製素材…", 0);
        const p = await request(apiPath("/media/import"), {
          expected_version: state.project.version,
          path: data.path.replace(/^"|"$/g, ""),
        });
        closeDialog();
        accept(p);
        toast("素材已匯入，點＋加入時間軸。");
        break;
      }
      case "smart-form": {
        state.smartOptions = data;
        const job = await request(apiPath("/smart-cut"), {
          expected_version: state.project.version,
          media_id: state.mediaId,
          options: data,
        });
        const result = await waitJob(job, "正在分析口播…");
        state.plan = result.plan;
        state.checked = new Set(state.plan.candidates.map((c) => c.id));
        state.smartTab = "results";
        renderPanels();
        toast(`分析完成，找到 ${state.checked.size} 段剪輯建議。`);
        break;
      }
      case "clip-properties": {
        const clip_id = data.clip_id;
        delete data.clip_id;
        await edit("clip_update", { clip_id, changes: data }, "片段屬性已更新");
        break;
      }
      case "title-properties": {
        const title_id = data.title_id;
        delete data.title_id;
        await edit("title_update", { title_id, changes: data }, "文字已更新");
        break;
      }
      case "caption-properties": {
        const caption_id = data.caption_id;
        delete data.caption_id;
        await edit(
          "caption_update",
          { caption_id, changes: data },
          "字幕時間已更新",
        );
        break;
      }
      case "project-properties": {
        const [width, height] = data.resolution.split(",").map(Number);
        await edit(
          "settings",
          { width, height, fps: Number(data.fps) },
          "畫布設定已更新",
        );
        break;
      }
      case "caption-style":
        await edit("caption_style", { style: data }, "字幕樣式已更新");
        break;
      case "transcribe-form": {
        const options = {
          device: data.device,
          compute_type: data.device === "cuda" ? "float16" : "int8",
        };
        if (data.model_path) options.model_path = data.model_path;
        options.language = data.language;
        closeDialog();
        const job = await request(apiPath("/transcribe"), {
          expected_version: state.project.version,
          media_id: state.mediaId,
          options,
        });
        await waitJob(job, "本機語音辨識中…");
        accept(await request(apiPath()));
        state.mode = "captions";
        renderPanels();
        toast("逐字稿已產生，請校正辨識結果。");
        break;
      }
      case "add-caption-form": {
        const captions = state.project.captions
          .filter((c) => c.media_id === state.mediaId)
          .concat({ ...data, media_id: state.mediaId });
        await edit("captions_set", { media_id: state.mediaId, captions });
        closeDialog();
        break;
      }
      case "replace-form": {
        let count = 0;
        const captions = state.project.captions
          .filter((c) => c.media_id === state.mediaId)
          .map((c) => {
            count += c.text.split(data.find).length - 1;
            return {
              ...c,
              text: c.text.split(data.find).join(data.replacement),
            };
          });
        if (!count) throw new Error("目前素材的字幕沒有符合的文字。");
        await edit(
          "captions_set",
          { media_id: state.mediaId, captions },
          `已取代 ${count} 處文字`,
        );
        closeDialog();
        break;
      }
      case "caption-export-form": {
        const r = await request(
          apiPath(`/captions/export?format=${data.format}`),
        );
        if (!r.text.trim())
          throw new Error("目前時間軸沒有字幕；先將有字幕的素材加入主影片軌。");
        download(r.text, `${state.project.name}.${data.format}`);
        closeDialog();
        toast("字幕檔已下載");
        break;
      }
      case "add-title-form": {
        const lower = data.preset === "lower";
        delete data.preset;
        await edit(
          "title_add",
          {
            ...data,
            x: 0,
            y: lower ? state.project.height * 0.3 : 0,
            font_size: lower ? 42 : 64,
            color: "#ffffff",
          },
          "文字已加入",
        );
        closeDialog();
        break;
      }
      case "export-form": {
        const options = {
          crf: Number(data.crf),
          burn_captions: data.burn_captions,
          preset: "veryfast",
        };
        if (data.resolution !== "original") {
          const base = Number(data.resolution),
            p = state.project;
          if (p.width >= p.height) {
            options.height = base;
            options.width = Math.round((base * p.width) / p.height / 2) * 2;
          } else {
            options.width = base;
            options.height = Math.round((base * p.height) / p.width / 2) * 2;
          }
        }
        const job = await request(apiPath("/export"), {
          expected_version: state.project.version,
          options,
        });
        dialog(
          "正在匯出影片",
          `<div class="export-working">${icon("film", 40)}<h3>${esc(state.project.name)}</h3><progress id="export-progress" aria-label="影片匯出進度" max="100" value="0"></progress><p id="export-status">正在準備 FFmpeg…</p><p class="hint">完成後可取得影片；關閉此視窗，工作仍會繼續。</p></div>`,
        );
        const r = await waitJob(job, "正在匯出影片…");
        dialog(
          "影片已匯出",
          `<div class="export-complete">${icon("check", 40)}<h3>你的作品，已準備好了。</h3><p>${esc(state.project.name)}</p><a class="button primary full" href="${esc(r.url)}" download>${icon("download", 17)}下載 MP4</a><p class="hint">${esc(r.path || "已儲存至本機匯出資料夾")}</p></div>`,
        );
        toast("MP4 匯出完成");
        break;
      }
    }
  });
});
$("#media-input").onchange = (e) => {
  const files = [...e.target.files];
  e.target.value = "";
  if (files.length) importFiles(files);
};
$("#caption-input").onchange = (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file)
    guarded(async () => {
      const p = await request(apiPath("/captions/import"), {
        expected_version: state.project.version,
        media_id: state.mediaId,
        text: await file.text(),
        format: file.name.toLowerCase().endsWith(".vtt") ? "vtt" : "srt",
      });
      accept(p);
      state.mode = "captions";
      renderPanels();
      toast("字幕已匯入");
    });
};
$("#dialog").addEventListener("cancel", () => {
  $$("video,audio", $("#dialog")).forEach((n) => n.pause());
});
document.addEventListener("keydown", (e) => {
  if (state.project && !$("#dialog").open) {
    const shortcut = playheadShortcut(e);
    if (shortcut) {
      e.preventDefault();
      actions[shortcut]();
      return;
    }
  }
  if (state.project && !$("#dialog").open && e.target.matches('[data-caption-text], input[type="range"]') &&
      !e.isComposing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    actions[e.shiftKey ? "redo" : "undo"]();
    return;
  }
  if (state.project && !$("#dialog").open && e.target.matches("[data-caption-text]") &&
      !e.isComposing && ["Delete", "Backspace"].includes(e.key)) {
    e.preventDefault();
    const selection = selectedCharacters(e.target.value, e.target.selectionStart, e.target.selectionEnd);
    if (selection) cutTranscript(transcriptRows(state.project).find(c => c.id === e.target.dataset.captionText), selection);
    return;
  }
  if (
    !state.project ||
    $("#dialog").open ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) ||
    e.target.isContentEditable
  )
    return;
  if ((e.ctrlKey || e.metaKey) && ["c", "v"].includes(e.key.toLowerCase())) {
    // Keep native copying for text selected outside the timeline.
    if (e.key.toLowerCase() === "c" && window.getSelection()?.toString()) return;
    e.preventDefault();
    actions[e.key.toLowerCase() === "c" ? "duplicate" : "paste"]();
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    actions[e.shiftKey ? "redo" : "undo"]();
  } else if (
    e.code === "Space" &&
    !e.target.closest("button,a,[role=button]")
  ) {
    e.preventDefault();
    preview.toggle();
  } else if (e.key === "Delete") {
    e.preventDefault();
    actions.delete();
  } else if (
    (e.key === "ArrowLeft" || e.key === "ArrowRight") &&
    !e.target.closest("button,a,[role=button]")
  ) {
    e.preventDefault();
    preview.pause();
    seek(state.time + (e.key === "ArrowLeft" ? -1 : 1) / state.project.fps);
  } else if (e.key === "Escape") {
    selectMany([]);
    renderPanels();
  }
});
async function boot() {
  try {
    await connect();
    const id = localStorage.getItem("shijian-project");
    if (id) {
      try {
        await openProject(id);
        return;
      } catch {
        localStorage.removeItem("shijian-project");
      }
    }
    await home();
  } catch (e) {
    $("#app").innerHTML =
      `<div class="boot"><div class="brand"><b>迅剪</b></div><h1>本機服務尚未連線</h1><p>${esc(e.message)}</p><p>請執行 start-local-editor.cmd，再重新整理。</p><button class="button primary" id="retry">重新連線</button></div>`;
    $("#retry").onclick = boot;
  }
}
const agentWorkspace = new AgentWorkspace({ getState: () => state, request, reconnect: connect,
  dialog, toast, guarded, edit, accept, waitJob });
boot();
