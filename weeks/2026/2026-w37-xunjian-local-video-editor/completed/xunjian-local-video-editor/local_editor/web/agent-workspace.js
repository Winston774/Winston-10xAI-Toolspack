import { esc, icon, field, total, clock } from "./utils.js";

export function agentPanel(project, state) {
  const brief = project.brief || {};
  const bounds = state.observationRange || { start: Math.min(state.time, Math.max(0, total(project) - .1)), end: Math.min(total(project), state.time + 6) };
  return `<div class="panel-heading"><h2>Agent 理解工作台</h2><span class="badge">v0.2</span></div>
  <div class="panel-content agent-understanding">
    <div id="agent-context-status" class="note" aria-live="polite">正在同步工作情境…</div>
    <h3 class="section-label">剪輯方向</h3>
    <p class="hint">保存你的目標與保留規則，Agent 讀取情境時會一起取得。</p>
    <form id="agent-brief-form">
      <label class="field"><span>這支影片要達成什麼？</span><textarea name="goal" rows="3" maxlength="4000" placeholder="例如：完整示範操作，剪掉無意義等待，保留關鍵步驟。">${esc(brief.goal || "")}</textarea></label>
      ${field("觀眾", "audience", brief.audience || "", 'maxlength="2000"')}
      ${field("節奏與風格", "pacing", brief.pacing || "", 'maxlength="2000" placeholder="例如：清楚、自然，保留操作思考時間"')}
      ${field("目標長度（秒，可留空）", "target_duration", brief.target_duration ?? "", 'type="number" min="0" step="any" placeholder="例如：60"')}
      <label class="field"><span>必須保留（每行一項）</span><textarea name="must_keep" rows="3">${esc((brief.must_keep || []).join("\n"))}</textarea></label>
      <label class="field"><span>補充說明</span><textarea name="notes" rows="2">${esc(brief.notes || "")}</textarea></label>
      <button class="button full">儲存剪輯方向</button>
    </form>
    <div class="divided"><h3 class="section-label">觀察與驗證</h3>
      <p class="hint">每次最多 30 秒。取得正式合成的聲畫證據，與 Agent 使用相同入口。</p>
      <form id="agent-range-form"><div class="field-pair">${field("時間軸開始（秒）", "start", bounds.start, 'type="number" min="0" step="any" required')}${field("結束（秒）", "end", bounds.end, 'type="number" min="0" step="any" required')}</div>
        <div class="button-row"><button class="button" name="operation" value="inspect">${icon("film", 15)}聲畫證據</button><button class="button" name="operation" value="analyze">${icon("spark", 15)}分析區間</button></div>
        <button class="button full spaced" name="operation" value="cut-review">檢查切點與黑畫面</button>
      </form>
      <button class="button full spaced" data-observe-action="verify">${icon("check", 15)}檢查目前剪輯</button>
      <button class="text-button spaced" data-observe-action="context">查看 Agent 目前取得的情境</button>
    </div>
    <div class="divided"><h3 class="section-label">剪輯提案</h3><div id="agent-proposals"><p class="hint">正在讀取提案…</p></div></div>
    <div class="divided"><h3 class="section-label">MCP 連線</h3><div id="agent-connections"><p class="hint">正在讀取連線活動…</p></div><button class="button full" data-action="mcp-config">查看連線設定</button><p class="hint">情境 → 聲畫觀察 → 分析 → 提案 → 預覽 → 套用 → 驗證。尚未確認的內容會保留未知標記。</p></div>
    <h3 class="section-label">操作紀錄</h3><div id="event-list"></div>
  </div>`;
}

const pretty = value => esc(JSON.stringify(value, null, 2));
const details = (label, value) => `<details class="evidence-details"><summary>${esc(label)}</summary><pre class="code-block">${pretty(value)}</pre></details>`;

