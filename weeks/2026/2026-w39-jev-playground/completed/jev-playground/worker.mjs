const JEV_ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
const LIMIT = 262144;
const securityHeaders = {
  'cache-control': 'no-store', 'referrer-policy': 'no-referrer',
  'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY',
  'permissions-policy': 'camera=(), microphone=(), geolocation=()',
  'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
};
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { ...securityHeaders, 'content-type': 'application/json; charset=utf-8' } });
async function readBounded(stream, limit) {
  if (!stream) throw new Error('empty');
  const reader = stream.getReader(); const chunks = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.byteLength; if (size > limit) { await reader.cancel(); throw new Error('large'); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return new TextDecoder().decode(bytes);
  } finally { reader.releaseLock(); }
}
function validPayload(body) {
  return body && body.model === 'jev-latest' && body.state &&
    Array.isArray(body.state.board) && body.state.board.length === 20 &&
    body.state.board.every(row => typeof row === 'string' && /^[.IOTSZJLG]{10}$/.test(row)) &&
    body.questions && typeof body.questions === 'object' && !Array.isArray(body.questions) &&
    Object.keys(body.questions).length > 0 && Object.keys(body.questions).length <= 8 &&
    Object.values(body.questions).every(q => q && ['choice', 'noul'].includes(q.type) &&
      typeof q.instructions === 'string' && q.instructions.length <= 2000 && q.criteria && typeof q.criteria === 'object');
}
function cleanResult(result, questions) {
  const answers = {};
  for (const [id, question] of Object.entries(questions)) {
    const answer = result?.answers?.[id];
    if (question.type === 'noul') answers[id] = { type: 'noul', noul: typeof answer?.noul === 'number' ? answer.noul : null };
    else answers[id] = {
      type: 'choice', choice: Object.hasOwn(question.criteria, answer?.choice) ? answer.choice : null,
      probabilities: Object.fromEntries(Object.keys(question.criteria).map(option => [option, typeof answer?.probabilities?.[option] === 'number' ? answer.probabilities[option] : null])),
    };
  }
  const tokens = value => Number.isFinite(value) && value >= 0 ? value : 0;
  return { model: 'jev-latest', answers, usage: { input_tokens: tokens(result?.usage?.input_tokens), output_tokens: tokens(result?.usage?.output_tokens) } };
}

// Stateless: no bindings, sessions, cache writes, logging, or retained credential variables.
export function createWorker(assets, upstreamFetch = fetch) {
  return {
    async fetch(request) {
      const url = new URL(request.url);
      if (url.pathname === '/api/jev') {
        if (request.method !== 'POST') return json({ error: 'METHOD_NOT_ALLOWED' }, 405);
        if (request.headers.get('origin') !== url.origin || request.headers.get('sec-fetch-site') === 'cross-site') return json({ error: 'ORIGIN_NOT_ALLOWED' }, 403);
        if (!(request.headers.get('content-type') || '').toLowerCase().startsWith('application/json')) return json({ error: 'JSON_REQUIRED' }, 415);
        const authorization = request.headers.get('authorization') || '';
        if (!/^Bearer [^\s]{1,4096}$/.test(authorization)) return json({ error: 'KEY_REQUIRED' }, 401);
        let body;
        try { body = JSON.parse(await readBounded(request.body, LIMIT)); } catch { return json({ error: 'INVALID_REQUEST' }, 400); }
        if (!validPayload(body)) return json({ error: 'INVALID_REQUEST' }, 400);
        try {
          const aborter = new AbortController();
          const timeout = setTimeout(() => aborter.abort(), 35000);
          // Cloudflare exposes incoming Request.signal only with enable_request_signal.
          // The relay must still work without it; our own upstream timeout remains active.
          const incomingSignal = request.signal;
          const cancel = () => aborter.abort();
          try {
            incomingSignal?.addEventListener('abort', cancel, { once: true });
            if (incomingSignal?.aborted) aborter.abort();
            const result = await upstreamFetch(JEV_ENDPOINT, {
              // Cloudflare supports manual/follow only. Manual keeps credentials at the fixed origin.
              method: 'POST', redirect: 'manual', signal: aborter.signal,
              headers: { authorization, 'content-type': 'application/json' },
              body: JSON.stringify({ model: 'jev-latest', state: body.state, questions: body.questions }),
            });
            // Never reflect upstream headers, exception text, or error bodies.
            if (!result.ok) { await result.body?.cancel(); return json({ error: 'JEV_REQUEST_FAILED' }, [400,401,403,429].includes(result.status) ? result.status : 502); }
            const raw = JSON.parse(await readBounded(result.body, 2_000_000));
            return json(cleanResult(raw, body.questions));
          } finally { clearTimeout(timeout); incomingSignal?.removeEventListener('abort', cancel); }
        } catch { return json({ error: 'JEV_UNAVAILABLE' }, 502); }
      }
      if (!['GET', 'HEAD'].includes(request.method)) return json({ error: 'METHOD_NOT_ALLOWED' }, 405);
      const asset = assets[url.pathname];
      if (!asset) return json({ error: 'NOT_FOUND' }, 404);
      return new Response(request.method === 'HEAD' ? null : asset.body, { headers: { ...securityHeaders, 'content-type': asset.type } });
    },
  };
}
