import { resampleMono } from './lib/audio.js';
import { createLiveCaptions } from './lib/live-captions.js';
import { connectGeminiLive } from './lib/gemini-live.js';

let active = null;
function emit(run, type, extra = {}) {
  return chrome.runtime.sendMessage({ type, sessionId: run.id, revision: run.revision, ...extra }).catch(() => {});
}
function current(run) { return active === run && !run.stopped; }
function owns(run, connection) { return current(run) && run.connection === connection && connection.revision === run.revision; }
function mediaTime(run) {
  return run.clock.time + (run.clock.paused ? 0 : Math.max(0, Date.now() - run.clock.wallTime) / 1000 * run.clock.playbackRate);
}
function disconnect(run) {
  const connection = run.connection;
  run.connection = null;
  if (!connection) return;
  clearTimeout(connection.flushTimer); clearTimeout(connection.paddingTimer); clearTimeout(connection.endTimer);
  connection.abort.abort();
  connection.transport?.close();
}
async function release(run) {
  if (!run || run.stopped) return;
  run.stopped = true;
  run.cancelStartup?.(new Error('收音已取消。'));
  clearInterval(run.heartbeat); clearTimeout(run.sessionTimer);
  disconnect(run);
  run.worklet?.port.postMessage({ type: 'stop' });
  run.worklet?.disconnect(); run.source?.disconnect();
  run.stream?.getTracks().forEach(track => track.stop());
  await run.context?.close().catch(() => {});
  if (active === run) active = null;
}
function fatal(run, message) {
  if (!current(run) || run.failing) return;
  run.failing = true;
  void emit(run, 'CAPTURE_ERROR', { message });
  void release(run);
}
function publish(run, connection, cues) {
  if (!owns(run, connection)) return;
  for (const cue of cues) void emit(run, 'CAPTURE_CUE', { revision: connection.revision, cue });
}
function completed(run, connection) {
  if (!owns(run, connection)) return;
  publish(run, connection, connection.captions.finish(mediaTime(run)));
  disconnect(run);
  if (run.finishing) { void emit(run, 'CAPTURE_FINISHED'); void release(run); }
}
async function connect(run) {
  disconnect(run);
  const connection = { epoch: ++run.epoch, revision: run.revision, ready: false, ending: false,
    abort: new AbortController(), pending: new Float32Array(0), pcm: new Float32Array(0) };
  run.connection = connection;
  run.worklet?.port.postMessage({ type: 'epoch', epoch: connection.epoch });
  connection.captions = createLiveCaptions({ prefix: `${run.id}_${run.revision}_${connection.epoch}`, nextSequence: () => ++run.sequence });
  const transport = await connectGeminiLive({
    apiKey: run.config.geminiApiKey, targetLanguage: run.config.targetLanguage, signal: connection.abort.signal,
    onTranscript(data) {
      if (!owns(run, connection)) return;
      publish(run, connection, connection.captions.push(data, mediaTime(run)));
      if (connection.endSent && data.turnComplete) completed(run, connection);
    },
    onError(error) { if (owns(run, connection) && connection.ready) fatal(run, error.message); },
    onClose(error) {
      if (!owns(run, connection)) return;
      if (connection.endSent && error.closeCode === 1000) completed(run, connection);
      else if (connection.ready) fatal(run, error.message);
    },
  });
  if (!owns(run, connection)) { transport.close(); throw new Error('字幕串流已取消。'); }
  connection.transport = transport;
  connection.ready = true;
  if (run.finishing) end(run);
}
function sendFrame(run, connection, samples) {
  if (!owns(run, connection) || !connection.ready) return;
  const buffer = new ArrayBuffer(3200), view = new DataView(buffer);
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, Number.isFinite(samples[i]) ? samples[i] : 0));
    view.setInt16(i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
  }
  try { connection.transport.sendAudio(buffer); }
  catch (error) { fatal(run, error.message || 'Gemini Live 音訊傳送失敗，請重新開始。'); }
}
function processAudio(run, connection, samples, flush = false) {
  const joined = new Float32Array(connection.pending.length + samples.length);
  joined.set(connection.pending); joined.set(samples, connection.pending.length);
  // Whole 10 ms input blocks preserve the resampling ratio across worklet callbacks.
  const quantum = Math.round(run.context.sampleRate / 100);
  const count = flush ? joined.length : Math.floor(joined.length / quantum) * quantum;
  connection.pending = joined.slice(count);
  const downsampled = resampleMono(joined.subarray(0, count), run.context.sampleRate);
  const pcm = new Float32Array(connection.pcm.length + downsampled.length);
  pcm.set(connection.pcm); pcm.set(downsampled, connection.pcm.length);
  let offset = 0;
  while (offset + 1600 <= pcm.length && owns(run, connection)) { sendFrame(run, connection, pcm.subarray(offset, offset + 1600)); offset += 1600; }
  connection.pcm = pcm.slice(offset);
  if (flush && connection.pcm.length) { sendFrame(run, connection, connection.pcm); connection.pcm = new Float32Array(0); }
}
function sendEnd(run, connection) {
  if (!owns(run, connection)) return;
  try { connection.endSent = true; connection.transport.endAudio(); }
  catch { fatal(run, 'Gemini Live 連線中斷，請重新開始字幕。'); return; }
  connection.endTimer = setTimeout(() => completed(run, connection), 8000);
}
function finishFlush(run, connection) {
  if (!owns(run, connection) || !connection.flushId || connection.ending) return;
  clearTimeout(connection.flushTimer);
  connection.flushId = null;
  if (!connection.hasAudio && !run.finishing) return;
  processAudio(run, connection, new Float32Array(0), true);
  if (!owns(run, connection)) return;
  connection.ending = true;
  if (!connection.hasAudio) { sendEnd(run, connection); return; }
  // Live Translate needs time on the audio clock to emit the last spoken words.
  // Pace tail silence on the same real-time audio clock as normal capture.
  let frames = 0;
  const silence = new Float32Array(1600);
  const pad = () => {
    if (!owns(run, connection)) return;
    sendFrame(run, connection, silence);
    if (!owns(run, connection)) return;
    if (++frames === 30) sendEnd(run, connection);
    else connection.paddingTimer = setTimeout(pad, 100);
  };
  connection.paddingTimer = setTimeout(pad, 100);
}

