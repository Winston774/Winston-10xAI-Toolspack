import { DEFAULT_TARGET_LANGUAGE, normalizeTargetLanguage } from './languages.js';

export const GEMINI_LIVE_MODEL = 'gemini-3.5-live-translate-preview';
const ENDPOINT = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent';
const MAX_PAYLOAD_BYTES = 1024 * 1024;
const MAX_BUFFERED_BYTES = 64 * 1024;
const MAX_AUDIO_BYTES = 3200;
const MESSAGES = Object.freeze({
  PROVIDER_AUTH_ERROR: 'Gemini API key 無效或未取得存取權，請檢查金鑰。',
  PROVIDER_RATE_LIMIT: 'Gemini 使用量或速率已達限制，請檢查額度後再試。',
  PROVIDER_MODEL_UNAVAILABLE: '目前的 Gemini 帳戶無法使用即時翻譯模型。',
  PROVIDER_UNAVAILABLE: 'Gemini 即時翻譯服務暫時無法使用。',
  PROVIDER_REQUEST_REJECTED: 'Gemini 拒絕即時翻譯設定，請確認金鑰及模型存取權。',
  PROVIDER_INVALID_RESPONSE: 'Gemini 回傳的即時字幕格式無效，已停止串流。',
  PROVIDER_TIMEOUT: 'Gemini 即時翻譯連線逾時，請檢查網路後再試。',
  PROVIDER_ERROR: '無法連接 Gemini，即時翻譯需要有效 API key 及網路連線。',
  PROVIDER_INVALID_INPUT: '即時音訊須為不超過 100 毫秒的 PCM16 單聲道片段。',
  PROVIDER_DISCONNECTED: 'Gemini 即時翻譯連線已中斷，請重新開始字幕。',
  PROVIDER_BACKPRESSURE: 'Gemini 音訊傳輸延遲過高，已停止收音，請檢查網路。',
  REQUEST_CANCELLED: '即時字幕連線已取消。',
});

export class GeminiLiveError extends Error {
  constructor(code) { super(MESSAGES[code]); this.name = 'GeminiLiveError'; this.code = code; }
}
function errorForStatus(status) {
  return new GeminiLiveError(status === 401 || status === 403 ? 'PROVIDER_AUTH_ERROR'
    : status === 429 ? 'PROVIDER_RATE_LIMIT' : status === 404 ? 'PROVIDER_MODEL_UNAVAILABLE'
      : status >= 500 ? 'PROVIDER_UNAVAILABLE' : 'PROVIDER_REQUEST_REJECTED');
}
function notify(callback, value) { try { callback?.(value); } catch { /* UI callbacks cannot leak upstream details. */ } }
function transcript(value) {
  const text = value?.text === undefined ? '' : value.text;
  if (!value || typeof value !== 'object' || Array.isArray(value) || typeof text !== 'string' || text.length > 16384 ||
      (value.finished !== undefined && typeof value.finished !== 'boolean')) throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
  return { text, finished: value.finished === true };
}
function payloadSize(data) {
  if (typeof data === 'string') return new TextEncoder().encode(data).byteLength;
  if (data instanceof ArrayBuffer) return data.byteLength;
  if (typeof Blob !== 'undefined' && data instanceof Blob) return data.size;
  throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
}

