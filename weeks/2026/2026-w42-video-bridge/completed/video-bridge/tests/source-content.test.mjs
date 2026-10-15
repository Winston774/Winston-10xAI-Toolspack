import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../extension/source-content.js', import.meta.url), 'utf8');
const POST_ID = '2101369117496521042';
const POSTER = 'https://pbs.twimg.com/amplify_video_thumb/2101367981486051328/img/POjBvV3P9O7LKDGZ.jpg';

class Element {
  constructor(tagName, attributes = {}) {
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map(Object.entries(attributes));
    this.children = [];
    this.parentElement = null;
    this.box = { left: 0, top: 0, right: 400, bottom: 300, width: 400, height: 300 };
    this.style = { display: 'block', visibility: 'visible' };
  }
  get isConnected() { return this.root === true || Boolean(this.parentElement?.isConnected); }
  get hidden() { return this.attributes.has('hidden'); }
  set hidden(value) { value ? this.attributes.set('hidden', '') : this.attributes.delete('hidden'); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
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
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  contains(element) { for (let node = element; node; node = node.parentElement) if (node === this) return true; return false; }
  append(...children) { children.forEach((child) => { child.remove(); child.parentElement = this; this.children.push(child); }); }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((child) => child !== this); this.parentElement = null; }
  getBoundingClientRect() { return this.box; }
}
class Video extends Element {
  constructor(url, poster = POSTER) { super('video'); this.currentSrc = url; this.poster = poster; }
}

function environment(page = 'https://x.com/home') {
  const html = new Element('html');
  html.root = true;
  const body = new Element('body');
  html.append(body);
  const state = { html, body, now: 10000, location: new URL(page), listeners: new Map(), scripts: [], pointStack: [], fetches: [], pages: new Map() };
  const document = {
    documentElement: html, body, baseURI: page, title: '來源貼文測試',
    addEventListener: () => { throw new Error('右鍵需在 window 捕獲階段處理'); },
    elementsFromPoint: () => state.pointStack,
    querySelectorAll(selector) {
      if (selector === 'script[type="application/json"]') return state.scripts;
      throw new Error('禁止全頁影片搜尋');
    },
  };
  const context = vm.createContext({
    Element, HTMLVideoElement: Video, document, location: state.location, URL, AbortController,
    window: { addEventListener: (name, handler, capture) => { assert.equal(capture, true); state.listeners.set(name, handler); } },
    Date: class extends Date { static now() { return state.now; } },
    getComputedStyle: (element) => element.style,
    setTimeout: () => 1, clearTimeout: () => {},
    fetch: async (url, options) => {
      state.fetches.push({ url, options });
      const page = state.pages.get(url);
      if (!page) return { ok: false, status: 404, text: async () => '' };
      return { ok: true, status: 200, text: async () => page };
    },
    DOMParser: class {
      parseFromString(text) {
        const scripts = [...text.matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)].map(([, textContent]) => ({ textContent }));
        return { querySelectorAll: (selector) => selector === 'script[type="application/json"]' ? scripts : [] };
      }
    },
    chrome: { runtime: { onMessage: { addListener: (listener) => { state.message = listener; } } } },
  });
  state.execute = () => vm.runInContext(source, context, { filename: 'source-content.js' });
  state.execute();
  state.addPost = ({ href = `/heystefan_/status/${POST_ID}`, url = 'blob:https://x.com/fixture', poster = POSTER } = {}) => {
    const article = new Element('article');
    const link = new Element('a', { href });
    const wrapper = new Element('div');
    const video = new Video(url, poster);
    wrapper.append(video);
    article.append(link, wrapper);
    body.append(article);
    return { article, link, wrapper, video };
  };
  state.rightClick = (target, { x = 100, y = 100, shiftKey = false } = {}) => {
    const path = [];
    for (let node = target; node; node = node.parentElement) path.push(node);
    const event = { composedPath: () => path, clientX: x, clientY: y, shiftKey, stopped: 0, prevented: 0,
      stopImmediatePropagation() { this.stopped++; }, stopPropagation() { this.stopped++; }, preventDefault() { this.prevented++; } };
    state.listeners.get('contextmenu')(event);
    return event;
  };
  state.get = () => new Promise((resolve) => {
    const keepsChannelOpen = state.message({ type: 'VC_GET_SOURCE' }, {}, resolve);
    assert.equal(keepsChannelOpen, true);
  });
  return state;
}

