import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { constants, createReadStream } from 'node:fs';
import { copyFile, link, mkdir, mkdtemp, readFile, rename, rm, rmdir, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { breezeSpeech, fishSpeech, validWav } from './media/speech.mjs';

function skillScript(skill, file) {
  const home = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
  return path.join(home, 'skills', skill, 'scripts', file);
}

function command(executable, args, signal) {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted();
    const child = spawn(executable, args, { signal, shell: false, windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1' } });
    let stdout = '', stderr = '';
    child.stdout.setEncoding('utf8').on('data', data => { stdout = (stdout + data).slice(-32768); });
    child.stderr.setEncoding('utf8').on('data', data => { stderr = (stderr + data).slice(-32768); });
    child.on('error', error => {
      if (error.code === 'ENOENT') reject(new Error(`找不到執行程式 ${path.basename(executable)}。`));
      else reject(error);
    });
    child.on('close', code => resolve({ code, stdout, stderr }));
  });
}

async function requireFile(file, message) {
  try {
    const info = await stat(file);
    if (info.isFile() && info.size > 0) return;
  } catch { /* present the relevant setup or artifact error */ }
  throw new Error(message);
}

function checkedBreezeResult(run, schema) {
  let result;
  try { result = JSON.parse(run.stdout); } catch { /* native tools sometimes emit non-JSON diagnostics */ }
  if (run.code === 0 && result?.schema === schema && result?.ok === true) return result;
  const errors = { gpu_busy: '可用顯示記憶體不足，請先釋出至少 8 GiB。', runtime_busy: '本機 Breeze 正在合成其他台詞。',
    resource_missing: '缺少模型或指定的音色檔案。', runtime_unavailable: '請檢查 WSL、Breeze 專案位置與已安裝的模型。',
    artifact_invalid: '本機 Breeze 回傳的音檔未通過驗證。' };
  throw new Error('本機 Breeze 執行失敗。' + (errors[result?.error?.code] || '請在本機執行 Breeze doctor 檢查執行環境。'));
}

function mountedWindowsPath(file) {
  const drive = /^\/mnt\/([a-z])\/(.*)$/iu.exec(file);
  return drive ? path.win32.normalize(drive[1] + ':\\' + drive[2]) : path.win32.normalize(file);
}

async function localBreeze({ input, target, signal, onProgress }) {
  if (process.platform !== 'win32') throw new Error('本機 Breeze 需要 Windows 與 WSL。也可以在連線設定填入 Breeze 服務網址。');
  const wrapper = skillScript('breeze-tts-agent-cli', 'invoke-breeze-tts.ps1');
  await requireFile(wrapper, '找不到本機 Breeze 技能。請安裝 breeze-tts-agent-cli 或填入 Colab 服務網址。');
  if (input.voiceId && !/^[\p{L}\p{N}][\p{L}\p{N}_ -]{0,63}$/u.test(input.voiceId)) {
    throw new Error('本機 Breeze 音色名稱限文字、數字、空白、底線與連字號。');
  }
  const args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', wrapper];
  onProgress('正在檢查本機 Breeze 模型與 GPU');
  const doctor = checkedBreezeResult(await command('powershell.exe', [...args, 'doctor'], signal), 'breeze-tts.doctor.v1');
  const temp = await mkdtemp(path.join(os.tmpdir(), 'studio-breeze-'));
  try {
    const textFile = path.join(temp, 'speech.txt');
    await writeFile(textFile, input.text, 'utf8');
    const instruction = input.voiceInstruction || '自然清晰的台灣華語，語速適中。';
    let synthArgs;
    if (input.voiceId) {
      synthArgs = [...args, 'synth', '-TextFile', textFile, '-Output', target, '-Instruction', instruction,
        '-VoiceProfile', input.voiceId];
    } else {
      // The skill wrapper always clones its default profile. Call the same checkout's
      // voice-design CLI for an original synthetic voice when no identity was selected.
      const designCli = path.join(mountedWindowsPath(doctor.project_root), 'scripts', 'breeze-tts.ps1');
      await requireFile(designCli, 'Breeze 本機專案缺少聲音設計指令。');
      synthArgs = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', designCli,
        'synth', '--text-file', textFile, '--output', target, '--instruction', instruction, '--cfg-scale', '4'];
    }
    onProgress('正在本機合成配音');
    const done = checkedBreezeResult(await command('powershell.exe', synthArgs, signal), 'breeze-tts.synth.v1');
    if (mountedWindowsPath(done.output || '').toLowerCase() !== target.toLowerCase()) throw new Error('Breeze 輸出位置與本次任務不符。');
    await requireFile(target, 'Breeze 配音檔未完成。');
  } finally {
    await rm(path.join(temp, 'speech.txt'), { force: true });
    await rmdir(temp);
  }
}

async function completedWav(file) {
  try { return validWav(await readFile(file)); }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}

async function synthesize({ settings, input, outputDir, signal, onProgress }) {
  const text = String(input.text || '').trim();
  if (!text || text.length > 5000) throw new Error('請輸入 1 到 5,000 字的台詞。');
  const finished = path.join(outputDir, 'voice.wav');
  if (await completedWav(finished)) return finished;
  const target = path.join(outputDir, '.voice-partial.wav');
  if (await completedWav(target)) {
    await rename(target, finished);
    return finished;
  }
  await rm(target, { force: true });
  const args = { settings, input: { ...input, text }, target, signal, onProgress };
  if (input.provider === 'fish') {
    onProgress('Fish Audio 正在合成配音');
    await fishSpeech(args);
  } else if (input.provider === 'breeze') {
    if (settings.breezeUrl) await breezeSpeech(args);
    else await localBreeze(args);
  } else {
    throw new Error('請選擇 Fish Audio 或 BreezeTTS。');
  }
  if (!await completedWav(target)) throw new Error('配音檔的 WAV 資料不完整。');
  await rename(target, finished);
  return finished;
}

