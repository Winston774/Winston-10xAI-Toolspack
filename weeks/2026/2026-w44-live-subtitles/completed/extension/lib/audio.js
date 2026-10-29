function requireRate(rate) {
  if (!Number.isFinite(rate) || rate <= 0) throw new RangeError('Sample rate must be positive');
}

/** Stateless, windowed-sinc resampling. Keep input batches aligned to sample-rate ratios. */
export function resampleMono(samples, sourceRate, targetRate = 16000) {
  requireRate(sourceRate);
  requireRate(targetRate);
  if (sourceRate === targetRate) return new Float32Array(samples);
  const output = new Float32Array(Math.round(samples.length * targetRate / sourceRate));
  const step = sourceRate / targetRate;
  const cutoff = Math.min(1, targetRate / sourceRate) * 0.94;
  const radius = 16;
  for (let i = 0; i < output.length; i++) {
    const position = i * step;
    const first = Math.max(0, Math.ceil(position - radius));
    const last = Math.min(samples.length - 1, Math.floor(position + radius));
    let value = 0;
    let weightSum = 0;
    for (let j = first; j <= last; j++) {
      const distance = j - position;
      const angle = Math.PI * cutoff * distance;
      const sinc = Math.abs(angle) < 1e-8 ? 1 : Math.sin(angle) / angle;
      const weight = cutoff * sinc * (0.5 + 0.5 * Math.cos(Math.PI * distance / radius));
      value += (Number.isFinite(samples[j]) ? samples[j] : 0) * weight;
      weightSum += weight;
    }
    output[i] = weightSum ? value / weightSum : 0;
  }
  return output;
}

/** Little-endian RIFF/WAVE, mono signed 16-bit PCM. */
export function encodeWav(samples, sampleRate = 16000) {
  requireRate(sampleRate);
  const bytes = new Uint8Array(44 + samples.length * 2);
  const view = new DataView(bytes.buffer);
  const writeText = (offset, value) => {
    for (let i = 0; i < value.length; i++) bytes[offset + i] = value.charCodeAt(i);
  };
  writeText(0, 'RIFF');
  view.setUint32(4, bytes.length - 8, true);
  writeText(8, 'WAVE');
  writeText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const sample = Number.isFinite(samples[i]) ? Math.max(-1, Math.min(1, samples[i])) : 0;
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  return bytes;
}

/**
 * Energy-based segmentation of 16 kHz mono PCM (music can also trigger it).
 * push(samples, {mediaStart, mediaEnd}) and flush() return arrays of
 * {samples: Float32Array, start, end}. Durations are audio seconds; timestamps
 * are media seconds supplied by the caller, so playback speed remains correct.
 * flush preserves any final detected speech. reset discards all buffered audio.
 */
