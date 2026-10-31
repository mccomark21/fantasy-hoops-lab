import copy
import math

import pandas as pd
import pytest

from fantasyhoops.core import common, profile
from fantasyhoops.core.common import load_config
from fantasyhoops.core.rotation import competitive_minutes, player_games
from fantasyhoops.players import data, role

ROLE = {"window": 3, "band_min": 3, "flag_min": 5, "prior_games": 4, "band_sd": 2}
ROT = {"close_margin": 5, "close_minutes": 5, "decided_sigma": 0.313, "decided_win_chance": 0.99}
CFG = {"players": {"role": ROLE}, "rotation": ROT}
# The minutes of Ace Bailey in his first 5 games (the approved sample) and a league spread of 5.37.
ACE = [24.3, 21.7, 29.2, 34.1, 39.5]
SPREAD = 5.366242966348352
UP = [20.0] * 8 + [40.0] * 3  # a minutes riser: the last rolling point (40.0) is above the band (15.75 to 35.15)
DOWN = [40.0] * 8 + [20.0] * 3
BACK = [30.0] * 6 + [12.0] * 3 + [30.0] * 3  # a dip below the band in game 9, then back in the band


def cfg(**role_settings):
    out = copy.deepcopy(CFG)
    out["players"]["role"].update(role_settings)
    return out


def rows(minutes, close=None, usg=None):
    """A table of player games for role_record(), one game each 2 days from 2026-10-21."""
    n = len(minutes)
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-10-21", periods=n, freq="2D"),
            "opponent": ["MEM"] * n,
            "started": [True] * n,
            "minutes": minutes,
            "close_game": close or [False] * n,
            "competitive_minutes": [m - 1 for m in minutes],
            "usg": usg or [20.0] * n,
        }
    )


# The settings


def test_config_holds_the_agent_defaults():
    assert role.settings(load_config()) == ROLE


def test_a_window_setting_changes_the_rolling_line_and_the_band():
    three = role.role_record(rows(ACE), SPREAD, CFG)
    two = role.role_record(rows(ACE), SPREAD, cfg(window=2))
    assert three["roll"] == [None, None, 25.07, 28.33, 34.27]
    assert two["roll"] == [None, 23.0, 25.45, 31.65, 36.8] and two["window"] == 2
    # A 2-game average has more noise, so the band is wider: the half width grows by the square root of 3 / 2.
    assert (two["hi"] - two["lo"]) / (three["hi"] - three["lo"]) == pytest.approx(math.sqrt(3 / 2), abs=1e-3)


def test_a_band_minimum_setting_changes_the_games_that_a_band_needs():
    assert role.role_record(rows(ACE[:2]), SPREAD, CFG)["lo"] is None
    assert role.role_record(rows(ACE[:2]), SPREAD, cfg(band_min=2))["lo"] is not None


def test_a_flag_minimum_setting_changes_the_games_that_a_flag_needs():
    assert role.role_record(rows(UP), SPREAD, CFG)["exits"] == [(10, "up")]
    assert role.role_record(rows(UP), SPREAD, cfg(flag_min=12))["exits"] == []


# The band and the flag on a fixture series


def test_the_band_mixes_his_spread_with_the_league_spread_as_in_the_sample():
    """The approved sample: Ace Bailey 22.41 to 37.11 (mean 29.76, spread 6.36), Quickley 23.83 to 33.22."""
    assert role.band(ACE, SPREAD, CFG) == pytest.approx((22.4118, 37.1082), abs=1e-3)
    assert role.band([28.2, 29.1, 28.2, 28.6], SPREAD, CFG) == pytest.approx((23.8298, 33.2202), abs=1e-3)


def test_the_league_spread_pools_the_players_with_2_or_more_games():
    # 1 and 3: squares 2, 1 dof. 10, 10, 13: squares 6, 2 dof. A player with 1 game adds nothing.
    assert role.league_spread([[1, 3], [10, 10, 13], [50]]) == pytest.approx(math.sqrt(8 / 3))
    assert role.league_spread([[50]]) is None


