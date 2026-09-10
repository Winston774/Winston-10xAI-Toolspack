import { duration } from './utils.js';

// Primary footage under the playhead owns S/Q/W, independently of selection.
// Later placements win overlaps, matching the preview's stacking order.
export function clipAtPlayhead(project, time) {
  return project.clips.findLast(c => c.track === 'video' &&
    time > c.offset + 1e-6 && time < c.offset + duration(c) - 1e-6) || null;
}

export function playheadShortcut(event) {
  if (event.isComposing || event.repeat || event.ctrlKey || event.metaKey || event.altKey) return null;
  const target = event.target;
  if (target.isContentEditable ||
      (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) &&
       !target.matches('[data-caption-text], input[type="range"]'))) return null;
  return { s: 'split', q: 'trim-before', w: 'trim-after' }[event.key.toLowerCase()] || null;
}
