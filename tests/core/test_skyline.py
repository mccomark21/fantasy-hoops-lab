import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.core.common import load_config
from fantasyhoops.core.skyline import week_facts

# Weeks A-E of docs/wiki/schedule-map-2026-11-04.md: the rows of data/schedule.csv on 2026-11-04, as JSON.
FIXTURE = Path(__file__).parent / "fixtures" / "skyline_weeks.json"
WEEKS = {
    "A": date(2026, 11, 2),
    "B": date(2027, 2, 15),
    "C": date(2027, 1, 11),
    "D": date(2026, 11, 9),
    "E": date(2027, 2, 8),
}
CFG = {
    "quality_games": {"max_games_per_day": 6},
    "skyline": {"max_adds": 4, "scarce_teams": 5, "anchor_max_games": 4, "heavy_max_teams": 3},
}


@pytest.fixture(scope="module")
def weeks():
    sched = pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])
    return {k: week_facts(sched, start, CFG) for k, start in WEEKS.items()}


def schedule(games):
    """A schedule with two rows for each game, as in data/schedule.csv. games: [(date, home, away)]."""
    rows = [(d.isoformat(), t, o) for d, h, a in games for t, o in ((h, a), (a, h))]
    return pd.DataFrame(rows, columns=["date", "team", "opponent"])


MON = date(2027, 3, 1)


def day(i):
    return MON + timedelta(i)


def filler(i, n, first=0):
    """n games on day i between filler teams F<first>, F<first+1>, ..."""
    return [(day(i), f"F{first + 2 * k:02}", f"F{first + 2 * k + 1:02}") for k in range(n)]


@pytest.mark.parametrize(
    "week, totals", [("A", [4, 5, 6, 6]), ("B", [3, 3, 4, 4]), ("C", [5, 5, 6, 7]), ("D", [4, 5, 6, 7])]
)
def test_ladder_totals_of_the_prototype(weeks, week, totals):
    assert [r.games for r in weeks[week].rungs] == totals
    assert [r.adds for r in weeks[week].rungs] == [1, 2, 3, 4]


def test_rung_one_of_week_a_names_the_two_teams_that_play_4_games(weeks):
    (leg,) = weeks["A"].rungs[0].legs
    assert (leg.games, leg.light) == (4, 1)
    assert set(leg.teams) == {"MIA", "PHX"}


@pytest.mark.parametrize(
    "week, kind, heavy",
    [
        ("A", "anchor", ()),
        ("B", "dead-day", ()),
        ("C", "heavy-team", ("DEN",)),
        ("D", "anchor", ()),
        ("E", "heavy-team", ("POR",)),
    ],
)
def test_week_types_of_weeks_a_to_e(weeks, week, kind, heavy):
    assert weeks[week].week_type == kind
    assert weeks[week].heavy_teams == heavy


def test_anchor_nights_of_the_anchor_weeks(weeks):
    assert weeks["A"].anchors == (date(2026, 11, 5),)
    assert weeks["D"].anchors == (date(2026, 11, 12),)
    assert weeks["C"].anchors == ()


def test_dead_day_span_of_week_b_is_the_three_days_with_no_games(weeks):
    assert weeks["B"].dead_span == (4, 7)
    assert weeks["B"].no_games == (False, False, False, False, True, True, True)


def test_rung_4_of_week_d_re_plans(weeks):
    rungs = weeks["D"].rungs
    assert [r.replan for r in rungs] == [False, False, False, True]
    assert rungs[3].best_games == rungs[3].games == 7
    # Each other rung keeps the legs of the rung above and splits one leg.
    for above, rung in zip(rungs[:2], rungs[1:3]):
        assert set(above.cuts) < set(rung.cuts) and len(rung.cuts) == len(above.cuts) + 1


def test_nested_rungs_keep_the_cuts_of_the_rung_above(weeks):
    for week in weeks.values():
        for above, rung in zip(week.rungs, week.rungs[1:]):
            if not rung.replan:
                assert set(above.cuts) <= set(rung.cuts)


def test_zero_gain_rungs(weeks):
    assert [r.zero_gain for r in weeks["A"].rungs] == [False, False, False, True]
    assert [r.zero_gain for r in weeks["B"].rungs] == [False, True, False, True]
    assert [r.gain for r in weeks["C"].rungs] == [0, 0, 1, 1]
    assert weeks["B"].rungs[1].plus_one == ()


def test_plus_one_is_the_new_game_that_the_extra_add_buys(weeks):
    a = weeks["A"].rungs
    assert a[0].plus_one == ()
    assert len(a[1].plus_one) == 1 and len(a[2].plus_one) == 1
    # The day that the 2nd add buys is a game day of the new leg that rung 1 did not cover.
    (bought,) = a[1].plus_one
    assert bought not in a[0].legs[0].pattern
    assert any(bought in leg.pattern for leg in a[1].legs)


