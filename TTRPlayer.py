import collections
from itertools import combinations
from collections import Counter
from TTRAI import AI
import copy

class Player(object):
    
    def __init__(self, 
                 startingHand, 
                 startingTickets, 
                 playerBoard, 
                 playerPosition, 
                 numTrains,
                 ai,
                 reward=None
                 ):
        """orderNumber: int
        startingHand: list
        startingTickets: list
        playerBoard: PlayerBoard object from the TTRBoard module
        playerPosition: int
        """
        name = ""
        if not ai:
            name = input("Enter player name: ")
        else:
            import random
            name = f"AI_Player_{random.randint(1000,9999)}"
        self.name           = name #ask for them to enter it on first turn
        
        #implimented as a collection to avoid O(n) hand.remove(x)
        self.hand           = collections.Counter(startingHand)
        
        self.tickets        = {x:False for x in startingTickets}
        self.numTrains      = numTrains
        self.points         = 0
        self.playerPosition = playerPosition
        self.reward = reward


        self.pendingTickets = []
        # a previousAction is only here for multi-action moves
        # after ever move the action is cleared, so if a player picks a wild, turn end and is cleared
        self.previousAction = {}

        #custom board to represent
        self.playerBoard    = playerBoard
        self.ai             = ai

                    
    def removeCardsFromHand(self, color, numColor):
        """removes one ore more cards from hand
        assumes all cards are in hand, error if not
        cards: list
        """
        if self.hand[color] >= numColor:
            self.hand[color] -= numColor
        else:
            self.hand[color] = 0
        
    #add card to hand
    def addCardToHand(self, card):
        """adds a single card to hand
        assumes card is a valid choice
        card: String
        """
        if card != None:
            self.hand[card] += 1
    
    #add ticket to hand
    def addTicket(self, ticket):
        """adds a single ticket to tickets
        ticket: tuple(city1, city2, value)
        """
        self.tickets[ticket] = False
    
    def completeTicket(self, ticket):
        """updates the value in the tickets dict to True for key: ticket
        ticket: tuple(city1, city2, value)
        """
        if ticket in self.tickets:
            self.tickets = True
    
    def getHand(self):
        return self.hand
    
    def addPoints(self, numPoints):
        self.points += numPoints
    
    def subtractPoints(self, numPoints):
        self.points -= numPoints
        
    def getPoints(self):
        return self.points
        
    def getTickets(self):
        return self.tickets
    
    def getNumTrains(self):
        return self.numTrains
    
    def playNumTrains(self, numTrains):
        if(numTrains <= self.numTrains):
            self.numTrains -= numTrains
        else:
            self.numTrains = 0
        
    def setPlayerName(self, name):
        """sets playerName to name
        name: string
        """
        self.name = name
    
    def getName(self):
        return self.name
    
    def isAi(self):
        return self.ai
        

    def endTurn(self):
        self.previousAction = {}
        self.pendingTickets = []
        return

    # Get colors
    def getCombinations(self, weight, color):
        possibleCombinations = []
        wilds = self.hand.get("wild") 

        if weight is None:
            return
        # print(wilds)
        if color == 'grey':
            #can use any combination of all 9 colors (8 colors + wild)
            elements = list(self.hand.elements())
            for combo in combinations(elements, weight):
                combo_dict = dict(Counter(combo))
                possibleCombinations.append(combo_dict)
        else:
            colorCount = self.hand.get(color)
            
            if colorCount == None:
                colorCount = 0
            if colorCount >= weight:
                possibleCombinations.append({color:weight})


            for x in range(min(colorCount, weight) + 1):
                if wilds is not None:
                    for y in range(min(wilds, weight - x) + 1):
                        possibleCombinations.append({color:x, "wild":y})
                
        return possibleCombinations

    def clone_for_sim(self):
        # To reduce processing overhead for AI simulations

        hand_copy = copy.deepcopy(self.getHand())
        tickets_copy = copy.deepcopy(self.getTickets())
        board_ref = copy.deepcopy(self.playerBoard)
        position = copy.deepcopy(self.playerPosition)
        num_trains = copy.deepcopy(self.getNumTrains())
        ai_flag = copy.deepcopy(self.isAi())
        reward = copy.deepcopy(self.reward)

        return Player (
            hand_copy,
            tickets_copy,
            board_ref,
            position,
            num_trains,
            ai_flag,
            reward
        )