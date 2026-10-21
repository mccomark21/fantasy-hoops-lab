from datetime import date, timedelta

import pandas as pd

from fantasyhoops.adds.readers import Player, Week
from fantasyhoops.adds.slots import (open_slots_by_day, planning_window, plans_next_week, roster_spots_used,
                                     team_games)

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON, TUE, WED = date(2027, 1, 4), date(2027, 1, 5), date(2027, 1, 6)

ROSTER = [
    Player("Guard", "BOS", ("PG", "SG"), "PG"),
    Player("Wing", "BOS", ("SF",), "SF"),
    Player("Big", "NY", ("C",), "C"),
    Player("Hurt", "NY", ("PF",), "PF", "O", "Out"),             # Out: does not play
    Player("Doubt", "SA", ("PF", "C"), "BN", "Q", "Questionable"),  # flagged: plays
    Player("Second big", "SA", ("C",), "BN"),
    Player("Stashed", "BOS", ("PG",), "IL", "O", "Out"),         # on IL: does not play
]
# Mon: BOS and NY play. Tue: SA plays. Wed: all three teams play.
GAMES = {MON: {"BOS", "NY", "LAL", "MIA"}, TUE: {"SA", "DAL"}, WED: {"BOS", "NY", "SA", "PHI", "GS", "OKC"}}


def by_date():
    return {d.date: d for d in open_slots_by_day(ROSTER, GAMES, SLOTS)}


def names(players):
    return [p.name for p in players]


def test_out_and_il_players_do_not_play():
    mon = by_date()[MON]
    assert [(slot, p.name) for slot, p in mon.starters] == [("PG", "Guard"), ("SF", "Wing"), ("C", "Big")]
    assert mon.open == ("SG", "PF", "Util")
    assert mon.nba_games == 2


def test_a_flagged_player_plays():
    tue = by_date()[TUE]
    assert [(slot, p.name) for slot, p in tue.starters] == [("PF", "Doubt"), ("C", "Second big")]
    assert tue.open == ("PG", "SG", "SF", "Util")


def test_util_takes_the_player_without_a_position_slot():
    # Wed: Big takes C and Doubt takes PF. Second big gets no position slot, so he takes Util.
    wed = by_date()[WED]
    assert [(slot, p.name) for slot, p in wed.starters] == [
        ("PG", "Guard"), ("SF", "Wing"), ("PF", "Doubt"), ("C", "Big"), ("Util", "Second big")]
    assert wed.open == ("SG",)
    assert wed.bench == ()


def test_a_third_center_goes_to_the_bench():
    roster = [Player(f"C{i}", "BOS", ("C",), "BN") for i in range(3)]
    day = open_slots_by_day(roster, {MON: {"BOS", "NY"}}, SLOTS)[0]
    assert names(day.bench) == ["C2"]
    assert day.open == ("PG", "SG", "SF", "PF")


def test_il_players_take_no_roster_spot():
    assert roster_spots_used(ROSTER) == 6


def test_planning_window_runs_from_today_to_the_end_of_the_week():
    week = Week(number=1, days=(MON, TUE, WED))
    assert planning_window(week, TUE) == [TUE, WED]
    assert planning_window(week, date(2027, 1, 1)) == [MON, TUE, WED]
    assert planning_window(week, date(2027, 1, 7)) == []


def test_on_the_last_day_of_the_week_the_planner_plans_the_next_week():
    week = Week(number=1, days=(MON, TUE, WED))
    following = Week(number=2, days=tuple(date(2027, 1, 7) + timedelta(days=i) for i in range(7)))
    assert not plans_next_week(week, MON)
    assert not plans_next_week(week, TUE)
    assert plans_next_week(week, WED)
    # The window of the next week is the whole week, also when today is before its first day.
    assert planning_window(following, WED) == list(following.days)


def test_team_games_reads_the_schedule():
    sched = pd.DataFrame({"date": pd.to_datetime(["2027-01-04", "2027-01-04", "2027-01-05", "2027-01-05"]),
                          "team": ["BOS", "NY", "SA", "DAL"], "opponent": ["NY", "BOS", "DAL", "SA"]})
    assert team_games(sched, [MON, TUE, WED]) == {MON: {"BOS", "NY"}, TUE: {"SA", "DAL"}, WED: set()}
