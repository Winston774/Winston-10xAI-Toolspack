import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { File } from 'node:buffer';
import vm from 'node:vm';

const source = await readFile(new URL('../extension/social-content.js', import.meta.url), 'utf8');
const CHUNK_BYTES = 256 * 1024;
const settle = async () => { for (let i = 0; i < 3; i++) await new Promise(setImmediate); };

// 小型 DOM 替身只提供接收程式使用的 API；測試透過貼上與按鈕事件走完整匯入流程。
class FakeElement {
  constructor(tagName, attributes = {}) {
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map(Object.entries(attributes));
    this.children = [];
    this.parentElement = null;
    this.listeners = new Map();
    this.dataset = {};
    this.files = [];
    this.style = { display: 'block', visibility: 'visible' };
    this.events = [];
    this.box = { width: 300, height: 100 };
  }
  get isConnected() { return this.root === true || Boolean(this.parentElement?.isConnected); }
  get isContentEditable() { return this.getAttribute('contenteditable') === 'true'; }
  get hidden() { return this.attributes.has('hidden'); }
  set hidden(value) { value ? this.attributes.set('hidden', '') : this.attributes.delete('hidden'); }
  get disabled() { return this.attributes.has('disabled'); }
  set disabled(value) { value ? this.attributes.set('disabled', '') : this.attributes.delete('disabled'); }
  get readOnly() { return this.attributes.has('readonly'); }
  get multiple() { return this.attributes.has('multiple'); }
  set multiple(value) { value ? this.attributes.set('multiple', '') : this.attributes.delete('multiple'); }
  get accept() { return this.getAttribute('accept') || ''; }
  set accept(value) { this.setAttribute('accept', value); }
  get type() { return this.getAttribute('type') || 'text'; }
  set type(value) { this.setAttribute('type', value); }
  get textContent() { return (this.text || '') + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this.text = value; this.children.forEach((child) => { child.parentElement = null; }); this.children = []; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  getBoundingClientRect() { return this.box; }
  append(...children) { children.forEach((child) => { child.remove(); child.parentElement = this; this.children.push(child); }); }
  remove() {
    if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((child) => child !== this);
    this.parentElement = null;
  }
  attachShadow() { this.shadowRoot = new FakeElement('shadow'); this.shadowRoot.parentElement = this; return this.shadowRoot; }
  matches(selector) {
    return selector.split(',').some((part) => {
      const token = part.trim();
      const tag = token.match(/^[a-z][a-z0-9]*/i)?.[0];
      if (tag && this.tagName !== tag.toUpperCase()) return false;
      return [...token.matchAll(/\[([\w-]+)(?:=['"]?([^'"\]]+)['"]?)?\]/g)]
        .every(([, name, value]) => value === undefined ? this.attributes.has(name) : this.getAttribute(name) === value);
    });
  }
  closest(selector) { for (let node = this; node; node = node.parentElement) if (node.matches(selector)) return node; return null; }
  querySelectorAll(selector) { return this.children.flatMap((child) => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
  contains(element) { for (let node = element; node; node = node.parentElement) if (node === this) return true; return false; }
  addEventListener(type, listener) { this.listeners.set(type, [...(this.listeners.get(type) || []), listener]); }
  dispatchEvent(event) {
    this.events.push(event.type);
    for (const listener of this.listeners.get(event.type) || []) listener(event);
    return !event.defaultPrevented;
  }
  click() { throw new Error('接收程式不得代按平台按鈕'); }
}

async function environment({ hostname = 'www.threads.com', bytes = new Uint8Array([1, 2, 3, 4]), metadata = {}, busy = false, composer = true } = {}) {
  const html = new FakeElement('html');
  html.root = true;
  const document = {
    documentElement: html,
    listeners: new Map(),
    createElement: (tag) => new FakeElement(tag),
    querySelectorAll: (selector) => html.querySelectorAll(selector),
    getElementById: (id) => html.querySelectorAll('[id]').find((element) => element.getAttribute('id') === id),
    addEventListener(type, listener) { this.listeners.set(type, listener); },
  };
  const state = {
    clip: { id: 'clip-123', name: 'fixture.mp4', size: bytes.length, mime: 'video/mp4', createdAt: 123, ...metadata },
    busy, requests: [], bytes, html, document,
  };
  state.addComposer = ({ label = hostname === 'www.facebook.com' ? '在想些什麼？' : '文字欄位空白。請輸入內容以撰寫新貼文。', title = '', hidden = false, readonly = false, editable = true, accept = 'image/avif,image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm' } = {}) => {
    const dialog = new FakeElement('div', { role: 'dialog' });
    dialog.hidden = hidden;
    if (title) { const heading = new FakeElement('h2'); heading.textContent = title; dialog.append(heading); }
    const editor = new FakeElement('div', { role: 'textbox', 'aria-label': label });
    if (editable) editor.setAttribute('contenteditable', 'true');
    if (readonly) editor.setAttribute('aria-readonly', 'true');
    const input = new FakeElement('input', { type: 'file', accept, multiple: '' });
    dialog.append(editor, input);
    html.append(dialog);
    return { dialog, editor, input };
  };
  if (composer) Object.assign(state, state.addComposer());
  const timers = new Map();
  let timerId = 0;
  const runtimeListeners = [];
  const context = vm.createContext({
    location: { hostname }, document, Element: FakeElement, File, Uint8Array, atob,
    getComputedStyle: (element) => element.style,
    DataTransfer: class { constructor() { this.files = []; this.items = { add: (file) => this.files.push(file) }; } },
    Event: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    MutationObserver: class { constructor(callback) { state.mutate = callback; } observe() {} },
    window: { addEventListener: (type, listener) => { state[`window_${type}`] = listener; } },
    setTimeout: (callback, delay) => { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: (id) => timers.delete(id),
    chrome: { runtime: {
      onMessage: { addListener: (listener) => runtimeListeners.push(listener) },
      sendMessage: async (message) => {
        state.requests.push(message);
        if (state.respond) { const result = await state.respond(message); if (result !== undefined) return result; }
        if (message.type === 'VC_GET_STATUS') return { ok: true, clip: state.clip, busy: state.busy };
        assert.equal(message.type, 'VC_READ_CHUNK');
        const chunk = state.bytes.slice(message.offset, message.offset + message.length);
        return { ok: true, total: state.clip.size, base64: Buffer.from(chunk).toString('base64'), eof: message.offset + chunk.length === state.clip.size };
      },
    } },
  });
  state.execute = () => vm.runInContext(source, context, { filename: 'social-content.js' });
  state.execute();
  state.paste = ({ text = 'video-bridge:clip-123', target = state.editor, trusted = true, files = [] } = {}) => {
    const event = { isTrusted: trusted, target, clipboardData: { files, getData: () => text }, defaultPrevented: false, stopped: false,
      preventDefault() { this.defaultPrevented = true; }, stopImmediatePropagation() { this.stopped = true; } };
    document.listeners.get('paste')?.(event);
    return event;
  };
  state.button = () => html.querySelectorAll('[data-video-bridge-control]')[0]?.shadowRoot.querySelectorAll('button')[0];
  state.toast = () => html.querySelectorAll('[data-video-bridge-toast]')[0]?.shadowRoot.querySelectorAll('[role="status"]')[0]?.textContent || '';
  state.click = ({ trusted = true } = {}) => state.button()?.dispatchEvent({ type: 'click', isTrusted: trusted });
  state.notify = async () => { for (const listener of runtimeListeners) listener({ type: 'VC_STATUS' }); await settle(); };
  state.update = () => { state.mutate?.([]); for (const [id, timer] of timers) if (timer.delay === 120) { timers.delete(id); timer.callback(); } };
  await settle();
  return state;
}

test('僅在五個精確平台網域啟用，重複載入不重複監聽', async () => {
  for (const hostname of ['www.facebook.com', 'threads.com', 'www.threads.com', 'threads.net', 'www.threads.net']) {
    const state = await environment({ hostname });
    assert.equal(state.requests.length, 1, hostname);
    state.execute();
    assert.equal(state.requests.length, 1, hostname);
    assert.match(state.button().textContent, hostname.includes('facebook') ? /Facebook/ : /Threads/);
  }
  for (const hostname of ['facebook.com', 'm.facebook.com', 'www.facebook.com.evil.test', 'evilthreads.com', 'x.com']) {
    const state = await environment({ hostname });
    assert.equal(state.requests.length, 0, hostname);
    assert.equal(state.document.listeners.size, 0, hostname);
  }
});

test('可信任標記貼上逐塊傳輸並交給唯一 Threads 附件欄位，保留原附件且不發佈', async () => {
  const bytes = new Uint8Array(CHUNK_BYTES + 7).fill(31);
  const state = await environment({ bytes });
  const previous = new File(['photo'], 'photo.jpg', { type: 'image/jpeg' });
  state.input.files = [previous];
  const event = state.paste();
  assert.equal(event.defaultPrevented, true);
  assert.equal(event.stopped, true);
  await settle();
  assert.equal(state.input.files.length, 2);
  assert.equal(state.input.files[0], previous);
  assert.deepEqual(new Uint8Array(await state.input.files[1].arrayBuffer()), bytes);
  assert.deepEqual(state.input.events, ['input', 'change']);
  const chunks = state.requests.filter(({ type }) => type === 'VC_READ_CHUNK');
  assert.deepEqual(chunks.map(({ offset, length }) => [offset, length]), [[0, CHUNK_BYTES], [CHUNK_BYTES, 7]]);
  assert.match(state.toast(), /已交給 Threads.*自行發佈/);
  assert.equal(state.button().disabled, false);
});

test('Facebook 使用平台對應提示且按鈕能插入目前暫存影片', async () => {
  const state = await environment({ hostname: 'www.facebook.com' });
  state.click();
  await settle();
  assert.equal(state.input.files.length, 1);
  assert.match(state.toast(), /已交給 Facebook/);
});

test('一般文字、真實檔案、非可信任事件與非精確標記不攔截', async () => {
  for (const options of [{ text: '一般貼文文字' }, { files: [new File(['x'], 'x.mp4')] }, { trusted: false },
    { text: ' video-bridge:clip-123' }, { text: 'video-bridge:clip-123\n' }, { text: 'video-bridge:' }, { text: `video-bridge:${'a'.repeat(129)}` }]) {
    const state = await environment();
    const event = state.paste(options);
    await settle();
    assert.equal(event.defaultPrevented, false, JSON.stringify(options));
    assert.equal(state.requests.length, 1);
    assert.equal(state.input.files.length, 0);
  }
  const state = await environment();
  state.click({ trusted: false });
  await settle();
  assert.equal(state.requests.length, 1);
});

test('剪貼簿標記必須精確對應最新影片', async () => {
  const state = await environment();
  state.clip = { ...state.clip, id: 'new-clip' };
  assert.equal(state.paste().defaultPrevented, true);
  await settle();
  assert.match(state.toast(), /已過期/);
  assert.equal(state.input.files.length, 0);
  assert.equal(state.requests.filter(({ type }) => type === 'VC_READ_CHUNK').length, 0);
});

test('背景準備中與無暫存影片均停止匯入', async () => {
  const busy = await environment({ busy: true });
  assert.equal(busy.button().disabled, true);
  busy.paste();
  await settle();
  assert.match(busy.toast(), /仍在準備/);
  assert.equal(busy.input.files.length, 0);
  const empty = await environment();
  empty.clip = null;
  empty.paste();
  await settle();
  assert.match(empty.toast(), /尚未複製/);
  assert.equal(empty.input.files.length, 0);
});

test('隱藏的外掛 dialog 不影響唯一發文視窗，非編輯 textbox 不構成 composer', async () => {
  const state = await environment();
  state.addComposer({ hidden: true });
  state.addComposer({ editable: false });
  state.paste();
  await settle();
  assert.equal(state.input.files.length, 1);
});

test('留言、訊息、回覆、未知用途、唯讀與不可編輯欄位保持原貼上行為', async () => {
  for (const config of [{ label: '發表留言' }, { label: '輸入訊息' }, { label: 'Reply to this thread' },
    { label: '搜尋' }, { title: '回覆', label: '文字欄位空白。請輸入內容以撰寫新貼文。' }, { readonly: true }, { editable: false }]) {
    const state = await environment({ composer: false });
    Object.assign(state, state.addComposer(config));
    const event = state.paste();
    await settle();
    assert.equal(event.defaultPrevented, false, JSON.stringify(config));
    assert.equal(state.input.files.length, 0);
  }
});

test('兩個可見 dialog 或多個可編輯 textbox 均拒絕選擇目標', async () => {
  const dialogs = await environment();
  dialogs.addComposer();
  assert.equal(dialogs.paste().defaultPrevented, false);
  dialogs.click();
  await settle();
  assert.match(dialogs.toast(), /保留一個 Threads/);
  assert.equal(dialogs.input.files.length, 0);
  const editors = await environment();
  editors.dialog.append(new FakeElement('div', { role: 'textbox', contenteditable: 'true', 'aria-label': 'New post' }));
  assert.equal(editors.paste().defaultPrevented, false);
  editors.click();
  await settle();
  assert.match(editors.toast(), /多個輸入區/);
  assert.equal(editors.input.files.length, 0);
});

test('多個影片附件欄位、停用欄位與不支援格式均不寫入', async () => {
  const multiple = await environment();
  multiple.dialog.append(new FakeElement('input', { type: 'file', accept: 'video/mp4' }));
  multiple.paste();
  await settle();
  assert.match(multiple.toast(), /多個附件欄位/);
  assert.equal(multiple.input.files.length, 0);
  const disabled = await environment();
  disabled.input.disabled = true;
  disabled.paste();
  await settle();
  assert.match(disabled.toast(), /附加影音內容/);
  const incompatible = await environment();
  incompatible.input.accept = 'video/webm';
  incompatible.paste();
  await settle();
  assert.match(incompatible.toast(), /不支援這種影片格式/);
  assert.equal(incompatible.input.files.length, 0);
});

test('貼上必須落在目前編輯器或其子元素內', async () => {
  const state = await environment();
  const unrelated = new FakeElement('div');
  state.dialog.append(unrelated);
  assert.equal(state.paste({ target: unrelated }).defaultPrevented, false);
  const child = new FakeElement('span');
  state.editor.append(child);
  assert.equal(state.paste({ target: child }).defaultPrevented, true);
  await settle();
  assert.equal(state.input.files.length, 1);
});

test('讀取中關閉視窗、切換 editor 或替換 input 都停止匯入', async () => {
  for (const change of [
    (state) => state.dialog.remove(),
    (state) => { state.dialog.hidden = true; state.addComposer(); },
    (state) => { state.editor.remove(); state.dialog.append(new FakeElement('div', { role: 'textbox', contenteditable: 'true', 'aria-label': 'New post' })); },
    (state) => { state.input.remove(); state.dialog.append(new FakeElement('input', { type: 'file', accept: 'video/mp4' })); },
    (state) => state.editor.setAttribute('aria-label', '回覆串文'),
    (state) => state.addComposer({ label: '回覆串文' }),
  ]) {
    const state = await environment();
    state.respond = (message) => { if (message.type === 'VC_READ_CHUNK') change(state); };
    state.paste();
    await settle();
    assert.equal(state.input.files.length, 0);
    assert.match(state.toast(), /已關閉|已變更|保留一個|新貼文/);
  }
});

test('等待狀態時變更 composer 會在讀取影片前停止', async () => {
  const state = await environment();
  state.respond = (message) => { if (message.type === 'VC_GET_STATUS') state.dialog.remove(); };
  state.paste();
  await settle();
  assert.match(state.toast(), /已關閉/);
  assert.equal(state.requests.filter(({ type }) => type === 'VC_READ_CHUNK').length, 0);
});

test('同一 DOM 發文視窗關閉後立刻重開仍使先前匯入失效', async () => {
  for (const mutation of [
    (state) => ({ type: 'attributes', target: state.dialog, attributeName: 'hidden' }),
    (state) => ({ type: 'childList', target: state.html, removedNodes: [state.dialog] }),
  ]) {
    const state = await environment();
    state.respond = (message) => { if (message.type === 'VC_READ_CHUNK') state.mutate([mutation(state)]); };
    state.paste();
    await settle();
    assert.equal(state.input.files.length, 0);
    assert.match(state.toast(), /已變更或關閉/);
  }
});

test('平台一般 DOM 更新與外掛控制 UI 更新不會取消正在讀取的影片', async () => {
  const state = await environment();
  state.respond = (message) => {
    if (message.type === 'VC_READ_CHUNK') state.mutate([
      { type: 'childList', target: state.html, removedNodes: [] },
      { type: 'attributes', target: state.button(), attributeName: 'disabled' },
    ]);
  };
  state.paste();
  await settle();
  assert.equal(state.input.files.length, 1);
});

test('重複貼上與已有相同檔案均不產生重複附件', async () => {
  const state = await environment();
  state.paste();
  await settle();
  state.paste();
  await settle();
  assert.equal(state.input.files.length, 1);
  assert.match(state.toast(), /已插入此影片/);
  const existing = await environment();
  existing.input.files = [new File([existing.bytes], 'fixture.mp4', { type: 'video/mp4' })];
  existing.paste();
  await settle();
  assert.equal(existing.input.files.length, 1);
  assert.match(existing.toast(), /已在附件欄位/);
  const single = await environment();
  single.input.multiple = false;
  single.input.files = [new File(['photo'], 'photo.jpg', { type: 'image/jpeg' })];
  single.paste();
  await settle();
  assert.equal(single.input.files.length, 1);
  assert.match(single.toast(), /已有檔案/);
});

test('並行貼上只啟動一個匯入，錯誤後恢復可操作狀態', async () => {
  const state = await environment();
  let release;
  state.respond = (message) => message.type === 'VC_READ_CHUNK' ? new Promise((resolve) => { release = resolve; }) : undefined;
  state.paste();
  await settle();
  assert.equal(state.button().disabled, true);
  state.paste();
  assert.match(state.toast(), /正在插入影片，請稍候/);
  assert.equal(state.requests.filter(({ type }) => type === 'VC_READ_CHUNK').length, 1);
  release({ ok: false, error: '讀取測試失敗' });
  await settle();
  assert.match(state.toast(), /讀取測試失敗/);
  assert.equal(state.button().disabled, false);
  state.respond = undefined;
  state.paste();
  await settle();
  assert.equal(state.input.files.length, 1);
});

test('無效影片大小與識別資訊在傳輸前拒絕', async () => {
  for (const metadata of [{ size: 0 }, { size: 150 * 1024 * 1024 + 1 }, { size: 2.5 }, { id: '' }, { id: '../clip' }]) {
    const state = await environment({ metadata });
    state.click();
    await settle();
    assert.match(state.toast(), /暫存影片資訊無效/);
    assert.equal(state.requests.filter(({ type }) => type === 'VC_READ_CHUNK').length, 0);
  }
});

test('分塊總長、編碼、實際長度與 EOF 不一致均不寫入', async () => {
  for (const result of [
    { total: 5, base64: 'AQIDBA==', eof: true },
    { total: 4, base64: 'AQID', eof: true },
    { total: 4, base64: 'AQIDBAAA', eof: true },
    { total: 4, base64: 'AQIDB?==', eof: true },
    { total: 4, base64: 'AQIDBA==', eof: false },
    { total: 4, base64: 'AQIDBA==', eof: 'true' },
  ]) {
    const state = await environment();
    state.respond = (message) => message.type === 'VC_READ_CHUNK' ? { ok: true, ...result } : undefined;
    state.paste();
    await settle();
    assert.equal(state.input.files.length, 0);
    assert.match(state.toast(), /已變更|不完整|長度不一致/);
  }
});

test('外掛更新錯誤顯示對應平台並恢復按鈕', async () => {
  const state = await environment({ hostname: 'www.facebook.com' });
  state.respond = () => { throw new Error('Extension context invalidated'); };
  state.paste();
  await settle();
  assert.match(state.toast(), /重新載入 Facebook/);
  assert.equal(state.button().disabled, false);
});