function end(run) {
  const connection = run.connection;
  if (!connection) { if (run.finishing) { void emit(run, 'CAPTURE_FINISHED'); void release(run); } return; }
  if (!connection.ready || connection.ending || connection.flushId) return;
  connection.flushId = `${connection.epoch}:tail`;
  connection.flushTimer = setTimeout(() => finishFlush(run, connection), 250);
  if (run.worklet) run.worklet.port.postMessage({ type: 'flush', id: connection.flushId, epoch: connection.epoch });
  else finishFlush(run, connection);
}
function receiveAudio(run, data) {
  const connection = run.connection;
  if (!connection || !owns(run, connection) || !connection.ready || connection.ending || data.epoch !== connection.epoch) return;
  const isTail = data.flushId && data.flushId === connection.flushId;
  if (data.flushId && !isTail) return;
  if (!isTail && (run.finishing || run.clock.paused || run.clock.adPlaying)) return;
  if (!(data.samples instanceof Float32Array) || data.samples.length > 48000) return;
  if (data.samples.length) connection.hasAudio = true;
  processAudio(run, connection, data.samples);
}
async function setupAudio(run, message) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: message.streamId } }, video: false });
  if (!current(run)) { stream.getTracks().forEach(track => track.stop()); throw new Error('收音已取消。'); }
  run.stream = stream;
  run.context = new AudioContext();
  run.source = run.context.createMediaStreamSource(stream);
  // Exactly one audible route restores the sound suppressed by tab capture.
  run.source.connect(run.context.destination);
  await run.context.audioWorklet.addModule(chrome.runtime.getURL('audio-worklet.js'));
  if (!current(run)) throw new Error('收音已取消。');
  run.worklet = new AudioWorkletNode(run.context, 'winston-audio-capture');
  run.worklet.port.onmessage = ({ data }) => {
    if (data?.type === 'audio') receiveAudio(run, data);
    else if (data?.type === 'flushed' && run.connection?.flushId === data.id && run.connection.epoch === data.epoch) finishFlush(run, run.connection);
  };
  run.worklet.port.postMessage({ type: 'epoch', epoch: run.connection?.epoch ?? run.epoch });
  run.source.connect(run.worklet); run.worklet.connect(run.context.destination); // The worklet outputs silence.
  for (const track of stream.getTracks()) track.addEventListener('ended', () => fatal(run, '分頁收音已中止，請重新開始字幕。'));
  await run.context.resume();
  if (!current(run)) throw new Error('收音已取消。');
}
async function start(message) {
  await release(active);
  const run = { id: message.sessionId, revision: message.revision, config: message.config, clock: message.clock,
    sequence: 0, epoch: 0, stopped: false };
  active = run;
  let timer;
  try {
    const cancelled = new Promise((_, reject) => { run.cancelStartup = reject; });
    const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('收音與 Gemini Live 啟動逾時，請重新開始。')), 12000); });
    await Promise.race([Promise.all([setupAudio(run, message), connect(run)]), cancelled, timeout]);
    if (!current(run)) throw new Error('收音已取消。');
    run.cancelStartup = null;
    run.sessionTimer = setTimeout(() => fatal(run, '本次字幕已達 30 分鐘，請重新開始以繼續翻譯。'), 30 * 60 * 1000);
    run.heartbeat = setInterval(() => { if (current(run)) void emit(run, 'CAPTURE_HEARTBEAT'); }, 15000);
    if (run.clock.adPlaying) disconnect(run);
    return { ok: true };
  } catch (error) { await release(run); return { ok: false, error: error.message }; }
  finally { clearTimeout(timer); }
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message?.target !== 'offscreen' || sender.id !== chrome.runtime.id) return false;
  if (message.type === 'CAPTURE_START') { start(message).then(respond); return true; }
  const run = active;
  if (!run || (message.sessionId && message.sessionId !== run.id)) { respond({ ok: true, active: false }); return false; }
  if (message.type === 'CAPTURE_STOP') { release(run).then(() => respond({ ok: true })); return true; }
  if (message.type === 'CAPTURE_FINISH') { run.finishing = true; end(run); }
  else if (message.type === 'CAPTURE_CLOCK' && !run.finishing) {
    if (message.revision < run.revision) { respond({ ok: false }); return false; }
    const previous = run.clock, changed = message.revision !== run.revision;
    if (changed) { disconnect(run); run.sequence = 0; run.revision = message.revision; }
    run.clock = message.clock;
    if (run.clock.adPlaying) disconnect(run);
    else if (run.clock.paused) { if (changed) disconnect(run); else end(run); }
    else if (changed || previous.paused || previous.adPlaying) {
      const reusable = !changed && !previous.adPlaying && run.connection?.ready && !run.connection.ending && !run.connection.flushId && !run.connection.hasAudio;
      if (!reusable) void connect(run).catch(() => fatal(run, 'Gemini Live 重新連線失敗，請重新開始字幕。'));
    }
  }
  respond({ ok: true, active: true, sessionId: run.id, revision: run.revision });
  return false;
});
