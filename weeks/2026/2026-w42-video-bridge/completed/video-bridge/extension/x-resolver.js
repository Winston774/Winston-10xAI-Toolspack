import { canonicalPage, isSourcePage, validateMediaUrl } from './policy.js';

export const SYNDICATION_ENDPOINT = 'https://cdn.syndication.twimg.com/tweet-result';
export const SYNDICATION_TIMEOUT_MS = 20_000;
export const MAX_SYNDICATION_JSON_BYTES = 2 * 1024 * 1024;

const X_PAGE_HOSTS = new Set(['x.com', 'www.x.com', 'twitter.com', 'www.twitter.com']);
const POST_PATH = /^\/[^/]+\/status\/(\d+)$/;

function postDetails(value) {
  if (typeof value !== 'string') throw new Error('缺少精確的 X 貼文網址。');
  let url;
  try { url = new URL(value); } catch { throw new Error('X 貼文網址格式無效。'); }
  if (url.protocol !== 'https:' || !X_PAGE_HOSTS.has(url.hostname) || url.port || url.username || url.password || url.search || url.hash) {
    throw new Error('X 貼文網址必須是 HTTPS 的精確 /user/status/id 網址。');
  }
  const match = POST_PATH.exec(url.pathname);
  if (!match) throw new Error('X 貼文網址必須是精確的 /user/status/id 路徑。');
  return { id: match[1], canonical: url.origin + url.pathname };
}

function syndicationToken(id) {
  return ((Number(id) / 1e15) * Math.PI).toString(36).replace(/(0+|\.)/g, '');
}

function isBlobOrPlaylist(value) {
  if (typeof value !== 'string' || !value) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'blob:' || (url.protocol === 'https:' && /\.(?:m3u8|mpd)(?:$|\/)/i.test(url.pathname));
  } catch {
    return false;
  }
}

function responseLength(response) {
  const value = response?.headers?.get?.('content-length');
  if (value === null || value === undefined) return null;
  const length = Number(value);
  if (!Number.isSafeInteger(length) || length < 0) throw new Error('X 回傳的影片資料不完整，請重新整理貼文後再試。');
  if (length > MAX_SYNDICATION_JSON_BYTES) throw new Error('X 回傳的影片資料超過大小上限。');
  return length;
}

async function readJsonLimited(response) {
  responseLength(response);
  if (!response?.body?.getReader) throw new Error('X 沒有提供可讀取的公開影片資料。');
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      if (!(part.value instanceof Uint8Array)) throw new Error('X 回傳的影片資料格式已改變，暫時無法解析。');
      total += part.value.byteLength;
      if (total > MAX_SYNDICATION_JSON_BYTES) throw new Error('X 回傳的影片資料超過大小上限。');
      chunks.push(part.value);
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    try {
      return JSON.parse(new TextDecoder().decode(bytes));
    } catch {
      throw new Error('X 回傳的影片資料格式已改變，暫時無法解析。');
    }
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  }
}

function mediaIdFromUrl(value, kind = 'poster') {
  if (typeof value !== 'string') return null;
  let pathname;
  try { pathname = new URL(value).pathname; } catch { return null; }
  const names = kind === 'poster'
    ? 'amplify_video_thumb|ext_tw_video_thumb|tweet_video_thumb'
    : 'amplify_video|amplify_video_thumb|ext_tw_video|ext_tw_video_thumb|tweet_video|tweet_video_thumb';
  const match = new RegExp(`/(?:${names})/([^/]+)(?:/|$)`, 'i').exec(pathname);
  return match?.[1]?.replace(/\.(?:jpe?g|png|webp|mp4)$/i, '') || null;
}

function normalizedThumbnail(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:') return null;
    return `${url.origin.toLowerCase()}${url.pathname.replace(/\/+$/, '')}`;
  } catch { return null; }
}

function mediaIdentity(media) {
  const ids = new Set();
  for (const value of [media?.id_str, media?.id]) {
    if (typeof value === 'string' || typeof value === 'number') ids.add(String(value));
  }
  const urls = new Set();
  for (const value of [media?.media_url_https, media?.media_url, media?.thumbnail_url, media?.poster]) {
    const normalized = normalizedThumbnail(value);
    if (normalized) urls.add(normalized);
    const id = mediaIdFromUrl(value, 'poster');
    if (id) ids.add(id);
  }
  for (const variant of media?.video_info?.variants || []) {
    const id = mediaIdFromUrl(variant?.url, 'media');
    if (id) ids.add(id);
  }
  return { ids, urls };
}

function mediaMatchesPoster(media, poster) {
  const identity = mediaIdentity(media);
  const posterId = mediaIdFromUrl(poster, 'poster');
  if (posterId && identity.ids.has(posterId)) return true;
  const posterUrl = normalizedThumbnail(poster);
  return Boolean(posterUrl && identity.urls.has(posterUrl));
}

function playerShape(candidate) {
  const duration = Number(candidate?.duration);
  const width = Number(candidate?.width);
  const height = Number(candidate?.height);
  return {
    duration: Number.isFinite(duration) && duration > 0 ? duration : null,
    ratio: Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0 ? width / height : null,
  };
}

function mediaMatchesShape(media, shape) {
  const millis = Number(media?.video_info?.duration_millis);
  if (shape.duration && Number.isFinite(millis) && millis > 0 && Math.abs(millis / 1000 - shape.duration) > 1) return false;
  const [width, height] = Array.isArray(media?.video_info?.aspect_ratio) ? media.video_info.aspect_ratio.map(Number) : [];
  if (shape.ratio && width > 0 && height > 0 && Math.abs(width / height - shape.ratio) / shape.ratio > 0.03) return false;
  return true;
}