test('X blob 回傳右鍵影片的唯一貼文 ID、海報與原頁面 URL', async () => {
  const state = environment();
  const selected = state.addPost();
  selected.article.append(new Element('a', { href: `/heystefan_/status/${POST_ID}/analytics` }),
    new Element('a', { href: `/heystefan_/status/${POST_ID}/quotes` }),
    new Element('a', { href: `/heystefan_/status/${POST_ID}/comments` }));
  state.rightClick(selected.video);
  const result = (await state.get());
  assert.equal(result.ok, true);
  assert.equal(result.url, selected.video.currentSrc);
  assert.equal(result.pageUrl, 'https://x.com/home');
  assert.equal(result.xPostUrl, `https://x.com/heystefan_/status/${POST_ID}`);
  assert.equal(result.poster, POSTER);
});

test('X 與 Twitter 永久連結正規化，支援 i/status 與 video/N', async () => {
  for (const [href, expected] of [
    [`/heystefan_/status/${POST_ID}/video/1`, `https://x.com/heystefan_/status/${POST_ID}`],
    [`/i/status/${POST_ID}`, `https://x.com/i/status/${POST_ID}`],
    [`https://www.twitter.com/author/status/${POST_ID}/?s=20`, `https://x.com/author/status/${POST_ID}`],
    [`https://twitter.com/author/status/${POST_ID}/video/2`, `https://x.com/author/status/${POST_ID}`],
  ]) {
    const state = environment('https://twitter.com/home');
    const selected = state.addPost({ href });
    state.rightClick(selected.video);
    assert.equal((await state.get()).xPostUrl, expected, href);
  }
});

test('analytics、quote、comments、額外路徑、偽裝主機與非 HTTPS 不作來源連結；沒有封面時也不從網址補 ID', async () => {
  for (const href of [
    `/author/status/${POST_ID}/analytics`, `/author/status/${POST_ID}/quotes`, `/author/status/${POST_ID}/comments`,
    `/author/status/${POST_ID}/video/1/extra`, `/author/status/${POST_ID}/photo/1`, `/author/status/${POST_ID}suffix`,
    `https://x.com.evil.test/author/status/${POST_ID}`, `https://user@x.com/author/status/${POST_ID}`,
    `https://x.com:8443/author/status/${POST_ID}`, `http://x.com/author/status/${POST_ID}`,
    '', '#video', '?s=20',
  ]) {
    const state = environment(`https://x.com/outer/status/${POST_ID}`);
    const selected = state.addPost({ href, poster: '' });
    state.rightClick(selected.video);
    const result = (await state.get());
    assert.equal(result.ok, false, href);
    assert.match(result.error, /貼文連結/);
  }
});

test('同一 ID 的多條永久連結不構成歧義', async () => {
  const state = environment();
  const selected = state.addPost();
  selected.article.append(new Element('a', { href: `/i/status/${POST_ID}/video/1` }));
  state.rightClick(selected.video);
  assert.equal((await state.get()).ok, true);
});

test('最近的引用卡片來源優先於外層貼文及另一張引用卡片', async () => {
  for (const attributes of [{ role: 'link' }, { 'data-testid': 'quoteTweet' }]) {
    const state = environment(`https://x.com/outer/status/999`);
    const outer = state.addPost({ href: '/outer/status/999' });
    const quote = new Element('div', attributes);
    quote.append(new Element('a', { href: '/original/status/111' }), outer.video);
    outer.wrapper.append(quote);
    const otherQuote = new Element('div', { role: 'link' });
    otherQuote.append(new Element('a', { href: '/other/status/222' }), new Video('blob:https://x.com/other'));
    outer.article.append(otherQuote);
    state.rightClick(outer.video);
    assert.equal((await state.get()).xPostUrl, 'https://x.com/original/status/111');
  }
});

test('點到外層影片時忽略旁邊引用卡片的來源連結', async () => {
  const state = environment();
  const selected = state.addPost();
  const quote = new Element('div', { role: 'link' });
  quote.append(new Element('a', { href: '/quoted/status/111' }), new Video('blob:https://x.com/quoted'));
  selected.article.append(quote);
  state.rightClick(selected.video);
  assert.equal((await state.get()).xPostUrl, `https://x.com/heystefan_/status/${POST_ID}`);
});

