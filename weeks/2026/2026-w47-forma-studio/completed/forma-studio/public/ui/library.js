const kinds = {
  face: { key: 'faces', title: '臉孔', search: '搜尋髮型、髮長或編號', filter: '所有髮長' },
  outfit: { key: 'outfits', title: '服裝', search: '搜尋單品、顏色或編號', filter: '所有系列' },
  pose: { key: 'poses', title: '姿勢', search: '搜尋動作、視角或編號', filter: '所有姿勢' },
  scene: { key: 'scenes', title: '場景', search: '搜尋場景或環境', filter: '所有場景' },
}
const licenses = {
  face: ['學員版包含工作室的虛構角色範本。也可以從角色編輯器上傳自備的已授權人像。', '', ''],
  outfit: ['學員版不附第三方服裝圖。可從角色編輯器上傳自備的已授權參考圖。', '', ''],
  pose: ['學員版不附第三方姿勢圖。可從角色編輯器上傳自備的已授權參考圖。', '', ''],
  scene: ['工作室自製場景參考圖。', '', ''],
}
const PAGE_SIZE = 24
const number = new Intl.NumberFormat('zh-TW')
const initial = (type) => ({ type, query: '', group: '', local: false, page: 1 })
let browser = initial('face')
let picker = initial('face')

function records(ctx, type) {
  return ctx.state.catalog?.[kinds[type].key] || []
}

function filters(scope) {
  return scope === 'picker' ? picker : browser
}

function local(item) {
  return item.image.startsWith('/') && item.reference.startsWith('/')
}

function normalize(text) {
  return String(text).normalize('NFKC').toLocaleLowerCase('zh-TW')
}

function results(ctx, options) {
  const tokens = normalize(options.query).trim().split(/\s+/u).filter(Boolean)
  return records(ctx, options.type).filter(item => {
    if (options.group && item.group !== options.group) return false
    if (options.local && !local(item)) return false
    if (!tokens.length) return true
    const terms = normalize([item.id, item.name, item.description || '', ...(item.tags || [])].join(' '))
    return tokens.every(token => terms.includes(token))
  })
}

function usage(type) {
  const [text, label, link] = licenses[type]
  return `<details class="lib-rights"><summary>素材來源與使用</summary><p>${text} ${link ? `<a href="${link}" target="_blank" rel="noreferrer">${label} ↗</a>` : ''}</p></details>`
}

function selectedId(ctx, type) {
  const draft = ctx.state.draft
  const current = draft?.[type + 'Asset'] || draft?.[type]
  return current?.id || ''
}

function cards(ctx, scope) {
  const { esc } = ctx
  const options = filters(scope)
  const { type } = options
  const matches = results(ctx, options)
  const pages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE))
  options.page = Math.min(options.page, pages)
  const first = (options.page - 1) * PAGE_SIZE
  const visible = matches.slice(first, first + PAGE_SIZE)
  const chosen = scope === 'picker' && selectedId(ctx, type)
  const count = `<p class="lib-count" role="status">${number.format(matches.length)} 個${kinds[type].title}</p>`
  const grid = visible.map(item => {
    const isSelected = item.id === chosen
    const tags = (item.tags || []).filter(tag => tag !== item.name && tag.length < 12)
    const classification = type === 'pose' ? item.group : tags.slice(0, type === 'outfit' ? 1 : 2).join(' · ')
    return `<button type="button" class="asset-card lib-card${isSelected ? ' is-chosen' : ''}" data-act="lib-item" data-id="${esc(item.id)}" aria-label="${esc(item.name)}${isSelected ? '，目前已選' : ''}">
      <span class="lib-photo lib-photo-${type}"><img src="${esc(item.image)}" alt="" loading="lazy" decoding="async" width="300" height="360" referrerpolicy="no-referrer">${isSelected ? '<span class="lib-selected">已選</span>' : ''}</span>
      <span class="lib-name">${esc(item.name)}</span><span class="lib-caption">${esc(classification)}</span>
    </button>`
  }).join('')
  const empty = records(ctx, type).length === 0
    ? `<div class="lib-empty"><strong>學員版未附${kinds[type].title}參考圖</strong><p>可在角色編輯器選擇「上傳自備圖片」。</p></div>`
    : `<div class="lib-empty"><strong>找不到符合條件的${kinds[type].title}</strong><button type="button" class="lib-text-btn" data-act="lib-reset">清除搜尋條件</button></div>`
  const navigation = pages > 1 ? `<nav class="lib-pager" aria-label="素材分頁">
    <button type="button" class="lib-arrow" aria-label="上一頁" data-act="lib-prev" ${options.page === 1 ? 'disabled' : ''}>‹</button>
    <span>第 ${options.page} 頁 / 共 ${pages} 頁</span>
    <button type="button" class="lib-arrow" aria-label="下一頁" data-act="lib-next" ${options.page === pages ? 'disabled' : ''}>›</button></nav>` : ''
  return `${count}${visible.length ? `<div class="catalog-grid lib-grid">${grid}</div>` : empty}${navigation}${usage(type)}`
}

