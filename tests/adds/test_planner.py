import random
from dataclasses import replace
from datetime import date, timedelta
from itertools import product

import pytest

from fantasyhoops.adds.planner import (
    Option,
    StreamSpot,
    aggressive_plan,
    aggressive_score,
    plan_score,
    rank_teams,
    schedule_plan,
    teams_to_read,
    value_above_empty,
    waiver_options,
)
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.core.lineup import best_lineup

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def fa(name, team, positions=("SF",), value=1.0, status=""):
    return Option(Player(name, team, tuple(positions), status=status), value)


def plan(roster, games, free_agents, spots=1, adds=5):
    days = open_slots_by_day(roster, games, SLOTS)
    return schedule_plan(days, games, [StreamSpot()] * spots, free_agents, adds, SLOTS)


def windows(p):
    return [(w.spot, w.team, w.add_day, w.started) for w in p.windows]


# A full roster on each day: 6 players of BOS fill all 6 starting slots. On a day when BOS does not play,
# all slots are open.
FULL = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "C", "C"])]


def test_one_player_on_several_open_days_beats_a_chain_of_adds():
    # Mon, Tue and Wed are open days (BOS does not play). PHI plays all three. Each chain team plays one day.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "CHI"}, WEEK[2]: {"PHI", "DAL"}, WEEK[3]: {"BOS", "NY"}}
    # The chain players have a higher value. The plan score does not use value.
    fas = [fa("Multi", "PHI", value=0.1), fa("A", "ATL", value=2), fa("C", "CHI", value=2), fa("D", "DAL", value=2)]
    p = plan(FULL, games, fas)
    assert (p.started_games, p.adds) == (3, 1)
    assert windows(p) == [(0, "PHI", WEEK[0], tuple(WEEK[:3]))]
    assert [o.player.name for o in p.windows[0].options] == ["Multi"]


def test_the_plan_uses_no_more_than_the_adds_that_are_left():
    # Each day only one team plays, so each started game needs a new add.
    teams = ["ATL", "CHI", "DAL", "DEN", "DET"]
    games = {d: {t} for d, t in zip(WEEK, teams)}
    fas = [fa(t, t) for t in teams]
    for adds in range(6):
        p = plan([], games, fas, adds=adds)
        assert (p.started_games, p.adds) == (adds, adds)
    assert plan([], games, fas, adds=0).windows == ()


def test_the_add_day_is_the_first_started_game_of_the_window():
    # Two empty spots, two adds. MIA plays Mon and Wed, MIL plays Tue and Thu: one add for each.
    games = {WEEK[0]: {"MIA"}, WEEK[1]: {"MIL"}, WEEK[2]: {"MIA"}, WEEK[3]: {"MIL"}}
    p = plan([], games, [fa("Mia", "MIA"), fa("Mil", "MIL")], spots=2, adds=2)
    assert (p.started_games, p.adds) == (4, 2)
    assert sorted((w.team, w.add_day, w.started, w.last_day) for w in p.windows) == [
        ("MIA", WEEK[0], (WEEK[0], WEEK[2]), WEEK[3]),
        ("MIL", WEEK[1], (WEEK[1], WEEK[3]), WEEK[3]),
    ]


def test_a_free_agent_must_fit_an_open_position():
    # Mon: BOS plays and only C is open (a third BOS guard takes Util). A PG cannot start, a C can.
    roster = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "PG"])]
    games = {WEEK[0]: {"BOS", "PHI", "ATL"}}
    fas = [fa("Guard", "PHI", ("PG",), value=5), fa("Big", "ATL", ("C",), value=1)]
    p = plan(roster, games, fas)
    assert windows(p) == [(0, "ATL", WEEK[0], (WEEK[0],))]


def test_two_added_players_cannot_fill_the_same_slot():
    # Mon: only C is open. Two spots and two centers: only one center starts, so the plan uses one add.
    roster = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "PG"])]
    games = {WEEK[0]: {"BOS", "PHI"}}
    p = plan(roster, games, [fa("Big 1", "PHI", ("C",)), fa("Big 2", "PHI", ("C",))], spots=2)
    assert (p.started_games, p.adds) == (1, 1)


