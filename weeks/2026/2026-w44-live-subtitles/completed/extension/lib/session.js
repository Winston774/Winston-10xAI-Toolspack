import { DEFAULT_TARGET_LANGUAGE, normalizeTargetLanguage } from './languages.js';

export const DEFAULT_CONFIG = Object.freeze({
  geminiApiKey: '', language: 'auto', targetLanguage: DEFAULT_TARGET_LANGUAGE, fontSize: 24, position: 'bottom'
});
export function normalizeConfig(input = {}) {
  const config = { ...DEFAULT_CONFIG, ...input };
  const geminiApiKey = String(config.geminiApiKey || '').trim();
  // Provider-issued credentials may contain punctuation; Google validates them.
  if (geminiApiKey && !/^[\x21-\x7E]{1,256}$/.test(geminiApiKey)) throw new Error('Gemini API key 格式不正確，請檢查是否完整貼上。');
  return {
    geminiApiKey,
    language: 'auto',
    targetLanguage: normalizeTargetLanguage(config.targetLanguage),
    fontSize: Math.max(16,Math.min(40,Math.round(Number(config.fontSize) || 24))),
    position: config.position === 'top' ? 'top' : 'bottom'
  };
}
export function newSession({tabId,mediaKey,captureMode='youtube',config,id=crypto.randomUUID()}) {
  return {id,tabId,mediaKey,captureMode,targetLanguage:config?.targetLanguage || 'zh-Hant',revision:0,state:'starting',message:'正在啟動字幕…',segments:0,lastCueSequence:-1,startedAt:Date.now()};
}
export function acceptsResult(session,envelope) {
  return !!session && !['stopped','error'].includes(session.state) && envelope.sessionId === session.id && envelope.revision === session.revision;
}
export function advanceRevision(session) {
  return {...session,revision:session.revision+1,segments:0,lastCueSequence:-1};
}
export function youtubeVideoId(raw) {
  try {
    const u = new URL(raw);
    const id = u.searchParams.get('v');
    return u.protocol==='https:' && ['www.youtube.com','youtube.com','m.youtube.com'].includes(u.hostname) && u.pathname==='/watch' && /^[a-zA-Z0-9_-]{11}$/.test(id || '') ? id : null;
  } catch { return null; }
}

// Ordinary anchors keep the session; hash-router paths can identify a new room.
export function tabMediaKey(raw) {
  try {
    const url = new URL(raw);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    const route = /^#!?\//.test(url.hash) ? url.hash : '';
    return youtubeVideoId(raw) || `tab:${url.origin}${url.pathname}${url.search}${route}`;
  } catch { return null; }
}

export function recordCue(session, cue) {
  if (!Number.isSafeInteger(cue?.sequence) || cue.sequence < 0) return false;
  if (cue.sequence > (session.lastCueSequence ?? -1)) {
    session.segments++;
    session.lastCueSequence = cue.sequence;
  }
  return true;
}
