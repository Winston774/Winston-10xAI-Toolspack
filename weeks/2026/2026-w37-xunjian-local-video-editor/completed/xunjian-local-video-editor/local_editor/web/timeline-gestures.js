import { duration } from "./utils.js";

export function selectionBox(a, b) {
  return { left: Math.min(a.x, b.x), top: Math.min(a.y, b.y),
    right: Math.max(a.x, b.x), bottom: Math.max(a.y, b.y) };
}

export function intersects(a, b) {
  return a.left <= b.right && a.right >= b.left && a.top <= b.bottom && a.bottom >= b.top;
}

export function groupDelta(clips, ids, desired, { snapping = false, time = 0, zoom = 55 } = {}) {
  const selected = clips.filter(c => ids.includes(c.id));
  if (!selected.length) return 0;
  const minimum = -Math.min(...selected.map(c => c.offset));
  let delta = Math.max(minimum, desired);
  if (snapping) {
    const points = [0, time, ...clips.filter(c => !ids.includes(c.id)).flatMap(c => [c.offset, c.offset + duration(c)])];
    let best = 8 / zoom;
    let correction = 0;
    for (const clip of selected) {
      for (const edge of [clip.offset, clip.offset + duration(clip)]) {
        for (const point of points) {
          const difference = point - (edge + delta);
          if (Math.abs(difference) < best && delta + difference >= minimum) {
            best = Math.abs(difference);
            correction = difference;
          }
        }
      }
    }
    delta += correction;
  }
  return delta;
}
