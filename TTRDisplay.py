"""
TTRDisplay.py
Interactive Ticket to Ride game display using Pygame.
Human players click to interact; AI players auto-play via rollout policy.

Usage:
    uv run python TTRDisplay.py
"""
import pygame, sys, math, random
import TTRGameSim

pygame.init()

# ─── Layout constants ─────────────────────────────────────────────────────────
WIN_W, WIN_H = 1500, 870
MAP_X, MAP_Y = 15, 15
MAP_W, MAP_H = 1010, 710
LOG_X, LOG_Y = MAP_X, MAP_Y + MAP_H + 5
LOG_W, LOG_H = MAP_W, 130
PAN_X, PAN_Y = MAP_X + MAP_W + 12, 5
PAN_W        = WIN_W - PAN_X - 8
PAN_H        = WIN_H - 10

# ─── Colours ──────────────────────────────────────────────────────────────────
FELT     = ( 32,  78,  32)
MAP_BG   = (210, 195, 163)
PAN_BG   = ( 26,  26,  42)
PAN_MID  = ( 42,  42,  68)
PAN_LITE = ( 65,  65, 100)
WHITE    = (255, 255, 255)
BLACK    = (  0,   0,   0)
YHL      = (255, 240,  55)
GHL      = ( 80, 200,  80)
RHL      = (220,  60,  60)

ROUTE_COL = {
    'red':    (215,  48,  48), 'orange': (255, 128,   0),
    'yellow': (225, 205,   0), 'green':  ( 30, 155,  30),
    'blue':   ( 35, 100, 215), 'purple': (148,  40, 195),
    'black':  ( 40,  40,  40), 'white':  (238, 238, 238),
    'grey':   (148, 148, 148), 'wild':   (255, 195,  45),
}
TEXT_ON = {
    'red': WHITE, 'orange': BLACK, 'yellow': BLACK, 'green': WHITE,
    'blue': WHITE, 'purple': WHITE, 'black': WHITE, 'white': BLACK,
    'grey': BLACK, 'wild': BLACK,
}

PCOL  = [(210,40,40),(50,120,220),(40,165,40),(210,175,0),(170,60,200),(230,115,0)]
PNAME = ['Red','Blue','Green','Yellow','Purple','Orange']

# ─── City positions (relative to MAP_X, MAP_Y) ────────────────────────────────
CITY_POS = {
    'Vancouver':      ( 78,  50), 'Seattle':        ( 80, 125),
    'Portland':       ( 75, 200), 'Calgary':        (208,  55),
    'Helena':         (308, 132), 'San Francisco':  ( 62, 310),
    'Salt Lake City': (258, 280), 'Las Vegas':      (198, 352),
    'Los Angeles':    (120, 425), 'Phoenix':        (218, 438),
    'Santa Fe':       (336, 400), 'El Paso':        (318, 480),
    'Denver':         (360, 292), 'Winnipeg':       (460,  76),
    'Duluth':         (556, 162), 'Omaha':          (512, 248),
    'Kansas City':    (530, 328), 'Oklahoma City':  (494, 410),
    'Dallas':         (486, 480), 'Houston':        (490, 545),
    'New Orleans':    (580, 545), 'Little Rock':    (560, 432),
    'Saint Louis':    (598, 350), 'Nashville':      (654, 390),
    'Atlanta':        (670, 454), 'Miami':          (762, 568),
    'Charleston':     (748, 445), 'Raleigh':        (738, 388),
    'Pittsburgh':     (722, 280), 'Toronto':        (710, 202),
    'Sault St Marie': (654, 152), 'Chicago':        (628, 244),
    'Montreal':       (800, 124), 'Boston':         (895, 150),
    'New York':       (840, 244), 'Washington':     (806, 312),
}

# ─── Game phases ──────────────────────────────────────────────────────────────
P_SETUP_PC    = 'setup_pc'
P_SETUP_AIC   = 'setup_aic'
P_SETUP_AIREW = 'setup_airew'
P_INIT_TIX    = 'init_tix'
P_TURN_START  = 'turn_start'
P_ACTION      = 'action'
P_DRAW_C1     = 'draw_c1'
P_DRAW_C2     = 'draw_c2'
P_SEL_ROUTE   = 'sel_route'
P_SEL_COLOR   = 'sel_color'
P_CONFIRM_R   = 'confirm_r'
P_DRAW_TIX    = 'draw_tix'
P_AI_TURN     = 'ai_turn'
P_GAME_OVER   = 'game_over'

# ─── Font cache ───────────────────────────────────────────────────────────────
_FC = {}
def fnt(sz, bold=False):
    k = (sz, bold)
    if k not in _FC:
        _FC[k] = pygame.font.SysFont('Arial', sz, bold=bold)
    return _FC[k]

# ─── Drawing helpers ──────────────────────────────────────────────────────────
def blit(surf, text, pos, sz=17, bold=False, col=WHITE, center=False):
    s = fnt(sz, bold).render(str(text), True, col)
    r = s.get_rect()
    if center: r.center = pos
    else:      r.topleft = pos
    surf.blit(s, r)
    return r

def drect(surf, col, r, rad=6, bw=0, bc=None):
    r = pygame.Rect(r)
    pygame.draw.rect(surf, col, r, border_radius=rad)
    if bw and bc:
        pygame.draw.rect(surf, bc, r, bw, border_radius=rad)
    return r

