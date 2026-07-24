"""
game_session.py
Server-side game state for a single Ticket to Ride session.

Mirrors the phase-based state machine from TTRDisplay.py but produces
JSON-serializable dicts instead of rendering to a pygame surface.
Every public method mutates state; callers call .serialize() afterwards.
"""
import TTRGameSim

# ── Phases ────────────────────────────────────────────────────────────────────
P_SETUP      = 'setup'
P_INIT_TIX   = 'init_tix'
P_TURN_START = 'turn_start'
P_ACTION     = 'action'
P_DRAW_C1    = 'draw_c1'
P_DRAW_C2    = 'draw_c2'
P_SEL_ROUTE  = 'sel_route'
P_SEL_COLOR  = 'sel_color'
P_CONFIRM_R  = 'confirm_r'
P_DRAW_TIX   = 'draw_tix'
P_AI_TURN    = 'ai_turn'
P_GAME_OVER  = 'game_over'

PLAYER_COLORS = ['#d22828', '#3278dc', '#28a528', '#d2af00', '#aa3cc8', '#e67300']


def _rkey(c1, c2):
    a, b = (c1, c2) if c1 < c2 else (c2, c1)
    return f"{a}|{b}"


class GameSession:

    def __init__(self):
        self.phase            = P_SETUP
        self.game             = None
        self.route_slots      = {}   # {key: [{'orig','owner','pcol'}]}
        self.orig_edges       = {}   # {key: {'weight','edgeColors'}}
        self.player_idx       = 0
        self.final_round      = False
        self.final_q          = []
        self.avail_routes     = {}   # {key: [colors]} for current human turn
        self.first_card       = None
        self.sel_route        = None  # route key string
        self.sel_color        = None
        self.sel_combo        = None
        self._playable_colors = []
        self.pending_tix      = []
        self.chosen_tix       = set()
        self.min_tix          = 1
        self.init_tix_i       = 0
        self.ai_msg           = ""
        self.messages         = []   # [{'text': str, 'pidx': int|None}]
        self.last_claim       = {'key': None, 'pidx': None}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _msg(self, text, pidx=None):
        self.messages.append({'text': str(text), 'pidx': pidx})
        if len(self.messages) > 10:
            self.messages.pop(0)

    def _snapshot_edges(self):
        self.route_slots = {}
        self.orig_edges  = {}
        for c1, c2, data in self.game.board.copyBoard.edges(data=True):
            key    = _rkey(c1, c2)
            colors = list(data['edgeColors'])
            self.route_slots[key] = [
                {'orig': col, 'owner': None, 'pcol': None} for col in colors
            ]
            self.orig_edges[key] = {
                'weight':     data['weight'],
                'edgeColors': list(colors),
            }

    def _refresh_slots(self):
        for key in self.route_slots:
            for s in self.route_slots[key]:
                s['owner'] = None
                s['pcol']  = None
        for pidx, player in enumerate(self.game.players):
            for c1, c2, data in player.playerBoard.iterEdges():
                key = _rkey(c1, c2)
                if key not in self.route_slots:
                    continue
                claimed = (data.get('edgeColors') or ['grey'])[0]
                for s in self.route_slots[key]:
                    if s['owner'] is None and (
                            s['orig'] == 'grey' or s['orig'] == claimed):
                        s['owner'] = pidx
                        s['pcol']  = claimed
                        break

    def _ticket_done(self, player, ticket):
        t1, t2, _ = ticket
        try:
            return (player.playerBoard.G.has_node(t1)
                    and player.playerBoard.G.has_node(t2)
                    and player.playerBoard.hasPath(t1, t2))
        except Exception:
            return False

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

    def _compute_avail_routes(self):
        self.avail_routes = {}
        player = self.game.players[self.player_idx]
        for ed in self.game.board.getEdgesData():
            c1, c2 = ed['edge']
            valid  = [col for col in ed['edgeColors']
                      if self.game.doesPlayerHaveCardsForEdgeColCheck(
                          player, c1, c2, col)]
            if valid:
                key = _rkey(c1, c2)
                self.avail_routes[key] = valid

    # ── Setup ─────────────────────────────────────────────────────────────────

    def start_game(self, n_human, n_ai, ai_strategies):
        total = n_human + n_ai
        if total < 1 or total > 5:
            raise ValueError("Need 1–5 players total")
        # Pad / truncate strategies list to length n_ai
        strats = list(ai_strategies) + [2] * n_ai
        strats = strats[:n_ai]

        names     = [f"Player {i+1}" for i in range(n_human)]
        self.game = TTRGameSim.Game(n_human, n_ai, strats, player_names=names)
        self._snapshot_edges()
        self.init_tix_i = 0
        self.phase      = P_INIT_TIX
        self._process_ai_init_tix()

    def _process_ai_init_tix(self):
        """Auto-process consecutive AI players; stop at the first human."""
        while self.init_tix_i < len(self.game.players):
            player = self.game.players[self.init_tix_i]
            if player.isAi():
                self.game.aiModel.apply_draw_tickets_turn_real(player)
                self._msg(f"{player.name} chose starting tickets",
                          self.init_tix_i)
                self.init_tix_i += 1
            else:
                self.pending_tix = self.game.deck.dealTickets(
                    self.game.numTicketsDealt)
                self.chosen_tix  = set(range(min(2, len(self.pending_tix))))
                self.min_tix     = 2
                return
        # All players done — start the game
        self.game.posToMove = 0
        self.player_idx     = 0
        self.phase          = P_TURN_START

    def confirm_init_tix(self, indices):
        idx_set = set(int(i) for i in indices)
        player  = self.game.players[self.init_tix_i]
        chosen  = [self.pending_tix[i] for i in sorted(idx_set)
                   if i < len(self.pending_tix)]
        for t in chosen:
            player.addTicket(t)
        for i, t in enumerate(self.pending_tix):
            if i not in idx_set:
                self.game.deck.addToTicketDiscard(t)
        self._msg(f"{player.name} kept {len(chosen)} starting ticket(s)",
                  self.init_tix_i)
        self.pending_tix = []
        self.chosen_tix  = set()
        self.init_tix_i += 1
        self._process_ai_init_tix()

    # ── Turn management ───────────────────────────────────────────────────────

    def start_turn(self):
        """Called by client after dismissing the turn-start banner."""
        player = self.game.players[self.player_idx]
        if player.isAi():
            self._exec_ai_turn(player)
            self.phase = P_AI_TURN
        else:
            self.phase = P_ACTION

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
                self.final_q    = [(start + i) % n for i in range(n)]
                self.player_idx = self.final_q.pop(0)
                self._msg("★ FINAL ROUND — everyone gets one last turn!")
            else:
                self.game.advanceOnePlayer()
                self.player_idx = self.game.posToMove

        self.ai_msg = ""
        self.phase  = P_TURN_START

    def _end_game(self):
        for p in self.game.players:
            self.game.scorePlayerTickets(p)
        self.game.scoreLongestPath()
        self.phase = P_GAME_OVER
        self._msg("=== GAME OVER ===")

    def advance_ai_turn(self):
        """Client calls this after the AI result has been displayed."""
        self._advance_turn()

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
            key = _rkey(c1, c2)
            self.last_claim = {'key': key, 'pidx': self.player_idx}
        elif mv == 'cards':
            self.ai_msg = f"{player.name} drew 2 train cards"
        else:
            self.ai_msg = f"{player.name} drew destination tickets"
        self._msg(self.ai_msg, self.player_idx)
        self._refresh_slots()

    # ── Human actions ─────────────────────────────────────────────────────────

    def action_draw_cards(self):
        self.first_card = None
        self.phase      = P_DRAW_C1

    def action_claim_route(self):
        self._compute_avail_routes()
        if not self.avail_routes:
            self._msg("No claimable routes right now.", self.player_idx)
            return False
        self.phase = P_SEL_ROUTE
        return True

    def action_draw_tickets(self):
        if not self.game.deck.tickets:
            self._msg("Ticket deck is empty.", None)
            return False
        self.pending_tix = self.game.deck.dealTickets(self.game.numTicketsDealt)
        self.chosen_tix  = {0}
        self.min_tix     = 1
        self.phase       = P_DRAW_TIX
        return True

    def pick_card(self, source, card=None):
        player = self.game.players[self.player_idx]
        if source == 'face_up' and card:
            drawn = self.game.deck.pickFaceUpCard(card)
            player.addCardToHand(drawn)
            self._msg(f"{player.name} picked {drawn} (face-up)", self.player_idx)
            if self.phase == P_DRAW_C1:
                self.first_card = drawn
                if drawn == 'wild':
                    self._advance_turn()      # wild face-up ends the turn
                else:
                    self.phase = P_DRAW_C2
            else:
                self._advance_turn()
        elif source == 'face_down':
            drawn = self.game.deck.pickFaceDown()
            if drawn:
                player.addCardToHand(drawn)
                self._msg(f"{player.name} drew from deck ({drawn})",
                          self.player_idx)
            if self.phase == P_DRAW_C1:
                self.first_card = drawn
                self.phase      = P_DRAW_C2
            else:
                self._advance_turn()

    def click_route(self, c1, c2):
        key = _rkey(c1, c2)
        if key not in self.avail_routes:
            return
        self.sel_route = key
        colors = self.avail_routes[key]
        player = self.game.players[self.player_idx]
        weight = self.orig_edges[key]['weight']

        # Expand grey slots to actual playable colours
        playable = []
        for col in colors:
            if col == 'grey':
                for hc, hcnt in player.hand.items():
                    if (hc != 'wild' and hcnt > 0
                            and hcnt + player.hand.get('wild', 0) >= weight
                            and hc not in playable):
                        playable.append(hc)
            elif col not in playable:
                playable.append(col)

        if not playable:
            self._msg("No valid card combination for this route.",
                      self.player_idx)
            self.sel_route = None
            return

        if len(playable) == 1:
            self.sel_color = playable[0]
            self.sel_combo = self._best_combo(player, self.sel_color, weight)
            self.phase     = P_CONFIRM_R
        else:
            self._playable_colors = playable
            self.phase            = P_SEL_COLOR

    def select_color(self, color):
        player = self.game.players[self.player_idx]
        weight = self.orig_edges[self.sel_route]['weight']
        self.sel_color = color
        self.sel_combo = self._best_combo(player, color, weight)
        self.phase     = P_CONFIRM_R

    def confirm_claim(self):
        player = self.game.players[self.player_idx]
        c1, c2 = self.sel_route.split('|')
        weight = self.orig_edges[self.sel_route]['weight']
        combo  = self.sel_combo

        if combo is None:
            self._msg("No valid card combination found.", self.player_idx)
            self.phase = P_ACTION
            self.sel_route = self.sel_color = self.sel_combo = None
            return

        player.playerBoard.addEdge(c1, c2, weight, self.sel_color)
        self.game.board.removeEdge(c1, c2, self.sel_color)
        pts = self.game.routeValues[weight]
        player.addPoints(pts)
        for card, cnt in combo.items():
            player.removeCardsFromHand(card, cnt)
            self.game.deck.addToDiscard([card] * cnt)
        player.playNumTrains(weight)

        self.last_claim = {'key': self.sel_route, 'pidx': self.player_idx}
        self._msg(
            f"{player.name} claimed {c1} → {c2}  "
            f"(len {weight}, +{pts} pts, {player.getNumTrains()} trains left)",
            self.player_idx,
        )
        self.sel_route = self.sel_color = self.sel_combo = None
        self._advance_turn()

    def confirm_tix(self, indices):
        idx_set = set(int(i) for i in indices)
        player  = self.game.players[self.player_idx]
        chosen  = [self.pending_tix[i] for i in sorted(idx_set)
                   if i < len(self.pending_tix)]
        for t in chosen:
            player.addTicket(t)
        for i, t in enumerate(self.pending_tix):
            if i not in idx_set:
                self.game.deck.addToTicketDiscard(t)
        self._msg(f"{player.name} kept {len(chosen)} ticket(s)", self.player_idx)
        self.pending_tix = []
        self.chosen_tix  = set()
        self._advance_turn()

    def cancel(self):
        if self.phase in (P_SEL_COLOR, P_CONFIRM_R):
            self.sel_route = self.sel_color = self.sel_combo = None
            self._playable_colors = []
            self.phase = P_SEL_ROUTE
        elif self.phase == P_SEL_ROUTE:
            self.sel_route        = None
            self.avail_routes     = {}
            self._playable_colors = []
            self.phase            = P_ACTION
        elif self.phase == P_DRAW_C1:
            self.phase = P_ACTION

    # ── Serialization ─────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        if self.game is None:
            return {'phase': self.phase}

        players = []
        for i, p in enumerate(self.game.players):
            tickets = []
            for ticket in p.tickets:
                t1, t2, val = ticket
                tickets.append({
                    'c1': t1, 'c2': t2,
                    'value': val,
                    'done': self._ticket_done(p, ticket),
                })
            players.append({
                'idx':     i,
                'name':    p.name,
                'is_ai':   p.isAi(),
                'hand':    {k: v for k, v in p.hand.items() if v > 0},
                'tickets': tickets,
                'points':  p.getPoints(),
                'trains':  p.getNumTrains(),
                'color':   PLAYER_COLORS[i % len(PLAYER_COLORS)],
            })

        sel_route_data = None
        if self.sel_route and self.sel_route in self.orig_edges:
            c1, c2 = self.sel_route.split('|')
            w   = self.orig_edges[self.sel_route]['weight']
            pts = self.game.routeValues.get(w, 0)
            sel_route_data = {
                'key': self.sel_route, 'c1': c1, 'c2': c2,
                'weight': w, 'pts': pts,
            }

        combo_display = None
        if self.sel_combo:
            combo_display = {k: v for k, v in self.sel_combo.items() if v > 0}

        return {
            'phase':           self.phase,
            'player_idx':      self.player_idx,
            'init_tix_i':      self.init_tix_i,
            'players':         players,
            'route_slots':     self.route_slots,
            'orig_edges':      self.orig_edges,
            'face_up_cards':   list(self.game.deck.getDrawPile()),
            'deck_count':      (len(self.game.deck.cards)
                                + len(self.game.deck.getDiscardPile())),
            'messages':        list(self.messages),
            'pending_tix':     [{'c1': t[0], 'c2': t[1], 'value': t[2]}
                                 for t in self.pending_tix],
            'chosen_tix':      list(self.chosen_tix),
            'min_tix':         self.min_tix,
            'avail_routes':    dict(self.avail_routes),
            'sel_route':       sel_route_data,
            'sel_color':       self.sel_color,
            'playable_colors': list(self._playable_colors),
            'combo':           combo_display,
            'ai_msg':          self.ai_msg,
            'last_claim':      dict(self.last_claim),
            'final_round':     self.final_round,
        }
