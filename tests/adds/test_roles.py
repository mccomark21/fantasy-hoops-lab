from datetime import date

import pandas as pd
import pytest

from fantasyhoops.adds import roles
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.roles import player_roles, read_roles
from fantasyhoops.core.common import load_config
from fantasyhoops.core.rotation import LOG, SCORES

FLAGS = {"window_games": 10, "min_games": 5, "new_games": 3, "close_window": 8, "min_close_games": 4,
         "new_closes": 2, "regular_share": 0.7, "some_share": 0.2}
CFG = {"rotation": {"close_margin": 5, "close_minutes": 5}, "adds": {"minutes_rise": 4.0, "flags": FLAGS}}
END = 2880  # the end of the fourth quarter, in seconds
TODAY = date(2026, 11, 20)


def stint(game, day, team, opp, pid, name, start, end, starter=False):
    return {"game_id": game, "date": pd.Timestamp(day), "team": team, "opponent": opp, "player_id": pid,
            "player": name, "starter": starter, "period": min(4, int(start // 720) + 1), "in_sec": start,
            "out_sec": end}


def team_game(game, day, minutes, starter=False, closes=False):
    """A game of PHI against BOS. Joe Fa plays minutes. If closes, he is on the floor at the end."""
    sec = minutes * 60
    start = END - sec if closes else 0
    # The log has one stint for each period. One stint of 4 periods is enough here, but its period must be 4.
    return [stint(game, day, "PHI", "BOS", "1", "Joe Fa", start, start + sec, starter),
            {**stint(game, day, "PHI", "BOS", "9", "Other Guy", 0, END, True), "period": 4},
            {**stint(game, day, "BOS", "PHI", "8", "Bos Guy", 0, END, True), "period": 4}]


def score(game, margin):
    """The score rows of a game: PHI (home) leads by margin from the first minute to the end."""
    return [{"game_id": game, "sec": sec, "home_score": 100 + margin, "away_score": 100} for sec in (60, END - 10)]


# Joe Fa: 2 old games at 10 minutes, then 5 games from Nov 8. He starts and closes g5 and g6.
# g5 (3 points) and g7 (2 points) are close games. g6 (20 points) is a blowout.
GAMES = [("g1", "2026-10-25", 10, False, False), ("g2", "2026-10-28", 10, False, False),
         ("g3", "2026-11-08", 12, False, False), ("g4", "2026-11-10", 14, False, False),
         ("g5", "2026-11-14", 30, True, True), ("g6", "2026-11-16", 32, True, True),
         ("g7", "2026-11-18", 34, True, False)]
MARGINS = {"g1": 20, "g2": 20, "g3": 20, "g4": 20, "g5": 3, "g6": 20, "g7": 2}


def log(games=GAMES, margins=MARGINS):
    stints = pd.DataFrame([s for g in games for s in team_game(*g)])
    scores = pd.DataFrame([row for g, m in margins.items() for row in score(g, m)])
    return stints, scores


def role(name="Joe Fa", team="PHI", today=TODAY, cfg=CFG, overrides=None):
    stints, scores = log()
    return player_roles([Player(name, team, ("SF",))], stints, scores, cfg, today, overrides).get((name, team))


def test_the_minutes_of_the_last_5_games_and_of_the_last_14_days():
    r = role()
    # The last 5 games: g3 to g7. The last 14 days (Nov 6 to Nov 19): g3 to g7 too.
    assert r.minutes_last5 == pytest.approx(24.4)
    assert r.minutes_14d == pytest.approx(24.4)
    assert r.games == 5


def test_the_last_14_days_end_yesterday_and_the_last_5_games_can_be_older():
    # On Nov 26, the last 14 days (Nov 12 to Nov 25) hold g5, g6 and g7 only.
    r = role(today=date(2026, 11, 26))
    assert r.games == 3
    assert r.minutes_14d == pytest.approx(32.0)
    assert r.minutes_last5 == pytest.approx(24.4)
    assert r.change == pytest.approx(24.4 - 32.0)
    assert not r.rise


def test_a_large_rise_of_the_minutes_gets_the_mark_and_the_threshold_is_a_setting():
    # 5 games at 10 minutes from Nov 6, then 5 games at 20 minutes from Nov 14. On Nov 20, the last 14 days
    # (Nov 6 to Nov 19) hold all 10 games: 15 minutes. The last 5 games: 20 minutes. The change: +5.
    games = [(f"o{n}", f"2026-11-{n + 6:02d}", 10, False, False) for n in range(5)]
    games += [(f"n{n}", f"2026-11-{n + 14:02d}", 20, False, False) for n in range(5)]
    stints, scores = log(games, {g[0]: 20 for g in games})
    players = [Player("Joe Fa", "PHI", ("SF",))]
    r = player_roles(players, stints, scores, CFG, TODAY)[("Joe Fa", "PHI")]
    assert (r.minutes_last5, r.minutes_14d, r.change) == (pytest.approx(20.0), pytest.approx(15.0), pytest.approx(5.0))
    assert r.rise
    high = {**CFG, "adds": {**CFG["adds"], "minutes_rise": 6.0}}
    assert not player_roles(players, stints, scores, high, TODAY)[("Joe Fa", "PHI")].rise


def test_the_starts_in_the_recent_games():
    r = role()
    assert (r.starts, r.games) == (3, 5)


def test_the_closes_in_the_close_games_of_his_team():
    r = role()
    # Close games in the last 14 days: g5 (3 points) and g7 (2 points). g6 is a blowout, so his close there
    # does not count. He closes g5, not g7.
    assert (r.closes, r.close_games) == (1, 2)


def test_the_role_has_the_starter_flag_and_the_closer_flag():
    r = role()
    # Starts in his 7 games, oldest first: - - - - S S S. So he is a new starter (core/role_flags.py).
    # PHI has 2 close games (g5 and g7), fewer than min_close_games: no closer flag.
    assert (r.starter, r.closer) == ("New", None)


def test_the_flags_count_games_before_today_only():
    # On Nov 18, the log holds g1 to g6 before today: - - - - S S. 2/6 is Inconsistent.
    assert role(today=date(2026, 11, 18)).starter == "Inconsistent"


def test_a_game_with_a_large_margin_is_not_a_close_game():
    stints, scores = log(margins={**MARGINS, "g5": 15, "g7": 15})
    r = player_roles([Player("Joe Fa", "PHI", ("SF",))], stints, scores, CFG, TODAY)[("Joe Fa", "PHI")]
    assert (r.closes, r.close_games) == (0, 0)


def test_a_player_who_is_not_in_the_log_has_no_role():
    assert role(name="Nobody Here") is None


def test_the_names_match_after_name_key_and_the_overrides():
    assert role(name="Joe Fa Jr.") is not None
    overrides = pd.DataFrame({"player_id": ["5"], "name": ["Joseph Fa"], "espn_name": ["Joe Fa"],
                              "yahoo_name": ["Joey Fa"], "team": [""]})
    assert role(name="Joey Fa") is None
    assert role(name="Joey Fa", overrides=overrides) is not None


def test_two_players_with_the_same_name_match_by_team():
    stints, scores = log()
    other = stints[stints.player_id == "8"].assign(player_id="7", player="Joe Fa", team="BOS")
    stints = pd.concat([stints, other])
    out = player_roles([Player("Joe Fa", "BOS", ("SF",))], stints, scores, CFG, TODAY)
    assert out[("Joe Fa", "BOS")].starts == 5  # the BOS player starts all his games


def test_two_players_with_the_same_name_and_none_on_his_team_give_no_role():
    stints, scores = log()
    other = stints[stints.player_id == "8"].assign(player_id="7", player="Joe Fa", team="BOS")
    stints = pd.concat([stints, other])
    assert player_roles([Player("Joe Fa", "MIA", ("SF",))], stints, scores, CFG, TODAY) == {}


def test_one_player_with_the_name_on_another_team_keeps_his_role():
    # A player who changed teams: the name has only one ESPN player, so the match is not in doubt.
    assert role(team="MIA") is not None


def test_read_roles_gives_nothing_with_no_log(monkeypatch, tmp_path):
    monkeypatch.setattr(roles, "LOG", tmp_path / "missing.csv")
    assert read_roles([Player("Joe Fa", "PHI", ("SF",))], CFG, TODAY) == {}


def test_read_roles_reads_the_real_log():
    if not LOG.exists() or not SCORES.exists():
        pytest.skip("data/rotation_log.csv or data/rotation_scores.csv is missing")
    stints = pd.read_csv(LOG, dtype={"player_id": str}, parse_dates=["date"])
    row = stints.iloc[0]
    today = (stints.date.max() + pd.Timedelta(days=1)).date()
    out = read_roles([Player(row.player, row.team, ("SF",))], load_config(), today)
    assert out[(row.player, row.team)].games >= 1
