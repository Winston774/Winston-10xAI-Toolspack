import fs from 'node:fs/promises'
import path from 'node:path'
import { check, Problem } from './store.mjs'
import { imageFormat } from './assets.mjs'

const endpoint = 'https://api.openai.com/v1/'
const profileFields = ['name','description','personality','age','hair','makeup','body','proportions','scene','camera','shot','lens','lighting','material','style']
const catalogFields = {face:'faces',outfit:'outfits',pose:'poses'}
const labels = {
  name:'角色名稱',description:'人物設定',personality:'個性',makeup:'妝容',body:'身材',proportions:'身體比例',
  face:'臉部',outfit:'服裝',pose:'姿勢',scene:'場景',camera:'機位',shot:'景別',lighting:'光影',style:'攝影風格',
  materials:'材質',material:'材質',lens:'鏡頭',hair:'髮型',age:'年齡',gender:'性別',expression:'表情',appearance:'外觀',
}
function describe(value) {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(describe).filter(Boolean).join('、')
  if (value && typeof value === 'object') return [value.name, value.description, describe(value.tags)].filter(Boolean).join('，')
  return ''
}
function describeCharacter(character) {
  return Object.entries(labels).map(([key,label]) => {
    const value = describe(character?.[key])
    return value ? label + '：' + value : null
  }).filter(Boolean).join('\n')
}

function cleanProviderError(error, key) {
  const msg = String(error || '').replaceAll(key, '••••').replace(/\bsk-[\w-]+/g,'••••').slice(0,360)
  return msg ? '（' + msg + '）' : ''
}
async function call(settings, fetchImpl, route, init, signal) {
  check(settings.openaiKey, '請先到設定填入 OpenAI API 金鑰。', 409)
  const combined = AbortSignal.any([signal, AbortSignal.timeout(route.startsWith('images/') ? 600000 : 100000)])
  const options = { ...init, headers:{...init.headers,Authorization:'Bearer ' + settings.openaiKey}, redirect:'error', signal:combined }
  let response
  try { response = await fetchImpl(endpoint + route, options) }
  catch (error) {
    throw new Problem(502, combined.aborted ? 'OpenAI 請求逾時或已中斷，請先查看執行紀錄再重試。' : '無法連線至 OpenAI，請檢查網路連線。')
  }
  let data
  try { data = await response.json() } catch { throw new Problem(502,'OpenAI 回傳了無法讀取的資料。') }
  if (!response.ok) {
    const statusText = { 401:'金鑰無效。',403:'沒有這個模型的使用權限。',404:'找不到指定的模型。',429:'額度或速率已達上限。' }
    throw new Problem(502,'OpenAI ' + (statusText[response.status] || ('請求失敗（HTTP ' + response.status + '）。')) +
      cleanProviderError(data?.error?.message,settings.openaiKey))
  }
  return data
}
export async function verifyOpenAI(settings, fetchImpl, signal) {
  const models = [...new Set([settings.textModel, settings.imageModel])]
  await Promise.all(models.map(id => call(settings, fetchImpl, 'models/' + encodeURIComponent(id), {method:'GET'}, signal)))
  return {ok:true, models}
}

export function references(character, input) {
  const entries = []
  const add = (url,label) => {
    if (typeof url === 'string' && url && !entries.some(item => item.url === url)) entries.push({url,label})
  }
  for (const item of character.references || []) add(typeof item === 'string' ? item : item?.url, '角色設定參考：' + (item?.label || '原角色'))
  const source = item => typeof item === 'object' && item ? item.reference || item.image : ''
  add(source(character.face),'臉部參考，保留臉型與可辨識特徵')
  if (!entries.length) add(character.cover, '角色封面，保留人物身分')
  add(source(character.outfit),'僅套用這張圖的穿搭與服裝材質，忽略示範者的臉')
  add(source(character.pose),'僅採用這張圖的姿勢，忽略示範者的臉與衣著')
  add(source(character.sceneAsset),'使用這張圖的場景、空間與背景，維持角色身分與造型')
  for (const item of input.referenceUrls || []) add(typeof item === 'string' ? item : item?.url, item?.label || '自訂參考')
  check(entries.length <= 16, '單次生圖最多可使用 16 張不同參考圖片。')
  return entries
}
function imagePrompt(character,input,refs) {
  return [
    '為以下虛構角色拍攝一張高品質定裝照。維持同一人的五官、骨架與身體比例，依所選造型及拍攝條件呈現。畫面不加入文字與標誌。',
    describeCharacter(character), input.view && ('所需視圖：' + input.view),
    refs.map(({label},i) => '參考圖 ' + (i+1) + '：' + label).join('\n'),
    input.prompt && ('本次創作指示：' + input.prompt),
  ].filter(Boolean).join('\n\n')
}
export async function generatePhoto({settings,fetchImpl,assets,character,input,outputDir,signal}) {
  const refs = references(character,input)
  const prompt = imagePrompt(character,input,refs)
  const fields = {model:settings.imageModel,prompt,size:input.size || '1024x1536',quality:input.quality || 'medium'}
  let route = 'images/generations', init
  if (refs.length) {
    const form = new FormData()
    for (const [key,value] of Object.entries(fields)) form.append(key,value)
    for (const [i, ref] of refs.entries()) {
      const {bytes,mime,ext} = await assets.image(ref.url,signal)
      form.append('image[]',new Blob([bytes],{type:mime}), 'reference-' + (i+1) + '.' + ext)
    }
    route = 'images/edits'
    init = {method:'POST',body:form}
  } else init = {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fields)}
  const data = await call(settings, fetchImpl, route, init, signal)
  const encoded = data.data?.[0]?.b64_json
  check(typeof encoded === 'string' && encoded.length > 0, 'OpenAI 未提供圖片檔案。', 502)
  const bytes = Buffer.from(encoded,'base64')
  const format = imageFormat(bytes)
  check(!!format,'OpenAI 圖片格式無法辨識。',502)
  const file = path.join(outputDir,'portrait.' + format)
  await fs.writeFile(file,bytes)
  return {path:file}
}

