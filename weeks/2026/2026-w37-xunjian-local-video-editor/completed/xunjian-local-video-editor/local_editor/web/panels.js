import { esc, icon, field, shortTime, duration, clock, mappedCaptions } from "./utils.js";
import { agentPanel } from "./agent-workspace.js";
const empty = (symbol, title, body, action = "") =>
  `<div class="panel-empty">${icon(symbol, 32)}<h3>${title}</h3><p>${body}</p>${action}</div>`;
const sourceSelect = (p, selected) =>
  `<label class="field"><span>分析素材</span><select id="source-media">${p.media
    .filter((m) => m.kind !== "image")
    .map(
      (m) =>
        `<option value="${esc(m.id)}" ${m.id === selected ? "selected" : ""}>${esc(m.name)}</option>`,
    )
    .join("")}</select></label>`;
export function panelHTML(mode, p, state) {
  if (mode === "agent") return agentPanel(p, state);
  if (mode === "media" || mode === "audio") {
    const items = p.media.filter((m) => mode !== "audio" || m.kind === "audio");
    return `<div class="panel-heading"><h2>${mode === "audio" ? "音訊素材" : "素材庫"} <span class="count">${items.length}</span></h2><button class="icon-button" data-action="import-path" title="從本機路徑匯入" aria-label="從本機路徑匯入">${icon("folder", 17)}</button></div><div class="panel-content"><button class="button primary full" data-action="import">${icon("plus", 17)}匯入${mode === "audio" ? "音訊" : "素材"}</button><p class="hint">檔案只會複製到這台電腦</p><label class="search-box">${icon("search", 16)}<input id="media-search" placeholder="搜尋素材名稱" aria-label="搜尋素材名稱"></label><div class="media-grid" id="media-grid">${items.length ? items.map((m) => `<article class="media-card ${state.mediaId === m.id ? "active" : ""}" draggable="true" data-media="${esc(m.id)}" data-name="${esc(m.name.toLowerCase())}"><button class="media-preview" data-preview="${esc(m.id)}" aria-label="預覽 ${esc(m.name)}">${m.thumbnail_url ? `<img src="${esc(m.thumbnail_url)}" alt="${esc(m.name)}" loading="lazy">` : `<span>${icon(m.kind === "audio" ? "audio" : m.kind === "image" ? "image" : "film", 30)}</span>`}<span class="media-length">${shortTime(m.duration)}</span></button><div class="media-card-footer"><span title="${esc(m.name)}">${esc(m.name)}</span><button class="add-media" data-add="${esc(m.id)}" title="加入時間軸" aria-label="加入 ${esc(m.name)} 到時間軸">${icon("plus", 14)}</button></div></article>`).join("") : empty("folder", "讓故事從這裡開始", "匯入影片、圖片或音訊。將素材拖到時間軸，或點選素材上的＋。")}</div><div class="drop-hint">${icon("upload", 17)}拖放檔案至此即可匯入</div>${mode === "audio" ? '<p class="note">獨立音訊軌可調整音量、變速與淡入淡出。原影片聲音也能在屬性面板調整。</p>' : ""}</div>`;
  }
  if (mode === "smart") {
    const plan = state.plan;
    const candidates = plan?.candidates || [];
    const chosen = candidates.filter((c) => state.checked.has(c.id));
    return `<div class="panel-heading"><h2>${icon("cut", 19)}智能剪口播</h2><span class="badge">本機分析</span></div><div class="panel-content smart-panel"><p class="panel-lead">留下重點，讓表達更俐落。</p><p class="hint">先聽、再選、再套用。原始素材會完整保留。</p>${p.media.some((m) => m.kind !== "image") ? `${sourceSelect(p, state.mediaId)}<div class="segment-tabs"><button class="${state.smartTab === "settings" ? "active" : ""}" data-smart-tab="settings">分析設定</button><button class="${state.smartTab === "results" ? "active" : ""}" data-smart-tab="results">剪輯建議 ${candidates.length ? `(${candidates.length})` : ""}</button></div>${state.smartTab === "settings" ? `<form id="smart-form"><div class="option-section"><h3>停頓與靜音</h3><p>依音量偵測，保留自然呼吸空間。</p>${field("靜音門檻（dB）", "threshold_db", state.smartOptions.threshold_db, 'type="number" min="-80" max="-10" step="1"')}${field("最短靜音（秒）", "min_silence", state.smartOptions.min_silence, 'type="number" min="0.15" max="4" step="any"')}${field("保留停頓（秒）", "keep_pause", state.smartOptions.keep_pause, 'type="number" min="0" max="2" step="any"')}</div><div class="option-section"><h3>逐字稿輔助</h3><label class="check-row"><input name="detect_fillers" type="checkbox" ${state.smartOptions.detect_fillers ? "checked" : ""}><span>辨識獨立贅詞<small>例如：嗯、呃、那個</small></span></label><label class="check-row"><input name="detect_repeats" type="checkbox" ${state.smartOptions.detect_repeats ? "checked" : ""}><span>標記相鄰重複語句<small>以完全相同的字幕片段比對</small></span></label><p class="note">贅詞／重複偵測需要字幕。可先匯入 SRT，或使用本機語音辨識。</p><button type="button" class="button ghost full" data-action="transcribe">${icon("captions", 17)}產生逐字稿</button></div><button class="button primary full" type="submit" ${false ? "disabled" : ""}>${icon("spark", 17)}開始分析</button></form>` : `${plan ? `<div class="cut-summary"><div><strong>${chosen.length}</strong><span>段待剪除</span></div><div><strong>${chosen.reduce((n, c) => n + c.end - c.start, 0).toFixed(1)}<small> 秒</small></strong><span>候選時間總和（重疊會合併）</span></div></div><div class="selection-bar"><label><input id="select-all-cuts" type="checkbox" ${chosen.length === candidates.length && candidates.length ? "checked" : ""}>全選</label><span>播放原片段確認</span></div><div class="candidate-list">${candidates.length ? candidates.map((c) => `<article class="candidate ${state.checked.has(c.id) ? "chosen" : ""}"><label><input data-candidate="${esc(c.id)}" type="checkbox" ${state.checked.has(c.id) ? "checked" : ""}><span><b class="kind-label ${c.kind}">${{ silence: "靜音", filler: "贅詞", repeat: "重複" }[c.kind] || "剪輯"}</b><span class="timecode">${shortTime(c.start)} — ${shortTime(c.end)}</span><small>${esc(c.text || c.reason || "停頓片段")}</small></span></label><button class="icon-button" data-audition="${esc(c.id)}" title="試聽原片段" aria-label="試聽 ${shortTime(c.start)} 片段">${icon("play", 16)}</button></article>`).join("") : empty("check", "沒有需要剪除的片段", "可調整靜音門檻，或確認素材已有逐字稿。")}</div><button class="button primary full sticky-action" data-action="apply-cuts" ${!chosen.length || false ? "disabled" : ""}>${icon("cut", 17)}套用 ${chosen.length} 段剪輯</button><p class="hint">會同步移動各軌，可用 Ctrl＋Z 復原。</p>` : empty("cut", "還沒有剪輯建議", "在分析設定選擇素材後，按「開始分析」。", '<button class="button ghost" data-smart-tab="settings">前往分析設定</button>')}`}` : empty("film", "先加入一段口播影片", "從素材庫匯入影片，並加入時間軸後開始分析。", '<button class="button primary" data-action="import">匯入素材</button>')}</div>`;
  }
  if (mode === "captions") {
    const captions = mappedCaptions(p);
    return `<div class="panel-heading"><h2>字幕與逐字稿</h2><span class="count">${captions.length} 句</span></div><div class="panel-content">
      <div class="button-row"><button class="button primary" data-action="transcribe">${icon("spark", 16)}語音辨識</button><button class="button" data-action="import-captions">匯入字幕</button></div>
      ${p.media.length ? sourceSelect(p, state.mediaId) : ""}
      <label class="search-box">${icon("search", 16)}<input id="caption-search" placeholder="搜尋逐字稿" aria-label="搜尋逐字稿"></label>
      <div class="caption-actions"><button class="text-button" data-action="add-caption">新增一句</button><button class="text-button" data-action="replace-captions">尋找取代</button><button class="text-button" data-action="export-captions">匯出</button></div>
      <p class="hint">顯示剪輯後的字幕與時間。選取文字後按 Delete／Backspace 剪除影片；改錯字可按「校正」。</p>
      ${state.skipCutConfirm ? '<button class="text-button" data-action="reset-caption-confirm">恢復剪除確認視窗</button>' : ''}
      <div class="transcript-list">${captions.length ? captions.map((s, i) => `<article class="transcript-row" data-caption-row="${esc(s.id)}" data-text="${esc(s.text.toLowerCase())}">
        <div class="transcript-head"><button class="text-button timecode" data-caption-seek="${esc(s.id)}">${String(i+1).padStart(2,"0")} <span>${shortTime(s.start)} — ${shortTime(s.end)}</span></button><button class="text-button" data-caption-edit="${esc(s.source_caption_id)}" title="校正來源字幕文字與時間">校正</button></div>
        <textarea readonly data-caption-text="${esc(s.id)}" rows="2" aria-label="第 ${i+1} 句字幕，可選字剪除">${esc(s.text)}</textarea>
        <div class="transcript-tools"><button class="text-button" data-caption-cut="${esc(s.id)}">${icon("cut",13)}剪除此句</button><button class="text-button" data-caption-selection="${esc(s.id)}">剪除選取文字</button></div>
      </article>`).join("") : empty("captions","時間軸尚無字幕","加入影片與字幕後，這裡會隨剪輯同步更新。")}</div></div>`;
  }
  if (mode === "text")
    return `<div class="panel-heading"><h2>文字與標題</h2>${icon("text", 18)}</div><div class="panel-content"><button class="button primary full" data-action="add-title">${icon("plus", 17)}新增文字</button><p class="hint">文字使用時間軸時間，可調整位置、大小與顏色。</p><div class="title-presets"><button data-title-preset="heading"><span class="preset-heading">你的下一個故事</span><small>主標題 · 64 px</small></button><button data-title-preset="lower"><span class="preset-lower">讓每一句話，都剛剛好。</span><small>下方重點 · 42 px</small></button></div><h3 class="section-label">時間軸文字</h3>${p.titles.length ? p.titles.map((t) => `<button class="list-button" data-select-title="${esc(t.id)}">${icon("text", 18)}<span>${esc(t.text)}<small>${shortTime(t.start)} — ${shortTime(t.end)}</small></span>${icon("chevron", 15)}</button>`).join("") : empty("text", "還沒有文字", "新增標題或選用上方樣式。")}</div>`;
  if (mode === "effects")
    return `<div class="panel-heading"><h2>調色與畫面</h2>${icon("sliders", 18)}</div><div class="panel-content"><p class="panel-lead">為畫面設定一致的語氣。</p><p class="hint">先選取時間軸片段，再套用可微調的調色預設。</p><div class="filter-presets">${[
      ["原始", 0, 1, 1, "neutral"],
      ["清透", 0.04, 1.06, 1.08, "clear"],
      ["柔和", 0.03, 0.91, 0.86, "soft"],
      ["電影", -0.03, 1.17, 0.78, "cinema"],
      ["黑白", 0, 1.08, 0, "mono"],
      ["鮮明", 0.02, 1.12, 1.3, "vivid"],
    ]
      .map(
        ([name, b, c, s, cls]) =>
          `<button class="filter-preset ${cls}" data-filter="${b},${c},${s}"><span class="filter-swatch">Aa</span><span>${name}</span></button>`,
      )
      .join(
        "",
      )}</div><p class="note">亮度、對比、飽和度、旋轉、縮放與透明度可在右側屬性微調。匯出由 FFmpeg 套用。</p></div>`;
  return "";
}

