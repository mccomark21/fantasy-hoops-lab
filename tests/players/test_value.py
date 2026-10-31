from datetime import date, timedelta

import pandas as pd
import pytest

from fantasyhoops.core import chart
from fantasyhoops.players import value
from fantasyhoops.players.data import Signal

LINE = {"pts": 12, "reb": 5, "ast": 3, "threes": 2, "stl": 0, "blk": 3}
# The game values of Ace Bailey in the approved sample, and the league spread of that sample.
ACE = [1.95, -3.37, 2.95, 5.56, -0.94]
ACE_SD = 3.3895259567910063
SETTINGS = {"window": 3, "band_min": 3, "flag_min": 5, "prior_games": 4, "band_sd": 2, "consistency_min_games": 10}


def games(n, line=LINE):
    return [
        value.Game(str(i), date(2026, 10, 20) + timedelta(i), "SA", i % 2 == 0, i == n - 1, dict(line))
        for i in range(n)
    ]


def test_a_dud_is_below_0_and_a_spike_is_at_the_top_30_level_or_more():
    assert [value.kind(v, 4.0) for v in (-0.01, 0, 3.99, 4.0, 7)] == ["dud", "normal", "normal", "spike", "spike"]
    assert value.kind(9, None) == "normal"  # no top-30 level: no spike


def test_the_block_counts_the_duds_and_the_spikes_of_fixture_games():
    block = value.value_block(games(5), ACE, ACE_SD, 4.0)
    assert (block["n"], block["duds"], block["spikes"]) == (5, 2, 1)
    assert [t["label"] for t in block["tips"]] == ["value", "value · dud", "value", "value · spike", "value · dud"]


def test_the_top_30_level_is_the_val_at_rank_30():
    vals = [float(v) for v in range(40)] + [None]
    assert value.spike_level(vals) == 10.0  # 39 is rank 1, 10 is rank 30
    assert value.spike_level([3.0, 1.0, None]) == 1.0  # fewer Vals: the last one
    assert value.spike_level([None]) is None


def test_the_band_mixes_his_spread_with_the_league_spread():
    tr = value.trend(ACE, ACE_SD)
    assert tr.roll[:2] == [None, None] and tr.roll[2] == pytest.approx(0.51)
    assert tr.mean == pytest.approx(1.23)
    # The sample: mean 1.23, band -2.73 to 5.19 (sd 3.43 = sqrt((48.06 + 4 x 3.39^2) / 8)).
    assert (tr.lo, tr.hi) == (pytest.approx(-2.729, abs=1e-3), pytest.approx(5.189, abs=1e-3))
    assert tr.exits == []


def test_a_point_outside_the_band_is_a_range_exit_from_5_games():
    values = [0, 0, 0, 0, 0, 9, 9, 9]
    tr = value.trend(values, 1.0)
    assert tr.exits == [7] and tr.roll[7] > tr.hi
    assert value.trend(values[:4] + [9], 1.0).exits == []  # the 3-game point stays in the band
    assert value.trend([0, 9, 9, 9], 1.0).exits == []  # 4 games: a band but no flag


def test_thin_data_gives_the_state_lines_of_design_md():
    assert value.trend([1, 2], 3.0).lo is None
    assert value.state(2, value.trend([1, 2], 3.0)) == (
        "<b>Too few games for a range:</b> 2 of 3. One game moves a rate 50 points."
    )
    four = value.trend([1, 2, 3, 4], 3.0)
    text = value.state(4, four)
    assert text.startswith("<b>Too few games for a flag:</b> 4 of 5. Range = mean ± ")
    assert text.endswith(" One game moves a rate 25 points.")
    assert value.state(5, value.trend(ACE, ACE_SD)) == "Range = mean ± 4.0, mostly the league prior at 5 games."
    assert "One game moves" not in value.state(12, value.trend(list(range(12)), 3.0))


