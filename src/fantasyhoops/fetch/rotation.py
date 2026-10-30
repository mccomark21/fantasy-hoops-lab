"""Download the play-by-play and the box score of each finished NBA game from ESPN, and add them to the data files.

A stint is the time from a check-in to the next check-out of one player in one period.
The log starts at the first regular-season game of espn_season in config.toml.
A run reads only the games that are not in the log. Run it again after each game day.
The run prints each player whose stints are more than minute_tolerance ([rotation] in config.toml) from his box-score minutes.
Output (the run adds rows):
  data/rotation_log.csv     - one row for each stint, with the score at the check-in and at the check-out
  data/rotation_scores.csv  - one row for each play that changes the score
  data/box_scores.csv       - one row for each player on the box score of each game, with his usage rate (usg)
With --rebuild, the run reads each game in the log again and writes the 3 files again.
With --box-scores, the run reads the logged games that are not in data/box_scores.csv and adds their box scores.
The reader for other tools is fantasyhoops.core.rotation.
"""

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fantasyhoops.core.common import load_config
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.rotation import BOX_SCORES, LOG, SCORES, period_bounds
from fantasyhoops.fetch.espn import API, get_json, local_date

LOG_COLUMNS = [
    "game_id",
    "date",
    "team",
    "opponent",
    "player_id",
    "player",
    "starter",
    "period",
    "in_sec",
    "out_sec",
    "in_team_score",
    "in_opp_score",
    "out_team_score",
    "out_opp_score",
]
SCORE_COLUMNS = ["game_id", "sec", "home_score", "away_score"]
# The box-score columns of ESPN -> the columns of data/box_scores.csv. ESPN gives "12-21" for made and attempted.
BOX_STATS = {
    "MIN": ["min"],
    "PTS": ["pts"],
    "FG": ["fgm", "fga"],
    "3PT": ["fg3m", "fg3a"],
    "FT": ["ftm", "fta"],
    "OREB": ["oreb"],
    "DREB": ["dreb"],
    "REB": ["reb"],
    "AST": ["ast"],
    "STL": ["stl"],
    "BLK": ["blk"],
    "TO": ["tov"],
    "PF": ["pf"],
    "+/-": ["plus_minus"],
}
STAT_COLUMNS = [col for cols in BOX_STATS.values() for col in cols]
BOX_COLUMNS = [
    "game_id",
    "date",
    "team",
    "opponent",
    "player_id",
    "player",
    "starter",
    "played",
    *STAT_COLUMNS,
    "usg",
]
# The weight of a free-throw attempt in a possession, as in the usage rate of Basketball-Reference.
FTA_WEIGHT = 0.44
LINEUP = 5
# A player on the bench can get these. They do not show that he is on the floor.
BENCH_PLAYS = ("Technical", "Ejection")


def clock_seconds(text):
    """Seconds left in the period. ESPN gives "8:11", or "45.3" in the last minute."""
    if ":" in text:
        minutes, secs = text.split(":")
        return int(minutes) * 60 + float(secs)
    return float(text)


def _ids(play):
    return [p["athlete"]["id"] for p in play.get("participants", [])]


def _is_sub(play):
    return play["type"]["text"] == "Substitution"


def _period_lineup(plays, last_lineup, team_of):
    """The players of each team on the floor at the start of a period after the first.

    ESPN does not log the changes between periods. A player is on the floor if his first play
    in the period is not a check-in. If a team then has fewer than 5, the players from the end
    of the last period who have no play in this period fill the lineup.
    """
    first = {}
    for play in plays:
        if any(word in play["type"]["text"] for word in BENCH_PLAYS):
            continue
        ids = _ids(play)
        if _is_sub(play) and len(ids) == 2:
            first.setdefault(ids[0], "in")
            first.setdefault(ids[1], "on")
        else:
            for pid in ids:
                first.setdefault(pid, "on")
    lineup = {}
    for team, last in last_lineup.items():
        on = [pid for pid, how in first.items() if how == "on" and team_of.get(pid) == team]
        rest = [pid for pid in last if pid not in first]
        lineup[team] = on + rest[: max(0, LINEUP - len(on))]
    return lineup


def _stat_values(names, values):
    """{column of data/box_scores.csv: int} from one ESPN box-score row. A stat that ESPN does not give is missing."""
    out = {}
    for name, text in zip(names, values):
        cols = BOX_STATS.get(name)
        if cols is None:
            continue
        parts = text.split("-") if len(cols) == 2 else [text.lstrip("+")]
        for col, part in zip(cols, parts):
            try:
                out[col] = int(part)
            except ValueError:
                out[col] = 0
    return out


