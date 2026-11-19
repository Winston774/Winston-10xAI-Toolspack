import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, access, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { runMedia } from '../server/media.mjs';

const exec = promisify(execFile);
async function temp(t) {
  const base = path.resolve(os.tmpdir());
  const directory = await mkdtemp(path.join(base, 'studio-media-test-'));
  t.after(async () => {
    if (path.dirname(directory) === base && path.basename(directory).startsWith('studio-media-test-')) {
      await rm(directory, { recursive: true, force: true });
    }
  });
  return directory;
}

function wav(samples = 30000) {
  const wav = Buffer.alloc(44 + 2 * samples);
  wav.write('RIFF', 0);
  wav.writeUInt32LE(wav.length - 8, 4);
  wav.write('WAVEfmt ', 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(24000, 24);
  wav.writeUInt32LE(48000, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write('data', 36);
  wav.writeUInt32LE(2 * samples, 40);
  return wav;
}

const voiceArgs = { type: 'voice', settings: {}, input: { provider: 'fish', text: '試音。', voiceId: 'voice123' } };

test('Fish 用選取的模型和音色，回傳可播放的 WAV', async t => {
  const audio = wav();
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'https://api.fish.audio/v1/tts');
    assert.equal(options.headers.model, 's2-pro');
    assert.equal(options.headers.Authorization, 'Bearer test-only');
    assert.deepEqual(JSON.parse(options.body), { text: '試音。', reference_id: 'voice123', format: 'wav', latency: 'normal' });
    return new Response(audio, { headers: { 'Content-Type': 'audio/wav' } });
  });
  const result = await runMedia({ ...voiceArgs, settings: { fishApiKey: 'test-only' }, outputDir: await temp(t) });
  assert.deepEqual(await readFile(result.path), audio);
});

test('Breeze 串接官方 multipart 並將每段 PCM 合併為 WAV', async t => {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(String(url), 'https://studio.example/v1/audio/speech');
    assert.equal(options.headers.Authorization, 'Bearer colab-token');
    assert.equal(options.body.get('instruction'), '輕快');
    requests.push(options.body.get('text'));
    return new Response(Buffer.alloc(100), { headers: { 'Content-Type': 'audio/pcm', 'X-Sample-Rate': '32000', 'X-Sample-Format': 's16le' } });
  });
  const text = '說'.repeat(400);
  const result = await runMedia({ type: 'voice', settings: { breezeUrl: 'https://studio.example/v1/', breezeToken: 'colab-token' },
    input: { provider: 'breeze', text, voiceInstruction: '輕快' }, outputDir: await temp(t) });
  assert.equal(requests.join(''), text);
  assert.equal(requests.length, 3);
  const resultWav = await readFile(result.path);
  assert.equal(resultWav.readUInt32LE(24), 32000);
  assert.equal(resultWav.readUInt32LE(40), 300 + 2 * 32000 * 0.12 * 2);
  assert.equal(resultWav.length, 44 + resultWav.readUInt32LE(40));
});

test('Colab 預設音色只使用該閘道已配置的名稱', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push(String(url));
    if (calls.length === 1) return Response.json({ profiles: ['guide'] });
    assert.equal(options.body.get('voice_id'), 'guide');
    return new Response(Buffer.alloc(20), { headers: { 'Content-Type': 'audio/pcm' } });
  });
  await runMedia({ type: 'voice', settings: { breezeUrl: 'https://studio.example/proxy/v1/audio/speech' },
    input: { provider: 'breeze', text: '試音', voiceId: 'guide' }, outputDir: await temp(t) });
  assert.deepEqual(calls, ['https://studio.example/proxy/studio/capabilities', 'https://studio.example/proxy/v1/audio/speech']);
});

test('拒絕空白台詞、無法辨識的音檔、未啟用的影片與非加密遠端 URL', async t => {
  const outputDir = await temp(t);
  const settings = { fishApiKey: 'private-test-key' };
  t.mock.method(globalThis, 'fetch', async () => new Response('html body'));
  await assert.rejects(runMedia({ ...voiceArgs, settings, outputDir }), /WAV/);
  await assert.rejects(runMedia({ ...voiceArgs, settings, outputDir, input: { text: ' ' } }), /台詞/);
  await assert.rejects(runMedia({ ...voiceArgs, settings, outputDir, type: 'video' }), /啟用/);
  await assert.rejects(runMedia({ type: 'voice', outputDir, settings: { breezeUrl: 'http://example.org' },
    input: { provider: 'breeze', text: '測試' } }), /HTTPS/);
});

test('服務錯誤不會將供應商回音的金鑰與敏感內文送到畫面', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('my-key my-private-text', { status: 401 }));
  const outputDir = await temp(t);
  await assert.rejects(runMedia({ ...voiceArgs, settings: { fishApiKey: 'my-key' }, outputDir }),
    error => error.message.includes('401') && !error.message.includes('my-key') && !error.message.includes('my-private-text'));
});

