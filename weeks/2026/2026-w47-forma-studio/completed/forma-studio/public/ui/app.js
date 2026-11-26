import { blank, templates, scenes } from './presets.js'
import { settingsView, settingsAction } from './settings.js'
import {
  libraryView,
  openPicker,
  libraryAction,
  libraryInput,
} from './library.js'
import { production, productionAction, productionInput } from './production.js'

const app = document.querySelector('#app')
const dialog = document.querySelector('#modal')
const es = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => es[ch])
const icon = (name, size = 18) =>
  `<svg class="icon" width="${Number(size) || 18}" height="${Number(size) || 18}" aria-hidden="true" viewBox="0 0 24 24"><use href="/ui/icons.svg#${esc(name)}"/></svg>`
const pages = {
  home: '角色工作室',
  library: '素材庫',
  works: '作品庫',
  settings: '服務設定',
  edit: '角色編輯',
}
const tabs = { profile: '角色設定', shoot: '攝影棚', perform: '聲音與表演' }
const copy = (value) => structuredClone(value)
const safeParse = (key, fallback, store = localStorage) => {
  try {
    return JSON.parse(store.getItem(key)) ?? fallback
  } catch {
    return fallback
  }
}
const state = {
  page: 'home',
  tab: 'profile',
  characters: [],
  jobs: [],
  settings: {},
  catalog: { faces: [], outfits: [], poses: [], scenes },
  draft: null,
  homeFilter: 'all',
  homeQuery: '',
  favorites: new Set(safeParse('forma-stars', [])),
  dirty: false,
  workFilter: 'all',
  ready: false,
}
const ctx = {
  state,
  api,
  render,
  toast,
  modal,
  closeModal,
  saveDraft,
  icon,
  esc,
  nav,
  refresh,
  openEditor,
  selectAsset,
  applyAsset,
  upload,
  markDirty,
  get settings() {
    return state.settings
  },
}
let noticeTimer, pending, saving, lastFocus, agentSuggestion, pendingFace
const cached = safeParse('forma-editor', null, sessionStorage)
if (cached?.draft) {
  state.draft = cached.draft
  state.dirty = Boolean(cached.dirty)
}
function remember() {
  if (state.draft)
    sessionStorage.setItem(
      'forma-editor',
      JSON.stringify({ draft: state.draft, dirty: state.dirty }),
    )
  else sessionStorage.removeItem('forma-editor')
}
async function api(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.error || '無法完成操作，請重新再試。')
    error.status = response.status
    throw error
  }
  return data
}
async function refresh() {
  const [characters, jobs, settings] = await Promise.all([
    api('/api/characters'),
    api('/api/jobs'),
    api('/api/settings'),
  ])
  Object.assign(state, {
    characters: characters.characters,
    jobs: jobs.jobs,
    settings: settings.settings,
  })
}
function toast(message) {
  const notice = document.querySelector('#notice')
  if (dialog.open) {
    let feedback = dialog.querySelector('.dialog-feedback')
    if (!feedback) {
      feedback = document.createElement('p')
      feedback.className = 'dialog-feedback'
      feedback.setAttribute('role', 'status')
      dialog.prepend(feedback)
    }
    feedback.textContent = message
  }
  notice.textContent = message
  notice.classList.add('show')
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => notice.classList.remove('show'), 4200)
}
function closeModal() {
  if (dialog.open) dialog.close()
}
function modal(title, body, size = '') {
  if (!dialog.open) lastFocus = document.activeElement
  dialog.className = size === 'wide' ? 'wide' : ''
  dialog.innerHTML = `<div class="dialog-bar"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-btn" data-act="close" aria-label="關閉視窗">${icon('x')}</button></div><div class="dialog-content">${body}</div>`
  if (!dialog.open) dialog.showModal()
}
dialog.addEventListener('close', () => {
  if (lastFocus?.isConnected) lastFocus.focus({ preventScroll: true })
})
dialog.addEventListener('click', (event) => {
  if (event.target === dialog) {
    const r = dialog.getBoundingClientRect()
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      closeModal()
  }
})
function markDirty() {
  state.dirty = true
  remember()
}
function nav(page, tab) {
  page = Object.hasOwn(pages, page) ? page : 'home'
  if (page === 'edit' && !state.draft) {
    state.draft = blank()
    remember()
  }
  if (tab && Object.hasOwn(tabs, tab)) state.tab = tab
  state.page = page
  closeModal()
  const path =
    page === 'edit'
      ? ['edit', state.draft.id || 'new', state.tab].join('/')
      : page
  if (location.hash !== '#' + path) history.pushState(null, '', '#' + path)
  render()
  window.scrollTo({ top: 0, behavior: 'instant' })
}
function applyRoute() {
  const [page, id, tab] = location.hash.slice(1).split('/')
  state.page = Object.hasOwn(pages, page) ? page : 'home'
  if (state.page === 'edit') {
    if (id === 'new' && state.draft?.id) {
      state.draft = blank()
      state.dirty = false
      remember()
    }
    if (id && id !== 'new' && (state.draft?.id !== id || !state.dirty)) {
      const match = state.characters.find((c) => c.id === id)
      if (match) {
        state.draft = copy(match)
        state.dirty = false
      } else state.page = 'home'
    }
    if (!state.draft) state.draft = blank()
    state.tab = Object.hasOwn(tabs, tab) ? tab : 'profile'
  }
  closeModal()
  render()
}
window.addEventListener('popstate', applyRoute)
function openEditor(item, tab = 'profile', force = false) {
  if (
    state.dirty &&
    state.draft &&
    !force &&
    !(item?.id && item.id === state.draft.id)
  ) {
    pending = () => openEditor(item, tab, true)
    return modal(
      '開啟另一個角色？',
      `<p>目前角色還有待儲存的修改。</p><div class="actions"><button class="btn secondary" data-act="close">繼續編輯</button><button class="btn primary" data-act="discard">捨棄修改並開啟</button></div>`,
    )
  }
  if (!(item?.id && item.id === state.draft?.id && state.dirty)) {
    state.draft = copy(item || blank())
    state.dirty = Boolean(item && !item.id)
    if (state.draft.key) {
      state.draft.templateKey = state.draft.key
      delete state.draft.key
    }
  }
  remember()
  nav('edit', tab)
}
async function saveDraft() {
  const draft = state.draft
  if (saving) {
    if (saving.draft === draft) return saving.promise
    await saving.promise.catch(() => {})
    if (state.draft !== draft)
      throw new Error('角色已切換，請重新確認要儲存的設定。')
    return saveDraft()
  }
  if (!draft?.name?.trim()) throw new Error('請先幫角色取一個名字。')
  const snapshot = copy(draft)
  const promise = (async () => {
    const route = '/api/characters' + (snapshot.id ? '/' + encodeURIComponent(snapshot.id) : '')
    let character
    try {
      const result = await api(route, { method: snapshot.id ? 'PUT' : 'POST', body: snapshot })
      character = result.character
    } catch (error) {
      if (snapshot.id && state.draft === draft && [404, 409].includes(error.status)) {
        modal(error.status === 409 ? '角色已在另一個頁面更新' : '原角色已刪除',
          `<p>可以將目前編輯的內容另存為新角色。</p><div class="actions"><button class="btn secondary" data-act="close">繼續編輯</button>${error.status === 409 ? '<button class="btn secondary" data-act="reload-role">載入最新版本</button>' : ''}<button class="btn primary" data-act="duplicate">另存副本</button></div>`)
        return null
      }
      throw error
    }
    state.characters = [
      character,
      ...state.characters.filter((c) => c.id !== character.id),
    ]
    if (state.draft === draft) {
      const changed = JSON.stringify(draft) !== JSON.stringify(snapshot)
      Object.assign(
        draft,
        changed
          ? {
              id: character.id,
              updatedAt: character.updatedAt,
              createdAt: character.createdAt,
            }
          : character,
      )
      state.dirty = changed
      remember()
      if (state.page === 'edit')
        history.replaceState(
          null,
          '',
          '#edit/' + character.id + '/' + state.tab,
        )
    }
    return character
  })().finally(() => {
    saving = null
  })
  saving = { draft, promise }
  return promise
}
function upload(file) {
  if (!file || file.size > 20 * 1024 * 1024)
    return Promise.reject(new Error('請選擇 20 MB 以內的圖片。'))
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('無法讀取選取的圖片。'))
    reader.onload = () =>
      api('/api/uploads', {
        method: 'POST',
        body: { dataUrl: reader.result },
      }).then((data) => resolve(data.url), reject)
    reader.readAsDataURL(file)
  })
}
function selectAsset(type) {
  openPicker(type, ctx)
}
function setAsset(type, item) {
  const d = state.draft
  if (type === 'scene') {
    d.scene = item.name
    d.sceneAsset = copy(item)
  } else d[type] = copy(item)
  if (type === 'face') {
    d.cover = item.image
    d.references = []
    d.performancePhoto = ''
  }
  markDirty()
  render()
}
function applyAsset(type, item, options = {}) {
  if (options.newCharacter || !state.draft || state.page === 'library') {
    const d = blank()
    if (type === 'scene') {
      d.scene = item.name
      d.sceneAsset = item
    } else d[type] = item
    if (type === 'face') d.cover = item.image
    return openEditor(d, type === 'scene' ? 'shoot' : 'profile')
  }
  if (type === 'face' && state.draft.references?.length) {
    pendingFace = item
    return modal(
      '更換角色臉部',
      `<p>這個角色有 ${state.draft.references.length} 張原人物參考照。更換臉部會一併移除這些參考，之後可重新加入新人物的視圖。</p><div class="actions"><button class="btn secondary" data-act="close">保留原臉</button><button class="btn primary" data-act="replace-face">更換臉部</button></div>`,
    )
  }
  setAsset(type, item)
}
function navItem(page, name, glyph) {
  const active =
    state.page === page || (page === 'home' && state.page === 'edit')
  return `<button class="nav-item ${active ? 'active' : ''}" aria-label="${name}" ${active ? 'aria-current="page"' : ''} data-act="nav" data-page="${page}">${icon(glyph, 19)}<span>${name}</span></button>`
}
function shell(content) {
  const place = pages[state.page]
  return `<aside class="rail" aria-label="主導覽"><button class="brand" data-act="nav" data-page="home" aria-label="Forma Studio 首頁"><img src="/ui/mark.svg" alt=""><span>Forma<span class="brand-studio"> Studio</span></span></button>
 <div class="rail-inner"><div class="nav-caption">工作空間</div><nav>${navItem('home', '角色工作室', 'contact-round')}${navItem('library', '素材庫', 'layers-3')}${navItem('works', '作品庫', 'images')}</nav></div>
 <div class="rail-bottom">${navItem('settings', '服務設定', 'settings-2')}<div class="local-profile"><span class="profile-avatar">${icon('monitor', 17)}</span><span><b>本機工作空間</b><small><i class="online-dot"></i>本機服務已連線</small></span></div></div></aside>
 <div class="stage"><div class="topbar"><span>${icon('panels-top-left', 15)}<span>工作空間</span><i>/</i><b>${place}</b></span><button class="top-gear icon-btn" data-act="nav" data-page="settings" aria-label="服務設定">${icon('settings-2')}</button><span class="studio-label"><i class="online-dot"></i> 本機模式</span></div>
 <main id="main" tabindex="-1" class="content ${state.page}-content">${content}</main></div>`
}
const filterMap = { all: '全部角色', mine: '我的角色', stars: '已收藏' }
const hero = templates.find((c) => c.key === 'sora')
function card(item) {
  const key = item.id || item.key,
    star = state.favorites.has(key),
    src = item.cover || item.face?.image || item.references?.[0]?.url
  return `<article class="char-card"><button class="card-open" data-act="character" data-id="${esc(key)}"><span class="card-photo">${src ? `<img src="${esc(src)}" alt="${esc(item.name)} 的角色形象" loading="lazy">` : `<span class="blank-face">${icon('contact-round', 46)}</span>`}</span><span class="card-title">${esc(item.name)}${item.alias ? `<span class="card-alias">${esc(item.alias)}</span>` : ''}</span><span class="card-info"><span>${esc(item.style || '自訂角色')}</span><i></i><span>${esc(item.role || item.description || '個人角色')}</span></span></button><button class="star ${star ? 'starred' : ''}" aria-label="${star ? '取消收藏' : '收藏'} ${esc(item.name)}" aria-pressed="${star}" data-act="star" data-id="${esc(key)}">${icon('bookmark', 16)}</button></article>`
}
function homeResults() {
  const q = state.homeQuery.trim().toLowerCase()
  const list = [...state.characters, ...templates].filter(
    (c) =>
      (state.homeFilter !== 'mine' || c.id) &&
      (state.homeFilter !== 'stars' || state.favorites.has(c.id || c.key)) &&
      (!q ||
        [c.name, c.alias, c.style, c.role, c.description].some((v) =>
          String(v || '')
            .toLowerCase()
            .includes(q),
        )),
  )
  return list.length
    ? `<div class="character-grid">${list.map(card).join('')}</div>`
    : `<div class="empty">${icon(state.homeFilter === 'stars' ? 'bookmark' : 'user-round', 30)}<h3>${q ? '找不到符合的角色' : state.homeFilter === 'stars' ? '還沒有收藏的角色' : '還沒有自己的角色'}</h3><p>${q ? '試試其他名稱或風格。' : state.homeFilter === 'stars' ? '點角色照片上的書籤，即可在這裡快速找到。' : '從空白角色開始，或挑選一個範本來編輯。'}</p>${!q && state.homeFilter === 'mine' ? '<button class="btn primary" data-act="new">建立角色</button>' : ''}</div>`
}
function home() {
  return `<header class="page-heading"><div><h1>角色工作室</h1><p>管理角色設定、定裝照與演出。</p></div><div class="heading-actions">${state.dirty ? '<button class="btn secondary" data-act="resume">繼續編輯草稿</button>' : ''}<button class="btn primary" data-act="new">${icon('plus', 17)} 建立角色</button></div></header>
 <section class="spotlight" aria-label="精選角色 Sora"><img class="hero-photo" src="/art/sora-hero.webp" alt="Sora 穿深色西裝，在赤陶色攝影棚中面向鏡頭" fetchpriority="high"><div class="hero-content"><span class="hero-kicker">${icon('sparkles', 14)} 精選角色範本</span><h2>Sora<span>空</span></h2><p>都會時裝 <i></i> 暖調棚拍</p><button class="hero-button" data-act="character" data-id="sora">使用範本 ${icon('arrow-up-right', 16)}</button></div><div class="camera-data" title="範本鏡頭與光圈">${icon('aperture', 15)} 85 mm <i></i> ƒ/2.8</div></section>
 <section class="collection"><div class="collection-head"><h2>角色庫 <span>${state.characters.length + templates.length}</span></h2><label class="search-box">${icon('search', 16)}<input id="home-search" type="search" value="${esc(state.homeQuery)}" placeholder="搜尋角色" aria-label="搜尋角色"></label></div>
 <div class="chips home-chips">${Object.entries(filterMap)
   .map(
     ([key, label]) =>
       `<button data-act="home-filter" data-id="${key}" aria-pressed="${state.homeFilter === key}" class="chip ${key === state.homeFilter ? 'selected' : ''}">${label}</button>`,
   )
   .join('')}</div><div id="home-results">${homeResults()}</div></section>`
}
function field(key, label, placeholder = '', multiline = false) {
  const d = state.draft
  return `<label class="field"><span>${label}</span>${multiline ? `<textarea rows="3" data-field="${key}" placeholder="${esc(placeholder)}">${esc(d[key])}</textarea>` : `<input data-field="${key}" value="${esc(d[key])}" placeholder="${esc(placeholder)}" ${key === 'name' ? 'maxlength="120" required' : ''}>`}</label>`
}
function profile() {
  const d = state.draft,
    src = d.cover || d.face?.image || d.references?.[0]?.url
  const assets = [
    ['face', '臉部', 'scan-face'],
    ['outfit', '服裝', 'shirt'],
    ['pose', '姿勢', 'accessibility'],
  ]
  const refList = (d.references || [])
    .map(
      (r, i) =>
        `<div class="ref-item"><img src="${esc(r.url)}" alt="${esc(r.label)}"><span>${esc(r.label)}</span><button class="icon-btn" data-act="remove-ref" data-index="${i}" aria-label="移除${esc(r.label)}">${icon('x', 15)}</button></div>`,
    )
    .join('')
  return `<div class="editor-layout"><div class="portrait-column"><div class="portrait-preview">${src ? `<img src="${esc(src)}" alt="角色形象參考">` : `<div class="portrait-placeholder">${icon('scan-face', 48)}<p>選擇第一張角色臉孔</p></div>`}</div>
 <button class="btn secondary full" data-act="choose" data-type="face">${icon('contact-round', 17)} 選擇臉部參考</button>
 <div class="reference-list"><div class="small-heading"><h3>角色視圖</h3><button class="icon-btn" data-act="add-ref" aria-label="加入角色視圖">${icon('plus', 17)}</button></div>${refList || '<p class="muted small">加入正面、側面或全身照，供下次生成時參考。</p>'}</div></div>
 <div class="editor-form"><section class="panel"><div class="panel-head"><h2>人物設定</h2><button class="btn secondary compact" data-act="agent">${icon('sparkles', 15)} Agent 訂製</button></div><div class="field-grid">${field('name', '角色名稱', '替你的角色取名')}${field('age', '年齡設定', '例如 28 歲')}${field('description', '角色背景', '職業、故事或內容定位', true)}${field('personality', '個性與說話方式', '例如 溫和、好奇，說話簡潔', true)}</div></section>
 <section class="panel"><h2>外觀與造型</h2><div class="asset-rows">${assets
   .map(([key, label, glyph]) => {
     const item = d[key]
     return `<div class="asset-row-group"><button class="asset-row" data-act="choose" data-type="${key}"><span class="mini-thumb">${item?.image ? `<img src="${esc(item.image)}" alt="">` : icon(glyph, 20)}</span><span><strong>${label}</strong><small>${esc(item?.name || (key === 'face' && src ? '角色形象參考' : '選擇素材'))}</small></span>${icon('chevron-right', 16)}</button>${item && key !== 'face' ? `<button class="icon-btn" data-act="clear-asset" data-type="${key}" aria-label="移除${label}參考">${icon('x', 15)}</button>` : ''}</div>`
   })
   .join(
     '',
   )}</div><div class="field-grid">${field('hair', '髮型', '例如 深色短髮')}${field('makeup', '妝容', '例如 自然霧面妝')}${field('body', '身材', '例如 修長、肩線挺直')}${field('proportions', '身體比例', '例如 七頭身')}</div></section>
 ${d.id ? '<button class="text-danger" data-act="ask-delete">刪除這個角色</button>' : ''}</div></div>`
}
function editor() {
  const d = state.draft
  return `<header class="page-heading editor-heading"><div><button class="back-link" data-act="nav" data-page="home">${icon('arrow-left', 14)} 角色庫</button><h1>${esc(d.name || '建立角色')}</h1></div><div class="heading-actions">${d.id ? '<button class="btn secondary" data-act="duplicate">另存副本</button>' : ''}<button class="btn primary" data-act="save">${icon('check', 17)} 儲存角色</button></div></header><div class="workspace-tabs">${Object.entries(
    tabs,
  )
    .map(
      ([key, label]) =>
        `<button class="${key === state.tab ? 'selected' : ''}" data-act="tab" data-id="${key}">${icon({ profile: 'contact-round', shoot: 'camera', perform: 'audio-lines' }[key], 17)} ${label}</button>`,
    )
    .join(
      '',
    )}</div>${state.tab === 'profile' ? profile() : production(state.tab, ctx)}`
}
function render() {
  if (!state.ready) return
  let view
  if (state.page === 'home') view = home()
  if (state.page === 'edit') view = editor()
  if (state.page === 'library') view = libraryView(ctx)
  if (state.page === 'works') view = production('works', ctx)
  if (state.page === 'settings')
    view =
      settingsView(ctx) +
      (state.draft
        ? `<button class="back-link" data-act="resume">${icon('arrow-left', 15)} 返回角色編輯</button>`
        : '')
  document.title = pages[state.page] + ' · Forma Studio'
  app.innerHTML = shell(view)
}
function agentForm() {
  if (!state.settings.openaiKeySet)
    return modal(
      'Agent 訂製角色',
      `<p>先連接 OpenAI，Agent 就能依你的描述建立可編輯的角色草稿。</p><div class="actions"><button class="btn primary" data-act="nav" data-page="settings">前往服務設定 ${icon('arrow-right', 16)}</button></div>`,
    )
  modal(
    'Agent 訂製角色',
    `<label class="field"><span>你想要什麼樣的角色？</span><textarea id="agent-brief" rows="4" placeholder="例如 一位熟悉台北巷弄的攝影師，擅長用輕鬆的語氣分享故事"></textarea></label><div class="actions"><button class="btn primary" data-act="agent-submit">${icon('sparkles', 16)} 產生草稿</button></div>`,
  )
}
async function handle(action, el) {
  if (action.startsWith('lib-')) return libraryAction(action, el, ctx)
  if (action.startsWith('prod-')) return productionAction(action, el, ctx)
  if (action.startsWith('settings-')) return settingsAction(action, el, ctx)
  switch (action) {
    case 'nav':
      return nav(el.dataset.page)
    case 'resume':
      return nav('edit')
    case 'close':
      return closeModal()
    case 'discard': {
      const run = pending
      pending = null
      closeModal()
      return run?.()
    }
    case 'new':
      return openEditor(null)
    case 'character':
      return openEditor(
        [...state.characters, ...templates].find(
          (c) => (c.id || c.key) === el.dataset.id,
        ),
      )
    case 'tab':
      return nav('edit', el.dataset.id)
    case 'star': {
      const k = el.dataset.id
      if (state.favorites.has(k)) state.favorites.delete(k)
      else state.favorites.add(k)
      localStorage.setItem('forma-stars', JSON.stringify([...state.favorites]))
      render()
      return
    }
    case 'home-filter':
      state.homeFilter = el.dataset.id
      return render()
    case 'save':
      if (!await saveDraft()) return
      render()
      toast('角色已儲存')
      return
    case 'reload-role': {
      const { character } = await api('/api/characters/' + encodeURIComponent(state.draft.id))
      state.characters = [character, ...state.characters.filter(item => item.id !== character.id)]
      state.draft = copy(character)
      state.dirty = false
      remember()
      nav('edit', state.tab)
      return
    }
    case 'duplicate':
      return modal(
        '另存角色副本',
        `<label class="field"><span>新角色名稱</span><input id="copy-name" maxlength="120" value="${esc(state.draft.name + ' · 新造型')}"></label><p class="small">包含目前的角色設定、視圖與選用素材。</p><div class="actions"><button class="btn secondary" data-act="close">取消</button><button class="btn primary" data-act="save-copy">儲存副本</button></div>`,
      )
    case 'save-copy': {
      const name = document.querySelector('#copy-name').value.trim()
      if (!name) throw new Error('請填寫新角色名稱。')
      const { id, createdAt, updatedAt, ...configuration } = state.draft
      const { character } = await api('/api/characters', {
        method: 'POST',
        body: { ...configuration, name },
      })
      state.characters = [character, ...state.characters]
      state.draft = copy(character)
      state.dirty = false
      remember()
      nav('edit', state.tab)
      toast('已另存角色副本')
      return
    }
    case 'choose':
      return selectAsset(el.dataset.type)
    case 'clear-asset':
      if (['outfit', 'pose'].includes(el.dataset.type)) {
        state.draft[el.dataset.type] = null
        markDirty()
        render()
      }
      return
    case 'replace-face':
      closeModal()
      setAsset('face', pendingFace)
      pendingFace = null
      return
    case 'remove-ref': {
      const [removed] = state.draft.references.splice(
        Number(el.dataset.index),
        1,
      )
      if (removed?.url === state.draft.cover)
        state.draft.cover =
          state.draft.references[0]?.url || state.draft.face?.image || ''
      markDirty()
      return render()
    }
    case 'add-ref':
      return modal(
        '加入角色視圖',
        `<label class="field"><span>視圖類型</span><select id="ref-label"><option>正面</option><option>側面</option><option>背面</option><option>全身</option><option>三視圖</option><option>細節參考</option></select></label><label class="field"><span>圖片</span><input id="ref-file" type="file" accept="image/png,image/jpeg,image/webp"></label><div class="actions"><button class="btn primary" data-act="upload-ref">加入視圖</button></div>`,
      )
    case 'upload-ref': {
      const file = document.querySelector('#ref-file').files[0],
        label = document.querySelector('#ref-label').value
      if (!file) throw new Error('請選擇要加入的圖片。')
      if ((state.draft.references?.length || 0) >= 16)
        throw new Error('每個角色最多可加入 16 張參考圖。')
      const url = await upload(file)
      ;(state.draft.references ??= []).push({ label, url })
      state.draft.cover ||= url
      markDirty()
      closeModal()
      render()
      return
    }
    case 'agent':
      return agentForm()
    case 'agent-submit': {
      const field = document.querySelector('#agent-brief'),
        brief = field.value.trim(),
        current = state.draft
      if (!brief) throw new Error('請先描述你想建立的角色。')
      const { draft } = await api('/api/agent', {
        method: 'POST',
        body: { brief, character: state.draft },
      })
      if (state.draft !== current || !dialog.open || !field.isConnected) return
      const changesIdentity =
        draft.face &&
        draft.face.id !== state.draft.face?.id &&
        (state.draft.cover || state.draft.references?.length)
      agentSuggestion = draft
      return modal(
        '檢視角色草稿',
        `<div class="draft-summary">${[
          ['名稱', 'name'],
          ['背景', 'description'],
          ['個性', 'personality'],
          ['妝容', 'makeup'],
          ['場景', 'scene'],
          ['風格', 'style'],
          ['臉部', 'face'],
          ['服裝', 'outfit'],
          ['姿勢', 'pose'],
        ]
          .map(
            ([label, key]) =>
              `<div><b>${label}</b><span>${esc(draft[key]?.name || draft[key] || '未指定')}</span></div>`,
          )
          .join(
            '',
          )}</div>${changesIdentity ? '<label class="settings-switch"><input type="checkbox" id="use-agent-face"> 用建議臉孔取代現有角色與視圖</label>' : ''}<div class="actions"><button class="btn secondary" data-act="close">取消</button><button class="btn primary" data-act="agent-apply">套用草稿</button></div>`,
      )
    }
    case 'agent-apply': {
      const draft = state.draft,
        choice = document.querySelector('#use-agent-face')
      if (choice && !choice.checked) agentSuggestion.face = draft.face
      const picked = agentSuggestion.face
      if (picked && picked.id !== draft.face?.id) {
        draft.cover = picked.image
        draft.references = []
        draft.performancePhoto = ''
      }
      if (agentSuggestion.scene !== draft.scene)
        draft.sceneAsset =
          scenes.find((s) => s.name === agentSuggestion.scene) || null
      Object.assign(draft, agentSuggestion)
      markDirty()
      agentSuggestion = null
      closeModal()
      render()
      toast('已套用，可繼續手動調整')
      return
    }
    case 'ask-delete':
      return modal(
        '刪除角色？',
        `<p>將從角色庫刪除「${esc(state.draft.name)}」。已生成的作品會保留在作品庫。</p><div class="actions"><button class="btn secondary" data-act="close">取消</button><button class="btn danger" data-act="delete">刪除角色</button></div>`,
      )
    case 'delete': {
      await api('/api/characters/' + state.draft.id, { method: 'DELETE' })
      state.draft = null
      state.dirty = false
      remember()
      await refresh()
      nav('home')
      toast('已刪除角色')
      return
    }
  }
}
document.addEventListener('click', async (e) => {
  const el = e.target.closest('[data-act]')
  if (!el || el.disabled || el.dataset.busy) return
  e.preventDefault()
  const action = el.dataset.act
  const blocking = [
    'save',
    'save-copy',
    'upload-ref',
    'agent-submit',
    'delete',
  ].includes(action)
  if (blocking) {
    el.disabled = true
    el.setAttribute('aria-busy', 'true')
  }
  el.dataset.busy = '1'
  try {
    await handle(action, el)
  } catch (error) {
    toast(error.message || '無法完成操作')
  } finally {
    delete el.dataset.busy
    if (blocking) {
      el.disabled = false
      el.removeAttribute('aria-busy')
    }
  }
})
function changed(e) {
  const el = e.target
  if (el.dataset.field && state.draft) {
    if (state.draft[el.dataset.field] !== el.value) {
      state.draft[el.dataset.field] = el.value
      markDirty()
    }
  }
  if (el.id === 'home-search') {
    state.homeQuery = el.value
    document.querySelector('#home-results').innerHTML = homeResults()
    return
  }
  libraryInput(el, ctx)
  if (state.page === 'edit' || state.page === 'works')
    productionInput?.(el, ctx)
}
document.addEventListener('input', changed)
document.addEventListener('change', changed)
async function boot() {
  try {
    const [, catalog] = await Promise.all([
      refresh(),
      api('/catalog/index.json'),
    ])
    state.catalog = { ...catalog, scenes }
    state.ready = true
    applyRoute()
  } catch (e) {
    app.innerHTML = `<main class="loading"><h1>無法開啟工作室</h1><p>${esc(e.message)}</p><a href="/">重新載入</a></main>`
    return
  }
  let polling = false
  setInterval(async () => {
    if (
      polling ||
      !state.jobs.some((j) => ['queued', 'running'].includes(j.status))
    )
      return
    polling = true
    try {
      const old = state.jobs
      state.jobs = (await api('/api/jobs')).jobs
      for (const job of state.jobs) {
        if (
          old.some(
            (j) => j.id === job.id && ['queued', 'running'].includes(j.status),
          ) &&
          ['succeeded', 'failed'].includes(job.status)
        )
          toast(job.status === 'failed' ? job.error : job.title + '已完成')
      }
      if (state.page === 'works' && !dialog.open) render()
    } catch {
    } finally {
      polling = false
    }
  }, 2200)
}
boot()