function controls(ctx, scope) {
  const { esc } = ctx
  const options = filters(scope)
  const labels = kinds[options.type]
  const groups = [...new Set(records(ctx, options.type).map(item => item.group).filter(Boolean))]
  return `<div class="lib-controls">
    <label class="lib-search"><span aria-hidden="true" class="lib-loupe"></span>
      <input type="search" aria-label="搜尋${labels.title}" data-lib-input="query" placeholder="${labels.search}" value="${esc(options.query)}" autocomplete="off">
    </label>
    <select class="lib-select" aria-label="篩選${labels.title}分類" data-lib-input="group">
      <option value="">${labels.filter}</option>${groups.map(group => `<option value="${esc(group)}" ${group === options.group ? 'selected' : ''}>${esc(group)}</option>`).join('')}
    </select>
    ${options.type === 'scene' ? '' : `<label class="lib-local"><input type="checkbox" data-lib-input="local" ${options.local ? 'checked' : ''}> 僅看本機</label>`}
    ${scope === 'picker' ? '<button class="lib-upload-link" data-act="lib-upload" type="button">上傳自備圖片</button>' : ''}
    </div>`
}

function body(ctx, scope) {
  const { type } = filters(scope)
  const tabs = scope === 'page' ? `<nav class="lib-tabs" aria-label="素材類型">${Object.entries(kinds).map(([key, value]) =>
    `<button type="button" class="lib-tab" data-act="lib-type" data-type="${key}" aria-pressed="${type === key}">${value.title}</button>`).join('')}</nav>` : ''
  return `${tabs}${controls(ctx, scope)}<div data-lib-results>${cards(ctx, scope)}</div>`
}

export function libraryView(ctx) {
  return `<section class="library-page"><header class="lib-heading"><h1>素材庫</h1></header>
    <div class="lib-surface" data-lib-scope="page">${body(ctx, 'page')}</div></section>`
}

export function openPicker(type, ctx) {
  if (!Object.hasOwn(kinds, type)) return
  picker = initial(type)
  showPicker(ctx)
}

function showPicker(ctx) {
  ctx.modal('選擇' + kinds[picker.type].title, `<div class="lib-surface lib-picker" data-lib-scope="picker">${body(ctx, 'picker')}</div>`, 'wide')
}

function uploadView(type, ctx) {
  const label = kinds[type].title
  ctx.modal('上傳自備' + label, `<div class="lib-upload-form" data-upload-type="${type}">
    <label class="field"><span>參考圖片</span><input type="file" data-lib-file accept="image/png,image/jpeg,image/webp"><small>PNG、JPG 或 WebP，最大 20 MB。</small></label>
    <label class="field"><span>素材名稱</span><input type="text" data-lib-name maxlength="100" placeholder="替這張${label}命名"></label>
    <p class="lib-upload-error" role="alert"></p>
    <div class="actions"><button class="btn secondary" type="button" data-act="lib-upload-back">返回素材庫</button>
    <button class="btn primary" type="button" data-act="lib-upload-submit">上傳並套用</button></div></div>`)
}

async function uploadSelection(form, ctx) {
  if (form.dataset.uploading) return
  const fileInput = form.querySelector('[data-lib-file]')
  const nameInput = form.querySelector('[data-lib-name]')
  const message = form.querySelector('[role="alert"]')
  const file = fileInput.files[0]
  const name = nameInput.value.trim()
  if (!file || !name) {
    message.textContent = file ? '請輸入素材名稱。' : '請選擇要上傳的圖片。'
    const field = file ? nameInput : fileInput
    field.focus()
    return
  }
  const { uploadType: type } = form.dataset
  const draft = ctx.state.draft
  const button = form.querySelector('[data-act="lib-upload-submit"]')
  const controls = [...form.querySelectorAll('button, input')]
  message.textContent = ''
  form.dataset.uploading = 'true'
  form.setAttribute('aria-busy', 'true')
  controls.forEach(control => { control.disabled = true })
  button.textContent = '上傳中…'
  try {
    const url = await ctx.upload(file)
    if (!form.isConnected || !form.closest('dialog[open]') || ctx.state.draft !== draft) return
    const item = { id: 'own-' + crypto.randomUUID(), name, tags: ['自備'], group: '自備', image: url, reference: url, source: '個人素材' }
    ctx.closeModal()
    await ctx.applyAsset(type, item)
  } catch (error) {
    message.textContent = error.message || '上傳失敗，請重新選擇圖片。'
  } finally {
    delete form.dataset.uploading
    form.removeAttribute('aria-busy')
    controls.forEach(control => { control.disabled = false })
    button.textContent = '上傳並套用'
  }
}

