import csv
import json
from pathlib import Path

from fantasyhoops.fetch import rotation
from fantasyhoops.fetch.rotation import clock_seconds, finished_games, game_stints, minute_gaps, season_dates, update

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def play(seq, period, clock, kind="Jump Shot", ids=(), home=0, away=0):
    return {
        "sequenceNumber": str(seq),
        "type": {"text": kind},
        "period": {"number": period},
        "clock": {"displayValue": clock},
        "homeScore": home,
        "awayScore": away,
        "participants": [{"athlete": {"id": i}} for i in ids],
    }


def athlete(pid, starter, minutes):
    return {
        "athlete": {"id": pid, "displayName": pid.upper()},
        "starter": starter,
        "didNotPlay": minutes == 0,
        "stats": [str(minutes)] if minutes else [],
    }


def tiny_game():
    """A made-up game. Home team AAA (a1-a6), away team BBB (b1-b6). a6 subs for a1 in period 1 only."""
    box = [
        {
            "team": {"id": "1", "abbreviation": "AAA"},
            "statistics": [
                {
                    "names": ["MIN"],
                    "athletes": [
                        athlete("a1", True, 42),
                        *(athlete(f"a{i}", True, 48) for i in range(2, 6)),
                        athlete("a6", False, 6),
                    ],
                }
            ],
        },
        {
            "team": {"id": "2", "abbreviation": "BBB"},
            "statistics": [
                {
                    "names": ["MIN"],
                    "athletes": [*(athlete(f"b{i}", True, 48) for i in range(1, 6)), athlete("b6", False, 0)],
                }
            ],
        },
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
    return {
        "header": {
            "id": "900",
            "competitions": [
                {
                    "date": "2026-10-21T23:30Z",
                    "status": {"type": {"completed": True}},
                    "competitors": [
                        {"homeAway": "home", "team": {"id": "1", "abbreviation": "AAA"}},
                        {"homeAway": "away", "team": {"id": "2", "abbreviation": "BBB"}},
                    ],
                }
            ],
        },
        "boxscore": {"players": box},
        "plays": plays + [play(8, 4, "0.0", "End Game", home=2, away=3)],
    }


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
        "game_id": "900",
        "date": "2026-10-21",
        "team": "AAA",
        "opponent": "BBB",
        "player": "A6",
        "starter": False,
    }
    assert (a6["in_sec"], a6["out_sec"]) == (360, 720)
    assert (a6["in_team_score"], a6["in_opp_score"]) == (0, 0)
    assert (a6["out_team_score"], a6["out_opp_score"]) == (2, 0)
    b1_last = [s for s in stints if s["player_id"] == "b1"][-1]
    assert (b1_last["out_team_score"], b1_last["out_opp_score"]) == (3, 2)  # the away team sees its own score first
    assert scores == [
        {"game_id": "900", "sec": 420, "home_score": 2, "away_score": 0},
        {"game_id": "900", "sec": 720 + 710, "home_score": 2, "away_score": 3},
    ]


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


def test_a_substitution_of_a_player_on_the_floor_does_not_take_the_other_player_off():
    """SA @ DAL, 2026-10-26 (ESPN event 401909858), trimmed to the fields that the script reads.

    ESPN logs "Daniel Gafford enters the game for Naji Marshall" at 9:14 of period 1, with Gafford on the floor
    since the tip. Marshall plays on until 3:09. The old code took him off at 9:14: 14.8 minutes, box score 21.
    """
    stints, _, box = game_stints(load("summary_401909858.json"))
    marshall = next(pid for pid, b in box.items() if b["player"] == "Naji Marshall")
    assert round(seconds(stints, marshall) / 60, 1) == 20.9
    assert [(s["in_sec"], s["out_sec"]) for s in stints if s["player_id"] == marshall][0] == (0, 531)
    assert minute_gaps(stints, box, 0.5) == []


def sub(seq, clock, pid_in, pid_out):
    return play(seq, 1, clock, "Substitution", [pid_in, pid_out])


def period_1(stints, pid):
    return [(s["in_sec"], s["out_sec"]) for s in stints if s["player_id"] == pid and s["period"] == 1]


def game_with_period_1(plays):
    """tiny_game(), with these plays in period 1 in place of its own."""
    game = tiny_game()
    game["plays"] = [play(1, 1, "12:00", "Jumpball", ["a1", "b1"]), *plays, play(4, 1, "0.0", "End Period")]
    game["plays"] += [play(5, 2, "11:00", "Jump Shot", ["a1"]), play(8, 4, "0.0", "End Game")]
    return game


