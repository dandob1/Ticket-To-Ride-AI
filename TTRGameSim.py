
#this version no longer takes input from user. 
#Designed for computer OR human player (mainly comp v comp sim)

#All values and methods associated with the Original Ticket to Ride board game
import TTRBoard
import TTRCards
import TTRPlayer
import collections
import pprint
import random
import TTRAI
from itertools import combinations
from collections import Counter
import networkx


import TTRPrint

class Game(object):
    def __init__(self, numPlayers, numAi, rewards):
        self.sizeDrawPile          = 5
        self.numTicketsDealt       = 3
        self.sizeStartingHand      = 4
        self.maxWilds              = 3

        self.endingTrainCount      = 3 # ending condition to trigger final round

        self.pointsForLongestRoute = 10
        self.startingNumOfTrains   = 14 #45
        self.deck                  = TTRCards.Cards(self.sizeDrawPile, self.maxWilds)
        
        self.board                 = TTRBoard.Board()
        self.numPlayers            = numPlayers
        self.numAi                 = numAi
        self.players               = []
        
        self.posToMove             = 0
        self.aiModel               = TTRAI.AI(self, self.board)

        self.endGame = False
        #card counting for observations
        #can do card couting on the face cards taken in other peoples hands
        # self.cardCounting = {p}

        #point values for tracks of different lengths
        self.routeValues           = {1:1, 2:2, 3:4, 4:7, 5:10, 6:15}

        self.rewardMap = {0:"tickets", 1:"route", 2: "random"}

        for position in range(numPlayers):
            startingHand     = self.deck.dealCards(self.sizeStartingHand)
            startingTickets  = [] #self.deck.dealTickets(self.numTicketsDealt)
                                  #this is now done in initialize method below
                                  #occurs before first player's first move
            playerBoard      = TTRBoard.PlayerBoard()
            
            player           = TTRPlayer.Player(startingHand, 
                                                startingTickets, 
                                                playerBoard, 
                                                position, 
                                                self.startingNumOfTrains,
                                                False
                                                )      
                                
            self.players.append(player)

        for position in range(numAi):
            startingHand     = self.deck.dealCards(self.sizeStartingHand)
            startingTickets  = [] #self.deck.dealTickets(self.numTicketsDealt)
                                  #this is now done in initialize method below
                                  #occurs before first player's first move
            playerBoard      = TTRBoard.PlayerBoard()

            player           = TTRPlayer.Player(startingHand, 
                                                startingTickets, 
                                                playerBoard, 
                                                position, 
                                                self.startingNumOfTrains,
                                                True,
                                                self.rewardMap[rewards[position]]
                                                )                          
            self.players.append(player)


        for player in self.players:
            if player.isAi():
                print(player.reward)
        # Precompute best paths for every ticket as heuristic
        self.ticket_paths = {}
        self.ticket_colors = {}


        for ticket in self.deck.tickets:
            city1, city2, value = ticket
            try:
                path_nodes = self.board.getShortestPath(city1, city2)
            except Exception:
                self.ticket_paths[ticket] = []
                self.ticket_colors[ticket] = {}
                continue
            self.ticket_paths[ticket] = path_nodes
            
            edges = list(zip(path_nodes, path_nodes[1:]))

            color_needs = collections.Counter()
            for u, v in edges:
                data = self.board.G.get_edge_data(u, v)
                if not data:
                    continue
                edge_colors = data.get("edgeColors", [])
                non_grey = [c for c in edge_colors if c != 'grey']
                if non_grey:
                    color_needs[non_grey[0]] += data.get("weight", 1)
            self.ticket_colors[ticket] = color_needs

    def getLegalActions(self, player):
        moves = []

        # 1. Claiming a Train Route
        for edge in self.board.getEdgesData():
            city1, city2 = edge["edge"]
            for color in edge["edgeColors"]:
                if self.doesPlayerHaveCardsForEdgeColCheck(player, city1, city2, color):
                    possibleCombinations = player.getCombinations(edge["weight"], color)

                    validCombinations = []
                    for combination in possibleCombinations:
                        base_color = None
                        valid = True
                        for color in combination:
                            if base_color == None and color != 'wild':
                                base_color = color
                            if base_color != color and color != 'wild':
                                valid = False
                        if valid:
                            validCombinations.append(combination)
                    
                    if len(validCombinations) > 0:
                        moves.append({
                            "move": "train",
                            "edge": edge,
                            "color": color,
                            "possible_cards": validCombinations
                        })

        # 2. Drawing Train Cards
        if self.deck.getDrawPile() or self.deck.cards:
            moves.append({
                "move": "cards",
            })

        # 3. Draw Route Tickets
        if self.deck.tickets:
            moves.append({
                "move": "tickets",
            })

        return moves


    #ADDITION
    def getPossibleTransitions(self, player):
        moves = []

        #game is over no possible moves to be made
        if self.checkEndingCondition(player):
            return
        
        #first move of a turn
        if not player.previousAction:
            moves.append({"move":"draw_tickets"},{"move":"pick_cards"}, {"move":"place_trains"}) 
            return moves
    
        # if the player previously selected draw_tickets then we return all subsets as possiblities
        # if there are pending tickets the only legal action is to select a subset
        if player.pendingTickets and player.previousAction["move"] == "draw_tickets":
            res = [list(combinations(player.pendingTickets, r)) for r in range(1, len(player.pendingTickets) + 1)]  
            res = [list(sublist) for g in res for sublist in g] 
            moves.append({
                "move": "select_tickets",
                "possible_tickets": res
            })
            return moves
        
        #second drawing
        if player.previousAction["move"] == "draw_card1":
            for card in self.deck.getDrawPile():
                if card != "wild":
                    moves.append({
                            "move":"drawcard2",
                            "card": card
                    })
            moves.append({
                    "move": "card",
                    "card": "drawPile",
            })
            return moves
        
        #pick up train cards
        if player.previousAction["move"] == "pick_cards":
            for card in self.deck.getDrawPile():
                moves.append({
                    "move": "draw_card1",
                    "card": card,
                })
            moves.append({
                    "move": "draw_card1",
                    "card": "drawPile",
            })
            return moves

        # A train move is appended as 
        # moves.append({
        #                 "move": type,
        #                 "edge": edge -> dictionary with edge: (city1,city2), weight: int, edgeColors: ["c1", "c2"]
        #                 "color": color, # including this because an ed
        #                 "possible_cards": possibleCombinations -> List of Counters {red:1, blue: 1, etc}
        #             }) 

        #generates all possible moves that can be played (currently a single move actually holds lots of move (different combos of cars))
        for edge in self.board.getEdgesData():
            city1, city2 = edge["edge"]
            for color in edge["edgeColors"]:
                if self.doesPlayerHaveCardsForEdgeColCheck(player, city1, city2, color):
                    possibleCombinations = player.getCombinations(edge["weight"], color)

                        #it can only be combined with a wild card, i.e green and purple cannot be combined
                    possibleCombinations = player.getCombinations(edge['weight'], color)

                        #check for multiple color violations
                    validCombinations = []
                    for combination in possibleCombinations:
                        base_color = None
                        valid = True
                        for color in combination:
                            if base_color == None and color != 'wild':
                                base_color = color
                            if base_color != color and color != 'wild':
                                valid = False
                        if valid:
                            validCombinations.append(combination)
                  

                        

                    if len(validCombinations) > 0:
                        moves.append({
                            "move": "train",
                            "edge": edge,
                            "color": color,
                            "possible_cards": validCombinations
                        })

        # 2. Drawing Train Cards
        if self.deck.getDrawPile() or self.deck.cards:
            moves.append({
                "move": "cards",
            })

        # 3. Draw Route Tickets
        if self.deck.tickets:
            moves.append({
                "move": "tickets",
            })

        return moves


    #ADDITION
    def getPossibleTransitions(self, player):
        moves = []

        #game is over no possible moves to be made
        if self.checkEndingCondition(player):
            return
        
        #first move of a turn
        if not player.previousAction:
            moves.append({"move":"draw_tickets"},{"move":"pick_cards"}, {"move":"place_trains"}) 
            return moves
    
        # if the player previously selected draw_tickets then we return all subsets as possiblities
        # if there are pending tickets the only legal action is to select a subset
        if player.pendingTickets and player.previousAction["move"] == "draw_tickets":
            res = [list(combinations(player.pendingTickets, r)) for r in range(1, len(player.pendingTickets) + 1)]  
            res = [list(sublist) for g in res for sublist in g] 
            moves.append({
                "move": "select_tickets",
                "possible_tickets": res
            })
            return moves
        
        #second drawing
        if player.previousAction["move"] == "draw_card1":
            for card in self.deck.getDrawPile():
                if card != "wild":
                    moves.append({
                            "move":"drawcard2",
                            "card": card
                    })
            moves.append({
                    "move": "card",
                    "card": "drawPile",
            })
            return moves
        
        #pick up train cards
        if player.previousAction["move"] == "pick_cards":
            for card in self.deck.getDrawPile():
                moves.append({
                    "move": "draw_card1",
                    "card": card,
                })
            moves.append({
                    "move": "draw_card1",
                    "card": "drawPile",
            })
            return moves

        # A train move is appended as 
        # moves.append({
        #                 "move": type,
        #                 "edge": edge -> dictionary with edge: (city1,city2), weight: int, edgeColors: ["c1", "c2"]
        #                 "color": color, # including this because an ed
        #                 "possible_cards": possibleCombinations -> List of Counters {red:1, blue: 1, etc}
        #             }) 

        #generates all possible moves that can be played (currently a single move actually holds lots of move (different combos of cars))
        
        if player.previousAction["move"] == "place_trains":
            for edge in self.board.getEdgesData():
                city1, city2 = edge["edge"]
                for color in edge["edgeColors"]:
                    if self.doesPlayerHaveCardsForEdgeColCheck(player, city1, city2, color):
                        # so the options are any amount of the color and greys
                        # if route is grey: any combination of 2 cards

                        #it can only be combined with a wild card, i.e green and purple cannot be combined
                        possibleCombinations = player.getCombinations(edge['weight'], color)

                        #check for multiple color violations
                        validCombinations = []
                        for combination in possibleCombinations:
                            base_color = None
                            valid = True
                            for color in combination:
                                if base_color == None and color != 'wild':
                                    base_color = color
                                if base_color != color and color != 'wild':
                                    valid = False
                            if valid:
                                validCombinations.append(combination)

                        if len(validCombinations) > 0:
                            moves.append({
                                "move": "train",
                                "edge": edge,
                                "color": color,
                                "possible_cards": validCombinations
                            })
            return moves
        return moves

            
    def getObservations(self, player):
        #get all edges on the board
        edges = list(self.board.iterEdges())

        #get the player's hand
        hand = player.getHand()

        #get the face up cards
        draw_pile = list(self.deck.getDrawPile())

        face_down = list(self.deck.cards)

        #get the player's destination tickets
        destination_tickets = player.tickets

        ticket_deck = list(self.deck.tickets)
        ticket_discard = list(self.deck.ticketDiscardPile)



        #get other player information
        player_info = {}
        for player in self.players:
            player_info[player.name] = {
                'score' : player.getPoints(), 
                'trains_left': player.getNumTrains()
            }
        
        return {
            'edges' : edges,
            'player' : player,
            'draw_pile' : draw_pile,
            'face_down' : face_down,
            'ticket_deck' : ticket_deck,
            'ticket_discard' : ticket_discard,
            'public_player_info' : player_info,
        }

    def getReward(self, player):
        if player.reward == "random":
            return self.getFinalScore(player)

        score = player.getPoints() 
        if player == self.viewLongestPath():
            score += self.pointsForLongestRoute

        if player.reward == "tickets":
            ticket_bonus = 0.0
            for ticket, completed in player.tickets.items():
                city1, city2, val = ticket

                path_nodes = self.ticket_paths.get(ticket)
                if not path_nodes:
                    continue

                edges = list(zip(path_nodes, path_nodes[1:]))
                claimed = 0
                for (c1, c2) in edges:
                    if (player.playerBoard.hasEdge(c1, c2)) or player.playerBoard.hasEdge(c2, c1):
                        claimed += 1

                frac = claimed / len(edges)

                if completed:
                    ticket_bonus += val * 2
                else:
                    ticket_bonus += val * frac
            train_penalty = 0.1 * player.getNumTrains()
            score += (ticket_bonus - train_penalty)
        elif player.reward == "route":
            longest = 0
            for city in player.playerBoard.getCities():
                length, _ = player.playerBoard.longestPath(city)
                if length > longest:
                    longest = length
            longest_bonus = longest * 1.5
            ticket_val = self.viewPlayerTicketsScore(player) * 0.3
            trains_used = self.startingNumOfTrains - player.getNumTrains()
            use_bonus = trains_used * 0.5
            score += (longest_bonus + ticket_val + use_bonus)

        return score
    
    def getFinalScore(self, player):
        curr = player.getPoints() + self.viewPlayerTicketsScore(player)
        if player == self.viewLongestPath():
            curr += self.pointsForLongestRoute
        return curr

    def printSepLine(self, toPrint):
        print(toPrint)
            
    def advanceOnePlayer(self):
        """Updates self.posToMove"""
        self.posToMove += 1
        self.posToMove %= self.numPlayers + self.numAi
    
    def getCurrentPlayer(self):
        return self.players[self.posToMove]
    
    def doesPlayerHaveCardsForEdge(self, player, city1, city2):
        if player.playerBoard.hasEdge(city1, city2):
            return False
        routeDist = self.board.getEdgeWeight(city1, city2)
        routeColors = self.board.getEdgeColors(city1, city2)
        for col in routeColors:
            if col == 'grey':
                if max([x for x in player.hand.values() if x != 'wild']) \
                + player.hand['wild'] >= routeDist:
                    return True
            else:
                routeDist = self.board.getEdgeWeight(city1, city2)
                if player.hand[col] + player.hand['wild'] >= routeDist:
                    return True
        return False    

    # checks if a player can use an edge and return the color or None
    def doesPlayerHaveCardsForEdgeColCheck(self, player, city1, city2, color ):
        if player.playerBoard.hasEdge(city1, city2):
            return False
        routeDist = self.board.getEdgeWeight(city1, city2)
        if color == 'grey':
            if max([x for x in player.hand.values() if x != 'wild']) \
            + player.hand['wild'] >= routeDist:
                return True
        else:
            routeDist = self.board.getEdgeWeight(city1, city2)
            if player.hand[color] + player.hand['wild'] >= routeDist:
                return True
        return False  
    
    def checkEndingCondition(self, player):
        return player.getNumTrains() < self.endingTrainCount
    
    def initialize(self):
        """Before game turns starts, enter names and pick destination tickets
        """

        for player in self.players:
                
            #pick desination tickets
            player.previousAction = {
                "move": "draw_tickets"
            }
            
            self.pickTickets(player, 2)
            player.endTurn()
            self.advanceOnePlayer()

    def scorePlayerTickets(self, player):
        """returns None.  
        Scores player's destination tickets and 
        adds/subtracts from player's points
        """
        for ticket in player.tickets:
            city1 = ticket[0]
            city2 = ticket[1]
            value = ticket[2]
            posNodes = player.playerBoard.getNodes()
            if city1 not in posNodes or city2 not in posNodes:
                player.subtractPoints(value)
                continue
            if player.playerBoard.hasPath(city1, city2):
                player.addPoints(value)

    def viewPlayerTicketsScore(self, player):
        """returns None.  
        Scores player's destination tickets and 
        adds/subtracts from player's points
        But does not set the values
        """
        total = 0
        for ticket in player.tickets:
            if ticket is None:
                continue
            city1 = ticket[0]
            city2 = ticket[1]
            value = ticket[2]
            posNodes = player.playerBoard.getNodes()
            if city1 not in posNodes or city2 not in posNodes:
                total -= value
                continue
            if player.playerBoard.hasPath(city1, city2):
                total += value
        return total
                
    def scoreLongestPath(self):
        """determines which player has the longest route and 
        adjusts their score accordingly
        players: list of players
        adds self.pointsForLongestRoute to player with longest route
        """

        scores = { x:(0, ()) for x in self.players }
        longestPath = 0
        for player in scores:

            for city in player.playerBoard.getCities():
                pathInfo = player.playerBoard.longestPath(city)
                if pathInfo[0] > scores[player][0]:
                    scores[player] = pathInfo
        
            if scores[player][0] > longestPath:
                longestPath = scores[player][0]
        
        print(scores)
        
        for player in scores:
            if scores[player][0] == longestPath:
                player.addPoints(self.pointsForLongestRoute)
        
        #does not return anthing
    

    def viewLongestPath(self):
        """determines which player has the longest route and 
        adjusts their score accordingly
        players: list of players
        returns the current player with the longest path, the score bonus is found
        in the game object
        """

        scores = { x:(0, ()) for x in self.players }
        longestPath = 0
        for player in scores:

            for city in player.playerBoard.getCities():
                pathInfo = player.playerBoard.longestPath(city)
                if pathInfo[0] > scores[player][0]:
                    scores[player] = pathInfo
        
            if scores[player][0] > longestPath:
                longestPath = scores[player][0]
        
        for player in scores:
            if scores[player][0] == longestPath:
                return player



    def printAllPlayerData(self):
        """prints out all of the non method attributes values for all players
        """
        for player in self.players:
            print (f"{player.name}'s Data: ")
            print ("------------------------------")
            print(f"{player.name}'s Hand: ")
            TTRPrint.formatHandPrint(player.getHand())
            print(f"{player.name}'s Destination Tickets: ")
            TTRPrint.formatTicketHandPrint(player.getTickets())
            print(f"{player.name}'s Claimed Routes:")
            for city1, city2, data in player.playerBoard.iterEdges():
                length = data.get("weight", "?")
                colors = data.get("edgeColors", [])
                if colors:
                    colors_str = "/".join(colors)
                    print(f"  {city1} -- {city2}  (Length: {length}, Color(s): {colors_str})")
                else:
                    print(f"  {city1} -- {city2}  (Length: {length})")
            print(f"{player.name}'s Postgame Data: ")
            other_info = [[player.__dict__['numTrains'], player.__dict__['points']]]
            TTRPrint.formatPrintOtherPostGameData(other_info)
                    
            print("==============================")

    def playTurn(self, player):
        """player chooses 'cards', 'trains', 'tickets'
        player: player object
        """
        if player.isAi():
            action = self.aiModel.monteCarlo(player, 10)
            if action is not None:
                self.aiModel.apply_action(player, action)
            else:
                print("AI found no legal action.")
            return "Move complete"
        #print ("------------------------------")
        #print("DEBUG: PRINTING LEGAL TRAIN ACTIONS")
        #print(len(self.getLegalActions(player)))
        #print ("------------------------------")
        #print(self.getReward(player))
        if player.isAi() == False:
            choice = input("Please type: cards, trains or tickets: ")
        else:
            choices = ['cards', 'trains', 'tickets']
            choice = random.choices(choices, k=1)[0]
            print(f"AI move: {choice}")
        count = 0 # a way out of the loop if 5 invalid responses
        while choice not in ['cards', 'trains', 'tickets'] and count < 5:
            choice = input("Invalid repsonse. Please select either cards, "
                               + "trains or tickets: ")
            count += 1
        if player.isAi() == False:
            displayMap = input("Display map? y/n: ")
        else:
            displayMap = 'n'
        if displayMap == 'y':
            pauseTime = input("For how many seconds? (between 1 and 30): ")
            if int(pauseTime) not in range(1, 31):
                pass
            else:
                self.board.showBoard(self.board.G, int(pauseTime))
                #Depricated? I don't think so

        if count >= 5:
            return "Move complete"
        

        if choice == 'cards':
            player.previousAction = {
                "move": "draw_cards"
            }
            self.pickCards(player)

        elif choice == 'trains':
            player.previousAction = {
                "move": "place_trains"
            }
            self.placeTrains(player)

        else:
            player.previousAction = {
                "move": "select_ticket"
            }
            self.pickTickets(player)
        

        player.endTurn()
        return "Move complete"
        
    
    def pickCards(self, player):
        count = 0 # a way out of the loop if 5 invalid responses
        print("Your hand consists of: ")
        TTRPrint.formatPrintHand(player.getHand())

        print("Draw pile consists of: ")
        TTRPrint.formatPrintDeck(self.deck.getDrawPile())

        choice1 = ''

        # print ("------------------------------")
        # print("DEBUG: PRINTING LEGAL ACTIONS")
        # print(self.getPossibleTransitions(player))
        # print ("------------------------------")

        #if player is not AI
        if player.isAi() == False:
            choice1 = input("Please type a card from the above list or "
                                + "type 'drawPile': ")
            while choice1 not in self.deck.getDrawPile() + ['drawPile'] \
                   and count < 5:

                choice1 = input("Invalid repsonse. Please type either from " 
                                    + str(self.deck.getDrawPile()) 
                                    + " or type 'drawPile' "
                                    )
                count += 1
        
        #otherwise it's AI
        else:
            choices = self.deck.getDrawPile().copy()
            choices.append('drawPile')
            choice1 = random.choices(choices, k=1)[0]
            if choice1 == 'drawPile':
                print("AI drew from drawPile")
            else:
                print(f"AI selected {choice1} from face up cards")

        #add card to player's hand
        #remove it from drawPile or cards and 
        #add new card to drawPile
        if count >= 5:
            pass
        elif choice1 == 'drawPile':
            chosenCard = self.deck.pickFaceDown()
            print(f"{str(chosenCard)} was selected from the pile")
            player.addCardToHand(chosenCard)
        else:
            player.addCardToHand(self.deck.pickFaceUpCard(choice1))
        
        #start second card selection
        if choice1 == 'wild':
            print("Hand now consists of: ")
            TTRPrint.formatPrintHand(player.getHand())
            return "Move complete"

        #update the player status
        player.previousAction = {
            "move": "drawcard1",
            "card": choice1
        }

        count = 0
        
        TTRPrint.formatPrintDeck(self.deck.getDrawPile())
        choice2 = ''
        if player.isAi() == False:
            choice2 = input("Please type another card from the above list or type 'drawPile': ")
            while (choice2 == 'wild' or
                   (choice2 not in self.deck.getDrawPile() + ['drawPile'] and
                   count < 5)):

                choice2 = input(f"Invalid repsonse. Please type either from {self.deck.getDrawPile()} or type 'drawPile' NOTE: second choice cannot be 'wild' ")
                count += 1
        else:
            choice = self.deck.getDrawPile()
            choices.append('drawPile')
            while 'wild' in choice:
                choice.remove('wild')

            choice2 = random.choices(choice, k=1)[0]
            if choice2 == 'drawPile':
                print("AI selected: drawPile")
            else:
                print(f"AI selected: {choice2}")
            
        #add card to player's hand
        #remove it from drawPile or cards and 
        #add new card to drawPile
        if count >= 5:
            return "Move complete"
        elif choice2 == 'drawPile':
            chosenCard = self.deck.pickFaceDown()
            print(f"{str(chosenCard)} chosen from the pile")
            player.addCardToHand(chosenCard)
        else:
            player.addCardToHand(self.deck.pickFaceUpCard(choice2))
        
        print("Hand now consists of: ")
        TTRPrint.formatPrintHand(player.getHand())
        
        return "Move complete"
    
    def placeTrains(self, player):
        
        count = 0
        print("Available cities:")
        TTRPrint.printLine()
        #only print routes that are legal given the players cards
        #sort alphabetically


        # print ("------------------------------")
        # print("DEBUG: PRINTING LEGAL ACTIONS")
        # print(self.getPossibleTransitions(player))
        # print ("------------------------------")
        
        playable_routes = [x for x in self.board.iterEdges() if self.doesPlayerHaveCardsForEdge(player, x[0], x[1])]
        TTRPrint.formatTrainPrint([x for x in sorted(self.board.iterEdges()) 
                        if self.doesPlayerHaveCardsForEdge(player, x[0], x[1])])
        TTRPrint.printLine()
        print("Your hand consists of: ")
        TTRPrint.printLine()
        TTRPrint.formatHandPrint(player.getHand())
        TTRPrint.printLine()
        city1 = ''
        if player.isAi() == False:
            city1 = input("Please type the start city of desired route: ")
            while city1 not in self.board.getCities() and count < 5:
                city1 = input("Invalid response.Please select from the above city list:")
                count += 1
        else:
            playable_choices = []
            for route in playable_routes:
                playable_choices.append(route[0])
            city1 = random.choices(playable_choices, k=1)[0]
            print(city1)
            print(f"AI selected start city: {city1}")

        if count >= 5:
            return "Move complete"
            
        if len([x for x in self.board.G.neighbors(city1) 
                if self.board.hasEdge(city1, x)]) == 0:
            print("Selected a city with no legal destination")
            return "Move complete"
        
        #start city2
        count = 0
        city2 = ''
        if player.isAi() == False:
            destination_cities = [x for x in self.board.G.neighbors(city1) if self.board.hasEdge(city1, x)]
            print_cities = " | ".join(map(str, destination_cities))
            print("Available destination cities:\n" + print_cities)
            city2 = input(f"Please type the destination city to go to from {city1} : ")
            
        else:
            choices = [x for x in self.board.G.neighbors(city1) 
              if self.doesPlayerHaveCardsForEdge(player, city1, x)]
            if len(choices) == 0:
                print(f"No legal destination from {city1}")
                return "Move complete"
            city2 = random.choices(choices, k=1)[0]
            print(f"AI selected destination city: {city2}")

    
        while not self.board.hasEdge(city1, city2) and count < 5:
            destination_cities = [x for x in self.board.G.neighbors(city1) if self.board.hasEdge(city1, x)]
            city2 = input(f"Invalid response. Please type one of the following cities (without quotes): \n {destination_cities}") 
            count += 1    
            
        if count >=5:
            return "Move complete"
    
        #start exchange cards and place trains
        routeDist = self.board.getEdgeWeight(city1, city2)
        spanColors = self.board.getEdgeColors(city1, city2)
        
        if len(spanColors) == 0:
            #a little harsh but will updated later to players start over
            print("Selected two cities with no legal route")
            return "Move complete"
        
        
        print (f"This route is of length: {routeDist} ")
        if player.isAi() == False:
            print ("Hand consists of: ")
            TTRPrint.formatPrintHand(player.getHand())
        
        if len(spanColors) == 1:
            color = spanColors[0] #use first element, getEdgeColors returns list
            print ("This route is: " + str(color))
        else:
            color = ''
            if player.isAi() == False:
                print("Track colors: " + " | ".join(spanColors))
                color = input(f"which color track would you like to claim?: ")
                if color not in spanColors:
                    print ("Invalid Color")
                    return "Move complete"
            else:
               
                color = random.choices(spanColors, k=1)[0]
                print(f"AI selected track color: {color}")
                
        #check to see if player has appropriate cards to play route 
        # (edge weight, color/wild)
        if not self.doesPlayerHaveCardsForEdge(player, city1, city2):
            print ("You do not have sufficient cards to play this route")
            return "Move complete"
        if color == 'grey':
            availColor = max(x for x in player.hand.values())
        else:
            availColor = player.hand[color]

        availWild = player.hand['wild']
        if color == 'grey':
            if player.isAi() == False:
                color = input("Which color would you like to play on this grey route? Pick a color, not 'wild'): ")
                if color not in self.deck.possibleColors:
                    print ("Invalid Color")
                    return "Move complete"
                availColor = player.hand[color]
                numColor = input(f"How many {color} cards would you like to play? ({availColor}) available ")
                                 
            else:
                possible_colors = player.getHand()

                #filter only playable ones
                playable = []
                for color, count in possible_colors.items():
                    if availWild + count >= routeDist and color != 'wild':
                        playable.append(color)
                color = random.choices(playable, k=1)[0]
                availColor = player.hand[color]
                min_num_needed = max(0, routeDist - availWild)
                numColor = random.randrange(min_num_needed,availColor + 1)
                print(f"AI selected color {numColor} {color} cards")
        else:
            if player.isAi() == False:
                numColor = input(f"How many {color} cards would you like to play? ({availColor}) available: ")
            else:
                numColor = random.randrange(1,availColor + 1)
        if str(numColor) not in [str(x) for x in range(routeDist + 1)]:
            print ("Invalid Entry")
            return "Move complete"
        numColor = int(numColor) # change raw string to int
        if numColor not in range(0, availColor +1):
            print ("You do not have that many")
            return "Move complete"

        if numColor < routeDist: #span distance
            if player.isAi() == False:
                numWild = input(f"How many wild cards would you like to play? {availWild} available)")
            else:
                wild_needed = routeDist - numColor
                numWild = random.randrange(wild_needed,availWild + 1)
                print(f"AI selected {numWild} wild color cards")
            numWild = int(numWild)
            if numWild not in range(0, availWild +1):
                print ("You do not have that many")
                return "Move complete"
        else:
            numWild = 0

        #verify that this is a legal move
        if numWild + numColor != routeDist:
            print ("Selected cards do not properly span that route")
            return "Move complete"
        
        #claim route for player (see dedicated method within Game class)
        player.playerBoard.addEdge(city1, city2, routeDist, color)
        
        #remove route from main board
        self.board.removeEdge(city1, city2, color)
        
        #calculate points
        player.addPoints(self.routeValues[routeDist])
    
        #remove cards from player's hand
        player.removeCardsFromHand(color, numColor)
        player.removeCardsFromHand('wild', numWild)
        
        #add cards to discard pile
        self.deck.addToDiscard([color for x in range(numColor)] 
                              + ['wild' for x in range(numWild)]
                              )
        
        #remove trains from players numTrains
        player.playNumTrains(routeDist)
        
        print("Number of trains left to play: ")
        self.printSepLine(player.getNumTrains())  
                    
        return "Move complete"
    
    def pickTickets(self, player, minNumToSelect = 1):


        if(minNumToSelect == 2 and player.isAi() == True):
            print("AI is selecting starting destination tickets")

        count = 0
        tickets = self.deck.dealTickets(self.numTicketsDealt)
        player.pendingTickets = tickets

        # print ("------------------------------")
        # print("DEBUG: PRINTING LEGAL ACTIONS")
        # print(self.getPossibleTransitions(player))
        # print ("------------------------------")

        #assign a number to each ticket to make it easier to choose
        tickets = {x[0]:x[1] for x in zip(range(len(tickets)), tickets)}
        if player.isAi() == False:
            print("Please select at least " + str(minNumToSelect) + ": ")
        TTRPrint.formatTicketPrint(tickets)
        
        choices = set()
        if player.isAi() == False:
            choice = input("Select the ID to the above tickets type 'done' when finished: ")
            while (choice != 'done' and count < 7) or len(choices) < minNumToSelect:
                try:
                    choices.add(tickets[int(choice)])
                    choice = input("Select the number corresponding to the above tickets, type 'done' when finished: ")
                except:
                    choice = input(f"Invalid Choice: Select the number corresponding to the above tickets, type 'done' when finished: "
                                        + f"must select at least {str(minNumToSelect)}")
                    count += 1
        else:
            num_choices = random.sample(range(0, len(tickets)), minNumToSelect)
            for index in num_choices:
                choice = tickets[int(index)]
                choices.add(choice)

        for ticket in choices:
            player.addTicket(ticket)
        
        
        #add tickets that weren't chosen to the ticketDiscardPile
        notChosen = set(range(len(tickets))).difference(choices)
        for i in notChosen:
            self.deck.addToTicketDiscard(tickets[i])
        
        print("Tickets selected: ")
        for ticket in player.getTickets():
            print(f"{ticket[0]} to {ticket[1]} | Length: {ticket[2]}")
            print()
        

        self.pendingTickets = []

        return "Move complete"
    

