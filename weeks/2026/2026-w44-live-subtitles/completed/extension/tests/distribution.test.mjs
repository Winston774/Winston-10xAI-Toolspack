import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { normalizeConfig, newSession, acceptsResult, advanceRevision, recordCue } from '../lib/session.js';
import { TARGET_LANGUAGES, normalizeTargetLanguage } from '../lib/languages.js';
import { createLiveCaptions } from '../lib/live-captions.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
test('manifest v3 and declared local assets exist',async()=>{
  const manifest=JSON.parse(await readFile(path.join(root,'manifest.json'),'utf8'));
  assert.equal(manifest.manifest_version,3);assert.equal(manifest.version,'0.3.0');
  const resources=[manifest.background.service_worker,manifest.action.default_popup,manifest.options_ui.page,...Object.values(manifest.icons),...Object.values(manifest.action.default_icon)];
  for(const name of resources)assert((await stat(path.join(root,name))).isFile(),name);
  for(const page of ['popup.html','options.html','offscreen.html']){
    const html=await readFile(path.join(root,page),'utf8');
    for(const [,name] of html.matchAll(/(?:src|href)="([^"#]+)"/g)){
      if(/^(https?:|data:)/.test(name))continue;
      assert((await stat(path.join(root,name))).isFile(),`${page}: ${name}`);
    }
  }
});
test('default configuration contains no credential and validates language and appearance',()=>{
  const config=normalizeConfig();assert.equal(config.geminiApiKey,'');assert.equal(config.targetLanguage,'zh-Hant');
  assert.equal(normalizeConfig({fontSize:100,position:'invalid'}).fontSize,40);
  assert.equal(normalizeConfig({position:'invalid'}).position,'bottom');
  assert(TARGET_LANGUAGES.length>70);assert.equal(normalizeTargetLanguage('ja'),'ja');
  assert.throws(()=>normalizeTargetLanguage('unsupported'));
});
test('session rejects stale events and tracks new cues',()=>{
  const s=newSession({tabId:1,mediaKey:'tab:test',config:normalizeConfig(),id:'test'});
  assert(acceptsResult(s,{sessionId:'test',revision:0}));
  const next=advanceRevision(s);assert(!acceptsResult(next,{sessionId:'test',revision:0}));
  assert(recordCue(next,{sequence:0}));assert(recordCue(next,{sequence:0}));assert.equal(next.segments,1);
  assert(!recordCue(next,{sequence:-1}));
});
test('caption stream joins original and translation and finishes without audio network',()=>{
  let n=0;const captions=createLiveCaptions({prefix:'test',nextSequence:()=>n++});
  const first=captions.push({input:{text:'Hello',finished:false}},1);assert.equal(first[0].original,'Hello');
  const finished=captions.push({output:{text:'你好',finished:true},turnComplete:true},2);
  assert.equal(finished[0].translation,'你好');assert.equal(finished[0].original,'Hello');assert.equal(finished[0].partial,false);
});
