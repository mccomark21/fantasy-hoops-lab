"""The data of the Role quadrant of the player card (#187): the minutes trend of each player, game by game.

For each player game: the total minutes, the competitive minutes (core/rotation.py competitive_minutes(), #184),
a start or the bench, a close game and the usage rate (data/box_scores.csv, #183).
For the minutes: a rolling average (the hero line) and a band of the normal range. The band is the season mean
plus or minus band_sd x spread / the square root of window. The spread mixes the sample spread of his own games with
the league spread (league_spread()), which counts as prior_games games. A range exit is a rolling point outside the
band. The settings are in [players.role] in config.toml: window, band_min (the games that a band needs), flag_min
(the games that a range exit and its signal need), prior_games and band_sd.
band_exit() is the signal rule of the quadrant (players/data.py SIGNAL_RULES).
core/profile_role.py draws the chart in the browser from the "role" field of a player record.
The module reads data/rotation_log.csv, data/rotation_scores.csv and data/box_scores.csv in read_roles().
It writes no files.
"""

import math

import pandas as pd

from fantasyhoops.core import common
from fantasyhoops.core.common import name_key
from fantasyhoops.core.identity import yahoo_keys
from fantasyhoops.core.rotation import competitive_minutes, player_games, read_log, read_scores

QUADRANT = "role"  # the quadrant key of profile.QUADRANTS
SIGNAL_KIND = "Minutes"  # the kind of the band-exit signal chip


def settings(cfg):
    """The [players.role] settings of cfg as a dict: window, band_min, flag_min, prior_games and band_sd."""
    role = cfg["players"]["role"]
    return {k: role[k] for k in ("window", "band_min", "flag_min", "prior_games", "band_sd")}


def rolling(values, window):
    """The rolling mean of the last window values at each index. None before the window has its values."""
    return [None if i + 1 < window else sum(values[i + 1 - window : i + 1]) / window for i in range(len(values))]


def league_spread(minutes_by_player):
    """The pooled spread of the minutes of one player from game to game, across players.

    minutes_by_player: a list with the minutes of each player. A player with fewer than 2 games adds nothing.
    The result is the square root of the sum of the squared deviations / the sum of (games - 1). None if no player
    has 2 games.
    """
    squares = dof = 0.0
    for values in minutes_by_player:
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        squares += sum((v - mean) ** 2 for v in values)
        dof += len(values) - 1
    return math.sqrt(squares / dof) if dof else None


def band(values, prior_sd, cfg):
    """(low, high) of the normal range of values, or None with fewer than band_min values or no prior_sd.

    The spread: the square root of (the sum of the squared deviations + prior_games x prior_sd²) /
    (games - 1 + prior_games). The range: the mean ± band_sd x the spread / the square root of window.
    """
    s = settings(cfg)
    n = len(values)
    if n < s["band_min"] or prior_sd is None:
        return None
    mean = sum(values) / n
    squares = sum((v - mean) ** 2 for v in values)
    spread = math.sqrt((squares + s["prior_games"] * prior_sd**2) / (n - 1 + s["prior_games"]))
    half = s["band_sd"] * spread / math.sqrt(s["window"])
    return mean - half, mean + half


def exits(roll, low_high, games, cfg):
    """The range exits: [(index, "up" or "down")] of each rolling point outside the band.

    No band, or fewer than flag_min games, gives [].
    """
    if low_high is None or games < settings(cfg)["flag_min"]:
        return []
    low, high = low_high
    return [(i, "up" if v > high else "down") for i, v in enumerate(roll) if v is not None and (v > high or v < low)]


def state(games, low_high, cfg):
    """The state line under the chart as (lead words in bold, the rest), DESIGN.md "Thin data"."""
    s = settings(cfg)
    if low_high is None:
        return "Too few games for a range:", f"{games} of {s['band_min']}."
    half = f"{(low_high[1] - low_high[0]) / 2:.1f}"
    if games < s["flag_min"]:
        return (
            "Too few games for a flag:",
            f"{games} of {s['flag_min']}. Range = mean ± {half}, mostly the league prior.",
        )
    if games - 1 <= s["prior_games"]:
        return "", f"Range = mean ± {half}, mostly the league prior at {games} games."
    return "", f"Range = mean ± {half} at {games} games."


def _mean(values):
    return sum(values) / len(values) if values else None


def _r(value, digits=1):
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), digits)


