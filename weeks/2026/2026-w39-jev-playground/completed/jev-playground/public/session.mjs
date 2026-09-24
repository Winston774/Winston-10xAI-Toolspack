import { createGame, resetGame, applyPlacement } from './lib/engine.mjs';
import { createJevProvider, decide, MODEL } from './lib/brain.mjs';

const emptyStats = () => ({ calls: 0, inputTokens: 0, outputTokens: 0, vetos: 0, decisions: 0 });
const fail = (message, code) => Object.assign(new Error(message), { code });

// One closure per browser tab. No cookies, browser storage, server session, or key export.
export function createSession({ fetchImpl = fetch, previewDelayMs = 220 } = {}) {
  let key = '', game = createGame({ seed: 42, scenario: 'holes' });
  let lastDecision = null, lastError = null, history = [], stats = emptyStats();
  let epoch = 0, active = null, controller = null;
  const listeners = new Set();
  const snapshot = () => structuredClone({ game, busy: Boolean(active), lastDecision, lastError, recentDecisions: history, sessionStats: stats });
  function cancel() { epoch++; controller?.abort(); }
  function dispose() { key = ''; cancel(); }

  // Keep only known numeric answer fields. Upstream debug text and headers never enter a trace.
  function cleanResponse(result, request) {
    const answers = {};
    for (const [id, question] of Object.entries(request.questions)) {
      const answer = result?.answers?.[id];
      if (question.type === 'noul') answers[id] = { type: 'noul', noul: answer?.noul };
      else answers[id] = {
        type: 'choice', choice: Object.hasOwn(question.criteria, answer?.choice) ? answer.choice : null,
        probabilities: Object.fromEntries(Object.keys(question.criteria).map(option => [option, answer?.probabilities?.[option]])),
      };
    }
    const tokens = value => Number.isFinite(value) && value >= 0 ? value : 0;
    return { model: MODEL, answers, usage: { input_tokens: tokens(result?.usage?.input_tokens), output_tokens: tokens(result?.usage?.output_tokens) } };
  }

  async function execute({ mode, version }) {
    if (version !== game.version) throw fail('棋盤已更新，請重試。', 'STALE_RESULT');
    if (!['preview', 'live'].includes(mode)) throw fail('請選擇有效的執行模式。', 'INVALID_MODE');
    if (mode === 'live' && !key) throw fail('請先設定你自己的 TypeSafe API Key。', 'KEY_REQUIRED');
    const ticket = epoch;
    const aborter = new AbortController(); controller = aborter; lastError = null;
    const provider = mode === 'live' ? createJevProvider(key, { fetchImpl }) : null;
    try {
      const decision = await decide({
        game, mode, signal: aborter.signal, previewDelayMs,
        provider: provider && (async (request, options) => {
          stats.calls++;
          const response = cleanResponse(await provider(request, options), request);
          if (ticket === epoch) { stats.inputTokens += response.usage.input_tokens; stats.outputTokens += response.usage.output_tokens; }
          return response;
        }),
        onPhase: event => { if (ticket === epoch) for (const listen of listeners) listen(event); },
      });
      if (ticket !== epoch || aborter.signal.aborted) throw fail('已停止本次決策。', 'STOPPED');
      game = applyPlacement(game, decision.selectedPlacementId, version);
      lastDecision = decision; history.push(decision); if (history.length > 300) history.shift();
      stats.decisions++; stats.vetos += decision.proposals.filter(p => p.veto).length;
      return structuredClone({ game, decision });
    } catch (error) {
      if (ticket !== epoch || aborter.signal.aborted) throw fail('已停止本次決策。', 'STOPPED');
      lastError = { message: error.message, code: error.code || 'DECISION_ERROR' };
      throw error;
    } finally { if (controller === aborter) controller = null; }
  }

  return {
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    dispose,
    export() {
      return structuredClone({ schemaVersion: 1, exportedAt: new Date().toISOString(), game, sessionStats: stats,
        decisions: history, retention: { maxDecisions: 300, retained: history.length, total: stats.decisions },
        privacy: '此檔案不含 API Key。遊戲與紀錄僅暫留於此瀏覽器分頁。' });
    },
    async request(path, body) {
      if (path === '/api/status') return { keyConfigured: Boolean(key), model: MODEL };
      if (path === '/api/state') return snapshot();
      if (path === '/api/config') {
        const next = typeof body?.apiKey === 'string' ? body.apiKey.trim() : '';
        if (next.length > 4096 || /\s/.test(next)) throw fail('API Key 格式不正確，請重新貼上。', 'INVALID_KEY');
        cancel(); key = next; await active?.catch(() => {});
        return { keyConfigured: Boolean(key), model: MODEL };
      }
      if (path === '/api/stop') { cancel(); await active?.catch(() => {}); return snapshot(); }
      if (path === '/api/reset') {
        cancel(); await active?.catch(() => {});
        game = resetGame(game, { seed: body?.seed ?? 42, scenario: body?.scenario ?? 'holes' });
        lastDecision = lastError = null; history = []; stats = emptyStats(); return snapshot();
      }
      if (path === '/api/step') {
        if (active) throw fail('目前正在進行決策。', 'BUSY');
        const task = execute(body); active = task;
        try { return await task; } finally { if (active === task) active = null; }
      }
      throw fail('無法辨識的操作。', 'NOT_FOUND');
    },
  };
}
