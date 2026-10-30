import pandas as pd
import pytest

from fantasyhoops.adds import name_check as nc
from fantasyhoops.adds.name_check import Mismatch, check_names, report
from fantasyhoops.core.common import load_config

PROJECTIONS = pd.DataFrame(
    {
        "player_id": [1, 2, 3, 4, 5, 6],
        "name": ["Exact Match", "Lu Dort", "Alexandre Sarr", "No Team", "Zero Games", "Walter Clayton"],
        "games": [70, 73, 60, 40, 0, 64],
    }
)

ESPN = ["Exact Match", "Luguentz Dort", "Alex Sarr", "Tony Bradley", "Zero Games", "Walter Clayton Jr.", "Exact Match"]


def overrides(rows=()):
    """data/name_overrides.csv with the rows (player_id, name, espn_name)."""
    cols = ["player_id", "name", "espn_name", "yahoo_name", "team"]
    return pd.DataFrame([(pid, name, espn, "", "") for pid, name, espn in rows], columns=cols, dtype=str)


SARR = ("3", "Alexandre Sarr", "Alex Sarr")


def test_a_projected_player_and_an_espn_name_with_his_last_name_are_a_mismatch():
    result = check_names(PROJECTIONS, ESPN, overrides([SARR]))
    assert result.mismatches == [Mismatch("2", "Lu Dort", "Luguentz Dort")]


def test_an_override_espn_name_removes_the_mismatch():
    result = check_names(PROJECTIONS, ESPN, overrides([SARR, ("2", "Lu Dort", "Luguentz Dort")]))
    assert result.mismatches == []
    assert "Luguentz Dort" not in result.no_projection


def test_a_blank_espn_name_in_an_override_row_has_no_effect():
    # The Dort row of 2026-10-29 had a yahoo_name but no espn_name.
    result = check_names(PROJECTIONS, ESPN, overrides([SARR, ("2", "Lu Dort", "")]))
    assert result.mismatches == [Mismatch("2", "Lu Dort", "Luguentz Dort")]


def test_an_espn_name_with_no_projection_row_is_not_a_mismatch():
    result = check_names(PROJECTIONS, ESPN, overrides([SARR]))
    assert result.no_projection == ["Tony Bradley"]


def test_a_projected_player_with_no_espn_name_and_no_candidate_is_listed_apart():
    result = check_names(PROJECTIONS, ESPN, overrides([SARR]))
    assert result.no_espn == ["No Team"]


def test_a_projection_row_with_0_games_matches_but_is_not_checked():
    result = check_names(PROJECTIONS, ESPN, overrides([SARR]))
    assert "Zero Games" not in result.no_projection + result.no_espn


def test_names_match_after_name_key():
    # "Walter Clayton Jr." and "Walter Clayton" have the same key.
    result = check_names(PROJECTIONS, ESPN, overrides([SARR]))
    assert "Walter Clayton" not in result.no_espn


def test_without_the_override_the_projection_name_does_not_match():
    result = check_names(PROJECTIONS, ESPN, overrides())
    assert Mismatch("3", "Alexandre Sarr", "Alex Sarr") in result.mismatches


def test_the_report_gives_each_list_with_its_count():
    lines = report(check_names(PROJECTIONS, ESPN, overrides([SARR])))
    assert lines == [
        "Mismatches (1). Put the ESPN name in espn_name of data/name_overrides.csv:",
        "  Lu Dort (player_id 2): Luguentz Dort",
        "Projected players with no ESPN name (1):",
        "  No Team",
        "ESPN names with no projection row (1). These are not mismatches:",
        "  Tony Bradley",
    ]


def test_the_local_data_has_no_name_mismatch():
    """The check of #181 on the files in data/. It skips when a file is missing."""
    cfg = load_config()
    try:
        projections = nc.read_projections(cfg)
    except FileNotFoundError:
        pytest.skip("no projections file in data/")
    if not (nc.OVERRIDES.exists() and nc.LOG.exists() and nc.ROSTERS.exists()):
        pytest.skip("data/name_overrides.csv, data/rotation_log.csv or data/rosters.csv is missing")
    result = check_names(projections, nc.read_espn_names(), nc.read_overrides())
    assert result.mismatches == [], "\n".join(report(result))
