"""Download the NBA hustle and tracking stats of the season from stats.nba.com (#251).

The script reads 6 league-wide tables with the nba_api package, one request for each table. All stats are per game.
NBA.com can block or time out a request. The script tries each request 3 times and names the table that failed.
No page uses this data yet. The refresh run does not run this script.
Output:
  data/nba_stats.csv - one row for each player that NBA.com lists, with the stat columns of all 6 tables
"""

import sys
import time

import pandas as pd
from nba_api.stats.endpoints import (
    leaguedashplayerstats,
    leaguedashptstats,
    leaguehustlestatsplayer,
)

from fantasyhoops.core.common import DATA, load_config, name_key
from fantasyhoops.core.console import use_utf8_output

OUT_FILE = DATA / "nba_stats.csv"
WAIT = 1.0  # seconds between two requests. NBA.com blocks clients that send requests too fast
TRIES = 3

# The columns that name the player or the team. merge_tables() keeps one copy, not one copy for each table.
ID_COLUMNS = {"PLAYER_ID", "PLAYER_NAME", "NICKNAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE"}
# The columns of the team record, and the games column of the hustle table. merge_tables() drops them.
DROP_COLUMNS = {"W", "L", "W_PCT", "G"}


def tables(season):
    """{label: a function that makes the nba_api request}. The label is the column prefix in the output file."""

    def tracking(measure):
        return lambda: leaguedashptstats.LeagueDashPtStats(
            season=season, pt_measure_type=measure, player_or_team="Player", per_mode_simple="PerGame", timeout=60
        )

    return {
        "adv": lambda: leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame", timeout=60
        ),
        "hustle": lambda: leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season, per_mode_time="PerGame", timeout=60
        ),
        "pass": tracking("Passing"),
        "reb": tracking("Rebounding"),
        "def": tracking("Defense"),
        "touch": tracking("Possessions"),
    }


def nba_season(espn_season):
    """The NBA.com season text from the ESPN season (the year that the season ends): 2027 -> "2026-27"."""
    return f"{espn_season - 1}-{espn_season % 100:02d}"


def stat_columns(frame):
    """The stat columns of one table: no id columns, no columns of the team record, no ranks, no work columns."""
    return [
        c
        for c in frame.columns
        if c not in ID_COLUMNS | DROP_COLUMNS and c != "GP" and not c.endswith("_RANK") and not c.startswith("sp_work_")
    ]


def merge_tables(frames):
    """One row for each player from {label: table}. The tables join on the NBA player id.

    The first columns are nba_id, name, name_key, team and gp. Each stat column gets the label of its table as a
    prefix, in lower case, for example "hustle_deflections". A player who is missing from a table gets empty cells.
    """
    ids = pd.concat(
        [f[[c for c in ("PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION") if c in f]] for f in frames.values()]
    )
    out = ids.drop_duplicates("PLAYER_ID").rename(
        columns={"PLAYER_ID": "nba_id", "PLAYER_NAME": "name", "TEAM_ABBREVIATION": "team"}
    )
    out.insert(2, "name_key", out["name"].map(name_key))
    games = pd.concat([f[["PLAYER_ID", "GP"]] for f in frames.values() if "GP" in f]).drop_duplicates("PLAYER_ID")
    out = out.merge(games.rename(columns={"PLAYER_ID": "nba_id", "GP": "gp"}), on="nba_id", how="left")
    for label, frame in frames.items():
        stats = frame[["PLAYER_ID", *stat_columns(frame)]].drop_duplicates("PLAYER_ID")
        stats.columns = ["nba_id"] + [f"{label}_{c.lower()}" for c in stats.columns[1:]]
        out = out.merge(stats, on="nba_id", how="left")
    return out.sort_values("name").reset_index(drop=True)


def get_table(label, request, wait=WAIT, tries=TRIES):
    """The first table of one nba_api request. Try again after a failure. Raise RuntimeError after the last try."""
    for attempt in range(1, tries + 1):
        try:
            frame = request().get_data_frames()[0]
            time.sleep(wait)
            return frame
        except Exception as err:
            if attempt == tries:
                raise RuntimeError(f"The NBA.com table '{label}' failed {tries} times: {err}") from err
            time.sleep(3 * wait)


def main():
    season = nba_season(load_config()["league"]["espn_season"])
    frames = {}
    for label, request in tables(season).items():
        frames[label] = get_table(label, request)
        print(f"{label}: {len(frames[label])} players")
    out = merge_tables(frames)
    DATA.mkdir(exist_ok=True)
    out.to_csv(OUT_FILE, index=False)
    print(f"Wrote {OUT_FILE} ({len(out)} players, {len(out.columns)} columns, season {season})")
    return 0


if __name__ == "__main__":
    use_utf8_output()
    sys.exit(main())