def test_options_are_the_best_three_who_fit_in_order_of_value():
    # BOS and PHI play on Mon and Tue. The roster leaves only C open.
    roster = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "PG"])]
    games = {WEEK[0]: {"PHI", "BOS"}, WEEK[1]: {"PHI", "BOS"}}
    fas = [
        fa("C1", "PHI", ("C",), 1),
        fa("C2", "PHI", ("PF", "C"), 3),
        fa("C3", "PHI", ("C",), 2),
        fa("C4", "PHI", ("C",), 0.5),
        fa("Guard", "PHI", ("PG",), 9),
        fa("Hurt", "PHI", ("C",), 9, status="O"),
        fa("No line", "PHI", ("C",), None),
    ]
    p = plan(roster, games, fas)
    assert [o.player.name for o in p.windows[0].options] == ["C2", "C3", "C1"]


def test_options_are_in_order_of_blended_value():
    # The projected value puts C1 first. The blended value puts C2 first.
    games = {WEEK[0]: {"PHI"}}
    fas = [
        Option(Player("C1", "PHI", ("C",)), 3, recent_value=-1, blended_value=1),
        Option(Player("C2", "PHI", ("C",)), 1, recent_value=5, blended_value=2),
    ]
    p = plan([], games, fas)
    assert [o.player.name for o in p.windows[0].options] == ["C2", "C1"]
    assert p.value == 2


def test_a_tie_on_started_games_and_adds_goes_to_the_higher_blended_value():
    # Two plans give 2 started games with 1 add: ATL (Mon and Wed) or CHI (Tue and Wed). The search finds the CHI
    # plan first, because it keeps the spot empty on Mon. The ATL player has the higher blended value.
    games = {WEEK[0]: {"ATL"}, WEEK[1]: {"CHI"}, WEEK[2]: {"ATL", "CHI"}}
    fas = [fa("Chi", "CHI", value=1), Option(Player("Atl", "ATL", ("SF",)), 0.5, blended_value=2)]
    p = plan([], games, fas, adds=1)
    assert windows(p) == [(0, "ATL", WEEK[0], (WEEK[0], WEEK[2]))]
    assert p.score == (2, -1, 4, 0)


def test_the_search_takes_a_score_function():
    # A score that wants the most value, then the most started games: one game of Good beats two games of Bad.
    games = {WEEK[0]: {"ATL", "CHI"}, WEEK[1]: {"ATL"}}
    fas = [fa("Bad", "ATL", value=-1), fa("Good", "CHI", value=1)]
    days = open_slots_by_day(FULL, games, SLOTS)
    p = schedule_plan(
        days, games, [StreamSpot()], fas, 1, SLOTS, score=lambda started, adds, value, *_: (value, started)
    )
    assert (p.started_games, p.value) == (1, 1)


def test_a_holder_plays_until_the_add_that_drops_him():
    # The spot holds a DEN player. DEN plays Mon. PHI plays Tue to Thu. The plan keeps him for Mon, then adds PHI.
    games = {WEEK[0]: {"DEN"}, WEEK[1]: {"PHI"}, WEEK[2]: {"PHI"}, WEEK[3]: {"PHI"}}
    days = open_slots_by_day([], games, SLOTS)
    holder = fa("Holder", "DEN")
    p = schedule_plan(days, games, [StreamSpot(holder)], [fa("Phi", "PHI")], 5, SLOTS)
    assert (p.started_games, p.adds) == (4, 1)
    assert windows(p) == [(0, "DEN", None, (WEEK[0],)), (0, "PHI", WEEK[1], tuple(WEEK[1:4]))]