test('包覆目標影片的直接永久連結可辨識同 article 中的影片來源', async () => {
  const state = environment();
  const selected = state.addPost();
  const link = new Element('a', { href: '/original/status/111/video/1' });
  link.append(selected.video);
  selected.wrapper.append(link);
  state.rightClick(selected.video);
  assert.equal((await state.get()).xPostUrl, 'https://x.com/original/status/111');
});

test('混合多 ID 且沒有明確引用區塊、也沒有封面時拒絕，不採 location 外層 status', async () => {
  const state = environment('https://x.com/outer/status/999');
  const selected = state.addPost({ href: '/outer/status/999', poster: '' });
  selected.article.append(new Element('a', { href: '/quoted/status/111' }));
  state.rightClick(selected.video);
  const result = (await state.get());
  assert.equal(result.ok, false);
  assert.match(result.error, /多個來源/);
});

test('引用區塊缺少自身來源或同區塊多 ID、且沒有封面時拒絕使用外層 status', async () => {
  for (const hrefs of [[], ['/one/status/111', '/two/status/222']]) {
    const state = environment('https://x.com/outer/status/999');
    const selected = state.addPost({ href: '/outer/status/999', poster: '' });
    const quote = new Element('div', { role: 'link' });
    quote.append(...hrefs.map((href) => new Element('a', { href })), selected.video);
    selected.wrapper.append(quote);
    state.rightClick(selected.video);
    const result = (await state.get());
    assert.equal(result.ok, false);
    assert.match(result.error, /原始貼文連結|多篇貼文/);
  }
});

test('缺少 article 或永久連結、且沒有封面可驗證時不從網址補 ID', async () => {
  for (const removeArticle of [true, false]) {
    const state = environment(`https://x.com/outer/status/${POST_ID}`);
    const selected = state.addPost({ href: '/unrelated', poster: '' });
    if (removeArticle) state.body.append(selected.video);
    state.rightClick(selected.video);
    const result = (await state.get());
    assert.equal(result.ok, false);
    assert.match(result.error, /所屬的貼文|貼文連結/);
  }
});

test('X HLS 與 DASH 交由背景解析器', async () => {
  for (const url of ['https://video.twimg.com/clip.m3u8?tag=1', 'https://video.twimg.com/clip.mpd', 'blob:https://x.com/fixture']) {
    const state = environment();
    const selected = state.addPost({ url });
    state.rightClick(selected.video);
    assert.equal((await state.get()).ok, true, url);
    assert.equal((await state.get()).xPostUrl, `https://x.com/heystefan_/status/${POST_ID}`);
  }
});

const THREADS_CODE = 'DdcCAYcjuua';
const THREADS_MP4 = 'https://instagram.fkhh1-1.fna.fbcdn.net/o1/v/t16/f2/m84/clip.mp4?oe=fixture';

function threadsPost({ code = THREADS_CODE, pk = '1', videoVersions = [{ type: 101, url: THREADS_MP4 }], carousel = null, width = 1296, height = 1080 } = {}) {
  return { pk, code, media_type: carousel ? 8 : 2, original_width: width, original_height: height, video_versions: carousel ? null : videoVersions, carousel_media: carousel, video_dash_manifest: '<MPD/>' };
}

function threadsScript(...posts) {
  // 模擬 Threads 內嵌資料：同一篇貼文會在多個節點重複出現。
  return { textContent: JSON.stringify({ require: [[{ __bbox: { result: { data: { media: posts[0], relatedPosts: { threads: posts.map((post) => ({ thread_items: [{ post }] })) } } } } }]] }) };
}

function threadsEnvironment({ url = 'blob:https://www.threads.com/fixture', href = `/@author/post/${THREADS_CODE}`, page = 'https://www.threads.com/' } = {}) {
  const state = environment(page);
  const selected = state.addPost({ url, href, poster: '' });
  selected.article.setAttribute('data-pressable-container', 'true');
  return { state, selected };
}