export function inspectorHTML(p, state) {
  if (state.selectedIds?.length > 1) {
    return `<div class="panel-heading"><h2>已選取 ${state.selectedIds.length} 個片段</h2><button class="icon-button" data-action="clear-selection" aria-label="取消選取">${icon("close", 16)}</button></div><div class="panel-content"><p class="panel-lead">拖動任一已選片段，整組一起移動。</p><p class="hint">保留各片段之間的時間間距與軌道。Ctrl／⌘ 點選可增減選取，Escape 可取消。</p><p class="note">開啟連動刪除時，會從所有軌道剪除所選時間區間，並自動接合後方內容。</p><button class="button danger full" data-action="delete">刪除 ${state.selectedIds.length} 個片段</button><p class="hint">群組移動或刪除，都可用一次 Ctrl＋Z 復原。</p></div>`;
  }
  const clip = p.clips.find((c) => c.id === state.selected);
  const title = p.titles.find((t) => t.id === state.selected);
  const caption = p.captions.find((c) => c.id === state.selected);
  const style = p.caption_style;
  if (state.mode === "smart" && state.smartTab === "results") {
    const transcript = p.captions.filter((c) => c.media_id === state.mediaId);
    const candidates = state.plan?.candidates || [];
    return `<div class="panel-heading"><h2>來源逐字稿</h2><span class="count">${transcript.length} 句</span></div><div class="panel-content"><p class="hint">對照左側建議檢閱上下文。點選時間即可定位；標記處與剪輯候選重疊。</p>${transcript.length ? transcript.map((c) => `<article class="speech-transcript ${candidates.some((x) => x.start < c.end && x.end > c.start) ? "flagged" : ""}"><button class="text-button timecode" data-caption-seek="${esc(c.id)}">${shortTime(c.start)} — ${shortTime(c.end)}</button><p>${esc(c.text)}</p></article>`).join("") : empty("captions", "加入逐字稿，判斷更完整", "本次可先處理靜音；語音辨識或匯入字幕後，也能分析贅詞與重複語句。", '<button class="button full" data-action="transcribe">產生逐字稿</button>')}<button class="button full spaced" data-mode="captions">編輯與校正字幕</button><p class="note">修改字幕後請重新分析，再套用新版本的建議。</p></div>`;
  }
  if (caption && state.selectedType === "caption")
    return `<div class="panel-heading"><h2>字幕時間</h2><button class="icon-button" data-action="clear-selection" aria-label="取消選取">${icon("close", 16)}</button></div><form id="caption-properties" class="panel-content"><p class="hint">來源素材的時間。剪輯後的顯示時間由系統映射。</p><p class="note">逐字對齊：${{valid:"有有效詞級時間",stale:"文字或時間已修改，需複核",missing:"尚無詞級時間"}[caption.alignment_status || (caption.words?.length ? "valid" : "missing")]}</p><button type="button" class="button full spaced" data-observe-action="caption-review" data-caption-id="${esc(caption.id)}">局部語音複核</button><input type="hidden" name="caption_id" value="${esc(caption.id)}">${field("開始（秒）", "start", caption.start, 'type="number" min="0" step="any" required')}${field("結束（秒）", "end", caption.end, 'type="number" min="0" step="any" required')}<label class="field"><span>字幕內容</span><textarea name="text" rows="4" required>${esc(caption.text)}</textarea></label><button class="button primary full">儲存字幕</button></form>`;
  if (title)
    return `<div class="panel-heading"><h2>文字屬性</h2><button class="icon-button" data-action="clear-selection" aria-label="取消選取">${icon("close", 16)}</button></div><form id="title-properties" class="panel-content"><input type="hidden" name="title_id" value="${esc(title.id)}"><label class="field"><span>文字內容</span><textarea name="text" rows="3" required>${esc(title.text)}</textarea></label><div class="field-pair">${field("開始（秒）", "start", title.start, 'type="number" min="0" step="any"')}${field("結束（秒）", "end", title.end, 'type="number" min="0" step="any"')}</div>${field("字體大小", "font_size", title.font_size, 'type="number" min="8" max="300"')}${field("文字顏色", "color", title.color, 'type="color"')}<div class="field-pair">${field("X 位移", "x", title.x, 'type="number" step="1"')}${field("Y 位移", "y", title.y, 'type="number" step="1"')}</div><button class="button primary full">儲存文字</button><button class="button danger full spaced" type="button" data-action="delete">${icon("trash", 15)}刪除文字</button></form>`;
  if (clip) {
    const m = p.media.find((m) => m.id === clip.media_id);
    return `<div class="panel-heading"><h2>${clip.track === "audio" ? "音訊" : "片段"}屬性</h2><button class="icon-button" data-action="clear-selection" aria-label="取消選取">${icon("close", 16)}</button></div><div class="inspector-name">${icon("film", 16)}<span>${esc(m?.name)}</span></div><form id="clip-properties" class="panel-content"><input name="clip_id" type="hidden" value="${esc(clip.id)}"><div class="segment-tabs"><button type="button" class="${state.inspectorTab === "basic" ? "active" : ""}" data-inspector-tab="basic">基本</button><button type="button" class="${state.inspectorTab === "picture" ? "active" : ""}" data-inspector-tab="picture">畫面</button><button type="button" class="${state.inspectorTab === "sound" ? "active" : ""}" data-inspector-tab="sound">聲音</button></div>${
      state.inspectorTab === "basic"
        ? `<h3 class="section-label">位置與時間</h3><label class="field"><span>軌道</span><select name="track">${[
            ["video", "主影片 V1"],
            ["overlay", "疊加畫面 V2"],
            ["audio", "音訊 A1"],
          ]
            .map(
              ([v, l]) =>
                `<option value="${v}" ${v === clip.track ? "selected" : ""}>${l}</option>`,
            )
            .join(
              "",
            )}</select></label>${field("時間軸開始（秒）", "offset", clip.offset, 'type="number" min="0" step="any"')}<div class="field-pair">${field("來源開始", "start", clip.start, 'type="number" min="0" step="any"')}${field("來源結束", "end", clip.end, 'type="number" min="0" step="any"')}</div>${field("播放速度", "speed", clip.speed, 'type="number" min="0.25" max="4" step="any"')}<p class="hint">片段長度 ${duration(clip).toFixed(2)} 秒</p>`
        : state.inspectorTab === "picture"
          ? `<h3 class="section-label">變形</h3>${field("縮放（倍）", "scale", clip.scale, 'type="number" min="0.05" max="4" step="any"')}<div class="field-pair">${field("X 位移（px）", "x", clip.x, 'type="number" step="1"')}${field("Y 位移（px）", "y", clip.y, 'type="number" step="1"')}</div>${field("旋轉（度）", "rotation", clip.rotation, 'type="number" min="-360" max="360" step="1"')}${field("透明度", "opacity", clip.opacity, 'type="range" min="0" max="1" step="any"')}<h3 class="section-label">調色</h3>${field("亮度", "brightness", clip.brightness, 'type="range" min="-0.5" max="0.5" step="any"')}${field("對比", "contrast", clip.contrast, 'type="range" min="0" max="2" step="any"')}${field("飽和度", "saturation", clip.saturation, 'type="range" min="0" max="3" step="any"')}`
          : `<h3 class="section-label">音訊</h3>${field("音量（倍）", "volume", clip.volume, 'type="number" min="0" max="4" step="any"')}<label class="check-row"><input name="muted" type="checkbox" ${clip.muted ? "checked" : ""}>靜音此片段</label><div class="field-pair">${field("淡入（秒）", "fade_in", clip.fade_in, 'type="number" min="0" step="any"')}${field("淡出（秒）", "fade_out", clip.fade_out, 'type="number" min="0" step="any"')}</div><p class="note">瀏覽器預覽音量最高為 1 倍；高於 1 倍的增益會套用至正式匯出。</p>`
    }<button class="button primary full spaced">套用屬性</button></form>`;
  }
  return `<div class="panel-heading"><h2>專案設定</h2><span class="badge">本機儲存</span></div><form id="project-properties" class="panel-content"><h3 class="section-label">畫布</h3><label class="field"><span>畫面比例</span><select name="resolution"><option value="1920,1080" ${p.width === 1920 && p.height === 1080 ? "selected" : ""}>16:9 · 1920 × 1080</option><option value="1080,1920" ${p.width === 1080 && p.height === 1920 ? "selected" : ""}>9:16 · 1080 × 1920</option><option value="1080,1080" ${p.width === 1080 && p.height === 1080 ? "selected" : ""}>1:1 · 1080 × 1080</option><option value="1280,720" ${p.width === 1280 && p.height === 720 ? "selected" : ""}>16:9 · 1280 × 720</option></select></label><label class="field"><span>影格率</span><select name="fps">${[24, 25, 30, 50, 60].map((n) => `<option value="${n}" ${p.fps === n ? "selected" : ""}>${n} fps</option>`).join("")}</select></label><button class="button full">更新畫布</button></form><form id="caption-style" class="panel-content divided"><h3 class="section-label">字幕樣式</h3><div class="caption-style-preview" style="color:${esc(style.color)};background:${esc(style.background)}">每一句話，都剛剛好。</div>${field("字幕大小", "font_size", style.font_size, 'type="number" min="8" max="200"')}<div class="field-pair">${field("文字顏色", "color", style.color, 'type="color"')}${field("底色", "background", style.background, 'type="color"')}</div><label class="field"><span>顯示位置</span><select name="position">${[
    ["bottom", "下方"],
    ["center", "中央"],
    ["top", "上方"],
  ]
    .map(
      ([v, l]) =>
        `<option value="${v}" ${style.position === v ? "selected" : ""}>${l}</option>`,
    )
    .join(
      "",
    )}</select></label><button class="button full">更新字幕樣式</button></form><div class="panel-content divided"><p class="hint">選取時間軸片段，可調整修剪、變速、畫面與聲音。</p></div>`;
}
