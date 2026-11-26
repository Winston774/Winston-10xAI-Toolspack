import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { chromium } from 'playwright-core'
import { createStudio } from '../server/index.mjs'

const browserPath = [process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome','/usr/bin/chromium','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',chromium.executablePath()]
  .find(value => value && existsSync(value))
const hasFfmpeg = spawnSync('ffmpeg',['-version'],{stdio:'ignore',windowsHide:true}).status === 0
const skip = !browserPath ? '需要 Chromium 瀏覽器' : !hasFfmpeg ? '需要 FFmpeg 產生測試用影音' : false
test('browser generates a portrait, uses that exact photo for performance, and plays the resulting local work', {skip,timeout:60000}, async t => {
  const root=await mkdtemp(path.join(tmpdir(),'forma-production-ui-'))
  const photoBytes=await readFile(new URL('../public/art/sora.webp',import.meta.url))
  const stills=[],clips=[]
  let fixtureError
  const app=createStudio({
    dataDir:path.join(root,'storage'),
    fetchImpl:async (url,options)=>{
      assert.match(url,/images\/edits$/)
      const form=options.body
      stills.push({prompt:form.get('prompt'),files:await Promise.all(form.getAll('image[]').map(file=>file.arrayBuffer().then(Buffer.from)))})
      return Response.json({data:[{b64_json:photoBytes.toString('base64')}]})
    },
    mediaRunner:async({type,input,imagePath,audioPath,outputDir,onAudioReady})=>{
      try {
      assert.equal(type,'video')
      assert.equal(audioPath,undefined)
      assert.deepEqual(await readFile(imagePath),photoBytes)
      clips.push(input)
      const video=path.join(outputDir,'portrait.mp4'), audio=path.join(outputDir,'voice.wav')
      // A silent fixture exercises browser playback without a TTS or GPU request.
      const run=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=0x808080:s=32x32:r=12',
        '-f','lavfi','-i','anullsrc=r=16000:cl=mono','-map','0:v:0','-map','1:a:0','-t','0.75','-c:v','libx264','-pix_fmt','yuv420p',
        '-c:a','aac','-movflags','+faststart',video,'-map','1:a:0','-t','0.75','-c:a','pcm_s16le',audio],{windowsHide:true})
      assert.equal(run.status,0,run.stderr?.toString())
      await onAudioReady(audio)
      return {path:video,audioPath:audio}
      } catch (error) { fixtureError = error; throw error }
    },
  })
  await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve))
  let browser
  t.after(async()=>{ if(browser) await browser.close();await app.close();await rm(root,{recursive:true,force:true}) })
  const base='http://127.0.0.1:'+app.server.address().port
  await fetch(base+'/api/settings',{method:'PATCH',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({openaiKey:'browser-fake-key',longcatEnabled:true})})
  browser=await chromium.launch({executablePath:browserPath,headless:true})
  const page=await browser.newPage()
  page.setDefaultTimeout(10000)
  const errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto(base)
  await page.locator('.hero-button').click()
  await page.locator('[data-act="tab"][data-id="shoot"]').click()
  await page.locator('[data-field="view"]').selectOption('側面肖像')
  await page.locator('[data-field="prompt"]').fill('坐在工作室窗邊')
  await page.getByRole('button',{name:'生成圖片'}).click()
  await page.waitForURL('**/#works')
  await page.locator('.result-card:has(img)').click()
  await page.getByRole('button',{name:'用這張照片演出'}).click()
  await page.waitForURL('**/perform')
  const photo=await page.locator('[data-field="performancePhoto"]').inputValue()
  assert.match(photo,/^\/media\/.+\/portrait.webp$/)
  await page.locator('[data-voice="provider"]').selectOption('fish')
  assert.equal(await page.locator('[data-voice="instruction"]').count(),0)
  await page.locator('[data-voice="provider"]').selectOption('breeze')
  await page.locator('[data-voice="instruction"]').fill('輕聲朗讀')
  await page.locator('[data-field="script"]').fill('大家好，我是空。')
  await page.locator('[data-field="performancePrompt"]').fill('微笑看著鏡頭')
  await page.getByRole('button',{name:'生成說話影片'}).click()
  await page.waitForURL('**/#works')
  let video
  const deadline=Date.now()+10000
  while(Date.now()<deadline){
    const {jobs}=await (await fetch(base+'/api/jobs')).json()
    video=jobs.find(j=>j.type==='video')
    if(video && ['failed','succeeded'].includes(video.status))break
    await delay(50)
  }
  assert.ok(video,'沒有收到影片任務')
  if (fixtureError) throw fixtureError
  assert.equal(video.status,'succeeded',video.error)
  await page.getByRole('button',{name:'重新整理'}).click()
  await page.locator('.result-card[data-id="'+video.id+'"]').click()
  const player=page.locator('dialog video')
  assert.equal(await player.getAttribute('src'),video.url)
  await player.evaluate(node=>{node.muted=true;return node.play()})
  await page.waitForFunction(()=>document.querySelector('dialog video')?.currentTime>0)
  assert.equal(await page.getByRole('link',{name:'下載配音'}).getAttribute('href'),video.audioUrl)
  assert.equal(stills.length,1);assert.equal(stills[0].files.length,2)
  assert.deepEqual(stills[0].files[0],photoBytes)
  assert.deepEqual(stills[0].files[1],await readFile(new URL('../public/art/scene-0.webp',import.meta.url)))
  assert.match(stills[0].prompt,/坐在工作室窗邊/)
  assert.match(stills[0].prompt,/時裝企劃與品牌敘事者/)
  assert.match(stills[0].prompt,/側面肖像/)
  assert.equal(clips[0].character.id,video.characterId)
  assert.equal(clips[0].imageUrl,photo)
  assert.equal(clips[0].provider,'breeze')
  assert.equal(clips[0].voiceInstruction,'輕聲朗讀')
  assert.equal(clips[0].performancePrompt,'微笑看著鏡頭')
  assert.equal(clips[0].text,'大家好，我是空。')
  assert.deepEqual(errors,[])
})