def test_scarce_legs_name_their_teams_and_other_legs_give_a_count(weeks):
    legs = weeks["A"].rungs[1].legs
    assert legs[0].scarce and set(legs[0].named) == {"MIA", "PHX"}
    assert not legs[1].scarce and legs[1].named == () and legs[1].team_count == 16
    five = next(leg for r in weeks["E"].rungs for leg in r.legs if leg.team_count == 5)
    assert five.scarce and len(five.named) == 5


def test_the_back_to_backs_of_each_team_in_a_leg(weeks):
    (leg,) = weeks["C"].rungs[0].legs  # DEN plays 5 games in 7 days
    pairs = leg.b2b["DEN"]
    assert pairs and all((b - a).days == 1 for a, b in pairs)


def test_a_back_to_back_is_decisive_only_when_a_scarce_leg_depends_on_it():
    # Leg Mon-Wed: only T1 and T2 play 2 games, and only on a back-to-back (Tue, Wed). The other teams play 1 game.
    games = [(day(1), "T1", "T2"), (day(2), "T1", "T2"), (day(0), "T3", "T4"), (day(0), "T5", "T6")]
    games += [(day(i), "T3", "T5") for i in (4, 6)] + [(day(i), "T4", "T6") for i in (4, 6)]
    week = week_facts(schedule(games), MON, CFG)
    leg = next(leg for r in week.rungs for leg in r.legs if (leg.first, leg.last) == (0, 3))
    assert leg.scarce and set(leg.teams) == {"T1", "T2"}
    assert leg.decisive_b2b == ((day(1), day(2)),)
    # The same back-to-back, but 6 teams have one in the leg: no callout.
    more = games + [(day(1), "T3", "T4"), (day(2), "T3", "T4"), (day(1), "T5", "T6"), (day(2), "T5", "T6")]
    week = week_facts(schedule(more), MON, CFG)
    assert all(leg.decisive_b2b == () for r in week.rungs for leg in r.legs)


def test_one_games_per_night_count_drives_labels_light_line_and_week_type():
    # 4 games (8 team rows) on Thursday, 10 or 11 games on the other days. S1 and S2 play each day, so the 1-add leg
    # is scarce and depends on Thursday. 4 games is a light night and an anchor night. 8 team rows is neither.
    # A count of team rows gives other labels, no light night and no anchor.
    games = [(day(i), "S1", "S2") for i in range(7)]
    for i in range(7):
        games += filler(i, 3, first=40) if i == 3 else filler(i, 9)
    games.append((day(6), "F18", "F19"))
    games.append((day(5), "F18", "F19"))
    week = week_facts(schedule(games), MON, CFG)
    assert week.games == (10, 10, 10, 4, 10, 11, 11)
    assert week.light == (False, False, False, True, False, False, False)
    assert week.light_max == 6
    assert week.scale_max == 11  # the skyline fits the busiest night, in games
    assert week.anchors == (day(3),)
    assert week.week_type == "anchor"


def test_light_night_limit_comes_from_config_toml():
    cfg = load_config()
    week = week_facts(schedule(filler(0, 3)), MON)
    assert week.light_max == cfg["quality_games"]["max_games_per_day"]


def test_a_week_with_missing_days_gives_a_result():
    # NBA Cup knockout weeks: the schedule has games on Mon-Wed only.
    games = filler(0, 8) + filler(1, 7) + filler(2, 8)
    week = week_facts(schedule(games), MON, CFG)
    assert week.games == (8, 7, 8, 0, 0, 0, 0)
    assert week.week_type == "dead-day" and week.dead_span == (3, 7)
    assert len(week.rungs) == 4 and week.rungs[0].games >= 1


def test_a_week_with_no_games_gives_a_result():
    week = week_facts(schedule(filler(0, 5, first=0)), MON + timedelta(7), CFG)
    assert week.games == (0,) * 7
    assert [r.games for r in week.rungs] == [0, 0, 0, 0]
    assert week.rungs[0].legs[0].teams == () and week.heavy_teams == ()
    assert week.week_type == "dead-day"


def test_a_light_night_weight_in_the_ladder_takes_fewer_light_night_games():
    # HH plays the 4 heavy nights (Mon, Wed, Fri, Sun: 9 games). LL plays the 3 light nights (Tue, Thu, Sat: 2 games).
    games = []
    for i in range(7):
        if i % 2:
            games += [(day(i), "LL", "L2")] + filler(i, 1, first=20 * i)
        else:
            games += [(day(i), "HH", "H2")] + filler(i, 8, first=20 * i)
    sched = schedule(games)
    rung = week_facts(sched, MON, CFG).rungs[0]
    assert (rung.games, rung.light, set(rung.legs[0].teams)) == (4, 0, {"HH", "H2"})
    # 3 light games x 2 = 6 beats 4 heavy games. Rung.games is the count with no weight.
    heavy = {**CFG, "quality_games": {"max_games_per_day": 6, "light_night_weight": 2.0}}
    rung = week_facts(sched, MON, heavy).rungs[0]
    assert (rung.games, rung.light, set(rung.legs[0].teams)) == (3, 3, {"LL", "L2"})
