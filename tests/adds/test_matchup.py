from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.matchup import (Matchup, category_weight, matchup_plan, matchup_score, matchup_spots,
                                       matchup_weights, read_matchup, weighted_cfg)
from fantasyhoops.adds.planner import Option, StreamSpot, aggressive_plan
from fantasyhoops.adds.readers import FreeAgent, Player
from fantasyhoops.adds.slots import open_slots_by_day

FIXTURES = Path(__file__).parent / "fixtures"
CATS = ("pts", "reb", "ast", "threes", "blk", "stl")
MATCHUP_CFG = {"close": {"pts": 40, "reb": 15, "ast": 10, "threes": 5, "blk": 3, "stl": 3},
               "large": {"pts": 120, "reb": 45, "ast": 30, "threes": 15, "blk": 9, "stl": 9},
               "min_weight": 0.5}
CFG = {"weights": {c: 1.0 for c in CATS}, "adds": {"matchup": MATCHUP_CFG}}
# A scale with mean 0 and std 1, so the value of a line is the weighted sum of its stats.
SCALE = pd.DataFrame({c: [0.0, 1.0] for c in CATS}, index=["mean", "std"])
SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def tied():
    return Matchup("Opponent", {c: 10.0 for c in CATS}, {c: 10.0 for c in CATS})


def test_the_reader_reads_the_category_scores_of_both_teams():
    m = read_matchup((FIXTURES / "matchup_scores.html").read_text(encoding="utf-8"), team=10)
    assert m.opponent == "Opponent"
    assert m.mine == {"threes": 1, "pts": 5, "reb": 0, "ast": 2, "stl": 0, "blk": 0}
    assert m.theirs == {"threes": 0, "pts": 13, "reb": 5, "ast": 7, "stl": 1, "blk": 2}
    assert m.margin("pts") == -8 and m.margin("threes") == 1


def test_the_reader_finds_your_row_by_the_team_link():
    m = read_matchup((FIXTURES / "matchup_scores.html").read_text(encoding="utf-8"), team=4)
    assert m.opponent == "TradeMark" and m.mine["pts"] == 13


def test_a_page_with_no_score_table_gives_no_matchup():
    assert read_matchup((FIXTURES / "matchup.html").read_text(encoding="utf-8"), team=10) is None


def test_the_weight_is_1_up_to_the_close_margin_and_min_weight_from_the_large_margin():
    assert [category_weight(m, 5, 15, 0.5) for m in (0, 5, -5, 10, -10, 15, 40)] == [1, 1, 1, 0.75, 0.75, 0.5, 0.5]


def test_a_close_category_gets_more_weight_than_a_category_with_a_large_lead():
    # You lead 3PM by 15 and trail BLK by 2 (the example of issue #59).
    mine = {c: 10.0 for c in CATS} | {"threes": 25.0, "blk": 3.0}
    theirs = {c: 10.0 for c in CATS} | {"blk": 5.0}
    w = matchup_weights(Matchup("Opponent", mine, theirs), CFG, share_left=1.0)
    assert w["blk"] == 1.0 and w["threes"] == 0.5
    assert w["blk"] > w["threes"]


def test_the_margins_scale_with_the_share_of_the_week_that_is_left():
    # A lead of 5 3PM is close with the whole week left. With 1 day of 7 left, the large margin is 15 / 7.
    m = Matchup("Opponent", {"threes": 5.0}, {"threes": 0.0})
    assert matchup_weights(m, CFG, share_left=1.0)["threes"] == 1.0
    assert matchup_weights(m, CFG, share_left=1 / 7)["threes"] == 0.5


def test_with_no_matchup_or_all_categories_tied_all_weights_are_1():
    assert matchup_weights(None, CFG, 1.0) == {c: 1.0 for c in CATS}
    assert matchup_weights(tied(), CFG, 0.5) == {c: 1.0 for c in CATS}


def test_with_all_categories_tied_the_matchup_value_equals_the_blended_value():
    mcfg = weighted_cfg(CFG, matchup_weights(tied(), CFG, 1.0))
    line = {"pts": 12.0, "reb": 5.0, "ast": 3.0, "threes": 2.0, "blk": 1.0, "stl": 1.0}
    (o,) = blended_options([FreeAgent(Player("A", "PHI", ("C",)), 3.0, line)], [], SCALE, CFG, mcfg)
    assert o.matchup_value == o.blended_value == 24.0


