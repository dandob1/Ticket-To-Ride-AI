// ═══════════════════════════════════════════════════════════════════════════════
//  game.js  —  Ticket to Ride Web Client
// ═══════════════════════════════════════════════════════════════════════════════

// ── City positions (matches TTRDisplay.py — the proven layout) ───────────────
// These are the exact 36 board cities with names that match the game engine.
// NOTE: there is no "Detroit"; the city is "Sault St Marie" (no period).
const CITY_POS = {
  'Vancouver':      [78,  50], 'Seattle':        [80, 125],
  'Portland':       [75, 200], 'Calgary':        [208,  55],
  'Helena':         [308, 132], 'San Francisco':  [62, 310],
  'Salt Lake City': [258, 280], 'Las Vegas':      [198, 352],
  'Los Angeles':    [120, 425], 'Phoenix':        [218, 438],
  'Santa Fe':       [336, 400], 'El Paso':        [318, 480],
  'Denver':         [360, 292], 'Winnipeg':       [460,  76],
  'Duluth':         [556, 162], 'Omaha':          [512, 248],
  'Kansas City':    [530, 328], 'Oklahoma City':  [494, 410],
  'Dallas':         [486, 480], 'Houston':        [490, 545],
  'New Orleans':    [580, 545], 'Little Rock':    [560, 432],
  'Saint Louis':    [598, 350], 'Nashville':      [654, 390],
  'Atlanta':        [670, 454], 'Miami':          [762, 568],
  'Charleston':     [748, 445], 'Raleigh':        [738, 388],
  'Pittsburgh':     [722, 280], 'Toronto':        [710, 202],
  'Sault St Marie': [654, 152], 'Chicago':        [628, 244],
  'Montreal':       [800, 124], 'Boston':         [895, 150],
  'New York':       [840, 244], 'Washington':     [806, 312],
};

// ── Card colours ─────────────────────────────────────────────────────────────
const CARD_CSS = {
  red:    '#d22828', orange: '#e67300', yellow: '#d2c800',
  green:  '#28a528', blue:   '#3278dc', purple: '#aa3cc8',
  black:  '#444',    white:  '#ddd',    wild:   '#f0a020',
  grey:   '#888',
};
const CARD_FG = {
  red:'#fff',orange:'#fff',yellow:'#222',green:'#fff',blue:'#fff',
  purple:'#fff',black:'#fff',white:'#333',wild:'#222',grey:'#fff',
};

// ── Player colours ───────────────────────────────────────────────────────────
const PLAYER_CSS = ['#d22828','#3278dc','#28a528','#d2c800','#aa3cc8','#e67300'];

// ── Session management ───────────────────────────────────────────────────────
let sessionId = localStorage.getItem('ttr_session_id');
if (!sessionId) {
  sessionId = Math.random().toString(36).slice(2);
  localStorage.setItem('ttr_session_id', sessionId);
}

// ── WebSocket ────────────────────────────────────────────────────────────────
const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
let ws;
let state = null;

function connect() {
  ws = new WebSocket(`${wsProto}//${location.host}/ws/${sessionId}`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      state = msg.data;
      render(state);
    } else if (msg.type === 'error') {
      console.warn('[Server error]', msg.msg);
    }
  };
  ws.onclose = () => setTimeout(connect, 1500);
  ws.onerror = () => ws.close();
}
connect();

function sendMsg(obj) {
  if (ws && ws.readyState === WebSocket.OPEN)
    ws.send(JSON.stringify(obj));
}

// ── Setup helpers ─────────────────────────────────────────────────────────────
function changeVal(id, delta) {
  const el = document.getElementById(id);
  let v = parseInt(el.textContent) + delta;
  const total = parseInt(document.getElementById('n-human').textContent)
              + parseInt(document.getElementById('n-ai').textContent)
              + (id === 'n-human' ? delta : 0)
              + (id === 'n-ai'    ? delta : 0);
  if (v < 0 || total < 1 || total > 5) return;
  el.textContent = v;
}

