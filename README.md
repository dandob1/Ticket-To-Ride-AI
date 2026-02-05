# Ticket to Ride AI

1. Install `requirements.txt` with `pip install requirements.txt`
2. Run `python TTRGameSim.py`
3. To play against the AI, type `2` players and select `1` AI when prompted
4. You can also make `2` AI play against each other by selecting `2` AI when prompted
5. Note: Final scores may appear negative. To avoid long runtimes, the current implementation (2/4/2026) limits simulations to approximately 25% of a full game. Since endgame is not reached, final scores are significantly deducted.


# Blog:

## Problem Statement
Ticket to Ride (TTR) is a multiplayer board game where players collect colored train cards and claim routes on a map of North America to complete destination tickets. Claiming routes and completing destination tickets leads to a score increase and are the most desirable actions throughout the game. Each turn a player has the option of taking any of the 3 options: drawing colored route cards, drawing new destination tickets or claiming an existing route. While these options seem simple, its difficult to coordinate which of the three actions is best for the current move at hand. Each player is unaware of the exact cards opponents hold, which tickets they are trying to construct and any potential routes that may be blocked in the future.

Therefore this makes the game a stochastic sequential decision problem. For an AI controlled player going against other users, must select one action that maximizes its eventual score by the end of the game and consider long term planning and outcomes. The shuffled decks, random ticket draws and other players actions result in a stochastic environment and given the opponent hands and ticket sets are hidden the resulting statespace is only partially observable. The resulting goal of this project is to design and implement an AI agent that can play Ticket to Ride using only a model of the rules and live search for predicted outcomes. Each round the agent must choose a single move that will maximize the final expected score according to the game rules.

## Related solutions to similar problems
Given the incredibly large number of possible moves, outcomes and steps the structure of this problem is similar to other board games such as Go, Chess or Catan where there are an extreme number of branching factors, unecertainty about opponents future actions, and an inability to "solve" the game as has been done in simpler game such as tic-tac-toe. In many of these games, using Monte Carlo Tree Search seems like the only valid approach because of its ability to handle extremely large numbers of possible moves by randomly trying out sequences of moves instead of exhaustively exploring all possibilities. MCTS has been applied successfully to Go, Chess, Checkers and other games with large state spaces. Ticket to Ride shares the same challenges that the exact value of any given move is difficult to perfectly calculate, but we can roll out semi simulated games to estimate each moves potential value.