test('Threads blob 與分段串流改用內嵌貼文資料的 MP4 版本，不另外連網', async () => {
  for (const url of ['blob:https://www.threads.com/fixture', 'https://scontent.cdninstagram.com/clip.mpd', 'https://scontent.cdninstagram.com/clip.m3u8']) {
    const { state, selected } = threadsEnvironment({ url });
    state.scripts.push({ textContent: '{"unrelated":true}' }, threadsScript(threadsPost(), threadsPost({ code: 'OtherPost1', pk: '2', videoVersions: [{ url: 'https://scontent.cdninstagram.com/other.mp4' }] })));
    state.rightClick(selected.video);
    const result = await state.get();
    assert.equal(result.ok, true, url);
    assert.equal(result.url, THREADS_MP4);
    assert.equal(result.pageUrl, `https://www.threads.com/@author/post/${THREADS_CODE}`);
    assert.equal(state.fetches.length, 0);
  }
});

test('Threads 內嵌資料沒有該貼文時，以 HTML 請求讀取同站貼文頁', async () => {
  const { state, selected } = threadsEnvironment({ page: 'https://www.threads.net/' });
  state.scripts.push(threadsScript(threadsPost({ code: 'OtherPost1' })));
  const postPage = `https://www.threads.net/@author/post/${THREADS_CODE}`;
  state.pages.set(postPage, `<html><script type="application/json">${threadsScript(threadsPost()).textContent}</script></html>`);
  state.rightClick(selected.video);
  const result = await state.get();
  assert.equal(result.ok, true);
  assert.equal(result.url, THREADS_MP4);
  assert.equal(result.pageUrl, postPage);
  assert.equal(state.fetches.length, 1);
  assert.equal(state.fetches[0].url, postPage);
  assert.equal(state.fetches[0].options.credentials, 'same-origin');
  assert.match(state.fetches[0].options.headers.Accept, /^text\/html/);
});

test('Threads 有尺寸資訊時選最高畫質，並略過非 HTTPS 版本', async () => {
  const { state, selected } = threadsEnvironment();
  state.scripts.push(threadsScript(threadsPost({ videoVersions: [
    { url: 'http://scontent.cdninstagram.com/insecure.mp4', width: 1920, height: 1080 },
    { url: 'https://scontent.cdninstagram.com/small.mp4', width: 640, height: 360 },
    { url: 'https://scontent.cdninstagram.com/large.mp4', width: 1280, height: 720 },
  ] })));
  state.rightClick(selected.video);
  assert.equal((await state.get()).url, 'https://scontent.cdninstagram.com/large.mp4');
});

test('Threads 輪播多支影片時以畫面比例比對，無法唯一確認就停止', async () => {
  const carousel = [
    { pk: 'a', original_width: 1080, original_height: 1920, video_versions: [{ url: 'https://scontent.cdninstagram.com/portrait.mp4' }] },
    { pk: 'b', original_width: 1920, original_height: 1080, video_versions: [{ url: 'https://scontent.cdninstagram.com/landscape.mp4' }] },
    { pk: 'c', original_width: 1080, original_height: 1080, image_versions2: {} },
  ];
  const { state, selected } = threadsEnvironment();
  state.scripts.push(threadsScript(threadsPost({ carousel })));
  Object.assign(selected.video, { videoWidth: 1280, videoHeight: 720, duration: 12 });
  state.rightClick(selected.video);
  assert.equal((await state.get()).url, 'https://scontent.cdninstagram.com/landscape.mp4');

  Object.assign(selected.video, { videoWidth: 0, videoHeight: 0 });
  const result = await state.get();
  assert.equal(result.ok, false);
  assert.match(result.error, /多支影片/);
});

test('Threads 找不到唯一貼文連結或 MP4 版本時明確失敗', async () => {
  for (const [setup, pattern] of [
    [({ selected }) => selected.link.setAttribute('href', '/@author'), /貼文連結/],
    [({ selected }) => selected.article.append(new Element('a', { href: '/@other/post/OtherPost1' })), /多篇 Threads 貼文/],
    [({ state }) => state.pages.set(`https://www.threads.com/@author/post/${THREADS_CODE}`, '<html></html>'), /MP4 版本/],
    [() => {}, /HTTP 404/],
  ]) {
    const env = threadsEnvironment();
    setup(env);
    env.state.rightClick(env.selected.video);
    const result = await env.state.get();
    assert.equal(result.ok, false);
    assert.match(result.error, pattern);
  }
});

