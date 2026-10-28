from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.matchup import (
    Matchup,
    category_weight,
    matchup_weights,
    read_matchup,
    weighted_cfg,
)
from fantasyhoops.adds.planner import Option
from fantasyhoops.adds.readers import FreeAgent, Player

FIXTURES = Path(__file__).parent / "fixtures"
CATS = ("pts", "reb", "ast", "threes", "blk", "stl")
MATCHUP_CFG = {
    "close": {"pts": 40, "reb": 15, "ast": 10, "threes": 5, "blk": 3, "stl": 3},
    "large": {"pts": 120, "reb": 45, "ast": 30, "threes": 15, "blk": 9, "stl": 9},
    "min_weight": 0.5,
}
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


def test_the_reader_reads_the_live_score_table_of_2026_10_21():
    # After the first games, the header has no "Score" cell, and the first link of each row is a logo with no text.
    m = read_matchup((FIXTURES / "matchup_scores_live.html").read_text(encoding="utf-8"), team=10)
    assert m.opponent == "Opponent"
    assert m.mine == {"threes": 4, "pts": 24, "reb": 4, "ast": 9, "stl": 1, "blk": 0}
    assert m.theirs == {"threes": 5, "pts": 45, "reb": 17, "ast": 14, "stl": 1, "blk": 3}


def test_the_reader_does_not_read_the_player_table_as_the_score_table():
    # The player table has the same stat headers. Its rows have player links, not team links.
    head = "".join(f"<th>{h}</th>" for h in ["Player", "PTS", "REB", "AST", "3PTM", "BLK", "ST"])
    row = '<tr><td><a href="https://sports.yahoo.com/nba/players/1">A Player</a></td>' + "<td>1</td>" * 6 + "</tr>"
    html = f"<table><thead><tr>{head}</tr></thead><tbody>{row}{row}</tbody></table>"
    assert read_matchup(html, team=10) is None


def test_a_player_link_that_ends_in_your_team_id_is_not_your_team_link():
    # Your team ID is 10. The row of the opponent has a player link that ends in /10, before the team link.
    head = "".join(f"<th>{h}</th>" for h in ["Team", "PTS", "REB", "AST", "3PTM", "BLK", "ST"])

    def row(links, pts):
        return f"<tr><td>{links}</td><td>{pts}</td>" + "<td>0</td>" * 5 + "</tr>"

    mine = row('<a href="https://basketball.fantasysports.yahoo.com/nba/22820/10">Mine</a>', 5)
    theirs = row(
        '<a href="https://sports.yahoo.com/nba/players/10">A Player</a>'
        '<a href="https://basketball.fantasysports.yahoo.com/nba/22820/4">Theirs</a>',
        9,
    )
    html = f"<table><thead><tr>{head}</tr></thead><tbody>{mine}{theirs}</tbody></table>"
    m = read_matchup(html, team=10)
    assert m.mine["pts"] == 5 and m.theirs["pts"] == 9


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


def test_config_has_a_close_and_a_large_margin_for_each_category():
    from fantasyhoops.core.common import load_config

    cfg = load_config()
    m = cfg["adds"]["matchup"]
    assert set(m["close"]) == set(m["large"]) == set(cfg["weights"])
    assert all(m["close"][c] < m["large"][c] for c in cfg["weights"]) and 0 < m["min_weight"] <= 1
