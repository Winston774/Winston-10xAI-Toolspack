import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveXSource } from '../extension/x-resolver.js';

const POST_ID = '2101369117496521042';
const POST_URL = `https://x.com/heystefan_/status/${POST_ID}`;
const FEED_URL = 'https://x.com/home?ref=video';
const POSTER = 'https://pbs.twimg.com/amplify_video_thumb/2101367981486051328/img/poster.jpg?name=small';
const LOW = 'https://video.twimg.com/amplify_video/2101367981486051328/vid/640x360/low.mp4?tag=12';
const HIGH = 'https://video.twimg.com/amplify_video/2101367981486051328/vid/1280x720/high.mp4?tag=12';

function responseJson(value, init = {}) {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'content-type': 'application/json' },
    ...init,
  });
}

function rootTweet(mediaDetails, extra = {}) {
  return { id_str: POST_ID, mediaDetails, ...extra };
}

function videoMedia(id, poster, variants) {
  return {
    type: 'video',
    id_str: id,
    media_url_https: poster,
    video_info: { variants },
  };
}

test('direct HTTPS MP4 is returned after policy validation without syndication fetch', async () => {
  const result = await resolveXSource({ pageUrl: FEED_URL, url: HIGH, poster: '' }, {
    fetchImpl: async () => { throw new Error('direct candidates must not fetch syndication'); },
  });

  assert.equal(result.url, HIGH);
  assert.equal(result.pageUrl, 'https://x.com/home');
});

test('a Threads source cannot use an X post hint to trigger the X resolver', async () => {
  let fetched = false;
  await assert.rejects(resolveXSource({ pageUrl: 'https://www.threads.com/', xPostUrl: POST_URL, url: 'blob:https://www.threads.com/player' }, {
    fetchImpl: async () => { fetched = true; throw new Error('unexpected fetch'); },
  }), /只有 X/);
  assert.equal(fetched, false);
});

test('a second video without MP4 remains ambiguous and cannot select a different downloadable video', async () => {
  const media = [
    videoMedia('111', 'https://pbs.twimg.com/ext_tw_video_thumb/111/a.jpg', [{ content_type: 'video/mp4', bitrate: 100, url: 'https://video.twimg.com/ext_tw_video/111/first.mp4' }]),
    videoMedia('222', 'https://pbs.twimg.com/ext_tw_video_thumb/222/b.jpg', [{ content_type: 'application/x-mpegURL', url: 'https://video.twimg.com/ext_tw_video/222/b.m3u8' }]),
  ];
  const candidate = { pageUrl: POST_URL, xPostUrl: POST_URL, url: 'blob:https://x.com/second-player' };
  await assert.rejects(resolveXSource(candidate, { fetchImpl: async () => responseJson(rootTweet(media)) }), /多支影片/);
  await assert.rejects(resolveXSource({ ...candidate, poster: 'https://pbs.twimg.com/ext_tw_video_thumb/222/b.jpg' }, {
    fetchImpl: async () => responseJson(rootTweet(media)),
  }), /選定影片沒有/);
});

test('GIF poster and MP4 identify the same media despite their different file extensions', async () => {
  const url = 'https://video.twimg.com/tweet_video/abcDEF.mp4';
  const result = await resolveXSource({ pageUrl: POST_URL, xPostUrl: POST_URL, url: 'blob:https://x.com/player', poster: 'https://pbs.twimg.com/tweet_video_thumb/abcDEF.jpg' }, {
    fetchImpl: async () => responseJson(rootTweet([{ type: 'animated_gif', video_info: { variants: [{ content_type: 'video/mp4', url }] } }])),
  });
  assert.equal(result.url, url);
});

test('blob candidate resolves the fixed syndication endpoint and picks highest bitrate root video', async () => {
  let request;
  const result = await resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, {
    fetchImpl: async (input, init) => {
      request = { input: String(input), init };
      return responseJson(rootTweet([
        videoMedia('2101367981486051328', POSTER, [
          { content_type: 'video/mp4', bitrate: 480000, url: LOW },
          { content_type: 'video/mp4', bitrate: 1200000, url: HIGH },
          { content_type: 'application/x-mpegURL', url: 'https://video.twimg.com/a.m3u8' },
        ]),
      ]));
    },
  });

  assert.equal(result.url, HIGH);
  assert.equal(result.pageUrl, POST_URL);
  assert.match(request.input, /^https:\/\/cdn\.syndication\.twimg\.com\/tweet-result\?/);
  const query = new URL(request.input).searchParams;
  assert.equal(query.get('id'), POST_ID);
  assert.equal(query.get('token'), '53dn8xlsiwx');
  assert.equal(query.get('lang'), 'en');
  assert.equal(request.init.credentials, 'omit');
  assert.equal(request.init.redirect, 'error');
  assert.equal(request.init.cache, 'no-store');
  assert.ok(request.init.signal instanceof AbortSignal);
});

test('HLS candidate follows syndication resolution, while foreign HTTPS is rejected by policy', async () => {
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return responseJson(rootTweet([
      videoMedia('2101367981486051328', POSTER, [{ content_type: 'video/mp4', bitrate: 10, url: HIGH }]),
    ]));
  };
  const result = await resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'https://video.twimg.com/stream/master.m3u8' }, { fetchImpl });
  assert.equal(result.url, HIGH);
  assert.equal(calls, 1);
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'https://example.com/video.mp4' }, { fetchImpl }),
    /支援媒體主機/,
  );
});