function startGame() {
  const nH = parseInt(document.getElementById('n-human').textContent);
  const nA = parseInt(document.getElementById('n-ai').textContent);
  const s  = parseInt(document.getElementById('ai-strat').value);
  sendMsg({
    type: 'start_game',
    n_human: nH,
    n_ai:    nA,
    ai_strategies: Array(nA).fill(s),
  });
  // new session id so refresh starts fresh
  sessionId = Math.random().toString(36).slice(2);
  localStorage.setItem('ttr_session_id', sessionId);
}

// ── Canvas setup ──────────────────────────────────────────────────────────────
const canvas = document.getElementById('map-canvas');
const ctx    = canvas.getContext('2d');
let SCALE    = 1;

function resizeCanvas() {
  const panel = document.getElementById('map-panel');
  const w = panel.clientWidth  || 800;
  const h = panel.clientHeight || 600;
  canvas.width  = w;
  canvas.height = h;
  SCALE = Math.min(canvas.width / 960, canvas.height / 630);
  if (state) drawMap(state);
}
window.addEventListener('resize', resizeCanvas);

function mx(x) { return x * SCALE + 10; }
function my(y) { return y * SCALE + 10; }

// ── Route slot geometry ───────────────────────────────────────────────────────

function slotOffsets(c1, c2, totalSlots) {
  // Returns perpendicular offset for each slot so double/triple routes don't overlap
  const [x1, y1] = [mx(CITY_POS[c1][0]), my(CITY_POS[c1][1])];
  const [x2, y2] = [mx(CITY_POS[c2][0]), my(CITY_POS[c2][1])];
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const perpX = -dy / len, perpY = dx / len;
  const gap = 8 * SCALE;
  return Array.from({length: totalSlots}, (_, i) => {
    const off = (i - (totalSlots - 1) / 2) * gap;
    return { ox: perpX * off, oy: perpY * off };
  });
}

// ── Draw map ──────────────────────────────────────────────────────────────────

function drawMap(st) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Background
  ctx.fillStyle = '#0d1b2a';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Routes
  for (const [key, slots] of Object.entries(st.route_slots)) {
    const [c1, c2] = key.split('|');
    if (!CITY_POS[c1] || !CITY_POS[c2]) continue;
    const nSlots  = slots.length;
    const offsets = slotOffsets(c1, c2, nSlots);
    const weight  = (st.orig_edges && st.orig_edges[key])
                    ? st.orig_edges[key].weight : 1;
    const claimable = st.phase === 'sel_route'
                   && st.avail_routes && (key in st.avail_routes);

    slots.forEach((slot, si) => {
      const { ox, oy } = offsets[si];
      const flash = key === st.last_claim?.key && slot.owner === st.last_claim?.pidx;
      drawRoute(c1, c2, slot, ox, oy, weight, flash, claimable);
    });
  }

  // Cities
  for (const [city, [cx, cy]] of Object.entries(CITY_POS)) {
    const x = mx(cx), y = my(cy);
    ctx.beginPath();
    ctx.arc(x, y, 6 * SCALE, 0, Math.PI * 2);
    ctx.fillStyle   = '#cce';
    ctx.fill();
    ctx.strokeStyle = '#002';
    ctx.lineWidth   = 1.5;
    ctx.stroke();

    ctx.fillStyle  = '#fff';
    ctx.font       = `${Math.max(9, 10 * SCALE)}px sans-serif`;
    ctx.textAlign  = 'center';
    ctx.fillText(city, x, y - 8 * SCALE);
  }

  // Legend
  drawLegend(st);
}

