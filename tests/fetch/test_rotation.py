import csv
import json
from pathlib import Path

from fantasyhoops.fetch import rotation
from fantasyhoops.fetch.rotation import clock_seconds, finished_games, game_stints, minute_gaps, season_dates, update

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def play(seq, period, clock, kind="Jump Shot", ids=(), home=0, away=0):
    return {"sequenceNumber": str(seq), "type": {"text": kind}, "period": {"number": period},
            "clock": {"displayValue": clock}, "homeScore": home, "awayScore": away,
            "participants": [{"athlete": {"id": i}} for i in ids]}


def athlete(pid, starter, minutes):
    return {"athlete": {"id": pid, "displayName": pid.upper()}, "starter": starter,
            "didNotPlay": minutes == 0, "stats": [str(minutes)] if minutes else []}


def tiny_game():
    """A made-up game. Home team AAA (a1-a6), away team BBB (b1-b6). a6 subs for a1 in period 1 only."""
    box = [
        {"team": {"id": "1", "abbreviation": "AAA"}, "statistics": [{"names": ["MIN"], "athletes": [
            athlete("a1", True, 42), *(athlete(f"a{i}", True, 48) for i in range(2, 6)), athlete("a6", False, 6)]}]},
        {"team": {"id": "2", "abbreviation": "BBB"}, "statistics": [{"names": ["MIN"], "athletes": [
            *(athlete(f"b{i}", True, 48) for i in range(1, 6)), athlete("b6", False, 0)]}]},
    ]
    plays = [
        play(1, 1, "12:00", "Jumpball", ["a1", "b1"]),
        play(99, 1, "6:00", "Substitution", ["a6", "a1"]),  # ESPN added it late: a high sequenceNumber
        play(3, 1, "5:00", "Jump Shot", ["a2"], home=2),
        play(4, 1, "0.0", "End Period", home=2),
        # The coach puts a1 back between periods. ESPN logs it at 12:00 of period 2.
        play(5, 2, "12:00", "Substitution", ["a1", "a6"], home=2),
        play(6, 2, "30.5", "Technical Foul", ["b6"], home=2),  # b6 is on the bench
        play(7, 2, "10.0", "Jump Shot", ["b1", "b2"], home=2, away=3),
    ]
    return {"header": {"id": "900", "competitions": [{"date": "2026-10-21T23:30Z", "status": {"type": {"completed": True}},
                                                      "competitors": [{"homeAway": "home", "team": {"id": "1", "abbreviation": "AAA"}},
                                                                      {"homeAway": "away", "team": {"id": "2", "abbreviation": "BBB"}}]}]},
            "boxscore": {"players": box}, "plays": plays + [play(8, 4, "0.0", "End Game", home=2, away=3)]}


def seconds(stints, pid):
    return sum(s["out_sec"] - s["in_sec"] for s in stints if s["player_id"] == pid)


def test_clock_seconds():
    assert clock_seconds("8:11") == 491
    assert clock_seconds("12:00") == 720
    assert clock_seconds("45.3") == 45.3
    assert clock_seconds("0.0") == 0


def test_stints_follow_the_substitutions():
    stints, _, _ = game_stints(tiny_game())
    assert seconds(stints, "a1") == 360 + 3 * 720  # out at 6:00 of period 1, back for periods 2 to 4
    assert seconds(stints, "a6") == 360
    assert seconds(stints, "b5") == 4 * 720  # no play after period 1: he stays on the floor
    assert not [s for s in stints if s["player_id"] == "b6"]  # a technical foul does not put him on the floor


def test_no_stint_of_zero_seconds():
    stints, _, _ = game_stints(tiny_game())
    assert all(s["out_sec"] > s["in_sec"] for s in stints)
    assert [s["period"] for s in stints if s["player_id"] == "a6"] == [1]