function detail(ctx, type, item) {
  const { esc } = ctx
  const tags = (item.tags || []).filter(tag => tag.length < 35).slice(0, 8)
  const scope = `data-lib-detail="${type}" data-id="${esc(item.id)}"`
  ctx.modal(item.name, `<article class="lib-detail" ${scope}>
    <div class="lib-detail-photo lib-photo-${type}"><img src="${esc(item.reference)}" alt="${esc(item.name)}" referrerpolicy="no-referrer"></div>
    ${item.description ? `<p>${esc(item.description)}</p>` : ''}
    <div class="lib-tags">${tags.map(tag => `<span>${esc(tag)}</span>`).join('')}</div>
    <div class="lib-detail-foot"><span class="lib-origin">${local(item) ? '本機素材' : '線上素材'}</span>
      <button class="btn primary" type="button" data-act="lib-create">用於新角色</button></div>
    ${usage(type)}</article>`)
}

export async function libraryAction(action, el, ctx) {
  if (!action.startsWith('lib-')) return false
  if (action === 'lib-upload-submit' || action === 'lib-upload-back') {
    const form = el.closest('[data-upload-type]')
    if (!form || ctx.state.page !== 'edit') return false
    if (action === 'lib-upload-submit') await uploadSelection(form, ctx)
    else showPicker(ctx)
    return true
  }
  if (action === 'lib-create') {
    const container = el.closest('[data-lib-detail]')
    if (!container) return false
    const type = container.dataset.libDetail
    const item = records(ctx, type).find(row => row.id === container.dataset.id)
    if (!item) return false
    ctx.closeModal()
    await ctx.applyAsset(type, item, { newCharacter: true })
    return true
  }
  const container = el.closest('[data-lib-scope]')
  if (!container) return false
  const scope = container.dataset.libScope
  const options = filters(scope)
  if (action === 'lib-upload' && scope === 'picker' && ctx.state.page === 'edit') {
    uploadView(options.type, ctx)
    return true
  }
  if (action === 'lib-item') {
    const item = records(ctx, options.type).find(row => row.id === el.dataset.id)
    if (!item) return false
    if (scope === 'picker') {
      ctx.closeModal()
      await ctx.applyAsset(options.type, item)
    } else {
      detail(ctx, options.type, item)
    }
    return true
  }
  if (action === 'lib-type' || action === 'lib-reset') {
    const type = action === 'lib-type' ? el.dataset.type : options.type
    if (!Object.hasOwn(kinds, type)) return false
    Object.assign(options, initial(type))
    container.innerHTML = body(ctx, scope)
    if (action === 'lib-type') container.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true })
    else container.querySelector('[type="search"]')?.focus({ preventScroll: true })
    return true
  }
  if (action === 'lib-prev' || action === 'lib-next') {
    options.page = Math.max(1, options.page + (action === 'lib-next' ? 1 : -1))
    container.querySelector('[data-lib-results]').innerHTML = cards(ctx, scope)
    const search = container.querySelector('[type="search"]')
    search.focus({ preventScroll: true })
    search.scrollIntoView({ block: 'nearest' })
    return true
  }
  return false
}

export function libraryInput(el, ctx) {
  if (el.matches?.('[data-lib-file]')) {
    const form = el.closest('[data-upload-type]')
    const field = form.querySelector('[data-lib-name]')
    const name = el.files[0]?.name
    if (name && (!field.value.trim() || field.value === field.dataset.fromFile)) {
      field.value = name.replace(/\.[^.]+$/u, '').slice(0, 100)
      field.dataset.fromFile = field.value
    }
    form.querySelector('[role="alert"]').textContent = ''
    return true
  }
  const key = el.dataset?.libInput
  if (!['query', 'group', 'local'].includes(key)) return false
  const container = el.closest('[data-lib-scope]')
  if (!container) return false
  const scope = container.dataset.libScope
  const options = filters(scope)
  const value = key === 'local' ? el.checked : el.value
  if (options[key] !== value) {
    options[key] = value
    options.page = 1
    container.querySelector('[data-lib-results]').innerHTML = cards(ctx, scope)
  }
  return true
}

// Public catalog entries beyond the featured set may be offline.
if (typeof document !== 'undefined') document.addEventListener('error', event => {
  const image = event.target
  if (image.tagName !== 'IMG' || !image.closest('.lib-photo, .lib-detail-photo')) return
  const message = document.createElement('span')
  message.className = 'lib-image-error'
  message.textContent = image.getAttribute('src')?.startsWith('/') ? '圖片暫時無法載入' : '連線後可載入圖片'
  image.replaceWith(message)
}, true)
