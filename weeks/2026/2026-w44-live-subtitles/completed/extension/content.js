(() => {
  'use strict';
  if (globalThis.__WINSTON_SUBTITLE_RENDERER__) return;
  if (!globalThis.WinstonCueStore?.createCueStore) return;

  const store = globalThis.WinstonCueStore.createCueStore();
  const display = globalThis.WinstonCueStore.createCaptionDisplay();
  let sessionId = null;
  let revision = -1;
  let sessionMediaKey = null;
  let captureMode = null;
  let tabStartedAt = performance.now();
  let currentVideo = null;
  let previousAd = false;
  let waitingForMainPlayback = false;
  let invalidated = false;
  let awaitingRevision = false;
  let hasVisibleCaption = false;
  let state = 'idle';
  let workerMessage = '';
  let testMode = false;
  let observedPlayer = null;
  let fullscreenWarning = '';
  let config = { fontSize: 24, position: 'bottom', targetLanguage: 'zh-Hant' };
  let timer;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  const host = element('div');
  host.id = 'winston-subtitle-host';
  host.hidden = true;
  host.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;max-width:none;max-height:none;margin:0;padding:0;border:0;background:transparent;z-index:2147483646;pointer-events:none;';
  // Noise Winston Extension Kit: background.js injects tokens.css, so --nw-* resolve on this
  // [data-nw-root] host and inherit into the shadow root. Every value keeps a fallback.
  host.setAttribute('data-nw-root', '');
  const shadow = host.attachShadow({ mode: 'open' });
  const style = element('style');
  style.textContent = `
    :host { all: initial; font-family: var(--nw-font-body, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei UI", "Microsoft JhengHei", system-ui, sans-serif); -webkit-font-smoothing: antialiased; }
    :host([hidden]) { display: none !important; }
    :host::backdrop { background: transparent; pointer-events: none; }
    *, *::before, *::after { box-sizing: border-box; }
    [hidden] { display: none !important; }
    button { font: inherit; cursor: pointer; color: inherit; }
    /* Toolbar and history float over the page: raised surface, theme-aware, like Toast and Popover. */
    .tools { position: absolute; top: 16px; right: 16px; display: flex; gap: 2px; align-items: center; max-width: calc(100% - 32px); pointer-events: auto; padding: 4px 4px 4px 12px; border-radius: var(--nw-radius-lg, 12px); color: var(--nw-text, #111111); background: var(--nw-surface-raised, #FFFFFF); box-shadow: var(--nw-shadow-raised, 0 0 0 1px rgba(17,17,17,0.08), 0 2px 6px rgba(17,17,17,0.05), 0 14px 36px rgba(17,17,17,0.12)); font-size: var(--nw-text-sm, 12px); font-weight: 500; line-height: var(--nw-leading, 1.55); }
    .status { min-width: 0; max-width: 290px; padding-right: 6px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .status::before { content: ""; display: inline-block; width: 7px; height: 7px; margin: 0 var(--nw-space-2, 8px) 1px 0; vertical-align: middle; border-radius: 50%; background: var(--nw-text-muted, #6B6B68); }
    .status[data-state="busy"]::before { background: var(--nw-action, #7432FF); animation: nw-pulse 1.2s var(--nw-ease-standard, cubic-bezier(0.2, 0, 0, 1)) infinite; }
    .status[data-state="ready"]::before { background: var(--nw-success, #18A76B); }
    .status[data-state="error"]::before { background: var(--nw-error, #DB1B1B); }
    .tools button { min-height: var(--nw-control-sm, 28px); padding: 0 10px; border: 0; border-radius: var(--nw-radius-sm, 6px); background: transparent; color: var(--nw-text-muted, #6B6B68); font-weight: 500; white-space: nowrap; transition: background-color var(--nw-duration-fast, 120ms) var(--nw-ease-standard, cubic-bezier(0.2, 0, 0, 1)), color var(--nw-duration-fast, 120ms) var(--nw-ease-standard, cubic-bezier(0.2, 0, 0, 1)); }
    .tools button:hover { background: var(--nw-fill-hover, rgba(17,17,17,0.075)); color: var(--nw-text, #111111); }
    .tools button:focus-visible { outline: 2px solid var(--nw-focus, #1877F2); outline-offset: 2px; }
    .tools button[aria-expanded="true"] { background: var(--nw-action-tint, rgba(116,50,255,0.09)); color: var(--nw-action-text, #7432FF); }
    .tools .stop { color: var(--nw-error-text, #C21818); }
    .tools .stop:hover { background: var(--nw-error-tint, rgba(219,27,27,0.09)); color: var(--nw-error-text, #C21818); }
    /* Captions sit on the video and never follow the theme: brand ink chips with ivory text. */
    .captions { position: absolute; left: 5%; right: 5%; bottom: 72px; display: flex; align-items: center; flex-direction: column; gap: 4px; text-align: center; color: var(--nw-brand-ivory, #F1EFE7); pointer-events: none; }
    .captions.top { top: 72px; bottom: auto; }
    .line { margin: 0; max-width: 100%; padding: 4px 12px; background: rgba(17, 17, 17, 0.82); border-radius: var(--nw-radius-xs, 4px); line-height: 1.45; max-height: calc(2.9em + 12px); overflow: hidden; font-weight: 600; white-space: pre-wrap; overflow-wrap: anywhere; }
    .original { color: rgba(241, 239, 231, 0.78); font-size: calc(var(--subtitle-size, 24px) * .75); font-weight: 400; }
    .translation { font-size: var(--subtitle-size, 24px); }
    .history { position: absolute; right: 16px; top: 68px; width: min(380px, calc(100% - 32px)); max-height: calc(100% - 145px); overflow: auto; padding: 12px 16px 16px; border-radius: var(--nw-radius-xl, 14px); background: var(--nw-surface-raised, #FFFFFF); box-shadow: var(--nw-shadow-raised, 0 0 0 1px rgba(17,17,17,0.08), 0 2px 6px rgba(17,17,17,0.05), 0 14px 36px rgba(17,17,17,0.12)); color: var(--nw-text, #111111); font-size: var(--nw-text-base, 14px); line-height: var(--nw-leading, 1.55); pointer-events: auto; user-select: text; }
    .history h2 { margin: 0 0 2px; font-size: var(--nw-text-md, 13px); font-weight: 600; line-height: var(--nw-leading-tight, 1.3); }
    .history-note { margin: 0 0 var(--nw-space-2, 8px); color: var(--nw-text-muted, #6B6B68); font-size: var(--nw-text-sm, 12px); }
    .history ol { list-style: none; padding: 0; margin: 0; }
    .history li { padding: var(--nw-space-3, 12px) 0; border-top: 1px solid var(--nw-line, rgba(17,17,17,0.1)); }
    .history time { color: var(--nw-text-muted, #6B6B68); font-family: var(--nw-font-signal, "Roboto Condensed", "Bahnschrift", "Arial Narrow", sans-serif); font-stretch: 87.5%; font-variant-numeric: tabular-nums; font-size: var(--nw-text-sm, 12px); font-weight: 600; }
    .history p { margin: 2px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; }
    .history .source { color: var(--nw-text-muted, #6B6B68); font-size: var(--nw-text-sm, 12px); }
    .empty { padding: var(--nw-space-3, 12px) 0 0; border-top: 1px solid var(--nw-line, rgba(17,17,17,0.1)); color: var(--nw-text-muted, #6B6B68); font-size: var(--nw-text-md, 13px); }
    @keyframes nw-pulse { 50% { opacity: 0.35; } }
    @media (max-width: 600px) { .status { max-width: 150px; } .tools { top: 8px; right: 8px; } .captions { left: 3%; right: 3%; bottom: 60px; } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; } }
  `;
  shadow.append(style);
  const tools = element('div', 'tools');
  const status = element('span', 'status', '準備字幕');
  status.setAttribute('role', 'status');
  const historyButton = element('button', '', '字幕紀錄');
  historyButton.type = 'button';
  historyButton.setAttribute('aria-expanded', 'false');
  const stopButton = element('button', 'stop', '停止');
  stopButton.type = 'button';
  tools.append(status, historyButton, stopButton);
  const captions = element('div', 'captions');
  captions.hidden = true;
  captions.setAttribute('aria-live', 'polite');
  captions.setAttribute('aria-atomic', 'true');
  const original = element('p', 'line original');
  const translation = element('p', 'line translation');
  original.setAttribute('dir', 'auto');
  translation.setAttribute('dir', 'auto');
  captions.append(original, translation);
  const historyPanel = element('section', 'history');
  historyPanel.hidden = true;
  historyPanel.setAttribute('aria-label', '本次字幕紀錄');
  historyPanel.append(element('h2', '', '本次字幕紀錄'), element('p', 'history-note', '畫面只顯示近期語句，完整文字保留最近 50 段。原文與譯文依到達時間分段，未逐句對齊。拖曳進度後重新累積。'));
  const historyList = element('ol');
  const empty = element('p', 'empty', '字幕完成後會出現在這裡。');
  historyPanel.append(empty, historyList);
  shadow.append(tools, captions, historyPanel);
  applyTheme('system');

  function mediaKey() {
    try {
      const url = new URL(location.href);
      if (!['http:', 'https:'].includes(url.protocol)) return null;
      if (isYoutubeWatch(url)) return url.searchParams.get('v');
      const routeHash = /^#!?\//.test(url.hash) ? url.hash : '';
      return `tab:${url.origin}${url.pathname}${url.search}${routeHash}`;
    } catch { return null; }
  }
  function isYoutubeWatch(url = new URL(location.href)) {
    return url.protocol === 'https:' && ['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(url.hostname)
      && url.pathname === '/watch' && /^[A-Za-z0-9_-]{11}$/.test(url.searchParams.get('v') ?? '');
  }
  function player() { return isYoutubeWatch() ? document.getElementById('movie_player') : null; }
  function selectVideo() { return player()?.querySelector('video.html5-main-video') ?? player()?.querySelector('video') ?? null; }
  function activeMode() { return captureMode || (selectVideo() ? 'youtube' : 'tab'); }
  function adPlaying() { return activeMode() === 'youtube' && Boolean(player()?.classList.contains('ad-showing') || player()?.classList.contains('ad-interrupting')); }
  function snapshot() {
    const mode = activeMode();
    const video = mode === 'youtube' ? selectVideo() : null;
    const key = mediaKey();
    const liveBadge = mode === 'youtube' ? player()?.querySelector('.ytp-live-badge') : null;
    return {
      ok: Boolean(key && (mode === 'tab' || video)), mediaKey: key, captureMode: mode,
      time: mode === 'tab' ? Math.max(0, (performance.now() - tabStartedAt) / 1000) : (Number.isFinite(video?.currentTime) ? video.currentTime : 0),
      paused: mode === 'tab' ? false : (video?.paused ?? true),
      playbackRate: mode === 'tab' ? 1 : (video?.playbackRate ?? 1),
      adPlaying: adPlaying(),
      title: document.querySelector('h1.ytd-watch-metadata')?.textContent?.trim() || document.title.replace(/ - YouTube$/, ''),
      url: location.href,
      isLive: video?.duration === Infinity || Boolean(liveBadge && liveBadge.getClientRects().length && getComputedStyle(liveBadge).display !== 'none'),
    };
  }
  function send(message) {
    try { Promise.resolve(chrome.runtime.sendMessage(message)).catch(() => {}); } catch { /* The extension may have been reloaded. */ }
  }
  function sendState(reason) {
    if (!sessionId) return;
    const data = snapshot();
    send({ type: 'MEDIA_STATE', sessionId, mediaKey: data.mediaKey, time: data.time,
      paused: data.paused, playbackRate: data.playbackRate, adPlaying: data.adPlaying, reason });
  }
  function clearPopover() {
    try { if (host.matches?.(':popover-open')) host.hidePopover?.(); } catch { /* The browser may already have removed it from the top layer. */ }
    host.removeAttribute('popover');
  }
  function mount(fullscreenChanged = false) {
    const fullscreen = document.fullscreenElement;
    const mode = activeMode();
    // Replaced elements cannot render an appended overlay. A manual popover
    // places our own host above their fullscreen top layer without changing media.
    const needsTopLayer = fullscreen && ['VIDEO', 'IFRAME', 'EMBED', 'OBJECT'].includes(fullscreen.tagName);
    const fullscreenContainer = fullscreen && !needsTopLayer ? fullscreen : null;
    const container = needsTopLayer ? document.documentElement : fullscreenContainer || (mode === 'youtube' ? player() : null) || document.documentElement;
    host.style.position = mode === 'youtube' && container === player() ? 'absolute' : 'fixed';
    if (container && host.parentElement !== container) container.append(host);
    fullscreenWarning = '';
    if (needsTopLayer && sessionId && !host.hidden) {
      try {
        if (typeof host.showPopover !== 'function') throw new Error('Popover unavailable');
        if (fullscreenChanged) clearPopover();
        host.setAttribute('popover', 'manual');
        if (!host.matches(':popover-open')) host.showPopover();
      } catch {
        clearPopover();
        fullscreenWarning = '此瀏覽器無法在影片全螢幕上方顯示字幕，請退出全螢幕後繼續。';
      }
    } else clearPopover();
    renderStatus();
  }
  function clearCaption(reset = true) {
    if (reset) display.reset();
    else display.dismiss();
    captions.hidden = true;
    original.textContent = '';
    translation.textContent = '';
    hasVisibleCaption = false;
  }
  function renderCaption() {
    const width = (host.parentElement?.clientWidth || document.documentElement?.clientWidth || 960) * 0.9;
    display.setLimits({ original: Math.floor(width / (config.fontSize * 0.75 * 0.56) * 1.8), translation: Math.floor(width / (config.fontSize * 0.56) * 1.8) });
    const text = display.read(performance.now());
    if (original.textContent !== text.original) original.textContent = text.original;
    if (translation.textContent !== text.translation) translation.textContent = text.translation;
    original.hidden = !text.original;
    translation.hidden = !text.translation;
    captions.hidden = !text.original && !text.translation;
    hasVisibleCaption = !captions.hidden;
  }
  // Status is always a dot plus words: busy breathes, ready is live captions, error needs action.
  function setStatus(message, dot) {
    status.textContent = message || '';
    status.title = message || '';
    if (dot) status.setAttribute('data-state', dot);
    else status.removeAttribute('data-state');
  }
  function applyTheme(mode) {
    if (mode === undefined) return;
    const theme = ['light', 'dark'].includes(mode) ? mode : 'system';
    host.setAttribute('data-nw-theme', theme);
    host.style.colorScheme = theme === 'system' ? 'light dark' : theme;
  }
  function renderStatus() {
    if (!sessionId || invalidated) return;
    if (state === 'stopped') { setStatus(workerMessage || '字幕已停止'); return; }
    if (state === 'error') { setStatus(workerMessage || '字幕發生問題，請開啟擴充功能查看。', 'error'); return; }
    if (fullscreenWarning) { setStatus(fullscreenWarning, 'error'); return; }
    const prefix = testMode ? '測試模式 · ' : '';
    if (adPlaying()) { setStatus(`${prefix}廣告播放中 · 字幕暫停`); return; }
    if (activeMode() === 'youtube' && currentVideo?.paused) { setStatus(`${prefix}影片已暫停 · 字幕待命`); return; }
    const latest = store.latest();
    if (latest && hasVisibleCaption) {
      const delay = latest.latencyMs ? ` · 約延遲 ${(latest.latencyMs / 1000).toFixed(1)} 秒` : ' · 即時生成有自然延遲';
      setStatus(`${prefix}${workerMessage || '雙語字幕運作中'}${delay}`, 'ready');
    } else {
      setStatus(`${prefix}${workerMessage || (state === 'processing' ? '正在辨識與翻譯 · 請稍候' : '聆聽中 · 字幕會稍晚出現')}`, 'busy');
    }
  }
  function formatTime(value) {
    const total = Math.max(0, Math.floor(value));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
  }
  function renderHistory() {
    const items = store.getHistory();
    historyList.replaceChildren();
    empty.hidden = items.length > 0;
    for (const cue of [...items].reverse()) {
      const item = element('li');
      const translated = element('p', '', cue.translation);
      const source = element('p', 'source', cue.original);
      translated.setAttribute('dir', 'auto');
      translated.setAttribute('lang', config.targetLanguage);
      source.setAttribute('dir', 'auto');
      item.append(element('time', '', formatTime(cue.start)), translated, source);
      historyList.append(item);
    }
  }
  function updateStyle(next) {
    const fontSize = Math.max(16, Math.min(40, Number(next?.fontSize) || 24));
    config = { fontSize, position: next?.position === 'top' ? 'top' : 'bottom', targetLanguage: next?.targetLanguage || config.targetLanguage };
    translation.setAttribute('lang', config.targetLanguage);
    captions.style.setProperty('--subtitle-size', `${config.fontSize}px`);
    captions.classList.toggle('top', config.position === 'top');
  }
  function discontinuity(reason) {
    if (!sessionId || invalidated) return;
    clearCaption();
    awaitingRevision = true;
    sendState(reason);
  }
  const handlers = {
    seeking: () => discontinuity('seek'),
    ratechange: () => discontinuity('rate'),
    play: () => {
      if (!adPlaying() && !currentVideo?.ended) waitingForMainPlayback = false;
      sendState('tick'); renderStatus();
    },
    pause: () => { sendState('tick'); renderStatus(); },
    ended: () => {
      if (!sessionId || adPlaying() || previousAd || waitingForMainPlayback) return;
      clearCaption(false);
      state = 'processing';
      workerMessage = '影片已結束 · 正在完成最後一段字幕';
      setStatus(workerMessage, 'busy');
      sendState('ended');
    },
  };
  function checkAdBoundary() {
    if (!sessionId || invalidated || state === 'stopped') return;
    const nextAd = adPlaying();
    if (previousAd !== nextAd) {
      previousAd = nextAd;
      waitingForMainPlayback = true;
      discontinuity('ad');
    }
    if (nextAd) clearCaption();
    renderStatus();
  }
  const adObserver = new MutationObserver(checkAdBoundary);
  function bindVideo() {
    const nextPlayer = activeMode() === 'youtube' ? player() : null;
    if (nextPlayer !== observedPlayer) {
      adObserver.disconnect();
      observedPlayer = nextPlayer;
      if (observedPlayer) adObserver.observe(observedPlayer, { attributes: true, attributeFilter: ['class'] });
    }
    const video = activeMode() === 'youtube' ? selectVideo() : null;
    if (video === currentVideo) return;
    if (currentVideo) for (const [name, handler] of Object.entries(handlers)) currentVideo.removeEventListener(name, handler);
    currentVideo = video;
    if (currentVideo) for (const [name, handler] of Object.entries(handlers)) currentVideo.addEventListener(name, handler);
  }
  function tick() {
    bindVideo();
    if (!sessionId) return;
    if (mediaKey() !== sessionMediaKey) {
      if (!invalidated) {
        invalidated = true;
        clearCaption();
        historyPanel.hidden = true;
        setStatus('頁面已切換 · 請重新開始字幕');
        sendState('video-change');
      }
      return;
    }
    mount();
    checkAdBoundary();
    if (!adPlaying() && currentVideo && !currentVideo.ended && !currentVideo.paused) waitingForMainPlayback = false;
    renderCaption();
    renderStatus();
    sendState('tick');
  }
  function stop() {
    sessionId = null;
    sessionMediaKey = null;
    captureMode = null;
    revision = -1;
    invalidated = false;
    awaitingRevision = false;
    state = 'stopped';
    clearCaption();
    historyPanel.hidden = true;
    historyButton.setAttribute('aria-expanded', 'false');
    clearPopover();
    fullscreenWarning = '';
    host.hidden = true;
  }
  historyButton.addEventListener('click', event => {
    event.stopPropagation();
    historyPanel.hidden = !historyPanel.hidden;
    historyButton.setAttribute('aria-expanded', String(!historyPanel.hidden));
    if (!historyPanel.hidden) renderHistory();
  });
  for (const node of [tools, historyPanel]) {
    node.addEventListener('click', event => event.stopPropagation());
    node.addEventListener('dblclick', event => event.stopPropagation());
    node.addEventListener('keydown', event => event.stopPropagation());
  }
  stopButton.addEventListener('click', event => {
    event.stopPropagation();
    send({ type: 'STOP' });
    stop();
  });
  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id && sender.id !== chrome.runtime.id) return false;
    if (message?.type === 'SUBTITLE_PING') { bindVideo(); respond(snapshot()); return false; }
    if (message?.type === 'SUBTITLE_INIT') {
      if (!mediaKey() || !store.reset(message.sessionId, message.revision)) { respond({ ok: false }); return false; }
      captureMode = ['youtube', 'tab'].includes(message.captureMode) ? message.captureMode : (selectVideo() ? 'youtube' : 'tab');
      tabStartedAt = performance.now();
      sessionId = message.sessionId;
      revision = message.revision;
      sessionMediaKey = mediaKey();
      invalidated = false;
      awaitingRevision = false;
      state = 'listening';
      workerMessage = '';
      testMode = false;
      previousAd = adPlaying();
      waitingForMainPlayback = previousAd;
      clearCaption();
      updateStyle(message.config);
      applyTheme(message.themeMode);
      renderHistory();
      bindVideo();
      host.hidden = false;
      mount();
      renderStatus();
      respond({ ok: true });
      return false;
    }
    if (message?.type === 'UPDATE_STYLE') { updateStyle({ ...config, ...message.config }); applyTheme(message.themeMode); respond({ ok: true }); return false; }
    if (message?.type === 'SUBTITLE_STOP' && (!message.sessionId || message.sessionId === sessionId)) { stop(); respond({ ok: true }); return false; }
    if (!sessionId || message?.sessionId !== sessionId || invalidated) return false;
    if (message.type === 'SUBTITLE_CLEAR') {
      if (!store.reset(sessionId, message.revision)) { respond({ ok: false }); return false; }
      revision = message.revision;
      awaitingRevision = false;
      workerMessage = '';
      state = 'listening';
      clearCaption();
      renderHistory();
      respond({ ok: true });
      return false;
    }
    if (message.type === 'SUBTITLE_STATUS') {
      state = message.state;
      workerMessage = message.message || '';
      if (workerMessage.includes('測試模式')) testMode = true;
      renderStatus();
      respond({ ok: true });
      return false;
    }
    if (message.type === 'SUBTITLE_CUE') {
      const accepted = message.revision === revision && !awaitingRevision && mediaKey() === sessionMediaKey && !adPlaying() && store.add(message);
      if (accepted) {
        // An older cue may update history, but cannot refresh the current screen.
        display.update({ ...message.cue, original: message.cue.original.trim(), translation: message.cue.translation.trim() }, performance.now());
        renderCaption();
        if (!historyPanel.hidden) renderHistory();
        renderStatus();
      }
      respond({ ok: Boolean(accepted) });
      return false;
    }
    return false;
  });
  document.addEventListener('fullscreenchange', () => mount(true));
  document.addEventListener('yt-navigate-finish', tick);
  timer = setInterval(tick, 500);
  globalThis.__WINSTON_SUBTITLE_RENDERER__ = Object.freeze({ version: '0.3.0', timer });
  bindVideo();
})();