def test_a_rolling_point_outside_the_band_is_a_range_exit():
    found = role.role_record(rows(BACK), SPREAD, CFG)
    low, high = found["lo"], found["hi"]
    assert (low, high) == pytest.approx((16.84, 34.16), abs=0.01)
    assert found["roll"][8] == 12.0 and found["exits"] == [(8, "down")]
    assert all(low <= v <= high for i, v in enumerate(found["roll"]) if v is not None and i != 8)
    assert role.role_record(rows(UP), SPREAD, CFG)["exits"] == [(10, "up")]


def test_under_3_games_no_band_and_the_state_line_of_thin_data():
    found = role.role_record(rows(ACE[:2]), SPREAD, CFG)
    assert found["lo"] is None and found["hi"] is None and found["exits"] == []
    assert found["roll"] == [None, None]
    assert found["state"] == ["Too few games for a range:", "2 of 3."]


@pytest.mark.parametrize("games", [3, 4])
def test_with_3_or_4_games_the_band_shows_but_no_flag(games):
    far = [10.0, 10.0, 40.0, 40.0][:games]  # the last rolling point is far from the mean
    found = role.role_record(rows(far), 0.1, CFG)
    assert found["lo"] is not None and found["exits"] == []
    assert found["state"][0] == "Too few games for a flag:"
    assert found["state"][1].startswith(f"{games} of 5. Range = mean ± ")
    assert role.band_exit({"role": found}) is None


def test_from_5_games_the_state_line_gives_the_range():
    assert role.role_record(rows(ACE), SPREAD, CFG)["state"] == [
        "",
        "Range = mean ± 7.3, mostly the league prior at 5 games.",
    ]
    assert role.role_record(rows(ACE * 2), SPREAD, CFG)["state"][1].endswith("at 10 games.")


# The signal


def test_a_range_exit_of_the_last_game_gives_a_minutes_signal_on_the_role_quadrant():
    up = role.role_record(rows(UP), SPREAD, CFG)
    signal = role.band_exit({"role": up})
    assert (up["lo"], up["hi"]) == pytest.approx((15.75, 35.15), abs=0.01)
    text = f"3-game 40.0 min, above the range {up['lo']:.1f}–{up['hi']:.1f}"
    assert signal == data.Signal("Minutes", "role", True, text)
    down = role.role_record(rows(DOWN), SPREAD, CFG)
    assert role.band_exit({"role": down}).up is False
    assert "below the range" in role.band_exit({"role": down}).text
    # An exit in an earlier game only, or no role: no signal.
    back = role.role_record(rows(BACK), SPREAD, CFG)
    assert back["exits"] and role.band_exit({"role": back}) is None
    assert role.band_exit({"role": None}) is None


def test_the_band_exit_is_a_signal_rule_of_the_player_records():
    assert role.band_exit in data.SIGNAL_RULES
    up = role.role_record(rows(UP), SPREAD, CFG)
    owned = {"fa five": data.Owned("Fa Five", "NY", ("C",), "Team", False)}
    records = data.player_records(owned, {}, {}, {}, extras={"fa five": {"role": up}})
    assert records[0]["role"] is up
    assert [s["kind"] for s in records[0]["signals"]] == ["Minutes"]
    assert records[0]["signals"][0]["quadrant"] == "role" and "role" in profile.QUADRANT_KEYS


# The labels agree with #183 (usage) and #184 (competitive minutes)