def box_score(summary):
    """The box score of one game. Gives {player_id: {"player", "team", "team_id", "minutes", "starter", ...}}.

    Each player also has "game_id", "date", "opponent", "played" and "stats" ({column in STAT_COLUMNS: int}).
    A player who did not play has "played" False and no stats.
    """
    comp = summary["header"]["competitions"][0]
    abbr = {c["team"]["id"]: c["team"]["abbreviation"] for c in comp["competitors"]}
    other = {a: b for a in abbr for b in abbr if a != b}
    game_id, date = summary["header"]["id"], local_date(comp["date"])
    box = {}
    for team in summary["boxscore"]["players"]:
        team_id = team["team"]["id"]
        stats = team["statistics"][0]
        for row in stats["athletes"]:
            values = _stat_values(stats["names"], row.get("stats") or [])
            box[row["athlete"]["id"]] = {
                "game_id": game_id,
                "date": date,
                "player": row["athlete"]["displayName"],
                "team": abbr[team_id],
                "team_id": team_id,
                "opponent": abbr[other[team_id]],
                "minutes": values.get("min", 0),
                "starter": row["starter"],
                "played": bool(values),
                "stats": values,
            }
    return box


def usage_rate(fga, fta, tov, minutes, team_fga, team_fta, team_tov, team_minutes):
    """USG%: the percent of the team plays that a player uses while he is on the floor. None for 0 minutes.

    USG% = 100 * (FGA + 0.44 * FTA + TOV) * (team MIN / 5) / (MIN * (team FGA + 0.44 * team FTA + team TOV))
    """
    team_plays = team_fga + FTA_WEIGHT * team_fta + team_tov
    if minutes <= 0 or team_plays <= 0:
        return None
    return round(100 * (fga + FTA_WEIGHT * fta + tov) * (team_minutes / 5) / (minutes * team_plays), 1)


def box_rows(box):
    """The rows of data/box_scores.csv for one game, from box_score(). The team totals are the sums of its players."""
    totals = defaultdict(lambda: defaultdict(int))
    for b in box.values():
        for col, value in b["stats"].items():
            totals[b["team_id"]][col] += value
    rows = []
    for pid, b in box.items():
        stats, team = b["stats"], totals[b["team_id"]]
        usg = None
        if b["played"]:
            usg = usage_rate(
                stats.get("fga", 0),
                stats.get("fta", 0),
                stats.get("tov", 0),
                stats.get("min", 0),
                team["fga"],
                team["fta"],
                team["tov"],
                team["min"],
            )
        game = {k: b[k] for k in ("game_id", "date", "team", "opponent")}
        player = {"player_id": pid, "player": b["player"], "starter": b["starter"], "played": b["played"]}
        rows.append({**game, **player, **{c: stats.get(c, "") for c in STAT_COLUMNS}, "usg": usg})
    return rows


