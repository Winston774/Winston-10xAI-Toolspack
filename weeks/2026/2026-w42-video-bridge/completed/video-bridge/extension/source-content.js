(() => {
  "use strict";
  if (globalThis.__videoBridgeSourceLoaded) return;
  globalThis.__videoBridgeSourceLoaded = true;

  let context = null;
  let toastHost;
  let toastTimer;
  const X_HOSTS = new Set(["x.com", "www.x.com", "twitter.com", "www.twitter.com"]);
  const THREADS_HOSTS = new Set(["threads.com", "www.threads.com", "threads.net", "www.threads.net"]);
  const THREADS_POST_PATH = /^\/@([A-Za-z0-9._]{1,30})\/post\/([A-Za-z0-9_-]{5,64})\/?$/;
  const PAGE_TIMEOUT_MS = 20000;
  const MAX_PAGE_CHARS = 8 * 1024 * 1024;

  function showStatus(message, state = "ready") {
    if (!toastHost?.isConnected) {
      toastHost = document.createElement("div");
      toastHost.setAttribute("data-video-bridge-toast", "");
      // Noise Winston Extension Kit: tokens come from noise-winston/tokens.css (injected by the manifest).
      toastHost.setAttribute("data-nw-root", "");
      const shadow = toastHost.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = ":host{all:initial;position:fixed;right:20px;top:20px;z-index:2147483647;pointer-events:none;max-width:min(380px,calc(100vw - 40px))}:host([hidden]){display:none!important}div{display:flex;align-items:flex-start;gap:10px;padding:11px 16px 11px 14px;border-radius:12px;background:var(--nw-surface-raised,#fff);color:var(--nw-text,#111);box-shadow:var(--nw-shadow-raised,0 0 0 1px rgba(17,17,17,.08),0 14px 36px rgba(17,17,17,.14));font:500 13px/1.55 var(--nw-font-body,system-ui,sans-serif);-webkit-font-smoothing:antialiased;overflow-wrap:anywhere;animation:nw-in 180ms cubic-bezier(.16,1,.3,1)}div::before{content:\"\";flex:0 0 auto;width:7px;height:7px;margin-top:7px;border-radius:50%;background:var(--nw-action,#7432FF)}div[data-state=working]::before{animation:nw-pulse 1.2s ease-in-out infinite}div[data-state=ready]::before{background:var(--nw-success,#18A76B)}div[data-state=error]::before{background:var(--nw-error,#DB1B1B)}@keyframes nw-in{from{opacity:0;transform:translateY(-4px)}}@keyframes nw-pulse{50%{opacity:.35}}@media (prefers-reduced-motion:reduce){div,div::before{animation:none!important}}";
      const text = document.createElement("div");
      text.setAttribute("role", "status");
      text.setAttribute("aria-live", "polite");
      shadow.append(style, text);
      toastHost._text = text;
      document.documentElement.append(toastHost);
      globalThis.NoiseWinstonTheme?.register(toastHost);
    }
    toastHost._text.textContent = String(message || "").slice(0, 350);
    toastHost._text.dataset.state = ["working", "ready", "error"].includes(state) ? state : "ready";
    toastHost.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastHost.hidden = true; }, state === "error" ? 8000 : 5000);
  }

  function pointerOnVideo(event, path) {
    if (path.some((node) => node instanceof HTMLVideoElement)) return true;
    try {
      return document.elementsFromPoint(event.clientX, event.clientY).some((node) => node instanceof HTMLVideoElement);
    } catch { return false; }
  }

  // 以 window 捕獲階段搶在網站之前處理。X 的播放器會取消右鍵並改顯示自己的選單，
  // 使 Chrome 選單與本外掛項目無法出現；指標在影片上時停止事件傳遞但不取消預設行為，
  // Chrome 選單便會照常顯示。按住 Shift 再按右鍵仍可使用 X 原本的選單。
  window.addEventListener("contextmenu", (event) => {
    const path = event.composedPath();
    const target = path.find((node) => node instanceof Element);
    context = target ? {
      target,
      path,
      x: event.clientX,
      y: event.clientY,
      at: Date.now(),
      pageUrl: location.href,
    } : null;
    if (target && X_HOSTS.has(location.hostname) && !event.shiftKey && pointerOnVideo(event, path)) {
      event.stopImmediatePropagation();
    }
  }, true);

  function isVisible(video) {
    if (!video?.isConnected || video.hidden || video.closest("[hidden],[aria-hidden='true'],[inert]")) return false;
    const box = video.getBoundingClientRect();
    const style = getComputedStyle(video);
    return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  }

  function topmostVideo(videos) {
    try {
      const top = document.elementsFromPoint(context.x, context.y).find((node) => videos.includes(node));
      if (top) return top;
    } catch { /* 無法判斷圖層時改比對來源。 */ }
    const sources = new Set(videos.map((video) => video.currentSrc || video.getAttribute("src") || ""));
    return sources.size === 1 && !sources.has("") ? videos[0] : null;
  }

  function selectVideo() {
    if (!context || Date.now() - context.at > 120000 || context.pageUrl !== location.href || !context.target.isConnected) {
      throw new Error("請在要複製的影片上重新按右鍵，再選「複製影片」。");
    }
    const direct = context.path.find((node) => node instanceof HTMLVideoElement);
    if (direct?.isConnected && isVisible(direct)) return direct;
    const post = context.target.closest("article,[role='article']");

    // Player overlays often receive the click. Walk only the clicked element's
    // ancestors; never choose the first video in the document or another post.
    for (let root = context.target; root && root !== document.body && root !== document.documentElement; root = root.parentElement) {
      const videos = [...root.querySelectorAll("video")].filter(isVisible);
      const isPost = root.matches("article,[role='article']");
      if (!videos.length) {
        if (isPost) throw new Error("這篇貼文找不到已載入的影片，請直接在影片畫面上按右鍵。");
        continue;
      }
      const underPointer = videos.filter((video) => {
        const box = video.getBoundingClientRect();
        return context.x >= box.left && context.x <= box.right && context.y >= box.top && context.y <= box.bottom;
      });
      if (underPointer.length === 1) return underPointer[0];
      if (underPointer.length > 1) {
        // 播放器可能疊放多個 video（例如模糊背景或預載畫面）；取畫面最上層、也就是使用者看到的那一支。
        const topmost = topmostVideo(underPointer);
        if (topmost) return topmost;
      }
      if (underPointer.length > 1 || videos.length > 1) {
        throw new Error("這個位置有多支影片，請直接在要複製的影片畫面上按右鍵。");
      }
      // Without post semantics, require the pointer to be over the video.
      // A visually compact wrapper can still contain two different posts.
      if (isPost) return videos[0];
      if (post) continue;
      throw new Error("無法確定右鍵位置所屬的影片，請直接在影片畫面上按右鍵。");
    }
    throw new Error("這個右鍵位置找不到影片，請先讓影片載入，再直接在影片畫面上按右鍵。");
  }

  function xPermalink(anchor) {
    try {
      const href = anchor.getAttribute("href")?.trim();
      // 空連結、hash 與純 query 會繼承目前網址，不能拿來認定影片所屬貼文。
      if (!href || !/^(?:https:\/\/|\/)/i.test(href)) return null;
      const url = new URL(href, location.href);
      if (url.protocol !== "https:" || !X_HOSTS.has(url.hostname) || url.port || url.username || url.password) return null;
      const match = url.pathname.match(/^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]+)(?:\/video\/[1-9][0-9]*)?\/?$/);
      if (!match) return null;
      return { id: match[2], url: `https://x.com/${match[1]}/status/${match[2]}` };
    } catch { return null; }
  }

  function isQuotedRegion(element) {
    return element.matches("[data-testid='quoteTweet'],div[role='link']");
  }

  function scopedPostLinks(root, video, article) {
    const anchors = [...(root.matches("a[href]") ? [root] : []), ...root.querySelectorAll("a[href]")];
    const posts = new Map();
    for (const anchor of anchors) {
      if (anchor.closest("article,[role='article']") !== article) continue;
      let belongsToOtherQuote = false;
      for (let parent = anchor.parentElement; parent && parent !== root; parent = parent.parentElement) {
        if (isQuotedRegion(parent) && !parent.contains(video)) { belongsToOtherQuote = true; break; }
      }
      if (belongsToOtherQuote) continue;
      const post = xPermalink(anchor);
      if (post && !posts.has(post.id)) posts.set(post.id, post.url);
    }
    return posts;
  }

  function findXPostUrl(video) {
    const article = video.closest("article,[role='article']");
    if (!article) throw new Error("無法確認這支 X 影片所屬的貼文，請開啟影片原始貼文後，再在影片上按右鍵。");
    // 影片直接位於永久連結內時，連結就是最接近的公開來源資訊。
    const wrappingLink = video.closest("a[href]");
    if (wrappingLink && article.contains(wrappingLink)) {
      const post = xPermalink(wrappingLink);
      if (post) return post.url;
    }
    // 引用貼文的可點擊區塊有自己的來源連結；先鎖定包含影片的最近區塊，
    // 避免採用外層貼文或旁邊另一張引用卡片的永久連結。
    for (let root = video.parentElement; root && root !== article; root = root.parentElement) {
      if (!isQuotedRegion(root)) continue;
      const posts = scopedPostLinks(root, video, article);
      if (posts.size === 1) return posts.values().next().value;
      if (posts.size > 1) throw new Error("這個 X 影片區塊包含多篇貼文，無法確認影片來源，請開啟影片原始貼文後再複製。");
      // 缺少來源連結的引用區塊不能改用外層貼文 ID。
      throw new Error("找不到這支引用影片的原始貼文連結，請開啟影片原始貼文後再複製。");
    }
    const posts = scopedPostLinks(article, video, article);
    if (posts.size === 1) return posts.values().next().value;
    if (posts.size > 1) throw new Error("這篇 X 貼文包含多個來源，無法確認引用影片所屬的貼文，請開啟影片原始貼文後再複製。");
    throw new Error("找不到這支 X 影片的貼文連結，請開啟影片原始貼文後，再在影片上按右鍵。");
  }

  function xPoster(video) {
    try {
      const value = video.poster || video.getAttribute("poster");
      if (!value) return "";
      const url = new URL(value, document.baseURI);
      return url.protocol === "https:" && url.hostname === "pbs.twimg.com" && !url.port && !url.username && !url.password ? url.href : "";
    } catch { return ""; }
  }

  function xStatusPath(url) {
    const match = url.pathname.match(/^\/([A-Za-z0-9_]{1,15})\/status\/([0-9]+)(?:\/(?:video|photo)\/[1-9][0-9]*)?\/?$/);
    return match ? `/${match[1]}/status/${match[2]}` : null;
  }

  function xPostFromLocation() {
    const path = xStatusPath(location);
    return path ? `https://x.com${path}` : null;
  }

  // 封面網址帶有影片的媒體 ID，可跨不同資料來源確認是同一支影片。
  function xMediaKey(poster) {
    try {
      const match = new URL(poster).pathname.match(/^\/(amplify_video_thumb|ext_tw_video_thumb|tweet_video_thumb)\/([A-Za-z0-9_-]+)/);
      return match ? { kind: match[1].replace(/_thumb$/, ""), id: match[2] } : null;
    } catch { return null; }
  }

  function xVideoShape(video) {
    const shape = {};
    if (Number.isFinite(video.duration) && video.duration > 0) shape.duration = video.duration;
    if (video.videoWidth > 0 && video.videoHeight > 0) Object.assign(shape, { width: video.videoWidth, height: video.videoHeight });
    return shape;
  }

  async function resolveXPage(postUrl, poster) {
    const key = xMediaKey(poster);
    let path;
    try {
      const url = new URL(postUrl);
      if (url.protocol === "https:" && X_HOSTS.has(url.hostname) && !url.port && !url.username && !url.password && !url.search && !url.hash) path = xStatusPath(url);
    } catch { /* 下方統一回報。 */ }
    if (!key || !path) throw new Error("缺少可比對的 X 貼文或影片封面。");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PAGE_TIMEOUT_MS);
    let html;
    try {
      // 不帶登入資訊時，X 會回傳含影片 MP4 版本的公開貼文頁；X 文章內的影片也在其中。
      const response = await fetch(location.origin + path, {
        credentials: "omit",
        cache: "no-store",
        headers: { Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`無法讀取 X 貼文頁面（HTTP ${response.status}）。`);
      html = await response.text();
      if (html.length > MAX_PAGE_CHARS) throw new Error("X 貼文頁面資料過大，無法解析影片。");
    } catch (error) {
      if (error?.name === "AbortError") throw new Error("讀取 X 貼文頁面逾時，請稍後重試。");
      if (error instanceof TypeError) throw new Error("目前無法連線取得 X 貼文頁面，請稍後重試。");
      throw error;
    } finally { clearTimeout(timer); }
    let best = null;
    for (const [raw] of html.matchAll(/https:\/\/video\.twimg\.com\/[^"'\s<>\\]+?\.mp4(?:\?[^"'\s<>\\]*)?/g)) {
      let url;
      try { url = new URL(raw.replace(/&amp;/g, "&")); } catch { continue; }
      const parts = url.pathname.split("/");
      const sameMedia = key.kind === "tweet_video"
        ? parts[1] === "tweet_video" && parts[2] === `${key.id}.mp4`
        : parts[1] === key.kind && parts[2] === key.id;
      if (!sameMedia) continue;
      const size = url.pathname.match(/\/(\d+)x(\d+)\//);
      const area = size ? Number(size[1]) * Number(size[2]) : 0;
      if (!best || area > best.area) best = { url: url.href, area };
    }
    if (!best) throw new Error("X 貼文頁面中找不到這支影片的 MP4 版本。");
    return { ok: true, url: best.url, pageUrl: `https://x.com${path}` };
  }

  function threadsPermalink(anchor) {
    try {
      const href = anchor.getAttribute("href")?.trim();
      if (!href || !/^(?:https:\/\/|\/)/i.test(href)) return null;
      const url = new URL(href, location.href);
      if (url.protocol !== "https:" || !THREADS_HOSTS.has(url.hostname) || url.port || url.username || url.password) return null;
      const match = url.pathname.match(THREADS_POST_PATH);
      return match ? { code: match[2], path: `/@${match[1]}/post/${match[2]}` } : null;
    } catch { return null; }
  }

  function findThreadsPost(video) {
    // 由影片往外找第一層帶有貼文永久連結的容器；不含此影片的其他貼文卡片連結不列入。
    for (let root = video.parentElement; root && root !== document.body && root !== document.documentElement; root = root.parentElement) {
      const posts = new Map();
      for (const anchor of root.querySelectorAll("a[href]")) {
        const card = anchor.closest("[data-pressable-container]");
        if (card && card !== root && root.contains(card) && !card.contains(video)) continue;
        const post = threadsPermalink(anchor);
        if (post && !posts.has(post.code)) posts.set(post.code, post);
      }
      if (posts.size === 1) return posts.values().next().value;
      if (posts.size > 1) throw new Error("這個位置包含多篇 Threads 貼文，無法確認影片來源，請開啟影片所在貼文後再試。");
    }
    throw new Error("找不到這支 Threads 影片所屬的貼文連結，請開啟影片所在貼文後再試。");
  }

  function threadsFileName(value) {
    try { return new URL(value, location.href).pathname.split("/").pop() || null; } catch { return null; }
  }

  // Threads 資料沒有影片長度欄位，但每支影片的 DASH 清單寫有總長度。
  function manifestDuration(manifest) {
    const match = typeof manifest === "string" && /mediaPresentationDuration="PT(?:([\d.]+)H)?(?:([\d.]+)M)?(?:([\d.]+)S)?"/.exec(manifest);
    if (!match) return null;
    const seconds = Number(match[1] || 0) * 3600 + Number(match[2] || 0) * 60 + Number(match[3] || 0);
    return seconds > 0 ? seconds : null;
  }

  function threadsVideosFromData(data, code) {
    const videos = new Map();
    const stack = [data];
    for (let visited = 0; stack.length && visited < 500000; visited++) {
      const node = stack.pop();
      if (!node || typeof node !== "object") continue;
      if (Array.isArray(node)) { for (const item of node) if (item && typeof item === "object") stack.push(item); continue; }
      if (node.code === code) {
        const carousel = Array.isArray(node.carousel_media) ? node.carousel_media : [];
        for (const media of [node, ...carousel]) {
          const versions = (Array.isArray(media?.video_versions) ? media.video_versions : [])
            .filter((version) => typeof version?.url === "string" && version.url.startsWith("https://"));
          if (!versions.length) continue;
          const key = String(media.pk ?? media.id ?? versions[0].url);
          const covers = new Set((Array.isArray(media.image_versions2?.candidates) ? media.image_versions2.candidates : [])
            .map((image) => threadsFileName(image?.url)).filter(Boolean));
          const duration = Number(media.video_duration) > 0 ? Number(media.video_duration) : manifestDuration(media.video_dash_manifest);
          if (!videos.has(key)) videos.set(key, { key, versions, covers, width: media.original_width, height: media.original_height, duration });
        }
      }
      for (const value of Object.values(node)) if (value && typeof value === "object") stack.push(value);
    }
    return [...videos.values()];
  }

  function threadsVideosInDocument(doc, code) {
    // Threads 頁面內嵌的貼文資料含 video_versions，即一般 MP4 版本；登入後播放器改用 blob 串流時仍會提供。
    const needle = `"code":"${code}"`;
    const videos = new Map();
    for (const script of doc.querySelectorAll('script[type="application/json"]')) {
      const text = script.textContent || "";
      if (!text.includes(needle) || !text.includes("video_versions")) continue;
      let data;
      try { data = JSON.parse(text); } catch { continue; }
      for (const video of threadsVideosFromData(data, code)) if (!videos.has(video.key)) videos.set(video.key, video);
    }
    return [...videos.values()];
  }

  async function fetchThreadsPost(post) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PAGE_TIMEOUT_MS);
    try {
      // 必須宣告接受 HTML；否則 Threads 只回傳不含貼文資料的頁面外殼。
      const response = await fetch(location.origin + post.path, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`無法讀取 Threads 貼文資料（HTTP ${response.status}），請重新整理頁面後再試。`);
      const html = await response.text();
      if (html.length > MAX_PAGE_CHARS) throw new Error("Threads 貼文頁面資料過大，無法解析影片。");
      return new DOMParser().parseFromString(html, "text/html");
    } catch (error) {
      if (error?.name === "AbortError") throw new Error("讀取 Threads 貼文資料逾時，請稍後重試。");
      if (error instanceof TypeError) throw new Error("目前無法連線取得 Threads 貼文資料，請稍後重試。");
      throw error;
    } finally { clearTimeout(timer); }
  }

  function threadsCoverMatches(videos, video) {
    // 輪播每一格都有封面圖，檔名與貼文資料的 image_versions2 相同；由影片往外找第一層能對應封面的範圍。
    for (let root = video.parentElement; root && root !== document.body && root !== document.documentElement; root = root.parentElement) {
      const names = new Set([...root.querySelectorAll("img")]
        .flatMap((img) => [img.currentSrc, img.getAttribute("src")]).filter(Boolean).map(threadsFileName).filter(Boolean));
      const matches = videos.filter((item) => [...item.covers].some((name) => names.has(name)));
      if (matches.length) return matches;
      if (root.matches("[data-pressable-container]")) break;
    }
    return [];
  }

  function chooseThreadsVideo(videos, video) {
    if (!videos.length) throw new Error("Threads 沒有提供這支影片的 MP4 版本，目前無法複製。");
    if (videos.length === 1) return videos[0];
    // 輪播貼文含多支影片：先比對右鍵位置的封面圖，再以長度與畫面比例縮小範圍；無法唯一確認就停止。
    const covered = threadsCoverMatches(videos, video);
    if (covered.length === 1) return covered[0];
    const ratio = video.videoWidth > 0 && video.videoHeight > 0 ? video.videoWidth / video.videoHeight : null;
    const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : null;
    const matches = (covered.length ? covered : videos).filter((item) => {
      if (ratio && item.width > 0 && item.height > 0 && Math.abs(item.width / item.height - ratio) / ratio > 0.03) return false;
      if (duration && item.duration > 0 && Math.abs(item.duration - duration) > 0.5) return false;
      return true;
    });
    if (matches.length === 1) return matches[0];
    throw new Error("這篇 Threads 貼文有多支影片，無法確認要複製哪一支。請先播放要複製的影片，再按右鍵。");
  }

  function bestThreadsVersion(versions) {
    const sized = versions.filter((version) => version.width > 0 && version.height > 0);
    if (!sized.length) return versions[0].url;
    return sized.sort((a, b) => b.width * b.height - a.width * a.height)[0].url;
  }

  async function resolveThreadsSource(video) {
    const post = findThreadsPost(video);
    let videos = threadsVideosInDocument(document, post.code);
    // 捲動或站內換頁載入的貼文不在原始頁面資料中，改讀該貼文頁。
    if (!videos.length) videos = threadsVideosInDocument(await fetchThreadsPost(post), post.code);
    const selected = chooseThreadsVideo(videos, video);
    return { ok: true, url: bestThreadsVersion(selected.versions), pageUrl: location.origin + post.path, title: document.title.slice(0, 200) };
  }

  async function getSource() {
    const video = selectVideo();
    const candidate = video.currentSrc || video.getAttribute("src") || video.querySelector("source[src]")?.getAttribute("src");
    if (!candidate) throw new Error("影片來源尚未載入，請先播放一下影片，再重新複製。");
    const url = new URL(candidate, document.baseURI);
    const isX = X_HOSTS.has(location.hostname);
    const needsResolver = url.protocol === "blob:" || (/^https?:$/.test(url.protocol) && /\.(m3u8|mpd)(?:$|[/?#])/i.test(url.pathname));
    if (needsResolver && THREADS_HOSTS.has(location.hostname)) return resolveThreadsSource(video);
    let xPostUrl;
    const pagePostUrl = isX ? xPostFromLocation() : null;
    if (isX) {
      try { xPostUrl = findXPostUrl(video); }
      catch (error) {
        // 影片檢視器與 X 文章中的影片沒有所屬貼文的連結，改用網址中的貼文；
        // 解析時仍以封面的媒體 ID 確認是同一支影片，對不上就停止。
        if (needsResolver && !(pagePostUrl && xMediaKey(xPoster(video)))) throw error;
        if (needsResolver) xPostUrl = pagePostUrl;
      }
    }
    if (isX && needsResolver && xPostUrl) {
      return { ok: true, url: url.href, pageUrl: location.href, title: document.title.slice(0, 200), xPostUrl, poster: xPoster(video),
        ...(pagePostUrl && pagePostUrl !== xPostUrl ? { xPageUrl: pagePostUrl } : {}), ...xVideoShape(video) };
    }
    if (url.protocol === "blob:") {
      throw new Error("這支影片使用串流播放（blob），目前版本僅支援可直接讀取的 MP4 影片。");
    }
    if (!/^https?:$/.test(url.protocol)) throw new Error("目前版本僅支援 HTTP 或 HTTPS 的 MP4 影片。");
    if (/\.(m3u8|mpd)(?:$|[/?#])/i.test(url.pathname)) {
      throw new Error("這支影片使用分段串流，目前版本尚未支援。");
    }
    return { ok: true, url: url.href, pageUrl: location.href, title: document.title.slice(0, 200),
      ...(isX ? { ...(xPostUrl ? { xPostUrl } : {}), poster: xPoster(video) } : {}) };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "VC_GET_SOURCE") {
      getSource().then(sendResponse, (error) => sendResponse({ ok: false, error: error.message || "無法取得影片來源。" }));
      return true;
    } else if (message?.type === "VC_RESOLVE_X_PAGE") {
      if (!X_HOSTS.has(location.hostname)) return;
      resolveXPage(message.postUrl, message.poster).then(sendResponse, (error) => sendResponse({ ok: false, error: error.message || "無法讀取 X 貼文頁面。" }));
      return true;
    } else if (message?.type === "VC_STATUS") {
      if (message.message) showStatus(message.message, message.state);
    }
  });
})();
