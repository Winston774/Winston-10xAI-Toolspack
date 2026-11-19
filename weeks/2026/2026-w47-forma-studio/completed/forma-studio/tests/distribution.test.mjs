import assert from 'node:assert/strict';
import { test } from 'node:test';
import { lstat, readFile, readdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { scenes, templates } from '../public/ui/presets.js';

const app = fileURLToPath(new URL('../', import.meta.url));
const week = path.resolve(app, '../..');
const read = (name) => readFile(path.join(app, name), 'utf8');
const forbidden = /^(?:\.git|node_modules|storage|tmp|test-results|__pycache__|\.env(?:\..*)?)$|\.(?:sqlite|db|pem|key|p12|pfx|log|zip|ipynb)$/i;
const credential = new RegExp(['(?:sk-|ghp_|github_pat_|AIza)[0-9a-z_-]{20,}', '-----BEGIN ' + '(?:RSA |EC |OPENSSH )?PRIVATE KEY-----', '(?:Bearer|[?&]token=)\\s+[0-9a-z_.-]{28,}'].join('|'), 'i');

async function files(dir) {
  const out = [];
  for (const name of await readdir(dir)) {
    assert(!forbidden.test(name), `不應分發：${name}`);
    const file = path.join(dir, name);
    const info = await lstat(file);
    assert(!info.isSymbolicLink(), `不允許連結：${name}`);
    if (info.isDirectory()) out.push(...await files(file));
    else { assert(info.isFile()); out.push(file); }
  }
  return out;
}

test('本機啟動與文件入口可解析；所有 JavaScript 通過語法檢查', async () => {
  const pkg = JSON.parse(await read('package.json'));
  assert.equal(pkg.engines.node, '>=24');
  assert.equal(pkg.scripts.start, 'node server/index.mjs');
  assert(!pkg.dependencies || Object.keys(pkg.dependencies).length === 0);
  assert.match(await read('server/index.mjs'), /\.listen\(port,'127\.0\.0\.1'/);
  for (const file of (await files(app)).filter(file => /\.m?js$/.test(file))) {
    const result = spawnSync(process.execPath, ['--check', file], {encoding: 'utf8'});
    assert.equal(result.status, 0, path.basename(file) + ': ' + result.stderr);
  }
  for (const file of (await files(week)).filter(file => /\.md$/.test(file))) {
    const content = await readFile(file, 'utf8');
    for (const [, href] of content.matchAll(/\]\(([^)\s]+)\)/gu)) {
      if (/^(?:https?:|#)/.test(href)) continue;
      const target = path.resolve(path.dirname(file), decodeURIComponent(href.split('#')[0]));
      assert(!path.relative(week, target).startsWith('..'), `連結超出教材：${href}`);
      await lstat(target);
    }
  }
});

test('五個影片無關的角色範本與十二個場景只依賴隨包素材', async () => {
  const catalog = JSON.parse(await read('public/catalog/index.json'));
  assert.equal(templates.length, 5);
  assert.equal(scenes.length, 12);
  assert.equal(catalog.faces.length, 5);
  assert.deepEqual(catalog.outfits, []);
  assert.deepEqual(catalog.poses, []);
  const paths = [...templates.flatMap(t => [t.cover, ...t.references.map(r => r.url)]),
    ...[...scenes, ...catalog.faces].flatMap(e => [e.image, e.reference]), '/art/sora-hero.webp'];
  for (const asset of new Set(paths)) {
    assert.match(asset, /^\/art\/[a-z0-9-]+\.webp$/u);
    const bytes = await readFile(path.join(app, 'public', asset));
    assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF');
    assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP');
  }
});

test('教材內容排除工作站路徑、常見憑證及第三方素材快取', async () => {
  const entries = await files(week);
  assert(entries.some(file => file.endsWith('lucide-license.txt')));
  for (const file of entries) {
    const relative = path.relative(week, file).split(path.sep).join('/');
    assert(!/\/catalog\/cache\/|import_catalog\.py|\/personal\//i.test(relative), relative);
    if (/\.(?:md|json|yml|txt|m?js|py|html|svg|css)$/i.test(file) && file !== fileURLToPath(import.meta.url)) {
      const body = await readFile(file, 'utf8');
      assert(!credential.test(body), `可疑憑證格式：${relative}`);
      assert(!/(?:[A-Z]:[\\/](?:Users[\\/]|Codex[\\/])|\/home\/winston[\\/]|drive\.google\.com\/open\?id=)/i.test(body), `機器專屬路徑：${relative}`);
    }
  }
});
