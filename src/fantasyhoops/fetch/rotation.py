"""Download the play-by-play of each finished NBA game from ESPN and add the stints to the rotation log.

A stint is the time from a check-in to the next check-out of one player in one period.
The log starts at the first regular-season game of espn_season in config.toml.
A run reads only the games that are not in the log. Run it again after each game day.
The run prints each player whose stints are more than 1.5 minutes from his box-score minutes.
Output (the run adds rows):
  data/rotation_log.csv     - one row for each stint, with the score at the check-in and at the check-out
  data/rotation_scores.csv  - one row for each play that changes the score
The reader for other tools is fantasyhoops.core.rotation.
"""
import csv
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fantasyhoops.core.common import DATA, load_config
from fantasyhoops.core.rotation import period_bounds
from fantasyhoops.fetch.espn import API, get_json, local_date

LOG = DATA / "rotation_log.csv"
SCORES = DATA / "rotation_scores.csv"
LOG_COLUMNS = ["game_id", "date", "team", "opponent", "player_id", "player", "starter", "period",
               "in_sec", "out_sec", "in_team_score", "in_opp_score", "out_team_score", "out_opp_score"]
SCORE_COLUMNS = ["game_id", "sec", "home_score", "away_score"]
TOLERANCE = 1.5  # minutes between the stints and the box score of a player
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
        lineup[team] = on + rest[:max(0, LINEUP - len(on))]
    return lineup


def game_stints(summary):
    """The stints, the score changes and the box score of one game.

    Gives (stints, scores, box). box is {player_id: {"player", "team", "minutes"}}.
    """
    comp = summary["header"]["competitions"][0]
    game_id = summary["header"]["id"]
    date = local_date(comp["date"])
    side = {c["team"]["id"]: c["homeAway"] for c in comp["competitors"]}
    abbr = {c["team"]["id"]: c["team"]["abbreviation"] for c in comp["competitors"]}
    other = {a: b for a in side for b in side if a != b}

    box, team_of, starters = {}, {}, defaultdict(list)
    for team in summary["boxscore"]["players"]:
        team_id = team["team"]["id"]
        stats = team["statistics"][0]
        col = stats["names"].index("MIN")
        for row in stats["athletes"]:
            pid = row["athlete"]["id"]
            text = row["stats"][col] if row.get("stats") else ""
            box[pid] = {"player": row["athlete"]["displayName"], "team": abbr[team_id],
                        "minutes": int(text) if text.isdigit() else 0, "starter": row["starter"]}
            team_of[pid] = team_id
            if row["starter"]:
                starters[team_id].append(pid)

    # ESPN gives the plays in time order. Do not sort by sequenceNumber: a play that ESPN adds late
    # (for example a substitution after a review) gets a high sequenceNumber.
    by_period = defaultdict(list)
    for play in summary["plays"]:
        by_period[play["period"]["number"]].append(play)

    score = {"home": 0, "away": 0}
    stints, scores, open_ = [], [], {}

    def team_score(pid):
        team = team_of[pid]
        return score[side[team]], score[side[other[team]]]

    def check_in(pid, sec, period):
        if pid in team_of and pid not in open_:
            open_[pid] = (sec, period, *team_score(pid))

    def check_out(pid, sec):
        if pid not in open_:
            return
        in_sec, period, in_team, in_opp = open_.pop(pid)
        if sec <= in_sec:
            return  # a stint of 0 seconds, for example a substitution at 12:00
        team = team_of[pid]
        out_team, out_opp = team_score(pid)
        stints.append({"game_id": game_id, "date": date, "team": abbr[team], "opponent": abbr[other[team]],
                       "player_id": pid, "player": box[pid]["player"], "starter": box[pid]["starter"],
                       "period": period, "in_sec": in_sec, "out_sec": sec,
                       "in_team_score": in_team, "in_opp_score": in_opp,
                       "out_team_score": out_team, "out_opp_score": out_opp})

    lineup = {team: starters[team] for team in side}
    for period in range(1, max(by_period) + 1):
        start, length = period_bounds(period)
        if period > 1:
            lineup = _period_lineup(by_period[period], lineup, team_of)
        for pids in lineup.values():
            for pid in pids:
                check_in(pid, start, period)
        for play in by_period[period]:
            sec = round(start + length - clock_seconds(play["clock"]["displayValue"]), 1)
            ids = _ids(play)
            if _is_sub(play) and len(ids) == 2:
                check_out(ids[1], sec)
                check_in(ids[0], sec, period)
                continue
            new = {"home": play["homeScore"], "away": play["awayScore"]}
            if new != score:
                score = new
                scores.append({"game_id": game_id, "sec": sec, "home_score": score["home"], "away_score": score["away"]})
        lineup = {team: [pid for pid in open_ if team_of[pid] == team] for team in side}
        for pid in list(open_):
            check_out(pid, start + length)
    return stints, scores, box


