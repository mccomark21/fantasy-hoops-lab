"""Read the rotation log: starts, minutes and closes of each player in each game.

fetch/rotation.py writes the log. This module writes no file.
Inputs:
  data/rotation_log.csv     - one row for each stint (a check-in to the next check-out in one period)
  data/rotation_scores.csv  - one row for each play that changes the score
A close game: at some moment in the last close_minutes of the fourth quarter or of an overtime period,
the margin is close_margin points or fewer. A close: the player is on the floor at the end of a close game.
The settings are in [rotation] in config.toml.
"""

import pandas as pd

from fantasyhoops.core.common import DATA

LOG = DATA / "rotation_log.csv"
SCORES = DATA / "rotation_scores.csv"
BOX_SCORES = DATA / "box_scores.csv"  # fetch/rotation.py writes it. This module does not read it.
QUARTER = 720  # seconds
OVERTIME = 300
QUARTERS = 4


def period_bounds(period):
    """(seconds from the start of the game to the start of the period, length of the period in seconds)."""
    if period <= QUARTERS:
        return (period - 1) * QUARTER, QUARTER
    return QUARTERS * QUARTER + (period - QUARTERS - 1) * OVERTIME, OVERTIME


def read_log(path=LOG):
    """The stints in the log. dtype str keeps the ESPN IDs as text."""
    return pd.read_csv(path, dtype={"game_id": str, "player_id": str}, parse_dates=["date"])


def read_scores(path=SCORES):
    """The score changes. A run that stopped can write a game two times. This function removes the duplicate rows."""
    return pd.read_csv(path, dtype={"game_id": str}).drop_duplicates()


def close_games(stints, scores, cfg):
    """One row for each game: game_id, close (True or False). The windows are the last close_minutes of each period from the fourth."""
    margin, window = cfg["rotation"]["close_margin"], cfg["rotation"]["close_minutes"] * 60
    by_game = {game_id: game.sort_values("sec") for game_id, game in scores.groupby("game_id")}
    empty = scores.iloc[0:0]
    rows = []
    for game_id, periods in stints.groupby("game_id")["period"]:
        game = by_game.get(game_id, empty)
        diff = (game.home_score - game.away_score).abs().to_numpy()
        secs = game.sec.to_numpy()
        close = False
        for period in range(QUARTERS, int(periods.max()) + 1):
            start, length = period_bounds(period)
            end = start + length
            begin = end - window
            before = diff[secs <= begin]
            at_start = before[-1] if len(before) else 0
            inside = diff[(secs > begin) & (secs <= end)]
            if min([at_start, *inside]) <= margin:
                close = True
        rows.append({"game_id": game_id, "close": close})
    return pd.DataFrame(rows, columns=["game_id", "close"])


def player_games(stints, scores, cfg):
    """One row for each player in each game that he played.

    Columns: game_id, date, team, opponent, player_id, player, started, minutes, close_game, closed.
    closed is True when the game is a close game and the player is on the floor at the end of it.
    """
    stints = stints.assign(sec=stints.out_sec - stints.in_sec)
    end = stints.groupby("game_id").out_sec.transform("max")
    stints = stints.assign(at_end=stints.out_sec == end)
    games = stints.groupby(["game_id", "date", "team", "opponent", "player_id", "player"], as_index=False).agg(
        started=("starter", "any"), sec=("sec", "sum"), at_end=("at_end", "any")
    )
    games = games.merge(
        close_games(stints, scores, cfg).rename(columns={"close": "close_game"}), on="game_id", how="left"
    )
    games["close_game"] = games.close_game.fillna(False).astype(bool)
    games["minutes"] = (games.pop("sec") / 60).round(1)
    games["closed"] = games.close_game & games.pop("at_end")
    return games[
        ["game_id", "date", "team", "opponent", "player_id", "player", "started", "minutes", "close_game", "closed"]
    ]


def team_games(stints, scores, cfg):
    """One row for each team in each game: game_id, date, team, opponent, close_game.

    The close games of a team in a date range: team_games(...).query("close_game") with a date filter.
    """
    teams = stints[["game_id", "date", "team", "opponent"]].drop_duplicates()
    close = close_games(stints, scores, cfg).rename(columns={"close": "close_game"})
    return teams.merge(close, on="game_id", how="left").reset_index(drop=True)