def playTTR():

    #before first turn, select 1, 2 or 3 destination tickets
    
    print("\n Welcome to Ticket to Ride! \n")
    
    numPlayers = input("How many players will be playing today? "
                            + "1,2,3,4,5 or 6? ")

    count = 0
    while int(numPlayers) not in range(1,7) and count < 5:
        if numPlayers == 'exit': return "Thanks for playing!"
        numPlayers = input("Please enter either 1,2,3,4,5 or 6: ")
        count += 1
    if count >= 5:
        print("Default player count has been set to 2 ")
        numPlayers = 2
    
    aiCount = input("How many players are AI?")
    # Changes to +1 to have just AI play
    while int(aiCount) not in range(0,int(numPlayers)+1)  and count < 5:
        if aiCount == 'exit': return "Thanks for playing!"
        numPlayers = input(f"Please enter a number between 0 and {numPlayers}: ")
        count += 1
    
    aiCount = int(aiCount)
    reward_type = []

    # Ask incentive for each AI
    for i in range(aiCount):
        while True:
            choice = input(f"Select reward function for AI {i} (0: tickets, 1: route, 2: random): ")
            if choice in ['0', '1', '2']:
                reward_type.append(int(choice))
                break
            else:
                print("Invalid input. Please enter 0, 1, or 2.")
    game = Game(int(numPlayers) - int(aiCount), int(aiCount), reward_type)    
    
    game.initialize()
    
    
    
    player = game.players[0]

    #main game loop
    while True:
        print(f"\n________________{player.name}'S TURN_________________ \n")

        game.playTurn(player)
        
        #condition to break out of loop
        if game.checkEndingCondition(player):
            game.advanceOnePlayer()
            player = game.getCurrentPlayer()
            break
    
        game.advanceOnePlayer()
        player = game.getCurrentPlayer()
    
    print("\n This is the last round!  Everyone has one more turn! \n")
    
    for i in range(len(game.players)):
        game.endGame = True
        print ("\n_________________NEW PLAYER'S TURN_________________ \n")
        print ("This is your LAST TURN " + str(player.getName()) + "! ")
        game.playTurn(player)
        game.advanceOnePlayer()
        player = game.getCurrentPlayer()
    
    
    for player in game.players:
        game.scorePlayerTickets(player)
    
    game.scoreLongestPath()
    

    scores = []
    for player in game.players:
        print (str(player.getName()) 
               + " had " 
               + str(player.getPoints()) 
               + " points!"
               )
        score = player.getPoints()
        scores.append(score)
        
    
    winners = [x.getName() for x in game.players 
              if x.getPoints() == max(scores)]

    if len(winners) == 1:
        print ("The winner is " + str(winners[0]))
    else:
        print ("The winners are " + ' and '.join(winners))
    
    
    print ("\n =========== Data =========== \n")
    
    game.printAllPlayerData()
    
    print ("\n =========== fin =========== \n")

if __name__ == "__main__":

    playTTR()