def test_a_large_search():
    # 2 empty spots, 5 adds, 7 open days with 6 open slots and 8 teams with 6 free agents each.
    # Each team plays 2 days, then rests 1 day. One spot needs 4 adds for 7 games (2 + 2 + 2 + 1).
    # With 5 adds, two spots get 12 games. 3 spots take about 5 seconds.
    teams = ["ATL", "CHI", "DAL", "DEN", "DET", "MIA", "MIL", "PHI"]
    games = {d: {t for j, t in enumerate(teams) if (i + j) % 3 != 0} for i, d in enumerate(WEEK)}
    pos = [("PG",), ("SG", "SF"), ("SF", "PF"), ("PF", "C"), ("C",), ("PG", "SG")]
    fas = [fa(f"{t}{k}", t, pos[k], value=k + j / 10) for j, t in enumerate(teams) for k in range(6)]
    assert plan([], games, fas, spots=1).score[:2] == (7, -4)
    assert plan([], games, fas, spots=2).score[:2] == (12, -4)


def brute_force(roster, games, free_agents, spots, adds, score=plan_score, next_week=None, weight=0.0):
    """The best score(started games, adds, value, next games, next value) of all plans, by a plain search over the
    timelines of the spots.

    value: the total value of the started games. Of the players who play, the lineup takes the best value first.
    next_week: {team: games next week}. The last player of each spot gets weight x his games next week. With
    next_week, a plan in which an added player has no started game does not count, because the search adds a
    player only on a day that he starts.
    """
    next_week = next_week or {}
    days = open_slots_by_day(roster, games, SLOTS)
    base = [[set(p.positions) for _, p in d.starters] + [set(p.positions) for p in d.bench] for d in days]

    def started(timelines):
        total, value, starts = 0, 0.0, set()
        for i, d in enumerate(days):
            now = [[o for o, first in t if first <= i][-1:] for t in timelines]
            playing = sorted((o for t in now for o in t if o.player.team in games[d.date]), key=lambda o: -o.value)
            lineup = best_lineup(base[i] + [set(o.player.positions) for o in playing], SLOTS)
            starters = [playing[j - len(base[i])] for j in lineup if j >= len(base[i])]
            total += len(starters)
            value += sum(o.value for o in starters)
            starts |= {(id(o), i) for o in starters}
        return total, value, starts

    def timelines(adds_left, first):
        yield []
        for i in range(first, len(days)):
            for o in free_agents:
                for rest in timelines(adds_left - 1, i + 1) if adds_left else []:
                    yield [(o, i), *rest]

    def distinct(combo, i):
        """True if no player is in two spots on day i."""
        now = [[o for o, first in t if first <= i][-1:] for t in combo]
        return len({o for t in now for o in t}) == sum(len(t) for t in now)

    best = score(0, 0, 0.0)
    for combo in product(*[list(timelines(adds, 0))] * spots):
        n = sum(len(t) for t in combo)
        if n <= adds and all(distinct(combo, i) for i in range(len(days))):
            count, value, starts = started(combo)
            if next_week and not all(_starts(t, starts, len(days)) for t in combo):
                continue
            last = [t[-1][0] for t in combo if t]
            ahead = [weight * next_week.get(o.player.team, 0) for o in last]
            best = max(best, score(count, n, value, sum(ahead), sum(g * o.value for g, o in zip(ahead, last))))
    return best


def _starts(timeline, starts, n_days):
    """True if each player of the timeline has a started game in his part of the timeline."""
    ends = [first for _, first in timeline[1:]] + [n_days]
    return all(any((id(o), i) in starts for i in range(first, end)) for (o, first), end in zip(timeline, ends))


@pytest.mark.parametrize("seed", range(20))
def test_the_search_finds_the_best_plan(seed):
    # Small random weeks: 4 days, 2 spots, 3 adds, 4 free agents. Compare with a plain search of all plans.
    rnd = random.Random(seed)
    teams = ["ATL", "CHI", "DAL", "DEN"]
    games = {d: {t for t in teams + ["BOS"] if rnd.random() < 0.5} for d in WEEK[:4]}
    roster = [Player(f"P{i}", "BOS", (rnd.choice(SLOTS),)) for i in range(rnd.randint(2, 6))]
    fas = [fa(t, t, rnd.sample(SLOTS, rnd.randint(1, 2)), value=rnd.random()) for t in teams]
    assert plan(roster, games, fas, spots=2, adds=3).score == pytest.approx(brute_force(roster, games, fas, 2, 3))