def test_a_second_copy_of_a_substitution_moves_it_to_the_later_time():
    """ESPN can log a substitution twice, the first copy at a wrong time (game 401909872, period 3)."""
    stints, _, _ = game_stints(game_with_period_1([sub(90, "6:00", "a6", "a1"), sub(10, "4:00", "a6", "a1")]))
    assert period_1(stints, "a1") == [(0, 480)]
    assert period_1(stints, "a6") == [(480, 720)]


def test_a_moved_substitution_keeps_the_player_it_replaced_on_the_floor():
    """ESPN can give the wrong player out in the first copy (game 401909868, period 3)."""
    stints, _, _ = game_stints(game_with_period_1([sub(90, "6:00", "a6", "a1"), sub(10, "4:00", "a6", "a2")]))
    assert period_1(stints, "a1") == [(0, 720)]
    assert period_1(stints, "a2") == [(0, 480)]
    assert period_1(stints, "a6") == [(480, 720)]


def test_a_substitution_for_a_player_off_the_floor_takes_off_his_replacement():
    """ESPN can give the wrong player out (game 401909891, period 3). The player who replaced him goes out."""
    game = game_with_period_1([sub(10, "6:00", "a6", "a1"), sub(11, "4:00", "a7", "a1")])
    game["boxscore"]["players"][0]["statistics"][0]["athletes"].append(athlete("a7", False, 4))
    stints, _, _ = game_stints(game)
    assert period_1(stints, "a6") == [(360, 480)]
    assert period_1(stints, "a7") == [(480, 720)]
    on_floor = sum(s["out_sec"] - s["in_sec"] for s in stints if s["team"] == "AAA" and s["period"] == 1)
    assert on_floor == 5 * 720


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
    monkeypatch.setattr(
        rotation, "load_config", lambda: {"league": {"espn_season": 2027}, "rotation": {"minute_tolerance": 1.5}}
    )
    board = {
        "leagues": [{"calendar": ["2026-10-21T07:00Z"]}],
        "events": [{"id": "900", "season": {"year": 2027, "type": 2}, "status": {"type": {"completed": True}}}],
    }
    asked = []

    def get(url):
        asked.append(url)
        return board if "scoreboard" in url else tiny_game()

    log, scores, box = tmp_path / "rotation_log.csv", tmp_path / "rotation_scores.csv", tmp_path / "box_scores.csv"
    first = update(get, today="2026-10-21", log=log, scores=scores, box_scores=box)
    assert first["games"] == ["900"] and first["gaps"] == []
    assert sum("summary" in u for u in asked) == 1
    rows = read_csv(log)
    assert {r["game_id"] for r in rows} == {"900"} and len(read_csv(scores)) == 2
    assert len(read_csv(box)) == 12  # one row for each player on the box score, b6 too

    asked.clear()
    second = update(get, today="2026-10-21", log=log, scores=scores, box_scores=box)
    assert second["games"] == [] and not any("summary" in u for u in asked)
    assert len(read_csv(log)) == len(rows) and len(read_csv(box)) == 12


def test_rebuild_writes_each_logged_game_again(tmp_path, monkeypatch):
    monkeypatch.setattr(rotation, "load_config", lambda: {"rotation": {"minute_tolerance": 1.5}})
    log, scores, box = tmp_path / "rotation_log.csv", tmp_path / "rotation_scores.csv", tmp_path / "box_scores.csv"
    stints, score_rows, _ = game_stints(tiny_game())
    old = [{**s, "out_sec": s["out_sec"] - 1} for s in stints]  # the rows of an older version of the code
    rotation._append(log, rotation.LOG_COLUMNS, old)
    rotation._append(scores, rotation.SCORE_COLUMNS, score_rows + score_rows)
    asked = []

    def get(url):
        asked.append(url)
        return tiny_game()

    result = rotation.rebuild(get, log=log, scores=scores, box_scores=box)
    assert result["games"] == ["900"] and asked == [f"{rotation.API}/summary?event=900"]
    assert len(read_csv(log)) == len(stints) and len(read_csv(scores)) == len(score_rows)
    assert [float(r["out_sec"]) for r in read_csv(log)] == [s["out_sec"] for s in stints]
    assert len(read_csv(box)) == 12
    assert sorted(p.name for p in tmp_path.iterdir()) == ["box_scores.csv", "rotation_log.csv", "rotation_scores.csv"]


def test_logged_games_of_a_missing_log_is_empty(tmp_path):
    assert rotation.logged_games(tmp_path / "rotation_log.csv") == (set(), None)


def test_usage_rate_matches_a_hand_computed_example():
    # Player: 20 FGA, 10 FTA, 4 TOV in 36 minutes. Team: 80 FGA, 25 FTA, 12 TOV in 240 minutes.
    # (20 + 0.44 * 10 + 4) * (240 / 5) / (36 * (80 + 0.44 * 25 + 12)) = 28.4 * 48 / 3708 = 0.3676
    assert rotation.usage_rate(20, 10, 4, 36, 80, 25, 12, 240) == 36.8
    assert rotation.usage_rate(1, 0, 0, 0, 80, 25, 12, 240) is None