def minute_gaps(stints, box, tolerance=TOLERANCE):
    """The players whose stints are more than tolerance minutes from their box-score minutes."""
    played = defaultdict(float)
    for s in stints:
        played[s["player_id"]] += (s["out_sec"] - s["in_sec"]) / 60
    gaps = []
    for pid in sorted(set(played) | {p for p, b in box.items() if b["minutes"]}, key=lambda p: box[p]["player"]):
        if abs(played[pid] - box[pid]["minutes"]) > tolerance:
            gaps.append({"player": box[pid]["player"], "team": box[pid]["team"],
                         "log_minutes": round(played[pid], 1), "box_minutes": box[pid]["minutes"]})
    return gaps


def season_dates(scoreboard, today, since=None):
    """The game dates of the season up to today, as "YYYYMMDD". since skips the dates before it."""
    days = [d[:10] for d in scoreboard["leagues"][0]["calendar"]]
    return [d.replace("-", "") for d in days if d <= today and (since is None or d >= since)]


def finished_games(scoreboard, season):
    """The ESPN event IDs of the final regular-season games on a scoreboard."""
    return [e["id"] for e in scoreboard["events"]
            if e["season"]["year"] == season and e["season"]["type"] == 2 and e["status"]["type"]["completed"]]


def logged_games(log=LOG):
    """The game IDs in the log and the newest date in the log."""
    if not log.exists():
        return set(), None
    with open(log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["game_id"] for r in rows}, max((r["date"] for r in rows), default=None)


def _append(path, columns, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def update(get=get_json, today=None, log=LOG, scores=SCORES):
    """Add the finished games that are not in the log. Gives {"games": new game IDs, "gaps": minute gaps}."""
    season = load_config()["league"]["espn_season"]
    today = today or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    done, newest = logged_games(log)
    log.parent.mkdir(exist_ok=True)

    calendar = get(f"{API}/scoreboard?dates={today.replace('-', '')}")
    new, gaps = [], []
    # A game day can end after a run. So the run reads the newest date in the log again.
    for day in season_dates(calendar, today, since=newest):
        for game_id in finished_games(get(f"{API}/scoreboard?dates={day}"), season):
            if game_id in done:
                continue
            stints, score_rows, box = game_stints(get(f"{API}/summary?event={game_id}"))
            # The scores go first. If the run stops between the two files, the game is not in the log and the next run reads it again.
            _append(scores, SCORE_COLUMNS, score_rows)
            _append(log, LOG_COLUMNS, stints)
            done.add(game_id)
            new.append(game_id)
            gaps += [{"game_id": game_id, **g} for g in minute_gaps(stints, box)]
            print(f"{day} {game_id}: {len(stints)} stints")
    return {"games": new, "gaps": gaps}


def main():
    result = update()
    print(f"Added {len(result['games'])} games to {LOG}")
    if result["gaps"]:
        print(f"{len(result['gaps'])} players are more than {TOLERANCE} minutes from the box score:")
        for g in result["gaps"]:
            print(f"  {g['game_id']} {g['team']} {g['player']}: log {g['log_minutes']}, box {g['box_minutes']}")


if __name__ == "__main__":
    main()
