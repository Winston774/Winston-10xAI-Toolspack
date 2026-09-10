import { duration } from "./utils.js";

const CHUNK_SECONDS = 30;

/** Source interval visible after trim, speed, timeline placement and scrolling. */
export function waveformWindow(clip, zoom, left, right) {
  const x = Math.max(left, clip.offset * zoom);
  const end = Math.min(right, (clip.offset + duration(clip)) * zoom);
  if (end <= x) return null;
  const source = pixel => clip.start + (pixel / zoom - clip.offset) * (clip.speed || 1);
  return { x, width: end - x, start: source(x), end: Math.min(clip.end, source(end)) };
}

export function waveformChunks(start, end) {
  const chunks = [];
  for (let i = Math.floor(start / CHUNK_SECONDS); i * CHUNK_SECONDS < end - 1e-8; i++) chunks.push(i);
  return chunks;
}

/** null means unavailable, zero is measured silence. Keep one scale across cuts. */
export function waveformPeak(chunks, start, end) {
  let peak = 0;
  for (const index of waveformChunks(start, end)) {
    const data = chunks.get(index);
    if (!data || start >= data.end || (end > data.end + 1e-6 && end <= (index + 1) * CHUNK_SECONDS)) return null;
    const first = Math.max(0, Math.floor((start - data.start) / data.bucket_seconds + 1e-7));
    const last = Math.min(data.peaks.length, Math.ceil((end - data.start) / data.bucket_seconds - 1e-7));
    for (let i = first; i < last; i++) peak = Math.max(peak, data.peaks[i]);
  }
  return peak;
}

/** One viewport-sized canvas, with shared source chunks across splits and undo. */
export class WaveformPainter {
  constructor(timeline) {
    this.timeline = timeline;
    this.cache = new Map();
    this.generation = 0;
    if (typeof ResizeObserver !== "undefined") {
      this.observer = new ResizeObserver(() => this.schedule());
      this.observer.observe(timeline.root);
    }
  }
  schedule() {
    this.generation++;
    if (typeof requestAnimationFrame === "undefined") return;
    cancelAnimationFrame(this.frame);
    this.frame = requestAnimationFrame(() => this.paint());
  }
  dispose() {
    this.generation++;
    this.observer?.disconnect();
    if (typeof cancelAnimationFrame !== "undefined") cancelAnimationFrame(this.frame);
    this.cache.clear();
  }
  async load(url) {
    let entry = this.cache.get(url);
    if (!entry) {
      entry = {};
      this.cache.set(url, entry);
      entry.promise = fetch(url).then(async response => {
        if (!response.ok) throw new Error("波形載入失敗，請重新整理重試");
        const data = await response.json();
        if (!Array.isArray(data.peaks)) throw new Error("波形資料無法讀取");
        entry.data = data;
      }).catch(() => { entry.error = true; });
    }
    await entry.promise;
    if (this.cache.size > 128) for (const [key, item] of this.cache) {
      if (key !== url && (item.data || item.error)) this.cache.delete(key);
      if (this.cache.size <= 128) break;
    }
    return entry;
  }
  async paint() {
    const { root, project, zoom } = this.timeline;
    const canvas = root.querySelector(".source-waveform-canvas");
    const track = root.querySelector(".source-waveform-track");
    const scroll = root.querySelector(".timeline-scroll");
    if (!canvas || !project || !root.isConnected) return;
    const generation = this.generation;
    const left = scroll.scrollLeft;
    const width = Math.max(1, scroll.clientWidth - 118);
    const height = 62;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.left = `${left}px`;
    canvas.style.width = `${width}px`;
    canvas.width = Math.ceil(width * ratio);
    canvas.height = height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    const theme = getComputedStyle(canvas);
    const waveformColor = theme.getPropertyValue("--waveform-color").trim();
    const mutedColor = theme.getPropertyValue("--waveform-muted").trim();
    const visible = project.clips.filter(c => c.track === "video").map(clip => {
      const media = project.media.find(m => m.id === clip.media_id);
      return { clip, media, view: waveformWindow(clip, zoom, left, left + width) };
    }).filter(item => item.view && item.media?.has_audio);
    const pending = new Set();
    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      let failed = false, loading = false;
      for (const { clip, media, view } of visible) {
        const chunks = new Map();
        for (const index of waveformChunks(view.start, view.end)) {
          const url = `/api/projects/${project.id}/media/${media.id}/peaks?chunk=${index}`;
          const entry = this.cache.get(url);
          if (entry?.data) chunks.set(index, entry.data);
          else if (entry?.error) failed = true;
          else { pending.add(url); loading = true; }
        }
        const x = view.x - left;
        // Shared square-root display scale makes quiet speech legible; no
        // per-clip normalization, so relative amplitudes survive every split.
        ctx.fillStyle = clip.muted || clip.volume === 0 ? mutedColor : waveformColor;
        for (let pixel = 0; pixel < view.width; pixel += 2) {
          const start = view.start + pixel / zoom * (clip.speed || 1);
          const end = Math.min(view.end, start + 2 / zoom * (clip.speed || 1));
          const peak = waveformPeak(chunks, start, end);
          if (peak === null) continue;
          const amplitude = Math.sqrt(Math.min(1, peak)) * 27;
          ctx.fillRect(x + pixel, height / 2 - Math.max(.5, amplitude), Math.min(1.5, view.width - pixel), Math.max(1, amplitude * 2));
        }
      }
      const status = track.querySelector(".waveform-status");
      status.textContent = failed ? "波形載入失敗，請重新整理重試" : loading ? "正在載入波形…" : "";
    };
    draw();
    for (const url of pending) {
      await this.load(url);
      if (generation !== this.generation || !canvas.isConnected) return;
      draw();
    }
  }
}