def test_stint_rows_hold_the_game_and_the_score():
    stints, scores, _ = game_stints(tiny_game())
    a6 = next(s for s in stints if s["player_id"] == "a6")
    assert {k: a6[k] for k in ("game_id", "date", "team", "opponent", "player", "starter")} == {
        "game_id": "900", "date": "2026-10-21", "team": "AAA", "opponent": "BBB", "player": "A6", "starter": False}
    assert (a6["in_sec"], a6["out_sec"]) == (360, 720)
    assert (a6["in_team_score"], a6["in_opp_score"]) == (0, 0)
    assert (a6["out_team_score"], a6["out_opp_score"]) == (2, 0)
    b1_last = [s for s in stints if s["player_id"] == "b1"][-1]
    assert (b1_last["out_team_score"], b1_last["out_opp_score"]) == (3, 2)  # the away team sees its own score first
    assert scores == [{"game_id": "900", "sec": 420, "home_score": 2, "away_score": 0},
                      {"game_id": "900", "sec": 720 + 710, "home_score": 2, "away_score": 3}]


def test_minute_gaps_name_each_player_off_by_more_than_the_tolerance():
    game = tiny_game()
    game["boxscore"]["players"][0]["statistics"][0]["athletes"][5]["stats"] = ["9"]  # a6 played 6 minutes
    stints, _, box = game_stints(game)
    assert [g["player"] for g in minute_gaps(stints, box, 1.5)] == ["A6"]


def test_real_game_matches_the_box_score():
    """BOS @ DET, 2026-10-20 (ESPN event 401909088), trimmed to the fields that the script reads."""
    stints, scores, box = game_stints(load("summary_401909088.json"))
    played = {pid for pid, b in box.items() if b["minutes"] > 0}
    assert {s["player_id"] for s in stints} == played
    assert (len(box), len(played)) == (28, 22)  # 6 players did not play
    assert minute_gaps(stints, box, 1.5) == []
    assert all(s["out_sec"] > s["in_sec"] for s in stints)
    assert scores[-1]["home_score"] == 121 and scores[-1]["away_score"] == 113


def test_finished_games_keep_final_regular_season_games():
    board = load("scoreboard_20261020.json")
    board["events"].append({"id": "1", "season": {"year": 2027, "type": 1}, "status": {"type": {"completed": True}}})
    board["events"].append({"id": "2", "season": {"year": 2027, "type": 2}, "status": {"type": {"completed": False}}})
    assert finished_games(board, 2027) == ["401909088", "401909089", "401909090"]


def test_season_dates_stop_at_today():
    board = load("scoreboard_20261020.json")
    assert season_dates(board, "2026-10-20")[-2:] == ["20261016", "20261020"]
    assert season_dates(board, "2026-10-20", since="2026-10-16") == ["20261016", "20261020"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_update_reads_each_game_once(tmp_path, monkeypatch):
    monkeypatch.setattr(rotation, "load_config", lambda: {"league": {"espn_season": 2027}, "rotation": {"minute_tolerance": 1.5}})
    board = {"leagues": [{"calendar": ["2026-10-21T07:00Z"]}],
             "events": [{"id": "900", "season": {"year": 2027, "type": 2}, "status": {"type": {"completed": True}}}]}
    asked = []

    def get(url):
        asked.append(url)
        return board if "scoreboard" in url else tiny_game()

    log, scores = tmp_path / "rotation_log.csv", tmp_path / "rotation_scores.csv"
    first = update(get, today="2026-10-21", log=log, scores=scores)
    assert first["games"] == ["900"] and first["gaps"] == []
    assert sum("summary" in u for u in asked) == 1
    rows = read_csv(log)
    assert {r["game_id"] for r in rows} == {"900"} and len(read_csv(scores)) == 2

    asked.clear()
    second = update(get, today="2026-10-21", log=log, scores=scores)
    assert second["games"] == [] and not any("summary" in u for u in asked)
    assert len(read_csv(log)) == len(rows)


def test_logged_games_of_a_missing_log_is_empty(tmp_path):
    assert rotation.logged_games(tmp_path / "rotation_log.csv") == (set(), None)
