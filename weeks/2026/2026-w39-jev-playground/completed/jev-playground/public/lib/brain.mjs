import { enumeratePlacements, boardFeatures } from './engine.mjs';

export const MODEL = 'jev-latest';
export const ENDPOINT = 'https://api.typesafe.ai/v1/systemone';
export const MOTIVES = Object.freeze([
  { id: 'survive', label: '生存', goal: 'Keep the stack low and avoid top-out; prioritize immediate survival.' },
  { id: 'cleanup', label: '整地', goal: 'Reduce holes and surface bumpiness without creating inaccessible cavities.' },
  { id: 'build', label: '堆疊', goal: 'Build a stable surface and useful wells for the visible next pieces.' },
  { id: 'clear', label: '消行', goal: 'Clear available lines efficiently while keeping the resulting board safe.' },
  { id: 'spin', label: '旋轉機會', goal: 'Consider useful rotated placements. These candidates use direct hard drop, so do not invent wall kicks or T-spin bonuses.' },
]);
export const THRESHOLDS = Object.freeze({ activation: 0.5, veto: 0.65 });

export class BrainError extends Error {
  constructor(message, code = 'PROVIDER_ERROR') { super(message); this.name = 'BrainError'; this.code = code; }
}

function abortIfNeeded(signal) { if (signal?.aborted) throw signal.reason ?? new DOMException('已停止', 'AbortError'); }
function pause(ms, signal) {
  abortIfNeeded(signal);
  return new Promise((resolve, reject) => {
    const finish = () => { signal?.removeEventListener('abort', cancel); resolve(); };
    const timer = setTimeout(finish, ms);
    const cancel = () => { clearTimeout(timer); signal?.removeEventListener('abort', cancel); reject(signal.reason ?? new DOMException('已停止', 'AbortError')); };
    signal?.addEventListener('abort', cancel, { once: true });
  });
}
function probability(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) throw new BrainError(`模型回傳的 ${label} 機率無效。`, 'INVALID_RESPONSE');
  return value;
}
function noul(response, id) {
  const answer = response?.answers?.[id];
  if (answer?.type !== 'noul') throw new BrainError(`模型缺少 ${id} Noul 結果。`, 'INVALID_RESPONSE');
  return probability(answer.noul, id);
}
function choice(response, id, options) {
  const answer = response?.answers?.[id];
  if (answer?.type !== 'choice' || !options.includes(answer.choice)) throw new BrainError(`模型回傳的 ${id} 選項不合法。`, 'INVALID_RESPONSE');
  const distribution = Object.fromEntries(options.map(option => [option, probability(answer.probabilities?.[option], `${id}.${option}`)]));
  if (Math.abs(Object.values(distribution).reduce((a, b) => a + b, 0) - 1) > 0.02) throw new BrainError(`模型回傳的 ${id} 機率總和無效。`, 'INVALID_RESPONSE');
  if (distribution[answer.choice] + 1e-8 < Math.max(...Object.values(distribution))) throw new BrainError(`模型回傳的 ${id} 選項與最高機率不一致。`, 'INVALID_RESPONSE');
  return { selected: answer.choice, probabilities: distribution };
}
function normalizedDistribution(items, score) {
  const scored = items.map(item => [item.id, score(item)]);
  const max = Math.max(...scored.map(([, value]) => value));
  const weights = scored.map(([id, value]) => [id, Math.exp(Math.max(-40, (value - max) / 2))]);
  const total = weights.reduce((sum, [, weight]) => sum + weight, 0);
  return Object.fromEntries(weights.map(([id, weight]) => [id, weight / total]));
}
function selectedAnswer(distribution) {
  const selected = Object.keys(distribution).sort((a, b) => distribution[b] - distribution[a] || a.localeCompare(b))[0];
  return { type: 'choice', choice: selected, probabilities: distribution, confidence: distribution[selected] };
}
function heuristic(candidate) { return Number.isFinite(candidate.heuristic) ? candidate.heuristic : -candidate.features.aggregateHeight - candidate.features.holes * 8 - candidate.features.bumpiness + candidate.features.linesCleared * 10; }
function motiveScore(candidate, motiveId) {
  const f = candidate.features;
  const base = heuristic(candidate);
  if (motiveId === 'survive') return base - f.maxHeight * 1.5 - f.holes * 2;
  if (motiveId === 'cleanup') return base - f.holes * 5 - f.bumpiness;
  if (motiveId === 'build') return base - f.bumpiness * 0.8 + Math.min(f.wells ?? 0, 4) * 0.2;
  if (motiveId === 'clear') return base + f.linesCleared * 8;
  return base + (candidate.rotation ? 0.7 : 0);
}
function placementSummary(candidate) {
  return { id: candidate.id, rotation: candidate.rotation, x: candidate.x, y: candidate.y, cells: candidate.cells, features: candidate.features, heuristic: heuristic(candidate) };
}
function boardState(game, candidates) {
  return {
    rules: '10 columns x 20 rows. Board rows run top to bottom. Coordinates x=0..9,y=0..19. Dot is empty. Candidates are engine-validated direct hard drops. No hold, soft drop, wall-kick path, or T-spin scoring.',
    board: game.board.map(row => row.map(cell => cell ?? '.').join('')),
    current: game.current, next: game.next, score: game.score, lines: game.lines,
    features: boardFeatures(game.board), candidates: candidates.map(placementSummary),
  };
}