function validVariants(media, sourcePage) {
  if (media?.type !== 'video' && media?.type !== 'animated_gif') return [];
  if (!Array.isArray(media?.video_info?.variants)) return [];
  const variants = [];
  for (const variant of media.video_info.variants) {
    if (variant?.content_type !== 'video/mp4' || typeof variant.url !== 'string') continue;
    try {
      const url = validateMediaUrl(variant.url, sourcePage);
      const bitrate = Number.isFinite(variant.bitrate) && variant.bitrate >= 0 ? variant.bitrate : null;
      variants.push({ url, bitrate });
    } catch {
      // Invalid hosts and playlists are filtered out before selection.
    }
  }
  return variants;
}

function chooseVariant(media, variants) {
  const rated = variants.filter((variant) => Number.isFinite(variant.bitrate));
  if (rated.length) {
    rated.sort((a, b) => b.bitrate - a.bitrate);
    return rated[0];
  }
  if (media?.type === 'animated_gif' && variants.length === 1) return variants[0];
  throw new Error('這支影片缺少可判定畫質的 MP4 版本，暫時無法下載。');
}

function rootMedia(tweet) {
  if (Array.isArray(tweet?.mediaDetails) && tweet.mediaDetails.length) return tweet.mediaDetails;
  if (Array.isArray(tweet?.extended_entities?.media)) return tweet.extended_entities.media;
  if (Array.isArray(tweet?.mediaDetails)) return tweet.mediaDetails;
  return [];
}

async function resolveViaSyndication(candidate, post, sourcePage, fetchImpl) {
  const endpoint = new URL(SYNDICATION_ENDPOINT);
  endpoint.searchParams.set('id', post.id);
  endpoint.searchParams.set('token', syndicationToken(post.id));
  endpoint.searchParams.set('lang', 'en');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SYNDICATION_TIMEOUT_MS);
  try {
    const response = await fetchImpl(endpoint.href, {
      credentials: 'omit',
      redirect: 'error',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (response?.status !== 200) throw new Error(`無法取得 X 公開影片資料（HTTP ${response?.status ?? 'unknown'}），請重新整理貼文後再試。`);
    const tweet = await readJsonLimited(response);
    if (typeof tweet?.id_str !== 'string' || tweet.id_str !== post.id) throw new Error('X 回傳的貼文 ID 與所選貼文不一致，請重新開啟原始貼文。');

    // Keep every root video while deciding identity. Filtering unavailable MP4
    // variants first could silently select another video from the same post.
    const entries = rootMedia(tweet)
      .filter((media) => media?.type === 'video' || media?.type === 'animated_gif')
      .map((media) => ({ media, variants: validVariants(media, sourcePage) }));
    if (!entries.length) throw new Error('這篇 X 貼文沒有可取得的 MP4 影片，請確認已開啟影片原始貼文。');

    let selected;
    if (candidate.poster) {
      const matches = entries.filter((entry) => mediaMatchesPoster(entry.media, candidate.poster));
      if (matches.length !== 1) throw new Error(matches.length ? '影片封面對應到多支影片，無法確認所選影片。' : '影片封面無法對應到這篇貼文的公開影片，請開啟原始貼文後再試。');
      selected = matches[0];
    } else if (entries.length === 1) {
      selected = entries[0];
    } else {
      // 沒有封面時，以播放器回報的長度與畫面比例比對；仍無法唯一確認就停止。
      const shape = playerShape(candidate);
      const matches = shape.duration || shape.ratio ? entries.filter((entry) => mediaMatchesShape(entry.media, shape)) : [];
      if (matches.length !== 1) throw new Error('貼文包含多支影片，缺少封面資訊而無法確認所選影片，請播放影片後重試。');
      selected = matches[0];
    }
    if (!selected.variants.length) throw new Error('選定影片沒有可用的 MP4 版本，無法下載此串流。');
    return { ...candidate, url: chooseVariant(selected.media, selected.variants).url, pageUrl: post.canonical };
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error('X 影片資料讀取逾時，請稍後重試。');
    if (error instanceof TypeError) throw new Error('目前無法連線取得 X 公開影片資料，請稍後重試。');
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function resolveXSource(candidate, { fetchImpl = fetch } = {}) {
  if (!candidate || typeof candidate !== 'object') throw new Error('影片來源候選資料無效。');
  if (!isSourcePage(candidate.pageUrl)) throw new Error('來源頁面不在支援範圍。');

  const hasPost = candidate.xPostUrl !== undefined && candidate.xPostUrl !== null && candidate.xPostUrl !== '';
  const isX = X_PAGE_HOSTS.has(new URL(candidate.pageUrl).hostname);
  if (hasPost && !isX) throw new Error('只有 X 來源頁面可以解析 X 貼文影片。');
  const post = hasPost ? postDetails(candidate.xPostUrl) : null;
  const selectedPage = post?.canonical || canonicalPage(candidate.pageUrl);
  const value = candidate.url;

  if (typeof value === 'string' && value && !isBlobOrPlaylist(value)) {
    const url = validateMediaUrl(value, candidate.pageUrl);
    return { ...candidate, url, pageUrl: selectedPage };
  }
  if (!post || !isX) throw new Error('blob 或分段串流需要精確的 X 貼文網址才能解析。');
  return resolveViaSyndication(candidate, post, candidate.pageUrl, fetchImpl);
}