def test_the_chart_has_the_marks_of_the_sample_and_passes_the_style_and_overlap_checks():
    block = value.value_block(games(5), ACE, ACE_SD, 4.0)
    svg = block["svg"]
    assert chart.style_problems(svg) == [] and chart.label_overlaps(svg) == []
    assert svg.count('class="lab-c-dud"') == 2 and svg.count('class="lab-c-spike"') == 1
    assert svg.count('class="lab-c-game"') == 2 and svg.count('class="lab-c-hero"') == 1
    assert svg.count('class="lab-c-hero-dot"') == 1 and svg.count('class="lab-c-band"') == 1
    assert svg.count('class="lab-c-ref"') == 2 and svg.count('class="lab-c-hit"') == 5
    texts = [t for _, t in chart.TEXT.findall(svg)]
    assert texts.count("dud") == 1 and texts.count("spike") == 1  # only the first dud and the first spike
    assert {"replacement", "top-30 level", "3-game 2.5", "normal range −2.7–5.2", "Oct 20", "Oct 24"} <= set(texts)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 30, 82])
def test_charts_of_each_size_pass_the_checks(n):
    values = [round(((i * 7) % 11) - 4 + (6 if i % 9 == 0 else 0), 2) for i in range(n)]
    tr = value.trend(values, 3.0)
    svg, tips = value.value_chart(games(n), values, tr, 4.0)
    assert chart.style_problems(svg) == [] and chart.label_overlaps(svg) == []
    assert len(tips) == n and svg.count('class="lab-c-hit"') == n
    assert ('class="lab-c-hero"' in svg) == (n >= 4)  # one hero point: the hero dot only
    assert ('class="lab-c-band"' in svg) == (n >= 3)


def test_a_range_exit_gets_its_label_on_a_clear_side():
    values = [0] * 8 + [-6] * 3 + [0] * 4
    tr = value.trend(values, 1.0)
    svg, _ = value.value_chart(games(15), values, tr, 4.0)
    assert tr.exits == [9, 10, 11]
    assert svg.count('<text class="lab-c-exit"') == 1 and "▼ out" in svg  # the other two have no clear side
    assert chart.label_overlaps(svg) == []


def test_the_tooltip_of_a_game_has_the_rows_of_design_md():
    tips = value.value_block(games(5), ACE, ACE_SD, 4.0)["tips"]
    assert tips[0] == {
        "ctx": "Oct 20 vs SA · start",
        "value": "+1.95",
        "label": "value",
        "rows": [["PTS · REB · AST", "12 · 5 · 3"], ["3PM · STL · BLK", "2 · 0 · 3"], ["3-game avg", "needs 3 games"]],
        "x": tips[0]["x"],
        "y0": tips[0]["y0"],
        "y1": tips[0]["y1"],
    }
    assert tips[4]["ctx"] == "Oct 24 vs SA · start · close game" and tips[4]["value"] == "−0.94"
    assert tips[4]["rows"][2] == ["3-game avg", "+2.52"]


def test_a_long_season_shows_a_date_under_some_games_only():
    svg, _ = value.value_chart(games(81), [1.0] * 81, value.trend([1.0] * 81, 1.0), 4.0)
    dates = [t for a, t in chart.TEXT.findall(svg) if 'text-anchor="middle"' in a]
    assert 0 < len(dates) < 81


def test_the_consistency_signal_needs_10_games_and_a_rate_of_40_percent():
    def record(n, duds, spikes, least=10):
        return {"value": {"n": n, "consistency_min": least, "duds": duds, "spikes": spikes}}

    assert value.consistency_signal(record(9, 9, 0)) is None  # under 10 games: no signal
    assert value.consistency_signal(record(10, 4, 0)) == Signal("Consistency", "value", False, "Duds: 4 of 10 games")
    assert value.consistency_signal(record(10, 1, 4)) == Signal("Consistency", "value", True, "Spikes: 4 of 10 games")
    assert value.consistency_signal(record(10, 3, 3)) is None
    assert value.consistency_signal(record(5, 2, 0, least=5)) == Signal(
        "Consistency", "value", False, "Duds: 2 of 5 games"
    )
    assert value.consistency_signal({"value": {"n": 9, "duds": 9, "spikes": 0}}) is None  # the default is 10
    assert value.consistency_signal({"value": {"n": 0, "empty": value.NO_VAL}}) is None
    assert value.consistency_signal({}) is None


def box_rows():
    base = {"team": "UTAH", "fgm": 0, "fga": 0, "fg3a": 0, "ftm": 0, "fta": 0, "oreb": 0, "dreb": 0, "tov": 0}
    rows = []
    for gid, day, opp, played in (("2", "2026-10-23", "NO", "True"), ("1", "2026-10-21", "MEM", "True")):
        rows.append(
            {
                **base,
                "game_id": gid,
                "date": day,
                "opponent": opp,
                "player_id": "9",
                "player": "Ace Bailey",
                "starter": "False",
                "played": played,
                **{col: 1 for col in value.BOX_COLUMNS.values()},
            }
        )
    rows.append({**rows[0], "game_id": "3", "date": "2026-10-25", "played": "False"})
    rows.append({**rows[0], "player_id": "8", "player": "Luguentz Dort"})
    return pd.DataFrame(rows)