@pytest.mark.parametrize("seed", range(20))
def test_the_search_finds_the_best_plan_with_teammates(seed):
    # Small random weeks with 2 or 3 free agents on each team, some with the same positions: the search must give
    # each added player the best value of the free agents with his key who are not in a spot.
    rnd = random.Random(seed)
    teams = ["ATL", "ATL", "ATL", "CHI", "CHI"]
    games = {d: {t for t in ["ATL", "CHI", "BOS"] if rnd.random() < 0.6} for d in WEEK[:4]}
    roster = [Player(f"P{i}", "BOS", (rnd.choice(SLOTS),)) for i in range(rnd.randint(2, 6))]
    fas = [fa(f"{t}{n}", t, rnd.choice([("C",), ("PF", "C")]), value=rnd.random() - 0.5) for n, t in enumerate(teams)]
    assert plan(roster, games, fas, spots=2, adds=2).score == pytest.approx(brute_force(roster, games, fas, 2, 2))


EMPTY_VALUE = -10.0  # the value of an empty slot in the aggressive tests. The real value is about -11.8.


def aggressive(roster, games, free_agents, spots=1, adds=5, holders=()):
    days = open_slots_by_day(roster, games, SLOTS)
    spots = [StreamSpot(h) for h in holders] + [StreamSpot()] * (spots - len(holders))
    return aggressive_plan(days, games, spots, free_agents, adds, SLOTS, EMPTY_VALUE)


def test_the_aggressive_plan_gives_up_started_games_for_a_better_player():
    # Mon and Tue are open days. Bad (ATL) plays both, Good (CHI) plays Mon only.
    # Schedule plan: 2 games of Bad. Aggressive plan: 1 game of Good is worth 9 above an empty slot, more than
    # 2 games of Bad (2 x 4).
    games = {WEEK[0]: {"ATL", "CHI"}, WEEK[1]: {"ATL"}}
    fas = [fa("Bad", "ATL", value=-6), fa("Good", "CHI", value=-1)]
    p = plan(FULL, games, fas, adds=1)
    a = aggressive(FULL, games, fas, adds=1)
    assert (p.started_games, p.adds, p.value) == (2, 1, -12)
    assert (a.started_games, a.adds, a.value) == (1, 1, -1)
    assert windows(a) == [(0, "CHI", WEEK[0], (WEEK[0],))]
    assert value_above_empty(p, EMPTY_VALUE) == 8 and value_above_empty(a, EMPTY_VALUE) == 9


def test_the_aggressive_plan_uses_more_adds_for_better_players_up_to_the_adds_left():
    # Mon to Wed are open. A streamer of PHI plays all three days (1 add). A better player of ATL, CHI and DAL
    # plays one day each.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "CHI"}, WEEK[2]: {"PHI", "DAL"}}
    fas = [
        fa("Phi", "PHI", value=-5),
        fa("Atl", "ATL", value=-1),
        fa("Chi", "CHI", value=-1),
        fa("Dal", "DAL", value=-1),
    ]
    assert (plan(FULL, games, fas, adds=3).started_games, plan(FULL, games, fas, adds=3).adds) == (3, 1)
    found = {adds: aggressive(FULL, games, fas, adds=adds) for adds in range(4)}
    assert [(a.started_games, a.adds) for a in found.values()] == [(0, 0), (3, 1), (3, 2), (3, 3)]
    assert [w.team for w in found[2].windows] == ["ATL", "PHI"]  # 9 + 2 x 5 = 19 is more than 3 x 5 = 15
    assert [w.team for w in found[3].windows] == ["ATL", "CHI", "DAL"]
    assert found[3].value == -3


def test_the_aggressive_plan_counts_a_holder_with_no_season_value_as_an_empty_slot():
    # The holder is not in the projections file (value -inf). He plays Mon and Tue. A free agent plays Mon only.
    # As an empty slot, the holder is worth 0, so the plan drops him on Mon for 1 game of the free agent.
    games = {WEEK[0]: {"DEN", "PHI"}, WEEK[1]: {"DEN"}}
    a = aggressive([], games, [fa("Phi", "PHI", value=-5)], holders=[fa("Holder", "DEN", value=float("-inf"))])
    assert [(w.team, w.add_day, w.last_day) for w in a.windows] == [("PHI", WEEK[0], WEEK[1])]


