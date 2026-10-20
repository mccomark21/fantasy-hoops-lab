import pandas as pd
import pytest

from fantasyhoops.adds.blend import blend_line, blended_options, recent_weight
from fantasyhoops.adds.readers import FreeAgent, Player
from fantasyhoops.adds.value import empty_slot_value

# A scale with mean 0 and std 1, so the value of a line is pts + reb.
CFG = {"weights": {"pts": 1.0, "reb": 1.0}}
SCALE = pd.DataFrame({"pts": [0.0, 1.0], "reb": [0.0, 1.0]}, index=["mean", "std"])
PROJECTED = {"pts": 10.0, "reb": 4.0}
RECENT = {"pts": 20.0, "reb": 8.0}


def agent(name="A", team="PHI", games=3.0, line=PROJECTED):
    return FreeAgent(Player(name, team, ("C",)), games, line)


def test_recent_weight_is_games_over_14_and_1_at_most():
    assert [recent_weight(g) for g in (0, 7, 14, 20)] == [0, 0.5, 1, 1]


def test_no_recent_games_gives_the_projected_line():
    assert blend_line(PROJECTED, {}, 0) == PROJECTED


def test_7_recent_games_give_50_percent_of_the_recent_line():
    assert blend_line(PROJECTED, RECENT, 7) == pytest.approx({"pts": 15.0, "reb": 6.0})


def test_no_projection_gives_the_recent_line():
    assert blend_line({}, RECENT, 3) == RECENT


def test_a_player_with_no_recent_games_has_blended_value_equal_to_projected_value():
    (o,) = blended_options([agent()], [agent(games=0, line={})], SCALE, CFG)
    assert (o.projected_value, o.recent_value, o.blended_value, o.value) == (14.0, None, 14.0, 14.0)


def test_blended_options_match_the_two_views_by_name_and_team():
    projected = [agent("A"), agent("B"), agent("A", team="BOS")]
    recent = [agent("B", games=7, line=RECENT), agent("A", team="BOS", games=14, line=RECENT)]
    a, b, a_bos = blended_options(projected, recent, SCALE, CFG)
    assert (a.recent_value, a.blended_value) == (None, 14.0)
    assert (b.projected_value, b.recent_value, b.blended_value) == pytest.approx((14.0, 28.0, 21.0))
    assert a_bos.blended_value == pytest.approx(28.0)


def test_a_player_with_no_projection_and_no_recent_games_has_no_value():
    (o,) = blended_options([agent(games=0, line={})], [], SCALE, CFG)
    assert (o.projected_value, o.recent_value, o.value) == (None, None, None)


def test_an_empty_slot_has_the_value_of_a_line_of_zeros():
    # Mean 10 and std 2 for pts, mean 4 and std 1 for reb: (0 - 10) / 2 + (0 - 4) / 1 = -9.
    scale = pd.DataFrame({"pts": [10.0, 2.0], "reb": [4.0, 1.0]}, index=["mean", "std"])
    assert empty_slot_value(CFG, scale) == pytest.approx(-9.0)
