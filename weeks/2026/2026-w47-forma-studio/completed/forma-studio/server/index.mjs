import http from 'node:http'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'
import { access, mkdir, stat } from 'node:fs/promises'
import { Assets, maxAsset } from './assets.mjs'
import { agentDraft, generatePhoto, references, verifyOpenAI } from './openai.mjs'
import { check, Problem, publicSettings, StudioStore } from './store.mjs'

const workspace = fileURLToPath(new URL('../',import.meta.url))
const now = () => new Date().toISOString()
const list = value => Array.isArray(value)
const object = value => value && typeof value === 'object' && !Array.isArray(value)
const typeTitles = {image:'角色定裝照',voice:'角色語音',video:'說話影片'}

async function readBody(req, max = 256 * 1024) {
  check(/^application\/json(?:;|$)/i.test(req.headers['content-type'] || ''), '請使用 JSON 格式送出資料。', 415)
  check(Number(req.headers['content-length'] || 0) <= max, '送出的資料太大。', 413)
  let size = 0
  const buffers = []
  for await (const chunk of req) {
    size += chunk.length
    check(size <= max, '送出的資料太大。', 413)
    buffers.push(chunk)
  }
  let body
  try { body = JSON.parse(Buffer.concat(buffers).toString('utf8')) } catch { throw new Problem(400,'JSON 格式錯誤。') }
  check(object(body), '請送出有效的表單。')
  return body
}
function json(res, data, status = 200) {
  res.writeHead(status, {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'})
  res.end(JSON.stringify(data))
}
function validateCharacter(value) {
  check(typeof value.name === 'string' && value.name.trim() && value.name.length <= 120,'角色名稱請填寫 1 到 120 個字。')
  if (value.references !== undefined) {
    check(list(value.references) && value.references.length <= 16 &&
      value.references.every(item => typeof (typeof item === 'string' ? item : item?.url) === 'string'), '請確認參考圖片的網址與數量。')
  }
}
function redact(message, settings) {
  let text = String(message).slice(0,1200)
  for (const key of [settings.openaiKey,settings.fishApiKey,settings.breezeToken]) if (key) text = text.replaceAll(key,'••••')
  return text.replace(/\bsk-[\w-]+/g,'••••')
}

export function createStudio({dataDir=path.join(workspace,'storage'), publicDir=path.join(workspace,'public'),
  fetchImpl=fetch, mediaRunner=async options => (await import('./media.mjs')).runMedia(options)} = {}) {
  dataDir = path.resolve(dataDir)
  publicDir = path.resolve(publicDir)
  const store = new StudioStore(dataDir)
  const assets = new Assets(store, dataDir,publicDir,fetchImpl)
  const stop = new AbortController()
  let queue = Promise.resolve()
  const updateJob = (id, fields) => store.put('jobs', {...store.get('jobs',id), ...fields})

  async function run(job, character, input, settings) {
    if (stop.signal.aborted) return
    try {
      updateJob(job.id,{status:'running',startedAt:now(),progress:'準備素材'})
      const outputDir = path.join(dataDir,'media',job.id)
      await mkdir(outputDir,{recursive:true})
      let result
      if (job.type === 'image') {
        updateJob(job.id,{progress:'正在產生圖片'})
        result = await generatePhoto({settings,fetchImpl,assets,character,input,outputDir,signal:stop.signal})
      } else {
        const imagePath = job.type === 'video' ? await assets.localImage(input.imageUrl,outputDir,stop.signal,job.attempt>1) : undefined
        const knownAudio = input.audioUrl || job.audioUrl
        let audioPath = knownAudio ? await assets.audio(knownAudio) : undefined
        let recoveredVoice = false
        if (!audioPath && job.type === 'video' && job.attempt > 1) {
          const previous = path.join(outputDir,'voice.wav')
          try {
            await access(path.join(outputDir,'longcat','run-manifest.json'))
            if ((await stat(previous)).size > 44) { audioPath = previous; recoveredVoice = true }
          } catch (error) { if (error.code !== 'ENOENT') throw error }
        }
        result = await mediaRunner({type:job.type,settings,input:{...input,character},imagePath,audioPath,outputDir,signal:stop.signal,
          onAudioReady: async filename => updateJob(job.id,{audioUrl:await assets.publish(outputDir,filename)}),
          onProgress:msg => { if (!stop.signal.aborted) updateJob(job.id,{progress:redact(msg,settings)}) }})
        if (recoveredVoice) result.audioPath = audioPath
      }
      const url = await assets.publish(outputDir,result.path)
      const audioUrl = result.audioPath ? await assets.publish(outputDir,result.audioPath) : input.audioUrl || store.get('jobs',job.id).audioUrl
      updateJob(job.id,{status:'succeeded',completedAt:now(),progress:'',url,...(audioUrl ? {audioUrl} : {})})
    } catch (e) {
      const msg = e instanceof Problem || !e.code ? e.message : '讀取素材或執行媒體服務失敗。'
      updateJob(job.id,{status:'failed',completedAt:now(),progress:'',error:redact(msg,settings)})
    }
  }
  function submit(body) {
    const {type, characterId} = body
    check(Object.hasOwn(typeTitles, type),'任務類型不正確。')
    check(typeof characterId === 'string','請先儲存並選擇角色。')
    const character = store.get('characters',characterId)
    const settings = store.settings()
    const input = {}
    for (const key of ['prompt','view','size','quality','text','provider','voiceId','imageUrl','audioUrl','performancePrompt','voiceInstruction','title']) {
      if (body[key] === undefined) continue
      check(typeof body[key] === 'string' && body[key].length <= 16000,'任務欄位格式錯誤。')
      input[key] = body[key]
    }
    if (body.referenceUrls !== undefined) {
      check(list(body.referenceUrls) && body.referenceUrls.length <= 16 && body.referenceUrls.every(r => typeof r === 'string' || (object(r) && typeof r.url === 'string')), '參考圖格式或數量有誤。')
      input.referenceUrls = body.referenceUrls
    }
    for (const k of ['scene','camera','shot','lighting','style','material','lens','pose','outfit','face']) {
      if (body[k] !== undefined) character[k] = body[k]
    }
    if (type === 'image') {
      check(settings.openaiKey, '請先到設定填入 OpenAI API 金鑰。', 409)
      check(!input.size || ['auto','1024x1024','1024x1536','1536x1024'].includes(input.size), '圖片尺寸不支援。')
      check(!input.quality || ['auto','low','medium','high'].includes(input.quality), '圖片品質選項錯誤。')
      references(character,input)
    } else {
      if (type === 'video') {
        check(settings.longcatEnabled, '請先在設定啟用 LongCat Colab。', 409)
        input.imageUrl ||= character.cover || character.references?.[0]?.url || character.face?.image
        check(input.imageUrl, '請先選擇演出照片。')
      }
      if (type === 'voice' || !input.audioUrl) {
        check(input.text?.trim() && input.text.length <= 5000,'請輸入 1 至 5,000 字的台詞。')
        input.provider ||= character.voice?.provider || 'fish'
        input.voiceId ||= character.voice?.id || character.voice?.voiceId || ''
        check(['fish','breeze'].includes(input.provider),'請選擇 Fish Audio 或 BreezeTTS。')
        if (input.provider === 'fish') check(settings.fishApiKey, '請先到設定填入 Fish Audio 金鑰。', 409)
      }
    }
    const job = store.put('jobs',{id:randomUUID(), type,characterId,characterName:character.name,
      title:input.title || input.view || typeTitles[type], status:'queued',createdAt:now(), progress:'等待執行',
      input, characterSnapshot:character})
    queue = queue.then(() => run(job,character,input,settings))
    return job
  }
  function retryJob(id) {
    const previous = store.get('jobs',id)
    check(previous.status === 'failed','只能重試先前失敗的任務。',409)
    const settings = store.settings()
    if (previous.type === 'image') check(settings.openaiKey,'請先到設定填入 OpenAI API 金鑰。',409)
    if (previous.type === 'video') check(settings.longcatEnabled,'請先在設定啟用 LongCat Colab。',409)
    const job = updateJob(id,{attempt:(previous.attempt || 1)+1,status:'queued',progress:'等待重新執行',completedAt:null,error:null})
    queue = queue.then(() => run(job,previous.characterSnapshot,previous.input,settings))
    return job
  }

  async function dispatch(req,res) {
    const host = req.headers.host || ''
    check(/^(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/i.test(host), '請使用本機網址開啟工作室。', 403)
    if (req.headers.origin) check(req.headers.origin === 'http://' + host, '請從本機工作室送出請求。',403)
    const url = new URL(req.url,'http://127.0.0.1')
    const p = url.pathname
    const method = req.method
    res.setHeader('X-Content-Type-Options','nosniff')
    res.setHeader('Referrer-Policy','no-referrer')
    if (!p.startsWith('/api/')) {
      check(['GET','HEAD'].includes(method),'不支援這個操作。',405)
      return assets.serve(p,req,res)
    }
    if (p === '/api/health' && method === 'GET') return json(res,{ok:true})
    if (p === '/api/settings' && method === 'GET') return json(res,{settings:publicSettings(store.settings())})
    if (p === '/api/settings' && method === 'PATCH') return json(res,{settings:store.updateSettings(await readBody(req))})
    if (p === '/api/settings/test' && method === 'POST') {
      const body = await readBody(req)
      check(!body.provider || body.provider === 'openai','目前支援 OpenAI 模型連線測試。')
      return json(res,await verifyOpenAI(store.settings(),fetchImpl,stop.signal))
    }
    if (p === '/api/uploads' && method === 'POST') {
      const {dataUrl} = await readBody(req,Math.ceil(maxAsset * 4 / 3) + 1024)
      return json(res,{url:await assets.upload(dataUrl)},201)
    }
    if (p === '/api/characters' && method === 'GET') return json(res,{characters:store.list('characters')})
    if (p === '/api/characters' && method === 'POST') {
      const value = await readBody(req)
      validateCharacter(value)
      const timestamp = now()
      return json(res,{character:store.put('characters',{...value,name:value.name.trim(),id:randomUUID(),createdAt:timestamp,updatedAt:timestamp})},201)
    }
    const member = /^\/api\/characters\/([\w-]+)$/.exec(p)
    if (member) {
      const id = member[1]
      if (method === 'GET') return json(res,{character:store.get('characters',id)})
      if (method === 'PUT' || method === 'PATCH') {
        const body = await readBody(req)
        const previous = store.get('characters',id)
        if (body.updatedAt) check(body.updatedAt === previous.updatedAt, '角色已在其他頁面更新，請重新載入後再儲存。',409)
        const value = {...previous,...body}
        validateCharacter(value)
        return json(res,{character:store.put('characters',{...value,name:value.name.trim(),id,createdAt:previous.createdAt,updatedAt:now()})})
      }
      if (method === 'DELETE') { store.removeCharacter(id); return json(res,{ok:true}) }
    }
    if (p === '/api/agent' && method === 'POST') {
      return json(res,await agentDraft({settings:store.settings(),fetchImpl,publicDir,input:await readBody(req),signal:stop.signal}))
    }
    if (p === '/api/jobs' && method === 'POST') return json(res,{job:submit(await readBody(req))},202)
    if (p === '/api/jobs' && method === 'GET') return json(res,{jobs:store.list('jobs')})
    const work = /^\/api\/jobs\/([\w-]+)$/.exec(p)
    if (work && method === 'GET') return json(res,{job:store.get('jobs',work[1])})
    const retry = /^\/api\/jobs\/([\w-]+)\/retry$/.exec(p)
    if (retry && method === 'POST') { await readBody(req); return json(res,{job:retryJob(retry[1])},202) }
    throw new Problem(404,'找不到這個操作。')
  }
  const server = http.createServer((req,res) => dispatch(req,res).catch(error => {
    if (res.headersSent) { res.destroy(); return }
    const message = error instanceof Problem ? error.message : '工作室暫時無法完成操作。'
    json(res,{error:message},error.status || 500)
  }))
  server.once('listening', () => store.recover())
  async function close() {
    stop.abort()
    const done = new Promise(resolve => server.close(resolve))
    server.closeIdleConnections()
    await Promise.all([done,queue])
    store.close()
  }
  return {server,close}
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  const port = Number(process.env.PORT || 4317)
  let app
  try { app = createStudio({dataDir:process.env.STUDIO_DATA_DIR || undefined}) } catch(error) {
    console.error(error instanceof Problem ? error.message : '無法開啟工作室資料目錄。')
    process.exit(1)
  }
  app.server.on('error',e => {
    console.error(e.code === 'EADDRINUSE' ? '連接埠已被使用，請開啟現有工作室或指定其他 PORT。' : '本機服務啟動失敗。')
    process.exitCode = 1
  })
  app.server.listen(port,'127.0.0.1',() => console.log('角色工作室 http://127.0.0.1:' + app.server.address().port))
  const shutdown = () => { app.close().then(() => process.exit(0)) }
  process.once('SIGINT',shutdown)
  process.once('SIGTERM',shutdown)
}