function drawRoute(c1, c2, slot, ox, oy, weight, flash, claimable) {
  const [x1, y1] = [mx(CITY_POS[c1][0]) + ox, my(CITY_POS[c1][1]) + oy];
  const [x2, y2] = [mx(CITY_POS[c2][0]) + ox, my(CITY_POS[c2][1]) + oy];

  const owned      = slot.owner !== null;
  const routeColor = owned ? (PLAYER_CSS[slot.owner] || '#888')
                           : (CARD_CSS[slot.orig] || '#888');

  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;      // unit direction
  const angle = Math.atan2(dy, dx);

  const n      = Math.max(1, weight || 1);
  const gap    = 3 * SCALE;                 // gap between cars
  const carLen = Math.max(4, (len - gap * (n + 1)) / n);
  const carW   = (owned ? 12 : 9) * SCALE;  // car thickness

  ctx.save();

  // Claimable glow underlay (only during route selection)
  if (claimable) {
    ctx.strokeStyle = 'rgba(255, 224, 102, 0.55)';
    ctx.lineWidth   = carW + 12 * SCALE;
    ctx.lineCap     = 'round';
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  }

  if (flash) { ctx.shadowColor = '#ffe066'; ctx.shadowBlur = 18; }

  // Draw each train-car segment (one per required card)
  for (let i = 0; i < n; i++) {
    const start = gap * (i + 1) + carLen * i;
    const cx = x1 + ux * (start + carLen / 2);
    const cy = y1 + uy * (start + carLen / 2);

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);

    // black casing
    ctx.fillStyle = '#000';
    ctx.fillRect(-carLen / 2 - 1.2, -carW / 2 - 1.5, carLen + 2.4, carW + 3);

    // colored body
    ctx.fillStyle = routeColor;
    ctx.fillRect(-carLen / 2, -carW / 2, carLen, carW);

    // light shine on top half for a 3D feel
    ctx.fillStyle = 'rgba(255,255,255,0.22)';
    ctx.fillRect(-carLen / 2, -carW / 2, carLen, carW * 0.42);

    ctx.restore();
  }

  ctx.shadowBlur = 0;
  const midX = (x1 + x2) / 2, midY = (y1 + y2) / 2;

  if (owned) {
    // Owner badge at midpoint
    ctx.fillStyle = PLAYER_CSS[slot.owner] || '#888';
    ctx.beginPath();
    ctx.arc(midX, midY, 8 * SCALE, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#000';
    ctx.lineWidth   = 1.5;
    ctx.stroke();

    ctx.fillStyle    = '#fff';
    ctx.font         = `bold ${Math.max(9, 10 * SCALE)}px sans-serif`;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(slot.owner + 1, midX, midY);
    ctx.textBaseline = 'alphabetic';
  } else {
    // Cost label: a small pill showing the length, tinted by required color.
    // This tells the player how many cards (and of what color) the route costs.
    const label = String(n);
    ctx.font = `bold ${Math.max(9, 10 * SCALE)}px sans-serif`;
    const padX = 4 * SCALE, r = 7 * SCALE;
    const isGrey = slot.orig === 'grey';

    ctx.fillStyle   = '#000';
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.arc(midX, midY, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // ring in the route's required color (grey ring = any single color)
    ctx.strokeStyle = isGrey ? '#cccccc' : (CARD_CSS[slot.orig] || '#ccc');
    ctx.lineWidth   = 2 * SCALE;
    ctx.beginPath();
    ctx.arc(midX, midY, r, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle    = '#fff';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, midX, midY);
    ctx.textBaseline = 'alphabetic';
  }

  ctx.restore();
}

function drawLegend(st) {
  if (!st.players) return;
  const x = 12, y = canvas.height - 12;
  const lineH = 18 * SCALE;
  ctx.save();
  st.players.forEach((p, i) => {
    const ly = y - (st.players.length - 1 - i) * lineH;
    ctx.fillStyle = PLAYER_CSS[i];
    ctx.beginPath();
    ctx.arc(x + 6, ly - 4, 6 * SCALE, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font      = `${Math.max(10, 11 * SCALE)}px sans-serif`;
    ctx.textAlign = 'left';
    ctx.fillText(`${p.name}  ${p.points}pts  🚂${p.trains}`, x + 15, ly);
  });
  ctx.restore();
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

const PHASE_LABELS = {
  setup:      'Setup',
  init_tix:   'Choose Starting Tickets',
  turn_start: 'New Turn',
  action:     'Your Turn — Choose Action',
  draw_c1:    'Draw Card #1',
  draw_c2:    'Draw Card #2',
  sel_route:  'Select a Route to Claim',
  sel_color:  'Choose Card Color',
  confirm_r:  'Confirm Claim',
  draw_tix:   'Draw Destination Tickets',
  ai_turn:    '🤖 AI Playing…',
  game_over:  'Game Over',
};

function renderSidebar(st) {
  // Phase banner
  const banner = document.getElementById('phase-banner');
  banner.textContent = PHASE_LABELS[st.phase] || st.phase;

  // Players
  const pp = document.getElementById('players-panel');
  pp.innerHTML = '';
  (st.players || []).forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'player-row' + (i === st.player_idx ? ' active' : '');
    row.innerHTML = `
      <div class="player-dot" style="background:${PLAYER_CSS[i]}"></div>
      <div class="player-name">${p.name}${p.is_ai ? ' 🤖' : ' 👤'}</div>
      <div class="player-stats">
        <b>${p.points}</b> pts &nbsp;🚂 ${p.trains}
        &nbsp;<span style="color:${p.tickets.filter(t=>!t.done).length>0?'#c66':'#6c6'}">${p.tickets.length} tickets</span>
      </div>`;
    pp.appendChild(row);
  });

  // Cards panel (only for current human player)
  const cardsPanel = document.getElementById('cards-panel');
  const curPlayer  = (st.players || [])[st.player_idx];
  if (curPlayer && !curPlayer.is_ai) {
    cardsPanel.classList.remove('hidden');
    renderHand(curPlayer.hand);
    renderFaceUp(st);
    document.getElementById('deck-count').textContent = st.deck_count || 0;
  } else {
    cardsPanel.classList.add('hidden');
  }

  // Tickets
  renderTickets(st);

  // Actions
  renderActions(st);

  // Log
  renderLog(st);

  // AI banner
  const aiBanner = document.getElementById('ai-banner');
  if (st.ai_msg && st.phase === 'ai_turn') {
    aiBanner.textContent = st.ai_msg;
    aiBanner.classList.remove('hidden');
  } else {
    aiBanner.classList.add('hidden');
  }
}

function renderHand(hand) {
  const el = document.getElementById('hand-cards');
  el.innerHTML = '';
  for (const [col, cnt] of Object.entries(hand || {})) {
    if (!cnt) continue;
    const chip = document.createElement('span');
    chip.className = 'card-chip';
    chip.style.background = CARD_CSS[col] || '#888';
    chip.style.color       = CARD_FG[col]  || '#fff';
    chip.textContent = `${col} ×${cnt}`;
    el.appendChild(chip);
  }
}

function renderFaceUp(st) {
  const el   = document.getElementById('face-up-cards');
  el.innerHTML = '';
  const cards = st.face_up_cards || [];
  cards.forEach(col => {
    const chip = document.createElement('span');
    chip.className = 'card-chip clickable';
    chip.style.background = CARD_CSS[col] || '#888';
    chip.style.color       = CARD_FG[col]  || '#fff';
    chip.textContent = col;

    const clickable = (st.phase === 'draw_c1' || st.phase === 'draw_c2')
                   && !(st.phase === 'draw_c2' && col === 'wild');
    if (clickable) {
      chip.addEventListener('click', () => sendMsg({type:'pick_card', source:'face_up', card: col}));
    } else {
      chip.style.opacity = '0.5';
    }
    el.appendChild(chip);
  });

  // Deck chip
  const deck = document.createElement('span');
  deck.className = 'card-chip' + ((st.phase==='draw_c1'||st.phase==='draw_c2')?' clickable':'');
  deck.style.background = '#333';
  deck.style.color       = '#fff';
  deck.style.border      = '2px dashed #888';
  deck.textContent       = `Deck (${st.deck_count})`;
  if (st.phase === 'draw_c1' || st.phase === 'draw_c2') {
    deck.addEventListener('click', () => sendMsg({type:'pick_card', source:'face_down'}));
  }
  el.appendChild(deck);
}

function renderTickets(st) {
  const curPlayer = (st.players || [])[st.player_idx];
  const el = document.getElementById('my-tickets');
  el.innerHTML = '';
  if (!curPlayer || curPlayer.is_ai) {
    document.getElementById('tickets-panel').classList.add('hidden');
    return;
  }
  document.getElementById('tickets-panel').classList.remove('hidden');
  (curPlayer.tickets || []).forEach(t => {
    const row = document.createElement('div');
    row.className = 'ticket-row ' + (t.done ? 'done' : 'undone');
    row.innerHTML = `<span>${t.c1} → ${t.c2}</span>
      <span style="margin-left:auto">${t.done ? '✔' : '✘'} <b>${t.value}</b></span>`;
    el.appendChild(row);
  });
}

function renderActions(st) {
  const el = document.getElementById('action-buttons');
  el.innerHTML = '';

  const btn = (text, cb, isPrimary) => {
    const b = document.createElement('button');
    b.className = 'action-btn' + (isPrimary ? ' primary' : '');
    b.textContent = text;
    b.addEventListener('click', cb);
    el.appendChild(b);
  };

  const curPlayer = (st.players || [])[st.player_idx];

  switch (st.phase) {
    case 'turn_start':
      btn('▶ Start Turn', () => sendMsg({type:'start_turn'}), true);
      break;

    case 'action':
      btn('🃏 Draw Train Cards',   () => sendMsg({type:'action', action:'draw_cards'}),   true);
      btn('🛤️ Claim a Route',      () => sendMsg({type:'action', action:'claim_route'}));
      btn('🎫 Draw Ticket Cards',  () => sendMsg({type:'action', action:'draw_tickets'}));
      break;

    case 'draw_c1':
    case 'draw_c2':
      // Handled by face-up card chips
      break;

    case 'sel_route':
      btn('✖ Cancel', () => sendMsg({type:'cancel'}));
      break;

    case 'ai_turn':
      // AI turn auto-advances after a short delay — no button needed
      break;
  }
}

function renderLog(st) {
  const el = document.getElementById('log-messages');
  el.innerHTML = '';
  (st.messages || []).slice().reverse().forEach(m => {
    const div = document.createElement('div');
    div.className = 'log-line';
    if (m.pidx !== null && m.pidx !== undefined) {
      div.style.color = PLAYER_CSS[m.pidx] || '#fff';
    }
    div.textContent = m.text;
    el.appendChild(div);
  });
}

// ── Modals ────────────────────────────────────────────────────────────────────

function renderModals(st) {
  showModal('tix-modal',     st.phase === 'init_tix' || st.phase === 'draw_tix');
  showModal('color-modal',   st.phase === 'sel_color');
  showModal('confirm-modal', st.phase === 'confirm_r');
  showModal('gameover-modal',st.phase === 'game_over');

  if (st.phase === 'init_tix' || st.phase === 'draw_tix')  renderTixModal(st);
  if (st.phase === 'sel_color')  renderColorModal(st);
  if (st.phase === 'confirm_r')  renderConfirmModal(st);
  if (st.phase === 'game_over')  renderGameOver(st);
}

function showModal(id, visible) {
  document.getElementById(id).classList.toggle('hidden', !visible);
}

// Ticket chooser
function renderTixModal(st) {
  const isInit = st.phase === 'init_tix';
  document.getElementById('tix-title').textContent = isInit
    ? 'Choose Starting Tickets'
    : 'Draw Destination Tickets';
  document.getElementById('tix-hint').textContent =
    `Select at least ${st.min_tix} ticket(s)`;

  const list = document.getElementById('tix-list');
  list.innerHTML = '';
  const chosen = new Set(st.chosen_tix || []);

  (st.pending_tix || []).forEach((t, i) => {
    const row = document.createElement('div');
    row.className = 'tix-item' + (chosen.has(i) ? ' selected' : '');
    row.innerHTML = `<span class="tix-val">${t.value}</span>
      <span>${t.c1} → ${t.c2}</span>`;
    row.addEventListener('click', () => {
      chosen.has(i) ? chosen.delete(i) : chosen.add(i);
      // enforce min
      if (chosen.size === 0) chosen.add(i);
      row.classList.toggle('selected', chosen.has(i));
    });
    list.appendChild(row);
  });

  // Override confirm button
  const confirmBtn = document.querySelector('#tix-modal .btn-primary');
  confirmBtn.onclick = () => confirmTix(chosen);
}

function confirmTix(chosen) {
  const min = state?.min_tix || 1;
  if (chosen.size < min) {
    alert(`You must keep at least ${min} ticket(s)`);
    return;
  }
  const type = state?.phase === 'init_tix' ? 'confirm_init_tix' : 'confirm_tix';
  sendMsg({type, indices: [...chosen]});
}

// Color picker
function renderColorModal(st) {
  // `sel_route` is serialized as an object (with `c1`/`c2` or `key`).
  // Safely format it for display to avoid runtime errors when it's an object.
  const sr = st.sel_route;
  const routeLabel = sr ? (sr.c1 && sr.c2
    ? `${sr.c1} → ${sr.c2}`
    : (sr.key ? sr.key.split('|').join(' → ') : '')) : '';
  document.getElementById('color-hint').textContent = routeLabel;
  const cb = document.getElementById('color-buttons');
  cb.innerHTML = '';
  (st.playable_colors || []).forEach(col => {
    const b = document.createElement('button');
    b.className   = 'color-btn';
    b.style.background = CARD_CSS[col] || '#888';
    b.style.color      = CARD_FG[col]  || '#fff';
    b.textContent = col;
    b.addEventListener('click', () => sendMsg({type:'select_color', color: col}));
    cb.appendChild(b);
  });
}

// Confirm claim
function renderConfirmModal(st) {
  const rd = st.sel_route;
  document.getElementById('confirm-text').textContent = rd
    ? `${rd.c1 || rd.key?.split('|')[0]} → ${rd.c2 || rd.key?.split('|')[1]}  •  Length ${rd.weight}  •  +${rd.pts} points`
    : '';
  const cc = document.getElementById('confirm-combo');
  cc.innerHTML = '';
  for (const [col, cnt] of Object.entries(st.combo || {})) {
    if (!cnt) continue;
    const chip = document.createElement('span');
    chip.className = 'card-chip';
    chip.style.background = CARD_CSS[col] || '#888';
    chip.style.color       = CARD_FG[col]  || '#fff';
    chip.textContent = `${col} ×${cnt}`;
    cc.appendChild(chip);
  }
}

// Game over screen
function renderGameOver(st) {
  const el = document.getElementById('final-scores');
  el.innerHTML = '';
  const sorted = [...(st.players || [])].sort((a, b) => b.points - a.points);
  const medals = ['🥇','🥈','🥉','4️⃣','5️⃣'];
  sorted.forEach((p, rank) => {
    const row = document.createElement('div');
    row.className = 'score-row';
    row.innerHTML = `
      <span class="score-rank">${medals[rank]}</span>
      <div class="player-dot" style="background:${PLAYER_CSS[(st.players||[]).indexOf(p)]}; width:12px; height:12px; border-radius:50%; display:inline-block"></div>
      <span style="margin-left:6px">${p.name}${p.is_ai?' 🤖':' 👤'}</span>
      <span class="score-pts">${p.points} pts</span>`;
    el.appendChild(row);
  });
}

// ── Canvas click → route selection ──────────────────────────────────────────

canvas.addEventListener('click', (ev) => {
  if (!state || state.phase !== 'sel_route') return;
  const rect  = canvas.getBoundingClientRect();
  // Convert CSS pixel coordinates to canvas bitmap coordinates.
  // Without this, any difference between the canvas's displayed size and
  // its internal resolution makes clicks miss the routes entirely.
  const scaleX = canvas.width  / rect.width;
  const scaleY = canvas.height / rect.height;
  const clickX = (ev.clientX - rect.left) * scaleX;
  const clickY = (ev.clientY - rect.top)  * scaleY;

  let best = null, bestDist = Infinity;
  for (const [key, colors] of Object.entries(state.avail_routes || {})) {
    const [c1, c2] = key.split('|');
    if (!CITY_POS[c1] || !CITY_POS[c2]) continue;
    const x1 = mx(CITY_POS[c1][0]), y1 = my(CITY_POS[c1][1]);
    const x2 = mx(CITY_POS[c2][0]), y2 = my(CITY_POS[c2][1]);
    const d = pointToSegDist(clickX, clickY, x1, y1, x2, y2);
    if (d < bestDist) { bestDist = d; best = key; }
  }

  const threshold = 24 * SCALE;
  if (best && bestDist < threshold) {
    const [c1, c2] = best.split('|');
    sendMsg({type: 'click_route', c1, c2});
  }
});

function pointToSegDist(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const len2 = dx*dx + dy*dy;
  if (!len2) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1)*dx + (py - y1)*dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t*dx), py - (y1 + t*dy));
}

