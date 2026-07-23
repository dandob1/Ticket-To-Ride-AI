import TTRGameSim
import TTRPlayer
import TTRPrint
import TTRBoard
import copy
import random
import math
import collections
class MTNode:
    def __init__(self, observation, move, parent):
        self.children = []
        self.state = observation
        self.move = move
        self.parent = parent
        self.visit_count = 0
        self.value = 0
        pass

    def search(self, state):
        return False

    """
    Searches the tree for a given state
    """
    def dfs(self, state):
        
        if self.compareStates(self.state, state):
            return True
        
        if len(self.children) == 0:
            
            return False

        for child in self.children:
            if child.dfs(state) == True:
                return True
        return False

    """
    Compares two states
    """
    def compareStates(self, state1, state2):
        
        for edge1 in state1['edges']:
            found = False
            for edge2 in state2['edges']:
                if edge1 == edge2:
                    found = True
            if not found:
                return False
        
        if state1['draw_pile'] != state2['draw_pile']:
            return False

        return True

class AI:
    def __init__(self, game, board):
        self.root = None
        self.game = game
        self.board = board
    
    """
    Entry point
    """
    def monteCarlo(self, player, depth):
        # State will be represented as a player
        state = self.game.getObservations(player)

        # State of the game when AI is called
        self.root = MTNode(state, None, None)

        # Build out the tree
        for i in range (0, 1000):
            self.simulate(state, depth, self.root)
        
        # Do a 1-layer bfs to find the best score move
        if not self.root.children:
            # No legal actions
            return None

        # Pick the most-visited child (the "robust child"), breaking ties by
        # average value. Selecting by raw total value is biased toward whichever
        # child happened to be expanded first (and therefore visited most), so
        # it is a poor final-move criterion.
        def child_score(c):
            avg = c.value / c.visit_count if c.visit_count > 0 else float('-inf')
            return (c.visit_count, avg)

        best_child = max(self.root.children, key=child_score)
        best_action = best_child.move
        best_avg = best_child.value / best_child.visit_count if best_child.visit_count > 0 else 0

        print(f"the best action is {best_action}")
        if(best_action["move"] == "tickets"):
            print(f"Current Destination Tickets:  {player.tickets}" )
        elif(best_action["move"] == "cards"):
            print(f"Current Cards: {player.hand}")
        print(f"current score {best_avg:.2f} (visits {best_child.visit_count})")
        return best_action

    def backpropagate(self, node, reward):
        # Backpropagate up the tree, updating the score of the state
        while node is not None:
            node.visit_count += 1
            node.value += reward
            node = node.parent

    def simulate(self,state, depth, node):
        # Terminal depth or no moves
        legal_actions = self.game.getLegalActions(state['player'])
        if depth == 0 or not legal_actions:
            reward = self.game.getReward(state['player'] )
            self.backpropagate(node, reward)
            return reward

        # Continue expansion if there are remaining legal actions
        #   not represented by children nodes
        if len(node.children) < len(legal_actions):
            tried_moves = [child.move for child in node.children]
            untried_actions = [a for a in legal_actions if a not in tried_moves]
            # Pick a move that hasn't been tried already
            if untried_actions:
                action = random.choice(untried_actions)
            else:
                action = random.choice(legal_actions)

            # Simulate the action
            new_state = self.makeNextMove(state, action)
            new_node = MTNode(new_state, action, node)
            node.children.append(new_node)
            
            # Random rollout to terminal
            reward = self.rollout(new_state, depth - 1, playerToTrack=node.state['player'])
            self.backpropagate(new_node, reward)
            return reward

        # Selection - Move down the existing tree
        # Use UCT score to find best path
        best_child = None
        best_uct = float('-inf')

        for child in node.children:
            uct = self.uct_value(node, child)
            if uct > best_uct:
                best_uct = uct
                best_child = child
        
        next_node = best_child
        next_state = next_node.state

        reward = self.simulate(next_state, depth - 1, next_node)

        return reward
        
    def uct_value(self, parent, child, c=math.sqrt(2)):
        if child.visit_count == 0:
            return float('inf')
        
        parent_visits = max(parent.visit_count, 1)

        exploitation = child.value / child.visit_count
        exploration = c * math.sqrt(math.log(parent_visits) / child.visit_count)
        return exploitation + exploration

    def rollout(self, state, depth, playerToTrack):
        # Play forward from `state` for up to `depth` moves, then evaluate the
        # single state actually reached. The previous implementation summed a
        # fresh reward at every recursion step, which inflated values by an
        # amount that depended on how deep the rollout ran and made the
        # estimates essentially meaningless.
        current = state
        steps = 0

        while steps < depth:
            player = current['player']

            # Stop once the (near) out-of-trains end condition is hit.
            if self.game.checkEndingCondition(player):
                break

            legal_actions = self.game.getLegalActions(player)
            if not legal_actions:
                break

            action = self.rollout_policy(player, legal_actions)
            current = self.makeNextMove(current, action)
            steps += 1

        # Evaluate the evolved player at the end of the rollout so the estimate
        # reflects the progress made during the rollout.
        return self.game.getReward(current['player'])

    def rollout_policy(self, player, legal_actions):
        """Rollout action selection.

        Points are only earned by claiming routes, so bias heavily toward
        claiming. Also gate ticket-drawing behind a trains-remaining check —
        incomplete tickets are a point *penalty*, and near end-game there is
        almost never enough time to finish newly drawn ones.
        """
        train_actions  = [a for a in legal_actions if a['move'] == 'train']
        ticket_actions = [a for a in legal_actions if a['move'] == 'tickets']

        # Strong bias toward claiming routes (weighted by their point value)
        if train_actions and random.random() < 0.75:
            weights = [self.game.routeValues[a['edge']['weight']]
                       for a in train_actions]
            return random.choices(train_actions, weights=weights, k=1)[0]

        # Don't draw tickets if trains are running low — unfinished tickets
        # carry a large negative-point penalty. Gate at 35 so the AI only
        # draws tickets in the very early game (first ~10 trains spent).
        if ticket_actions and player.getNumTrains() <= 35:
            non_ticket = [a for a in legal_actions if a['move'] != 'tickets']
            if non_ticket:
                return random.choice(non_ticket)

        # Cap outstanding (uncompleted) tickets — accumulating more tickets
        # than can realistically be finished is the #1 cause of negative scores.
        if ticket_actions:
            outstanding = sum(1 for t in player.tickets if not player.tickets[t])
            if outstanding >= 4:
                non_ticket = [a for a in legal_actions if a['move'] != 'tickets']
                if non_ticket:
                    return random.choice(non_ticket)

        return random.choice(legal_actions)
    
    # Transition function between states
    def makeNextMove(self, state, action):
        new_state = self.makeStateCopy(state)
    
        # 1. Claim a Route
        if action['move'] == 'train':
            city1 =action['edge']['edge'][0]
            city2 =action['edge']['edge'][1]
            routeDist =action['edge']['weight'] 
            
            # Get random valid coloring
            color = random.choice(action['possible_cards'])
            
            keys = color.keys()
            choice = None

            for key in keys:
                if key != 'wild':
                    choice = key

            # Add claimed edge to the board
            new_state['player'].playerBoard.addEdge(city1, city2, routeDist, choice) 
            
            # Remove used cards
            for card, count in color.items():
                new_state['player'].removeCardsFromHand(card, count) 
            
            # Spend the trains used to claim this route. Without this the
            # simulation never approaches the end-game condition and the AI
            # cannot reason about the cost of routes or when the game ends.
            new_state['player'].playNumTrains(routeDist)

            # Give points
            new_state['player'].addPoints(self.game.routeValues[routeDist])
            #the player's theorectical points for entering this state

        # 2. Draw Train Cards
        elif action['move'] == 'cards':
            self.apply_draw_cards_turn(new_state)

        # 3. Draw Route Tickets
        else:
            self.apply_draw_tickets_turn(new_state)
        
        return new_state

    # Draw two cards for the given "card action"
    def apply_draw_cards_turn(self, state):
        player = state['player']
        face_up = list(state['draw_pile'])
        face_down = list(state['face_down'])

        if not face_up and not face_down:
            return
        
        first_draw_was_faceup_wild = False

        for draw_index in range(2):
            if draw_index == 1 and first_draw_was_faceup_wild:
                break

            # Make a list of all possible choices
            # - ("face_down", None)
            # - ("face_up, index")
            choices = []

            if face_down:
                choices.append(("face_down", None))

            for idx, color in enumerate(face_up):
                if draw_index == 1 and color == "wild":
                    continue
                choices.append(("face_up", idx))

            if not choices:
                break

            from_where, idx = random.choice(choices)

            if from_where == "face_down":
                drawn_color = face_down.pop()
                player.hand[drawn_color] += 1
                
            elif from_where == "face_up":
                drawn_color = face_up.pop(idx)
                player.hand[drawn_color] += 1

                if face_down:
                    replacement = face_down.pop()
                    face_up.append(replacement)

                if drawn_color == "wild" and draw_index == 0:
                    first_draw_was_faceup_wild = True
        
        # Update state
        state['draw_pile'] = face_up
        state['face_down'] = face_down


    def apply_draw_tickets_turn(self, state):
        player = state["player"]
        ticket_deck = state["ticket_deck"]
        ticket_discard = state["ticket_discard"]

        num_deal = getattr(self.game, "numTicketsDealt", 3)
        if not ticket_deck:
            return
        
        draw_count = min(num_deal, len(ticket_deck))
        drawn = []
        for _ in range(draw_count):
            drawn.append(ticket_deck.pop())

        keep_count = random.randint(1, draw_count)
        tickets_to_keep = random.sample(drawn, keep_count)

        for t in tickets_to_keep:
            player.tickets[t] = False

        for t in drawn:
            if t not in tickets_to_keep:
                ticket_discard.append(t)

        state["ticket_deck"] = ticket_deck
        state["ticket_discard"] = ticket_discard

    def makeStateCopy(self, state):
        player = state['player'].clone_for_sim()
        edges = state['edges'].copy() if hasattr(state['edges'], "copy") else state['edges']
        
        # Train cards
        draw_pile = list(state['draw_pile'])
        face_down = list(state.get("face_down", []))

        # Tickets
        ticket_deck = list(state.get("ticket_deck", []))
        ticket_discard = list(state.get("ticket_discard", []))

        player_info = {
            pid: info.copy() if hasattr(info, "copy") else info
            for pid, info in state['public_player_info'].items()
        }
        return {
            'edges': edges,
            'player': player,
            'draw_pile': draw_pile,
            'face_down': face_down,
            'ticket_deck': ticket_deck,
            'ticket_discard': ticket_discard,
            'public_player_info': player_info,
        }
    
    # Actually apply the chosen action
    def apply_action(self, player, action):
        # 1. Claim a Train Route
        if action['move'] == 'train':
            self.apply_claim_route_real(player, action)

        # 2. Draw Train Cards
        elif action['move'] == 'cards':
            self.apply_draw_cards_turn_real(player)

        # 3. Draw Route Tickets
        elif action['move'] == 'tickets':
            self.apply_draw_tickets_turn_real(player)

    def apply_claim_route_real(self, player, action):
        edge = action['edge']
        city1, city2 = edge['edge']
        routeDist = edge['weight']
        combos = action['possible_cards']

        #choose a card combination
        best = max(combos, key=lambda combo:self.evaluate_card_combo(player, edge, combo))
        #pick a non wild color for the track
        color_choice = 'wild'  # default
        for c in best.keys():
            if c != 'wild':
                color_choice = c
                break

        #claim route on player board
        player.playerBoard.addEdge(city1, city2, routeDist, color_choice)

        #remove route from main board
        self.game.board.removeEdge(city1, city2, color_choice)

        #add points
        player.addPoints(self.game.routeValues[routeDist])

        #remove cards from hand and add to discard
        for c, count in best.items():
            player.removeCardsFromHand(c, count)
            self.game.deck.addToDiscard([c] * count)

        #remove trains
        player.playNumTrains(routeDist)

    def evaluate_card_combo(self, player, edge, combo):
        hand = player.getHand()
        route_len = edge["weight"]
        score = 0.0

        score += float(route_len)
        wilds_used = combo.get("wild", 0) or 0
        if wilds_used > 0:
            score -= 2.0 * wilds_used

        for color, count_used in combo.items():
            if color == "wild":
                continue
            have_before = hand.get(color, 0)
            have_after = have_before - count_used
            if have_after < 0:
                score -= 100.0
                continue

            if have_before > 0:
                relative_cost = count_used / (have_before * 1e-6)
                score -= 1.0 * relative_cost
            else:
                score -= 3.0

        total_wilds_in_hand = hand.get("wild", 0)
        wilds_left = total_wilds_in_hand - wilds_used
        if wilds_left > 0:
            score += 0.3 * wilds_left
        return score

    def apply_draw_cards_turn_real(self, player):
        deck = self.game.deck
        first_draw_was_faceup_wild = False

        for draw_index in range(2):
            if draw_index == 1 and first_draw_was_faceup_wild:
                break

            face_up = list(deck.getDrawPile())
            choices = []

            if deck.cardsLeft() > 0 or deck.getDiscardPile():
                choices.append(("face_down", None))

            for card in face_up:
                if draw_index == 1 and card == "wild":
                    continue
                choices.append(("face_up", card))

            if not choices:
                break

            scored = []
            for source, card in choices:
                if source == "face_up":
                    value = self.evaluate_train_card(player, card)
                else:
                    value = self.estimate_face_down_value(player, deck)
                scored.append(((source, card), value))

            (source, card), _ = max(scored, key=lambda x: x[1])

            if source == "face_down":
                drawn = deck.pickFaceDown()
                if drawn is None:
                    break
                player.addCardToHand(drawn)
            else:
                drawn = deck.pickFaceUpCard(card)
                player.addCardToHand(drawn)

                if draw_index == 0 and drawn == "wild":
                    first_draw_was_faceup_wild = True

    """
    Estimates the score of a given train card
    """
    def evaluate_train_card(self, player, color, state=None):
        if color == "wild":
            return 6.0

        board = self.game.board
        route_values = self.game.routeValues
        tickets = getattr(player, 'tickets', [])
        player_board = player.playerBoard

        try:
            player_cities = set(player_board.getCities())
        except Exception:
            player_cities = set()

        same_color_edges = []
        for edge in board.getEdgesData():
            if color in edge['edgeColors']:
                same_color_edges.append(edge)

        if not same_color_edges:
            return 0.1

        score = 1.0

        for edge in same_color_edges:
            (c1, c2) = edge['edge']
            length   = edge['weight']
            route_val = route_values.get(length, length)
            score += route_val / 10.0
            if c1 in player_cities or c2 in player_cities:
                score += 0.7
            for (t1, t2, val) in tickets:
                if c1 in (t1, t2) or c2 in (t1, t2):
                    score += val / 40.0

        hand = player.getHand()
        count_of_color = hand.get(color, 0)
        score += 0.4 * count_of_color

        return score

    """
    Estimates the score of drawing a face down card
    """
    def estimate_face_down_value(self, player, deck):
        remaining = list(deck.cards) + deck.getDiscardPile() + deck.getDrawPile()
        if not remaining:
            return 0.0
        
        counts = collections.Counter(remaining)
        total = sum(counts.values())

        expected = 0.0
        for color, cnt in counts.items():
            expected += (cnt / total) * self.evaluate_train_card(player, color)

        return expected

    def apply_draw_tickets_turn_real(self, player):
        deck = self.game.deck
        num_deal = self.game.numTicketsDealt

        tickets = deck.dealTickets(num_deal)

        scored = [(t, self.evaluate_ticket(player, t)) for t in tickets]

        scored.sort(key=lambda x: x[1], reverse=True)

        trains_left = player.getNumTrains()
        # Raise the keep threshold as trains deplete so the AI stops
        # collecting tickets it cannot possibly finish.
        if trains_left >= 35:
            threshold = 0.5
        elif trains_left >= 25:
            threshold = 1.5
        else:
            threshold = 3.5

        kept = []
        kept_set = set()

        for t, score in scored:
            if score > threshold:
                kept.append(t)
                kept_set.add(t)

        # Always keep at least one ticket — but only if it isn't going to
        # cost more points than it's worth (score < -value means we'd
        # definitely lose more than the ticket is worth).
        if not kept:
            best_t, best_score = scored[0]
            t_value = best_t[2]
            if best_score > -t_value:
                kept.append(best_t)
                kept_set.add(best_t)
            # else: keep nothing this round — discarding all is intentional

        for t in kept:
            player.addTicket(t)

        for t, _ in scored:
            if t not in kept_set:
                deck.addToTicketDiscard(t)

    def evaluate_ticket(self, player, ticket):
        city1, city2, value = ticket

        board = self.game.board
        player_board = player.playerBoard

        try:
            total_dist = board.getPathWeight(city1, city2)  # uses Dijkstra
        except Exception:
            return -999

        try:
            path_nodes = board.getShortestPath(city1, city2)
            path_edges = list(zip(path_nodes, path_nodes[1:]))
        except Exception:
            path_edges = []

        claimed_dist = 0
        for u, v in path_edges:
            if player_board.hasEdge(u, v):
                claimed_dist += board.getEdgeWeight(u, v)

        remaining_dist = max(total_dist - claimed_dist, 0)

        if remaining_dist == 0:
            return value + 20

        trains_left = player.getNumTrains()

        # Hard block — not enough trains to complete this ticket → big penalty
        if remaining_dist > trains_left:
            return -(value * 2.5)

        # Risky — completing this ticket would consume more than 65% of all
        # remaining trains, leaving very little flexibility for other routes
        if remaining_dist > trains_left * 0.65:
            return -(value * 0.8)

        efficiency = value / (remaining_dist + 1e-6)
        return efficiency