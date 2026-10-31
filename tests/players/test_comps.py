from datetime import date

import pandas as pd
import pytest

from fantasyhoops.players import comps
from fantasyhoops.players.value import Game

CATS = ["pts", "reb", "ast", "threes", "stl", "blk"]
CFG = {"weights": {"pts": 1.0, "reb": 1.0, "ast": 1.0, "threes": 0.7, "blk": 0.65, "stl": 0.5}}
SCALE = pd.DataFrame({c: [10.0, 2.0] for c in CATS}, index=["mean", "std"])
NO_OVERRIDES = pd.DataFrame(columns=["player_id", "name", "espn_name", "yahoo_name", "team"])


def z(**values):
    return {c: values.get(c, 0.0) for c in CATS}


def test_the_nearest_players_come_first_with_the_category_of_the_largest_difference():
    me = z(pts=1.0, reb=1.0)
    others = {
        "far": z(pts=-2.0),
        "near": z(pts=1.0, reb=1.2),
        "mid": z(pts=1.0, reb=1.0, ast=-0.9),
        "tie-b": z(pts=1.0, reb=1.0, blk=0.5),
        "tie-a": z(pts=1.0, reb=1.0, stl=-0.5),
        "sixth": z(reb=3.0),
    }
    found = comps.nearest(me, others)
    assert [k for k, *_ in found] == ["near", "tie-a", "tie-b", "mid", "sixth"]  # 5 at most, ties by key
    key, dist, cat, diff = found[0]
    assert dist == pytest.approx(0.2) and (cat, diff) == ("reb", pytest.approx(0.2))
    assert found[3][2:] == ("ast", pytest.approx(-0.9))  # theirs minus mine


def test_the_weighted_z_score_uses_the_pool_scale_and_the_weights():
    found = comps.weighted_z(dict.fromkeys(CATS, 12.0), SCALE, CFG)
    assert found == {c: pytest.approx(w) for c, w in CFG["weights"].items()}


def test_the_blended_line_moves_the_projection_toward_the_espn_games_of_14_days():
    projected = {"ace bailey": dict.fromkeys(CATS, 10.0), "proj only": dict.fromkeys(CATS, 5.0)}
    old = Game("0", date(2026, 10, 1), "SA", True, False, dict.fromkeys(CATS, 99.0))
    new = [Game(str(i), date(2026, 10, 20 + i), "SA", True, False, dict.fromkeys(CATS, 24.0)) for i in range(7)]
    games = {"ace bailey": [old, *new], "espn only": new[:2]}
    lines = comps.blended_lines(projected, games, date(2026, 10, 29))
    assert lines["ace bailey"]["pts"] == pytest.approx(0.5 * 10 + 0.5 * 24)  # 7 games in 14 days: weight 0.5
    assert lines["proj only"]["pts"] == 5.0
    assert lines["espn only"]["pts"] == 24.0
    assert comps.recent_line([old], date(2026, 10, 29)) == ({}, 0)


def test_projected_lines_use_the_yahoo_name_of_an_override():
    projections = pd.DataFrame(
        [
            {"player_id": 7, "first_name": "Luguentz", "last_name": "Dort", "games": 2, "minutes": 60},
            {"player_id": 8, "first_name": "No", "last_name": "Games", "games": 0, "minutes": 0},
        ]
    ).assign(
        field_goals=10,
        threes=4,
        free_throws=2,
        offensive_rebounds=2,
        defensive_rebounds=6,
        assists=4,
        steals=2,
        blocks=0,
    )
    overrides = pd.DataFrame(
        [{"player_id": "7", "name": "Lu Dort", "espn_name": "Luguentz Dort", "yahoo_name": "Lu Dort", "team": "OKC"}]
    )
    lines = comps.projected_lines(projections, overrides)
    assert list(lines) == ["lu dort"]
    assert lines["lu dort"] == {"pts": 13.0, "reb": 4.0, "ast": 2.0, "threes": 2.0, "stl": 1.0, "blk": 0.0}


def test_attach_links_5_comps_by_slug_and_leaves_out_the_player_himself():
    names = ["Ace Bailey", "B One", "C Two", "D Three", "E Four", "F Five", "G Six"]
    records = [{"slug": n.lower().replace(" ", "-"), "name": n} for n in names] + [
        {"slug": "no-line", "name": "No Line"}
    ]
    lines = {n.lower(): dict.fromkeys(CATS, 10.0 + i) for i, n in enumerate(names)}
    comps.attach(records, lines, NO_OVERRIDES, SCALE, CFG)
    ace = records[0]["comps"]
    assert [c["slug"] for c in ace] == ["b-one", "c-two", "d-three", "e-four", "f-five"]
    assert ace[0] == {"slug": "b-one", "dist": 1.02, "cat": "PTS", "diff": 0.5}
    assert records[-1]["comps"] is None
    assert all(r["slug"] not in [c["slug"] for c in r["comps"]] for r in records[:-1])
