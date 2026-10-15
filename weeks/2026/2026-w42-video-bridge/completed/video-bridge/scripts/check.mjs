import { readFile, readdir, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const extension = await realpath(path.join(root, 'extension'));
const manifest = JSON.parse(await readFile(path.join(extension, 'manifest.json'), 'utf8'));
const failures = [];
const references = new Set();

function add(value) {
  if (typeof value === 'string') references.add(value);
  else if (value && typeof value === 'object') Object.values(value).forEach(add);
}

if (manifest.manifest_version !== 3) failures.push('manifest_version 必須為 3。');
if (!manifest.name || !manifest.version) failures.push('manifest 缺少名稱或版本。');
add(manifest.background?.service_worker);
add(manifest.background?.scripts);
add(manifest.action?.default_popup);
add(manifest.action?.default_icon);
add(manifest.icons);
add(manifest.options_page);
add(manifest.options_ui?.page);
add(manifest.side_panel?.default_path);
add(manifest.devtools_page);
add(manifest.chrome_url_overrides);
for (const script of manifest.content_scripts || []) { add(script.js); add(script.css); }
for (const entry of manifest.web_accessible_resources || []) add(entry.resources);

async function verifyReference(reference, base = extension) {
  if (/^[a-z]+:/i.test(reference) || path.isAbsolute(reference)) throw new Error(`外掛資源必須使用相對路徑：${reference}`);
  if (reference.includes('*')) throw new Error(`目前檢查器需要明確資源路徑，不接受萬用字元：${reference}`);
  const resource = await realpath(path.resolve(base, reference.split(/[?#]/, 1)[0]));
  const relative = path.relative(extension, resource);
  if (relative.startsWith('..') || path.isAbsolute(relative)) throw new Error(`資源超出 extension 資料夾：${reference}`);
  if (!(await stat(resource)).isFile()) throw new Error(`資源不是一般檔案：${reference}`);
}

for (const reference of references) {
  try { await verifyReference(reference); }
  catch (error) { failures.push(`${reference}: ${error.message}`); }
}

async function allFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await allFiles(full));
    else if (entry.isFile()) files.push(full);
    else failures.push(`extension 內含非一般檔案：${path.relative(extension, full)}`);
  }
  return files;
}

const files = await allFiles(extension);
let jsCount = 0;
for (const file of files) {
  const relative = path.relative(extension, file);
  if (file.endsWith('.js') || file.endsWith('.mjs')) {
    const result = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8', windowsHide: true });
    jsCount++;
    if (result.error || result.status !== 0) failures.push(`${relative}: ${result.error?.message || result.stderr || 'JavaScript 語法檢查失敗'}`);
    const content = await readFile(file, 'utf8');
    for (const match of content.matchAll(/\b(?:import|export)\s+(?:[^'";]*?\s+from\s+)?['"](\.[^'"]+)['"]/g)) {
      try { await verifyReference(match[1], path.dirname(file)); }
      catch (error) { failures.push(`${relative}: ${error.message}`); }
    }
  }
  if (file.endsWith('.html')) {
    const html = await readFile(file, 'utf8');
    for (const match of html.matchAll(/<(?:script|link|img)\b[^>]*?\b(?:src|href)=["']([^"']+)["']/gi)) {
      try { await verifyReference(match[1], path.dirname(file)); }
      catch (error) { failures.push(`${relative}: ${error.message}`); }
    }
  }
}

if (failures.length) {
  console.error(`外掛檢查失敗：\n${failures.map((failure) => `- ${failure}`).join('\n')}`);
  process.exitCode = 1;
} else {
  console.log(`檢查通過：Manifest V3、${references.size} 個 manifest 資源、${jsCount} 個 JavaScript 檔案，以及 HTML / 模組的本機引用。`);
  console.log('此檢查不代表 Chrome 已載入外掛，也不代表 Threads 或 Facebook 已接受上傳。');
}
