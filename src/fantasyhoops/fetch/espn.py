"""Download NBA rosters and the regular-season schedule from ESPN.

Run this script again when rosters change (trades, signings).
Output:
  data/rosters.csv   - one row for each player on an NBA roster
  data/schedule.csv  - one row for each team in each regular-season game, with the start time (US Eastern)
season_stats() gets the season stats to date of all players in one request (#120). It writes no file.
"""

import csv
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fantasyhoops.core.common import DATA, load_config, name_key
from fantasyhoops.core.console import use_utf8_output

API = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
STATS_API = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"
# The stat key of the roster page (core/home.py) -> (category, stat name) in the statistics/byathlete answer.
SEASON_STATS = {
    "gp": ("general", "gamesPlayed"),
    "min": ("general", "avgMinutes"),
    "pts": ("offensive", "avgPoints"),
    "reb": ("general", "avgRebounds"),
    "ast": ("offensive", "avgAssists"),
    "threes": ("offensive", "avgThreePointFieldGoalsMade"),
    "stl": ("defensive", "avgSteals"),
    "blk": ("defensive", "avgBlocks"),
}


def get_json(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.load(resp)
        except Exception as err:
            if attempt == 2:
                raise RuntimeError(f"Download failed: {url}") from err
            time.sleep(2)


def local_date(utc_text):
    # ESPN gives UTC times. All NBA games start after 18:00 UTC, so
    # 6 hours earlier gives the US calendar date of the game.
    utc = datetime.strptime(utc_text, "%Y-%m-%dT%H:%MZ")
    return (utc - timedelta(hours=6)).date().isoformat()


def local_time(utc_text):
    """The start time of the game in US Eastern time, for example "19:30"."""
    utc = datetime.strptime(utc_text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    return utc.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M")


def stats_url(season):
    """The statistics/byathlete request for all players of the regular season, on one page."""
    return f"{STATS_API}?region=us&lang=en&isqualified=false&limit=1000&season={season}&seasontype=2"


def parse_season_stats(answer):
    """{name_key(name): {"team": ESPN code, "gp": ..., "min": ..., "pts": ..., ...}} from a statistics/byathlete answer.

    The stats are per game, except gp (games played). Two players with the same name key: the first one stays.
    """
    names = {c["name"]: c["names"] for c in answer["categories"]}
    out = {}
    for row in answer["athletes"]:
        values = {c["name"]: c["values"] for c in row["categories"]}
        stats = {key: float(values[cat][names[cat].index(stat)]) for key, (cat, stat) in SEASON_STATS.items()}
        stats["gp"] = int(stats["gp"])
        athlete = row["athlete"]
        out.setdefault(name_key(athlete["displayName"]), {"team": athlete.get("teamShortName", ""), **stats})
    return out


def season_stats(season):
    """The season stats to date of all players (parse_season_stats()), from one ESPN request."""
    return parse_season_stats(get_json(stats_url(season)))


def main():
    season = load_config()["league"]["espn_season"]
    DATA.mkdir(exist_ok=True)

    league = get_json(f"{API}/teams")
    teams = [t["team"] for t in league["sports"][0]["leagues"][0]["teams"]]

    rosters, games = [], []
    for team in teams:
        abbr = team["abbreviation"]
        roster = get_json(f"{API}/teams/{team['id']}/roster")
        for athlete in roster["athletes"]:
            rosters.append({"espn_name": athlete["fullName"], "team": abbr})

        schedule = get_json(f"{API}/teams/{team['id']}/schedule?season={season}&seasontype=2")
        for event in schedule["events"]:
            sides = event["competitions"][0]["competitors"]
            opponent = next(s["team"]["abbreviation"] for s in sides if s["team"]["id"] != team["id"])
            games.append(
                {
                    "date": local_date(event["date"]),
                    "team": abbr,
                    "opponent": opponent,
                    "time": local_time(event["date"]),
                }
            )
        print(f"{abbr}: {len(roster['athletes'])} players, {len(schedule['events'])} games")

    for name, rows in (("rosters.csv", rosters), ("schedule.csv", games)):
        with open(DATA / name, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(rosters)} players and {len(games)} team-games to {DATA}")


if __name__ == "__main__":
    use_utf8_output()
    main()
