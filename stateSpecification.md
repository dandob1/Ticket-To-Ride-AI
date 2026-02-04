# State Specification

## Natural Language Description
  In Ticket to Ride, a game state captures information about every player’s cards and trains, and the board itself. The board has vertices and edges, represented as city destinations and train routes, respectively. Every train route has two destinations it connects, the color and player association of the route, and the length of the route. The state also contains information about each player’s possessions. At any time in the game, a player can have trains of varying colors to place on the board and different destination tickets. 
	The state space of Ticket to Ride is the set of all possible states. In other words, it is the set of all possible information combinations about the board and player-specific information. With over 140 cards and 30 destination vertices, it is evident that this state space cannot be searched using a simple breadth-first search or A* search. We can also express the state space in mathematical notation.

## Mathematical Description
As mentioned above, the state space of Ticket to Ride consists of the board state, the cards in players' hands, and the current face-up train cards.

### Players
$P = \{ P_1, P_2, \ldots, P_k \}$

Each player has a set of trains and destination tickets in their hand:
$P_{i_{trains}} = \{Tr_1, Tr_2, \ldots, Tr_k\}$
$P_{i_{tickets}} = \{T_1, T_2, \ldots, T_k\}$

### Colors
$c = \{ \text{Purple}, \text{White}, \text{Blue}, \text{Yellow}, \text{Orange}, \text{Black}, \text{Red}, \text{Green} \}$

### Vertices (Cities)
$C = \{ C_{ny}, C_{la}, C_{ph}, \ldots, C_{j} \}$


### Edges (Train Routes)
Edges are unordered pairs of distinct cities:
$E = \{ (C_i, C_j) \mid C_i, C_j \in C,\ i \neq j \}$

Each edge $e \in E$ is defined by the functions:

- Weight (number of trains required):
  $$w : E \to \mathbb{N}$$

- Color of the route:
  $$c : E \to c$$

- Player assignment (or unclaimed):
  $$p : E \to P \cup \{ \varnothing \}$$

### Train Deck
$$D_{\text{train}} \subseteq \mathcal\{\text{The set of all card colors}\} \cup \{\text{Locomotive train cards}\}$$

### Destination Ticket Deck
$$D_{\text{dest}} = \text{remaining unobserved destination tickets}$$

### Board
The board is the set of all edges with attributes:
$$B = \{ (e, w(e), c(e), p(e)) \mid e \in E \}$$

### Player State

For each player $P_k$, they have the following components:

- $H_k$: the hand of train cards held by player $P_k$
- $T_k$: the set of destination tickets held by player $P_k$
- $R_k$: the number of remaining train pieces for player $P_k$
- $S_k$: the current score of player $P_k$

### Face-Up Train Cards

Let $F_{\text{train}}$ represent the set of face up train cards that can be chosen from.

## Actions
Every turn, an agent has three decisions to make:


$\text{ACTIONS(turn)} = \{ \text{drawCard}, \text{placeTrain(e)}, \text{drawDestinationTicket} \}$

$\text{drawCard}$ will allow the player, $P_i$, to add two train cards to their hand. This action only affects $P_i$'s hand. Given an edge $e \in E$, $\text{placeTrain(e)}$ allows a player $P_i$ to place their trains on an edge and claim a route. This action affects $P_i$'s hand and the board's state. $\text{drawDestinationTicket}$ allows the player, $P_i$, to add an additional destination ticket to their hand. This action affects $P_i$'s hand only.

## State Transitions

The transition model is:

$$T(s' \mid s, a)$$

This model shows the probability of moving from state \(s\) to state \(s'\) after taking action \(a\). There are 3 real distinct actions a player can take on any hand: Draw a train card, Claim a route, or Draw a set of destination tickets.

### 1. Draw Train Card

There are two cases:

* #### (a) Drawing a card thats face up (Deterministic)

$$T(s' \mid s, \text{drawCard}) = 1$$

This is for the one successor state \(s'\) in which the selected face up card is added to the player's hand and a new card from the deck replaces it in the face up row.

* #### (b) Drawing from the deck (Stochastic)

When the player draws a card from the top of the deck, the result is random since we do not know what card we will recieve:

$$T(s' \mid s, \text{drawCard}) = \frac{1}{D_{\text{train}}}$$

This is for each distinct successor state \(s'\) by adding one of the remaining deck cards to the player's hand.

### 2. Claim Route (Deterministic)

Claiming a track \(e\) will produce one state since the player is explicitly choosing their action and location:

$$T(s' \mid s, \text{placeTrain}(e)) = 1$$

Then the colored cards used are removed from the players hand, $P_{i_T}$. The remaining train pieces are removed from the players hand, $P_{i_{TR}}$, and the overall score is updated.

$e$ is then updated in $B$ with a new color, $c(e)$, representing the color the player chose to color the route.  


### 3. Draw Destination Tickets (Stochastic)

When a player chooses to draw tickets they randomly choose 3 distinct tickets from the destination deck. Since the draw is made without replacement and all at once any possible combination of train cards is equally likely to one another. 

$$T(s' \mid s, \text{drawDestinationTicket}) = \frac{1}{\binom{|D_{\text{dest}}|}{3}}$$

After drawing the mandatory 3 cards the player gets to choose which tickets to keep and which to discard. They must keep at least one and at most 3 of the available options.



## Observability

This is a partially observable state space, as a player, or the agent, cannot fully observe the entire state space. As mentioned above, a player only has access to their own destination tickets and train cars. An agent cannot observe other players' or agents' tickets and cars, which means no agent has access to the full state space. This means the state space is partially observable.

## Observations
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