test('Threads 引用卡片中的其他貼文連結不影響外層影片來源', async () => {
  const { state, selected } = threadsEnvironment();
  const quote = new Element('div', { 'data-pressable-container': 'true' });
  quote.append(new Element('a', { href: '/@quoted/post/QuotedPost1' }));
  selected.article.append(quote);
  state.scripts.push(threadsScript(threadsPost()));
  state.rightClick(selected.video);
  assert.equal((await state.get()).pageUrl, `https://www.threads.com/@author/post/${THREADS_CODE}`);
});

test('X 影片上的右鍵阻止網站自訂選單但不取消 Chrome 選單；Shift 與非影片位置維持原樣', async () => {
  const state = environment();
  const selected = state.addPost();
  const overlay = new Element('button');
  selected.wrapper.append(overlay);

  let event = state.rightClick(selected.video);
  assert.equal(event.stopped, 1);
  assert.equal(event.prevented, 0);

  state.pointStack = [overlay, selected.video, selected.wrapper];
  event = state.rightClick(overlay);
  assert.equal(event.stopped, 1);
  assert.equal(event.prevented, 0);
  assert.equal((await state.get()).url, selected.video.currentSrc);

  event = state.rightClick(overlay, { shiftKey: true });
  assert.equal(event.stopped, 0);

  state.pointStack = [selected.link, selected.article];
  event = state.rightClick(selected.link);
  assert.equal(event.stopped, 0);
});

test('Threads 頁面的右鍵不攔截網站事件', async () => {
  const { state, selected } = threadsEnvironment();
  state.pointStack = [selected.video];
  const event = state.rightClick(selected.video);
  assert.equal(event.stopped, 0);
  assert.equal(event.prevented, 0);
});

test('直接 MP4 保留既有行為，即使 X 貼文 ID 缺失或引用歧義也可回傳', async () => {
  for (const page of ['https://x.com/home', 'https://www.threads.com/@author/post/fixture']) {
    const state = environment(page);
    const selected = state.addPost({ url: 'https://video.twimg.com/clip.mp4?signature=fixture' });
    selected.article.append(new Element('a', { href: '/quoted/status/111' }));
    state.rightClick(selected.video);
    const result = (await state.get());
    assert.equal(result.ok, true);
    assert.equal(result.url, selected.video.currentSrc);
    assert.equal(result.xPostUrl, undefined);
    if (page.includes('threads')) assert.equal(result.poster, undefined);
  }
});

test('只回傳目標影片的受支援公開海報，不採旁邊影片海報', async () => {
  for (const poster of ['', 'https://pbs.twimg.com.evil.test/poster.jpg', 'http://pbs.twimg.com/poster.jpg', 'https://user@pbs.twimg.com/poster.jpg']) {
    const state = environment();
    const selected = state.addPost({ poster });
    selected.article.append(new Video('blob:https://x.com/other', POSTER));
    state.rightClick(selected.video);
    assert.equal((await state.get()).poster, '');
  }
});

test('播放器覆蓋層依可見影片與指標命中選取，其他貼文影片不參與', async () => {
  const state = environment();
  state.addPost({ href: '/wrong/status/222', url: 'blob:https://x.com/wrong' });
  const selected = state.addPost();
  const overlay = new Element('div');
  selected.wrapper.append(overlay);
  const hidden = new Video('blob:https://x.com/hidden');
  hidden.hidden = true;
  selected.wrapper.append(hidden);
  state.rightClick(overlay);
  assert.equal((await state.get()).xPostUrl, `https://x.com/heystefan_/status/${POST_ID}`);
  assert.equal((await state.get()).url, selected.video.currentSrc);
  hidden.hidden = false;
  assert.equal((await state.get()).ok, false);
  assert.match((await state.get()).error, /多支影片/);
});

test('右鍵上下文過期、路由變更與目標移除均要求重新右鍵', async () => {
  for (const change of [
    (state) => { state.now += 120001; },
    (state) => { state.location.pathname = '/different'; },
    (_state, selected) => selected.video.remove(),
  ]) {
    const state = environment();
    const selected = state.addPost();
    state.rightClick(selected.video);
    change(state, selected);
    assert.equal((await state.get()).ok, false);
    assert.match((await state.get()).error, /重新按右鍵/);
  }
});

