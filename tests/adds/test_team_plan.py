import time
from datetime import date, timedelta

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.adds.team_plan import UTIL, team_plan

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]
THU, SAT = WEEK[3], WEEK[5]
X = ["ATL", "CLE", "MEM", "NO", "POR", "SAC"]  # six teams that play Thu and Sat

# The kept roster: AAA plays Thu and Sat with a PG and a C. BBB plays Sat with a SF and a C.
# Thu: PG and C are full, so SG, SF, PF and Util are open. Sat: PG, SF, C and Util are full, so SG and PF are open.
KEPT = [
    Player("Pg", "AAA", ("PG",)),
    Player("Ctr", "AAA", ("C",)),
    Player("Wing", "BBB", ("SF",)),
    Player("Big", "BBB", ("C",)),
]
GAMES = {THU: {"AAA", "YYY", *X}, SAT: {"AAA", "BBB", *X}}


def plan(roster, games, spots=1, adds=5, **kw):
    days = open_slots_by_day(roster, games, SLOTS)
    return team_plan(days, games, [StreamSpot()] * spots if isinstance(spots, int) else spots, adds, SLOTS, **kw)


def summary(p):
    return [(a.spot, a.day, a.last_day, a.slots, a.teams, a.starts) for a in p.adds]


def test_one_team_on_several_open_days_beats_a_chain_of_adds():
    # Mon, Tue and Wed are open. PHI plays all three. Each other team plays one day.
    games = {WEEK[0]: {"PHI", "ATL"}, WEEK[1]: {"PHI", "CHI"}, WEEK[2]: {"PHI", "DAL"}}
    p = plan([], games)
    assert (p.started_games, len(p.adds)) == (3, 1)
    assert summary(p) == [(0, WEEK[0], WEEK[2], (UTIL,), ("PHI",), tuple(WEEK[:3]))]


def test_the_plan_uses_no_more_than_the_adds_that_are_left():
    teams = ["ATL", "CHI", "DAL", "DEN", "DET"]
    games = {d: {t} for d, t in zip(WEEK, teams)}
    for adds in range(6):
        p = plan([], games, adds=adds)
        assert (p.started_games, len(p.adds)) == (adds, adds)
    assert plan([], games, adds=0).adds == ()


def test_an_add_names_the_open_slots_of_its_start_days_and_each_team_that_fits_equally():
    # The add starts Thu and Sat. Util is open on Thu, but only SG and PF on Sat. YYY plays only Thu.
    # AAA, the team of two kept players, fits too: the planner does not know its free agents.
    p = plan(KEPT, GAMES, adds=1)
    assert p.started_games == 2
    assert summary(p) == [(0, THU, SAT, ("SG", "PF"), ("AAA", *sorted(X)), (THU, SAT))]
    assert not p.adds[0].mixed


def test_two_adds_on_one_day_share_the_two_open_slots():
    p = plan(KEPT, GAMES, spots=2, adds=2)
    assert p.started_games == 4
    assert [(a.spot, a.day, a.slots, a.starts) for a in p.adds] == [
        (0, THU, ("SG", "PF"), (THU, SAT)),
        (1, THU, ("SG", "PF"), (THU, SAT)),
    ]


def test_a_later_add_in_the_same_spot_ends_the_band_of_the_earlier_add():
    # One spot. PHI plays Mon and Tue, CHI plays Thu, Fri and Sat. Two adds give 5 started games. The window has
    # no Wed (no game), so the first add holds the spot to Tue.
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI"}, WEEK[3]: {"CHI"}, WEEK[4]: {"CHI"}, WEEK[5]: {"CHI"}}
    p = plan([], games, adds=2)
    assert p.started_games == 5
    assert [(a.day, a.last_day, a.teams) for a in p.adds] == [
        (WEEK[0], WEEK[1], ("PHI",)),
        (WEEK[3], WEEK[5], ("CHI",)),
    ]


def test_teams_with_the_same_count_on_other_days_are_mixed_and_the_starts_are_the_days_of_all():
    # Mon, Tue and Wed are open. AAA plays Mon and Tue, BBB plays Mon and Wed: 2 started games each.
    games = {WEEK[0]: {"AAA", "BBB"}, WEEK[1]: {"AAA"}, WEEK[2]: {"BBB"}}
    (add,) = plan([], games, adds=1).adds
    assert (add.teams, add.starts, add.mixed) == (("AAA", "BBB"), (WEEK[0],), True)


def test_a_holder_plays_until_the_add_that_drops_him():
    # The holder plays Mon. PHI plays Tue to Thu. The add on Tue drops him.
    holder = Option(Player("Old", "MIA", ("SF",)), -1.0)
    games = {WEEK[0]: {"MIA"}, WEEK[1]: {"PHI"}, WEEK[2]: {"PHI"}, WEEK[3]: {"PHI"}}
    p = plan([], games, spots=[StreamSpot(holder)], adds=1)
    assert p.started_games == 4
    assert [(a.day, a.teams) for a in p.adds] == [(WEEK[1], ("PHI",))]


