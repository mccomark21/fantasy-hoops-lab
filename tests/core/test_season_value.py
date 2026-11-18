from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.core import season_value
from fantasyhoops.core.season_value import SeasonLine, SeasonValues, line_val, season_lines

CFG = {
    "league": {"teams": 2, "roster_spots": 1},
    "weights": {"pts": 1.0, "reb": 0.5},
    "games": {"full_season": 82, "power": 1.25},
    "season_value": {"stale_days": 7},
}
# pg_value = (pts - 10) / 5 + 0.5 x (reb - 5) / 2.5
SCALE = pd.DataFrame({"pts": [10.0, 5.0], "reb": [5.0, 2.5]}, index=["mean", "std"])
OVERRIDES = pd.DataFrame(
    {
        "player_id": ["4", "5"],
        "name": ["Alexandre Sarr", "Nicolas Claxton"],
        "espn_name": ["Alex Sarr", "Nic Claxton"],
        "yahoo_name": ["Alex Sarr", "Nic Claxton"],
        "team": ["", ""],
    }
)


def projection(pid, first, last, games=70, pts=15.0, reb=5.0):
    """A projections row with pts and reb per game (all points from 2-point field goals)."""
    return {
        "player_id": pid,
        "first_name": first,
        "last_name": last,
        "games": games,
        "minutes": 30 * games,
        "field_goals": pts / 2 * games,
        "threes": 0,
        "free_throws": 0,
        "offensive_rebounds": 0,
        "defensive_rebounds": reb * games,
        "assists": 0,
        "steals": 0,
        "blocks": 0,
    }


def sample():
    """Players of a rest-of-season projections file. Full Season plays all 60 games of BOS. Half Games plays 30 of
    the 60 games of BOS. Four Games has 70 games, more than the 66 games of NY. Alex Sarr and Nic Claxton come from the
    name overrides. Hurt Five gets his team from data/rosters.csv. No Team has no team. No Games has 0 games."""
    projections = pd.DataFrame(
        [
            projection(1, "Full", "Season", games=60, pts=25.0),
            projection(2, "Half", "Games", games=30),
            projection(3, "Four", "Games", games=70),
            projection(4, "Alexandre", "Sarr", games=55),
            projection(5, "Nicolas", "Claxton", games=40),
            projection(6, "No", "Games", games=0),
            projection(7, "Hurt", "Five", games=12),
            projection(8, "No", "Team", games=50),
        ]
    )
    rosters = pd.DataFrame(
        {
            "espn_name": ["Full Season", "Half Games", "Four Games", "Alex Sarr", "Nic Claxton", "Hurt Five"],
            "team": ["BOS", "BOS", "NY", "WSH", "WSH", "NY"],
        }
    )
    remaining = {"BOS": 60, "NY": 66, "WSH": 64}
    return season_lines(projections, OVERRIDES, CFG, SCALE, rosters, remaining)


def test_the_per_game_value_is_the_value_of_the_projection():
    lines = sample()
    assert lines["full season"].pg_value == pytest.approx(3.0)  # (25 - 10) / 5
    assert lines["half games"].pg_value == pytest.approx(1.0)  # (15 - 10) / 5
    assert lines["full season"].games == 60


def test_the_games_share_is_the_projected_games_over_the_remaining_games_of_his_team():
    lines = sample()
    assert (lines["full season"].share, lines["full season"].team_games) == (pytest.approx(1.0), 60)
    assert lines["half games"].share == pytest.approx(30 / 60)
    assert lines["hurt five"].share == pytest.approx(12 / 66)
    assert lines["four games"].share == pytest.approx(1.0)  # 70 of 66 games: the share stops at 1


def test_a_player_with_no_team_gets_the_mean_remaining_games_of_the_teams():
    line = sample()["no team"]
    assert line.team_games == 0
    assert line.share == pytest.approx(50 / ((60 + 66 + 64) / 3))


def test_with_no_remaining_games_the_share_uses_the_full_season():
    projections = pd.DataFrame([projection(1, "Full", "Season", games=41)])
    line = season_lines(projections, OVERRIDES, CFG, SCALE, None, {})["full season"]
    assert line.share == pytest.approx(41 / 82)