def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx-ax, by-ay
    if dx == dy == 0:
        return math.hypot(px-ax, py-ay)
    t = max(0.0, min(1.0, ((px-ax)*dx + (py-ay)*dy) / (dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))

def perp(ax, ay, bx, by, d):
    dx, dy = bx-ax, by-ay
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy/L*d, dx/L*d
    return (ax+nx, ay+ny), (bx+nx, by+ny)


# ─── Button ───────────────────────────────────────────────────────────────────
class Btn:
    def __init__(self, r, label, col=PAN_LITE, hov=GHL, tc=WHITE,
                 sz=17, bold=False, br=8, en=True, tag=None):
        self.r     = pygame.Rect(r)
        self.label = label
        self.col   = col
        self.hov   = hov
        self.tc    = tc
        self.sz    = sz
        self.bold  = bold
        self.br    = br
        self.en    = en
        self.tag   = tag
        self._h    = False

    def upd(self, mp):
        self._h = self.en and self.r.collidepoint(mp)

    def draw(self, surf):
        c = (60,60,60) if not self.en else (self.hov if self._h else self.col)
        pygame.draw.rect(surf, c, self.r, border_radius=self.br)
        pygame.draw.rect(surf,
                         WHITE if self.en else (90,90,90),
                         self.r, 2, border_radius=self.br)
        s = fnt(self.sz, self.bold).render(
            self.label, True, self.tc if self.en else (110,110,110))
        surf.blit(s, s.get_rect(center=self.r.center))

    def hit(self, ev):
        return (self.en
                and ev.type == pygame.MOUSEBUTTONDOWN
                and ev.button == 1
                and self.r.collidepoint(ev.pos))


# ─── Main Display Class ───────────────────────────────────────────────────────
class TTRDisplay:

    def __init__(self):
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Ticket to Ride")
        self.clock  = pygame.time.Clock()

        self.phase  = P_SETUP_PC
        self.game   = None

        # Setup state
        self.n_human  = 1
        self.n_ai     = 1
        self.ai_rews  = []
        self.ai_rew_i = 0

        # Map snapshot
        self.route_slots = {}   # {(c1,c2): [{'orig','owner','pcol'}]}
        self.orig_edges  = {}   # {(c1,c2): {'weight','edgeColors'}}

        # Turn
        self.player_idx  = 0
        self.final_round = False
        self.final_q     = []

        # Per-phase data
        self.buttons      = []
        self.hover_route  = None
        self.avail_routes = {}

        self.first_card   = None
        self.sel_route    = None
        self.sel_color    = None
        self.sel_combo    = None

        self.pending_tix  = []
        self.chosen_tix   = set()
        self.min_tix      = 1
        self.init_tix_i   = 0

        self.ai_timer     = 0
        self.ai_msg       = ""
        self.turn_start_t = 0
        self.messages     = []      # list of (text, player_idx_or_None)
        self.last_claim   = {'key': None, 'pidx': None, 'time': 0}  # flash effect

        self._build_setup_pc()

    # ── Setup builders ────────────────────────────────────────────────────────

    def _build_setup_pc(self):
        self.buttons = []
        total  = 5   # 0..4
        cx     = MAP_X + MAP_W // 2
        start  = cx - (total * 88) // 2
        for n in range(total):
            self.buttons.append(
                Btn((start + n*88, MAP_Y+420, 78, 60),
                    str(n), sz=30, bold=True, tag=('n_human', n)))

    def _build_setup_aic(self):
        self.buttons = []
        min_ai = 1 if self.n_human == 0 else 0
        max_ai = max(1, 4 - self.n_human)
        total  = max_ai - min_ai + 1
        cx     = MAP_X + MAP_W // 2
        start  = cx - (total * 88) // 2
        for i, n in enumerate(range(min_ai, max_ai + 1)):
            self.buttons.append(
                Btn((start + i*88, MAP_Y+420, 78, 60),
                    str(n), sz=30, bold=True, tag=('n_ai', n)))

    def _build_setup_airew(self):
        self.buttons = []
        labels = [('Tickets', 0), ('Routes', 1), ('Random', 2)]
        cx     = MAP_X + MAP_W // 2
        start  = cx - (3 * 138) // 2
        for i, (lbl, idx) in enumerate(labels):
            self.buttons.append(
                Btn((start + i*138, MAP_Y+420, 128, 60),
                    lbl, sz=22, bold=True, tag=('ai_rew', idx)))

    def _finish_setup(self):
        names = [f"{PNAME[i]} Player" for i in range(self.n_human)]
        self.game = TTRGameSim.Game(self.n_human, self.n_ai,
                                    self.ai_rews, player_names=names)
        self._snapshot_edges()
        self.init_tix_i = 0
        self.phase = P_INIT_TIX
        self._start_init_tix()

    def _snapshot_edges(self):
        self.route_slots = {}
        self.orig_edges  = {}
        for c1, c2, data in self.game.board.copyBoard.edges(data=True):
            key = (min(c1,c2), max(c1,c2))
            colors = list(data['edgeColors'])
            self.route_slots[key] = [
                {'orig': col, 'owner': None, 'pcol': None} for col in colors
            ]
            self.orig_edges[key] = {
                'weight': data['weight'],
                'edgeColors': list(colors),
            }

    def _refresh_slots(self):
        for key in self.route_slots:
            for s in self.route_slots[key]:
                s['owner'] = None
                s['pcol']  = None
        for pidx, player in enumerate(self.game.players):
            for c1, c2, data in player.playerBoard.iterEdges():
                key = (min(c1,c2), max(c1,c2))
                if key not in self.route_slots:
                    continue
                claimed = (data.get('edgeColors') or ['grey'])[0]
                for s in self.route_slots[key]:
                    if s['owner'] is None and (s['orig'] == 'grey' or s['orig'] == claimed):
                        s['owner'] = pidx
                        s['pcol']  = claimed
                        break

    # ── Initial ticket flow ───────────────────────────────────────────────────

    def _start_init_tix(self):
        if self.init_tix_i >= len(self.game.players):
            self.game.posToMove = 0
            self.player_idx = 0
            self.phase = P_TURN_START
            self.turn_start_t = pygame.time.get_ticks()
            self.buttons = []
            return
        player = self.game.players[self.init_tix_i]
        if player.isAi():
            self.game.aiModel.apply_draw_tickets_turn_real(player)
            self._msg(f"{player.name} selected starting tickets", self.init_tix_i)
            self.init_tix_i += 1
            self._start_init_tix()
        else:
            self.pending_tix = self.game.deck.dealTickets(self.game.numTicketsDealt)
            self.chosen_tix  = {0, 1}
            self.min_tix     = 2
            self.buttons     = []

    def _confirm_init_tix(self):
        player = self.game.players[self.init_tix_i]
        chosen = [self.pending_tix[i] for i in self.chosen_tix]
        for t in chosen:
            player.addTicket(t)
        for i, t in enumerate(self.pending_tix):
            if i not in self.chosen_tix:
                self.game.deck.addToTicketDiscard(t)
        self._msg(f"{player.name} kept {len(chosen)} starting ticket(s)", self.init_tix_i)
        self.init_tix_i += 1
        self._start_init_tix()

    # ── Turn management ───────────────────────────────────────────────────────

    def _start_turn(self):
        player = self.game.players[self.player_idx]
        if player.isAi():
            self.phase    = P_AI_TURN
            self.ai_timer = pygame.time.get_ticks()
            self.ai_msg   = ""
            self._exec_ai_turn(player)
        else:
            self.phase = P_ACTION
            self._build_action_btns()

    def _build_action_btns(self):
        by = PAN_Y + 218
        bw = PAN_W - 20
        self.buttons = [
            Btn((PAN_X+10, by,     bw, 56), 'DRAW CARDS',
                col=(38,88,158), hov=(62,130,230), sz=19, bold=True, tag='act_cards'),
            Btn((PAN_X+10, by+66,  bw, 56), 'PLACE TRAINS',
                col=(148,38,38), hov=(210,70,70),  sz=19, bold=True, tag='act_trains'),
            Btn((PAN_X+10, by+132, bw, 56), 'DRAW TICKETS',
                col=(38,128,48), hov=(62,190,80),  sz=19, bold=True, tag='act_tickets'),
        ]

    def _advance_turn(self):
        self._refresh_slots()
        player = self.game.players[self.player_idx]
        player.endTurn()

        if self.final_round:
            if self.final_q:
                self.player_idx = self.final_q.pop(0)
            else:
                self._end_game()
                return
        else:
            if self.game.checkEndingCondition(player):
                self.final_round = True
                self.game.advanceOnePlayer()
                n     = len(self.game.players)
                start = self.game.posToMove
                self.final_q = [(start + i) % n for i in range(n)]
                self.player_idx = self.final_q.pop(0)
                self._msg("*** FINAL ROUND — everyone gets one last turn! ***", None)
            else:
                self.game.advanceOnePlayer()
                self.player_idx = self.game.posToMove

        self.phase        = P_TURN_START
        self.turn_start_t = pygame.time.get_ticks()
        self.buttons      = []

    def _end_game(self):
        for p in self.game.players:
            self.game.scorePlayerTickets(p)
        self.game.scoreLongestPath()
        self.phase   = P_GAME_OVER
        self.buttons = [
            Btn((WIN_W//2-90, WIN_H-80, 180, 52),
                'QUIT', col=RHL, hov=(255,80,80), sz=22, bold=True, tag='quit'),
        ]
        self._msg("=== GAME OVER ===", None)

    # ── AI execution ──────────────────────────────────────────────────────────

    def _exec_ai_turn(self, player):
        legal = self.game.getLegalActions(player)
        if not legal:
            self.ai_msg = f"{player.name}: no legal moves"
            self._msg(self.ai_msg, self.player_idx)
            return
        action = self.game.aiModel.rollout_policy(player, legal)
        self.game.aiModel.apply_action(player, action)
        mv = action['move']
        if mv == 'train':
            c1, c2 = action['edge']['edge']
            w      = action['edge']['weight']
            pts    = self.game.routeValues[w]
            self.ai_msg = f"{player.name} claimed {c1} → {c2}  (+{pts} pts)"
            key = (min(c1,c2), max(c1,c2))
            self.last_claim = {'key': key, 'pidx': self.player_idx,
                               'time': pygame.time.get_ticks()}
        elif mv == 'cards':
            self.ai_msg = f"{player.name} drew 2 train cards"
        else:
            self.ai_msg = f"{player.name} drew destination tickets"
        self._msg(self.ai_msg, self.player_idx)
        self._refresh_slots()

    # ── Card drawing ──────────────────────────────────────────────────────────

    def _build_draw_card_btns(self, skip_wild=False):
        self.buttons = []
        pile   = self.game.deck.getDrawPile()
        base_y = PAN_Y + 220
        for i, card in enumerate(pile):
            col = ROUTE_COL.get(card, (100,100,100))
            tc  = TEXT_ON.get(card, WHITE)
            en  = not (skip_wild and card == 'wild')
            label = card.upper() + (' (disabled)' if not en else '')
            self.buttons.append(
                Btn((PAN_X+10, base_y + i*44, PAN_W-20, 38),
                    label, col=col, hov=YHL, tc=tc, sz=15, bold=True,
                    en=en, tag=('face_up', card)))
        n_left = len(self.game.deck.cards) + len(self.game.deck.getDiscardPile())
        deck_y = base_y + len(pile)*44 + 6
        self.buttons.append(
            Btn((PAN_X+10, deck_y, PAN_W-20, 38),
                f'DRAW FROM DECK  ({n_left} left)',
                col=(55,55,80), hov=(90,90,140), sz=14, bold=True,
                tag=('face_down',)))
        self.buttons.append(
            Btn((PAN_X+10, PAN_Y+PAN_H-58, PAN_W-20, 44),
                'Back', col=(70,70,70), hov=RHL, sz=15, tag='back'))

    def _pick_card(self, ev):
        """Returns the drawn card string, 'BACK', or None."""
        for btn in self.buttons:
            if not btn.hit(ev):
                continue
            if btn.tag == 'back':
                return 'BACK'
            player = self.game.players[self.player_idx]
            if isinstance(btn.tag, tuple) and btn.tag[0] == 'face_up':
                card  = btn.tag[1]
                drawn = self.game.deck.pickFaceUpCard(card)
                player.addCardToHand(drawn)
                self._msg(f"{player.name} picked {drawn} (face-up)", self.player_idx)
                return drawn
            elif isinstance(btn.tag, tuple) and btn.tag[0] == 'face_down':
                drawn = self.game.deck.pickFaceDown()
                if drawn:
                    player.addCardToHand(drawn)
                    self._msg(f"{player.name} drew from deck  ({drawn})", self.player_idx)
                return drawn or 'empty'
        return None

    # ── Route selection ───────────────────────────────────────────────────────

    def _compute_avail_routes(self):
        self.avail_routes = {}
        player = self.game.players[self.player_idx]
        for ed in self.game.board.getEdgesData():
            c1, c2 = ed['edge']
            valid  = [col for col in ed['edgeColors']
                      if self.game.doesPlayerHaveCardsForEdgeColCheck(player, c1, c2, col)]
            if valid:
                key = (min(c1,c2), max(c1,c2))
                self.avail_routes[key] = valid

    def _route_under_mouse(self, mx, my):
        best_key, best_d = None, 9.0
        rx, ry = mx - MAP_X, my - MAP_Y
        for key, slots in self.route_slots.items():
            c1, c2 = key
            if c1 not in CITY_POS or c2 not in CITY_POS:
                continue
            ax, ay = CITY_POS[c1]
            bx, by = CITY_POS[c2]
            n = len(slots)
            for si in range(n):
                off = (si - (n-1)/2.0) * 9
                (sax, say), (sbx, sby) = perp(ax, ay, bx, by, off)
                d = seg_dist(rx, ry, sax, say, sbx, sby)
                if d < best_d:
                    best_d   = d
                    best_key = key
        return best_key

    def _build_color_btns(self, colors):
        self.buttons = []
        bw     = (PAN_W - 28) // 2
        base_y = PAN_Y + 278
        for i, col in enumerate(colors):
            row, ci = i // 2, i % 2
            bx = PAN_X + 10 + ci * (bw + 8)
            by = base_y + row * 50
            rc = ROUTE_COL.get(col, (100,100,100))
            tc = TEXT_ON.get(col, WHITE)
            self.buttons.append(
                Btn((bx, by, bw, 42), col.upper(),
                    col=rc, hov=YHL, tc=tc, sz=15, bold=True,
                    tag=('sel_color', col)))
        rows   = (len(colors) + 1) // 2
        c_y    = base_y + rows*50 + 8
        self.buttons.append(
            Btn((PAN_X+10, c_y, PAN_W-20, 40),
                'Cancel', col=(70,70,70), hov=RHL, sz=14, tag='cancel'))

    def _build_confirm_btns(self):
        self.buttons = [
            Btn((PAN_X+10, PAN_Y+420, PAN_W-20, 54),
                '✓  CONFIRM CLAIM',
                col=(28,130,28), hov=GHL, sz=20, bold=True, tag='confirm'),
            Btn((PAN_X+10, PAN_Y+482, PAN_W-20, 42),
                'Cancel', col=(70,70,70), hov=RHL, sz=14, tag='cancel'),
        ]

    def _best_combo(self, player, color, weight):
        combos = player.getCombinations(weight, color) or []
        valid  = []
        for c in combos:
            base = None; ok = True
            for k in c:
                if k == 'wild': continue
                if base is None: base = k
                elif base != k:  ok = False; break
            if ok and sum(c.values()) == weight:
                valid.append(c)
        if not valid:
            return None
        return min(valid, key=lambda c: c.get('wild', 0))

    def _execute_claim(self):
        player = self.game.players[self.player_idx]
        c1, c2 = self.sel_route
        weight  = self.orig_edges[self.sel_route]['weight']
        combo   = self.sel_combo
        if combo is None:
            self._msg("No valid card combination found.", self.player_idx)
            self.phase = P_ACTION; self._build_action_btns(); return
        player.playerBoard.addEdge(c1, c2, weight, self.sel_color)
        self.game.board.removeEdge(c1, c2, self.sel_color)
        pts = self.game.routeValues[weight]
        player.addPoints(pts)
        for card, cnt in combo.items():
            player.removeCardsFromHand(card, cnt)
            self.game.deck.addToDiscard([card] * cnt)
        player.playNumTrains(weight)
        self.last_claim = {'key': self.sel_route, 'pidx': self.player_idx,
                           'time': pygame.time.get_ticks()}
        self._msg(
            f"{player.name} claimed {c1} → {c2}  "
            f"(len {weight}, +{pts} pts, {player.getNumTrains()} trains left)",
            self.player_idx
        )
        self.sel_route = self.sel_color = self.sel_combo = None
        self._advance_turn()

    # ── Ticket confirm ────────────────────────────────────────────────────────

    def _confirm_tix(self):
        player = self.game.players[self.player_idx]
        chosen = [self.pending_tix[i] for i in self.chosen_tix]
        for t in chosen:
            player.addTicket(t)
        for i, t in enumerate(self.pending_tix):
            if i not in self.chosen_tix:
                self.game.deck.addToTicketDiscard(t)
        self._msg(f"{player.name} kept {len(chosen)} ticket(s)", self.player_idx)
        self._advance_turn()

    def _ticket_done(self, player, ticket):
        """Return True if the player has completed the given ticket."""
        t1, t2, _ = ticket
        try:
            return (player.playerBoard.G.has_node(t1)
                    and player.playerBoard.G.has_node(t2)
                    and player.playerBoard.hasPath(t1, t2))
        except Exception:
            return False

    # ── Messages ──────────────────────────────────────────────────────────────

    def _msg(self, text, pidx=None):
        self.messages.append((str(text), pidx))
        if len(self.messages) > 8:
            self.messages.pop(0)

    # ─────────────────────────────────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        while True:
            mp = pygame.mouse.get_pos()
            for btn in self.buttons:
                btn.upd(mp)

            if self.phase == P_SEL_ROUTE:
                rh = self._route_under_mouse(*mp)
                self.hover_route = rh if rh in self.avail_routes else None
            else:
                self.hover_route = None

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                self._handle(ev)

            self._update()
            self._draw()
            self.clock.tick(60)

    # ─────────────────────────────────────────────────────────────────────────
    # Event handling
    # ─────────────────────────────────────────────────────────────────────────

    def _handle(self, ev):  # noqa: C901

        # ── Setup ──
        if self.phase == P_SETUP_PC:
            for btn in self.buttons:
                if btn.hit(ev) and isinstance(btn.tag, tuple) and btn.tag[0] == 'n_human':
                    self.n_human = btn.tag[1]
                    self.phase   = P_SETUP_AIC
                    self._build_setup_aic()

        elif self.phase == P_SETUP_AIC:
            for btn in self.buttons:
                if btn.hit(ev) and isinstance(btn.tag, tuple) and btn.tag[0] == 'n_ai':
                    self.n_ai    = btn.tag[1]
                    self.ai_rews = []
                    if self.n_ai == 0:
                        self._finish_setup()
                    else:
                        self.ai_rew_i = 0
                        self.phase    = P_SETUP_AIREW
                        self._build_setup_airew()

        elif self.phase == P_SETUP_AIREW:
            for btn in self.buttons:
                if btn.hit(ev) and isinstance(btn.tag, tuple) and btn.tag[0] == 'ai_rew':
                    self.ai_rews.append(btn.tag[1])
                    self.ai_rew_i += 1
                    if self.ai_rew_i >= self.n_ai:
                        self._finish_setup()
                    else:
                        self._build_setup_airew()

        # ── Initial ticket selection ──
        elif self.phase == P_INIT_TIX:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i in range(len(self.pending_tix)):
                    ty = PAN_Y + 100 + i*122
                    if pygame.Rect(PAN_X+10, ty, PAN_W-20, 112).collidepoint(ev.pos):
                        if i in self.chosen_tix and len(self.chosen_tix) > self.min_tix:
                            self.chosen_tix.discard(i)
                        elif i not in self.chosen_tix:
                            self.chosen_tix.add(i)
                conf = pygame.Rect(PAN_X+10, PAN_Y+PAN_H-68, PAN_W-20, 54)
                if conf.collidepoint(ev.pos) and len(self.chosen_tix) >= self.min_tix:
                    self._confirm_init_tix()

        # ── Turn start banner ──
        elif self.phase == P_TURN_START:
            if (ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN)
                    and pygame.time.get_ticks() - self.turn_start_t > 700):
                self._start_turn()

        # ── Choose action ──
        elif self.phase == P_ACTION:
            for btn in self.buttons:
                if btn.hit(ev):
                    if btn.tag == 'act_cards':
                        self.first_card = None
                        self.phase      = P_DRAW_C1
                        self._build_draw_card_btns()
                    elif btn.tag == 'act_trains':
                        self._compute_avail_routes()
                        if not self.avail_routes:
                            self._msg("No claimable routes right now — choose another action.", self.player_idx)
                        else:
                            self.phase   = P_SEL_ROUTE
                            self.buttons = []
                    elif btn.tag == 'act_tickets':
                        if not self.game.deck.tickets:
                            self._msg("Ticket deck is empty.", None)
                        else:
                            self.pending_tix = self.game.deck.dealTickets(
                                self.game.numTicketsDealt)
                            self.chosen_tix  = {0}
                            self.min_tix     = 1
                            self.phase       = P_DRAW_TIX

        # ── Draw first card ──
        elif self.phase == P_DRAW_C1:
            result = self._pick_card(ev)
            if result == 'BACK':
                self.phase = P_ACTION; self._build_action_btns()
            elif result is not None:
                self.first_card = result
                if result == 'wild':
                    self._advance_turn()          # wild face-up = turn ends
                else:
                    self.phase = P_DRAW_C2
                    self._build_draw_card_btns(skip_wild=True)

        # ── Draw second card ──
        elif self.phase == P_DRAW_C2:
            result = self._pick_card(ev)
            if result == 'BACK':
                self._advance_turn()              # keep first card, end turn
            elif result is not None:
                self._advance_turn()

        # ── Click a route on the map ──
        elif self.phase == P_SEL_ROUTE:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                clicked = self._route_under_mouse(*ev.pos)
                if clicked and clicked in self.avail_routes:
                    self.sel_route = clicked
                    colors  = self.avail_routes[clicked]
                    player  = self.game.players[self.player_idx]
                    weight  = self.orig_edges[clicked]['weight']
                    # Expand grey → actual playable colours
                    playable = []
                    for col in colors:
                        if col == 'grey':
                            for hc, hcnt in player.hand.items():
                                if (hc != 'wild' and hcnt > 0
                                        and hcnt + player.hand.get('wild',0) >= weight
                                        and hc not in playable):
                                    playable.append(hc)
                        elif col not in playable:
                            playable.append(col)
                    if len(playable) == 1:
                        self.sel_color = playable[0]
                        self.sel_combo = self._best_combo(player, self.sel_color, weight)
                        self.phase     = P_CONFIRM_R
                        self._build_confirm_btns()
                    elif len(playable) > 1:
                        self.phase = P_SEL_COLOR
                        self._build_color_btns(playable)
                    else:
                        self._msg("No valid card combination for this route.", self.player_idx)
            if ((ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE) or
                    (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3)):
                self.sel_route = None
                self.phase     = P_ACTION
                self._build_action_btns()

        # ── Pick colour ──
        elif self.phase == P_SEL_COLOR:
            for btn in self.buttons:
                if btn.hit(ev):
                    if btn.tag == 'cancel':
                        self.sel_route = None
                        self.phase     = P_SEL_ROUTE
                        self.buttons   = []
                    elif isinstance(btn.tag, tuple) and btn.tag[0] == 'sel_color':
                        self.sel_color = btn.tag[1]
                        player = self.game.players[self.player_idx]
                        weight = self.orig_edges[self.sel_route]['weight']
                        self.sel_combo = self._best_combo(player, self.sel_color, weight)
                        self.phase     = P_CONFIRM_R
                        self._build_confirm_btns()

        # ── Confirm route claim ──
        elif self.phase == P_CONFIRM_R:
            for btn in self.buttons:
                if btn.hit(ev):
                    if btn.tag == 'confirm':
                        self._execute_claim()
                    elif btn.tag == 'cancel':
                        self.sel_route = self.sel_color = self.sel_combo = None
                        self.phase     = P_SEL_ROUTE
                        self.buttons   = []

        # ── In-game ticket draw ──
        elif self.phase == P_DRAW_TIX:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i in range(len(self.pending_tix)):
                    ty = PAN_Y + 100 + i*122
                    if pygame.Rect(PAN_X+10, ty, PAN_W-20, 112).collidepoint(ev.pos):
                        if i in self.chosen_tix and len(self.chosen_tix) > self.min_tix:
                            self.chosen_tix.discard(i)
                        elif i not in self.chosen_tix:
                            self.chosen_tix.add(i)
                conf = pygame.Rect(PAN_X+10, PAN_Y+PAN_H-68, PAN_W-20, 54)
                if conf.collidepoint(ev.pos) and len(self.chosen_tix) >= self.min_tix:
                    self._confirm_tix()

        # ── Game over ──
        elif self.phase == P_GAME_OVER:
            for btn in self.buttons:
                if btn.hit(ev) and btn.tag == 'quit':
                    pygame.quit(); sys.exit()

    # ─────────────────────────────────────────────────────────────────────────
    # Per-frame update
    # ─────────────────────────────────────────────────────────────────────────

    def _update(self):
        now = pygame.time.get_ticks()
        if self.phase == P_TURN_START:
            if now - self.turn_start_t > 1800:
                self._start_turn()
        elif self.phase == P_AI_TURN:
            if now - self.ai_timer > 1800:
                self._advance_turn()

    # ─────────────────────────────────────────────────────────────────────────
    # Drawing
    # ─────────────────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(FELT)
        if self.game:
            self._draw_map()
            self._draw_log()
        self._draw_panel()
        self._draw_overlay()
        for btn in self.buttons:
            btn.draw(self.screen)
        pygame.display.flip()

    # ── Map ───────────────────────────────────────────────────────────────────

    def _draw_map(self):
        surf = pygame.Surface((MAP_W, MAP_H))
        surf.fill(MAP_BG)
        self._draw_routes(surf)
        self._draw_cities(surf)
        if self.game:
            self._draw_map_legend(surf)
        self.screen.blit(surf, (MAP_X, MAP_Y))
        pygame.draw.rect(self.screen, (90, 65, 30),
                         (MAP_X-2, MAP_Y-2, MAP_W+4, MAP_H+4), 3, border_radius=5)

    def _draw_map_legend(self, surf):
        """Small player-colour legend in the bottom-left corner of the map."""
        players = self.game.players
        lx, ly = 8, MAP_H - 14 - len(players)*18
        bg = pygame.Surface((160, len(players)*18 + 6), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        surf.blit(bg, (lx-2, ly-2))
        for i, p in enumerate(players):
            pc = PCOL[i % len(PCOL)]
            pygame.draw.circle(surf, BLACK, (lx+7, ly+i*18+7), 7)
            pygame.draw.circle(surf, pc,    (lx+7, ly+i*18+7), 5)
            tag = "(AI)" if p.isAi() else "(You)"
            label = f"P{i+1} {p.name} {tag}"
            lbl = fnt(11).render(label, True, pc)
            surf.blit(lbl, (lx+17, ly+i*18))

    def _draw_routes(self, surf):
        now = pygame.time.get_ticks()
        flash_key  = self.last_claim.get('key')
        flash_age  = now - self.last_claim.get('time', 0)
        flash_pidx = self.last_claim.get('pidx')
        FLASH_DUR  = 2200  # ms

        for key, slots in self.route_slots.items():
            c1, c2 = key
            if c1 not in CITY_POS or c2 not in CITY_POS:
                continue
            ax, ay = CITY_POS[c1]
            bx, by = CITY_POS[c2]
            n      = len(slots)
            is_flash = (key == flash_key and flash_age < FLASH_DUR)

            for si, s in enumerate(slots):
                off = (si - (n-1)/2.0) * 9
                (sax, say), (sbx, sby) = perp(ax, ay, bx, by, off)
                ia = (int(sax), int(say))
                ib = (int(sbx), int(sby))

                is_avail = (self.phase == P_SEL_ROUTE
                            and key in self.avail_routes
                            and s['owner'] is None)
                is_hover = (key == self.hover_route and s['owner'] is None)
                is_sel   = (key == self.sel_route   and s['owner'] is None)

                if s['owner'] is not None:
                    pcol = PCOL[s['owner'] % len(PCOL)]

                    # Flash: bright white/gold glow fades over FLASH_DUR
                    if is_flash:
                        t = 1.0 - (flash_age / FLASH_DUR)
                        glow_r = int(255 * t)
                        glow_g = int(230 * t)
                        glow_b = int(80  * t)
                        pygame.draw.line(surf, (glow_r, glow_g, glow_b),
                                         ia, ib, 20)

                    # Thick outlined bar in owner colour
                    pygame.draw.line(surf, BLACK,  ia, ib, 14)
                    pygame.draw.line(surf, pcol,   ia, ib, 10)
                    # Bright thin inner highlight
                    bright = tuple(min(255, c+80) for c in pcol)
                    pygame.draw.line(surf, bright, ia, ib,  3)

                    # Train-car markers along the route
                    self._draw_markers(surf, sax, say, sbx, sby,
                                       pcol, self.orig_edges[key]['weight'])

                    # Player badge at midpoint
                    mx2 = int((sax + sbx) / 2)
                    my2 = int((say + sby) / 2)
                    pygame.draw.circle(surf, BLACK, (mx2, my2), 9)
                    pygame.draw.circle(surf, pcol,  (mx2, my2), 7)
                    initial = str(s['owner'] + 1)
                    lbl = fnt(9, True).render(initial, True, WHITE)
                    surf.blit(lbl, lbl.get_rect(center=(mx2, my2)))

                else:
                    orig_col = ROUTE_COL.get(s['orig'], (130,130,130))
                    if is_sel:
                        pygame.draw.line(surf, YHL,           ia, ib, 13)
                    elif is_hover:
                        pygame.draw.line(surf, (255,255,100), ia, ib, 13)
                    elif is_avail:
                        pygame.draw.line(surf, WHITE,         ia, ib, 12)
                    lw = 7 if is_avail else 5
                    pygame.draw.line(surf, BLACK,    ia, ib, lw+2)
                    pygame.draw.line(surf, orig_col, ia, ib, lw)

    def _draw_markers(self, surf, ax, ay, bx, by, col, n):
        if n <= 0: return
        dx, dy = bx-ax, by-ay
        angle  = -math.degrees(math.atan2(dy, dx))
        for i in range(n):
            t  = (i + 0.5) / n
            cx = int(ax + dx*t)
            cy = int(ay + dy*t)
            car = pygame.Surface((15, 8), pygame.SRCALPHA)
            car.fill(col)
            pygame.draw.rect(car, BLACK, car.get_rect(), 1)
            rot = pygame.transform.rotate(car, angle)
            surf.blit(rot, rot.get_rect(center=(cx, cy)))

    def _draw_cities(self, surf):
        for city, (cx, cy) in CITY_POS.items():
            pygame.draw.circle(surf, (75, 48, 18), (cx, cy), 9)
            pygame.draw.circle(surf, (245, 225, 170), (cx, cy), 7)
            pygame.draw.circle(surf, BLACK, (cx, cy), 7, 1)
            for wi, word in enumerate(city.split()):
                s  = fnt(10).render(word, True, BLACK)
                bg = pygame.Surface((s.get_width()+2, s.get_height()+1))
                bg.fill(MAP_BG)
                surf.blit(bg, bg.get_rect(centerx=cx, top=cy+9+wi*12))
                surf.blit(s,   s.get_rect(centerx=cx, top=cy+9+wi*12))

    # ── Log ───────────────────────────────────────────────────────────────────

    def _draw_log(self):
        drect(self.screen, (18, 18, 32), (LOG_X, LOG_Y, LOG_W, LOG_H),
              rad=6, bw=2, bc=(55,55,85))
        blit(self.screen, "GAME LOG",
             (LOG_X+8, LOG_Y+5), sz=12, bold=True, col=(140,140,200))
        for i, (msg, pidx) in enumerate(self.messages[-7:]):
            age_alpha = max(160, 255 - i*14)
            if pidx is not None and pidx < len(PCOL):
                pc = PCOL[pidx]
                r = min(255, int(pc[0]*0.85 + age_alpha*0.15))
                g = min(255, int(pc[1]*0.85 + age_alpha*0.15))
                b = min(255, int(pc[2]*0.85 + age_alpha*0.15))
                col = (r, g, b)
            else:
                col = (age_alpha, age_alpha, min(age_alpha+40, 255))
            blit(self.screen, msg,
                 (LOG_X+8, LOG_Y+22+i*15), sz=13, col=col)

    # ── Right panel ───────────────────────────────────────────────────────────

    def _draw_panel(self):
        drect(self.screen, PAN_BG, (PAN_X, PAN_Y, PAN_W, PAN_H),
              rad=8, bw=2, bc=PAN_LITE)

        if self.game is None:
            self._draw_setup_panel(); return

        if self.phase in (P_INIT_TIX, P_DRAW_TIX):
            self._draw_tix_panel(); return

        player = self.game.players[self.player_idx]
        pidx   = self.player_idx

        # ── Header ──
        pcol = PCOL[pidx % len(PCOL)]
        drect(self.screen, pcol, (PAN_X+8, PAN_Y+10, PAN_W-16, 62), rad=8)
        label = player.name + ("  (AI)" if player.isAi() else "")
        blit(self.screen, label,
             (PAN_X+PAN_W//2, PAN_Y+26), sz=20, bold=True, col=WHITE, center=True)
        blit(self.screen, f"Score: {player.getPoints()}   ·   Trains left: {player.getNumTrains()}",
             (PAN_X+PAN_W//2, PAN_Y+47), sz=13, col=(225,225,225), center=True)

        # ── Hand ──
        drect(self.screen, PAN_MID, (PAN_X+8, PAN_Y+78, PAN_W-16, 122), rad=6)
        blit(self.screen, "YOUR HAND",
             (PAN_X+14, PAN_Y+82), sz=12, bold=True, col=(150,150,215))
        hand     = player.getHand()
        non_zero = [(c, n) for c, n in sorted(hand.items()) if n > 0]
        per_row, cw = 4, (PAN_W-24) // 4
        for i, (cname, cnt) in enumerate(non_zero):
            row, ci = i // per_row, i % per_row
            bx = PAN_X + 12 + ci*(cw+3)
            by = PAN_Y + 97 + row*40
            rc = ROUTE_COL.get(cname, (100,100,100))
            tc = TEXT_ON.get(cname, WHITE)
            drect(self.screen, rc, (bx, by, cw, 32), rad=5, bw=1, bc=WHITE)
            blit(self.screen, f"{cname[:4]}:{cnt}",
                 (bx + cw//2, by+16), sz=13, bold=True, col=tc, center=True)

        # ── Phase content ──
        self._draw_phase_section(PAN_Y+206, player)

        # ── Tickets ──
        ty = PAN_Y + 490
        drect(self.screen, PAN_MID, (PAN_X+8, ty, PAN_W-16, 165), rad=6)
        blit(self.screen, "DESTINATION TICKETS",
             (PAN_X+14, ty+5), sz=12, bold=True, col=(140,215,140))
        for i, (ticket, _done) in enumerate(list(player.tickets.items())[:6]):
            t1, t2, val = ticket
            completed = self._ticket_done(player, ticket)
            sym = '✓' if completed else '·'
            tc  = GHL if completed else (200,200,200)
            blit(self.screen,
                 f"{sym} {t1[:9]} → {t2[:9]}  ({val}pt)",
                 (PAN_X+14, ty+22+i*22), sz=13, col=tc)

        # ── Scoreboard ──
        sy = PAN_Y + 662
        drect(self.screen, PAN_MID, (PAN_X+8, sy, PAN_W-16, 148), rad=6)
        blit(self.screen, "SCOREBOARD",
             (PAN_X+14, sy+5), sz=12, bold=True, col=(215,200,100))
        scores = sorted(
            [(p.getPoints(), p.name, i) for i, p in enumerate(self.game.players)],
            reverse=True)
        for rank, (pts, name, pi) in enumerate(scores):
            pc    = PCOL[pi % len(PCOL)]
            arr   = '▶' if pi == self.player_idx else ' '
            tr    = self.game.players[pi].getNumTrains()
            tix   = self.game.players[pi].tickets
            done  = sum(1 for t, d in tix.items()
                        if self._ticket_done(self.game.players[pi], t))
            total = len(tix)
            # player colour dot
            pygame.draw.circle(self.screen, pc,
                               (PAN_X+20, sy+30+rank*24), 5)
            blit(self.screen,
                 f"{arr}{rank+1}. {name}: {pts}pts  🚂{tr}  🎫{done}/{total}",
                 (PAN_X+30, sy+22+rank*24), sz=12, col=pc)

    def _draw_phase_section(self, y, player):
        """250px content block between hand and tickets."""
        drect(self.screen, PAN_MID, (PAN_X+8, y, PAN_W-16, 278), rad=6)

        if self.phase == P_ACTION:
            blit(self.screen, "YOUR TURN — choose an action:",
                 (PAN_X+14, y+8), sz=13, bold=True, col=(185,185,240))

        elif self.phase in (P_DRAW_C1, P_DRAW_C2):
            title = "DRAW CARDS — Pick 1st card:" if self.phase == P_DRAW_C1 \
                    else "DRAW CARDS — Pick 2nd card:"
            blit(self.screen, title, (PAN_X+14, y+8), sz=13, bold=True, col=(185,185,240))
            if self.phase == P_DRAW_C2:
                blit(self.screen, "(wildcards disabled for 2nd pick)",
                     (PAN_X+14, y+26), sz=12, col=(160,160,195))

        elif self.phase == P_SEL_ROUTE:
            blit(self.screen, "PLACE TRAINS",
                 (PAN_X+14, y+8), sz=14, bold=True, col=(185,185,240))
            blit(self.screen, "Hover over a glowing route",
                 (PAN_X+14, y+30), sz=13, col=(175,175,220))
            blit(self.screen, "and click to claim it.",
                 (PAN_X+14, y+48), sz=13, col=(175,175,220))
            blit(self.screen, "(Esc / right-click to cancel)",
                 (PAN_X+14, y+66), sz=12, col=(130,130,165))
            if self.hover_route:
                c1, c2 = self.hover_route
                w      = self.orig_edges[self.hover_route]['weight']
                pts    = self.game.routeValues.get(w, 0)
                drect(self.screen, (36,58,36),
                      (PAN_X+10, y+86, PAN_W-20, 54), rad=6, bw=1, bc=GHL)
                blit(self.screen, f"{c1}  →  {c2}",
                     (PAN_X+16, y+92), sz=14, bold=True, col=YHL)
                blit(self.screen, f"Length {w}  ·  +{pts} points",
                     (PAN_X+16, y+112), sz=13, col=(200,240,200))

        elif self.phase == P_SEL_COLOR:
            c1, c2 = self.sel_route
            blit(self.screen, "Choose track colour:",
                 (PAN_X+14, y+8), sz=14, bold=True, col=(185,185,240))
            blit(self.screen, f"{c1}  →  {c2}",
                 (PAN_X+14, y+28), sz=13, col=YHL)

        elif self.phase == P_CONFIRM_R:
            c1, c2 = self.sel_route
            w      = self.orig_edges[self.sel_route]['weight']
            pts    = self.game.routeValues.get(w, 0)
            blit(self.screen, "Confirm route claim?",
                 (PAN_X+14, y+8), sz=14, bold=True, col=(185,185,240))
            drect(self.screen, (36,58,36),
                  (PAN_X+10, y+28, PAN_W-20, 70), rad=6, bw=1, bc=GHL)
            blit(self.screen, f"{c1}  →  {c2}",
                 (PAN_X+16, y+34), sz=16, bold=True, col=YHL)
            blit(self.screen, f"Length {w}  ·  +{pts} points",
                 (PAN_X+16, y+56), sz=13, col=(200,240,200))
            blit(self.screen, "Cards to spend:",
                 (PAN_X+14, y+108), sz=12, col=(165,195,165))
            cx2 = PAN_X + 14
            if self.sel_combo:
                for card, cnt in self.sel_combo.items():
                    if cnt > 0:
                        rc = ROUTE_COL.get(card, (100,100,100))
                        tc = TEXT_ON.get(card, WHITE)
                        drect(self.screen, rc, (cx2, y+124, 100, 26),
                              rad=5, bw=1, bc=WHITE)
                        blit(self.screen, f"{cnt}×{card}",
                             (cx2+50, y+137), sz=13, bold=True, col=tc, center=True)
                        cx2 += 108

        elif self.phase == P_AI_TURN:
            t    = pygame.time.get_ticks()
            dots = '.' * ((t // 380) % 4)
            blit(self.screen, f"AI is playing{dots}",
                 (PAN_X+14, y+10), sz=17, bold=True, col=(220,220,80))
            if self.ai_msg:
                # Simple word-wrap
                words = self.ai_msg.split()
                line = ''; lines = []
                for w in words:
                    test = line + (' ' if line else '') + w
                    if fnt(13).size(test)[0] < PAN_W-28:
                        line = test
                    else:
                        lines.append(line); line = w
                if line: lines.append(line)
                for li, l in enumerate(lines[:4]):
                    blit(self.screen, l, (PAN_X+14, y+38+li*20),
                         sz=13, col=(175,220,175))

        elif self.phase == P_TURN_START:
            blit(self.screen, "Get ready,",
                 (PAN_X+14, y+10), sz=14, col=(185,185,240))
            blit(self.screen, f"{player.name}!",
                 (PAN_X+14, y+32), sz=24, bold=True, col=YHL)
            blit(self.screen, "Click anywhere to continue",
                 (PAN_X+14, y+65), sz=13, col=(140,140,180))

    # ── Ticket panel (full panel for P_INIT_TIX / P_DRAW_TIX) ───────────────

    def _draw_tix_panel(self):
        is_init = (self.phase == P_INIT_TIX)
        pidx    = self.init_tix_i if is_init else self.player_idx
        player  = self.game.players[pidx]
        pcol    = PCOL[pidx % len(PCOL)]

        drect(self.screen, pcol,
              (PAN_X+8, PAN_Y+10, PAN_W-16, 60), rad=8)
        title = (f"{player.name}: Select Starting Tickets  (keep ≥2)"
                 if is_init
                 else f"{player.name}: Draw Tickets  (keep ≥1)")
        blit(self.screen, title,
             (PAN_X+PAN_W//2, PAN_Y+40), sz=13, bold=True, col=WHITE, center=True)

        blit(self.screen,
             f"Chosen: {len(self.chosen_tix)} / {len(self.pending_tix)}",
             (PAN_X+14, PAN_Y+78), sz=13, col=(200,200,200))

        for i, tix in enumerate(self.pending_tix):
            t1, t2, val = tix
            ty  = PAN_Y + 100 + i*122
            sel = i in self.chosen_tix
            bg  = (32,88,52) if sel else PAN_MID
            bc  = GHL        if sel else (60,60,98)
            drect(self.screen, bg,
                  (PAN_X+10, ty, PAN_W-20, 112), rad=8, bw=2, bc=bc)
            sym = '☑' if sel else '☐'
            blit(self.screen, f"{sym}  {t1}",
                 (PAN_X+18, ty+10), sz=15, bold=True, col=WHITE)
            blit(self.screen, f"     → {t2}",
                 (PAN_X+18, ty+32), sz=15, col=(200,220,200))
            blit(self.screen, f"     Value: {val} points",
                 (PAN_X+18, ty+54), sz=13, col=YHL)
            blit(self.screen, "     Click to toggle",
                 (PAN_X+18, ty+78), sz=11, col=(130,130,130))

        # Confirm button
        can = len(self.chosen_tix) >= self.min_tix
        drect(self.screen,
              (26,120,38) if can else (55,55,55),
              (PAN_X+10, PAN_Y+PAN_H-68, PAN_W-20, 54),
              rad=8, bw=2, bc=GHL if can else (80,80,80))
        blit(self.screen, '✓  CONFIRM SELECTION',
             (PAN_X+PAN_W//2, PAN_Y+PAN_H-41),
             sz=17, bold=True,
             col=WHITE if can else (100,100,100), center=True)

    # ── Setup panel (right side during game creation) ─────────────────────────

    def _draw_setup_panel(self):
        blit(self.screen, "TICKET TO RIDE",
             (PAN_X+PAN_W//2, PAN_Y+40), sz=20, bold=True, col=YHL, center=True)
        blit(self.screen, "Set up your game",
             (PAN_X+PAN_W//2, PAN_Y+68), sz=14, col=(170,170,215), center=True)
        if self.phase == P_SETUP_PC:
            blit(self.screen, "Step 1:",  (PAN_X+14, PAN_Y+130), sz=13, col=(130,130,175))
            blit(self.screen, "Human players?", (PAN_X+14, PAN_Y+150), sz=17, bold=True, col=WHITE)
        elif self.phase == P_SETUP_AIC:
            blit(self.screen, "Step 2:",  (PAN_X+14, PAN_Y+130), sz=13, col=(130,130,175))
            blit(self.screen, "AI players?", (PAN_X+14, PAN_Y+150), sz=17, bold=True, col=WHITE)
            blit(self.screen, f"Humans: {self.n_human}", (PAN_X+14, PAN_Y+182), sz=14, col=(175,200,175))
        elif self.phase == P_SETUP_AIREW:
            blit(self.screen, f"AI #{self.ai_rew_i+1} strategy:",
                 (PAN_X+14, PAN_Y+130), sz=15, bold=True, col=WHITE)
            info = [
                ("0 – Tickets", "Completes destination\nticket objectives"),
                ("1 – Routes",  "Builds long continuous\ntrain networks"),
                ("2 – Random",  "Balanced / adaptive\nstrategy"),
            ]
            for i, (name, desc) in enumerate(info):
                y2 = PAN_Y + 165 + i*65
                blit(self.screen, name,  (PAN_X+14, y2),    sz=14, bold=True, col=WHITE)
                for li, line in enumerate(desc.split('\n')):
                    blit(self.screen, line, (PAN_X+18, y2+18+li*16), sz=12, col=(155,155,190))

    # ── Overlays (map area + full screen) ────────────────────────────────────

    def _draw_overlay(self):
        # Setup: dim the map area and show instructions
        if self.phase in (P_SETUP_PC, P_SETUP_AIC, P_SETUP_AIREW):
            bg = pygame.Surface((MAP_W, MAP_H))
            bg.fill(MAP_BG)
            self.screen.blit(bg, (MAP_X, MAP_Y))
            pygame.draw.rect(self.screen, (90,65,30),
                             (MAP_X-2, MAP_Y-2, MAP_W+4, MAP_H+4), 3, border_radius=5)
            ov = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 168))
            self.screen.blit(ov, (MAP_X, MAP_Y))
            blit(self.screen, "TICKET  TO  RIDE",
                 (MAP_X+MAP_W//2, MAP_Y+120), sz=52, bold=True, col=YHL, center=True)
            blit(self.screen, "The classic railway adventure game",
                 (MAP_X+MAP_W//2, MAP_Y+195), sz=20, col=(210,210,210), center=True)
            if self.phase == P_SETUP_PC:
                q = "How many HUMAN players?"
            elif self.phase == P_SETUP_AIC:
                q = f"How many AI players?  (humans already set: {self.n_human})"
            else:
                q = f"Choose a strategy for AI #{self.ai_rew_i+1}:"
            blit(self.screen, q,
                 (MAP_X+MAP_W//2, MAP_Y+355), sz=26, bold=True, col=WHITE, center=True)

        # Turn-start banner over the map
        elif self.phase == P_TURN_START and self.game:
            player = self.game.players[self.player_idx]
            pcol   = PCOL[self.player_idx % len(PCOL)]
            ov     = pygame.Surface((MAP_W, 108), pygame.SRCALPHA)
            ov.fill((*pcol, 215))
            self.screen.blit(ov, (MAP_X, MAP_Y + MAP_H//2 - 54))
            ai_tag = "  [AI]" if player.isAi() else ""
            blit(self.screen, f"  {player.name}'s Turn!{ai_tag}",
                 (MAP_X+MAP_W//2, MAP_Y+MAP_H//2),
                 sz=42, bold=True, col=WHITE, center=True)
            blit(self.screen,
                 f"Score: {player.getPoints()}  ·  Trains: {player.getNumTrains()}",
                 (MAP_X+MAP_W//2, MAP_Y+MAP_H//2+48),
                 sz=16, col=(235,235,235), center=True)

        # AI action result banner — shown while we wait before advancing
        elif self.phase == P_AI_TURN and self.game and self.ai_msg:
            player = self.game.players[self.player_idx]
            pcol   = PCOL[self.player_idx % len(PCOL)]
            ov     = pygame.Surface((MAP_W, 62), pygame.SRCALPHA)
            ov.fill((*pcol, 195))
            self.screen.blit(ov, (MAP_X, MAP_Y + 8))
            blit(self.screen, self.ai_msg,
                 (MAP_X+MAP_W//2, MAP_Y+39),
                 sz=18, bold=True, col=WHITE, center=True)

        # Game over: full-screen overlay
        elif self.phase == P_GAME_OVER and self.game:
            ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 200))
            self.screen.blit(ov, (0, 0))
            blit(self.screen, "GAME  OVER",
                 (WIN_W//2, 148), sz=62, bold=True, col=YHL, center=True)
            scores = sorted(
                [(p.getPoints(), p.name, i) for i, p in enumerate(self.game.players)],
                reverse=True)
            wp, wn, _ = scores[0]
            blit(self.screen, f"Winner:  {wn}  with  {wp}  points!",
                 (WIN_W//2, 248), sz=30, bold=True, col=WHITE, center=True)
            for rank, (pts, name, pi) in enumerate(scores):
                pc = PCOL[pi % len(PCOL)]
                tr = self.game.players[pi].getNumTrains()
                blit(self.screen,
                     f"{rank+1}.  {name}:  {pts} points   ({tr} trains unused)",
                     (WIN_W//2, 312+rank*46), sz=22, col=pc, center=True)


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    display = TTRDisplay()
    display.run()


if __name__ == '__main__':
    main()
