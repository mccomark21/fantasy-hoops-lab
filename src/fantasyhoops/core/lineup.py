"""The daily lineup: which players fill the starting slots on one day.

The slots are the position slots (config.toml [league] slots) + one Util slot. A player fills at most one slot that
his positions allow. Util takes any player. A player without a slot sits on the bench.
"""


def best_lineup(players, slots):
    """Indexes of the players who start, in the order of players.

    players: the positions of each player who plays that day (a set or a list, such as {"PG", "SG"}), best first.
    slots: the position slots, for example cfg["league"]["slots"].
    Adding players in the order of players gives the best lineup: legal lineups are a matroid. So the lineup has the
    most starters, and a better player never sits for a worse one.
    """
    lineup = []
    for i, pos in enumerate(players):
        roster = [players[j] for j in lineup] + [pos]
        # A player who gets no position slot goes to Util. There is one Util slot.
        if len(roster) - (len(slots) - open_slots(roster, slots)) <= 1:
            lineup.append(i)
    return lineup


def open_slots(roster, slots):
    """Number of slots that the roster cannot fill. Each player fills one slot (bipartite matching)."""
    holder = {}

    def place(player, tried):
        for slot in slots:
            if slot in roster[player] and slot not in tried:
                tried.add(slot)
                if slot not in holder or place(holder[slot], tried):
                    holder[slot] = player
                    return True
        return False

    for player in range(len(roster)):
        place(player, set())
    return len(slots) - len(holder)
