"""The daily lineup: which players fill the starting slots on one day, and the rules of the playoff lineup fit.

The slots are the position slots (config.toml [league] slots) + one Util slot. A player fills at most one slot that
his positions allow. Util takes any player. A player without a slot sits on the bench.

This module is the one source of the lineup-fit rules (#133): the best lineup, the Util count, the ideal games of a
week and the percent bands. core/roster.py and draft/team_score.py call these functions. draft/board.py puts UTIL,
BANDS and an ideal_games() table in the page data, and draft/team_builder.js reads them. team_builder.js keeps a
copy of the matching and of the rest rule, because the board scores the core that the user picks in the browser.
tests/draft/test_team_builder.py shows that the copy gives the same results as this module.
The module writes no file.
"""

from collections import Counter

UTIL = 1  # the Util slots of a lineup
# The percent bands of the lineup fit: (lowest ratio, level, text for a screen reader), highest band first.
BANDS = [(0.9, "good", "90% or more"), (0.7, "warn", "70% to 89%"), (0.0, "bad", "less than 70%")]


def band(ratio):
    """(level, text) of the band of a ratio, for example ("good", "90% or more") for 0.95."""
    return next((level, text) for low, level, text in BANDS if ratio >= low)


def ideal_games(players, week_teams, slots):
    """The ideal started games of a team of players in one week.

    week_teams: the NBA teams that play on each day of the week (one collection for each day).
    Each player gets the most games of any NBA team that week. Each game day has at most the starting slots
    (the position slots + UTIL).
    """
    counts = Counter(team for teams in week_teams for team in teams)
    game_days = sum(1 for teams in week_teams if teams)
    return min(players * max(counts.values(), default=0), (len(slots) + UTIL) * game_days)


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
    return len(slots) - len(_match(roster, slots))


def starting_slots(players, slots):
    """The slot of each player who starts, as {index in players: slot}. The slot is a position slot or "Util".

    players and slots are the same as in best_lineup(). The players who sit are not in the result.
    """
    lineup = best_lineup(players, slots)
    holder = _match([players[i] for i in lineup], slots)
    out = {lineup[j]: slot for slot, j in holder.items()}
    # best_lineup() lets at most one starter go without a position slot. He takes Util.
    out.update({i: "Util" for i in lineup if i not in out})
    return out


def _match(roster, slots):
    """A largest matching of players to position slots, as {slot: index in roster}."""
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
    return holder