def test_box_games_keep_the_played_games_by_date_with_the_yahoo_name():
    overrides = pd.DataFrame(
        [{"player_id": "1", "name": "Lu Dort", "espn_name": "Luguentz Dort", "yahoo_name": "Lu Dort", "team": "OKC"}]
    )
    found = value.box_games(box_rows(), {"2": True}, overrides)
    assert set(found) == {"ace bailey", "lu dort"}
    ace = found["ace bailey"]
    assert [g.game_id for g in ace] == ["1", "2"] and [g.close for g in ace] == [False, True]
    assert ace[0].opponent == "MEM" and ace[0].started is False and ace[0].line["threes"] == 1.0
    assert value.box_games(pd.DataFrame(), {}, overrides) == {}


def test_game_values_are_the_value_above_replacement():
    cats = ["pts", "reb", "ast", "threes", "stl", "blk"]
    scale = pd.DataFrame({c: [1.0, 1.0] for c in cats}, index=["mean", "std"])
    cfg = {"weights": dict.fromkeys(cats, 1.0)}
    found = value.game_values(games(2, dict.fromkeys(cats, 2.0)), scale, -1.0, cfg)
    assert found == [7.0, 7.0]  # 6 categories at z = 1, minus a replacement of -1


def test_attach_gives_each_record_a_block_or_an_empty_box_text():
    records = [
        {"slug": "ace-bailey", "name": "Ace Bailey", "val": 1.0},
        {"slug": "no-games", "name": "No Games", "val": 2.0},
    ]
    cats = ["pts", "reb", "ast", "threes", "stl", "blk"]
    scale = pd.DataFrame({c: [1.0, 1.0] for c in cats}, index=["mean", "std"])
    cfg = {"weights": dict.fromkeys(cats, 1.0), "players": {"value": SETTINGS}}
    overrides = pd.DataFrame(columns=["player_id", "name", "espn_name", "yahoo_name", "team"])
    meta = value.attach(records, {"ace bailey": games(3)}, overrides, scale, 0.0, cfg)
    assert records[0]["value"]["n"] == 3 and records[0]["value"]["svg"].startswith('<svg class="lab-chart"')
    assert records[1]["value"] == {"n": 0, "empty": value.NO_GAMES}
    assert meta["spike"] == 1.0 and meta["window"] == 3 and meta["flag_min"] == 5
    assert value.attach(records, {}, overrides, scale, None, cfg) is None
    assert records[0]["value"] == {"n": 0, "empty": value.NO_VAL}


def test_config_toml_holds_the_settings_of_the_value_quadrant():
    from fantasyhoops.core.common import load_config

    assert value.settings(load_config()) == value.DEFAULT == value.Settings(**SETTINGS)


def test_a_change_in_the_config_changes_the_band_and_the_flag():
    wide = value.Settings(**{**SETTINGS, "band_sd": 4})
    narrow = value.trend(ACE, ACE_SD)
    assert value.trend(ACE, ACE_SD, wide).hi - value.trend(ACE, ACE_SD, wide).lo == pytest.approx(
        2 * (narrow.hi - narrow.lo)
    )
    late = value.Settings(**{**SETTINGS, "window": 2, "band_min": 6, "flag_min": 6, "consistency_min_games": 6})
    tr = value.trend(ACE, ACE_SD, late)
    assert tr.roll[1] == pytest.approx((1.95 - 3.37) / 2) and tr.lo is None
    block = value.value_block(games(5), ACE, ACE_SD, 4.0, late)
    assert block["state"].startswith("<b>Too few games for a range:</b> 5 of 6.") and block["consistency_min"] == 6
    assert value.consistency_signal({"value": block}) is None  # 5 games: under 6
    early = value.value_block(games(5), ACE, ACE_SD, 4.0, value.Settings(**{**SETTINGS, "consistency_min_games": 5}))
    assert value.consistency_signal({"value": early}) == Signal("Consistency", "value", False, "Duds: 2 of 5 games")
