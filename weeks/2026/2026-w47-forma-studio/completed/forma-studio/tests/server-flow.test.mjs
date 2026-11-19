import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import http from 'node:http'
import { setTimeout as delay } from 'node:timers/promises'
import { DatabaseSync } from 'node:sqlite'
import { createStudio } from '../server/index.mjs'

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/WS6U4YAAAAASUVORK5CYII=','base64')
async function setup(t, overrides={}) {
  const root = await mkdtemp(path.join(tmpdir(),'studio-api-test-'))
  const dataDir = path.join(root,'storage'), publicDir = path.join(root,'public')
  await mkdir(path.join(publicDir,'catalog'),{recursive:true})
  await writeFile(path.join(publicDir,'index.html'),'<title>角色工作室</title>')
  const face = {id:'f1',name:'短髮',reference:'/catalog/face.png',image:'/catalog/face.png'}
  const outfit = {id:'o1',name:'套裝',reference:'/catalog/outfit.png'}
  const pose = {id:'p1',name:'站姿',reference:'/catalog/pose.png'}
  for (const item of [face,outfit,pose]) await writeFile(path.join(publicDir,item.reference.slice(1)),png)
  await writeFile(path.join(publicDir,'catalog','index.json'),JSON.stringify({faces:[face],outfits:[outfit],poses:[pose]}))
  let app, origin
  const start = async () => {
    app = createStudio({dataDir, publicDir,fetchImpl: async () => { throw Error('未設定測試供應商') }, ...overrides})
    await new Promise(resolve => app.server.listen(0,'127.0.0.1',resolve))
    origin = 'http://127.0.0.1:' + app.server.address().port
  }
  await start()
  t.after(async() => { await app.close(); await rm(root,{recursive:true,force:true}) })
  const request = async (url, method='GET', body) => {
    const r = await fetch(origin+url,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
    return {status:r.status,...await r.json()}
  }
  const poll = async id => {
    for (let i=0;i<50;i++) {
      const {job} = await request('/api/jobs/'+id)
      if (['failed','succeeded'].includes(job.status)) return job
      await delay(10)
    }
    throw new Error('工作未完成')
  }
  return {face,outfit,pose,request,poll,dataDir,url:() => origin,fetch:(url,options)=>fetch(origin+url,options),restart:async mid => {
    await app.close()
    if (mid) mid()
    await start()
  }}
}

test('local character template, reference uploads, secret filtering, range reads, restart persistence and origin checks',async t => {
  const s = await setup(t)
  assert.throws(()=>createStudio({dataDir:s.dataDir}),/已由另一個工作室使用/)
  const settings = await s.request('/api/settings','PATCH',{openaiKey:'dummy-secret',breezeToken:'dummy-breeze',fishKey:'dummy-fish'})
  assert.deepEqual([settings.settings.openaiKeySet,settings.settings.fishKeySet,settings.settings.breezeTokenSet],[true,true,true])
  assert.doesNotMatch(JSON.stringify(settings),/dummy/)
  assert.equal((await s.fetch('/api/settings',{headers:{Origin:'https://example.org'}})).status,403)
  const externalHost = await new Promise((resolve,reject) => {
    http.get(s.url() + '/api/settings',{headers:{Host:'example.org'}},r => { r.resume(); resolve(r.statusCode) }).on('error',reject)
  })
  assert.equal(externalHost,403)
  assert.equal((await s.fetch('/storage/studio.sqlite')).status,404)
  const invalid = await s.request('/api/uploads','POST',{dataUrl:'data:image/png;base64,' + Buffer.from('hello').toString('base64')})
  assert.equal(invalid.status,400)
  const {url} = await s.request('/api/uploads','POST',{dataUrl:'data:image/png;base64,'+png.toString('base64')})
  const partial = await s.fetch(url,{headers:{Range:'bytes=0-7'}})
  assert.equal(partial.status,206)
  assert.deepEqual(Buffer.from(await partial.arrayBuffer()),png.subarray(0,8))
  assert.equal((await s.fetch(url,{headers:{Range:'bytes=999-'}})).status,416)
  const {character} = await s.request('/api/characters','POST',{name:'秋雨',references:[{label:'正面',url}],body:'高挑'})
  assert.equal((await s.request('/api/characters/'+character.id,'PUT',{body:'中等',updatedAt:'stale'})).status,409)
  const edit = await s.request('/api/characters/'+character.id,'PUT',{body:'中等',updatedAt:character.updatedAt})
  assert.equal(edit.character.name,'秋雨')
  await s.restart()
  assert.equal((await s.request('/api/settings')).settings.fishKeySet,true)
  assert.deepEqual((await s.request('/api/characters')).characters[0],edit.character)
  assert.equal((await s.fetch(url)).status,200)
  assert.equal((await s.request('/api/characters/'+character.id,'DELETE')).ok,true)
  assert.equal((await s.request('/api/characters/'+character.id)).status,404)
})

test('photo generation and edits send actual ordered identity, clothing and pose reference bytes',async t => {
  const calls = []
  const fetchImpl = async (url, options) => {
    calls.push({url, options})
    return Response.json({data:[{b64_json:png.toString('base64')}]})
  }
  const s = await setup(t,{fetchImpl})
  const {character} = await s.request('/api/characters','POST',{name:'澄'})
  const submit = () => s.request('/api/jobs','POST',{type:'image',characterId:character.id,view:'三視圖',prompt:'換上套裝'})
  assert.equal((await submit()).status,409)
  assert.equal(calls.length,0)
  await s.request('/api/settings','PATCH',{openaiKey:'unused-test-key'})
  const first = await submit()
  assert.equal(first.status,202)
  const photo = await s.poll(first.job.id)
  assert.equal(photo.status,'succeeded')
  assert.match(calls[0].url,/images\/generations$/)
  assert.match(JSON.parse(calls[0].options.body).prompt,/三視圖/)
  const {url:scenePhoto} = await s.request('/api/uploads','POST',{dataUrl:'data:image/png;base64,'+png.toString('base64')})
  const partialEdit = {face:s.face,pose:s.pose,outfit:s.outfit,sceneAsset:{name:'影棚',image:scenePhoto},references:[{label:'側面',url:photo.url}]}
  await s.request('/api/characters/'+character.id,'PUT',partialEdit)
  const second = await s.poll((await submit()).job.id)
  assert.equal(second.status,'succeeded',second.error)
  assert.match(calls[1].url,/images\/edits$/)
  const form = calls[1].options.body
  assert.match(form.get('prompt'),/參考圖 3：僅套用這張圖的穿搭/)
  assert.match(form.get('prompt'),/參考圖 4：僅採用這張圖的姿勢/)
  assert.match(form.get('prompt'),/參考圖 5：使用這張圖的場景/)
  assert.equal(form.getAll('image[]').length,5)
  for (const file of form.getAll('image[]')) assert.deepEqual(Buffer.from(await file.arrayBuffer()),png)
  assert.deepEqual(Buffer.from(await (await s.fetch(second.url)).arrayBuffer()),png)
  assert.equal((await s.request('/api/jobs')).jobs.length,2)
})

test('agent uses editable profile fields, valid catalog entries, prompt mode and read-only model verification',async t => {
  const calls = []
  const fetchImpl = async (url, options) => {
    calls.push(url)
    if (url.includes('/models/')) return Response.json({id:url.split('/').pop()})
    const req = JSON.parse(options.body)
    const keys = req.text.format.schema.required
    const values = Object.fromEntries(keys.map(key => [key,'攝影師']))
    Object.assign(values, keys.includes('prompt') ? {prompt:'晨光下的攝影師'} : {face:'f1',outfit:'o1',pose:'p1'})
    return Response.json({output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(values)}]}]})
  }
  const s = await setup(t,{fetchImpl})
  await s.request('/api/settings','PATCH',{openaiKey:'unused-test-key'})
  const result = await s.request('/api/settings/test','POST',{provider:'openai'})
  assert.equal(result.ok,true)
  assert.ok(calls.every(url => url.includes('/models/')))
  const {draft} = await s.request('/api/agent','POST',{brief:'攝影師'})
  assert.deepEqual(draft.face,s.face)
  assert.deepEqual(draft.outfit,s.outfit)
  assert.equal((await s.request('/api/agent','POST',{brief:'晨光',mode:'prompt'})).prompt,'晨光下的攝影師')
  assert.equal((await s.request('/api/characters')).characters.length,0)
})