def test_the_name_overrides_link_the_projection_to_the_yahoo_name_and_the_team():
    lines = sample()
    assert lines["alex sarr"].name == "Alex Sarr" and lines["alex sarr"].share == pytest.approx(55 / 64)
    assert lines["nic claxton"].team_games == 64  # his ESPN name (override) finds his team in data/rosters.csv
    assert "alexandre sarr" not in lines and "nicolas claxton" not in lines


def test_a_0_game_projection_has_no_line():
    assert "no games" not in sample()


def test_the_remaining_games_count_the_games_on_and_after_the_date():
    sched = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-19"]),
            "team": ["BOS", "BOS", "BOS", "NY"],
        }
    )
    assert season_value.remaining_games(sched, date(2026, 11, 18)) == {"BOS": 2, "NY": 1}


def test_val_is_above_the_replacement_with_the_games_factor_only_above_0():
    line = SeasonLine("A", 5, 2.0, 0.8)
    assert line_val(line, 1.0, 1.25) == pytest.approx(1.0 * 0.8**1.25)
    assert line_val(line, 3.0, 1.25) == pytest.approx(-1.0)  # no reward for missed games below replacement


def test_season_values_give_the_val_and_the_rank_of_each_line():
    lines = {
        "a": SeasonLine("A", 10, 2.0, 1.0),
        "b": SeasonLine("B", 10, 2.2, 0.5),  # a higher per-game value, but half of the games
        "c": SeasonLine("C", 10, 0.5, 1.0),
    }
    season = SeasonValues(lines, 1.0, 1.25)
    assert season.vals() == {"a": 1.0, "b": round(1.2 * 0.5**1.25, 2), "c": -0.5}
    assert season.ranks() == {"a": 1, "b": 2, "c": 3}
    assert season.val("nobody") is None
    assert SeasonValues(lines, None, 1.25).vals() == {} and SeasonValues(lines, None, 1.25).ranks() == {}


def test_the_replacement_is_the_line_at_rank_among_the_keys_or_after_the_pool():
    lines = {k: SeasonLine(k, 1, v, 1.0) for k, v in zip("abcde", [5.0, 4.0, 3.0, 2.0, 1.0])}
    assert season_value.replacement_of(lines, ["c", "d", "e", "x"], 2) == 2.0
    assert season_value.replacement_of(lines, ["c", "d"], 15) == 2.0  # fewer lines than rank: the last line
    assert season_value.replacement_of(lines, ["x"], 1) is None
    # The pool of CFG is 2 x 1 players. Rank 1 after the pool is the 3rd line.
    assert season_value.pool_replacement(lines, CFG, 1) == 3.0


def test_the_basis_line_names_the_date_of_the_projections_file(monkeypatch):
    monkeypatch.setattr(season_value, "latest_projections", lambda cfg: Path("data/Projections_2026-11-18.csv"))
    assert season_value.basis_text(CFG, date(2026, 11, 25)) == (
        "Val = the per-game value of the Basketball Monster projection of 2026-11-18."
    )


def test_the_basis_line_warns_when_the_projections_file_is_older_than_stale_days(monkeypatch):
    monkeypatch.setattr(season_value, "latest_projections", lambda cfg: Path("data/Projections_2026-11-18.csv"))
    warning = "Warning: the projections file is 8 days old. Download a new Basketball Monster export."
    assert season_value.stale_warning(CFG, date(2026, 11, 26)) == warning
    assert season_value.basis_text(CFG, date(2026, 11, 26)).endswith(f"2026-11-18. {warning}")
    assert season_value.stale_warning(CFG, date(2026, 11, 25)) is None  # 7 days: not older than stale_days


def test_with_no_projections_file_the_basis_line_has_no_date_and_no_warning(monkeypatch):
    def missing(cfg):
        raise FileNotFoundError("no file")

    monkeypatch.setattr(season_value, "latest_projections", missing)
    assert season_value.basis_text(CFG) == "Val = the per-game value of the Basketball Monster projection."
    assert season_value.stale_warning(CFG) is None


def test_with_no_projections_file_there_are_no_lines(monkeypatch):
    def missing(cfg):
        raise FileNotFoundError("no file")

    monkeypatch.setattr(season_value, "latest_projections", missing)
    assert season_value.read_season_lines(CFG) == {}
