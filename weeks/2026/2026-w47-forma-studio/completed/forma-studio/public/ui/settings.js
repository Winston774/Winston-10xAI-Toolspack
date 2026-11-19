const secretFlags = { openaiKey: 'openaiKeySet', fishApiKey: 'fishKeySet', breezeToken: 'breezeTokenSet' };
const secretLabels = { openaiKey: 'OpenAI API 金鑰', fishApiKey: 'Fish Audio API 金鑰', breezeToken: 'Breeze 存取權杖' };

function secretField(key, config) {
  const saved = Boolean(config[secretFlags[key]]);
  const remove = saved ? `<button class="btn ghost" type="button" data-act="settings-remove" data-key="${key}">移除已存${key === 'breezeToken' ? '權杖' : '金鑰'}</button>` : '';
  return `<div class="field"><label for="setting-${key}">${secretLabels[key]}</label>
    <div class="settings-secret"><input id="setting-${key}" name="${key}" type="password" autocomplete="new-password" spellcheck="false"
      placeholder="${saved ? '已儲存，輸入新值即可更新' : '貼上' + secretLabels[key]}">${remove}</div></div>`;
}

function textField(key, label, value, esc, placeholder = '') {
  return `<div class="field"><label for="setting-${key}">${label}</label>
    <input id="setting-${key}" name="${key}" type="text" spellcheck="false" autocomplete="off"
      value="${esc(value || '')}" placeholder="${esc(placeholder)}"></div>`;
}

export function settingsView({ state, esc }) {
  const config = state.settings || {};
  const mediaOpen = typeof document !== 'undefined' && document.querySelector('#studio-media-settings')?.open;
  return `<section class="settings-page">
    <header class="page-heading"><div><h1>服務設定</h1><p>管理圖片、配音與影片服務。金鑰儲存在這台電腦。</p></div></header>
    <section class="panel" data-settings-group="openai">
      <div class="panel-head"><h2 class="section-title">OpenAI</h2>
        <span class="settings-status muted">${config.openaiKeySet ? '已儲存金鑰' : '尚未設定'}</span></div>
      ${secretField('openaiKey', config)}
      <div class="field-grid">${textField('imageModel', '圖片模型', config.imageModel, esc)}
        ${textField('textModel', '角色設定與提示詞模型', config.textModel, esc)}</div>
      <div class="settings-actions"><button type="button" class="btn primary" data-act="settings-save">儲存設定</button>
        <button type="button" class="btn secondary" data-act="settings-test">儲存並測試連線</button></div>
    </section>
    <details class="panel settings-details" id="studio-media-settings" data-settings-group="media"${mediaOpen ? ' open' : ''}>
      <summary class="section-title">配音與影片服務</summary>
      <div class="settings-detail-body">
        <h3>Fish Audio</h3>${secretField('fishApiKey', config)}${textField('fishModel', '語音模型', config.fishModel, esc)}
        <h3>BreezeTTS</h3>${textField('breezeUrl', 'Colab 服務網址', config.breezeUrl, esc, '留白使用本機 BreezeTTS')}
        ${secretField('breezeToken', config)}
        <h3>LongCat Avatar</h3>
        <label class="settings-switch"><input type="checkbox" name="longcatEnabled"${config.longcatEnabled ? ' checked' : ''}> 啟用 Colab A100 影片生成</label>
        <p class="muted">每次生成會傳送選取的照片與配音，使用 Colab 計算額度。片長為 1–60 秒。</p>
        <div class="settings-actions"><button type="button" class="btn primary" data-act="settings-save">儲存設定</button></div>
      </div>
    </details>
  </section>`;
}

function readGroup(group) {
  const values = {};
  for (const field of group.querySelectorAll('input[name]')) {
    if (field.type === 'password' && !field.value.trim()) continue;
    values[field.name] = field.type === 'checkbox' ? field.checked : field.value.trim();
  }
  return values;
}

export async function settingsAction(action, el, ctx) {
  const group = el.closest('[data-settings-group]');
  if (!group || el.disabled) return;
  const removing = action === 'settings-remove';
  const testing = action === 'settings-test';
  if (!removing && !testing && action !== 'settings-save') return;
  const key = el.dataset.key;
  if (removing && (!Object.hasOwn(secretFlags, key) || !window.confirm(`移除本機儲存的${secretLabels[key]}？`))) return;
  const body = removing ? { [key]: '' } : readGroup(group);
  const original = el.textContent;
  const buttons = [...group.querySelectorAll('button')];
  buttons.forEach(button => { button.disabled = true; });
  el.textContent = testing ? '正在測試…' : '正在儲存…';
  let saved = false;
  try {
    const result = await ctx.api('/api/settings', { method: 'PATCH', body });
    ctx.state.settings = result.settings;
    saved = true;
    if (testing) {
      await ctx.api('/api/settings/test', { method: 'POST', body: { provider: 'openai' } });
      ctx.toast('兩個 OpenAI 模型皆可連線。');
    } else {
      ctx.toast(removing ? '已移除本機儲存的資料。' : '已儲存設定。');
    }
  } finally {
    buttons.forEach(button => { button.disabled = false; });
    el.textContent = original;
    if (saved && group.isConnected) {
      // Keep other fields, including the other panel's unsaved edits, in place.
      for (const field of group.querySelectorAll('input[type=password]')) {
        if (!(field.name in body)) continue;
        const wasFocused = field.matches(':focus');
        const wrapper = field.closest('.field');
        wrapper.outerHTML = secretField(field.name, ctx.state.settings);
        if (wasFocused) document.getElementById('setting-' + field.name)?.focus();
      }
      const indicator = group.querySelector('.settings-status');
      if (indicator) indicator.textContent = ctx.state.settings.openaiKeySet ? '已儲存金鑰' : '尚未設定';
    }
  }
}
