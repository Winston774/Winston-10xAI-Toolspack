import {
  $,
  esc,
  total,
  mappedCaptions,
  duration,
  clock,
  icon,
  clipFade,
} from "./utils.js";

/** The player reads the saved edit decision list; original media stays untouched. */
export class Preview {
  constructor(stage, onTime, onState) {
    this.stage = stage;
    this.onTime = onTime;
    this.onState = onState;
    this.time = 0;
    this.playing = false;
    this.project = null;
    this.nodes = new Map();
    this.solo = null;
    this.frame = 0;
    this.caption = document.createElement("div");
    this.caption.className = "preview-caption";
    stage.append(this.caption);
    this.titleLayer = document.createElement("div");
    this.titleLayer.className = "title-layer";
    this.titleLayer.style.zIndex = "7";
    stage.append(this.titleLayer);
    this.stage.style.backgroundColor = "#000";
    this.viewport = stage.closest(".preview-viewport") || stage.parentElement;
    this.resizeObserver = new ResizeObserver(() => this.fitStage());
    if (this.viewport) this.resizeObserver.observe(this.viewport);
  }
  fitStage() {
    if (!this.project || !this.viewport) return;
    const style = getComputedStyle(this.viewport),
      px = (value) => parseFloat(value) || 0;
    const availableWidth =
      this.viewport.clientWidth -
      px(style.paddingLeft) -
      px(style.paddingRight);
    const availableHeight =
      this.viewport.clientHeight -
      px(style.paddingTop) -
      px(style.paddingBottom);
    if (availableWidth <= 0 || availableHeight <= 0) return;
    const ratio = this.project.width / this.project.height,
      width = Math.min(availableWidth, availableHeight * ratio);
    this.stage.style.width = `${width}px`;
    this.stage.style.height = `${width / ratio}px`;
  }
  setProject(project) {
    this.pause();
    this.solo = null;
    this.project = project;
    this.captions = mappedCaptions(project);
    for (const node of this.nodes.values()) {
      node.pause?.();
      node.remove();
    }
    this.nodes.clear();
    this.stage.style.aspectRatio = `${project.width} / ${project.height}`;
    this.fitStage();
    for (const clip of project.clips) {
      const media = project.media.find((m) => m.id === clip.media_id);
      if (!media) continue;
      const el = document.createElement(
        clip.track === "audio" || media.kind === "audio"
          ? "audio"
          : media.kind === "image"
            ? "img"
            : "video",
      );
      el.src = media.url || "";
      el.preload = "metadata";
      el.playsInline = true;
      el.className = "preview-media";
      el.dataset.clipId = clip.id;
      el.style.backgroundColor = "transparent";
      el.addEventListener("error", () => {
        el.dataset.error = "true";
      });
      this.stage.insertBefore(el, this.caption);
      this.nodes.set(clip.id, el);
    }
    this.seek(Math.min(this.time, total(project)));
  }
  seek(time) {
    this.time = Math.max(0, Math.min(total(this.project), Number(time) || 0));
    this.baseTime = this.time;
    this.baseClock = performance.now();
    this.paint(true);
    this.onTime?.(this.time);
  }
  play() {
    if (!this.project || !total(this.project)) return;
    if (this.time >= total(this.project) - 0.03) this.seek(0);
    this.solo = null;
    this.playing = true;
    this.baseTime = this.time;
    this.baseClock = performance.now();
    this.onState?.(true);
    this.tick();
  }
  pause() {
    this.playing = false;
    cancelAnimationFrame(this.frame);
    for (const n of this.nodes.values()) n.pause?.();
    this.onState?.(false);
  }
  toggle() {
    this.playing ? this.pause() : this.play();
  }
  tick() {
    if (!this.playing) return;
    this.time = this.baseTime + (performance.now() - this.baseClock) / 1000;
    if (this.time >= total(this.project)) {
      this.time = total(this.project);
      this.pause();
    }
    this.paint();
    this.onTime?.(this.time);
    if (this.playing) this.frame = requestAnimationFrame(() => this.tick());
  }
  paint(force = false) {
    if (!this.project) return;
    const p = this.project;
    let visible = false;
    for (const c of p.clips) {
      const el = this.nodes.get(c.id);
      if (!el) continue;
      const active =
        this.time >= c.offset && this.time < c.offset + duration(c);
      const visual = c.track !== "audio" && el.tagName !== "AUDIO";
      el.hidden = !active || !visual;
      if (!active) {
        el.pause?.();
        continue;
      }
      if (visual) visible = true;
      const source = c.start + (this.time - c.offset) * (c.speed || 1);
      const fade = clipFade(c, this.time);
      if (el.tagName !== "IMG") {
        if (force || Math.abs(el.currentTime - source) > 0.22)
          try {
            el.currentTime = source;
          } catch {}
        el.playbackRate = c.speed || 1;
        el.volume = Math.min(1, Math.max(0, (c.volume ?? 1) * fade));
        el.muted = !!c.muted;
        if (this.playing && el.paused) el.play().catch(() => {});
      }
      el.style.zIndex = c.track === "overlay" ? "2" : "1";
      el.style.opacity = String((c.opacity ?? 1) * fade);
      el.style.filter = `brightness(${1 + (c.brightness || 0)}) contrast(${c.contrast ?? 1}) saturate(${c.saturation ?? 1})`;
      el.style.transform = `translate(${(100 * (c.x || 0)) / p.width}%,${(100 * (c.y || 0)) / p.height}%) rotate(${c.rotation || 0}deg) scale(${c.scale || 1})`;
    }
    const text = (this.captions || [])
      .filter((s) => this.time >= s.start && this.time < s.end)
      .map((s) => s.text)
      .join("\n");
    const style = p.caption_style || {};
    this.caption.textContent = text;
    this.caption.hidden = !text;
    this.caption.style.color = style.color || "#fff";
    this.caption.style.backgroundColor = style.background || "#000000";
    this.caption.style.fontSize = `${((style.font_size || 48) / p.width) * 100}cqw`;
    this.caption.style.bottom =
      style.position === "top"
        ? "auto"
        : style.position === "center"
          ? "45%"
          : "7%";
    this.caption.style.top = style.position === "top" ? "7%" : "auto";
    this.titleLayer.replaceChildren();
    for (const t of p.titles || [])
      if (this.time >= t.start && this.time < t.end) {
        const el = document.createElement("div");
        el.className = "preview-title";
        el.textContent = t.text;
        el.style.fontSize = `${((t.font_size || 64) / p.width) * 100}cqw`;
        el.style.color = t.color || "#fff";
        el.style.left = `${50 + (100 * (t.x || 0)) / p.width}%`;
        el.style.top = `${50 + (100 * (t.y || 0)) / p.height}%`;
        this.titleLayer.append(el);
      }
    this.stage.classList.toggle("has-frame", visible);
    const blank = $("#preview-empty");
    if (blank) blank.hidden = visible || p.clips.length > 0;
  }
  destroy() {
    this.pause();
    this.resizeObserver.disconnect();
    for (const node of this.nodes.values()) {
      node.pause?.();
      node.removeAttribute("src");
      node.load?.();
    }
    this.nodes.clear();
  }
}
