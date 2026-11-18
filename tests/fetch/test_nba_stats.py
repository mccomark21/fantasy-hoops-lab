import pandas as pd
import pytest

from fantasyhoops.fetch.nba_stats import get_table, merge_tables, nba_season


def adv():
    return pd.DataFrame(
        {
            "PLAYER_ID": [1, 2],
            "PLAYER_NAME": ["Dyson Daniels", "Derrick White Jr."],
            "NICKNAME": ["Dyson", "Derrick"],
            "TEAM_ID": [10, 20],
            "TEAM_ABBREVIATION": ["ATL", "BOS"],
            "AGE": [23.0, 32.0],
            "GP": [12, 13],
            "W": [7, 8],
            "L": [5, 5],
            "W_PCT": [0.58, 0.62],
            "USG_PCT": [0.18, 0.21],
            "USG_PCT_RANK": [200, 150],
            "sp_work_PACE": [101.0, 98.0],
        }
    )


def hustle():
    # Player 2 is missing: a player can be missing from one table.
    return pd.DataFrame(
        {
            "PLAYER_ID": [1, 3],
            "PLAYER_NAME": ["Dyson Daniels", "Alex Caruso"],
            "TEAM_ID": [10, 30],
            "TEAM_ABBREVIATION": ["ATL", "OKC"],
            "AGE": [23.0, 32.0],
            "G": [12, 11],
            "DEFLECTIONS": [6.0, 4.4],
        }
    )


def test_the_season_text_comes_from_the_espn_season():
    assert nba_season(2027) == "2026-27"
    assert nba_season(2100) == "2099-00"


def test_each_player_gets_one_row_with_prefixed_stat_columns():
    out = merge_tables({"adv": adv(), "hustle": hustle()})
    assert list(out.columns) == ["nba_id", "name", "name_key", "team", "gp", "adv_usg_pct", "hustle_deflections"]
    rows = out.set_index("nba_id")
    assert rows.loc[1, "hustle_deflections"] == 6.0
    assert rows.loc[2, "name_key"] == "derrick white"
    assert pd.isna(rows.loc[2, "hustle_deflections"])
    assert rows.loc[3, "team"] == "OKC"
    assert pd.isna(rows.loc[3, "gp"])


def test_a_request_that_fails_every_time_names_the_table():
    def failing():
        raise ConnectionError("timed out")

    with pytest.raises(RuntimeError, match="'hustle' failed 3 times"):
        get_table("hustle", failing, wait=0)


def test_a_request_that_fails_once_tries_again():
    answers = iter([ConnectionError("timed out"), "ok"])

    class Answer:
        def get_data_frames(self):
            return [hustle()]

    def flaky():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return Answer()

    assert len(get_table("hustle", flaky, wait=0)) == 2
