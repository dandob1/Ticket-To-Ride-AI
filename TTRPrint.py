from tabulate import tabulate
def formatTrainPrint(toPrint):
        display = []
        for item in toPrint:
            colors = ""
            if len(item[2]['edgeColors']) > 1:
                colors = f"{item[2]['edgeColors'][0]} and {item[2]['edgeColors'][1]}"
            else:
                colors = item[2]['edgeColors'][0]
            info = [item[0], item[1], item[2]['weight'], colors]
            display.append(info)
        print(tabulate(display, headers=['From', 'To', 'Length', 'Color(s)']))
        

def formatHandPrint(toPrint):
    info = []
    for color, count in toPrint.items():
        info.append([color, count])
    print(tabulate(info, headers=['Color', 'Count']))

def formatTicketPrint(toPrint):
    i = 0
    for ticket in toPrint:
        print(f"ID: {i} | {toPrint[ticket][0]} to {toPrint[ticket][1]} | Length: {toPrint[ticket][2]}")
        print("")
        i += 1

def formatTicketHandPrint(toPrint):
    display = []
    for ticket in toPrint:
        display.append([ticket[0], ticket[1], ticket[2], toPrint[ticket]])
    print(tabulate(display, headers=['From', 'To', 'Length', 'Completed']))

def printLine():
    print("--------------------")

def formatPrintHand(hand):
    card_table = []
    for color in hand:
        card_table.append([color, hand[color]])
    print(tabulate(card_table, headers=['Color', 'Count']))
    print()

def formatPrintDeck(deck):
    print(" | ".join(map(str, deck)))
    print()

def formatPrintOtherPostGameData(info):
    print(tabulate(info, headers=['Number of Trains Left', 'Points']))