test('重複載入保持單一 listener，缺少右鍵上下文與來源 URL 均明確失敗', async () => {
  const state = environment();
  const listener = state.message;
  state.execute();
  assert.equal(state.message, listener);
  assert.equal((await state.get()).ok, false);
  const selected = state.addPost({ url: '' });
  state.rightClick(selected.video);
  assert.match((await state.get()).error, /來源尚未載入/);
});

test('非 HTTP 與 blob 協定不能靠串流副檔名繞過來源限制', async () => {
  for (const url of ['data:video/mp4,fixture.m3u8', 'javascript:fixture.mpd', 'file:///fixture.m3u8']) {
    const state = environment();
    const selected = state.addPost({ url });
    state.rightClick(selected.video);
    assert.equal((await state.get()).ok, false, url);
    assert.match((await state.get()).error, /HTTP/);
  }
});

function sendMessage(state, message) {
  return new Promise((resolve) => {
    const keepsChannelOpen = state.message(message, {}, resolve);
    if (keepsChannelOpen !== true) resolve(undefined);
  });
}

const VIEWER_POST = 'https://x.com/thebuggeddev/status/2110241991233790456';
const VIEWER_POSTER = 'https://pbs.twimg.com/amplify_video_thumb/2110241050128531456/img/rltHeW2JxIqnljU4?format=webp&name=medium';

test('X 影片檢視器的影片沒有所屬 article 時，改用網址中的貼文並附上封面與播放器尺寸', async () => {
  const state = environment(`${VIEWER_POST}/video/1`);
  const dialog = new Element('div', { role: 'dialog', 'aria-modal': 'true' });
  const video = new Video('blob:https://x.com/viewer', VIEWER_POSTER);
  Object.assign(video, { duration: 50.1, videoWidth: 1414, videoHeight: 922 });
  dialog.append(video);
  state.body.append(dialog);
  state.rightClick(video);
  const result = await state.get();
  assert.equal(result.ok, true);
  assert.equal(result.xPostUrl, VIEWER_POST);
  assert.equal(result.poster, VIEWER_POSTER);
  assert.equal(result.xPageUrl, undefined);
  assert.deepEqual([result.duration, result.width, result.height], [50.1, 1414, 922]);
});

test('X 文章中的影片找不到貼文連結時用網址貼文；找到其他貼文連結時一併附上網址貼文供備援', async () => {
  const page = 'https://x.com/OriSilver/status/2074089635177746707';
  const poster = 'https://pbs.twimg.com/amplify_video_thumb/2074085545349689344/img/ek-QS-G1vs25FZYs.jpg';
  let state = environment(page);
  let selected = state.addPost({ href: '/OriSilver/article/1', poster });
  state.rightClick(selected.video);
  assert.equal((await state.get()).xPostUrl, page);

  state = environment(page);
  selected = state.addPost({ href: '/someone/status/111', poster });
  state.rightClick(selected.video);
  const result = await state.get();
  assert.equal(result.xPostUrl, 'https://x.com/someone/status/111');
  assert.equal(result.xPageUrl, page);
});

test('VC_RESOLVE_X_PAGE 以不帶登入資訊的貼文頁取出同一媒體 ID 的最高解析度 MP4', async () => {
  const state = environment(`${VIEWER_POST}/video/1`);
  state.pages.set(VIEWER_POST, [
    '<video src="https://video.twimg.com/amplify_video/999/vid/avc1/1920x1080/other.mp4?tag=1"></video>',
    '<source src="https://video.twimg.com/amplify_video/2110241050128531456/vid/avc1/552x360/low.mp4?tag=29&amp;x=1">',
    '"https://video.twimg.com/amplify_video/2110241050128531456/vid/avc1/1656x1080/high.mp4?tag=29"',
    '"https://video.twimg.com/amplify_video/2110241050128531456/pl/playlist.m3u8"',
  ].join('\n'));
  const result = await sendMessage(state, { type: 'VC_RESOLVE_X_PAGE', postUrl: VIEWER_POST, poster: VIEWER_POSTER });
  assert.deepEqual({ ...result }, { ok: true, url: 'https://video.twimg.com/amplify_video/2110241050128531456/vid/avc1/1656x1080/high.mp4?tag=29', pageUrl: VIEWER_POST });
  assert.equal(state.fetches[0].url, VIEWER_POST);
  assert.equal(state.fetches[0].options.credentials, 'omit');
  assert.match(state.fetches[0].options.headers.Accept, /^text\/html/);
});

