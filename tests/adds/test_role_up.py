from datetime import date

import pandas as pd

from fantasyhoops.adds import role_up as role
from fantasyhoops.adds.planner import Option
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.role_up import Absence, absences, mark_role_ups, with_positions

CFG = {"adds": {"role_up": {"starter_games": 5, "days": 7, "games": 3}}}
TODAY = date(2026, 11, 10)
# BOS plays on these days. The last BOS game in the log is on Nov 9.
BOS_DAYS = ["2026-11-01", "2026-11-03", "2026-11-05", "2026-11-07", "2026-11-09"]


def team_games(team="BOS", days=BOS_DAYS):
    return pd.DataFrame({"game_id": [f"{team}{d}" for d in days], "date": pd.to_datetime(days), "team": team,
                         "opponent": "NY", "close_game": False})


def player_games(name, days, started, team="BOS"):
    """The games of one player. started: True or False for each game."""
    return pd.DataFrame({"game_id": [f"{team}{d}" for d in days], "date": pd.to_datetime(days), "team": team,
                         "opponent": "NY", "player_id": name.lower(), "player": name, "started": started,
                         "minutes": 30.0, "close_game": False, "closed": False})


def find(pgames, tgames=None, today=TODAY, cfg=CFG):
    return absences(pd.concat(pgames), team_games() if tgames is None else tgames, today, cfg)


def test_a_starter_who_missed_the_last_games_of_his_team_is_absent():
    # He started the first 3 BOS games. Then he missed the games of Nov 7 and Nov 9.
    found = find([player_games("Star Wing", BOS_DAYS[:3], [True] * 3)])
    assert found == [Absence("Star Wing", "BOS", date(2026, 11, 7), 2)]


def test_a_player_who_played_the_last_game_of_his_team_is_not_absent():
    assert find([player_games("Star Wing", BOS_DAYS, [True] * 5)]) == []


def test_a_bench_player_who_is_absent_is_not_a_starter():
    # He started 1 of his 3 games. A starter starts more than half of his last starter_games games.
    assert find([player_games("Bench Guy", BOS_DAYS[:3], [False, True, False])]) == []


def test_the_starter_test_uses_only_his_last_starter_games_games():
    cfg = {"adds": {"role_up": {"starter_games": 2, "days": 7, "games": 3}}}
    # He came off the bench, then started his last 2 games.
    found = find([player_games("New Starter", BOS_DAYS[:4], [False, False, True, True])], cfg=cfg)
    assert [a.name for a in found] == ["New Starter"]


def test_an_absence_that_started_before_the_window_gets_no_mark():
    # The first missed game is Nov 3. On Nov 10, the window starts on today - 7 days = Nov 3, so Nov 3 is in the
    # window. On Nov 11, the window starts on Nov 4. games = 10, so the 4 missed games do not end the mark.
    pgames = [player_games("Star Wing", BOS_DAYS[:1], [True])]
    cfg = {"adds": {"role_up": {"starter_games": 5, "days": 7, "games": 10}}}
    assert [a.first_missed for a in find(pgames, today=date(2026, 11, 10), cfg=cfg)] == [date(2026, 11, 3)]
    assert find(pgames, today=date(2026, 11, 11), cfg=cfg) == []


def test_the_mark_stays_for_games_missed_games_only():
    # He missed 3 games: Nov 5, Nov 7 and Nov 9. With games = 2, the mark is gone.
    pgames = [player_games("Star Wing", BOS_DAYS[:2], [True, True])]
    assert [a.missed for a in find(pgames)] == [3]
    cfg = {"adds": {"role_up": {"starter_games": 5, "days": 7, "games": 2}}}
    assert find(pgames, cfg=cfg) == []


def test_the_games_of_other_teams_do_not_count_as_missed_games():
    tgames = pd.concat([team_games(), team_games("NY", ["2026-11-08"])])
    assert find([player_games("Star Wing", BOS_DAYS, [True] * 5)], tgames) == []


def test_with_positions_gives_each_absent_starter_his_yahoo_positions():
    yahoo = pd.DataFrame({"yahoo_id": [1, 2], "name": ["Star Wing", "Alex Sarr"], "team": ["BOS", "WAS"],
                          "positions": ["SF,PF", "PF,C"], "status": "", "yahoo_rank": [1, 2], "pct_drafted": 100,
                          "yahoo_cost": 1.0, "yahoo_value": 1, "adp": 1.0})
    rosters = pd.DataFrame({"espn_name": ["Star Wing", "Alexandre Sarr"], "team": ["BOS", "WSH"]})
    # The override gives the Yahoo name of a player whose ESPN name does not match.
    overrides = pd.DataFrame({"player_id": ["9"], "name": ["Alexandre Sarr"], "espn_name": ["Alexandre Sarr"],
                              "yahoo_name": ["Alex Sarr"], "team": [""]})
    found = [Absence("Star Wing", "BOS", date(2026, 11, 7), 2), Absence("Alexandre Sarr", "WSH", date(2026, 11, 7), 1),
             Absence("Nobody Known", "BOS", date(2026, 11, 7), 1)]
    assert [a.positions for a in with_positions(found, yahoo, rosters, overrides)] == [("SF", "PF"), ("PF", "C"), ()]


def option(name, team, positions):
    return Option(Player(name, team, positions), -2.0)


ABSENT = [Absence("Star Wing", "BOS", date(2026, 11, 7), 2, ("SF", "PF"))]


def test_a_free_agent_at_the_position_of_an_absent_teammate_gets_the_mark():
    marked = mark_role_ups([option("Bos Forward", "BOS", ("PF", "C"))], ABSENT)
    assert marked[0].role_up == ("Star Wing",)


def test_a_free_agent_with_no_absent_teammate_at_his_position_has_no_mark():
    options = [option("Bos Guard", "BOS", ("PG", "SG")), option("Ny Forward", "NY", ("SF",))]
    assert [o.role_up for o in mark_role_ups(options, ABSENT)] == [(), ()]


def test_the_absent_starter_does_not_mark_himself():
    assert mark_role_ups([option("Star Wing", "BOS", ("SF",))], ABSENT)[0].role_up == ()


def test_read_absences_gives_none_without_the_rotation_log(monkeypatch, tmp_path):
    monkeypatch.setattr(role, "LOG", tmp_path / "rotation_log.csv")
    assert role.read_absences(TODAY, CFG) == []


def test_read_absences_warns_and_gives_none_without_the_yahoo_files(monkeypatch, tmp_path, capsys):
    # The rotation log exists, but data/yahoo_players.csv does not. The planner must not stop.
    for name in ("rotation_log.csv", "rotation_scores.csv", "rosters.csv", "name_overrides.csv"):
        (tmp_path / name).write_text("", encoding="utf-8")
    monkeypatch.setattr(role, "LOG", tmp_path / "rotation_log.csv")
    monkeypatch.setattr(role, "SCORES", tmp_path / "rotation_scores.csv")
    monkeypatch.setattr(role, "IDENTITY_FILES", [tmp_path / n for n in
                                                 ("yahoo_players.csv", "rosters.csv", "name_overrides.csv")])
    assert role.read_absences(TODAY, CFG) == []
    out = capsys.readouterr().out
    assert out.count("Warning") == 1 and "yahoo_players.csv" in out
