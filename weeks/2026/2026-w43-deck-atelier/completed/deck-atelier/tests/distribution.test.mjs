import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {loadStyles} from '../scripts/styles.mjs';
import {phraseTargets} from '../scripts/phrase.mjs';

const skill=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function cli(name,args,ok=true){
  const r=spawnSync(process.execPath,[path.join(skill,'scripts',name),...args],{encoding:'utf8',timeout:30000,windowsHide:true});
  assert.equal(Boolean(r.status===0),ok,r.stderr||r.error?.message||r.stdout);
  return r;
}
async function temporary(fn){
  const tempRoot=path.resolve(os.tmpdir());
  const dir=await fs.mkdtemp(path.join(tempRoot,'toolspack-w43-'));
  try{return await fn(dir);}finally{
    const target=path.resolve(dir);
    assert.equal(path.dirname(target),tempRoot);
    assert(path.basename(target).startsWith('toolspack-w43-'));
    await fs.rm(target,{recursive:true,force:true});
  }
}

test('all shipped JavaScript parses; Python AST parses without writing caches',async()=>{
  const scripts=(await fs.readdir(path.join(skill,'scripts'))).filter(x=>x.endsWith('.mjs'));
  for(const name of [...scripts.map(x=>'scripts/'+x),'assets/engine/atelier.js']){
    const r=spawnSync(process.execPath,['--check',path.join(skill,name)],{encoding:'utf8',windowsHide:true});
    assert.equal(r.status,0,r.stderr);
  }
  const py=process.platform==='win32'?'python':'python3';
  const code='import ast,sys; from pathlib import Path; root=Path(sys.argv[1]); files=list(root.rglob("*.py")); [ast.parse(p.read_text(encoding="utf-8-sig"),filename=str(p)) for p in files]; print(len(files))';
  const r=spawnSync(py,['-B','-c',code,skill],{encoding:'utf8',windowsHide:true});
  assert.equal(r.status,0,r.stderr||r.error?.message);
  assert.equal(Number(r.stdout.trim()),3);
});

test('all ten styles scaffold from their real registry and preserve authored content on retry',()=>temporary(async dir=>{
  const registry=await loadStyles();assert.equal(Object.keys(registry).length,10);
  for(const style of Object.keys(registry)){
    const output=path.join(dir,style);cli('new_deck.mjs',[output,'--title','Test <deck> & evidence','--style',style]);
    const p=path.join(output,'deck.html');const before=await fs.readFile(p,'utf8');
    assert(before.includes('data-style="'+style+'"'));
    assert(before.includes('Test &lt;deck&gt; &amp; evidence'));
    assert.equal((before.match(/class="slide"/g)||[]).length,5);
    assert(!before.includes('{{TITLE}}'));
    cli('new_deck.mjs',[output,'--style',style],false);
    assert.equal(await fs.readFile(p,'utf8'),before);
  }
}));

test('restyle changes fonts and theme while retaining authored notes',()=>temporary(async dir=>{
  cli('new_deck.mjs',[dir,'--title','Portable deck']);
  const p=path.join(dir,'deck.html');const before=await fs.readFile(p,'utf8');
  cli('set_style.mjs',[p,'--style','glitch']);const after=await fs.readFile(p,'utf8');
  assert(after.includes('data-style="glitch"'));assert(after.includes('data-theme="dark"'));
  assert(after.includes('Chakra+Petch'));assert(after.includes('Opening line. Why this matters'));
  cli('set_style.mjs',[p,'--style','does-not-exist'],false);
  assert.equal(await fs.readFile(p,'utf8'),after);assert.notEqual(after,before);
}));

test('static and motion bundling inlines local resources and leaves source untouched',()=>temporary(async dir=>{
  cli('new_deck.mjs',[dir,'--title','Bundle check']);const p=path.join(dir,'deck.html');
  const before=await fs.readFile(p,'utf8');const out=path.join(dir,'export');
  cli('build.mjs',[p,'--out',out,'--name','check','--no-fonts','--no-phrase']);
  for(const [name,motion] of [['check.html','off'],['check-motion.html','on']]){
    const result=await fs.readFile(path.join(out,name),'utf8');
    assert(result.includes('data-motion="'+motion+'"'));
    assert(result.includes('data-inlined="atelier.css"'));assert(result.includes('data-inlined="atelier.js"'));
    assert(!/<script[^>]+src="engine\//.test(result));
    assert(result.includes('fonts.googleapis.com'));
  }
  assert.equal(await fs.readFile(p,'utf8'),before);
}));

test('phrase targeting keeps author-controlled text, SVG and notes intact',()=>{
  const html='<h2 class="title">中文標題需要正確分詞</h2><p><span class="nw">手動分詞</span></p><aside class="notes"><p>私人講稿不處理</p></aside><svg><text>圖中文字</text></svg>';
  const targets=phraseTargets(html);assert.equal(targets.length,1);assert.equal(targets[0].text,'中文標題需要正確分詞');
});

test('bundled 15-slide example resolves its local engine resources',async()=>{
  const p=path.join(skill,'examples/attention/deck.html');const html=await fs.readFile(p,'utf8');
  assert.equal((html.match(/<section class="slide"/g)||[]).length,15);
  for(const [,reference] of html.matchAll(/<(?:link|script|img)\b[^>]*\b(?:href|src)="([^"]+)"/g)){
    if(/^(?:https?:|data:|#)/.test(reference))continue;
    assert((await fs.stat(path.resolve(path.dirname(p),reference))).isFile(),reference);
  }
});