// ── AI auto-advance ───────────────────────────────────────────────────────────
// Tracks the last state key we scheduled an auto-advance for — prevents
// duplicate timeouts if the server sends the same phase twice.
let lastAutoKey = null;

function scheduleAutoAdvance(st) {
  const curPlayer = (st.players || [])[st.player_idx];
  const key = `${st.phase}:${st.player_idx}`;

  if (key === lastAutoKey) return;   // already scheduled for this state
  lastAutoKey = key;

  if (st.phase === 'turn_start' && curPlayer?.is_ai) {
    // Brief pause so the player can see whose turn it is before it fires
    setTimeout(() => {
      if (state?.phase === 'turn_start' && state?.player_idx === st.player_idx)
        sendMsg({type: 'start_turn'});
    }, 700);
  } else if (st.phase === 'ai_turn') {
    // Longer pause so the player can read what the AI did
    setTimeout(() => {
      if (state?.phase === 'ai_turn')
        sendMsg({type: 'advance_ai_turn'});
    }, 1600);
  } else if (!curPlayer?.is_ai) {
    lastAutoKey = null;   // reset so future AI phases trigger correctly
  }
}

// ── Main state render (this is the active render; the earlier definition
//    is overridden by this one via function hoisting) ──────────────────────────
function render(st) {
  if (!st) return;

  const setupScreen = document.getElementById('setup-screen');
  const gameScreen  = document.getElementById('game-screen');

  if (st.phase === 'setup') {
    setupScreen.classList.remove('hidden');
    gameScreen.classList.add('hidden');
    return;
  }

  if (!setupScreen.classList.contains('hidden')) {
    setupScreen.classList.add('hidden');
    gameScreen.classList.remove('hidden');
    resizeCanvas();
    // Re-measure once layout has settled so click coordinates stay aligned
    requestAnimationFrame(resizeCanvas);
  }

  drawMap(st);
  renderSidebar(st);
  renderModals(st);
  scheduleAutoAdvance(st);
}