def test_a_holder_dropped_on_the_first_day_has_no_window():
    # The holder plays Tue only. PHI plays Mon to Wed, so the plan drops him on Mon.
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"DEN", "PHI"}, WEEK[2]: {"PHI"}}
    days = open_slots_by_day([], games, SLOTS)
    p = schedule_plan(days, games, [StreamSpot(fa("Holder", "DEN"))], [fa("Phi", "PHI")], 5, SLOTS)
    assert windows(p) == [(0, "PHI", WEEK[0], tuple(WEEK[:3]))]


@pytest.mark.parametrize("seed", range(20))
def test_the_search_finds_the_best_aggressive_plan(seed):
    # Small random weeks, as in test_the_search_finds_the_best_plan, with values below 0 and the aggressive score.
    rnd = random.Random(seed)
    teams = ["ATL", "CHI", "DAL", "DEN"]
    games = {d: {t for t in teams + ["BOS"] if rnd.random() < 0.5} for d in WEEK[:4]}
    roster = [Player(f"P{i}", "BOS", (rnd.choice(SLOTS),)) for i in range(rnd.randint(2, 6))]
    fas = [fa(t, t, rnd.sample(SLOTS, rnd.randint(1, 2)), value=-9 * rnd.random()) for t in teams]
    score = aggressive_score(EMPTY_VALUE)
    a = aggressive(roster, games, fas, spots=2, adds=3)
    assert a.adds <= 3
    assert score(a.started_games, a.adds, a.value) == pytest.approx(brute_force(roster, games, fas, 2, 3, score))


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


def test_a_waiver_player_is_not_in_a_plan_before_his_clear_day():
    # PHI plays Mon to Thu. The waiver player clears on Tue, so the first day that a plan can use him is Wed.
    games = {d: {"PHI"} for d in WEEK[:4]}
    p = plan([], games, [claim("Claim", "PHI", WEEK[1])])
    assert windows(p) == [(0, "PHI", WEEK[2], (WEEK[2], WEEK[3]))]
    assert [o.player.name for o in p.windows[0].options] == ["Claim"]


def test_waiver_options_are_the_waiver_players_with_a_value_best_first():
    low, high = claim("Low", "PHI", WEEK[1], value=0.2), claim("High", "PHI", WEEK[1], value=0.9)
    no_value = Option(Player("None", "PHI", ("C",), clear_day=WEEK[1]), None)
    assert waiver_options([fa("Free", "PHI"), low, no_value, high]) == [high, low]


def test_a_free_agent_with_more_games_beats_a_better_waiver_player():
    # The free agent starts Mon to Thu. The waiver player starts only Wed and Thu, so he is not a window option.
    games = {d: {"PHI"} for d in WEEK[:4]}
    p = plan([], games, [claim("Claim", "PHI", WEEK[1], value=3.0), fa("Free", "PHI", value=0.5)])
    assert windows(p) == [(0, "PHI", WEEK[0], tuple(WEEK[:4]))]
    assert [o.player.name for o in p.windows[0].options] == ["Free"]


def rester(name, team, positions=("SF",), value=1.0, nights=(), count=0.5):
    """A free agent on the rest list. nights: his second nights of a back-to-back. Each one counts count games."""
    return replace(fa(name, team, positions, value), rest_games=tuple((d, count) for d in nights))


def test_a_player_on_the_rest_list_counts_less_than_2_started_games_for_a_back_to_back():
    # PHI plays Mon and Tue, a back-to-back. The second night counts 0.5 games, and its value counts 0.5 too.
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI"}}
    p = plan([], games, [rester("Rests", "PHI", value=2.0, nights=[WEEK[1]])])
    assert (p.started_games, p.adds, p.value) == (1.5, 1, 3.0)
    assert windows(p) == [(0, "PHI", WEEK[0], (WEEK[0], WEEK[1]))]


