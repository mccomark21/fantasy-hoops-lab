import math

import pandas as pd
import pytest

from fantasyhoops.core import common
from fantasyhoops.core.common import load_config
from fantasyhoops.players import luck

K = {"stl": 80, "blk": 25, "ast": 100, "reb": 60, "threes": 300}
MIN_CHANCES = {"stl": 20, "blk": 25, "ast": 40, "reb": 40, "threes": 20}
CFG = {"players": {"luck": {"k": K, "min_games": 5, "min_chances": MIN_CHANCES}}, "league": {"espn_season": 2027}}


def frame(rows):
    """A frame in the shape of data/nba_stats.csv. rows: (nba_id, gp, {cat: (makes, chances)})."""
    out = []
    for nba_id, gp, stats in rows:
        rec = {"nba_id": nba_id, "name": f"P{nba_id}", "name_key": f"p{nba_id}", "team": "AAA", "gp": gp}
        for cat in luck.CATEGORIES:
            makes, chances = stats.get(cat, (math.nan, math.nan))
            rec[f"{cat}_makes"], rec[f"{cat}_chances"] = makes, chances
        out.append(rec)
    return pd.DataFrame(out)


def test_config_has_the_luck_settings():
    s = luck.settings(load_config())
    assert set(s["k"]) == set(luck.CATEGORIES) == set(s["min_chances"])
    assert s["min_games"] > 0


def test_nba_season():
    assert luck.nba_season(2026) == "2025-26"


def test_league_rates_skip_rows_with_no_chances():
    rates = luck.league_rates(frame([(1, 10, {"blk": (10, 40)}), (2, 10, {"blk": (5, 60)}), (3, 10, {})]))
    assert rates["blk"] == pytest.approx(15 / 100)
    assert rates["stl"] is None


def test_baseline_shrinks_the_past_rate_toward_the_league():
    # (40 + 25 x 0.2) / (100 + 25) = 0.36, and the league rate did not change.
    p0, weight = luck.baseline(40, 100, 25, 0.2, 0.2)
    assert p0 == pytest.approx(0.36)
    assert weight == 125


def test_baseline_rescales_by_the_league_rate_change():
    # REB: 0.695 in 2025-26, 0.543 in 2026-27. A 0.80 rebounder with 1000 chances and k 60.
    p0, _ = luck.baseline(800, 1000, 60, 0.695, 0.543)
    assert p0 == pytest.approx((800 + 60 * 0.695) / 1060 * 0.543 / 0.695)


def test_baseline_with_no_past_row_is_the_league_rate_of_now():
    assert luck.baseline(None, None, 25, 0.193, 0.218) == (0.218, 25)
    assert luck.baseline(math.nan, math.nan, 25, 0.193, 0.218) == (0.218, 25)
    assert luck.baseline(4, 20, 25, None, 0.218) == (0.218, 25)


def test_baseline_stays_below_1():
    p0, _ = luck.baseline(99, 100, 1, 0.5, 0.9)
    assert p0 == luck.RATE_LIMITS[1]


def test_luck_z_uses_the_beta_binomial_spread():
    # n = 100, p0 = 0.2, w = 125: variance = 100 x 0.2 x 0.8 x 225 / 126.
    z = luck.luck_z(30, 100, 0.2, 125)
    assert z == pytest.approx(10 / math.sqrt(16 * 225 / 126))
    assert luck.luck_z(20, 100, 0.2, 125) == 0
    assert luck.luck_z(10, 100, 0.2, 125) < 0  # fewer makes than expected: unlucky


def test_luck_z_with_no_chances_is_none():
    assert luck.luck_z(0, 0, 0.2, 25) is None
    assert luck.luck_z(math.nan, math.nan, 0.2, 25) is None


def test_ready_rule():
    assert luck.is_ready(5, 25, 5, 25)
    assert not luck.is_ready(4, 100, 5, 25)
    assert not luck.is_ready(10, 24, 5, 25)
    assert not luck.is_ready(10, math.nan, 5, 25)


def test_overall_is_stouffer():
    assert luck.overall([1.0, 2.0, None, math.nan]) == pytest.approx(3 / math.sqrt(2))
    assert luck.overall([None, math.nan]) is None