export class AgentWorkspace {
  constructor(host) {
    Object.assign(this, host);
    this.clientId = crypto.randomUUID();
    this.sequence = 0;
    this.lastSent = 0;
    this.lastPayload = "";
    this.contextPending = false;
    this.context = null;
    this.activeEvidence = null;
    this.pendingProposal = null;
    document.addEventListener("submit", e => this.submit(e));
    document.addEventListener("click", e => this.click(e));
    document.addEventListener("input", e => {
      const form = e.target.closest("#agent-range-form");
      if (!form) return;
      const start = Number(form.elements.start.value), end = Number(form.elements.end.value);
      const state = this.getState();
      if (Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start && end <= total(state.project) && end - start <= 30) {
        state.observationRange = { start, end };
        this.publish(true);
      }
    });
    document.addEventListener("visibilitychange", () => this.publish(true));
    window.addEventListener("focus", () => this.publish(true));
    window.addEventListener("blur", () => this.publish(true));
    this.timer = setInterval(() => this.publish(), 1000);
  }

  async publish(force = false) {
    const state = this.getState(), project = state.project;
    const selected = state.selected ? { id: state.selected, type: state.selectedType } : null;
    let range = state.observationRange || null;
    if (project && range && range.end > total(project)) range = null;
    const payload = { client_id: this.clientId, project_id: project?.id || null,
      project_version: project?.version || null, selected, playhead: state.time || 0,
      range, mode: state.mode, media_id: state.mediaId, focused: document.visibilityState === "visible" && document.hasFocus() };
    const serialized = JSON.stringify(payload), now = Date.now();
    if (this.contextPending || (!force && serialized === this.lastPayload && now - this.lastSent < 15000)) return;
    this.contextPending = true;
    try {
      await this.request("/context", { ...payload, sequence: ++this.sequence });
      this.lastPayload = serialized;
      this.lastSent = now;
    } catch (error) {
      if (error.code === "invalid_session") await this.reconnect();
    } finally { this.contextPending = false; }
  }

  async refresh() {
    const project = this.getState().project;
    if (!project) return;
    await this.publish(true);
    try {
      const context = await this.request(`/context?project_id=${encodeURIComponent(project.id)}&client_id=${encodeURIComponent(this.clientId)}`);
      this.context = context;
      const status = document.querySelector("#agent-context-status");
      if (status) status.textContent = context.ui ? `情境已同步 · v${context.project.version} · 播放頭 ${clock(context.ui.playhead)}${context.ui.selected ? " · 已選取片段或字幕" : ""}` : "尚無即時 UI 情境";
      const connections = document.querySelector("#agent-connections");
      if (connections) connections.innerHTML = context.agents.length ? [...context.agents].sort((a,b) => b.last_seen-a.last_seen).slice(0,4).map(a => `<p class="hint"><b>${esc(a.name)}</b> · ${a.status === "recently_active" ? "最近有活動" : "暫無近期活動"}<br>${esc(a.last_tool && a.last_tool !== "None" ? a.last_tool : "已完成 MCP 握手")}</p>`).join("") : '<p class="hint">目前沒有 MCP 連線活動。設定連線後，Agent 可直接取得影格與音訊。</p>';
      const proposals = document.querySelector("#agent-proposals");
      if (proposals) proposals.innerHTML = context.proposals?.length ? context.proposals.map(p => `<button class="proposal-item" data-observe-action="proposal" data-edit-id="${esc(p.edit_id || p.id)}"><b>${esc(p.intent || "剪輯提案")}</b><small>v${p.base_version} · ${p.status === "applied" ? "已套用" : p.can_apply === false ? "已過期" : "待審閱"}</small></button>`).join("") : '<p class="hint">尚無提案。Agent 的批次剪輯與智能剪口播提案會在這裡顯示。</p>';
    } catch (error) {
      const status = document.querySelector("#agent-context-status");
      if (status) status.textContent = error.message;
    }
  }

  bounds() {
    const state = this.getState(), end = total(state.project);
    return state.observationRange || { start: Math.min(state.time, Math.max(0, end - .1)), end: Math.min(end, state.time + 6) };
  }