export function createJevProvider(apiKey, { fetchImpl = fetch, timeoutMs = 35000 } = {}) {
  if (typeof apiKey !== 'string' || !apiKey.trim()) throw new BrainError('請先設定 TypeSafe API Key。', 'KEY_REQUIRED');
  return async (request, { signal } = {}) => {
    abortIfNeeded(signal);
    const combined = signal ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs);
    let response;
    try {
      response = await fetchImpl(ENDPOINT, { method: 'POST', headers: { authorization: `Bearer ${apiKey}`, 'content-type': 'application/json' }, body: JSON.stringify(request), signal: combined, redirect: 'error' });
    } catch (error) {
      abortIfNeeded(signal);
      throw new BrainError(combined.aborted ? 'Jev 請求逾時，遊戲已暫停。' : '無法連線至 Jev，遊戲已暫停。', combined.aborted ? 'PROVIDER_TIMEOUT' : 'PROVIDER_NETWORK');
    }
    if (!response.ok) throw new BrainError(`Jev API 回傳 HTTP ${response.status}，遊戲已暫停。`, `PROVIDER_HTTP_${response.status}`);
    let text;
    try { text = await response.text(); } catch {
      abortIfNeeded(signal);
      throw new BrainError(combined.aborted ? 'Jev 回應逾時，遊戲已暫停。' : 'Jev 回應傳輸中斷，遊戲已暫停。', combined.aborted ? 'PROVIDER_TIMEOUT' : 'PROVIDER_NETWORK');
    }
    if (text.length > 2_000_000) throw new BrainError('Jev 回應超過允許大小。', 'INVALID_RESPONSE');
    try { return JSON.parse(text); } catch { throw new BrainError('Jev 回應不是有效 JSON。', 'INVALID_RESPONSE'); }
  };
}