def test_box_rows_hold_the_stats_and_the_usage_of_each_player():
    """BOS @ DET, 2026-10-20 (ESPN event 401909088). Paul George: 38 points, 12-21 FG, 7-12 3PT, 7-8 FT, 3 TO."""
    _, _, box = game_stints(load("summary_401909088.json"))
    rows = {r["player"]: r for r in rotation.box_rows(box)}
    assert len(rows) == 28
    george = rows["Paul George"]
    assert {k: george[k] for k in ("game_id", "date", "team", "opponent", "starter", "played")} == {
        "game_id": "401909088",
        "date": "2026-10-20",
        "team": "BOS",
        "opponent": "DET",
        "starter": True,
        "played": True,
    }
    stats = ("min", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "tov", "plus_minus")
    assert [george[k] for k in stats] == [31, 38, 12, 21, 7, 12, 7, 8, 3, 9]
    bos = [r for r in rows.values() if r["team"] == "BOS" and r["played"]]
    team = {c: sum(r[c] for r in bos) for c in ("fga", "fta", "tov", "min")}
    assert (team["fga"], team["fta"], team["tov"]) == (88, 21, 14)  # the team totals of the ESPN box score
    assert george["usg"] == rotation.usage_rate(21, 8, 3, 31, 88, 21, 14, team["min"])
    conley = rows["Mike Conley"]
    assert (conley["played"], conley["min"], conley["usg"]) == (False, "", None)


def test_saved_box_minutes_match_the_rotation_log(tmp_path, monkeypatch):
    """Each player game in the saved box scores has the minutes of his stints in the rotation log."""
    monkeypatch.setattr(
        rotation, "load_config", lambda: {"league": {"espn_season": 2027}, "rotation": {"minute_tolerance": 1.5}}
    )
    board = {
        "leagues": [{"calendar": ["2026-10-20T07:00Z"]}],
        "events": [{"id": "401909088", "season": {"year": 2027, "type": 2}, "status": {"type": {"completed": True}}}],
    }

    def get(url):
        return board if "scoreboard" in url else load("summary_401909088.json")

    log, scores, box = tmp_path / "rotation_log.csv", tmp_path / "rotation_scores.csv", tmp_path / "box_scores.csv"
    update(get, today="2026-10-20", log=log, scores=scores, box_scores=box)
    minutes = {}
    for s in read_csv(log):
        key = (s["game_id"], s["player_id"])
        minutes[key] = minutes.get(key, 0) + (float(s["out_sec"]) - float(s["in_sec"])) / 60
    played = {(r["game_id"], r["player_id"]): int(r["min"]) for r in read_csv(box) if r["played"] == "True"}
    assert set(played) == set(minutes)
    assert all(abs(played[k] - minutes[k]) <= 1 for k in played)


def test_backfill_adds_the_box_scores_of_logged_games_once(tmp_path):
    log, box = tmp_path / "rotation_log.csv", tmp_path / "box_scores.csv"
    stints, _, _ = game_stints(tiny_game())
    rotation._append(log, rotation.LOG_COLUMNS, stints)
    asked = []

    def get(url):
        asked.append(url)
        return tiny_game()

    assert rotation.backfill(get, log=log, box_scores=box) == {"games": ["900"]}
    assert len(read_csv(box)) == 12 and asked == [f"{rotation.API}/summary?event=900"]
    assert rotation.backfill(get, log=log, box_scores=box) == {"games": []}
    assert len(read_csv(box)) == 12 and len(asked) == 1


def test_update_does_not_write_a_box_score_twice(tmp_path, monkeypatch):
    """A run that stopped before the log wrote the box score. The next run reads the game again."""
    monkeypatch.setattr(
        rotation, "load_config", lambda: {"league": {"espn_season": 2027}, "rotation": {"minute_tolerance": 1.5}}
    )
    board = {
        "leagues": [{"calendar": ["2026-10-21T07:00Z"]}],
        "events": [{"id": "900", "season": {"year": 2027, "type": 2}, "status": {"type": {"completed": True}}}],
    }
    box = tmp_path / "box_scores.csv"
    rotation._append(box, rotation.BOX_COLUMNS, rotation.box_rows(game_stints(tiny_game())[2]))

    def get(url):
        return board if "scoreboard" in url else tiny_game()

    update(get, today="2026-10-21", log=tmp_path / "log.csv", scores=tmp_path / "scores.csv", box_scores=box)
    assert len(read_csv(box)) == 12
    assert len(read_csv(tmp_path / "log.csv")) > 0
