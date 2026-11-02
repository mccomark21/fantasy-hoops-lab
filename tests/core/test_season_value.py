import pandas as pd
import pytest

from fantasyhoops.core import season_value
from fantasyhoops.core.season_value import SeasonLine, SeasonValues, line_val, season_lines

CFG = {
    "league": {"teams": 2, "roster_spots": 1},
    "weights": {"pts": 1.0, "reb": 0.5},
    "games": {"full_season": 82, "power": 1.25},
    "season_value": {"blend_games": 10},
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


def box_rows(player, team, games, pts=25, reb=5, team_games=None, start=0, pid=None):
    """The box-score rows of a player: games played, then the games of his team that he missed (played False)."""
    rows = []
    for i in range(team_games or games):
        played = i < games
        rows.append(
            {
                "game_id": f"{team}{start + i}",
                "date": f"2026-10-{20 + i:02d}",
                "team": team,
                "player_id": pid or player,
                "player": player,
                "played": played,
                "pts": pts if played else None,
                "reb": reb if played else None,
                "ast": 0,
                "fg3m": 0,
                "blk": 0,
                "stl": 0,
            }
        )
    return rows


def sample():
    """A 0-game player, a player with 12 games (more than blend_games), a player with 4 of 5 team games, the two
    players of the name overrides, a player with games and no projection, and two 0-game players on teams with 5 and
    12 games. Hurt Five gets his team from data/rosters.csv, Hurt Twelve from his box-score rows with played False."""
    projections = pd.DataFrame(
        [
            projection(1, "Zero", "Games"),
            projection(2, "Full", "Season"),
            projection(3, "Four", "Games"),
            projection(4, "Alexandre", "Sarr"),
            projection(5, "Nicolas", "Claxton"),
            projection(6, "No", "Games", games=0),
            projection(7, "Hurt", "Five"),
            projection(8, "Hurt", "Twelve"),
        ]
    )
    box = pd.DataFrame(
        [
            *box_rows("Full Season", "BOS", 12),
            *box_rows("Four Games", "NYK", 4, team_games=5),
            *box_rows("Alex Sarr", "WSH", 10),
            *box_rows("Box Only", "MIA", 3, pts=20),
            *box_rows("Hurt Twelve", "BOS", 0, team_games=12),
        ]
    )
    rosters = pd.DataFrame({"espn_name": ["Hurt Five", "Nic Claxton"], "team": ["NYK", "WSH"]})
    return season_lines(projections, box, OVERRIDES, CFG, SCALE, rosters)


def test_a_0_game_player_gets_the_projection_value():
    line = sample()["zero games"]
    assert (line.games, line.weight) == (0, 0.0)
    assert line.pg_value == pytest.approx(1.0)  # (15 - 10) / 5
    assert line.share == pytest.approx(70 / 82)  # no NBA team: t = 0


def test_a_0_game_player_loses_games_share_as_his_team_plays():
    # Owner decision of 2026-11-01 (half penalty): the share blends by the team games, t = min(team games, 10) / 10.
    # The per-game value keeps the blend by his own games, so it stays the projection value.
    lines = sample()
    five, twelve = lines["hurt five"], lines["hurt twelve"]
    assert (five.team_games, five.pg_value) == (5, pytest.approx(1.0))
    assert five.share == pytest.approx(0.5 * 0 / 5 + 0.5 * 70 / 82)
    assert (twelve.team_games, twelve.pg_value) == (12, pytest.approx(1.0))
    assert twelve.share == pytest.approx(0.0)  # t = 1: 0 of 12 games
    assert line_val(twelve, 0.5, 1.25) == pytest.approx(0.0) and line_val(five, 0.5, 1.25) > 0
    assert line_val(twelve, 2.0, 1.25) == pytest.approx(-1.0)  # below replacement: no games factor


def test_a_player_with_blend_games_or_more_gets_the_season_to_date_value():
    line = sample()["full season"]
    assert (line.games, line.weight) == (12, 1.0)
    assert line.pg_value == pytest.approx(3.0)  # (25 - 10) / 5
    assert line.share == pytest.approx(1.0)  # 12 of the 12 games of his team


def test_a_player_between_gets_the_blend_of_the_value_and_of_the_games_share():
    line = sample()["four games"]
    assert (line.games, line.weight) == (4, 0.4)
    assert line.pg_value == pytest.approx(0.4 * 3.0 + 0.6 * 1.0)
    assert line.share == pytest.approx(0.5 * 4 / 5 + 0.5 * 70 / 82)  # t = 5 team games / 10


def test_the_name_overrides_link_the_projection_and_the_box_scores_to_the_yahoo_name():
    lines = sample()
    assert lines["alex sarr"].name == "Alex Sarr" and lines["alex sarr"].games == 10
    assert lines["alex sarr"].pg_value == pytest.approx(3.0)
    assert lines["nic claxton"].name == "Nic Claxton" and lines["nic claxton"].games == 0
    assert lines["nic claxton"].team_games == 10  # his ESPN name (override) finds his team in data/rosters.csv
    assert "alexandre sarr" not in lines and "nicolas claxton" not in lines


def test_a_player_with_no_projection_gets_the_season_to_date_value_and_a_0_game_projection_has_no_line():
    lines = sample()
    assert lines["box only"].pg_value == pytest.approx(2.0) and lines["box only"].weight == 1.0
    assert "no games" not in lines


def test_val_is_above_the_replacement_with_the_games_factor_only_above_0():
    line = SeasonLine("A", 5, 0.5, 2.0, 0.8)
    assert line_val(line, 1.0, 1.25) == pytest.approx(1.0 * 0.8**1.25)
    assert line_val(line, 3.0, 1.25) == pytest.approx(-1.0)  # no reward for missed games below replacement


def test_season_values_give_the_val_and_the_rank_of_each_line():
    lines = {
        "a": SeasonLine("A", 10, 1.0, 2.0, 1.0),
        "b": SeasonLine("B", 10, 1.0, 2.2, 0.5),  # a higher per-game value, but half of the games
        "c": SeasonLine("C", 10, 1.0, 0.5, 1.0),
    }
    season = SeasonValues(lines, 1.0, 1.25)
    assert season.vals() == {"a": 1.0, "b": round(1.2 * 0.5**1.25, 2), "c": -0.5}
    assert season.ranks() == {"a": 1, "b": 2, "c": 3}
    assert season.val("nobody") is None
    assert SeasonValues(lines, None, 1.25).vals() == {} and SeasonValues(lines, None, 1.25).ranks() == {}


def test_the_replacement_is_the_line_at_rank_among_the_keys_or_after_the_pool():
    lines = {k: SeasonLine(k, 1, 0.1, v, 1.0) for k, v in zip("abcde", [5.0, 4.0, 3.0, 2.0, 1.0])}
    assert season_value.replacement_of(lines, ["c", "d", "e", "x"], 2) == 2.0
    assert season_value.replacement_of(lines, ["c", "d"], 15) == 2.0  # fewer lines than rank: the last line
    assert season_value.replacement_of(lines, ["x"], 1) is None
    # The pool of CFG is 2 x 1 players. Rank 1 after the pool is the 3rd line.
    assert season_value.pool_replacement(lines, CFG, 1) == 3.0


def test_the_basis_line_names_blend_games():
    assert season_value.basis_text(CFG) == "Val = season value to date, blended with the projection until 10 games."


def test_with_no_projections_file_there_are_no_lines(monkeypatch):
    def missing(cfg):
        raise FileNotFoundError("no file")

    monkeypatch.setattr(season_value, "latest_projections", missing)
    assert season_value.read_season_lines(CFG) == {}
