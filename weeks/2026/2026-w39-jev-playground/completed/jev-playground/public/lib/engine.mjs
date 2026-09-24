/** A deterministic, serializable Tetris simulator. No model or network calls. */
export const WIDTH = 10;
export const HEIGHT = 20;
export const PIECE_TYPES = Object.freeze(['I', 'O', 'T', 'S', 'Z', 'J', 'L']);

const BASE_SHAPES = {
  I: [[0, 0], [1, 0], [2, 0], [3, 0]],
  O: [[0, 0], [1, 0], [0, 1], [1, 1]],
  T: [[0, 0], [1, 0], [2, 0], [1, 1]],
  S: [[1, 0], [2, 0], [0, 1], [1, 1]],
  Z: [[0, 0], [1, 0], [1, 1], [2, 1]],
  J: [[0, 0], [0, 1], [1, 1], [2, 1]],
  L: [[2, 0], [0, 1], [1, 1], [2, 1]],
};

function normalized(cells) {
  const minX = Math.min(...cells.map(([x]) => x));
  const minY = Math.min(...cells.map(([, y]) => y));
  return cells.map(([x, y]) => [x - minX, y - minY])
    .sort((a, b) => a[1] - b[1] || a[0] - b[0]);
}

function rotations(base) {
  const result = [];
  let cells = normalized(base);
  for (let turn = 0; turn < 4; turn++) {
    if (!result.some(shape => JSON.stringify(shape) === JSON.stringify(cells))) {
      result.push(cells);
    }
    cells = normalized(cells.map(([x, y]) => [-y, x]));
  }
  return Object.freeze(result.map(shape => Object.freeze(
    shape.map(([x, y]) => Object.freeze({ x, y })),
  )));
}

export const SHAPES = Object.freeze(Object.fromEntries(
  PIECE_TYPES.map(type => [type, rotations(BASE_SHAPES[type])]),
));

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  throw error;
}

function hashSeed(seed) {
  let value = 2166136261;
  for (const char of String(seed)) {
    value = Math.imul(value ^ char.charCodeAt(0), 16777619);
  }
  return value >>> 0;
}

function random(state) {
  state.rngState = (state.rngState + 0x6D2B79F5) >>> 0;
  let value = state.rngState;
  value = Math.imul(value ^ value >>> 15, value | 1);
  value ^= value + Math.imul(value ^ value >>> 7, value | 61);
  return ((value ^ value >>> 14) >>> 0) / 4294967296;
}

function draw(state) {
  if (!state.bag.length) {
    state.bag = [...PIECE_TYPES];
    for (let index = state.bag.length - 1; index > 0; index--) {
      const other = Math.floor(random(state) * (index + 1));
      [state.bag[index], state.bag[other]] = [state.bag[other], state.bag[index]];
    }
  }
  return state.bag.pop();
}

export function emptyBoard() {
  return Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(null));
}

function initialBoard(scenario) {
  const board = emptyBoard();
  const fillColumn = (x, height) => {
    for (let y = HEIGHT - height; y < HEIGHT; y++) board[y][x] = 'G';
  };
  if (scenario === 'empty') return board;
  if (scenario === 'stairs') {
    for (let x = 0; x < WIDTH; x++) fillColumn(x, Math.floor(x / 2));
  } else if (scenario === 'holes') {
    [3, 4, 5, 3, 4, 3, 5, 4, 2, 2].forEach((height, x) => fillColumn(x, height));
    board[HEIGHT - 2][2] = null;
    board[HEIGHT - 1][6] = null;
  } else if (scenario === 'danger') {
    [14, 15, 13, 14, 12, 14, 15, 13, 14, 11].forEach((height, x) => fillColumn(x, height));
    // Keep a central well open so the scenario contains no pre-cleared rows.
    for (let y = 0; y < HEIGHT; y++) board[y][4] = null;
  } else {
    fail('INVALID_SCENARIO', `Unknown scenario: ${scenario}`);
  }
  return board;
}

/** All random-generator and bag state lives in the returned JSON object. */
export function createGame({ seed = 'jev-demo', scenario = 'empty' } = {}) {
  const game = {
    seed: String(seed), scenario, board: initialBoard(scenario),
    current: null, next: [], score: 0, lines: 0, pieces: 0,
    version: 0, gameOver: false, rngState: hashSeed(seed), bag: [],
    lastMove: null,
  };
  game.current = draw(game);
  game.next = Array.from({ length: 5 }, () => draw(game));
  return game;
}

/** Reset reproduces the initial stream/board while invalidating pending moves. */
export function resetGame(game, options = {}) {
  return {
    ...createGame({ seed: game.seed, scenario: game.scenario, ...options }),
    version: game.version + 1,
  };
}

function validateBoard(board) {
  if (!Array.isArray(board) || board.length !== HEIGHT ||
      board.some(row => !Array.isArray(row) || row.length !== WIDTH)) {
    fail('INVALID_BOARD', `Board must contain ${HEIGHT} rows of ${WIDTH} cells`);
  }
}

const occupied = value => value !== null && value !== 0 && value !== undefined;