def game_stints(summary):
    """The stints, the score changes and the box score of one game.

    Gives (stints, scores, box). box is the box_score() of the game.
    """
    comp = summary["header"]["competitions"][0]
    game_id = summary["header"]["id"]
    date = local_date(comp["date"])
    side = {c["team"]["id"]: c["homeAway"] for c in comp["competitors"]}
    abbr = {c["team"]["id"]: c["team"]["abbreviation"] for c in comp["competitors"]}
    other = {a: b for a in side for b in side if a != b}

    box = box_score(summary)
    team_of = {pid: b["team_id"] for pid, b in box.items()}
    starters = defaultdict(list)
    for pid, b in box.items():
        if b["starter"]:
            starters[b["team_id"]].append(pid)

    # ESPN gives the plays in time order. Do not sort by sequenceNumber: a play that ESPN adds late
    # (for example a substitution after a review) gets a high sequenceNumber.
    by_period = defaultdict(list)
    for play in summary["plays"]:
        by_period[play["period"]["number"]].append(play)

    score = {"home": 0, "away": 0}
    stints, scores, open_ = [], [], {}
    # The substitutions of the current period: who each player replaced, and who replaced each player.
    came_in_for, went_out_for = {}, {}

    def team_score(pid):
        team = team_of[pid]
        return score[side[team]], score[side[other[team]]]

    def check_in(pid, sec, period):
        if pid in team_of and pid not in open_:
            open_[pid] = (sec, period, *team_score(pid))

    def check_out(pid, sec):
        """Close the stint of pid. Gives (open stint, row), with no row for a stint of 0 seconds.

        Gives None if pid is not on the floor.
        """
        if pid not in open_:
            return None
        start = open_.pop(pid)
        in_sec, period, in_team, in_opp = start
        if sec <= in_sec:
            return start, None  # a stint of 0 seconds, for example a substitution at 12:00
        team = team_of[pid]
        out_team, out_opp = team_score(pid)
        row = {
            "game_id": game_id,
            "date": date,
            "team": abbr[team],
            "opponent": abbr[other[team]],
            "player_id": pid,
            "player": box[pid]["player"],
            "starter": box[pid]["starter"],
            "period": period,
            "in_sec": in_sec,
            "out_sec": sec,
            "in_team_score": in_team,
            "in_opp_score": in_opp,
            "out_team_score": out_team,
            "out_opp_score": out_opp,
        }
        stints.append(row)
        return start, row

    def undo_sub(pid, sec):
        """Move the last substitution that put pid on the floor to sec. Gives False if there is none to move.

        ESPN can log one substitution twice, the first copy at a wrong time.
        The player that pid replaced stays on the floor until sec.
        """
        replaced = came_in_for.get(pid)
        if replaced is None or replaced in open_ or went_out_for.get(replaced, (None,))[0] != pid:
            return False
        _, (start, row) = went_out_for.pop(replaced)
        if row is not None:
            stints.remove(row)
        open_[replaced] = start
        open_[pid] = (sec, open_[pid][1], *team_score(pid))
        del came_in_for[pid]
        return True

    def substitute(pid_in, pid_out, sec, period):
        """Apply "pid_in enters the game for pid_out". ESPN substitutions can be wrong, so check them first."""
        if pid_in in open_ and not undo_sub(pid_in, sec):
            return  # the player is on the floor and no substitution put him there: ESPN logged a wrong player
        if pid_out not in open_:
            # ESPN can give the wrong player out. If pid_out left the floor for a player who is still on it,
            # that player goes out now.
            replacement = went_out_for.get(pid_out, (None,))[0]
            pid_out = replacement if replacement in open_ and came_in_for.get(replacement) == pid_out else None
        closed = check_out(pid_out, sec) if pid_out else None
        check_in(pid_in, sec, period)
        if closed and pid_in in open_:
            went_out_for[pid_out] = (pid_in, closed)
            came_in_for[pid_in] = pid_out

    lineup = {team: starters[team] for team in side}
    for period in range(1, max(by_period) + 1):
        start, length = period_bounds(period)
        came_in_for.clear()
        went_out_for.clear()
        if period > 1:
            lineup = _period_lineup(by_period[period], lineup, team_of)
        for pids in lineup.values():
            for pid in pids:
                check_in(pid, start, period)
        for play in by_period[period]:
            sec = round(start + length - clock_seconds(play["clock"]["displayValue"]), 1)
            ids = _ids(play)
            if _is_sub(play) and len(ids) == 2:
                substitute(ids[0], ids[1], sec, period)
                continue
            new = {"home": play["homeScore"], "away": play["awayScore"]}
            if new != score:
                score = new
                scores.append(
                    {"game_id": game_id, "sec": sec, "home_score": score["home"], "away_score": score["away"]}
                )
        lineup = {team: [pid for pid in open_ if team_of[pid] == team] for team in side}
        for pid in list(open_):
            check_out(pid, start + length)
    return stints, scores, box


def minute_gaps(stints, box, tolerance):
    """The players whose stints are more than tolerance minutes from their box-score minutes."""
    played = defaultdict(float)
    for s in stints:
        played[s["player_id"]] += (s["out_sec"] - s["in_sec"]) / 60
    gaps = []
    for pid in sorted(set(played) | {p for p, b in box.items() if b["minutes"]}, key=lambda p: box[p]["player"]):
        if abs(played[pid] - box[pid]["minutes"]) > tolerance:
            gaps.append(
                {
                    "player": box[pid]["player"],
                    "team": box[pid]["team"],
                    "log_minutes": round(played[pid], 1),
                    "box_minutes": box[pid]["minutes"],
                }
            )
    return gaps


def season_dates(scoreboard, today, since=None):
    """The game dates of the season up to today, as "YYYYMMDD". since skips the dates before it."""
    days = [d[:10] for d in scoreboard["leagues"][0]["calendar"]]
    return [d.replace("-", "") for d in days if d <= today and (since is None or d >= since)]


def finished_games(scoreboard, season):
    """The ESPN event IDs of the final regular-season games on a scoreboard."""
    return [
        e["id"]
        for e in scoreboard["events"]
        if e["season"]["year"] == season and e["season"]["type"] == 2 and e["status"]["type"]["completed"]
    ]


def logged_games(log=LOG):
    """The game IDs in the log and the newest date in the log."""
    if not log.exists():
        return set(), None
    with open(log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["game_id"] for r in rows}, max((r["date"] for r in rows), default=None)


def box_games(box_scores=BOX_SCORES):
    """The game IDs in data/box_scores.csv."""
    if not box_scores.exists():
        return set()
    with open(box_scores, newline="", encoding="utf-8") as f:
        return {r["game_id"] for r in csv.DictReader(f)}