  async submit(event) {
    const form = event.target;
    if (!["agent-brief-form", "agent-range-form", "evidence-review-form"].includes(form.id)) return;
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const operation = event.submitter?.value || "inspect";
    await this.guarded(async () => {
      const state = this.getState();
      if (form.id === "agent-brief-form") {
        await this.edit("brief_update", { brief: { ...values, target_duration: values.target_duration.trim() ? Number(values.target_duration) : null, must_keep: values.must_keep.split("\n").map(s => s.trim()).filter(Boolean) } }, "剪輯方向已儲存，Agent 可直接讀取。");
        return;
      }
      if (form.id === "agent-range-form") {
        const range = { start: Number(values.start), end: Number(values.end) };
        if (!Number.isFinite(range.start) || !Number.isFinite(range.end) || range.end <= range.start || range.end - range.start > 30 || range.end > total(state.project)) throw new Error("請選擇時間軸內 0 至 30 秒的有效區間。");
        state.observationRange = range;
        await this.publish(true);
        await this.observe(operation === "cut-review" ? "inspect" : operation, { time_space: "timeline", range,
          ...(operation === "cut-review" ? { sampling: { strategy: "cut_boundaries", offset_frames: [-2,-1,0,1,2] }, scan_black_frames: true, max_frames: 8 } : {}) });
        return;
      }
      const evidence = this.activeEvidence;
      if (!evidence) throw new Error("請先取得聲畫證據。");
      const submitted = new FormData(form);
      const checks = submitted.getAll("checks");
      const file_ids = submitted.getAll("file_ids");
      await this.request(`/projects/${state.project.id}/reviews`, { expected_version: state.project.version,
        evidence_id: evidence.evidence_id, ...(evidence.edit_id ? { edit_id: evidence.edit_id, preview_side: evidence.preview_side } : {}),
        file_ids, reviewer: "工作台使用者", checks, outcome: values.outcome, notes: values.notes });
      this.toast("已保存實際審閱紀錄；未選取的檢查仍保留未確認狀態。");
    });
  }

  async click(event) {
    const button = event.target.closest("[data-observe-action]");
    if (!button) return;
    event.preventDefault();
    await this.guarded(async () => {
      const state = this.getState(), action = button.dataset.observeAction;
      if (action === "context") {
        await this.refresh();
        this.dialog("Agent 工作情境", `<p class="hint">來自正式情境入口，包含剪輯方向、目前選取與能力限制。</p>${details("完整情境資料", this.context)}`, "evidence-dialog");
      } else if (action === "verify") {
        const report = await this.request(`/projects/${state.project.id}/verify`, { expected_version: state.project.version });
        this.showVerification(report);
      } else if (action === "proposal") {
        const proposal = await this.request(`/projects/${state.project.id}/edits/${encodeURIComponent(button.dataset.editId)}`);
        this.showProposal(proposal);
      } else if (action === "verify-proposal") {
        const proposal = this.pendingProposal;
        const report = await this.request(`/projects/${state.project.id}/verify`, { expected_version: state.project.version,
          edit_id: proposal.edit_id || proposal.id, preview_side: "after" });
        this.showVerification(report);
      } else if (action === "preview-before" || action === "preview-after") {
        const proposal = this.pendingProposal;
        if (!proposal) throw new Error("請重新開啟提案。");
        const side = action.endsWith("before") ? "before" : "after";
        const duration = proposal[side]?.duration || 0;
        if (!duration) throw new Error("此側時間軸沒有可預覽內容。");
        const selected = this.bounds(), start = Math.min(selected.start, Math.max(0, duration - 1));
        await this.observe("inspect", { time_space: "timeline", range: { start, end: Math.min(duration, start + Math.min(30, selected.end - selected.start || 6)) }, edit_id: proposal.edit_id || proposal.id, preview_side: side,
          sampling: { strategy: "cut_boundaries" }, scan_black_frames: true, max_frames: 8 });
      } else if (action === "back-proposal") {
        this.showProposal(this.pendingProposal);
      } else if (action === "apply-proposal") {
        const proposal = this.pendingProposal;
        const updated = await this.request(`/projects/${state.project.id}/edits/apply`, { expected_version: state.project.version, edit_id: proposal.edit_id || proposal.id });
        this.accept(updated);
        this.showVerification(updated.verification);
        this.toast("提案已整批套用，可用一次復原還原。");
      } else if (action === "caption-review") {
        const caption_id = button.dataset.captionId || state.selected;
        await this.observe("captions/review", { caption_id });
      }
    });
  }