async function readCatalog(publicDir) {
  try { return JSON.parse(await fs.readFile(path.join(publicDir,'catalog','index.json'),'utf8')) }
  catch (error) { if (error.code === 'ENOENT') return {}; throw error }
}

// Keep the model input small even when a source collection has thousands of entries.
function shortlist(items, brief, selected) {
  const terms = [...new Set(brief.match(/[a-z0-9]+|[\p{Script=Han}]/giu) || [])]
  const matches = (items || []).map((item,i) => {
    const summary = describe(item).toLowerCase()
    const score = terms.reduce((total,term) => total + Number(summary.includes(term.toLowerCase())), 0)
    return {item,i,score:score + Number(selected?.id === item.id) * 10}
  }).sort((a,b) => b.score-a.score || a.i-b.i).slice(0,28)
  return matches.map(({item}) => ({id:String(item.id),description:describe(item).slice(0,120)}))
}
export async function agentDraft({settings,fetchImpl,publicDir,input,signal}) {
  const brief = String(input.brief || input.prompt || '').trim()
  check(brief || (input.mode === 'prompt' && input.character), '請先描述想建立的角色或畫面。')
  const character = input.character || {}
  const catalog = input.mode === 'prompt' ? {} : await readCatalog(publicDir)
  const choices = Object.fromEntries(Object.entries(catalogFields).map(([field,group]) => [field,shortlist(catalog[group], brief, character[field])]))
  const promptMode = input.mode === 'prompt'
  const keys = promptMode ? ['prompt'] : [...profileFields,...Object.keys(catalogFields)]
  const schema = {type:'object',additionalProperties:false,properties:Object.fromEntries(keys.map(k => [k,{type:'string'}])),required:keys}
  const body = {
    model:settings.textModel,store:false,
    instructions: promptMode ?
      '你是台灣攝影指導。根據提供的角色、鏡位與文字，產出一段可直接用於生圖的繁體中文提示詞，保持角色身份一致。' :
      '你是虛構數位人造型師。以精簡自然的繁體中文填寫人物與攝影設定，在未指定修改的欄位保留使用者的原設定。face、outfit、pose 僅能填可選清單的 id 或空字串。',
    input:JSON.stringify({brief,character:describeCharacter(character),view:input.view || '',...(promptMode ? {} : {choices})}),
    text:{format:{type:'json_schema',name:promptMode?'photo_prompt':'character_design',strict:true,schema}},
  }
  const data = await call(settings,fetchImpl,'responses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)},signal)
  const value = (data.output || []).flatMap(item => item.content || []).filter(c => c.type === 'output_text').map(c => c.text).join('')
  let draft
  try { draft = JSON.parse(value) } catch { throw new Problem(502,'OpenAI 未回傳有效草稿，請調整描述再試一次。') }
  check(keys.every(key => typeof draft?.[key] === 'string'),'OpenAI 草稿欄位不完整。',502)
  if (promptMode) return {prompt:draft.prompt}
  for (const [field,group] of Object.entries(catalogFields)) {
    draft[field] = (catalog[group] || []).find(item => String(item.id) === draft[field]) || character[field] || null
  }
  return {draft}
}
