export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
export const duration = (clip) => (clip.end - clip.start) / (clip.speed || 1);
export const total = (project) =>
  Math.max(
    0,
    ...(project?.clips || []).map((c) => c.offset + duration(c)),
    ...(project?.titles || []).map((t) => t.end),
  );
export const clock = (seconds, precise = false) => {
  let ms = Math.round(Math.max(0, seconds || 0) * 1000);
  const h = Math.floor(ms / 3600000);
  ms %= 3600000;
  const m = Math.floor(ms / 60000);
  ms %= 60000;
  const s = Math.floor(ms / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}${precise ? "." + String(ms % 1000).padStart(3, "0") : ""}`;
};
export const shortTime = (seconds) =>
  `${Math.floor(Math.max(0, seconds) / 60)
    .toString()
    .padStart(
      2,
      "0",
    )}:${(Math.max(0, seconds) % 60).toFixed(1).padStart(4, "0")}`;
export const field = (label, name, value, attrs = "") =>
  `<label class="field"><span>${label}</span><input name="${name}" value="${esc(value)}" ${attrs}></label>`;
export function icon(name, size = 20) {
  const paths = {
    folder: '<path d="M3 7V5h6l2 2h10v12H3Z"/>',
    film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
    cut: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8.5 7.5 12 12m-12-3 12-12"/>',
    captions:
      '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M10 9H6v6h4m8-6h-4v6h4"/>',
    audio:
      '<path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
    text: '<path d="M4 7V4h16v3M12 4v16m-4 0h8"/>',
    sliders:
      '<path d="M4 3v7m0 4v7m8-18v12m0 4v2m8-18v2m0 4v12M1 10h6m2 5h6m2-10h6"/>',
    agent:
      '<rect x="4" y="7" width="16" height="13" rx="3"/><path d="M12 3v4M1 12h3m16 0h3M8 12v2m8-2v2m-7 3h6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
    download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    undo: '<path d="m8 4-5 5 5 5M3 9h11a7 7 0 0 1 0 14"/>',
    redo: '<path d="m16 4 5 5-5 5m5-5H10a7 7 0 0 0 0 14"/>',
    play: '<path d="m8 4 12 8-12 8Z"/>',
    pause: '<path d="M8 4v16M16 4v16"/>',
    prev: '<path d="M5 5v14M19 5 7 12l12 7Z"/>',
    next: '<path d="M19 5v14M5 5l12 7-12 7Z"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 5V3H3v13h2"/>',
    paste: '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M9 11h6m-6 4h6"/>',
    zoom: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M7 10h6m-3-3v6"/>',
    fit: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
    check: '<path d="m4 12 5 5L20 6"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    home: '<path d="m3 10 9-7 9 7v11h-6v-8H9v8H3Z"/>',
    help: '<circle cx="12" cy="12" r="9"/><path d="M9 8a3 3 0 0 1 6 1c0 2-3 2-3 5m0 3h.01"/>',
    link: '<path d="m10 14 4-4M8 16l-2 2a4 4 0 0 1-6-6l4-4m12 0 2-2a4 4 0 0 1 6 6l-4 4"/>',
    spark:
      '<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z"/>',
    volume:
      '<path d="M3 9h4l5-5v16l-5-5H3ZM16 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
    image:
      '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
    save: '<path d="M4 3h14l3 3v15H3V3Zm3 0v6h10V3M7 21v-8h10v8"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.film}</svg>`;
}
export function mappedCaptions(project) {
  const result = [];
  for (const clip of project?.clips || []) {
    if (clip.track !== "video") continue;
    for (const caption of project.captions || []) {
      if (clip.media_id !== caption.media_id) continue;
      const start = Math.max(clip.start, caption.start),
        end = Math.min(clip.end, caption.end);
      if (end - start <= 1e-7) continue;
      const map = (time) =>
        clip.offset + (time - clip.start) / (clip.speed || 1);
      const item = {
        ...caption,
        id: `${caption.id}:${clip.id}`,
        source_caption_id: caption.id,
        clip_id: clip.id,
        start: map(start),
        end: map(end),
      };
      if (caption.words?.length) {
        const words = caption.words.filter(
          (word) =>
            (word.start < end && word.end > start) ||
            (word.start === word.end &&
              start <= word.start &&
              word.start < end),
        );
        if (!words.length) continue;
        item.text = words
          .map((word) => word.text)
          .join("")
          .trim();
        item.words = words.map((word) => ({
          ...word,
          start: map(Math.max(start, word.start)),
          end: map(Math.min(end, word.end)),
        }));
      }
      result.push(item);
    }
  }
  return result.sort(
    (a, b) =>
      a.start - b.start ||
      a.end - b.end ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
}

/** Match the two chained FFmpeg fades after speed adjustment, in timeline seconds. */
export function clipFade(clip, time) {
  const length = duration(clip),
    local = time - clip.offset;
  if (length <= 0 || local < 0 || local >= length) return 0;
  const fadeIn = Math.min(length, Math.max(0, clip.fade_in || 0));
  const fadeOut = Math.min(length, Math.max(0, clip.fade_out || 0));
  return (
    (fadeIn ? Math.min(1, local / fadeIn) : 1) *
    (fadeOut ? Math.min(1, (length - local) / fadeOut) : 1)
  );
}

/** Peak-sample only the clip's source window. null means that section was not measured. */
export function sampleClipWaveform(media, clip, count = 70) {
  const values = media?.waveform,
    extent = Number(media?.waveform_duration ?? media?.duration);
  const start = Number(clip.start),
    end = Number(clip.end);
  if (
    !Array.isArray(values) ||
    !values.length ||
    !Number.isFinite(extent) ||
    extent <= 0 ||
    !Number.isFinite(start) ||
    !Number.isFinite(end) ||
    end <= start ||
    start >= extent ||
    end <= 0
  )
    return [];
  const bins = Math.max(1, Math.min(240, Math.floor(Number(count) || 1)));
  return Array.from({ length: bins }, (_, index) => {
    const left = start + ((end - start) * index) / bins,
      right = start + ((end - start) * (index + 1)) / bins;
    if (left >= extent || right <= 0) return null;
    const first = Math.max(0, Math.floor((left / extent) * values.length));
    const last = Math.min(
      values.length,
      Math.ceil((Math.min(extent, right) / extent) * values.length),
    );
    let peak = 0;
    for (let i = first; i < last; i++)
      if (Number.isFinite(values[i]))
        peak = Math.max(peak, Math.abs(values[i]));
    return Math.min(1, peak);
  });
}
