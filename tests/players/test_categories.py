import pandas as pd
import pytest

from fantasyhoops.core import common
from fantasyhoops.players import categories
from fantasyhoops.players.data import Signal

CFG = common.load_config()
NO_OVERRIDES = pd.DataFrame(columns=["player_id", "name", "espn_name", "yahoo_name", "team"])
CATS = list(CFG["weights"])


def nm(i):
    """The last name of player i, with letters only, for example "Qac" (name_key() drops digits)."""
    return "Q" + chr(97 + i // 26) + chr(97 + i % 26)


def key(i):
    return f"player q{nm(i)[1:]}"


def projections(n=200):
    """A projections table of n players. Player i has more of each stat than player i + 1."""
    rows = []
    for i in range(n):
        g, s = 70, (n - i) / n
        rows.append(
            {
                "player_id": str(1000 + i),
                "first_name": "Player",
                "last_name": nm(i),
                "games": g,
                "minutes": g * (12 + 24 * s),
                "field_goals": g * (2 + 8 * s),
                "threes": g * (0.2 + 3 * s),
                "free_throws": g * (1 + 5 * s),
                "offensive_rebounds": g * (0.5 + 2 * s),
                "defensive_rebounds": g * (1.5 + 7 * s),
                "assists": g * (1 + 7 * s),
                "steals": g * (0.3 + 1.5 * s),
                "blocks": g * (0.1 + 1.6 * s),
            }
        )
    return pd.DataFrame(rows)


def box(player, games, played=True, **stats):
    """games box-score rows of player with the same stats in each game."""
    base = {"pts": 0, "reb": 0, "ast": 0, "fg3m": 0, "blk": 0, "stl": 0}
    return [
        {"game_id": f"g{j}", "player_id": "1", "player": player, "played": played, **{**base, **stats}}
        for j in range(games)
    ]


def test_the_config_holds_the_6_shrinkage_values_of_the_issue():
    conf = categories.settings(CFG)
    assert conf["shrink"] == {"pts": 4, "reb": 4, "ast": 4, "threes": 10, "blk": 10, "stl": 15}
    assert conf["gap_points"] == 25 and conf["gap_games"] == 5
    assert set(conf["shrink"]) == set(CFG["weights"])


def test_the_percentile_is_the_mid_rank_percentile():
    assert categories.percentile(3, [1, 2, 3, 4]) == 62.5
    assert categories.percentile(9, [1, 2, 3, 4]) == 100
    assert categories.percentile(0, [1, 2, 3, 4]) == 0
    assert categories.percentile(2, [2, 2]) == 50


def test_the_population_is_the_valuation_pool_of_140_players():
    proj, pool = categories.projected_lines(projections(), NO_OVERRIDES, CFG)
    assert CFG["league"]["teams"] * CFG["league"]["roster_spots"] == 140
    assert len(pool) == 140 and len(proj) == 200
    assert set(pool) == {key(i) for i in range(140)}  # the best 140 by value
    out = categories.category_records(proj, pool, pd.DataFrame(columns=[*CATS, "games"]), CFG)
    assert out[key(0)]["pool"] == 140
    pts = {r["cat"]: r for r in out[key(0)]["rows"]}["PTS"]
    assert pts["proj"] == pytest.approx(100 * 139.5 / 140, abs=0.05)  # the best of 140: 139 below, 1 equal
    last = {r["cat"]: r for r in out[key(139)]["rows"]}["PTS"]
    assert last["proj"] == pytest.approx(100 * 0.5 / 140, abs=0.05)
    # A player outside the pool ranks against the pool: below each pool player.
    assert {r["cat"]: r for r in out[key(199)]["rows"]}["PTS"]["proj"] == 0
    # With no games, "now" is the projection, so both percentiles are equal.
    assert all(r["now"] == r["proj"] and r["raw"] is None and r["nw"] == 0 for r in out[key(0)]["rows"])
    assert out[key(0)]["n"] == 0 and out[key(0)]["gap"] is None


def test_a_category_with_few_games_shrinks_toward_the_projection():
    proj, pool = categories.projected_lines(projections(), NO_OVERRIDES, CFG)
    line = proj.loc[key(70)]
    season = categories.season_lines(
        pd.DataFrame(box(f"Player {nm(70)}", 2, pts=40, stl=4) + box(f"Player {nm(70)}", 1, played=False)),
        NO_OVERRIDES,
        CATS,
    )
    assert season.loc[key(70), "games"] == 2  # a game that he did not play does not count
    rows = {r["cat"]: r for r in categories.category_records(proj, pool, season, CFG)[key(70)]["rows"]}
    # (n x season + k x projection) / (n + k), with n = 2 and k = 4 for PTS, 15 for STL.
    assert rows["PTS"]["shrunk"] == round((2 * 40 + 4 * line.pts) / 6, 2) and rows["PTS"]["nw"] == 0.33
    assert rows["STL"]["shrunk"] == round((2 * 4 + 15 * line.stl) / 17, 2) and rows["STL"]["nw"] == 0.12
    assert rows["PTS"]["raw"] == 40 and rows["PTS"]["k"] == 4 and rows["STL"]["k"] == 15
    # STL moves less than PTS: its k is larger.
    assert rows["PTS"]["now"] - rows["PTS"]["proj"] > rows["STL"]["now"] - rows["STL"]["proj"] > 0
    assert [r["cat"] for r in rows.values()] == ["PTS", "REB", "AST", "3PM", "BLK", "STL"]
    assert [r["w"] for r in rows.values()] == [1.0, 1.0, 1.0, 0.7, 0.65, 0.5]


def test_a_box_score_name_goes_to_the_yahoo_name_of_the_overrides():
    overrides = pd.DataFrame(
        [{"player_id": "5988", "name": "Lu Dort", "espn_name": "Luguentz Dort", "yahoo_name": "Luguentz Dort"}]
    ).fillna("")
    overrides.loc[0, "yahoo_name"] = "Lu Dort"
    season = categories.season_lines(pd.DataFrame(box("Luguentz Dort", 3, pts=9)), overrides, CATS)
    assert list(season.index) == ["lu dort"] and season.loc["lu dort", "pts"] == 9


def test_the_gap_needs_5_games_and_25_percentile_points():
    proj, pool = categories.projected_lines(projections(), NO_OVERRIDES, CFG)
    for games, expected in ((4, None), (5, "PTS")):
        season = categories.season_lines(pd.DataFrame(box(f"Player {nm(100)}", games, pts=60)), NO_OVERRIDES, CATS)
        gap = categories.category_records(proj, pool, season, CFG)[key(100)]["gap"]
        assert (gap and gap["cat"]) == expected
    assert gap["now"] > gap["proj"] + 25


def test_the_projection_gap_rule_gives_a_signal_of_the_categories_quadrant():
    up = {"cats": {"gap": {"cat": "REB", "now": 63, "proj": 25}}}
    down = {"cats": {"gap": {"cat": "STL", "now": 4, "proj": 30}}}
    assert categories.projection_gap(up) == Signal(
        "Projection gap", "cats", True, "REB above projection: percentile 63 vs 25"
    )
    assert categories.projection_gap(down) == Signal(
        "Projection gap", "cats", False, "STL below projection: percentile 4 vs 30"
    )
    assert categories.projection_gap({"cats": {"gap": None}}) is None
    assert categories.projection_gap({}) is None  # no projection: no cats


def test_no_projections_file_gives_no_categories(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    assert categories.read_categories(CFG) == {}


def test_the_real_data_gives_6_rows_for_each_projected_player():
    if not any(common.ROOT.glob(CFG["league"]["projections"])) or not (common.DATA / "box_scores.csv").exists():
        pytest.skip("No projections file or no data/box_scores.csv")
    out = categories.read_categories(CFG)
    assert out and all(len(c["rows"]) == 6 and c["pool"] == 140 for c in out.values())
    assert all(0 <= r[k] <= 100 for c in out.values() for r in c["rows"] for k in ("now", "proj"))