def test_a_large_lead_lowers_the_matchup_value_of_a_player_who_adds_that_category():
    mcfg = weighted_cfg(CFG, {c: 1.0 for c in CATS} | {"threes": 0.5})
    shooter = {"pts": 10.0, "reb": 0, "ast": 0, "threes": 4.0, "blk": 0, "stl": 0}
    (o,) = blended_options([FreeAgent(Player("A", "PHI", ("C",)), 3.0, shooter)], [], SCALE, CFG, mcfg)
    assert (o.blended_value, o.matchup_value) == (14.0, 12.0)
    assert o.match == 12.0
    # An Option with no matchup value uses the blended value.
    assert Option(Player("B", "PHI", ("C",)), 1.0).match == 1.0


def test_the_matchup_value_of_a_holder_comes_from_his_season_projection():
    # Season totals in 10 games. Per game: 10 pts, 10 reb, 10 ast, 1 3PM, 1 stl, 1 blk.
    projections = pd.DataFrame({"first_name": ["Old"], "last_name": ["Streamer"], "games": [10],
                                "field_goals": [40], "threes": [10], "free_throws": [10],
                                "offensive_rebounds": [50], "defensive_rebounds": [50], "assists": [100],
                                "steals": [10], "blocks": [10]})
    holder = Option(Player("Old Streamer", "MIA", ("C",)), 6.0)
    mcfg = weighted_cfg(CFG, {c: 1.0 for c in CATS} | {"pts": 0.5})
    spots = matchup_spots([StreamSpot(), StreamSpot(holder)], SCALE, mcfg, projections)
    assert spots[0] == StreamSpot()
    assert spots[1].holder.value == 6.0 and spots[1].holder.matchup_value == pytest.approx(28.0)
    # A holder who is not in the projections file keeps no matchup value.
    other = Option(Player("New Guy", "MIA", ("C",)), float("-inf"))
    assert matchup_spots([StreamSpot(other)], SCALE, mcfg, projections)[0].holder.matchup_value is None


def fa(name, team, value, match=None):
    return Option(Player(name, team, ("SF",)), value, blended_value=value, matchup_value=match)


def test_the_matchup_plan_equals_the_aggressive_plan_when_all_weights_are_1():
    games = {WEEK[0]: {"ATL", "CHI"}, WEEK[1]: {"ATL"}}
    days = open_slots_by_day([], games, SLOTS)
    fas = [fa("Bad", "ATL", -6, -6), fa("Good", "CHI", -1, -1)]
    a = aggressive_plan(days, games, [StreamSpot()], fas, 1, SLOTS, -10.0)
    m = matchup_plan(days, games, [StreamSpot()], fas, 1, SLOTS, -10.0)
    assert m == a


def test_the_matchup_plan_scores_the_matchup_values_and_shows_the_blended_values():
    # Mon and Tue are open. Bad (ATL) plays both days, Good (CHI) plays Mon only. With the blended values, 1 game of
    # Good (9 above an empty slot) beats 2 games of Bad (2 x 4). The matchup lowers Good to -6 (4 above).
    games = {WEEK[0]: {"ATL", "CHI"}, WEEK[1]: {"ATL"}}
    days = open_slots_by_day([], games, SLOTS)
    fas = [fa("Bad", "ATL", -6, -6), fa("Good", "CHI", -1, -6)]
    m = matchup_plan(days, games, [StreamSpot()], fas, 1, SLOTS, -10.0)
    assert [w.player.player.name for w in m.windows] == ["Bad"]
    # The plan holds the Options with their blended values, so the value of the plan is the blended value.
    assert m.windows[0].player is fas[0] and m.value == -12
    assert matchup_score(m, -10.0) == 8


def test_the_matchup_score_counts_a_holder_with_no_value_as_an_empty_slot():
    games = {WEEK[0]: {"DEN"}}
    days = open_slots_by_day([], games, SLOTS)
    holder = Option(Player("Holder", "DEN", ("C",)), float("-inf"))
    m = matchup_plan(days, games, [StreamSpot(holder)], [], 1, SLOTS, -10.0)
    assert m.started_games == 1 and matchup_score(m, -10.0) == 0


def test_config_has_a_close_and_a_large_margin_for_each_category():
    from fantasyhoops.core.common import load_config
    cfg = load_config()
    m = cfg["adds"]["matchup"]
    assert set(m["close"]) == set(m["large"]) == set(cfg["weights"])
    assert all(m["close"][c] < m["large"][c] for c in cfg["weights"]) and 0 < m["min_weight"] <= 1