def _append(path, columns, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def read_game(get, game_id):
    """Download the ESPN game summary of one game. Gives (stints, scores, box), as game_stints() does."""
    return game_stints(get(f"{API}/summary?event={game_id}"))


def update(get=get_json, today=None, log=LOG, scores=SCORES, box_scores=BOX_SCORES):
    """Add the finished games that are not in the log. Gives {"games": new game IDs, "gaps": minute gaps}."""
    cfg = load_config()
    season, tolerance = cfg["league"]["espn_season"], cfg["rotation"]["minute_tolerance"]
    today = today or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    done, newest = logged_games(log)
    boxed = box_games(box_scores)
    log.parent.mkdir(exist_ok=True)

    calendar = get(f"{API}/scoreboard?dates={today.replace('-', '')}")
    new, gaps = [], []
    # A game day can end after a run. So the run reads the newest date in the log again.
    for day in season_dates(calendar, today, since=newest):
        for game_id in finished_games(get(f"{API}/scoreboard?dates={day}"), season):
            if game_id in done:
                continue
            stints, score_rows, box = read_game(get, game_id)
            # Make all the rows before the run writes a file. A game that fails then changes no file.
            game_box = box_rows(box) if game_id not in boxed else []
            # The log goes last. If the run stops before the log, the game is not in the log and the next run reads it again.
            _append(scores, SCORE_COLUMNS, score_rows)
            if game_box:
                _append(box_scores, BOX_COLUMNS, game_box)
                boxed.add(game_id)
            _append(log, LOG_COLUMNS, stints)
            done.add(game_id)
            new.append(game_id)
            gaps += [{"game_id": game_id, **g} for g in minute_gaps(stints, box, tolerance)]
            print(f"{day} {game_id}: {len(stints)} stints")
    return {"games": new, "gaps": gaps, "tolerance": tolerance}


def _log_games(log):
    """The game IDs in the log, in the order of the log."""
    if not log.exists():
        return []
    with open(log, newline="", encoding="utf-8") as f:
        return list(dict.fromkeys(r["game_id"] for r in csv.DictReader(f)))


def backfill(get=get_json, log=LOG, box_scores=BOX_SCORES):
    """Add the box score of each game in the log that is not in data/box_scores.csv. Gives {"games": game IDs}.

    A second run reads no game again, so it adds no duplicate rows.
    """
    boxed = box_games(box_scores)
    games = [g for g in _log_games(log) if g not in boxed]
    for game_id in games:
        _, _, box = read_game(get, game_id)
        _append(box_scores, BOX_COLUMNS, box_rows(box))
        print(f"{game_id}: {len(box)} players")
    return {"games": games}


def rebuild(get=get_json, log=LOG, scores=SCORES, box_scores=BOX_SCORES):
    """Read each game in the log again and write the 3 files again. Gives the same dict as update().

    Run it after a change to game_stints(). The run writes new files next to the old ones,
    and replaces the old files only at the end.
    """
    tolerance = load_config()["rotation"]["minute_tolerance"]
    if not log.exists():
        return {"games": [], "gaps": [], "tolerance": tolerance}
    games = _log_games(log)
    new_log, new_scores = log.with_suffix(".csv.new"), scores.with_suffix(".csv.new")
    new_box = box_scores.with_suffix(".csv.new")
    for path in (new_log, new_scores, new_box):
        path.unlink(missing_ok=True)
    gaps = []
    for game_id in games:
        stints, score_rows, box = read_game(get, game_id)
        game_box = box_rows(box)
        _append(new_scores, SCORE_COLUMNS, score_rows)
        _append(new_box, BOX_COLUMNS, game_box)
        _append(new_log, LOG_COLUMNS, stints)
        gaps += [{"game_id": game_id, **g} for g in minute_gaps(stints, box, tolerance)]
        print(f"{game_id}: {len(stints)} stints")
    new_scores.replace(scores)
    new_box.replace(box_scores)
    new_log.replace(log)
    return {"games": games, "gaps": gaps, "tolerance": tolerance}


def main(again=False, box_only=False):
    if box_only:
        result = backfill()
        print(f"Added the box scores of {len(result['games'])} games to {BOX_SCORES}")
        return
    result = rebuild() if again else update()
    print(f"{'Wrote' if again else 'Added'} {len(result['games'])} games to {LOG}")
    if result["gaps"]:
        print(f"{len(result['gaps'])} players are more than {result['tolerance']} minutes from the box score:")
        for g in result["gaps"]:
            print(f"  {g['game_id']} {g['team']} {g['player']}: log {g['log_minutes']}, box {g['box_minutes']}")


if __name__ == "__main__":
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Add the finished NBA games to the rotation log.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Read each game in the log again. Write the log, the scores and the box scores again.",
    )
    parser.add_argument(
        "--box-scores",
        action="store_true",
        help="Add the box score of each logged game that is not in data/box_scores.csv.",
    )
    args = parser.parse_args()
    main(again=args.rebuild, box_only=args.box_scores)
