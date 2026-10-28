from datetime import date, timedelta

from fantasyhoops.adds.planner import Option, counted_games, rank_teams, teams_to_read, waiver_options
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]

# A full roster on each day: 6 players of BOS fill all 6 starting slots. On a day when BOS does not play,
# all slots are open.
FULL = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "C", "C"])]


def fa(name, team, positions=("SF",), value=1.0):
    return Option(Player(name, team, tuple(positions)), value)


def test_rank_teams_by_open_days_covered():
    games = {WEEK[0]: {"PHI", "ATL", "BOS"}, WEEK[1]: {"PHI", "BOS"}, WEEK[2]: {"PHI", "CHI"}}
    days = open_slots_by_day(FULL, games, SLOTS)  # Mon and Tue: BOS plays, no open slot. Wed is open.
    ranking = rank_teams(days, games)
    assert [(r.team, r.open_days) for r in ranking] == [("CHI", (WEEK[2],)), ("PHI", (WEEK[2],))]


def test_teams_to_read_cover_each_open_day():
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "ATL"}, WEEK[2]: {"CHI"}}
    ranking = rank_teams(open_slots_by_day([], games, SLOTS), games)
    assert [r.team for r in ranking] == ["ATL", "PHI", "CHI"]
    assert teams_to_read(ranking, count=1) == ["ATL", "CHI"]


def claim(name, team, clear_day, positions=("SF",), value=1.0):
    """The Option of a waiver player who clears waivers on clear_day."""
    return Option(Player(name, team, tuple(positions), clear_day=clear_day), value)


def test_waiver_options_are_the_waiver_players_with_a_value_best_first():
    low, high = claim("Low", "PHI", WEEK[1], value=0.2), claim("High", "PHI", WEEK[1], value=0.9)
    no_value = Option(Player("None", "PHI", ("C",), clear_day=WEEK[1]), None)
    assert waiver_options([fa("Free", "PHI"), low, no_value, high]) == [high, low]


def test_counted_games_counts_1_for_each_game_or_the_count_of_a_rest_day():
    assert counted_games(((WEEK[1], 0.5),), WEEK[:3]) == 2.5
    assert counted_games((), WEEK[:3]) == 3