export function createSegmenter(options = {}) {
  const config = {
    sampleRate: 16000,
    frameDuration: 0.02,
    prefixDuration: 0.25,
    minSpeechDuration: 0.35,
    minSegmentDuration: 1,
    silenceDuration: 0.5,
    maxSegmentDuration: 6,
    rmsThreshold: 0.012,
    discontinuityTolerance: 0.05,
    ...options,
  };
  requireRate(config.sampleRate);
  for (const [key, value] of Object.entries(config)) {
    if (!Number.isFinite(value) || value < 0) throw new RangeError(`Invalid ${key}`);
  }
  const toSamples = (seconds) => Math.round(seconds * config.sampleRate);
  const frameSize = toSamples(config.frameDuration);
  const prefixSize = toSamples(config.prefixDuration);
  const speechSize = toSamples(config.minSpeechDuration);
  const minimumSize = toSamples(config.minSegmentDuration);
  const silenceSize = toSamples(config.silenceDuration);
  const maximumSize = toSamples(config.maxSegmentDuration);
  if (!frameSize || !maximumSize || frameSize > maximumSize || prefixSize >= maximumSize ||
      minimumSize > maximumSize || speechSize > maximumSize) {
    throw new RangeError('Invalid segment durations');
  }

  let pending = new Float32Array(frameSize);
  let pendingSize = 0;
  let pendingStart = 0;
  let pendingEnd = 0;
  let previousEnd = null;
  let prefix = [];
  let prefixLength = 0;
  let active = null;

  function reset() {
    pending = new Float32Array(frameSize);
    pendingSize = 0;
    previousEnd = null;
    prefix = [];
    prefixLength = 0;
    active = null;
  }

  function slicePart(part, from, to) {
    const duration = part.end - part.start;
    return {
      samples: part.samples.subarray(from, to),
      start: part.start + duration * from / part.samples.length,
      end: part.start + duration * to / part.samples.length,
    };
  }

  function rememberPrefix(part) {
    if (!prefixSize) return;
    prefix.push(part);
    prefixLength += part.samples.length;
    while (prefixLength > prefixSize) {
      const excess = prefixLength - prefixSize;
      if (prefix[0].samples.length <= excess) {
        prefixLength -= prefix.shift().samples.length;
      } else {
        prefix[0] = slicePart(prefix[0], excess, prefix[0].samples.length);
        prefixLength -= excess;
      }
    }
  }

  function finish(output, partial = false) {
    if (active && active.voiced > 0 && (partial || active.continuation || active.voiced >= speechSize)) {
      const samples = new Float32Array(active.length);
      let offset = 0;
      for (const part of active.parts) {
        samples.set(part.samples, offset);
        offset += part.samples.length;
      }
      output.push({ samples, start: active.parts[0].start, end: active.parts.at(-1).end });
    }
    active = null;
  }

  function acceptFrame(frame, output) {
    let energy = 0;
    for (const value of frame.samples) energy += value * value;
    const voiced = Math.sqrt(energy / frame.samples.length) >= config.rmsThreshold;
    let offset = 0;
    while (offset < frame.samples.length) {
      if (!active) {
        if (!voiced) {
          rememberPrefix(slicePart(frame, offset, frame.samples.length));
          return;
        }
        active = { parts: prefix, length: prefixLength, voiced: 0, silent: 0 };
        prefix = [];
        prefixLength = 0;
      }
      const count = Math.min(frame.samples.length - offset, maximumSize - active.length);
      const part = slicePart(frame, offset, offset + count);
      active.parts.push(part);
      active.length += count;
      active.voiced += voiced ? count : 0;
      active.silent = voiced ? 0 : active.silent + count;
      offset += count;
      if (active.length >= maximumSize) {
        const continuation = voiced && (active.continuation || active.voiced >= speechSize);
        finish(output);
        // A maximum-length split can land inside a word. Its short remainder
        // is already confirmed speech, so retain it through silence closure.
        if (continuation) active = { parts: [], length: 0, voiced: 0, silent: 0, continuation: true };
      } else if (active.silent >= silenceSize && active.length >= minimumSize) {
        finish(output);
      }
    }
  }

  function drainFrame(output) {
    if (!pendingSize) return;
    acceptFrame({ samples: pending.slice(0, pendingSize), start: pendingStart, end: pendingEnd }, output);
    pendingSize = 0;
  }

  return {
    push(samples, { mediaStart, mediaEnd } = {}) {
      if (!samples.length) return [];
      if (!Number.isFinite(mediaStart) || !Number.isFinite(mediaEnd) || mediaEnd <= mediaStart) {
        throw new RangeError('A positive media time interval is required');
      }
      if (previousEnd !== null && Math.abs(mediaStart - previousEnd) > config.discontinuityTolerance) reset();
      previousEnd = mediaEnd;
      const output = [];
      let offset = 0;
      const timeAt = (index) => mediaStart + (mediaEnd - mediaStart) * index / samples.length;
      while (offset < samples.length) {
        if (!pendingSize) pendingStart = timeAt(offset);
        const count = Math.min(frameSize - pendingSize, samples.length - offset);
        pending.set(samples.subarray(offset, offset + count), pendingSize);
        pendingSize += count;
        offset += count;
        pendingEnd = timeAt(offset);
        if (pendingSize === frameSize) drainFrame(output);
      }
      return output;
    },
    flush() {
      const output = [];
      drainFrame(output);
      finish(output, true);
      reset();
      return output;
    },
    reset,
  };
}
