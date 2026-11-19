const typeNames = {image:'圖片',voice:'語音',video:'影片'}
const statusNames = {queued:'等待中',running:'處理中',succeeded:'已完成',failed:'未完成'}
const viewNames = ['場景定裝照','正面肖像','側面肖像','三視圖（正面、側面、背面）','全身與比例']
const cameraNames = ['平視','略微俯拍','仰角','側面','背面','四分之三側面']
const shotNames = ['半身近景','臉部特寫','胸像','全身','遠景']
const lights = ['自然窗光','陰天散射光','柔光棚拍','黃金時刻','霓虹側光','戲劇性逆光']
const styles = ['自然寫實','日系清新','街頭風','文青感','商業攝影','澎湃電影感']

function imageUrl(value,esc) {
  if (typeof value !== 'string') return ''
  if (/^\/(?!\/)/.test(value) || /^https:\/\/(?:ai-portrait-gallery\.pages\.dev|raw\.githubusercontent\.com)\//.test(value)) return esc(value)
  return ''
}
function option(value,text,selected,esc) {
  return '<option value="' + esc(value) + '"' + (value === selected ? ' selected' : '') + '>' + esc(text) + '</option>'
}
function selectField(key,label,options,current,esc) {
  const values = current && !options.includes(current) ? [current,...options] : options
  return '<label class="field"><span>'+label+'</span><select data-field="'+key+'">' + values.map(v => option(v,v,current,esc)).join('') + '</select></label>'
}
function button(action,label,style='secondary',extra='') {
  return '<button type="button" class="btn '+style+'" data-act="prod-'+action+'" '+extra+'>'+label+'</button>'
}
function photoChoices(ctx) {
  const {draft, jobs} = ctx.state
  const choices = []
  function add(url,label) {
    if (url && !choices.some(item => item.url === url)) choices.push({url,label})
  }
  for (const job of jobs || []) {
    if (job.type === 'image' && job.status === 'succeeded' && job.characterId === draft?.id) add(job.url,job.title || '生成定裝照')
  }
  for (const item of draft?.references || []) add(typeof item === 'string' ? item : item.url, item.label || '角色參考圖')
  if (draft?.cover!==draft?.face?.image) add(draft?.cover,'角色封面')
  add(draft?.face?.reference || draft?.face?.image,'臉部素材')
  if (draft?.performancePhoto) add(draft.performancePhoto,'指定演出照片')
  return choices
}
function voiceChoices(ctx) {
  const draft = ctx.state.draft
  return (ctx.state.jobs || []).filter(job => ((job.type === 'voice' && job.status === 'succeeded') || job.audioUrl) && job.characterId === draft?.id)
    .map(job => ({url:job.type === 'voice' ? job.url : job.audioUrl,label:job.title + ' · ' + dateLabel(job.createdAt)}))
}
function dateLabel(value) {
  const d = new Date(value)
  return Number.isNaN(d.valueOf()) ? '' : d.toLocaleString('zh-TW',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})
}
function preview(url,label,ctx) {
  const src = imageUrl(url,ctx.esc)
  return '<div class="production-preview">'+(src ? '<img src="'+src+'" alt="'+ctx.esc(label)+'">' : '<div class="empty">'+ctx.icon('image',30)+'<p>尚未選擇照片</p></div>')+'</div>'
}
function shoot(ctx) {
  const {esc,state,icon} = ctx, d = state.draft
  const src = d.references?.[0]?.url || d.cover || d.face?.image || ''
  const scene = d.sceneAsset
  const sceneImage = imageUrl(scene?.image || scene?.reference,esc)
  return '<div class="production-layout"><section class="panel production-visual">'+preview(src,d.name || '人物參考',ctx)+
    '<div class="work-meta"><strong>'+esc(d.name || '角色')+'</strong><span class="muted">人物參考</span></div></section>'+
    '<section class="panel production-options"><h3 class="section-title">拍攝設定</h3>'+
    '<button type="button" class="scene-picker" data-act="prod-scene">'+(sceneImage ? '<img src="'+sceneImage+'" alt="">' : icon('image',22))+
    '<span><small>場景</small><strong>'+esc(d.scene || '選擇場景')+'</strong></span>'+icon('chevron-right',16)+'</button>'+
    '<div class="field-grid">'+selectField('view','視圖',viewNames,d.view || viewNames[0],esc)+selectField('shot','景別',shotNames,d.shot || shotNames[0],esc)+
    selectField('camera','機位',cameraNames,d.camera || cameraNames[0],esc)+selectField('lighting','光線',lights,d.lighting || lights[0],esc)+
    selectField('style','攝影風格',styles,d.style || styles[0],esc)+
    '<label class="field"><span>圖片比例</span><select data-field="size">'+[['1024x1536','直式 2:3'],['1024x1024','方形 1:1'],['1536x1024','橫式 3:2']].map(([v,t]) => option(v,t,d.size || '1024x1536',esc)).join('')+'</select></label>'+
    '<label class="field"><span>鏡頭</span><input data-field="lens" placeholder="例：85 mm，ƒ/2.8" value="'+esc(d.lens || '')+'"></label>'+
    '<label class="field"><span>材質與質感</span><input data-field="material" placeholder="例：亞麻布料、霧面膚質" value="'+esc(d.material || '')+'"></label></div>'+
    '<label class="field"><span>拍攝提示詞</span><textarea rows="3" data-field="prompt" placeholder="補充畫面中的細節">'+esc(d.prompt || '')+'</textarea></label>'+
    '<div class="production-actions">'+button('prompt',icon('sparkles',16)+' 潤飾提示詞')+
    button('image',icon('camera',17)+' 生成圖片','primary')+'</div></section></div>'
}
function perform(ctx) {
  const {esc,state,icon} = ctx, d = state.draft
  const photos = photoChoices(ctx), audio = voiceChoices(ctx)
  const photo = d.performancePhoto || photos[0]?.url || ''
  const voice = typeof d.voice === 'object' && d.voice ? d.voice : {}
  const provider = voice.provider || d.provider || 'fish'
  const audioUrl = audio.some(x => x.url === d.performanceAudio) ? d.performanceAudio : ''
  return '<div class="production-layout"><section class="panel production-visual">'+preview(photo,d.name || '演出照片',ctx)+
    '<label class="field"><span>演出照片</span><select data-field="performancePhoto" data-prod-redraw>'+
    (photos.length ? photos.map(p => option(p.url,p.label,photo,esc)).join('') : '<option value="">尚未選擇照片</option>')+'</select></label>'+
    button('upload-photo',icon('upload',15)+' 上傳演出照片','ghost')+'</section>'+
    '<section class="panel production-options"><h3 class="section-title">聲音與表演</h3>'+
    '<div class="field-grid"><label class="field"><span>語音服務</span><select data-voice="provider">'+
    option('fish','Fish Audio',provider,esc)+option('breeze','BreezeTTS',provider,esc)+'</select></label>'+
    '<label class="field"><span>音色 ID 或名稱</span><input data-voice="id" placeholder="留白使用預設聲音" value="'+esc(voice.id ?? voice.voiceId ?? d.voiceId ?? '')+'"></label></div>'+
    (provider==='breeze'?'<label class="field"><span>聲音指示</span><input data-voice="instruction" value="'+esc(voice.instruction ?? d.voiceInstruction ?? '')+'" placeholder="例：自然台灣口音，語速適中"></label>':'<p class="muted small">可用 Fish 音色 ID 指定聲音，也可在台詞內加入模型支援的語氣標記。</p>')+
    '<label class="field"><span>台詞</span><textarea rows="4" maxlength="5000" data-field="script" placeholder="輸入角色要說的話">'+esc(d.script || '')+'</textarea></label>'+
    button('voice',icon('mic',16)+' 合成語音','secondary')+
    '<label class="field"><span>影片配音</span><select data-field="performanceAudio">'+option('','使用上方台詞合成',audioUrl || '',esc)+
    audio.map(a => option(a.url,a.label,audioUrl,esc)).join('')+'</select></label>'+
    '<label class="field"><span>表演指示</span><textarea rows="2" maxlength="3000" data-field="performancePrompt" placeholder="例：直視鏡頭，微笑說話">'+esc(d.performancePrompt || '')+'</textarea></label>'+
    '<div class="production-actions">'+button('video',icon('video',17)+' 生成說話影片','primary')+'</div></section></div>'
}
function workCard(job,ctx) {
  const {esc,icon}=ctx, src=imageUrl(job.url,esc)
  const title=esc(job.title || typeNames[job.type] || '作品')
  let thumb
  if (job.type==='image' && src) thumb='<img src="'+src+'" alt="" loading="lazy">'
  else if (job.type==='video' && src) {
    const poster=imageUrl(job.input?.imageUrl,esc)
    thumb=poster ? '<img src="'+poster+'" alt="" loading="lazy">' : icon('video',28)
  } else thumb=icon(job.type==='voice'?'mic':job.type==='video'?'video':'image',28)
  return '<button type="button" class="result-card" data-act="prod-work" data-id="'+esc(job.id)+'"><span class="work-thumbnail">'+thumb+'</span>'+
    '<span class="work-meta"><strong>'+title+'</strong><small>'+esc(typeNames[job.type] || '')+'</small></span>'+
    '<span class="muted">'+esc(job.characterName || '')+' · '+esc(job.status==='succeeded'?dateLabel(job.completedAt):statusNames[job.status] || '')+'</span></button>'
}
function works(ctx) {
  const {state,esc,icon}=ctx
  const filter = Object.hasOwn(typeNames,state.workFilter) ? state.workFilter : 'all'
  const jobs=(state.jobs || []).filter(j => filter==='all'||j.type===filter)
  return '<header class="page-heading"><div><h1>作品庫</h1></div>'+button('refresh',icon('refresh-cw',15)+' 重新整理','ghost')+'</header><div class="work-header"><div class="chips">'+Object.entries({all:'全部',...typeNames}).map(([v,t]) =>
    '<button type="button" class="chip '+(filter===v?'selected':'')+'" aria-pressed="'+(filter===v)+'" data-act="prod-filter" data-value="'+v+'">'+t+'</button>').join('')+'</div></div>'+
    (jobs.length ? '<div class="work-grid">'+jobs.map(j=>workCard(j,ctx)).join('')+'</div>' :
    '<div class="empty">'+icon('image',32)+'<h3>'+esc(filter==='all'?'還沒有作品':'還沒有'+typeNames[filter])+'</h3><p>生成的圖片、語音與影片會儲存在這裡。</p></div>')
}
export function production(panel,ctx) {
  if (panel==='works') return works(ctx)
  if (!ctx.state.draft) return '<div class="empty"><h3>請先選擇角色</h3></div>'
  return panel==='shoot' ? shoot(ctx) : perform(ctx)
}
function showWork(job,ctx) {
  const {esc,icon,modal}=ctx
  const url=imageUrl(job.url,esc)
  const download=(src,name) => '<a class="btn secondary" href="'+src+'" download>'+icon('download',16)+' '+name+'</a>'
  let media=''
  if (url) {
    if(job.type==='image') media='<img class="modal-media" src="'+url+'" alt="'+esc(job.title || '生成圖片')+'">'
    if(job.type==='video') media='<video class="modal-media" src="'+url+'" controls playsinline preload="metadata"></video>'
    if(job.type==='voice') media='<audio class="modal-media" src="'+url+'" controls preload="metadata"></audio>'
  }
  const actions=[]
  if(url) actions.push(download(url,'下載'+typeNames[job.type]))
  const audio=imageUrl(job.audioUrl,esc)
  if(audio && audio!==url) actions.push(download(audio,'下載配音'))
  if(audio && !media) media='<audio class="modal-media" src="'+audio+'" controls preload="metadata" aria-label="已合成的配音"></audio>'
  const role=ctx.state.characters.find(c=>c.id===job.characterId)
  if(job.type==='image' && url && role) {
    actions.push(button('reference','設為角色參考','secondary','data-id="'+esc(job.id)+'"'))
    actions.push(button('animate','用這張照片演出','primary','data-id="'+esc(job.id)+'"'))
  }
  if(job.status==='failed') actions.push(button('retry','以原設定重試','primary','data-id="'+esc(job.id)+'"'))
  modal(job.title || typeNames[job.type],'<div class="work-detail">'+media+
    '<p class="muted">'+esc(job.characterName || '')+' · '+esc(dateLabel(job.createdAt))+' · '+esc(statusNames[job.status] || '')+'</p>'+
    (job.error?'<p role="alert">'+esc(job.error)+'</p>':'')+(job.progress?'<p>'+esc(job.progress)+'</p>':'')+
    (!url && !job.error ? '<button class="btn ghost" data-act="prod-check" data-id="'+esc(job.id)+'">更新進度</button>':'')+
    '<div class="production-actions">'+actions.join('')+'</div></div>')
}
export function productionInput(el,ctx) {
  const d=ctx.state.draft
  if (el.dataset.voice && d) {
    if (!d.voice || typeof d.voice!=='object') d.voice={}
    if (d.voice[el.dataset.voice] !== el.value) {
      d.voice[el.dataset.voice] = el.value
      ctx.markDirty?.()
      if(el.dataset.voice==='provider')ctx.render()
    }
  }
  if ('prodRedraw' in el.dataset && d) {
    d.performancePhoto=el.value
    ctx.render()
  }
}
async function submit(type,ctx) {
  const {state}=ctx, d=state.draft
  const payload={type}
  if (type==='image') {
    Object.assign(payload,{prompt:d.prompt || '',view:d.view || viewNames[0],size:d.size || '1024x1536',
      shot:d.shot || shotNames[0],camera:d.camera || cameraNames[0],lighting:d.lighting || lights[0],style:d.style || styles[0]})
  } else {
    const v=typeof d.voice==='object' && d.voice ? d.voice : {}
    const trim=(v='') => String(v || '').trim()
    const provider=v.provider || d.provider || 'fish'
    Object.assign(payload,{text:trim(d.script),provider,voiceId:trim(v.id ?? v.voiceId ?? d.voiceId)})
    if(provider==='breeze')payload.voiceInstruction=trim(v.instruction ?? d.voiceInstruction)
    if(type==='video') {
      payload.imageUrl=d.performancePhoto || photoChoices(ctx)[0]?.url || ''
      payload.audioUrl=voiceChoices(ctx).some(v=>v.url===d.performanceAudio) ? d.performanceAudio : ''
      payload.performancePrompt=trim(d.performancePrompt)
      if(!payload.imageUrl) throw Error('請先選擇演出照片。')
    }
    if(!payload.text && !payload.audioUrl) throw Error('請先輸入台詞。')
  }
  const saved=await ctx.saveDraft()
  if (!saved?.id) return
  await ctx.api('/api/jobs',{method:'POST',body:{...payload,characterId:saved.id}})
  state.workFilter='all'
  await ctx.refresh()
  ctx.nav('works')
  ctx.toast('已排入'+typeNames[type]+'生成任務')
}
export async function productionAction(action,el,ctx) {
  if (!action.startsWith('prod-')) return false
  const {state}=ctx
  const op=action.slice(5)
  if(op==='scene'){ctx.selectAsset('scene');return true}
  if(op==='filter'){state.workFilter=el.dataset.value;ctx.render();return true}
  if(op==='work'){const job=state.jobs.find(j=>j.id===el.dataset.id);if(job)showWork(job,ctx);return true}
  if(op==='upload-photo'){
    const picker=document.createElement('input')
    picker.type='file';picker.accept='image/png,image/jpeg,image/webp'
    const draft=state.draft
    picker.onchange=async()=>{
      if(!picker.files[0]) return
      try {draft.performancePhoto=await ctx.upload(picker.files[0]);if(state.draft===draft)ctx.markDirty?.();ctx.render();ctx.toast('已選用上傳照片')}
      catch(e){ctx.toast(e.message)}
    }
    picker.click();return true
  }
  if (state.productionBusy) return true
  state.productionBusy=true
  el.disabled=true
  try {
    if(['image','voice','video'].includes(op)) await submit(op,ctx)
    else if(op==='prompt'){
      const d=state.draft
      const {prompt}=await ctx.api('/api/agent',{method:'POST',body:{mode:'prompt',brief:d.prompt || '',character:d,view:d.view || viewNames[0]}})
      d.prompt=prompt;if(state.draft===d)ctx.markDirty?.();ctx.render();ctx.toast('已更新提示詞，可繼續編輯')
    } else if(op==='refresh'){await ctx.refresh();ctx.render()}
    else if(op==='check'){
      await ctx.refresh()
      const j=state.jobs.find(j=>j.id===el.dataset.id)
      if(j)showWork(j,ctx)
    } else if(op==='retry'){
      await ctx.api('/api/jobs/'+encodeURIComponent(el.dataset.id)+'/retry',{method:'POST',body:{}})
      ctx.closeModal();await ctx.refresh();ctx.render();ctx.toast('已重新排入任務')
    } else if(op==='reference' || op==='animate'){
      const job=state.jobs.find(j=>j.id===el.dataset.id)
      if(!job)throw Error('找不到作品。')
      const {character}=await ctx.api('/api/characters/'+encodeURIComponent(job.characterId))
      if(op==='animate'){
        if(state.draft?.id===character.id){state.draft.performancePhoto=job.url;ctx.markDirty?.()}
        ctx.closeModal();await ctx.openEditor({...character,performancePhoto:job.url},'perform')
      } else {
        const refs=character.references || []
        if(!refs.some(r=>(typeof r==='string'?r:r.url)===job.url)){
          const {character:updated}=await ctx.api('/api/characters/'+encodeURIComponent(character.id),{method:'PUT',body:{
            updatedAt:character.updatedAt,references:[...refs,{url:job.url,label:job.input?.view || '定裝照'}]}})
          if(state.draft?.id===updated.id){state.draft.references=updated.references;state.draft.updatedAt=updated.updatedAt}
        }
        ctx.closeModal();await ctx.refresh();ctx.render();ctx.toast('已存入角色參考圖')
      }
    }
  } catch(e) { ctx.toast(e.message || '操作未完成，請再試一次。') }
  finally {state.productionBusy=false;el.disabled=false}
  return true
}
