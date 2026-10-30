import pandas as pd
import pytest

from fantasyhoops.core.common import load_config
from fantasyhoops.core.rotation import (
    LOG,
    SCORES,
    close_games,
    competitive_minutes,
    decided_spans,
    lead_needed,
    period_bounds,
    player_games,
    read_log,
    read_scores,
    team_games,
)

CFG = {"rotation": {"close_margin": 5, "close_minutes": 5}}
END = 2880  # the end of the fourth quarter, in seconds
WINDOW = END - 300  # 5:00 left in the fourth quarter


def stint(game, team, opp, player, start, end, starter=False, period=None):
    return {
        "game_id": game,
        "date": pd.Timestamp("2026-10-21"),
        "team": team,
        "opponent": opp,
        "player_id": player,
        "player": player.upper(),
        "starter": starter,
        "period": period or min(4, int(start // 720) + 1),
        "in_sec": start,
        "out_sec": end,
    }


def game(game_id, last=END):
    """A game of HHH (home) against AAA. h1 starts and plays to the end. h2 enters for the last 2 minutes."""
    return [
        stint(game_id, "HHH", "AAA", "h1", 0, last, starter=True),
        stint(game_id, "HHH", "AAA", "h2", last - 120, last),
        stint(game_id, "HHH", "AAA", "h3", 0, last - 120, starter=True),
        stint(game_id, "AAA", "HHH", "a1", 0, last, starter=True),
    ]


def scores(game_id, rows):
    return pd.DataFrame([{"game_id": game_id, "sec": s, "home_score": h, "away_score": a} for s, h, a in rows])


def is_close(score_rows, last=END):
    return bool(close_games(pd.DataFrame(game("1", last)), scores("1", score_rows), CFG).close.iloc[0])


def test_period_bounds():
    assert period_bounds(1) == (0, 720)
    assert period_bounds(4) == (2160, 720)
    assert period_bounds(5) == (2880, 300)
    assert period_bounds(6) == (3180, 300)


def test_a_game_with_a_large_margin_is_not_a_close_game():
    assert not is_close([(100, 20, 0), (END - 10, 20, 2)])


def test_a_margin_of_5_in_the_window_makes_a_close_game():
    assert is_close([(100, 10, 0), (WINDOW + 60, 10, 5), (END - 10, 14, 5)])


def test_the_margin_at_the_start_of_the_window_counts():
    assert is_close([(100, 3, 0), (END - 10, 13, 0)])  # 3 points at 5:00 left, then a run


def test_a_close_margin_before_the_window_does_not_count():
    assert not is_close([(100, 3, 0), (WINDOW - 1, 9, 0), (END - 10, 11, 0)])


def test_the_settings_change_the_definition():
    rows = [(100, 7, 0)]
    assert not is_close(rows)
    assert close_games(
        pd.DataFrame(game("1")), scores("1", rows), {"rotation": {"close_margin": 7, "close_minutes": 5}}
    ).close.all()


def test_overtime_is_a_close_game():
    # 20 points up in overtime, but the score was tied at the end of the fourth quarter.
    stints = pd.DataFrame(game("1", END + 300)).assign(period=lambda s: s.period.where(s.out_sec <= END, 5))
    rows = [(END - 1, 100, 100), (END + 290, 120, 100)]
    assert close_games(stints, scores("1", rows), CFG).close.all()


def test_player_games_give_starts_minutes_and_closes():
    stints = pd.DataFrame(game("1") + game("2"))
    rows = pd.concat([scores("1", [(END - 10, 100, 98)]), scores("2", [(100, 30, 0), (END - 10, 120, 90)])])
    pg = player_games(stints, rows, CFG).set_index(["game_id", "player_id"])
    assert (pg.loc[("1", "h1"), "started"], pg.loc[("1", "h1"), "minutes"]) == (True, 48.0)
    assert (pg.loc[("1", "h2"), "started"], pg.loc[("1", "h2"), "minutes"]) == (False, 2.0)
    assert pg.loc[("1", "h2"), "closed"] and pg.loc[("1", "a1"), "closed"]
    assert not pg.loc[("1", "h3"), "closed"]  # he left 2 minutes before the end
    assert pg.loc[("1", "h1"), "close_game"] and not pg.loc[("2", "h1"), "close_game"]
    assert not pg.xs("2").closed.any()  # no closes in a blowout


def test_team_games_count_the_close_games():
    stints = pd.DataFrame(game("1") + game("2"))
    rows = pd.concat([scores("1", [(END - 10, 100, 98)]), scores("2", [(100, 30, 0)])])
    tg = team_games(stints, rows, CFG)
    assert len(tg) == 4
    assert tg.groupby("team").close_game.sum().to_dict() == {"AAA": 1, "HHH": 1}


def test_config_has_the_close_game_settings():
    assert load_config()["rotation"] == {
        "close_margin": 5,
        "close_minutes": 5,
        "minute_tolerance": 1.5,
        "decided_sigma": 0.313,
        "decided_win_chance": 0.99,
    }


DECIDED = {"rotation": {"decided_sigma": 0.313, "decided_win_chance": 0.99}}


@pytest.mark.parametrize(("sec_left", "lead"), [(1440, 28), (720, 20), (360, 14)])
def test_lead_needed_grows_with_the_square_root_of_the_time_left(sec_left, lead):
    # The start of the third quarter, 12:00 left and 6:00 left.
    assert lead_needed(sec_left, load_config()) == pytest.approx(lead, abs=0.6)


def test_the_settings_change_the_lead_needed():
    low = {"rotation": {"decided_sigma": 0.251, "decided_win_chance": 0.99}}
    assert lead_needed(1440, low) == pytest.approx(22, abs=0.6)
    assert lead_needed(1440, {"rotation": {"decided_sigma": 0.313, "decided_win_chance": 0.9}}) < 28


def test_a_game_is_decided_when_the_lead_needed_falls_to_the_lead():
    # 15 up at 12:00 left (2160) and no more scores: the lead needed falls to 15 at about 7:04 left.
    (span,) = decided_spans(scores("1", [(2160, 15, 0)]), END, DECIDED)
    assert span == (pytest.approx(END - (15 / lead_needed(1, DECIDED)) ** 2), END)
    assert lead_needed(END - span[0], DECIDED) == pytest.approx(15)
    # 20 up at 12:00 left is more than the lead needed (about 19.5), so the game is decided at once.
    assert decided_spans(scores("1", [(2160, 20, 0)]), END, DECIDED) == [(2160.0, END)]


def test_a_comeback_makes_the_game_not_decided_again():
    rows = [(1500, 30, 0), (2000, 30, 25), (END - 10, 31, 25)]
    spans = decided_spans(scores("1", rows), END, DECIDED)
    assert spans[0] == (1500.0, 2000.0)  # 30 up with 23:00 left is decided
    assert spans[1][0] > 2000  # 5 up is decided only near the end
    assert spans[1][1] == END


def test_a_tie_at_the_end_of_regulation_is_not_decided():
    rows = [(END - 1, 100, 100), (END + 290, 110, 100)]
    spans = decided_spans(scores("1", rows), END + 300, DECIDED)
    assert len(spans) == 1 and spans[0][0] >= END + 290  # only the last seconds of overtime


def test_competitive_minutes_leave_out_the_minutes_after_the_decided_point():
    # HHH leads by 30 from 24:00 left (1440). The lead needed then is about 28, so the game is decided at 1440.
    stints = pd.DataFrame(
        [
            stint("1", "HHH", "AAA", "star", 0, 2160, starter=True),  # 36 minutes, 12 of them after the decided point
            stint("1", "HHH", "AAA", "bench", 2160, END),  # 12 minutes, all after the decided point
            stint("1", "HHH", "AAA", "early", 0, 1200),  # 20 minutes, all before
        ]
    )
    rows = scores("1", [(600, 10, 0), (1440, 30, 0)])
    cm = competitive_minutes(stints, rows, DECIDED).set_index("player_id").competitive_minutes
    assert cm.to_dict() == {"bench": 0.0, "early": 20.0, "star": 24.0}


def test_a_close_game_keeps_all_its_minutes():
    stints = pd.DataFrame(game("1"))
    cm = competitive_minutes(stints, scores("1", [(1000, 10, 8), (END - 1, 100, 99)]), DECIDED)
    pg = player_games(stints, scores("1", [(1000, 10, 8)]), CFG).merge(cm, on=["game_id", "player_id"])
    # A lead of 2 is decided only in the last 8 seconds.
    assert (pg.minutes - pg.competitive_minutes).abs().max() <= 0.15


def test_read_the_saved_log():
    if not (LOG.exists() and SCORES.exists()):
        pytest.skip("data/rotation_log.csv is not downloaded")
    stints, score_rows = read_log(), read_scores()
    assert (stints.out_sec > stints.in_sec).all()
    pg = player_games(stints, score_rows, load_config())
    assert pg.groupby(["game_id", "team"]).started.sum().eq(5).all()


def test_competitive_minutes_of_the_saved_log():
    if not (LOG.exists() and SCORES.exists()):
        pytest.skip("data/rotation_log.csv is not downloaded")
    stints, score_rows = read_log(), read_scores()
    cfg = load_config()
    pg = player_games(stints, score_rows, cfg).merge(
        competitive_minutes(stints, score_rows, cfg), on=["game_id", "player_id"], how="left"
    )
    assert pg.competitive_minutes.notna().all()
    assert (pg.competitive_minutes >= 0).all() and (pg.competitive_minutes <= pg.minutes).all()