test('VC_RESOLVE_X_PAGE 支援 GIF，並拒絕非貼文網址、缺少封面與找不到的媒體', async () => {
  const state = environment('https://x.com/home');
  state.pages.set('https://x.com/a/status/1', '<video src="https://video.twimg.com/tweet_video/GifName_1.mp4"></video>');
  const gif = await sendMessage(state, { type: 'VC_RESOLVE_X_PAGE', postUrl: 'https://x.com/a/status/1', poster: 'https://pbs.twimg.com/tweet_video_thumb/GifName_1.jpg' });
  assert.equal(gif.url, 'https://video.twimg.com/tweet_video/GifName_1.mp4');
  for (const [postUrl, poster, pattern] of [
    ['https://x.com/home', VIEWER_POSTER, /缺少/],
    ['https://evil.test/a/status/1', VIEWER_POSTER, /缺少/],
    ['https://x.com/a/status/1', '', /缺少/],
    ['https://x.com/a/status/1', VIEWER_POSTER, /找不到這支影片/],
    ['https://x.com/a/status/2', VIEWER_POSTER, /HTTP 404/],
  ]) {
    const result = await sendMessage(state, { type: 'VC_RESOLVE_X_PAGE', postUrl, poster });
    assert.equal(result.ok, false, postUrl);
    assert.match(result.error, pattern);
  }
  const threads = environment('https://www.threads.com/');
  assert.equal(await sendMessage(threads, { type: 'VC_RESOLVE_X_PAGE', postUrl: VIEWER_POST, poster: VIEWER_POSTER }), undefined);
});

test('同一位置疊放多個 video 時選畫面最上層的那一支', async () => {
  const state = environment();
  const selected = state.addPost();
  const backdrop = new Video('blob:https://x.com/backdrop');
  selected.wrapper.append(backdrop);
  const overlay = new Element('div');
  selected.wrapper.append(overlay);
  state.pointStack = [overlay, selected.video, backdrop];
  state.rightClick(overlay);
  assert.equal((await state.get()).url, selected.video.currentSrc);
  state.pointStack = [overlay, backdrop, selected.video];
  assert.equal((await state.get()).url, backdrop.currentSrc);
});

test('Threads 輪播多支相同比例的影片時，以封面圖或 DASH 清單長度確認所選影片', async () => {
  const cover = (name) => ({ candidates: [{ url: `https://scontent.cdninstagram.com/v/t51/${name}?stp=dst-jpg` }] });
  const carousel = [
    { pk: 'img', original_width: 1080, original_height: 1350, image_versions2: cover('photo_n.jpg') },
    { pk: 'a', original_width: 1080, original_height: 1350, image_versions2: cover('first_n.jpg'), video_dash_manifest: '<MPD mediaPresentationDuration="PT5.27093S">', video_versions: [{ url: 'https://scontent.cdninstagram.com/first.mp4' }] },
    { pk: 'b', original_width: 1080, original_height: 1350, image_versions2: cover('second_n.jpg'), video_dash_manifest: '<MPD mediaPresentationDuration="PT1M13.3S">', video_versions: [{ url: 'https://scontent.cdninstagram.com/second.mp4' }] },
  ];

  let { state, selected } = threadsEnvironment();
  state.scripts.push(threadsScript(threadsPost({ carousel })));
  const item = new Element('div');
  item.append(new Element('img', { src: 'https://scontent.cdninstagram.com/v/t51/second_n.jpg?stp=dst-webp' }), selected.video);
  selected.wrapper.append(item);
  selected.wrapper.append(new Element('img', { src: 'https://scontent.cdninstagram.com/v/t51/first_n.jpg' }));
  state.rightClick(selected.video);
  assert.equal((await state.get()).url, 'https://scontent.cdninstagram.com/second.mp4');

  ({ state, selected } = threadsEnvironment());
  state.scripts.push(threadsScript(threadsPost({ carousel })));
  Object.assign(selected.video, { duration: 5.385, videoWidth: 720, videoHeight: 900 });
  state.rightClick(selected.video);
  assert.equal((await state.get()).url, 'https://scontent.cdninstagram.com/first.mp4');

  Object.assign(selected.video, { duration: Number.NaN });
  const result = await state.get();
  assert.equal(result.ok, false);
  assert.match(result.error, /先播放/);
});