def test_a_holder_with_the_same_games_stays_and_the_plan_uses_no_add():
    holder = Option(Player("Keep", "TOR", ("SF",)), -1.0)
    games = {d: {"TOR", "PHX"} for d in WEEK}
    p = plan([], games, spots=[StreamSpot(holder)], adds=3)
    assert (p.started_games, p.adds) == (7, ())


def test_an_out_holder_has_no_games():
    holder = Option(Player("Hurt", "BOS", ("SF",), status="O"), -1.0)
    games = {d: {"BOS", "PHI"} for d in WEEK}
    p = plan([], games, spots=[StreamSpot(holder)], adds=1)
    assert (p.started_games, len(p.adds)) == (7, 1)


def test_a_holder_on_the_rest_list_counts_less_on_a_second_night():
    # The holder rests on Tue (count 0.5). PHI also plays Mon and Tue. The add on Mon gives 2 full games.
    holder = Option(Player("Rest", "MIA", ("SF",)), 1.0, rest_games=((WEEK[1], 0.5),))
    games = {WEEK[0]: {"MIA", "PHI"}, WEEK[1]: {"MIA", "PHI"}}
    assert plan([], games, spots=[StreamSpot(holder)], adds=0).started_games == 1.5
    p = plan([], games, spots=[StreamSpot(holder)], adds=1)
    assert (p.started_games, [a.teams for a in p.adds]) == (2, [("MIA", "PHI")])


def test_the_team_with_more_games_next_week_wins_a_tie_and_is_the_only_team():
    games = {WEEK[0]: {"AAA", "BBB"}}
    next_week = {"AAA": 2, "BBB": 4}
    (add,) = plan([], games, adds=1, next_week=next_week, next_weight=0.5).adds
    assert add.teams == ("BBB",)
    (add,) = plan([], games, adds=1).adds  # no next-week tiebreak: both teams fit
    assert add.teams == ("AAA", "BBB")


def test_the_next_week_games_never_beat_a_started_game_this_week():
    games = {WEEK[0]: {"AAA"}, WEEK[1]: {"AAA", "BBB"}}
    (add,) = plan([], games, adds=1, next_week={"BBB": 4}, next_weight=0.5).adds
    assert (add.day, add.teams) == (WEEK[0], ("AAA",))


# The week of 2026-10-26 to 2026-11-01 from data/schedule.csv, and the kept roster of the search benchmark of #100.
# The roster fills all 6 slots on Wed and Fri and leaves the other 5 days open.
FULL_WEEK = [date(2026, 10, 26) + timedelta(days=i) for i in range(7)]
FULL_GAMES = dict(
    zip(
        FULL_WEEK,
        [
            set("ATL BOS CHA CHI CLE DAL DEN GS HOU IND MEM MIA MIL MIN OKC PHX UTAH WSH".split()),
            set("BKN BOS DET LAL NY POR SA SAC".split()),
            set("ATL CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MIA MIL MIN NO NY OKC ORL PHI SA TOR UTAH WSH".split()),
            set("ATL CLE MEM NO POR SAC".split()),
            set("BKN BOS CHA CHI DAL DEN DET GS HOU IND LAC LAL MIA MIN NY ORL PHI PHX TOR WSH".split()),
            set("ATL CHA CLE HOU MEM MIL MIN NO OKC PHI POR SA SAC UTAH".split()),
            set("BKN BOS GS IND LAC LAL ORL TOR".split()),
        ],
    )
)
FULL_ROSTER = [
    Player("R1", "LAL", ("PG",)),
    Player("R2", "NY", ("SG",)),
    Player("R3", "PHI", ("SF",)),
    Player("R4", "DET", ("PF",)),
    Player("R5", "TOR", ("C",)),
    Player("R6", "ORL", ("SF", "PF")),
    Player("R7", "LAC", ("PG", "SG")),
]


def test_a_full_week_with_3_adds_and_3_spots_takes_less_than_half_a_second(monkeypatch):
    # #140: the 2026-10-26 run (7 days, 5 open, 3 adds) took 6.59 s for the schedule search alone.
    work = timing.Work()
    monkeypatch.setattr(timing, "WORK", work)
    start = time.perf_counter()
    p = plan(FULL_ROSTER, FULL_GAMES, spots=3, adds=3, next_week={"ATL": 4, "BKN": 3}, next_weight=0.5)
    assert time.perf_counter() - start < 0.5
    assert 0 < work.states <= work.calls
    assert len(p.adds) <= 3 and p.started_games > 0
    for a in p.adds:
        assert a.day in a.starts and all(a.day <= d <= a.last_day for d in a.starts)
        assert all(t in FULL_GAMES[d] for t in a.teams for d in a.starts)
