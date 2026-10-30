"""Read the rotation log: starts, minutes and closes of each player in each game.

fetch/rotation.py writes the log. This module writes no file.
Inputs:
  data/rotation_log.csv     - one row for each stint (a check-in to the next check-out in one period)
  data/rotation_scores.csv  - one row for each play that changes the score
A close game: at some moment in the last close_minutes of the fourth quarter or of an overtime period,
the margin is close_margin points or fewer. A close: the player is on the floor at the end of a close game.
Competitive minutes: the minutes of a player while the game is not decided. A game is decided while the lead is
the lead needed or more. Lead needed = z x decided_sigma x the square root of the seconds left, with z from
decided_win_chance. In regulation, the seconds left go to the end of the fourth quarter. In an overtime period,
they go to the end of that period.
The settings are in [rotation] in config.toml.
"""

from statistics import NormalDist

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


def lead_needed(sec_left, cfg):
    """The lead in points that makes a game decided with sec_left seconds left."""
    rot = cfg["rotation"]
    return NormalDist().inv_cdf(rot["decided_win_chance"]) * rot["decided_sigma"] * sec_left**0.5


def decided_spans(game_scores, game_end, cfg):
    """The (start, end) seconds of each span in which the game is decided. game_scores: the score rows of one game.

    The lead stays the same from one scoring play to the next. The lead needed gets smaller while the clock runs.
    The game becomes decided when the lead needed falls to the lead. A comeback makes the game not decided again.
    """
    rot = cfg["rotation"]
    scale = NormalDist().inv_cdf(rot["decided_win_chance"]) * rot["decided_sigma"]
    regulation = QUARTERS * QUARTER
    rows = game_scores.sort_values("sec", kind="stable")
    times, leads = [0.0], [0]
    for sec, home, away in zip(rows.sec, rows.home_score, rows.away_score):
        if sec == times[-1]:
            leads[-1] = abs(home - away)  # the last play at the same second gives the score
        else:
            times.append(float(sec))
            leads.append(abs(home - away))
    # The ends of the time blocks: the end of regulation, then the end of each overtime period.
    ends = [regulation]
    while ends[-1] < game_end:
        ends.append(ends[-1] + OVERTIME)
    spans = []
    for i, lead in enumerate(leads):
        start = times[i]
        stop = times[i + 1] if i + 1 < len(times) else max(game_end, start)
        if lead <= 0:
            continue
        for block_end in ends:
            block_start = block_end - (regulation if block_end == regulation else OVERTIME)
            a, b = max(start, block_start), min(stop, block_end)
            if a >= b:
                continue
            a = max(a, block_end - (lead / scale) ** 2)  # from here on, the lead needed is the lead or less
            if a < b:
                if spans and spans[-1][1] == a:
                    spans[-1] = (spans[-1][0], b)
                else:
                    spans.append((a, b))
    return spans


def competitive_minutes(stints, scores, cfg):
    """One row for each player in each game that he played: game_id, player_id, competitive_minutes.

    The minutes of his stints, minus the minutes in the decided spans of the game. Merge on player_games().
    """
    by_game = {game_id: game for game_id, game in scores.groupby("game_id")}
    empty = scores.iloc[0:0]
    rows = []
    for game_id, game in stints.groupby("game_id"):
        spans = decided_spans(by_game.get(game_id, empty), game.out_sec.max(), cfg)
        for player_id, own in game.groupby("player_id"):
            sec = 0.0
            for in_sec, out_sec in zip(own.in_sec, own.out_sec):
                sec += out_sec - in_sec
                sec -= sum(max(0.0, min(out_sec, b) - max(in_sec, a)) for a, b in spans)
            rows.append({"game_id": game_id, "player_id": player_id, "competitive_minutes": sec / 60})
    out = pd.DataFrame(rows, columns=["game_id", "player_id", "competitive_minutes"])
    out["competitive_minutes"] = out.competitive_minutes.round(1)  # the same rounding as the minutes of player_games()
    return out