test('voice output can drive a video, or a video can generate speech from text, and raw working files stay private',async t => {
  const inputs = []
  const mediaRunner = async ({type,input,audioPath,imagePath,outputDir,onProgress}) => {
    inputs.push(input)
    onProgress('執行中')
    await writeFile(path.join(outputDir,'private.txt'),'test')
    const audio = path.join(outputDir,'voice.wav')
    if (!audioPath) await writeFile(audio,'test-audio')
    if (type === 'voice') return {path:audio}
    assert.deepEqual(await readFile(imagePath),png)
    if (audioPath) assert.equal(await readFile(audioPath,'utf8'),'test-audio')
    const file = path.join(outputDir,'portrait.mp4')
    await writeFile(file,'test-video')
    return {path:file,...(!audioPath?{audioPath:audio}:{})}
  }
  const s = await setup(t,{mediaRunner})
  await s.request('/api/settings','PATCH',{longcatEnabled:true})
  const {character:c} = await s.request('/api/characters','POST',{name:'晨',cover:s.face.image})
  const base = {characterId:c.id,provider:'breeze',text:'早安'}
  const {job:v} = await s.request('/api/jobs','POST',{...base,type:'voice'})
  const a = await s.poll(v.id)
  assert.equal(a.status,'succeeded')
  assert.equal((await s.fetch('/media/'+v.id+'/private.txt')).status,404)
  const {job:movie} = await s.request('/api/jobs','POST',{characterId:c.id,type:'video',audioUrl:a.url})
  const video = await s.poll(movie.id)
  assert.equal(video.status,'succeeded',video.error)
  assert.equal(video.audioUrl,a.url)
  const full = await s.poll((await s.request('/api/jobs','POST',{...base,type:'video'})).job.id)
  assert.equal(full.status,'succeeded')
  assert.ok(full.audioUrl.includes(full.id))
  assert.equal(inputs[2].character.id,c.id)
})