def test_a_player_who_is_not_on_the_rest_list_counts_as_before():
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI"}}
    p = plan([], games, [fa("Plays", "PHI", value=2.0)])
    assert (p.started_games, p.adds, p.value) == (2, 1, 4.0)


def test_the_plan_takes_a_player_with_no_rest_risk_over_a_player_on_the_rest_list():
    # Both play Mon and Tue. The player on the rest list has the higher value, but he counts 1.5 games, not 2.
    # He is not a window option, because the plan loses 0.5 games with him.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "ATL"}}
    fas = [rester("Rests", "PHI", value=5.0, nights=[WEEK[1]]), fa("Plays", "ATL", value=1.0)]
    p = plan([], games, fas)
    assert (p.started_games, [w.team for w in p.windows]) == (2, ["ATL"])
    assert [o.player.name for o in p.windows[0].options] == ["Plays"]


def test_a_tie_on_fractional_started_games_goes_to_the_fewer_adds():
    # One spot. PHI and CHI play Tue on a second night. One PHI player gives 1.5 games with 1 add.
    # ATL on Mon, then CHI on Tue, also gives 1.5 games, but with 2 adds.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "CHI"}}
    fas = [
        rester("Phi", "PHI", nights=[WEEK[1]]),
        fa("Atl", "ATL", value=3.0),
        rester("Chi", "CHI", value=3.0, nights=[WEEK[1]]),
    ]
    p = plan([], games, fas)
    assert (p.started_games, p.adds, [w.team for w in p.windows]) == (1.5, 1, ["PHI"])


def test_the_plan_score_rounds_the_started_games_for_a_tie():
    assert plan_score(0.1 + 0.2, 1) == plan_score(0.3, 1)
    assert aggressive_score(0.0)(0.1 + 0.2, 1) == aggressive_score(0.0)(0.3, 1)


def test_a_holder_on_the_rest_list_counts_less_on_a_second_night():
    games = {WEEK[0]: {"DEN"}, WEEK[1]: {"DEN"}}
    days = open_slots_by_day([], games, SLOTS)
    holder = rester("Holder", "DEN", nights=[WEEK[1]], count=0.0)
    p = schedule_plan(days, games, [StreamSpot(holder)], [], 5, SLOTS)
    assert (p.started_games, p.adds) == (1, 0)


# Next week (#60): a player who holds a stream spot on the last day of the week gets a bonus for his games next week.


def test_between_two_equal_plans_the_last_streamer_with_more_games_next_week_wins():
    # ATL and CHI play Mon only. Both plans give 1 started game with 1 add and the same value.
    games = {WEEK[0]: {"ATL", "CHI"}}
    fas = [fa("Atl", "ATL"), fa("Chi", "CHI")]
    days = open_slots_by_day(FULL, games, SLOTS)
    for more in ["ATL", "CHI"]:
        next_week = {"ATL": 2, "CHI": 2, more: 4}
        p = schedule_plan(days, games, [StreamSpot()], fas, 1, SLOTS, next_week=next_week, next_weight=0.5)
        assert windows(p) == [(0, more, WEEK[0], (WEEK[0],))]
        assert (p.started_games, p.adds, p.value, p.next_games) == (1, 1, 1.0, 2.0)
        assert p.score == (1, -1, 1.0, 2.0)


def test_the_schedule_plan_uses_the_next_week_games_only_as_a_tiebreak():
    # Phi starts Mon and Tue this week and has no games next week. Atl starts Mon only and has 4 games next week.
    # The schedule plan keeps the most started games this week.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI"}}
    days = open_slots_by_day(FULL, games, SLOTS)
    p = schedule_plan(
        days,
        games,
        [StreamSpot()],
        [fa("Phi", "PHI"), fa("Atl", "ATL")],
        1,
        SLOTS,
        next_week={"ATL": 4},
        next_weight=1.0,
    )
    assert [w.team for w in p.windows] == ["PHI"] and p.next_games == 0