  async observe(operation, params) {
    const state = this.getState();
    this.dialog("正在取得聲畫證據", '<p class="hint">以本機合成引擎處理選取區間，原始素材完整保留。</p>');
    const job = await this.request(`/projects/${state.project.id}/${operation}`, { expected_version: state.project.version,
      ...(operation === "inspect" ? { include: ["frames", "audio", "video"], max_frames: 4, detail: "review" } : {}), ...params });
    const result = await this.waitJob(job, "取得聲畫證據");
    this.showEvidence(result);
  }

  async prepareOperations(operations, intent) {
    const state = this.getState();
    const proposal = await this.request(`/projects/${state.project.id}/edits`, { expected_version: state.project.version, operations, intent,
      checks: [{ kind: "no_timeline_gaps" }] });
    this.showProposal(proposal);
  }

  showProposal(proposal) {
    this.pendingProposal = proposal;
    const ready = proposal.base_version === this.getState().project.version && proposal.status === "prepared";
    this.dialog("審閱剪輯提案", `<p>${esc(proposal.intent)}</p><div class="review-stats"><div><small>修改前</small><strong>${clock(proposal.before.duration)}</strong></div><div><small>修改後</small><strong>${clock(proposal.after.duration)}</strong></div><div><small>來源版本</small><strong>v${proposal.base_version}</strong></div></div>
      ${proposal.warnings?.length ? `<p class="note">${proposal.warnings.map(w => esc(typeof w === "string" ? w : w.message || w.code || JSON.stringify(w))).join("<br>")}</p>` : ""}
      <p class="hint">前後預覽各取目前觀察區間；剪輯後的時間軸座標可能已位移。可查看精確差異，再確認套用。</p>
      <div class="button-row"><button class="button" data-observe-action="preview-before" ${!ready ? "disabled" : ""}>修改前聲畫</button><button class="button" data-observe-action="preview-after" ${!ready ? "disabled" : ""}>修改後聲畫</button></div>
      ${details("精確差異與受影響項目", { diff: proposal.diff, affected_ids: proposal.affected_ids })}
      ${details("提案驗收規格（建立時檢查）", { checks: proposal.checks, acceptance: proposal.acceptance })}
      <button class="button full spaced" data-observe-action="verify-proposal" ${!ready ? "disabled" : ""}>更新提案驗收結果</button>
      <button class="button primary full spaced" data-observe-action="apply-proposal" ${!ready ? "disabled" : ""}>${ready ? "確認套用整批修改" : "提案已套用或已過期，請重新提案"}</button>`, "evidence-dialog");
  }