test('response id_str must be the requested string id', async () => {
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, {
      fetchImpl: async () => responseJson(rootTweet([], { id_str: Number(POST_ID) })),
    }),
    /貼文 ID.*不一致/,
  );
});

test('only root mediaDetails or extended_entities.media are considered; quoted descendants do not count', async () => {
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, {
      fetchImpl: async () => responseJson(rootTweet(undefined, {
        quoted_tweet: { id_str: POST_ID, mediaDetails: [videoMedia('2101367981486051328', POSTER, [{ content_type: 'video/mp4', bitrate: 1, url: HIGH }])] },
      })),
    }),
    /沒有可取得的 MP4/,
  );
});

test('poster media id mismatch fails even when there is one video', async () => {
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: 'https://pbs.twimg.com/amplify_video_thumb/999999/img/other.jpg', url: 'blob:https://x.com/player' }, {
      fetchImpl: async () => responseJson(rootTweet([
        videoMedia('2101367981486051328', POSTER, [{ content_type: 'video/mp4', bitrate: 1, url: HIGH }]),
      ])),
    }),
    /封面.*對應/,
  );
});

test('poster selects one media among multiple root videos and never defaults to the first', async () => {
  const otherPoster = 'https://pbs.twimg.com/amplify_video_thumb/777/img/other.jpg';
  const otherUrl = 'https://video.twimg.com/amplify_video/777/vid/640x360/other.mp4';
  const result = await resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, {
    fetchImpl: async () => responseJson(rootTweet([
      videoMedia('777', otherPoster, [{ content_type: 'video/mp4', bitrate: 900000, url: otherUrl }]),
      videoMedia('2101367981486051328', POSTER, [{ content_type: 'video/mp4', bitrate: 200000, url: LOW }, { content_type: 'video/mp4', bitrate: 300000, url: HIGH }]),
    ])),
  });
  assert.equal(result.url, HIGH);
});

test('multiple root videos without a precise poster match fail clearly', async () => {
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: '', url: 'blob:https://x.com/player' }, {
      fetchImpl: async () => responseJson(rootTweet([
        videoMedia('777', 'https://pbs.twimg.com/ext_tw_video_thumb/777/other.jpg', [{ content_type: 'video/mp4', bitrate: 1, url: LOW }]),
        videoMedia('888', 'https://pbs.twimg.com/ext_tw_video_thumb/888/other.jpg', [{ content_type: 'video/mp4', bitrate: 2, url: HIGH }]),
      ])),
    }),
    /多支|唯一|poster/,
  );
});

test('animated GIF may use its single MP4 variant without bitrate', async () => {
  const result = await resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, {
    fetchImpl: async () => responseJson(rootTweet([{
      type: 'animated_gif',
      media_url_https: POSTER,
      video_info: { variants: [{ content_type: 'video/mp4', url: HIGH }] },
    }])),
  });
  assert.equal(result.url, HIGH);
});

test('oversized JSON response is rejected before parsing the body', async () => {
  let bodyRead = false;
  const response = {
    status: 200,
    ok: true,
    headers: new Headers({ 'content-length': String(2 * 1024 * 1024 + 1) }),
    body: { getReader() { bodyRead = true; throw new Error('body should not be read'); } },
  };
  await assert.rejects(
    resolveXSource({ pageUrl: FEED_URL, xPostUrl: POST_URL, poster: POSTER, url: 'blob:https://x.com/player' }, { fetchImpl: async () => response }),
    /資料超過大小上限/,
  );
  assert.equal(bodyRead, false);
});

test('without a poster, player duration and aspect ratio select exactly one root video', async () => {
  const media = [
    { ...videoMedia('777', 'https://pbs.twimg.com/ext_tw_video_thumb/777/a.jpg', [{ content_type: 'video/mp4', bitrate: 1, url: LOW }]), video_info: { duration_millis: 12000, aspect_ratio: [16, 9], variants: [{ content_type: 'video/mp4', bitrate: 1, url: LOW }] } },
    { ...videoMedia('888', 'https://pbs.twimg.com/ext_tw_video_thumb/888/b.jpg', [{ content_type: 'video/mp4', bitrate: 2, url: HIGH }]), video_info: { duration_millis: 30500, aspect_ratio: [16, 9], variants: [{ content_type: 'video/mp4', bitrate: 2, url: HIGH }] } },
  ];
  const base = { pageUrl: FEED_URL, xPostUrl: POST_URL, poster: '', url: 'blob:https://x.com/player' };
  const fetchImpl = async () => responseJson(rootTweet(media));
  assert.equal((await resolveXSource({ ...base, duration: 30.4, width: 1280, height: 720 }, { fetchImpl })).url, HIGH);
  assert.equal((await resolveXSource({ ...base, duration: 12.1 }, { fetchImpl })).url, LOW);
  await assert.rejects(resolveXSource({ ...base, width: 1280, height: 720 }, { fetchImpl }), /多支影片/);
  await assert.rejects(resolveXSource({ ...base, duration: 20 }, { fetchImpl }), /多支影片/);
});
