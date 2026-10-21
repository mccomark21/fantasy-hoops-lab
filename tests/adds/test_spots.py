from datetime import date, timedelta

from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.spots import spot_plans

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def fa(name, team, value=1.0):
    return Option(Player(name, team, ("SF",)), value)


def moves(row):
    return [(w.player.player.name, w.started) for w in row.added]


def test_a_row_can_use_two_adds_in_one_spot():
    # ATL plays Mon and Tue, CHI plays Thu and Fri. One spot gets 4 games with 2 adds.
    games = {WEEK[0]: {"ATL"}, WEEK[1]: {"ATL"}, WEEK[3]: {"CHI"}, WEEK[4]: {"CHI"}}
    rows = spot_plans([], [StreamSpot()], games, [fa("Atl", "ATL"), fa("Chi", "CHI")], 5, SLOTS)
    assert moves(rows[0]) == [("Atl", tuple(WEEK[:2])), ("Chi", tuple(WEEK[3:5]))]
    assert (rows[0].plan.adds, rows[0].gain) == (2, 4)


def test_each_row_uses_different_players():
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI"}}
    fas = [fa("Best", "PHI", 2.0), fa("Next", "PHI", 1.0), fa("Last", "PHI", 0.5)]
    rows = spot_plans([], [StreamSpot()], games, fas, 5, SLOTS, rows=2)
    assert [moves(r)[0][0] for r in rows] == ["Best", "Next"]
    # The rows end when no player is left.
    assert len(spot_plans([], [StreamSpot()], games, fas[:1], 5, SLOTS)) == 1


def test_the_gain_counts_the_games_that_the_holder_loses():
    # The holder (DEN) plays Mon. PHI plays Mon, Tue and Wed: 3 games, but the holder loses 1.
    games = {WEEK[0]: {"DEN", "PHI"}, WEEK[1]: {"PHI"}, WEEK[2]: {"PHI"}}
    holder = Option(Player("Holder", "DEN", ("SF",)), 0.0)
    rows = spot_plans([Player("Holder", "DEN", ("SF",))], [StreamSpot(holder)], games, [fa("Phi", "PHI")], 5, SLOTS)
    assert rows[0].gain == 2 and rows[0].spot.holder is holder


def test_a_row_drops_the_holder_who_loses_the_fewest_games():
    # The DEN holder plays each day, the MIA holder plays no day. The row takes the spot of the MIA holder.
    games = {d: {"DEN", "PHI"} for d in WEEK[:3]}
    den, mia = (Option(Player(n, t, ("SF",)), 0.0) for n, t in (("Den", "DEN"), ("Mia", "MIA")))
    roster = [den.player, mia.player]
    rows = spot_plans(roster, [StreamSpot(den), StreamSpot(mia)], games, [fa("Phi", "PHI")], 5, SLOTS)
    assert rows[0].spot.holder is mia and rows[0].gain == 3


def test_no_adds_left_gives_no_rows():
    games = {WEEK[0]: {"PHI"}}
    assert spot_plans([], [StreamSpot()], games, [fa("Phi", "PHI")], 0, SLOTS) == []
