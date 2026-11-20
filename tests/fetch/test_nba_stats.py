from datetime import date

import pandas as pd
import pytest

from fantasyhoops.fetch import nba_stats
from fantasyhoops.fetch.nba_stats import add_chances, get_table, merge_tables, nba_season, output_paths


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


def five_tables():
    """The 5 tables of one season for 2 players, with only the columns that add_chances() needs."""
    ids = {
        "PLAYER_ID": [1, 2],
        "PLAYER_NAME": ["Dyson Daniels", "Victor Wembanyama"],
        "TEAM_ABBREVIATION": ["ATL", "SAS"],
    }
    return {
        "base": pd.DataFrame(
            {
                **ids,
                "GP": [16, 15],
                "STL": [40, 18],
                "BLK": [8, 62],
                "AST": [90, 53],
                "REB": [100, 191],
                "FG3M": [10, 30],
                "FG3A": [40, 100],
            }
        ),
        "hustle": pd.DataFrame(
            {**ids, "G": [16, 15], "DEFLECTIONS": [95.0, 45.0], "CONTESTED_SHOTS_2PT": [60.0, 139.0]}
        ),
        "pass": pd.DataFrame({**ids, "GP": [16, 15], "POTENTIAL_AST": [160, 79]}),
        "reb": pd.DataFrame({**ids, "GP": [16, 15], "REB_CHANCES": [180.0, 352.0]}),
        "touch": pd.DataFrame({**ids, "GP": [16, 15], "TOUCHES": [900, 800]}),
    }


def test_the_makes_and_chances_columns_follow_gp():
    out = add_chances(merge_tables(five_tables()), "2026-27")
    assert list(out.columns[:16]) == [
        "nba_id", "name", "name_key", "team", "gp", "season",
        "stl_makes", "stl_chances", "blk_makes", "blk_chances", "ast_makes", "ast_chances",
        "reb_makes", "reb_chances", "threes_makes", "threes_chances",
    ]  # fmt: skip
    wemby = out.set_index("nba_id").loc[2]
    assert (wemby["blk_makes"], wemby["blk_chances"]) == (62, 139.0)
    assert (wemby["threes_makes"], wemby["threes_chances"]) == (30, 100)
    assert wemby["season"] == "2026-27"


def test_a_missing_chances_column_raises():
    frames = five_tables()
    frames["pass"] = frames["pass"].drop(columns="POTENTIAL_AST")
    with pytest.raises(ValueError, match="pass_potential_ast"):
        add_chances(merge_tables(frames), "2026-27")


def test_only_the_current_season_gets_a_dated_copy(tmp_path):
    day = date(2026, 11, 20)
    assert output_paths("2026-27", "2026-27", tmp_path / "a.csv", day) == (
        tmp_path / "a.csv",
        tmp_path / "nba_stats" / "2026-11-20.csv",
    )
    assert output_paths("2025-26", "2026-27", today=day) == (nba_stats.DATA / "nba_stats_2025-26.csv", None)
    assert output_paths("2026-27", "2026-27", today=day)[0] == nba_stats.OUT_FILE


def test_a_run_writes_the_file_and_the_dated_copy(tmp_path):
    frames = five_tables()
    season = nba_season(nba_stats.load_config()["league"]["espn_season"])
    out = tmp_path / "nba_stats.csv"
    code = nba_stats.main(["--out", str(out)], get=lambda label, request: frames[label], today=date(2026, 11, 20))
    assert code == 0
    written = pd.read_csv(out)
    assert len(written) == 2 and written["season"].eq(season).all()
    assert (tmp_path / "nba_stats" / "2026-11-20.csv").read_text() == out.read_text()


def test_a_failed_request_keeps_the_last_good_file(tmp_path, capsys):
    out = tmp_path / "nba_stats.csv"
    out.write_text("old")

    def failing(label, request):
        raise RuntimeError(f"The NBA.com table '{label}' failed 3 times: timed out")

    assert nba_stats.main(["--out", str(out)], get=failing) == 1
    assert out.read_text() == "old"
    assert not (tmp_path / "nba_stats").exists()
    assert "No file written. The NBA.com table 'base' failed 3 times" in capsys.readouterr().out