test('provider errors redact credentials and interrupted jobs become failed without a second paid submission',async t => {
  let calls=0
  const s = await setup(t,{fetchImpl:async () => {
    calls++
    return Response.json({error:{message:'wrong dummy-key'}},{status:401})
  }})
  const {character:c} = await s.request('/api/characters','POST',{name:'澄'})
  await s.request('/api/settings','PATCH',{openaiKey:'dummy-key'})
  const {job} = await s.request('/api/jobs','POST',{type:'image',characterId:c.id})
  const fail = await s.poll(job.id)
  assert.equal(fail.status,'failed')
  assert.doesNotMatch(fail.error,/dummy-key/)
  await s.restart(() => {
    const db = new DatabaseSync(path.join(s.dataDir,'studio.sqlite'))
    db.prepare('UPDATE jobs SET value=? WHERE id=?').run(JSON.stringify({...job,status:'running'}),job.id)
    db.close()
  })
  assert.match((await s.request('/api/jobs/'+job.id)).job.error,/中斷/)
  assert.equal(calls,1)
  assert.equal((await s.request('/api/jobs/'+job.id+'/retry','POST',{})).status,202)
  assert.equal((await s.poll(job.id)).attempt,2)
  assert.equal(calls,2)
})

test('failed video keeps its WAV, and retry uses the original scene and subject snapshot without resynthesizing', async t => {
  const attempts=[]
  let downloads=0
  const s=await setup(t,{fetchImpl:async()=>{
    downloads++
    return downloads===1 ? new Response(png) : new Response(null,{status:404})
  },mediaRunner:async({input,audioPath,outputDir,onAudioReady})=>{
    attempts.push({name:input.character.name,scene:input.character.scene,outputDir,audioPath})
    if(attempts.length===1){
      const file=path.join(outputDir,'voice.wav')
      await writeFile(file,'recorded-audio')
      await onAudioReady(file)
      throw Error('模擬 LongCat 暫時無法使用')
    }
    assert.equal(await readFile(audioPath,'utf8'),'recorded-audio')
    const file=path.join(outputDir,'portrait.mp4')
    await writeFile(file,'test-video')
    return {path:file}
  }})
  await s.request('/api/settings','PATCH',{longcatEnabled:true})
  const {character}=await s.request('/api/characters','POST',{name:'阿任',scene:'棚拍',cover:'https://ai-portrait-gallery.pages.dev/img/full/test.png'})
  const {job}=await s.request('/api/jobs','POST',{type:'video',characterId:character.id,provider:'breeze',text:'嗨'})
  const failed=await s.poll(job.id)
  assert.equal(failed.status,'failed')
  assert.equal(await (await s.fetch(failed.audioUrl)).text(),'recorded-audio')
  await s.request('/api/characters/'+character.id,'PUT',{name:'新角色',scene:'海邊'})
  await s.request('/api/jobs/'+job.id+'/retry','POST',{})
  const done=await s.poll(job.id)
  assert.equal(done.status,'succeeded',done.error)
  assert.equal(done.audioUrl,failed.audioUrl)
  assert.equal(attempts[0].outputDir,attempts[1].outputDir)
  assert.deepEqual([attempts[1].name,attempts[1].scene],['阿任','棚拍'])
  assert.equal(downloads,1)
})

test('Windows migrates legacy credentials to user-scoped DPAPI and preserves unreadable records', {skip:process.platform!=='win32'}, async t=>{
  const s=await setup(t)
  const file=path.join(s.dataDir,'studio.sqlite')
  const key='synthetic-migration-credential'
  await s.restart(()=>{
    const db=new DatabaseSync(file)
    db.prepare('INSERT OR REPLACE INTO settings VALUES (1,?)').run(JSON.stringify({openaiKey:key}))
    db.close()
  })
  const state=await s.request('/api/settings')
  assert.equal(state.settings.openaiKeySet,true)
  assert.doesNotMatch(JSON.stringify(state),/protectedSecrets|synthetic-migration/)
  const readRecord=()=>{
    const db=new DatabaseSync(file)
    try{return db.prepare('SELECT value FROM settings WHERE id=1').get().value}
    finally{db.close()}
  }
  const protectedRow=JSON.parse(readRecord())
  assert.ok(protectedRow.protectedSecrets.length>128)
  assert.equal(protectedRow.openaiKey,undefined)
  assert.equal((await readFile(file)).includes(Buffer.from(key)),false)
  await s.restart()
  assert.equal((await s.request('/api/settings')).settings.openaiKeySet,true)
  const corrupt=JSON.stringify({...protectedRow,protectedSecrets:'AAAA'})
  await s.restart(()=>{
    const db=new DatabaseSync(file)
    db.prepare('UPDATE settings SET value=? WHERE id=1').run(corrupt)
    db.close()
  })
  assert.equal((await s.request('/api/settings','PATCH',{openaiKey:'replacement'})).status,409)
  assert.equal(readRecord(),corrupt)
})