def test_luck_table_expected_and_z():
    current = frame(
        [
            (1, 10, {"blk": (20, 100), "reb": (30, 100)}),
            (2, 10, {"blk": (20, 100), "reb": (30, 30)}),  # REB is not ready: 30 chances
            (3, 4, {"blk": (40, 100)}),  # not ready: 4 games
        ]
    )
    previous = frame([(1, 70, {"blk": (100, 500), "reb": (300, 500)}), (9, 70, {"blk": (100, 500)})])
    table = luck.luck_table(current, previous, CFG).set_index("nba_id")
    now = luck.league_rates(current)
    before = luck.league_rates(previous)
    p0, weight = luck.baseline(100, 500, 25, before["blk"], now["blk"])
    one = table.loc[1]
    assert one["blk_p0"] == pytest.approx(p0)
    assert one["blk_expected_pg"] == pytest.approx(100 * p0 / 10)
    assert one["blk_chances_pg"] == 10 and one["blk_makes_pg"] == 2
    assert one["blk_z"] == pytest.approx(luck.luck_z(20, 100, p0, weight))
    assert one["luck"] == pytest.approx((one["blk_z"] + one["reb_z"]) / math.sqrt(2))
    assert one["luck_count"] == 2
    two = table.loc[2]  # no past row: p0 = the league rate of now
    assert two["blk_p0"] == pytest.approx(now["blk"])
    assert not two["reb_ready"] and math.isnan(two["reb_z"])
    assert two["luck"] == pytest.approx(two["blk_z"])
    assert math.isnan(table.loc[3, "luck"]) and table.loc[3, "luck_count"] == 0


def test_elite_shot_blocker_is_not_lucky_against_his_own_rate():
    # A 0.40 shot blocker in the past season blocks at 0.40 again. Against the league rate he looks lucky.
    current = frame([(1, 15, {"blk": (40, 100)}), (2, 15, {"blk": (19, 100)}), (3, 15, {"blk": (19, 100)})])
    previous = frame([(1, 70, {"blk": (240, 600)}), (2, 70, {"blk": (114, 600)}), (3, 70, {"blk": (114, 600)})])
    with_past = luck.luck_table(current, previous, CFG).set_index("nba_id")
    no_past = luck.luck_table(current, None, CFG).set_index("nba_id")
    assert no_past.loc[1, "blk_z"] > 1
    assert abs(with_past.loc[1, "blk_z"]) < 0.2


def test_read_luck_with_no_file_is_none(tmp_path):
    assert luck.read_luck(CFG, tmp_path) is None


def test_read_luck_with_no_past_file(tmp_path):
    frame([(1, 10, {"blk": (20, 100)})]).to_csv(tmp_path / "nba_stats.csv", index=False)
    table = luck.read_luck(CFG, tmp_path)
    assert table.loc[0, "blk_p0"] == pytest.approx(0.2)


def test_read_luck_of_the_real_files():
    if not (common.DATA / "nba_stats.csv").exists():
        pytest.skip("no data/nba_stats.csv")
    table = luck.read_luck(load_config())
    assert len(table) > 0
    assert table["luck"].notna().any()


def test_by_name_key_gives_the_row_of_each_key_with_none_for_nan():
    table = luck.luck_table(frame([(1, 10, {"blk": (20, 100)}), (2, 2, {"blk": (20, 100)})]), None, CFG)
    rows = luck.by_name_key(table)
    assert set(rows) == {"p1", "p2"}
    assert rows["p1"]["luck"] == pytest.approx(table.loc[0, "luck"])
    assert rows["p2"]["luck"] is None and rows["p2"]["blk_z"] is None  # 2 games: not ready
    assert rows["p1"]["stl_z"] is None  # no chances


def test_by_name_key_keeps_the_first_row_of_a_key_and_none_gives_nothing():
    table = luck.luck_table(frame([(1, 10, {"blk": (20, 100)}), (2, 10, {"blk": (5, 100)})]), None, CFG)
    table["name_key"] = "same"
    assert luck.by_name_key(table)["same"]["nba_id"] == 1
    assert luck.by_name_key(None) == {}


def test_z_text_shows_the_sign_and_a_dash_for_none():
    assert [luck.z_text(z) for z in (1.234, -0.4, 0.0, None, math.nan)] == ["+1.23", "−0.40", "0.00", "–", "–"]