  showEvidence(result) {
    const e = result.evidence;
    this.activeEvidence = e;
    const media = e.files.map((f, index) => {
      const label = `${{image:"影格",audio:"區間音訊",video:"合成短片"}[f.kind] || "證據"} ${index + 1}${f.time === undefined ? "" : ` · ${clock(f.time, true)}`}`;
      return `<figure class="evidence-item">${f.kind === "image" ? `<img src="${esc(f.url)}" alt="${esc(label)}">` : f.kind === "audio" ? `<audio src="${esc(f.url)}" controls preload="metadata"></audio>` : `<video src="${esc(f.url)}" controls preload="metadata"></video>`}<figcaption><label><input type="checkbox" name="file_ids" value="${esc(f.id)}" form="evidence-review-form">我已檢視 ${esc(label)}</label></figcaption></figure>`;
    }).join("");
    this.dialog("區間聲畫證據", `<div class="evidence-heading"><span class="badge">${e.time_space === "source" ? "來源素材" : "合成時間軸"}</span><span>v${e.project_version} · ${clock(e.range.start)} — ${clock(e.range.end)}</span>${e.edit_id ? `<span class="badge">${e.preview_side === "before" ? "修改前" : "修改後"}提案預覽</span>` : ""}</div>
      ${result.stale ? '<p class="note">處理期間專案已修改；這份證據屬舊版本。</p>' : ""}
      ${e.black_scan ? `<p class="note">已掃描 ${esc(e.black_scan.decoded_frame_count)} 個解碼影格，發現 ${esc(e.black_scan.candidate_count)} 組近黑畫面候選。此結果尚需人工或 Agent 複核，未檢查即時 UI 播放。</p>` : ""}
      ${e.findings?.length ? `<div class="review-record">${e.findings.map(f => `<p><b>${esc(f.time.toFixed(3))} 秒 · ${esc(f.frame_count)} 影格</b><br>${esc(f.message)}<br><small>片段：${esc(f.target_ids.join(", ") || "無作用中片段")}</small></p>`).join("")}</div>` : ""}
      <div class="evidence-grid">${media}</div>
      ${e.sampling ? details("切點取樣與省略範圍", e.sampling) : ""}
      ${e.findings?.length ? details("可定位的檢查結果", e.findings) : ""}
      <p class="note">影格為抽樣證據；完整區間的聲畫請播放短片。取得檔案不會自動記為已審閱。</p>
      ${e.proposal ? details("字幕複核候選（尚未修改原字幕）", { authored: e.authored, proposal: e.proposal, comparison: e.comparison, alignment: e.alignment }) : ""}
      ${e.analysis ? details("音訊與畫面變化分析", e.analysis) : ""}
      ${e.structural_analysis ? details("逐字稿、節奏與版面問題", e.structural_analysis) : ""}
      ${details("時間映射與圖層", result.structure)}${details("證據範圍、合成一致性與未知", { coverage: e.coverage, render_parity: e.render_parity, unknowns: e.unknowns })}
      <form id="evidence-review-form" class="review-record"><h3>記錄已完成的審閱</h3><p class="hint">先勾選上方實際檢視的檔案，再記錄檢查範圍。</p><div class="button-row">${[["visual", "畫面"], ["audio", "聲音"], ["subtitle_layout", "字幕版面"]].map(([v, l]) => `<label class="inline-check"><input type="checkbox" name="checks" value="${v}">${l}</label>`).join("")}</div><label class="field"><span>結論</span><select name="outcome"><option value="pass">所選範圍檢查通過</option><option value="issue">發現問題</option></select></label><label class="field"><span>具體觀察</span><textarea name="notes" rows="2" required maxlength="4000" placeholder="例如：已聽過切點前後，接句自然；抽樣畫面的字幕沒有遮住操作按鈕。"></textarea></label><button class="button full">保存審閱紀錄</button></form>
      ${this.pendingProposal && e.edit_id ? '<button class="button full spaced" data-observe-action="back-proposal">返回提案與套用</button>' : ""}`, "evidence-dialog");
  }

  showVerification(report) {
    const summary = report.summary || {};
    this.dialog("剪輯驗證結果", `<p class="panel-lead">結構檢查與視聽確認分開記錄。</p>
      <p class="note">${report.audiovisual_review?.status === "partially_reviewed" ? "已有部分聲畫審閱紀錄；未列出的區間仍未確認。" : "尚未記錄聲畫審閱，無法判定整片聽感與敘事自然度。"}</p>
      <div class="doctor-row"><b>專案與來源範圍</b><span>${summary.structure_passed ? "結構檢查通過" : "需要檢查"}</span></div>
      <div class="doctor-row"><b>字幕對齊問題</b><span>${summary.caption_issue_count ?? "—"} 項</span></div>
      <div class="doctor-row"><b>主影片空隙</b><span>${summary.main_video_gap_count ?? "—"} 處</span></div>
      <div class="doctor-row"><b>字幕版面估算疑慮</b><span>${summary.estimated_layout_concern_count ?? "—"} 處 · 尚需查看合成</span></div>
      <div class="doctor-row"><b>尚待視聽確認的切點</b><span>${summary.unreviewed_cut_count ?? "—"} 處</span></div>
      <div class="doctor-row"><b>提案驗收</b><span>${({passed:"自動條件通過",failed:"條件不符",pending:"等待證據",needs_review:"候選待複核",not_requested:"未指定"})[report.acceptance?.status] || "未指定"}</span></div>
      ${details("驗收條件與黑畫面候選", { acceptance: report.acceptance, findings: report.findings })}
      ${report.edit_id && this.pendingProposal ? '<button class="button full spaced" data-observe-action="back-proposal">返回提案</button>' : ""}
      ${details("結構、字幕問題與切點位置", report)}<button class="button full spaced" data-action="close-dialog">返回工作台</button>`, "evidence-dialog");
  }
}
