"""Download the NBA hustle and tracking stats of a season from stats.nba.com (#251, #252).

The script reads 5 league-wide tables with the nba_api package, one request for each table. All stats are season
totals. NBA.com can block or time out a request. The script tries each request 3 times and names the table that failed.
The refresh run runs this script. If a request fails, the script writes no file, so the last good file stays.
Run it with: python -m fantasyhoops.fetch.nba_stats [--season 2025-26] [--out PATH]
Output (docs/fetch/README.md lists the columns):
  data/nba_stats.csv - the current season: one row for each player that NBA.com lists
  data/nba_stats/<YYYY-MM-DD>.csv - a dated copy of data/nba_stats.csv, one for each day of a run
  data/nba_stats_<season>.csv - a past season, for example data/nba_stats_2025-26.csv. It gets no dated copy.
"""

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import (
    leaguedashplayerstats,
    leaguedashptstats,
    leaguehustlestatsplayer,
)

from fantasyhoops.core.common import DATA, load_config, name_key
from fantasyhoops.core.console import use_utf8_output

OUT_FILE = DATA / "nba_stats.csv"
SNAPSHOT_DIR = "nba_stats"  # the folder of the dated copies, next to the output file
WAIT = 1.0  # seconds between two requests. NBA.com blocks clients that send requests too fast
TRIES = 3

# The columns that name the player or the team. merge_tables() keeps one copy, not one copy for each table.
ID_COLUMNS = {"PLAYER_ID", "PLAYER_NAME", "NICKNAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE"}
# The columns of the team record, and the games column of the hustle table. merge_tables() drops them.
DROP_COLUMNS = {"W", "L", "W_PCT", "G"}

# The makes and the chances of each category, as {category: (makes column, chances column)} of the merged table.
# The category names are the keys of [weights] in config.toml. add_chances() copies the two columns to
# <category>_makes and <category>_chances.
CHANCES = {
    "stl": ("base_stl", "hustle_deflections"),
    "blk": ("base_blk", "hustle_contested_shots_2pt"),
    "ast": ("base_ast", "pass_potential_ast"),
    "reb": ("base_reb", "reb_reb_chances"),
    "threes": ("base_fg3m", "base_fg3a"),
}


def tables(season):
    """{label: a function that makes the nba_api request}. The label is the column prefix in the output file."""

    def tracking(measure):
        return lambda: leaguedashptstats.LeagueDashPtStats(
            season=season, pt_measure_type=measure, player_or_team="Player", per_mode_simple="Totals", timeout=60
        )

    return {
        "base": lambda: leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, measure_type_detailed_defense="Base", per_mode_detailed="Totals", timeout=60
        ),
        "hustle": lambda: leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season, per_mode_time="Totals", timeout=60
        ),
        "pass": tracking("Passing"),
        "reb": tracking("Rebounding"),
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


def add_chances(out, season):
    """Put the season column and the makes and chances columns of CHANCES after the gp column.

    Raise ValueError when the tables do not give a column of CHANCES. Then a change at NBA.com cannot go unseen.
    """
    missing = [c for pair in CHANCES.values() for c in pair if c not in out]
    if missing:
        raise ValueError(f"NBA.com did not give these columns: {', '.join(missing)}")
    front = {"season": season}
    for category, (makes, chances) in CHANCES.items():
        front[f"{category}_makes"] = out[makes]
        front[f"{category}_chances"] = out[chances]
    at = out.columns.get_loc("gp") + 1
    return pd.concat([out.iloc[:, :at], pd.DataFrame(front, index=out.index), out.iloc[:, at:]], axis=1)


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


def write_csv(frame, path):
    """Write the CSV file in one step. A crash during the write keeps the old file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    work = path.with_name(path.name + ".tmp")
    frame.to_csv(work, index=False)
    os.replace(work, path)


def output_paths(season, current, out=None, today=None):
    """(the output file, the dated copy or None). Only the current season gets a dated copy.

    The default output file is data/nba_stats.csv for the current season and data/nba_stats_<season>.csv for
    another season. The dated copy goes in the nba_stats folder next to the output file.
    """
    path = Path(out) if out else OUT_FILE if season == current else DATA / f"nba_stats_{season}.csv"
    if season != current:
        return path, None
    return path, path.parent / SNAPSHOT_DIR / f"{(today or date.today()).isoformat()}.csv"


def main(argv=None, get=get_table, today=None):
    """Download the 5 tables, merge them and write the files. Return 0, or 1 when a request fails.

    get takes the label and the request function and returns the table (default get_table()). today is the date of
    the dated copy (default the date of the run).
    """
    current = nba_season(load_config()["league"]["espn_season"])
    parser = argparse.ArgumentParser(
        prog="python -m fantasyhoops.fetch.nba_stats", description="Download the NBA.com stats of a season."
    )
    parser.add_argument(
        "--season", default=current, help=f"The NBA.com season, for example 2025-26 (default {current})."
    )
    parser.add_argument("--out", help="The output file. The default depends on the season. See the module docstring.")
    args = parser.parse_args(argv)
    path, snapshot = output_paths(args.season, current, args.out, today)

    frames = {}
    try:
        for label, request in tables(args.season).items():
            frames[label] = get(label, request)
            print(f"{label}: {len(frames[label])} players")
        out = add_chances(merge_tables(frames), args.season)
    except (RuntimeError, ValueError) as err:
        print(f"No file written. {err}")
        return 1
    write_csv(out, path)
    print(f"Wrote {path} ({len(out)} players, {len(out.columns)} columns, season {args.season})")
    if snapshot:
        write_csv(out, snapshot)
        print(f"Wrote {snapshot}")
    return 0


if __name__ == "__main__":
    use_utf8_output()
    sys.exit(main())
