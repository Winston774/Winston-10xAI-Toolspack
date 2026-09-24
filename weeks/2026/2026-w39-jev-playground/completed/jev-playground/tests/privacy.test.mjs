import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createSession } from '../public/session.mjs';
import { createWorker } from '../worker.mjs';

const origin = 'https://playground.example';
const sentinelA = 'TEST_ONLY_VISITOR_A_NOT_A_REAL_KEY';
const sentinelB = 'TEST_ONLY_VISITOR_B_NOT_A_REAL_KEY';
function answersFor(body) {
  return { answers: Object.fromEntries(Object.entries(body.questions).map(([id,q]) => {
    const options = Object.keys(q.criteria);
    return [id, q.type === 'noul' ? { type:'noul', noul: id.startsWith('veto_') ? 0.05 : 0.8 } :
      { type:'choice', choice: options[0], probabilities: Object.fromEntries(options.map((o,i)=>[o, i===0 ? 1 : 0])) }];
  })), usage: { input_tokens: 100, output_tokens: 10 } };
}
function request(key = sentinelA, body = { model:'jev-latest', state: { board: Array(20).fill('..........') }, questions:{ sense:{type:'noul',instructions:'Assess board',criteria:{true:'yes',false:'no'}} } }, siteOrigin = origin) {
  return new Request(`${origin}/api/jev`, { method:'POST', headers:{ origin:siteOrigin, authorization:`Bearer ${key}`, 'content-type':'application/json' }, body:JSON.stringify(body) });
}

test('preview makes no network request; fresh tabs have independent games and keys', async () => {
  const session = createSession({fetchImpl:()=>{throw new Error('Unexpected network');},previewDelayMs:0});
  const other = createSession({previewDelayMs:0});
  const before = await session.request('/api/state');
  await session.request('/api/config', {apiKey:sentinelA});
  await session.request('/api/step', {mode:'preview',version:before.game.version});
  assert.equal((await session.request('/api/state')).game.pieces,1);
  assert.equal((await other.request('/api/state')).game.pieces,0);
  assert.equal((await other.request('/api/status')).keyConfigured,false);
  assert.equal(JSON.stringify(session.export()).includes(sentinelA),false);
  assert.equal((await session.request('/api/state')).sessionStats.calls,0);
});

test('two visitors use only their own key; exactly three live calls; exports and status omit keys', async () => {
  const keys=[];
  const worker=createWorker({},async (url, options)=>{
    assert.equal(url,'https://api.typesafe.ai/v1/systemone');
    keys.push(options.headers.authorization);
    const body=JSON.parse(options.body); assert.equal(options.body.includes('TEST_ONLY'),false);
    return Response.json({...answersFor(body), debug:options.headers.authorization, model:sentinelA, headers:{authorization:sentinelB}});
  });
  const browserFetch=(_url, options)=>worker.fetch(new Request(`${origin}/api/jev`,{...options,headers:{...options.headers,origin}}));
  const a=createSession({fetchImpl:browserFetch}),b=createSession({fetchImpl:browserFetch});
  await a.request('/api/config',{apiKey:sentinelA}); await b.request('/api/config',{apiKey:sentinelB});
  for(const session of [a,b]) await session.request('/api/step',{mode:'live',version:(await session.request('/api/state')).game.version});
  assert.deepEqual(keys,[...Array(3).fill(`Bearer ${sentinelA}`),...Array(3).fill(`Bearer ${sentinelB}`)]);
  for(const session of [a,b]) {
    assert.equal((await session.request('/api/state')).game.pieces,1);
    assert.equal((await session.request('/api/state')).sessionStats.calls,3);
    const content=JSON.stringify([session.export(),await session.request('/api/state'),await session.request('/api/status')]);
    assert.equal(content.includes('TEST_ONLY'),false); assert.equal(content.includes('authorization'),false);
  }
  await a.request('/api/config',{apiKey:''});
  assert.equal((await a.request('/api/status')).keyConfigured,false);
  assert.equal((await b.request('/api/status')).keyConfigured,true);
  b.dispose(); assert.equal((await b.request('/api/status')).keyConfigured,false);
});

test('clear key cancels an in-flight call and prevents a late placement or next request', async () => {
  let started;const entered=new Promise(resolve=>started=resolve);let calls=0;
  const session=createSession({fetchImpl:async (_url, options)=>{calls++;started();return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}));}});
  await session.request('/api/config',{apiKey:sentinelA});
  const task=session.request('/api/step',{mode:'live',version:(await session.request('/api/state')).game.version});
  const rejected=assert.rejects(task,{code:'STOPPED'});await entered;
  await session.request('/api/config',{apiKey:''});await rejected;
  const state=await session.request('/api/state');assert.equal(state.game.pieces,0);assert.equal(state.busy,false);assert.equal(calls,1);
  await assert.rejects(session.request('/api/step',{mode:'live',version:state.game.version}),{code:'KEY_REQUIRED'});
});

test('relay errors never echo upstream body, exception, cookies or credentials', async () => {
  for(const fetcher of [async()=>new Response(sentinelA,{status:401,headers:{'set-cookie':sentinelA}}),async()=>{throw new Error(sentinelA);}]) {
    const response=await createWorker({},fetcher).fetch(request());
    assert.equal((await response.text()).includes(sentinelA),false);assert.equal(response.headers.has('set-cookie'),false);
    assert.equal(response.headers.get('cache-control'),'no-store');
  }
});

test('relay rejects cross-origin, missing-key and malformed requests without contacting Jev', async () => {
  let calls=0;const worker=createWorker({},async()=>{calls++;throw new Error('must not call');});
  assert.equal((await worker.fetch(request(sentinelA,undefined,'https://untrusted.example'))).status,403);
  assert.equal((await worker.fetch(request(''))).status,401);
  assert.equal((await worker.fetch(request(sentinelA,{model:'other',state:{},questions:{}}))).status,400);
  assert.equal((await worker.fetch(new Request(`${origin}/api/config`))).status,404);
  assert.equal((await worker.fetch(new Request(`${origin}/api/export`))).status,404);
  assert.equal(calls,0);
});

test('HTML and client code have no persistence, third-party scripts or server configuration writes',async()=>{
  const app=await readFile(new URL('../public/app.js',import.meta.url),'utf8');
  const session=await readFile(new URL('../public/session.mjs',import.meta.url),'utf8');
  const html=await readFile(new URL('../public/index.html',import.meta.url),'utf8');
  const worker=await readFile(new URL('../worker.mjs',import.meta.url),'utf8');
  assert.doesNotMatch(app+session+worker,/localStorage|sessionStorage|indexedDB|document\.cookie|console\.(log|error|warn)|caches\.put/);
  assert.doesNotMatch(html,/<script[^>]+src=["']https?:/);
  assert.match(app,/pagehide.*session\.dispose/); assert.match(app,/input\.value=''/);
  assert.match(html,/Created by Winston/);assert.doesNotMatch(html,/<section class="intro"/);
  assert.deepEqual((await readdir(new URL('../public/',import.meta.url))).sort(),['app.js','favicon.svg','index.html','lib','session.mjs','styles.css']);
});