/** Exactly three batch evaluations in live mode; preview performs zero network calls. */
export async function decide({ game, mode = 'preview', provider, signal, onPhase = () => {}, previewDelayMs = 220 }) {
  if (!['preview', 'live'].includes(mode)) throw new BrainError('模式不合法。', 'INVALID_MODE');
  if (mode === 'live' && typeof provider !== 'function') throw new BrainError('請先設定 TypeSafe API Key。', 'KEY_REQUIRED');
  const candidates = enumeratePlacements(game);
  if (game.gameOver || !candidates.length) throw new BrainError('遊戲已結束，沒有合法落點。', 'GAME_OVER');
  const start = performance.now();
  const state = boardState(game, candidates);
  const before = state.features;
  const baseline = [...candidates].sort((a, b) => heuristic(b) - heuristic(a) || a.id.localeCompare(b.id))[0];
  const rawTrace = [];
  const timings = {};
  let calls = 0;
  const usage = { inputTokens: 0, outputTokens: 0 };
  async function batch(phase, request, previewResponse) {
    abortIfNeeded(signal);
    onPhase({ phase, status: 'started', mode, version: game.version });
    const began = performance.now();
    let response;
    if (mode === 'live') { calls += 1; response = await provider(request, { signal }); }
    else { await pause(previewDelayMs, signal); response = previewResponse(); }
    abortIfNeeded(signal);
    const durationMs = Math.round(performance.now() - began);
    timings[phase] = durationMs;
    rawTrace.push({ phase, source: mode === 'live' ? 'jev-api' : 'local-deterministic-preview', request: structuredClone(request), response: structuredClone(response), durationMs });
    usage.inputTokens += Number.isFinite(response?.usage?.input_tokens) ? response.usage.input_tokens : 0;
    usage.outputTokens += Number.isFinite(response?.usage?.output_tokens) ? response.usage.output_tokens : 0;
    return response;
  }
  const sensesResponse = await batch('sense', {
    model: MODEL, state,
    questions: Object.fromEntries(MOTIVES.map(motive => [motive.id, {
      type: 'noul', instructions: `Should the ${motive.id} motive activate for this piece? ${motive.goal}`,
      criteria: { true: 'This motive is useful or urgent for the current board and piece.', false: 'This motive offers little value on this board.' },
    }])),
  }, () => ({ model: 'local-deterministic-preview', answers: {
    survive: { type: 'noul', noul: Math.min(0.98, 0.52 + before.maxHeight * 0.025) },
    cleanup: { type: 'noul', noul: Math.min(0.96, 0.2 + before.holes * 0.1 + before.bumpiness * 0.018) },
    build: { type: 'noul', noul: before.maxHeight < 13 ? 0.73 : 0.32 },
    clear: { type: 'noul', noul: candidates.some(c => c.features.linesCleared > 0) ? 0.94 : 0.16 },
    spin: { type: 'noul', noul: game.current === 'T' && before.bumpiness > 2 ? 0.63 : 0.25 },
  }, usage: { input_tokens: 0, output_tokens: 0 } }));
  const senses = MOTIVES.map(motive => { const p = noul(sensesResponse, motive.id); return { id: motive.id, label: motive.label, probability: p, active: p >= THRESHOLDS.activation }; });
  const active = senses.filter(sense => sense.active);
  onPhase({ phase: 'sense', status: 'completed', mode, version: game.version, detail: { senses } });
  const criteria = Object.fromEntries(candidates.map(c => [c.id, JSON.stringify(placementSummary(c))]));
  const motorQuestions = Object.fromEntries(active.map(sense => [sense.id, {
    type: 'choice', instructions: `Choose one legal placement for motive ${sense.id}. ${MOTIVES.find(m => m.id === sense.id).goal} Evaluate resulting features and upcoming pieces.`, criteria,
  }]));
  // Preserve the three-batch contract even if no perception crosses its threshold.
  if (!active.length) motorQuestions.baseline_check = { type: 'noul', instructions: 'All motives are inactive. Does the supplied local baseline remain a legal reference proposal?', criteria: { true: 'Baseline exists in the legal candidates.', false: 'Baseline is absent.' } };
  const motorResponse = await batch('motor', { model: MODEL, state: { ...state, senses, baselinePlacementId: baseline.id }, questions: motorQuestions }, () => ({
    model: 'local-deterministic-preview', usage: { input_tokens: 0, output_tokens: 0 },
    answers: active.length ? Object.fromEntries(active.map(sense => [sense.id, selectedAnswer(normalizedDistribution(candidates, c => motiveScore(c, sense.id)))])) : { baseline_check: { type: 'noul', noul: 1 } },
  }));
  if (!active.length) noul(motorResponse, 'baseline_check');
  const proposals = active.map(sense => {
    const result = choice(motorResponse, sense.id, candidates.map(c => c.id));
    const placement = candidates.find(c => c.id === result.selected);
    return { id: `proposal_${sense.id}`, motiveId: sense.id, label: sense.label, placementId: placement.id, placement: placementSummary(placement), motorProbability: result.probabilities[placement.id], probability: 0, veto: false };
  });
  proposals.push({ id: 'proposal_baseline', motiveId: 'baseline', label: '本機基準', placementId: baseline.id, placement: placementSummary(baseline), motorProbability: null, probability: 0, veto: false });
  onPhase({ phase: 'motor', status: 'completed', mode, version: game.version, detail: { proposals } });
  const judgeQuestions = {
    judge: { type: 'choice', instructions: 'Rank the proposals for strongest overall Tetris play: immediate survival, fewer holes, line clears, stable board, and next pieces. Return a distribution across ALL proposal IDs. Coaches assess veto in this same batch independently.', criteria: Object.fromEntries(proposals.map(p => [p.id, JSON.stringify({ motive: p.motiveId, placement: p.placement })])) },
    ...Object.fromEntries(proposals.map(p => [`veto_${p.id}`, {
      type: 'noul', instructions: `Should proposal ${p.id} be vetoed because it is clearly harmful? Compare before and resulting features; consider unnecessary holes, severe height increase, and loss of an obvious safe clear. Do not veto a merely nonoptimal but reasonable placement.`,
      criteria: { true: 'Clearly harmful placement that should not execute.', false: 'Safe enough to remain in consideration.' },
    }])),
  };
  const judgeResponse = await batch('judge', { model: MODEL, state: { ...state, senses, proposals }, questions: judgeQuestions }, () => ({
    model: 'local-deterministic-preview', usage: { input_tokens: 0, output_tokens: 0 },
    answers: {
      judge: selectedAnswer(normalizedDistribution(proposals, p => heuristic(p.placement))),
      ...Object.fromEntries(proposals.map(p => {
        const f = p.placement.features;
        const hazard = (f.holes - before.holes) * 0.23 + Math.max(0, f.maxHeight - 15) * 0.1;
        return [`veto_${p.id}`, { type: 'noul', noul: Math.min(0.97, Math.max(0.04, hazard)) }];
      })),
    },
  }));
  const judged = choice(judgeResponse, 'judge', proposals.map(p => p.id));
  for (const proposal of proposals) {
    proposal.probability = judged.probabilities[proposal.id];
    proposal.vetoProbability = noul(judgeResponse, `veto_${proposal.id}`);
    proposal.veto = proposal.vetoProbability >= THRESHOLDS.veto;
  }
  const surviving = proposals.filter(p => !p.veto).sort((a, b) => b.probability - a.probability || a.id.localeCompare(b.id));
  const selected = surviving[0] ?? proposals.find(p => p.motiveId === 'baseline');
  const fallback = surviving.length ? null : { kind: 'deterministic-baseline', reason: '全部提案被教練否決，明確改採本機基準落點。' };
  timings.total = Math.round(performance.now() - start);
  const decision = {
    mode, isLive: mode === 'live', sourceLabel: mode === 'live' ? '真實 Jev API' : '本機確定性預演', model: mode === 'live' ? (judgeResponse.model ?? MODEL) : 'local-deterministic-preview',
    version: game.version, senses, proposals, selectedPlacementId: selected.placementId, selectedProposalId: selected.id,
    selected: selected.placement, coachVeto: proposals.some(p => p.veto), timings, usage, calls, batches: 3, fallback,
    thresholds: THRESHOLDS, rawTrace,
  };
  onPhase({ phase: 'judge', status: 'completed', mode, version: game.version, detail: { proposals, selectedPlacementId: selected.placementId, selectedProposalId: selected.id, fallback } });
  return decision;
}
