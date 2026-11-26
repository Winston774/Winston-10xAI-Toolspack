import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=async p=>readFile(path.join(root,p),'utf8');
test('manifest identifies immutable portable ZIP and expected digest',async()=>{
  const m=JSON.parse(await read('download-manifest.json'));
  assert.equal(m.version,'0.1.0-preview.1');assert.equal(m.platform,'Windows x64');
  assert.equal(m.asset_bytes,58577023);assert.equal(m.sha256,'e30c04e3d1c8e821e6522ac579c4ec2509aea40d3ba8140a9ca3a0c4323b5e7a');
  assert.equal(new URL(m.asset_url).host,'github.com');assert(m.asset_url.endsWith('/'+m.asset_name));
  assert(m.checksum_url.endsWith('/'+m.asset_name+'.sha256'));
});
test('supplied checksum matches download manifest',async()=>{
  const m=JSON.parse(await read('download-manifest.json'));
  const line=(await read(m.asset_name+'.sha256')).trim();
  assert.equal(line,m.sha256+'  '+m.asset_name);
});
test('installation handoff and source notices remain available',async()=>{
  for(const file of ['AGENT_INSTALL.md','README-FIRST.md','使用指南.md','LICENSE.txt','VB-CABLE-NOTICE.md'])assert((await stat(path.join(root,file))).size>0,file);
  const text=await read('AGENT_INSTALL.md');assert(text.includes('UAC'));assert(text.includes('備份'));assert(text.includes('還原'));assert(text.includes('未測'));
});
test('example profile has only placeholder device selections',async()=>{
  const p=JSON.parse(await read('profile.example.json'));
  assert(p.source_id.startsWith('REPLACE_WITH_'));assert(p.mic_id.startsWith('REPLACE_WITH_'));
  for(const role of ['FL','FR','RL','RR']){assert(p.channels[role].device_id.startsWith('REPLACE_WITH_'));assert.equal(p.channels[role].delay_ms,0);}
});
