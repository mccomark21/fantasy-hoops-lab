import pandas as pd
import pytest

from fantasyhoops.core.common import load_config
from fantasyhoops.core.role_flags import INCONSISTENT, NEW, REGULAR, closer_flag, flag, role_flags, starter_flag

# The approved rule of #75.
SETTINGS = {"window_games": 10, "min_games": 5, "new_games": 3, "close_window": 8, "min_close_games": 4,
            "new_closes": 2, "regular_share": 0.7, "some_share": 0.2}


def pattern(text):
    """'S S - S' -> [True, True, False, True], oldest first. S = a start (or a close), - = none."""
    return [c == "S" for c in text.split()]


def starter(text):
    return flag(pattern(text), SETTINGS["window_games"], SETTINGS["min_games"], SETTINGS["new_games"],
                SETTINGS["regular_share"], SETTINGS["some_share"])


@pytest.mark.parametrize("text, expected", [
    ("S S S S S S S S S S", REGULAR),
    ("S S - S S S - S S -", REGULAR),
    ("- - - - - - - S S S", NEW),
    ("- S - - S - S - - S", INCONSISTENT),
    ("- - - - S - - - - -", None),
    ("- - S S S", NEW),
    ("- S S", None),
])
def test_the_starter_flag_of_the_sample_patterns(text, expected):
    assert starter(text) == expected


def test_the_window_holds_only_the_last_games():
    # 10 old starts, then 10 games with 1 start: only the last 10 games count.
    assert starter("S " * 10 + "- - - - S - - - - -") is None


def test_new_needs_fewer_than_half_of_the_earlier_games():
    # The last 3 are starts. The earlier 7 hold 4 starts (more than half): 7/10 is Regular, not New.
    assert starter("S S S S - - - S S S") == REGULAR
    # The earlier 7 hold 3 starts (fewer than half): New.
    assert starter("S S S - - - - S S S") == NEW


def test_the_shares_are_inclusive():
    assert starter("S S - - - - - - - -") == INCONSISTENT  # 2/10 = 20%
    assert starter("S S S S S S S - - -") == REGULAR  # 7/10 = 70%
    assert starter("S S S S S S - - - -") == INCONSISTENT  # 6/10


def closer(text):
    return flag(pattern(text), SETTINGS["close_window"], SETTINGS["min_close_games"], SETTINGS["new_closes"],
                SETTINGS["regular_share"], SETTINGS["some_share"])


@pytest.mark.parametrize("text, expected", [
    ("S S S S S S - S", REGULAR),
    ("- - - - - - S S", NEW),
    ("- S - - S - - -", INCONSISTENT),
    ("- - - - - - - -", None),
    ("- - S S", NEW),
    ("S S S", None),
])
def test_the_closer_flag_uses_its_own_window_and_minimum(text, expected):
    assert closer(text) == expected


# The log frames: player_games() of core/rotation.py. Joe (PHI) plays g1 to g6.
def games_frame():
    rows = []
    for n in range(1, 9):
        game, day = f"g{n}", pd.Timestamp(f"2026-11-{n:02d}")
        close = n in (1, 2, 3, 5, 6, 7, 8)
        joe = n <= 6
        if joe:
            rows.append({"game_id": game, "date": day, "team": "PHI", "player_id": "1", "started": n >= 4,
                         "close_game": close, "closed": close and n in (5, 6)})
        rows.append({"game_id": game, "date": day, "team": "PHI", "player_id": "9", "started": True,
                     "close_game": close, "closed": close})
    return pd.DataFrame(rows).sample(frac=1, random_state=1)  # the order of the rows must not matter


def test_the_starter_flag_uses_his_games_in_date_order():
    # Joe: - - - S S S over 6 games: New.
    assert starter_flag(games_frame(), "1", SETTINGS) == NEW


def test_the_closer_flag_counts_a_close_game_that_he_did_not_play_as_not_closed():
    # The close games of PHI: g1 g2 g3 g5 g6 g7 g8. Joe closes g5 and g6. He does not play g7 and g8.
    # So his closes, oldest first: - - - S S - -. 2/7 is Inconsistent, and the last 2 are not closes.
    assert closer_flag(games_frame(), "1", "PHI", SETTINGS) == INCONSISTENT


def test_the_closer_flag_uses_the_close_games_of_his_current_team():
    assert closer_flag(games_frame(), "1", "BOS", SETTINGS) is None  # BOS has no close games in the log


def test_role_flags_gives_both_flags():
    assert role_flags(games_frame(), "9", "PHI", SETTINGS) == (REGULAR, REGULAR)


def test_too_few_games_give_no_flag():
    few = games_frame().query("date < '2026-11-04'")
    assert role_flags(few, "1", "PHI", SETTINGS) == (None, None)


def test_the_settings_are_in_config():
    assert load_config()["adds"]["flags"] == SETTINGS