/** Holes are all empty cells below an occupied cell in their column. */
export function boardFeatures(board) {
  validateBoard(board);
  const heights = Array(WIDTH).fill(0);
  let holes = 0;
  for (let x = 0; x < WIDTH; x++) {
    let seenBlock = false;
    for (let y = 0; y < HEIGHT; y++) {
      if (occupied(board[y][x])) {
        if (!seenBlock) heights[x] = HEIGHT - y;
        seenBlock = true;
      } else if (seenBlock) holes++;
    }
  }
  let wells = 0;
  for (let x = 0; x < WIDTH; x++) {
    const left = x === 0 ? HEIGHT : heights[x - 1];
    const right = x === WIDTH - 1 ? HEIGHT : heights[x + 1];
    const depth = Math.max(0, Math.min(left, right) - heights[x]);
    wells += depth * (depth + 1) / 2;
  }
  return {
    aggregateHeight: heights.reduce((sum, height) => sum + height, 0),
    maxHeight: Math.max(...heights), holes,
    bumpiness: heights.slice(1).reduce((sum, height, index) => sum + Math.abs(height - heights[index]), 0),
    wells,
  };
}

function canOccupy(board, shape, x, y) {
  return shape.every(cell => {
    const column = x + cell.x;
    const row = y + cell.y;
    return column >= 0 && column < WIDTH && row < HEIGHT &&
      (row < 0 || !occupied(board[row][column]));
  });
}

function placeAndClear(board, cells, type) {
  const placed = board.map(row => [...row]);
  for (const { x, y } of cells) placed[y][x] = type;
  const remaining = placed.filter(row => !row.every(occupied));
  const linesCleared = HEIGHT - remaining.length;
  return {
    board: [...Array.from({ length: linesCleared }, () => Array(WIDTH).fill(null)), ...remaining],
    linesCleared,
  };
}

function heuristic(features) {
  return Number((
    features.linesCleared * 1.5 - features.aggregateHeight * 0.51 -
    features.holes * 0.9 - features.bumpiness * 0.19 -
    features.maxHeight * 0.1 - features.wells * 0.05
  ).toFixed(6));
}

/**
 * Enumerates vertical hard drops after selecting a rotation and column.
 * Rotation and horizontal position are chosen above the board; no wall kicks,
 * sideways slides under blocks, or mid-drop rotation are simulated.
 */
export function enumeratePlacements(game) {
  validateBoard(game.board);
  if (game.gameOver) return [];
  const shapes = SHAPES[game.current];
  if (!shapes) fail('INVALID_PIECE', `Unknown piece: ${game.current}`);
  const candidates = [];
  shapes.forEach((shape, rotation) => {
    const width = 1 + Math.max(...shape.map(cell => cell.x));
    const height = 1 + Math.max(...shape.map(cell => cell.y));
    for (let x = 0; x <= WIDTH - width; x++) {
      let y = -height;
      while (canOccupy(game.board, shape, x, y + 1)) y++;
      const cells = shape.map(cell => ({ x: x + cell.x, y: y + cell.y }));
      if (cells.some(cell => cell.y < 0)) continue;
      const result = placeAndClear(game.board, cells, game.current);
      const features = { ...boardFeatures(result.board), linesCleared: result.linesCleared };
      candidates.push({
        id: `v${game.version}:r${rotation}:x${x}:y${y}`,
        rotation, x, y, cells, features, heuristic: heuristic(features),
      });
    }
  });
  return candidates;
}

/** Invalid/stale moves throw without modifying the input game. */
export function applyPlacement(game, placementId, expectedVersion) {
  if (!Number.isInteger(expectedVersion) || expectedVersion !== game.version) {
    fail('STALE_VERSION', `Expected board version ${game.version}, received ${expectedVersion}`);
  }
  if (game.gameOver) fail('GAME_OVER', 'The game has ended');
  const candidate = enumeratePlacements(game).find(item => item.id === placementId);
  if (!candidate) fail('INVALID_PLACEMENT', 'Placement is not legal for the current board');
  const result = placeAndClear(game.board, candidate.cells, game.current);
  const level = 1 + Math.floor(game.lines / 10);
  const scoreAdded = [0, 100, 300, 500, 800][result.linesCleared] * level;
  const updated = {
    ...game, board: result.board, next: [...game.next], bag: [...game.bag],
    score: game.score + scoreAdded, lines: game.lines + result.linesCleared,
    pieces: game.pieces + 1, version: game.version + 1,
    lastMove: {
      placementId: candidate.id, piece: game.current, rotation: candidate.rotation,
      x: candidate.x, y: candidate.y, cells: candidate.cells,
      linesCleared: result.linesCleared, scoreAdded,
    },
  };
  updated.current = updated.next.shift();
  updated.next.push(draw(updated));
  updated.gameOver = enumeratePlacements(updated).length === 0;
  return updated;
}

/** Explicit local preview; this does not call Jev or represent a model result. */
export function previewDecision(game) {
  const candidates = enumeratePlacements(game);
  const placement = [...candidates].sort((a, b) => b.heuristic - a.heuristic ||
    a.rotation - b.rotation || a.x - b.x)[0] ?? null;
  return {
    mode: 'preview', placementId: placement?.id ?? null, placement,
    reason: placement
      ? `本機預覽：依消行、孔洞、堆疊高度與表面起伏計分，選擇 ${placement.id}。`
      : '目前沒有可用落點，遊戲結束。',
  };
}
