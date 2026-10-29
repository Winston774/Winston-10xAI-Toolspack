// A continuous Live stream has no guaranteed sentence boundaries. Both languages
// share one bounded reception window, so unequal text lengths cannot drift apart.
export function createLiveCaptions({ prefix, nextSequence, maxCharacters = 480 }) {
  if (!Number.isSafeInteger(maxCharacters) || maxCharacters < 1 || maxCharacters > 5000) throw new Error('字幕長度限制無效。');
  let active = null;
  let index = 0;
  function ensure(time) {
    if (!active) active = { id: `${prefix}_${index++}`, sequence: nextSequence(), original: '', translation: '', start: time, end: time, inputDone: false, outputDone: false, version: 0 };
    return active;
  }
  function snapshot(final) {
    active.version++;
    return { id: active.id, sequence: active.sequence, original: active.original, translation: active.translation,
      start: active.start, end: active.end, latencyMs: 0, partial: !final, version: active.version };
  }
  function finalize(cues) {
    if (active && (active.original.trim() || active.translation.trim())) cues.push(snapshot(true));
    active = null;
  }
  function push(event, time = 0) {
    if (!Number.isFinite(time) || time < 0) time = 0;
    // Validate both deltas before changing the shared accumulator.
    for (const side of ['input', 'output']) {
      const delta = event[side];
      if (delta && (typeof delta.text !== 'string' || delta.text.length > 16000 || (delta.finished !== undefined && typeof delta.finished !== 'boolean'))) throw new Error('字幕串流格式無效。');
    }
    const cues = [];
    let changed = false;
    for (const side of ['input', 'output']) {
      const delta = event[side];
      if (!delta) continue;
      const field = side === 'input' ? 'original' : 'translation';
      const text = [...delta.text];
      let offset = 0;
      while (offset < text.length) {
        const item = ensure(time);
        const room = maxCharacters - [...item[field]].length;
        if (!room) { finalize(cues); changed = false; continue; }
        const count = Math.min(room, text.length - offset);
        item[field] += text.slice(offset, offset + count).join('');
        offset += count;
        item.end = Math.max(item.end, time);
        item[`${side}Done`] = false;
        changed = true;
        if (offset < text.length) { finalize(cues); changed = false; }
      }
      if (active && delta.finished !== undefined) {
        active[`${side}Done`] = delta.finished;
        active.end = Math.max(active.end, time);
        changed = true;
      }
    }
    if (event.turnComplete || (active?.inputDone && active?.outputDone)) finalize(cues);
    else if (changed && active && (active.original.trim() || active.translation.trim())) cues.push(snapshot(false));
    return cues;
  }
  return { push, finish: time => push({ turnComplete: true }, time) };
}
