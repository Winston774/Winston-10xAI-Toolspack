import { writeFile } from 'node:fs/promises';

const MAX_AUDIO_BYTES = 96 * 1024 * 1024;
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

function speechEndpoint(raw) {
  let url;
  try { url = new URL(raw); } catch { throw new Error('Breeze 服務網址格式錯誤。'); }
  if (url.username || url.password || url.hash || url.search ||
      !(url.protocol === 'https:' || (url.protocol === 'http:' && LOCAL_HOSTS.has(url.hostname)))) {
    throw new Error('請使用 HTTPS Breeze 服務網址，本機服務可用 http://127.0.0.1。');
  }
  const base = url.pathname.replace(/\/+$/, '').replace(/\/v1\/audio\/speech$/, '').replace(/\/v1$/, '');
  url.pathname = base + '/v1/audio/speech';
  return url;
}

async function request(url, options, label) {
  let response;
  try {
    response = await fetch(url, { ...options, redirect: 'error' });
  } catch (error) {
    options.signal?.throwIfAborted();
    throw new Error(`${label} 無法連線，請檢查網址、服務狀態與網路。`, { cause: error });
  }
  if (!response.ok) {
    await response.body?.cancel();
    const hint = { 401: '請檢查金鑰或存取權杖', 402: '請檢查帳號額度', 403: '請檢查存取權限',
      404: '請核對服務網址與音色', 409: '已有其他推論執行中，稍後可再試', 429: '服務流量或額度已達限制' };
    throw new Error(`${label} 回覆 HTTP ${response.status}。${hint[response.status] || '請檢查服務的請求設定與日誌'}。`);
  }
  return response;
}

async function bytes(response, limit = MAX_AUDIO_BYTES) {
  const chunks = [];
  let length = 0;
  if (!response.body) throw new Error('語音服務回傳空白內容。');
  for await (const chunk of response.body) {
    length += chunk.byteLength;
    if (length > limit) throw new Error('配音資料超出單筆容量，請分段送出。');
    chunks.push(chunk);
  }
  if (!length) throw new Error('語音服務回傳空白內容。');
  return Buffer.concat(chunks, length);
}

export function validWav(buffer, repairStreamHeader = false) {
  if (buffer.length < 44 || buffer.toString('ascii', 0, 4) !== 'RIFF' ||
      buffer.toString('ascii', 8, 12) !== 'WAVE') return false;
  let format = false;
  for (let pos = 12; pos + 8 <= buffer.length;) {
    const name = buffer.toString('ascii', pos, pos + 4);
    const size = buffer.readUInt32LE(pos + 4);
    const start = pos + 8;
    if (name === 'fmt ' && size >= 16 && start + size <= buffer.length) {
      format = buffer.readUInt16LE(start) > 0 && buffer.readUInt16LE(start + 2) > 0 &&
        buffer.readUInt32LE(start + 4) > 0 && buffer.readUInt16LE(start + 12) > 0;
    }
    if (name === 'data') {
      if (!format || !size || start >= buffer.length) return false;
      if (size === 0xffffffff && repairStreamHeader) {
        buffer.writeUInt32LE(buffer.length - start, pos + 4);
        buffer.writeUInt32LE(buffer.length - 8, 4);
        return true;
      }
      return size <= buffer.length - start;
    }
    pos = start + size + (size % 2);
  }
  return false;
}

function pcmWav(samples, sampleRate) {
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + samples.length, 4);
  header.write('WAVEfmt ', 8);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36);
  header.writeUInt32LE(samples.length, 40);
  return Buffer.concat([header, samples]);
}

export async function fishSpeech({ settings, input, target, signal }) {
  const key = settings.fishApiKey || process.env.FISH_API_KEY;
  if (!key) throw new Error('請先在連線設定填入 Fish Audio API 金鑰。');
  const payload = { text: input.text, format: 'wav', latency: 'normal' };
  if (input.voiceId) payload.reference_id = input.voiceId;
  const response = await request('https://api.fish.audio/v1/tts', {
    method: 'POST', headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json',
      model: settings.fishModel || 's2-pro' }, body: JSON.stringify(payload), signal
  }, 'Fish Audio');
  const audio = await bytes(response);
  if (!validWav(audio, true)) throw new Error('Fish Audio 回傳的音檔無法辨識為 WAV。');
  await writeFile(target, audio, { flag: 'wx' });
}

// Keep each call within Breeze's single-utterance generation budget.
function utterances(text) {
  const items = [];
  let current = '';
  for (const point of text) {
    current += point;
    if (current.length >= 180 || (current.length >= 90 && /[。！？.!?，,、\s]/u.test(point))) {
      if (current.trim()) items.push(current.trim());
      current = '';
    }
  }
  if (current.trim()) items.push(current.trim());
  return items;
}

export async function breezeSpeech({ settings, input, target, signal, onProgress }) {
  const url = speechEndpoint(settings.breezeUrl);
  const headers = {};
  if (settings.breezeToken) headers.Authorization = 'Bearer ' + settings.breezeToken;
  if (input.voiceId) {
    const capabilities = new URL(url);
    capabilities.pathname = capabilities.pathname.replace(/\/v1\/audio\/speech$/, '/studio/capabilities');
    const response = await request(capabilities, { headers, signal }, 'Breeze 音色閘道');
    const result = JSON.parse((await bytes(response, 64 * 1024)).toString());
    if (!Array.isArray(result.profiles) || !result.profiles.includes(input.voiceId)) {
      throw new Error('Colab 閘道找不到指定的音色。使用原生 Breeze 服務時請清空音色 ID，改填聲音描述。');
    }
  }
  const chunks = utterances(input.text);
  const audio = [];
  let sampleRate, length = 0;
  for (const [index, chunk] of chunks.entries()) {
    onProgress(`Breeze 正在合成第 ${index + 1}／${chunks.length} 段`);
    const form = new FormData();
    form.set('text', chunk);
    form.set('instruction', input.voiceInstruction || '自然清晰的台灣華語，語速適中。');
    form.set('cfg_scale', '4');
    form.set('seed', '42');
    if (input.voiceId) form.set('voice_id', input.voiceId);
    const response = await request(url, { method: 'POST', headers, body: form, signal }, 'Breeze');
    const type = response.headers.get('content-type')?.split(';')[0];
    const rate = Number(response.headers.get('x-sample-rate') || 24000);
    const format = response.headers.get('x-sample-format') || 's16le';
    if (type !== 'audio/pcm' || format.toLowerCase() !== 's16le' || !Number.isInteger(rate) ||
        rate < 8000 || rate > 192000 || (sampleRate && sampleRate !== rate)) {
      await response.body?.cancel();
      throw new Error('請確認該網址提供 Breeze 原生 /v1/audio/speech 的單聲道 PCM 服務。');
    }
    sampleRate = rate;
    if (index) {
      const pause = Buffer.alloc(2 * Math.round(rate * 0.12));
      audio.push(pause);
      length += pause.length;
    }
    const pcm = await bytes(response, MAX_AUDIO_BYTES - length);
    if (pcm.length % 2) throw new Error('Breeze 回傳的 PCM 資料不完整。');
    audio.push(pcm);
    length += pcm.length;
  }
  await writeFile(target, pcmWav(Buffer.concat(audio, length), sampleRate), { flag: 'wx' });
}