def stint(game, player, start, end, starter=False):
    return {
        "game_id": game,
        "date": pd.Timestamp("2026-10-21") + pd.Timedelta(days=int(game)),
        "team": "HHH",
        "opponent": "AAA",
        "player_id": player,
        "player": {"p1": "Fixture One", "p2": "Fixture Two"}[player],
        "starter": starter,
        "period": min(4, int(start // 720) + 1),
        "in_sec": start,
        "out_sec": end,
    }


def fixture_games():
    """Game 1: a blowout, decided from early in the 4th quarter. Game 2: a close game. Player p1 plays both."""
    stints = pd.DataFrame(
        [
            stint("1", "p1", 0, 2880, True),
            stint("1", "p2", 0, 2160, True),
            stint("2", "p1", 0, 2400, True),
            stint("2", "p2", 2400, 2880),
        ]
    )
    scores = pd.DataFrame(
        [
            {"game_id": "1", "sec": 100, "home_score": 30, "away_score": 0},
            {"game_id": "1", "sec": 2000, "home_score": 70, "away_score": 30},
            {"game_id": "2", "sec": 100, "home_score": 2, "away_score": 0},
            {"game_id": "2", "sec": 2800, "home_score": 90, "away_score": 88},
        ]
    )
    box = pd.DataFrame(
        [
            {"game_id": "1", "player_id": "p1", "usg": 24.4},
            {"game_id": "2", "player_id": "p1", "usg": 18.1},
            {"game_id": "1", "player_id": "p2", "usg": 15.0},
        ]
    )
    return stints, scores, box


def test_the_usage_and_close_game_labels_agree_with_the_box_scores_and_the_competitive_minutes():
    stints, scores, box = fixture_games()
    table = role.game_table(stints, scores, box, CFG)
    p1 = table[table.player_id == "p1"]
    comp = competitive_minutes(stints, scores, CFG).set_index(["game_id", "player_id"]).competitive_minutes
    games = player_games(stints, scores, CFG).set_index(["game_id", "player_id"])
    found = role.role_record(p1, 5.0, CFG)
    assert [g["comp"] for g in found["games"]] == [comp["1", "p1"], comp["2", "p1"]]
    assert found["games"][0]["comp"] < found["games"][0]["min"]  # game 1 was decided
    assert [g["usg"] for g in found["games"]] == [24.4, 18.1]
    assert found["usg"] == pytest.approx((24.4 + 18.1) / 2, abs=0.06)
    assert found["usg_last"] is None  # 2 games: too few for a 3-game usage
    # Close-game minutes: the mean minutes of his close games (player_games() close_game), and of the other games.
    assert games.close_game.to_dict() == {("1", "p1"): False, ("1", "p2"): False, ("2", "p1"): True, ("2", "p2"): True}
    assert (found["close_n"], found["close_min"], found["other_min"]) == (1, 40.0, 48.0)
    # A game with no box row has no usage.
    p2 = role.role_record(table[table.player_id == "p2"], 5.0, CFG)
    assert [g["usg"] for g in p2["games"]] == [15.0, None]


def test_the_roles_have_the_yahoo_name_key_of_an_override():
    stints, scores, box = fixture_games()
    overrides = pd.DataFrame(
        [{"player_id": "", "name": "", "espn_name": "Fixture One", "yahoo_name": "Yahoo One", "team": ""}]
    )
    found = role.roles(role.game_table(stints, scores, box, CFG), overrides, CFG)
    assert set(found) == {"yahoo one", "fixture two"}
    assert len(found["yahoo one"]["games"]) == 2


def test_with_no_data_files_there_are_no_roles(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "DATA", tmp_path)
    assert role.read_roles(CFG, data.read_overrides()) == {}


def test_the_roles_of_the_saved_data():
    """The real data files, when they exist: each role has a game for each logged game of the player."""
    if not (common.DATA / "rotation_log.csv").exists() or not (common.DATA / "rotation_scores.csv").exists():
        pytest.skip("no rotation log in data/")
    found = role.read_roles(load_config(), data.read_overrides())
    assert found
    for r in found.values():
        assert len(r["games"]) == len(r["roll"]) and all(g["min"] is not None for g in r["games"])


def test_the_band_has_no_minutes_below_0():
    found = role.role_record(rows([1.0, 2.0, 0.5, 1.5, 1.0]), SPREAD, CFG)
    assert found["lo"] == 0.0 and found["hi"] > 0