There are some implementations already with other basic algorithms such as a [regular breadth first search](https://github.com/ss2cp/AI-TicketToRide) or [reinforcement learning](https://github.com/mcandocia/tickets_ai). We choose to do Monte Carlo Tree Search as a different approach that made the most sense for this game with a large state space.
## State space, actions, transitions, and observations

### Natural Language Description
  In Ticket to Ride, a game state captures information about every player’s cards and trains, and the board itself. The board has vertices and edges, represented as city destinations and train routes, respectively. Every train route has two destinations it connects, the color and player association of the route, and the length of the route. The state also contains information about each player’s possessions. At any time in the game, a player can have trains of varying colors to place on the board and different destination tickets. 
	The state space of Ticket to Ride is the set of all possible states. In other words, it is the set of all possible information combinations about the board and player-specific information. With over 140 cards and 30 destination vertices, it is evident that this state space cannot be searched using a simple breadth-first search or A* search. We can also express the state space in mathematical notation.

### Mathematical Description
As mentioned above, the state space of Ticket to Ride consists of the board state, the cards in players' hands, and the current face-up train cards.

#### Players
$P = \{ P_1, P_2, \ldots, P_k \}$

Each player has a set of trains and destination tickets in their hand:
$P_{i_{trains}} = \{Tr_1, Tr_2, \ldots, Tr_k\}$
$P_{i_{tickets}} = \{T_1, T_2, \ldots, T_k\}$

#### Colors
$c = \{ \text{Purple}, \text{White}, \text{Blue}, \text{Yellow}, \text{Orange}, \text{Black}, \text{Red}, \text{Green} \}$

#### Vertices (Cities)
$C = \{ C_{ny}, C_{la}, C_{ph}, \ldots, C_{j} \}$


#### Edges (Train Routes)
Edges are unordered pairs of distinct cities:
$E = \{ (C_i, C_j) \mid C_i, C_j \in C,\ i \neq j \}$

Each edge $e \in E$ is defined by the functions:

- Weight (number of trains required):
  $$w : E \to \mathbb{N}$$

- Color of the route:
  $$c : E \to c$$

- Player assignment (or unclaimed):
  $$p : E \to P \cup \{ \varnothing \}$$

#### Train Deck
$$D_{\text{train}} \subseteq \mathcal\{\text{The set of all card colors}\} \cup \{\text{Locomotive train cards}\}$$

#### Destination Ticket Deck
$$D_{\text{dest}} = \text{remaining unobserved destination tickets}$$

#### Board
The board is the set of all edges with attributes:
$$B = \{ (e, w(e), c(e), p(e)) \mid e \in E \}$$

#### Player State

For each player $P_k$, they have the following components:

- $H_k$: the hand of train cards held by player $P_k$
- $T_k$: the set of destination tickets held by player $P_k$
- $R_k$: the number of remaining train pieces for player $P_k$
- $S_k$: the current score of player $P_k$

#### Face-Up Train Cards

Let $F_{\text{train}}$ represent the set of face up train cards that can be chosen from.

### Actions
Every turn, an agent has three decisions to make:


$\text{ACTIONS(turn)} = \{ \text{drawCard}, \text{placeTrain(e)}, \text{drawDestinationTicket} \}$

$\text{drawCard}$ will allow the player, $P_i$, to add two train cards to their hand. This action only affects $P_i$'s hand. Given an edge $e \in E$, $\text{placeTrain(e)}$ allows a player $P_i$ to place their trains on an edge and claim a route. This action affects $P_i$'s hand and the board's state. $\text{drawDestinationTicket}$ allows the player, $P_i$, to add an additional destination ticket to their hand. This action affects $P_i$'s hand only.

### State Transitions

The transition model is:

$$T(s' \mid s, a)$$

This model shows the probability of moving from state \(s\) to state \(s'\) after taking action \(a\). There are 3 real distinct actions a player can take on any hand: Draw a train card, Claim a route, or Draw a set of destination tickets.

#### 1. Draw Train Card

During a draw train card move, a player selects two train cards. If the first card selected is a wild, then a player does not draw a second card. In between selecting face-up cards, the train card is replaced by a card from the deck, making drawing the first card and the second card independent subactions. 
When selecting a card there are two cases:

* ##### (a) Drawing a card thats face up (Deterministic)

$$T(s' \mid s, \text{drawCard}) = 1$$

This is for the one successor state \(s'\) in which the selected face-up card is added to the player's hand and a new card from the deck replaces it in the face-up row. 

* ##### (b) Drawing from the deck (Stochastic)

When the player draws a card from the top of the deck, the result is random since we do not know what card we will recieve:

$$T(s' \mid s, \text{drawCard}) = \frac{1}{D_{\text{train}}}$$

This is for each distinct successor state \(s'\) by adding one of the remaining deck cards to the player's hand.

#### 2. Claim Route (Deterministic)

Claiming a track \(e\) will produce one state since the player is explicitly choosing their action and location:

$$T(s' \mid s, \text{placeTrain}(e)) = 1$$

Then the colored cards used are removed from the player's hand, $P_{i_T}$. The remaining train pieces are removed from the player's hand, $P_{i_{TR}}$, and the overall score is updated.

$e$ is then updated in $B$ with a new color, $c(e)$, representing the color the player chose to color the route.  The action includes ("placeTrain", edge, cards from hand). The player declares they are taking a train, the train they want to take, and the combination of trains in their hand that they want to use. Wild trains/edges can be made up of any color, so the possible transitions explode because all combinations of valid length are possible.

#### 3. Draw Destination Tickets (Stochastic)

When a player chooses to draw tickets, they randomly choose 3 distinct tickets from the destination deck. Since the draw is made without replacement and all at once, any possible combination of train cards is equally likely to one another. 

$$T(s' \mid s, \text{drawDestinationTicket}) = \frac{1}{\binom{|D_{\text{dest}}|}{3}}$$

After drawing the mandatory 3 cards, the player gets to choose which tickets to keep and which to discard. They must keep at least one and at most 3 of the available options.


### Observability

This is a partially observable state space, as a player, or the agent, cannot fully observe the entire state space. As mentioned above, a player only has access to their own destination tickets and train cars. An agent cannot observe other players' or agents' tickets and cars, which means no agent has access to the full state space. This means the state space is partially observable.

### Observations
The players do not observe the full state as some aspects are hidden from the player. They can view the following:
- The board
- Face up row of train cards
- Their hand of cards
- Their destination tickets
- Their remaining trains
- Cards previously taken from the face up trains cards by other players and when the the train deck is to be reshuffled.

They cannot however see:
- Other players train cards
- Other players tickets
- The hidden destination cards, and train cards

The observable state for a player $P_k$ is defined by:

$$o_i = \big( B,\ F_{\text{train}},\ H_k,\ T_k,\ R_k,\ P_k)$$



## Solution method

### Overview

Our solution method is a Monte Carlo Tree Search (MCTS) agent where each time it is the AI's turn, the agent:
1. Builds a search tree based off the current observation
2. Repeatedly simulates random futures from that root
3. Estimates the expected final score of each potential action to determine the best expected move
4. Selects the action that has the highest estimated value and executes it

This attempts to build an approximate solution to a partially observable stochastic problem. We approximate each action in the current state by using rollout simulations to determine the best probability move.

### Monte Carlo Tree Search Implementation
#### Tree Node Structure

Each node in the MCTS tree is represented by an MTNode object where each node stores:
1. The state
2. The action that led to it
3. Pointers to parent and children
4. Visit count
5. Total simulation value

#### Search Initialization

At the beginning of each AI turn, the algorithm gathers the current state and creates the search root which then performs 1,000 simulations where each simulation descends the tree, potentially expanding a new node, performing a rollout, and backpropagating the results. When the simulations finish the AI selects the child from the root that has the highest cumulative value or the best predicted value score.

#### Selection & Expansion

We explore a number of nodes and once the simulation reaches the depth limit it cuts off and stops the simulation down that path. If the number of children for the current node is smaller than the number of legal actions for that player, this node still has unexplored actions and the algorithm retrieves all legal actions, randomly selects one unexplored action, applies this action to create a new state, creates a new child node connected to the current node and performs a rollout from that new node to estimate the actions value. If all actions have already been expanded, the algorithm selects one of the existing children at random and continues the simulation downward.

#### Rollout

Each rollout simulates a random continuation of the game until the defined depth limit is reached. Each simulation has players take turns in sequence where the active player’s legal moves are retrieved, one legal action is sampled at random and applied to generate the next state. Finally, it returns a expected value of the resulting state that is computed by the reward function to demonstrate the success of that move.

#### Reward Function
The reward function returns the current score of the player at that current state. The score consists of how many trains they have placed on the board, bonus points for the longest train path on the board, bonus or deduction points for completed and incompleted tickets, and points for constructing longer paths.  
We implemented two seperate reward functions, one that focuses on progress and one that focuses on ticket completion. The ticket completion reward function gives the player's current score as a reward + 2*value of all completed tickets - value of all uncompleted tickets. We did this to incentivize completed destination tickets as if you do not have the path completed you lose the tickets value in the endgame scoring. For the second reward function we prioitized building progress on the train tickets. rewarding a fraction of the value of the ticket as you get closer to completing them. 

#### Backpropagation

After each simulation the visit count of each node along the path is incremented and the node’s value is increased by the reward returned from the simulation. As you run more simulations and accumulate increased visits and expected values we average the value per total number of visits to get the estimated reward cost to pass up the tree. The AI obviously chooses the path with the best average value and takes that move to continue the game.