test('影片先合成語音，沿用選取照片，驗證後封存；中斷重取不會重新提交', async t => {
  const base = await temp(t);
  const settings = { longcatEnabled: true, fishApiKey: 'test-only' };
  const scriptDir = path.join(base, 'skills', 'longcat-avatar-colab', 'scripts');
  await mkdir(scriptDir, { recursive: true });
  const oldHome = process.env.CODEX_HOME;
  process.env.CODEX_HOME = base;
  t.after(() => { if (oldHome) process.env.CODEX_HOME = oldHome; else delete process.env.CODEX_HOME; });
  // Deterministic stand-in for the external Colab CLI. No remote runtime is contacted.
  await writeFile(path.join(scriptDir, 'run_colab.py'), `import json, pathlib, sys
a=sys.argv[1:]
out=pathlib.Path(a[a.index('--out')+1])
if a[0]=='run':
    out.mkdir()
    assert pathlib.Path(a[a.index('--image')+1]).read_bytes()==b'selected-photo'
    assert pathlib.Path(a[a.index('--audio')+1]).read_bytes()[:4]==b'RIFF'
    assert a[a.index('--prompt')+1]=='面對鏡頭'
    (out/'longcat_avatar_2s.mp4').write_bytes(b'fixture-video')
    (out/'run-manifest.json').write_text(json.dumps({'video_name':'longcat_avatar_2s.mp4','status':'stopped','stop_confirmed':True,'latest_verification':'report.json'}))
elif a[0]=='collect':
    (out/'collected.txt').write_text('yes')
else:
    raise ValueError(a[0])
`);
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return new Response(wav()); });
  const photo = path.join(base, 'actor.png');
  await writeFile(photo, 'selected-photo');
  const args = { type: 'video', settings, input: { ...voiceArgs.input, performancePrompt: '面對鏡頭' },
    imagePath: photo, outputDir: path.join(base, 'job') };
  let publicAudio;
  const result = await runMedia({ ...args, onAudioReady: async file => {
    assert.deepEqual(await readFile(file), wav());
    await assert.rejects(access(path.join(args.outputDir, 'longcat')));
    publicAudio = file;
  } });
  assert.equal(result.audioPath, publicAudio);
  assert.equal(await readFile(result.path, 'utf8'), 'fixture-video');
  assert.deepEqual(await readFile(result.audioPath), wav());
  const recovered = await runMedia({ ...args, audioPath: result.audioPath });
  assert.equal(recovered.path, result.path);
  assert.equal(calls, 1);
  assert.equal(await readFile(path.join(args.outputDir, 'longcat', 'collected.txt'), 'utf8'), 'yes');
});

test('首次影片失敗仍保留可用配音，續取完整 WAV 時不會再次合成', async t => {
  const base = await temp(t);
  const oldHome = process.env.CODEX_HOME;
  process.env.CODEX_HOME = base;
  t.after(() => { if (oldHome) process.env.CODEX_HOME = oldHome; else delete process.env.CODEX_HOME; });
  const dir = path.join(base, 'skills', 'longcat-avatar-colab', 'scripts');
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, 'run_colab.py'), 'raise SystemExit(1)');
  const imagePath = path.join(base, 'source.png');
  await writeFile(imagePath, 'fixture');
  let calls = 0, publicAudio;
  t.mock.method(globalThis, 'fetch', async () => { calls++; return new Response(wav()); });
  const args = { ...voiceArgs, type: 'video', outputDir: path.join(base, 'job'),
    imagePath, settings: { longcatEnabled: true, fishApiKey: 'test-only' },
    onAudioReady: async file => { publicAudio = file; } };
  await mkdir(args.outputDir);
  // Simulate a truncated staging file left by a killed process.
  await writeFile(path.join(args.outputDir, '.voice-partial.wav'), wav().subarray(0, 50));
  await assert.rejects(runMedia(args), /LongCat/);
  assert.deepEqual(await readFile(publicAudio), wav());
  await assert.rejects(runMedia(args), /LongCat/);
  assert.equal(calls, 1);
});

test('本機現有 LongCat CLI 可離線檢查素材並產生可提交的 notebook 任務', { skip: process.env.STUDIO_TEST_LONGCAT_PREPARE !== '1' }, async t => {
  const script = path.join(process.env.CODEX_HOME || path.join(os.homedir(), '.codex'), 'skills', 'longcat-avatar-colab', 'scripts', 'run_colab.py');
  await access(script);
  const dir = await temp(t);
  const photo = path.join(dir, 'actor.png'), sound = path.join(dir, 'voice.wav'), work = path.join(dir, 'prepared');
  await exec('ffmpeg', ['-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=64x64:d=1', '-frames:v', '1', photo]);
  await writeFile(sound, wav());
  await exec('python', ['-X', 'utf8', script, 'run', '--prepare-only', '--image', photo, '--audio', sound, '--prompt', '自然說話。', '--out', work]);
  const manifest = JSON.parse(await readFile(path.join(work, 'run-manifest.json'), 'utf8'));
  assert.equal(manifest.status, 'prepared');
  assert.equal(manifest.duration, 1.25);
  assert.equal(manifest.allocation_attempts, undefined);
  assert.match(await readFile(path.join(work, 'job.py'), 'utf8'), /LONGCAT_JOB_COMPLETE/);
  t.diagnostic('素材解碼、正規化與 notebook 工作產生均通過。');
});