def role_record(rows, prior_sd, cfg):
    """The "role" field of a player record from his player games, in date order. None with no game.

    rows: a table with date, opponent, started, minutes, close_game, competitive_minutes and usg (NaN: no usage).
    """
    if rows.empty:
        return None
    s = settings(cfg)
    minutes = [float(m) for m in rows.minutes]
    roll = rolling(minutes, s["window"])
    low_high = band(minutes, prior_sd, cfg)
    usages = [float(u) for u in rows.usg if not pd.isna(u)]
    usg = _mean(usages)
    usg_last = _mean(usages[-s["window"] :]) if len(usages) >= s["window"] else None
    close = [m for m, c in zip(minutes, rows.close_game) if c]
    other = [m for m, c in zip(minutes, rows.close_game) if not c]
    lead, rest = state(len(minutes), low_high, cfg)
    return {
        "window": s["window"],
        "games": [
            {
                "d": f"{r.date:%b} {r.date.day}",
                "opp": r.opponent,
                "min": _r(r.minutes),
                "comp": _r(r.competitive_minutes),
                "usg": _r(r.usg),
                "start": bool(r.started),
                "close": bool(r.close_game),
            }
            for r in rows.itertuples()
        ],
        "roll": [_r(v, 2) for v in roll],
        "lo": _r(max(0.0, low_high[0]), 2) if low_high else None,  # the chart shows no minutes below 0
        "hi": _r(low_high[1], 2) if low_high else None,
        "exits": exits(roll, low_high, len(minutes), cfg),
        "usg": _r(usg),
        "usg_last": _r(usg_last),
        "close_n": len(close),
        "close_min": _r(_mean(close)),
        "other_min": _r(_mean(other)),
        "state": [lead, rest],
    }


def game_table(stints, scores, box, cfg):
    """The player games of the Role quadrant: player_games() with competitive_minutes and usg, by date.

    box: data/box_scores.csv as a table (game_id, player_id, usg), or None. A game with no box row has no usage.
    """
    games = player_games(stints, scores, cfg).merge(
        competitive_minutes(stints, scores, cfg), on=["game_id", "player_id"], how="left"
    )
    if box is None or box.empty:
        games["usg"] = float("nan")
    else:
        usg = box[["game_id", "player_id", "usg"]].drop_duplicates(["game_id", "player_id"])
        games = games.merge(usg, on=["game_id", "player_id"], how="left")
    return games.sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)


def roles(games, overrides, cfg):
    """{Yahoo name key: the "role" field} of each player in games (game_table()).

    The key is the name key of his ESPN name in his last game, mapped to the Yahoo name key by the override rows, as
    in players/data.played_players(). Two players with one key: the player with more games.
    """
    if games.empty:
        return {}
    prior_sd = league_spread([list(g.minutes) for _, g in games.groupby("player_id")])
    to_yahoo = yahoo_keys(overrides)
    out, counts = {}, {}
    for _, rows in games.groupby("player_id", sort=False):
        key = name_key(rows.iloc[-1].player)
        key = to_yahoo.get(key, key)
        if counts.get(key, -1) >= len(rows):
            continue
        counts[key] = len(rows)
        out[key] = role_record(rows, prior_sd, cfg)
    return out


def read_roles(cfg, overrides):
    """roles() of the data files. No rotation log or no score file gives {}. No box-score file: no usage."""
    log, scores, box = (common.DATA / n for n in ("rotation_log.csv", "rotation_scores.csv", "box_scores.csv"))
    if not log.exists() or not scores.exists():
        return {}
    stints = read_log(log)
    if stints.empty:
        return {}
    table = pd.read_csv(box, dtype={"game_id": str, "player_id": str}) if box.exists() else None
    return roles(game_table(stints, read_scores(scores), table, cfg), overrides, cfg)


def band_exit(record):
    """The signal of a range exit: the last rolling point of the minutes is outside the band. Else None.

    The exit needs flag_min games (role_record() gives no exit with fewer). Above the band is a good sign.
    """
    from fantasyhoops.players.data import Signal

    role = record.get("role")
    if not role or not role["exits"] or role["exits"][-1][0] != len(role["games"]) - 1:
        return None
    up = role["exits"][-1][1] == "up"
    last = role["roll"][-1]
    where = "above" if up else "below"
    text = f"{role['window']}-game {last:.1f} min, {where} the range {role['lo']:.1f}–{role['hi']:.1f}"
    return Signal(SIGNAL_KIND, QUADRANT, up, text)
