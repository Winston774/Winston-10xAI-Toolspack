import {
  $,
  $$,
  esc,
  duration,
  total,
  shortTime,
  icon,
  mappedCaptions,
  sampleClipWaveform,
} from "./utils.js";
import { selectionBox, intersects, groupDelta } from "./timeline-gestures.js";
import { WaveformPainter } from "./waveform.js";

export class Timeline {
  constructor(root, { onSeek, onSelect, onSelectMany, onMoveMany, onTrim, onAdd }) {
    this.root = root;
    this.root.tabIndex = 0;
    this.root.setAttribute("aria-label", "時間軸片段操作區");
    Object.assign(this, { onSeek, onSelect, onSelectMany, onMoveMany, onTrim, onAdd });
    this.zoom = 55;
    this.selected = null;
    this.selectedIds = [];
    this.marqueeMode = true;
    this.snapping = true;
    this.time = 0;
    this.waveformPainter = new WaveformPainter(this);
  }
  setProject(project, selected, selectedIds = []) {
    if (this.project && this.project.id !== project.id) this.cancelGesture?.();
    this.project = project;
    this.selected = selected;
    this.selectedIds = selectedIds.filter(id => project.clips.some(c => c.id === id));
    this.render();
  }
  render() {
    this.waveformPainter.timeline = this;
    // Scrubbing belongs to the stable timeline root, not the rebuilt clips.
    if (this.gestureKind !== "scrub") this.cancelGesture?.();
    const p = this.project;
    if (!p) return;
    const span = Math.max(total(p) + 5, 20);
    const width = Math.max(800, span * this.zoom);
    const interval = this.zoom < 30 ? 10 : this.zoom < 65 ? 5 : 2;
    let ticks = "";
    for (let t = 0; t <= span; t += interval)
      ticks += `<span class="ruler-tick" style="left:${t * this.zoom}px">${shortTime(t)}</span>`;
    const oldScroll = $(".timeline-scroll", this.root)?.scrollLeft || 0;
    const oldScrollTop = $(".timeline-scroll", this.root)?.scrollTop || 0;
    const track = (key, label, note) =>
      `<div class="track-row"><div class="track-label">${icon(key === "audio" ? "audio" : "film", 15)}<span>${label}<small>${note}</small></span></div><div class="track-content ${key}-track" data-track="${key}" style="width:${width}px">${p.clips
        .filter((c) => c.track === key)
        .map((c) => this.clipHTML(c))
        .join("")}</div></div>`;
    const captions = mappedCaptions(p)
      .map(
        (s) =>
          `<button class="caption-block" style="left:${s.start * this.zoom}px;width:${Math.max(4, (s.end - s.start) * this.zoom)}px" data-time="${s.start}" title="${esc(s.text)}">${esc(s.text)}</button>`,
      )
      .join("");
    const titles = p.titles
      .map(
        (t) =>
          `<button class="title-block" style="left:${t.start * this.zoom}px;width:${(t.end - t.start) * this.zoom}px" data-title="${esc(t.id)}">${esc(t.text)}</button>`,
      )
      .join("");
    const titleRow = p.titles.length
      ? `<div class="track-row caption-row"><div class="track-label">${icon("text", 15)}<span>文字<small>T1</small></span></div><div class="track-content" data-track="titles" style="width:${width}px">${titles}</div></div>`
      : "";
    this.root.classList.toggle("marquee-mode", this.marqueeMode);
    this.root.innerHTML = `<div class="timeline-scroll"><div class="timeline-inner" style="min-width:${width + 118}px">
    <div class="ruler-row"><div class="track-label">時間軸</div><div class="ruler" style="width:${width}px">${ticks}</div></div>
    ${track("overlay", "疊加畫面", "V2")}${track("video", "主影片", "V1")}
    ${this.waveformHTML(width)}
    <div class="track-row caption-row"><div class="track-label">${icon("captions", 15)}<span>字幕<small>S1</small></span></div><div class="track-content" data-track="captions" style="width:${width}px">${captions}</div></div>
    ${titleRow}${track("audio", "音訊", "A1")}<div class="playhead" title="拖拉整條播放頭以定位" style="left:${118 + this.time * this.zoom}px"><span></span></div>
  </div></div>`;
    $(".timeline-scroll", this.root).scrollLeft = oldScroll;
    $(".timeline-scroll", this.root).scrollTop = oldScrollTop;
    $(".timeline-scroll", this.root).addEventListener("scroll", () => this.waveformPainter.schedule(), { passive: true });
    this.waveformPainter.schedule();
    this.rebaseScrub();
    this.setSelection(this.selectedIds);
    $(".ruler", this.root).addEventListener("pointerdown", (e) =>
      this.scrub(e),
    );
    $(".playhead", this.root).addEventListener("pointerdown", e => this.scrub(e));
    $(".source-waveform-track", this.root)?.addEventListener("pointerdown", e => {
      if (e.button !== 0 || document.body.classList.contains("working")) return;
      const id = e.target.closest("[data-waveform-id]")?.dataset.waveformId;
      if (id) this.onSelectMany([id]);
      this.scrub(e);
    });
    $$("[data-waveform-id]", this.root).forEach(el => el.addEventListener("click", e => {
      if (e.detail !== 0) return;
      const clip = p.clips.find(c => c.id === el.dataset.waveformId);
      this.onSelectMany([clip.id]);
      this.onSeek(clip.offset);
    }));
    $(".timeline-inner", this.root).addEventListener("pointerdown", e => {
      if (e.defaultPrevented || e.target.closest(".track-label,.ruler,.clip-block,.caption-block,.title-block,.playhead")) return;
      if (this.marqueeMode || e.shiftKey) this.marquee(e);
      else this.scrub(e);
    });
    $$(".clip-block", this.root).forEach((el) => {
      el.addEventListener("pointerdown", (e) => this.drag(e, el));
      el.addEventListener("click", (e) => {
        if (e.detail === 0) this.onSelect(el.dataset.id);
      });
    });
    $$("[data-time]", this.root).forEach(
      (el) => (el.onclick = () => this.onSeek(+el.dataset.time)),
    );
    $$("[data-title]", this.root).forEach(
      (el) => (el.onclick = () => this.onSelect(el.dataset.title, "title")),
    );
    $$(".track-content", this.root).forEach((el) => {
      el.addEventListener("dragover", (e) => {
        e.preventDefault();
        el.classList.add("drag-over");
      });
      el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
      el.addEventListener("drop", (e) => {
        e.preventDefault();
        el.classList.remove("drag-over");
        const id = e.dataTransfer.getData("application/x-editor-media");
        if (id && ["video", "audio", "overlay"].includes(el.dataset.track))
          this.onAdd(
            id,
            el.dataset.track,
            Math.max(
              0,
              (e.clientX - el.getBoundingClientRect().left) / this.zoom,
            ),
          );
      });
      el.addEventListener("dblclick", (e) => {
        if (e.target === el)
          this.onSeek(
            Math.max(
              0,
              (e.clientX - el.getBoundingClientRect().left) / this.zoom,
            ),
          );
      });
    });
  }
  waveformHTML(width) {
    const clips = this.project.clips.filter(c => c.track === "video");
    const segments = clips.map(c => {
      const media = this.project.media.find(m => m.id === c.media_id);
      const note = media?.has_audio ? (c.muted || c.volume === 0 ? "原音波形（已靜音）" : "原音波形") : "無音軌";
      return `<button class="source-waveform-segment" data-waveform-id="${esc(c.id)}" style="left:${c.offset * this.zoom}px;width:${duration(c) * this.zoom}px" aria-label="${esc(media?.name || "片段")}，${note}，點擊定位剪接" title="${esc(media?.name)} · ${note} · 拖拉定位，S 分割">${media?.has_audio ? "" : '<span class="no-source-audio">無音軌</span>'}</button>`;
    }).join("");
    return `<div class="track-row source-waveform-row"><div class="track-label" title="主影片原始音訊振幅；點擊或拖拉波形定位剪接"><span>原音波形<small>V1</small></span></div><div class="track-content source-waveform-track" data-track="source-waveform" style="width:${width}px">${segments}<canvas class="source-waveform-canvas" aria-hidden="true"></canvas><span class="waveform-status" role="status"></span></div></div>`;
  }
  dispose() {
    this.cancelGesture?.();
    this.waveformPainter.dispose();
  }
  clipHTML(c) {
    const m = this.project.media.find((m) => m.id === c.media_id);
    const w = Math.max(5, duration(c) * this.zoom);
    const waveform = c.track === "video" ? [] : sampleClipWaveform(
      m,
      c,
      Math.min(70, Math.max(1, Math.floor(w / 3))),
    );
    return `<button class="clip-block ${c.track} ${this.selectedIds.includes(c.id) ? "selected" : ""}" aria-pressed="${this.selectedIds.includes(c.id)}" style="left:${c.offset * this.zoom}px;width:${w}px" data-id="${esc(c.id)}" aria-label="${esc(m?.name || "片段")}，${shortTime(c.offset)}，長度 ${duration(c).toFixed(2)} 秒" title="${esc(m?.name)} · 拖曳移動，邊緣修剪"><span class="trim-handle start" data-edge="start"></span><span class="clip-name">${icon(m?.kind === "audio" ? "audio" : m?.kind === "image" ? "image" : "film", 12)}${esc(m?.name || "片段")}${c.speed !== 1 ? ` · ${c.speed}×` : ""}</span>${waveform.length ? `<span class="waveform">${waveform.map((v) => `<i style="height:${v === null ? 0 : Math.max(2, v * 100)}%;${v === null ? "visibility:hidden" : ""}"></i>`).join("")}</span>` : `<span class="clip-duration">${duration(c).toFixed(1)} s</span>`}<span class="trim-handle end" data-edge="end"></span></button>`;
  }
  setSelection(ids) {
    this.selectedIds = [...new Set(ids)];
    this.paintSelection(ids);
    const count = document.querySelector("#timeline-selection-count");
    if (count) count.textContent = ids.length ? `已選 ${ids.length} 段` : "";
  }
  paintSelection(ids) {
    $$("[data-waveform-id]", this.root).forEach(el => {
      el.classList.toggle("selected", ids.includes(el.dataset.waveformId));
      el.setAttribute("aria-pressed", String(ids.includes(el.dataset.waveformId)));
    });
    $$(".clip-block", this.root).forEach(el => {
      el.classList.toggle("selected", ids.includes(el.dataset.id));
      el.setAttribute("aria-pressed", String(ids.includes(el.dataset.id)));
    });
  }
  trackPointer(e, move, finish, cancel = () => {}, kind = "edit") {
    this.cancelGesture?.();
    this.gestureKind = kind;
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
      window.removeEventListener("blur", abort);
      window.removeEventListener("keydown", onKey, true);
      this.root.removeEventListener("lostpointercapture", onCancel);
      this.cancelGesture = null;
      this.gestureKind = null;
      this.scrubState = null;
      if (kind === "scrub" && this.root.hasPointerCapture?.(e.pointerId))
        this.root.releasePointerCapture(e.pointerId);
    };
    const onMove = ev => {
      if (ev.pointerId !== e.pointerId) return;
      if (ev.buttons === 0) { cleanup(); finish(ev); }
      else move(ev);
    };
    const onUp = ev => { if (ev.pointerId === e.pointerId) { cleanup(); finish(ev); } };
    const abort = () => { cleanup(); cancel(); };
    const onCancel = ev => { if (ev.pointerId === e.pointerId) abort(); };
    const onKey = ev => { if (ev.key === "Escape") { ev.preventDefault(); ev.stopImmediatePropagation(); abort(); } };
    this.cancelGesture = abort;
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    window.addEventListener("blur", abort);
    window.addEventListener("keydown", onKey, true);
    if (kind === "scrub") {
      this.root.addEventListener("lostpointercapture", onCancel);
      this.root.setPointerCapture(e.pointerId);
    }
  }
  scrub(e) {
    if (e.button !== 0 || document.body.classList.contains("working")) return;
    e.preventDefault();
    this.root.focus({ preventScroll: true });
    const session = { initial: this.time, x: e.clientX, offset: 0 };
    const update = (x) => {
      session.x = x;
      this.onSeek(Math.min(total(this.project), Math.max(0, this.scrubTime(x) + session.offset)));
    };
    this.trackPointer(e, ev => update(ev.clientX), ev => update(ev.clientX),
      () => this.onSeek(session.initial), "scrub");
    this.scrubState = session;
    update(e.clientX);
  }
  scrubTime(x) {
    return (x - $(".ruler", this.root).getBoundingClientRect().left) / this.zoom;
  }
  rebaseScrub() {
    if (!this.scrubState) return;
    this.scrubState.offset = this.time - this.scrubTime(this.scrubState.x);
    // Escape may cancel subsequent movement, but cannot restore a pre-edit time.
    this.scrubState.initial = this.time;
  }
  marquee(e) {
    if (e.button !== 0 || document.body.classList.contains("working")) return;
    e.preventDefault();
    this.root.focus({ preventScroll: true });
    const inner = $(".timeline-inner", this.root);
    const point = ev => { const r = inner.getBoundingClientRect(); return { x: Math.max(118, ev.clientX-r.left), y: ev.clientY-r.top }; };
    const origin = point(e), original = [...this.selectedIds];
    const seed = e.ctrlKey || e.metaKey ? original : [];
    const box = document.createElement("div");
    box.className = "selection-marquee";
    inner.append(box);
    let ids = seed;
    const move = ev => {
      const bounds = selectionBox(origin, point(ev)), r = inner.getBoundingClientRect();
      Object.assign(box.style, { left: `${bounds.left}px`, top: `${bounds.top}px`, width: `${bounds.right-bounds.left}px`, height: `${bounds.bottom-bounds.top}px` });
      ids = [...new Set([...seed, ...$$(".clip-block", inner).filter(el => {
        const c = el.getBoundingClientRect();
        return intersects(bounds, { left: c.left-r.left, right: c.right-r.left, top: c.top-r.top, bottom: c.bottom-r.top });
      }).map(el => el.dataset.id)])];
      this.paintSelection(ids);
    };
    this.trackPointer(e, move, ev => { move(ev); box.remove(); this.onSelectMany(ids); },
      () => { box.remove(); this.paintSelection(original); });
  }
  drag(e, el) {
    if (e.button !== 0 || document.body.classList.contains("working")) return;
    e.preventDefault();
    this.root.focus({ preventScroll: true });
    const c = this.project.clips.find((c) => c.id === el.dataset.id);
    const edge = e.target.dataset.edge;
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      this.onSelectMany(this.selectedIds.includes(c.id) ? this.selectedIds.filter(id => id !== c.id) : [...this.selectedIds, c.id]);
      return;
    }
    if (edge || !this.selectedIds.includes(c.id)) this.onSelectMany([c.id]);
    const ids = [...this.selectedIds];
    const origin = e.clientX;
    let delta = 0;
    let moved = false;
    const move = (ev) => {
      if (!moved && Math.abs(ev.clientX-origin) < 4) return;
      moved = true;
      delta = (ev.clientX - origin) / this.zoom;
      if (!edge) delta = groupDelta(this.project.clips, ids, delta, { snapping: this.snapping, time: this.time, zoom: this.zoom });
      if (edge) {
        el.style.opacity = ".6";
      } else $$(".clip-block", this.root).filter(node => ids.includes(node.dataset.id)).forEach(node => {
        const clip = this.project.clips.find(x => x.id === node.dataset.id);
        node.style.left = `${(clip.offset + delta) * this.zoom}px`;
      });
      if (!edge) {
        $$("[data-waveform-id]", this.root).forEach(node => {
          const clip = this.project.clips.find(x => x.id === node.dataset.waveformId);
          node.style.left = `${(clip.offset + (ids.includes(clip.id) ? delta : 0)) * this.zoom}px`;
        });
        this.waveformPainter.timeline = { root: this.root, zoom: this.zoom, project: {
          ...this.project, clips: this.project.clips.map(clip => ids.includes(clip.id) ? { ...clip, offset: clip.offset + delta } : clip),
        }};
        this.waveformPainter.schedule();
      }
    };
    const up = async ev => {
      move(ev);
      try {
        if (moved && Math.abs(delta) > 1e-7) {
          if (edge) await this.onTrim(c, edge, delta);
          else await this.onMoveMany(ids, delta);
        }
      } finally { this.render(); }
    };
    this.trackPointer(e, move, up, () => this.render());
  }
  setTime(time) {
    this.time = time;
    const el = $(".playhead", this.root);
    if (el) el.style.left = `${118 + time * this.zoom}px`;
  }
  setZoom(value) {
    this.zoom = value;
    this.render();
  }
  revealTime(time) {
    const scroller = $(".timeline-scroll", this.root);
    if (!scroller) return;
    const x = 118 + time * this.zoom;
    if (x < scroller.scrollLeft + 138 || x > scroller.scrollLeft + scroller.clientWidth - 32)
      scroller.scrollLeft = Math.max(0, x - Math.max(150, scroller.clientWidth / 3));
  }
}