// The browser owns this connection. Credentials never enter a page/content script.
export async function connectGeminiLive({ apiKey, targetLanguage = DEFAULT_TARGET_LANGUAGE, onTranscript, onError, onClose, signal,
  WebSocketClass = globalThis.WebSocket, setupTimeoutMs = 10000 } = {}) {
  const key = typeof apiKey === 'string' ? apiKey.trim() : '';
  if (!key || key.length > 256 || /\s/.test(key)) throw new GeminiLiveError('PROVIDER_AUTH_ERROR');
  if (signal?.aborted) throw new GeminiLiveError('REQUEST_CANCELLED');
  const targetLanguageCode = normalizeTargetLanguage(targetLanguage);
  return new Promise((resolve, reject) => {
    let socket, ready = false, stopped = false, queuedBytes = 0, incoming = Promise.resolve();
    const timeout = setTimeout(() => fail(new GeminiLiveError('PROVIDER_TIMEOUT')), setupTimeoutMs);
    function cleanup() {
      clearTimeout(timeout);
      signal?.removeEventListener('abort', onAbort);
      if (socket) socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
    }
    function closeSocket() { try { socket?.close(); } catch { /* Closed or failed handshake. */ } }
    function fail(error) {
      if (stopped) return;
      stopped = true; cleanup();
      if (!ready) reject(error);
      notify(onError, error); closeSocket();
    }
    function sendPacket(packet) {
      if (stopped || socket?.readyState !== 1) throw new GeminiLiveError('PROVIDER_DISCONNECTED');
      const encoded = JSON.stringify(packet);
      if (socket.bufferedAmount + new TextEncoder().encode(encoded).byteLength > MAX_BUFFERED_BYTES) {
        const error = new GeminiLiveError('PROVIDER_BACKPRESSURE'); fail(error); throw error;
      }
      try { socket.send(encoded); }
      catch { const error = new GeminiLiveError('PROVIDER_ERROR'); fail(error); throw error; }
    }
    const session = {
      get bufferedAmount() { return stopped ? 0 : socket.bufferedAmount; },
      sendAudio(audio) {
        if (!ready) throw new GeminiLiveError('PROVIDER_DISCONNECTED');
        const bytes = audio instanceof ArrayBuffer ? new Uint8Array(audio) : audio;
        if (!(bytes instanceof Uint8Array) || !bytes.byteLength || bytes.byteLength % 2 || bytes.byteLength > MAX_AUDIO_BYTES) throw new GeminiLiveError('PROVIDER_INVALID_INPUT');
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        sendPacket({ realtimeInput: { audio: { data: btoa(binary), mimeType: 'audio/pcm;rate=16000' } } });
      },
      endAudio() { sendPacket({ realtimeInput: { audioStreamEnd: true } }); },
      close() {
        if (stopped) return;
        stopped = true; cleanup(); closeSocket();
      },
    };
    function onAbort() { fail(new GeminiLiveError('REQUEST_CANCELLED')); }
    function consume(raw) {
      if (stopped) return;
      const message = JSON.parse(raw);
      if (!message || typeof message !== 'object' || Array.isArray(message)) throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
      if (message.error) { fail(errorForStatus(Number(message.error.code))); return; }
      if (Object.hasOwn(message, 'setupComplete')) {
        if (ready || !message.setupComplete || typeof message.setupComplete !== 'object' || Array.isArray(message.setupComplete)) throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
        ready = true; clearTimeout(timeout); resolve(session);
      }
      if (message.serverContent) {
        if (!ready || typeof message.serverContent !== 'object' || Array.isArray(message.serverContent)) throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
        const content = message.serverContent, event = { type: 'transcript' };
        if (Object.hasOwn(content, 'inputTranscription')) event.input = transcript(content.inputTranscription);
        if (Object.hasOwn(content, 'outputTranscription')) event.output = transcript(content.outputTranscription);
        if (content.turnComplete === true) event.turnComplete = true;
        if (Object.keys(event).length > 1) notify(onTranscript, event);
        // modelTurn audio is intentionally discarded; this product displays subtitles.
      }
    }
    try {
      const url = new URL(ENDPOINT); url.searchParams.set('key', key);
      socket = new WebSocketClass(url.href);
      socket.binaryType = 'arraybuffer';
      socket.onopen = () => {
        if (stopped) return;
        try {
          sendPacket({ setup: {
            model: `models/${GEMINI_LIVE_MODEL}`,
            inputAudioTranscription: {}, outputAudioTranscription: {},
            generationConfig: { responseModalities: ['AUDIO'], translationConfig: { targetLanguageCode, echoTargetLanguage: false } },
          } });
        } catch (error) { fail(error instanceof GeminiLiveError ? error : new GeminiLiveError('PROVIDER_ERROR')); }
      };
      socket.onmessage = ({ data }) => {
        if (stopped) return;
        let size;
        try {
          size = payloadSize(data);
          if (size > MAX_PAYLOAD_BYTES || queuedBytes + size > 2 * MAX_PAYLOAD_BYTES) throw new GeminiLiveError('PROVIDER_INVALID_RESPONSE');
        } catch { fail(new GeminiLiveError('PROVIDER_INVALID_RESPONSE')); return; }
        queuedBytes += size;
        // Blob decoding is asynchronous; serialize all frames to retain wire order.
        incoming = incoming.then(async () => {
          if (stopped) return;
          const raw = typeof data === 'string' ? data : data instanceof ArrayBuffer ? new TextDecoder('utf-8', { fatal: true }).decode(data) : await data.text();
          consume(raw);
        }).catch(error => fail(error instanceof GeminiLiveError ? error : new GeminiLiveError('PROVIDER_INVALID_RESPONSE')))
          .finally(() => { queuedBytes -= size; });
      };
      socket.onerror = () => fail(new GeminiLiveError('PROVIDER_ERROR'));
      socket.onclose = ({ code } = {}) => {
        if (stopped) return;
        stopped = true; cleanup();
        const error = new GeminiLiveError(!ready && [1007, 1008].includes(code) ? 'PROVIDER_REQUEST_REJECTED' : !ready && code === 1011 ? 'PROVIDER_UNAVAILABLE' : 'PROVIDER_DISCONNECTED');
        error.closeCode = code;
        if (!ready) reject(error);
        notify(onClose, error);
      };
      signal?.addEventListener('abort', onAbort, { once: true });
    } catch { fail(new GeminiLiveError('PROVIDER_ERROR')); }
  });
}

export async function checkGeminiConnection(apiKey, options = {}) {
  const session = await connectGeminiLive({ ...options, apiKey });
  session.close();
  return { configured: true, provider: 'gemini', mode: 'live', model: GEMINI_LIVE_MODEL };
}
