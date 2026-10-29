(() => {
  'use strict';
  if (globalThis.WinstonCueStore) return;

  function createCueStore() {
    let sessionId = null;
    let revision = -1;
    let sequence = -1;
    let history = [];
    const ids = new Map();

    function reset(nextSessionId, nextRevision) {
      if (typeof nextSessionId !== 'string' || !nextSessionId || !Number.isInteger(nextRevision) || nextRevision < 0) return false;
      if (nextSessionId === sessionId && nextRevision < revision) return false;
      sessionId = nextSessionId;
      revision = nextRevision;
      sequence = -1;
      history = [];
      ids.clear();
      return true;
    }

    function add(message) {
      if (!sessionId || message?.sessionId !== sessionId || message.revision !== revision) return false;
      const item = message.cue;
      if (!item || typeof item.id !== 'string' || !item.id || item.id.length > 256) return false;
      const previous = ids.get(item.id);
      const live = typeof item.partial === 'boolean';
      if (!Number.isInteger(item.sequence) || item.sequence < 0 || (!previous && item.sequence <= sequence)) return false;
      if (previous && (!previous.partial || !live || item.sequence !== previous.sequence || !Number.isSafeInteger(item.version) || item.version <= previous.version)) return false;
      if (live && (!Number.isSafeInteger(item.version) || item.version < 1)) return false;
      if (typeof item.original !== 'string' || item.original.length > 5000 || typeof item.translation !== 'string' || item.translation.length > 5000) return false;
      if (live ? (!item.original.trim() && !item.translation.trim()) : (!item.original.trim() || !item.translation.trim())) return false;
      if (!Number.isFinite(item.start) || !Number.isFinite(item.end) || item.start < 0 || item.end < item.start) return false;
      const saved = Object.freeze({
        id: item.id, sequence: item.sequence,
        original: item.original.trim(), translation: item.translation.trim(),
        start: item.start, end: item.end,
        latencyMs: Number.isFinite(item.latencyMs) ? Math.max(0, item.latencyMs) : 0,
        ...(live ? { partial: item.partial, version: item.version } : {}),
      });
      sequence = Math.max(sequence, saved.sequence);
      ids.set(saved.id, saved);
      if (previous) history[history.findIndex(value => value.id === saved.id)] = saved;
      else history.push(saved);
      if (history.length > 50) ids.delete(history.shift().id);
      return true;
    }

    return Object.freeze({ reset, add, latest: () => history.at(-1) ?? null, getHistory: () => [...history] });
  }

  // The transcript is durable for the session; the reading surface has its own
  // clock and consumed offsets. Provider final markers must never extend it.
  function createCaptionDisplay({ minHoldMs = 2200, maxHoldMs = 6000, originalLimit = 120, translationLimit = 84 } = {}) {
    let sequence = -1;
    let id = null;
    let sides = {};
    const meaningful = value => /[\p{L}\p{N}]/u.test(value);
    const weight = value => [...value].reduce((sum, letter) => sum + (/[^\x00-\xff]/u.test(letter) ? 2 : 1), 0);
    const fresh = () => ({ full: '', consumed: 0, text: '', startedAt: 0, expiresAt: 0 });
    function reset() { sequence = -1; id = null; sides = { original: fresh(), translation: fresh() }; }
    function expire(side, now) {
      if (side.text && now >= side.expiresAt) { side.consumed = side.full.length; side.text = ''; }
    }
    function window(side, limit, now) {
      let remaining = side.full.slice(side.consumed);
      // Advance at a completed sentence once it has had a short reading slot.
      // Never jump on the first letter of the next sentence.
      if (now - side.startedAt >= 1500) {
        const boundary = /[.!?。！？][\s\u201d\u2019」』]*/gu;
        let match, next = 0;
        while ((match = boundary.exec(remaining))) {
          const end = match.index + match[0].length;
          if (weight(remaining.slice(end).trim()) >= 12) next = end;
        }
        if (next) { side.consumed += next; remaining = side.full.slice(side.consumed); side.startedAt = now; }
      }
      // Keep words and Unicode characters intact. Overflow skips old phrases;
      // it never builds a reading queue that falls further behind the speaker.
      while (weight(remaining) > limit) {
        let units = 0, end = 0, boundary = 0;
        for (const letter of remaining) {
          if (units + weight(letter) > limit) break;
          units += weight(letter); end += letter.length;
          if (/[\s,，、;；.!?。！？]/u.test(letter)) boundary = end;
        }
        const cut = boundary > end / 3 ? boundary : end;
        side.consumed += Math.max(1, cut);
        remaining = side.full.slice(side.consumed);
        side.startedAt = now;
      }
      side.text = remaining.trim();
    }
    function update(cue, now) {
      if (cue.sequence < sequence || (cue.sequence === sequence && cue.id !== id)) return false;
      if (cue.sequence > sequence) { reset(); sequence = cue.sequence; id = cue.id; }
      let changed = false;
      for (const name of ['original', 'translation']) {
        const side = sides[name];
        expire(side, now);
        const full = cue[name];
        if (full === side.full) continue;
        const correction = !full.startsWith(side.full);
        const added = full.startsWith(side.full) ? full.slice(side.full.length) : '';
        const expired = !side.text && side.consumed > 0;
        // A correction or punctuation-only finalization of an already read
        // passage is retained in history without bringing it back on screen.
        if (expired && !meaningful(added)) { side.full = full; side.consumed = full.length; continue; }
        if (!full.startsWith(side.full)) side.consumed = Math.min(side.consumed, full.length);
        side.full = full;
        if (!side.text) side.startedAt = now;
        window(side, name === 'original' ? originalLimit : translationLimit, now);
        if (!meaningful(side.text)) { side.text = ''; continue; }
        if (meaningful(added) || correction) side.expiresAt = now + Math.max(minHoldMs, Math.min(maxHoldMs, 1000 + weight(side.text) * 65));
        changed = true;
      }
      return changed;
    }
    function read(now) {
      for (const name of ['original', 'translation']) {
        const side = sides[name];
        expire(side, now);
        if (side.text) window(side, name === 'original' ? originalLimit : translationLimit, now);
      }
      return { original: sides.original.text, translation: sides.translation.text };
    }
    function setLimits(next) {
      originalLimit = Math.max(24, Math.min(120, next.original || originalLimit));
      translationLimit = Math.max(24, Math.min(84, next.translation || translationLimit));
    }
    function dismiss() { for (const side of Object.values(sides)) { side.consumed = side.full.length; side.text = ''; } }
    reset();
    return Object.freeze({ reset, update, read, setLimits, dismiss });
  }

  globalThis.WinstonCueStore = Object.freeze({ createCueStore, createCaptionDisplay });
})();