const longcatStages = {
  prepared: '已完成素材檢查', allocating: '正在配置 Colab A100', session_ready: 'Colab A100 已就緒',
  executing: 'LongCat 正在生成影片', submitted: 'LongCat 正在生成影片', collection_pending: '正在等候下載',
  verified: '影片驗證完成', verified_stop_pending: '正在確認 Colab 停機', stopped: '成片已驗證並取回'
};

async function loadManifest(directory) {
  try { return JSON.parse(await readFile(path.join(directory, 'run-manifest.json'), 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}

function longcatFailure(run, manifest) {
  const diagnostic = run.stderr + '\n' + run.stdout;
  if (manifest && !manifest.stop_confirmed && manifest.status !== 'prepared') {
    const name = /^longcat-[\w-]{8,50}$/.test(manifest.session || '') ? '（' + manifest.session + '）' : '';
    return 'Colab 執行階段' + name + '可能仍在計費。可重試以續取同一份結果，或依 docs/media.md 確認並停止該階段。';
  }
  if (diagnostic.includes('配音長') || diagnostic.includes('duration 必須')) return '完整配音須介於 1 到 60 秒，請縮短或延長台詞。';
  if (diagnostic.includes('ffprobe') || diagnostic.includes('ffmpeg')) return '請確認 FFmpeg、FFprobe 已安裝，且來源素材可完整解碼。';
  return '請檢查 Colab CLI 登入狀態、GPU 額度與本機工作目錄。';
}

async function digest(file) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}

async function renderVideo({ script, input, imagePath, audioPath, outputDir, signal, onProgress }) {
  const work = path.join(outputDir, 'longcat');
  const prompt = String(input.performancePrompt || '').trim() ||
    '單人自然說話，目光穩定，動作細微，保持原圖中的人物外觀、衣著、光線與背景，固定鏡頭。';
  if (prompt.length > 3000) throw new Error('演出描述請縮短至 3,000 字以內。');
  const existing = await loadManifest(work);
  // A previous submission may already own a billable VM. Collect only from that job.
  let args;
  if (existing && existing.status !== 'prepared') args = ['collect', '--out', work];
  else args = ['run', '--out', work, '--image', imagePath, '--audio', audioPath, '--prompt', prompt];
  let lastStatus;
  const monitor = setInterval(async () => {
    try {
      const state = await loadManifest(work);
      if (state && state.status !== lastStatus) {
        lastStatus = state.status;
        onProgress(longcatStages[lastStatus] || 'LongCat 正在處理影片');
      }
    } catch { /* the CLI performs atomic writes and may be changing stage */ }
  }, 2500);
  monitor.unref();
  let run;
  try { run = await command(process.env.STUDIO_PYTHON || 'python', ['-X', 'utf8', script, ...args], signal); }
  finally { clearInterval(monitor); }
  const manifest = await loadManifest(work);
  if (run.code !== 0 || manifest?.status !== 'stopped' || manifest.stop_confirmed !== true ||
      !manifest.latest_verification || !/^longcat_avatar_[0-9]+(?:\.[0-9]+)?s\.mp4$/.test(manifest.video_name || '')) {
    throw new Error('LongCat 作業尚未完成。' + longcatFailure(run, manifest));
  }
  const source = path.join(work, manifest.video_name);
  await requireFile(source, 'LongCat 驗證紀錄存在，缺少對應的 MP4。');
  const target = path.join(outputDir, 'portrait.mp4');
  // Keep the manifest's original artifact available for later inspection with no duplicate disk use.
  try { await link(source, target); } catch (error) {
    if (error.code !== 'EEXIST') {
      await copyFile(source, target, constants.COPYFILE_EXCL);
    } else {
      const [original, previous] = await Promise.all([digest(source), digest(target)]);
      if (original !== previous) throw new Error('工作目錄中的成片與 LongCat 驗證結果不同。');
    }
  }
  return target;
}

export async function runMedia({ type, settings, input, imagePath, audioPath, outputDir, signal, onProgress = () => {}, onAudioReady }) {
  signal?.throwIfAborted();
  outputDir = path.resolve(outputDir);
  await mkdir(outputDir, { recursive: true });
  if (type === 'voice') return { path: await synthesize({ settings, input, outputDir, signal, onProgress }) };
  if (type !== 'video') throw new Error('不支援的媒體任務。');
  if (settings.longcatEnabled !== true) throw new Error('請先在連線設定啟用 LongCat Colab A100。');
  if (!imagePath) throw new Error('請先選擇人物照片。');
  await requireFile(imagePath, '找不到指定的人物照片。');
  const script = skillScript('longcat-avatar-colab', 'run_colab.py');
  await requireFile(script, '找不到 LongCat 技能，請安裝 longcat-avatar-colab。');
  let synthesized;
  if (audioPath) await requireFile(audioPath, '找不到指定的配音。');
  else {
    synthesized = await synthesize({ settings, input, outputDir, signal, onProgress });
    await onAudioReady?.(synthesized);
    audioPath = synthesized;
  }
  onProgress('正在檢查照片與配音，準備 LongCat 作業');
  const result = await renderVideo({ script, input, imagePath, audioPath, outputDir, signal, onProgress });
  return synthesized ? { path: result, audioPath: synthesized } : { path: result };
}