def test_the_aggressive_plan_adds_the_next_week_bonus_to_the_value_of_this_week():
    # Mon is open. Good (CHI) is worth 9 above an empty slot and has no games next week. Bad (ATL) is worth 4 and
    # has 4 games next week. With weight 0.5, Bad gets a bonus of 0.5 x 4 x 4 = 8, so 4 + 8 = 12 beats 9.
    games = {WEEK[0]: {"ATL", "CHI"}}
    fas = [fa("Bad", "ATL", value=-6), fa("Good", "CHI", value=-1)]
    days = open_slots_by_day(FULL, games, SLOTS)
    found = {
        w: aggressive_plan(days, games, [StreamSpot()], fas, 1, SLOTS, EMPTY_VALUE, next_week={"ATL": 4}, next_weight=w)
        for w in [0.0, 0.5]
    }
    assert [w.team for w in found[0.0].windows] == ["CHI"]
    assert [w.team for w in found[0.5].windows] == ["ATL"]
    assert (found[0.5].next_games, found[0.5].next_value) == (2.0, -12.0)
    assert value_above_empty(found[0.5], EMPTY_VALUE) == 4  # the this-week part
    assert aggressive_score(EMPTY_VALUE)(*found[0.5].totals)[0] == 12


def test_the_bonus_never_lowers_the_this_week_part_of_the_score():
    score = aggressive_score(EMPTY_VALUE)
    this_week = score(3, 1, -15.0)
    assert score(3, 1, -15.0, 2.0, -8.0)[0] == this_week[0] + 12  # 2 games at -4: 2 x 6 above an empty slot
    assert score(3, 1, -15.0, 2.0, -30.0)[0] == this_week[0]  # below an empty slot: no bonus, never less
    assert score(3, 1, -15.0, 0.0, 0.0) == this_week
    assert plan_score(3, 1, -15.0, 2.0, -8.0)[:3] == plan_score(3, 1, -15.0)[:3]


def test_an_out_holder_gets_no_next_week_bonus():
    games = {WEEK[0]: {"PHI"}}
    days = open_slots_by_day([], games, SLOTS)
    holder = fa("Hurt", "DEN", status="O")
    p = schedule_plan(days, games, [StreamSpot(holder)], [], 0, SLOTS, next_week={"DEN": 4}, next_weight=0.5)
    assert p.next_games == 0


def test_a_kept_holder_gets_the_next_week_bonus():
    # The holder (DEN) plays Mon. With no adds left, he holds the spot on the last day of the week.
    games = {WEEK[0]: {"DEN"}, WEEK[1]: {"PHI"}}
    days = open_slots_by_day([], games, SLOTS)
    p = schedule_plan(
        days, games, [StreamSpot(fa("Holder", "DEN"))], [], 0, SLOTS, next_week={"DEN": 3}, next_weight=0.5
    )
    assert p.next_games == 1.5


@pytest.mark.parametrize("seed", range(20))
def test_the_search_finds_the_best_plan_with_next_week_games(seed):
    # Small random weeks with random games next week, for the schedule score and for the aggressive score.
    rnd = random.Random(seed)
    teams = ["ATL", "CHI", "DAL", "DEN"]
    games = {d: {t for t in teams + ["BOS"] if rnd.random() < 0.5} for d in WEEK[:4]}
    roster = [Player(f"P{i}", "BOS", (rnd.choice(SLOTS),)) for i in range(rnd.randint(2, 6))]
    fas = [fa(t, t, rnd.sample(SLOTS, rnd.randint(1, 2)), value=-9 * rnd.random()) for t in teams]
    next_week = {t: rnd.randint(0, 4) for t in teams}
    days = open_slots_by_day(roster, games, SLOTS)
    p = schedule_plan(days, games, [StreamSpot()] * 2, fas, 3, SLOTS, next_week=next_week, next_weight=0.5)
    assert p.score == pytest.approx(brute_force(roster, games, fas, 2, 3, next_week=next_week, weight=0.5))
    score = aggressive_score(EMPTY_VALUE)
    a = aggressive_plan(
        days, games, [StreamSpot()] * 2, fas, 3, SLOTS, EMPTY_VALUE, next_week=next_week, next_weight=0.5
    )
    assert score(*a.totals) == pytest.approx(brute_force(roster, games, fas, 2, 3, score, next_week, 0.5))
