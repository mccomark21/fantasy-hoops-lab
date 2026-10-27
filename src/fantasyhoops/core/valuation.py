"""Player value from per-game category stats and config.toml.

  1. Per-game z-score for each category, multiplied by its weight -> pg_value.
     The mean and the standard deviation come from the player pool (teams x roster_spots).
  2. pg_value minus replacement level -> pg_var (value above a waiver player).
  3. Final value: pg_var x (games / full_season) ^ power.
  4. Auction dollars: the teams buy the top teams x spots players by value. Each bought player gets min_bid.
     The rest of the money (teams x budget) goes to the bought players in proportion to value above
     replacement. Here, replacement is the first player who is not bought. That player and all players
     below get $0.
The first pool is the players with the most minutes. Each later pass uses the players with the most value.

Other tools value any per-game stat line with the same formula: get the scale of the pool once with
category_scale(), then call pg_value() for each line.
"""

import numpy as np
import pandas as pd

PASSES = 5


def value_players(players, cfg):
    """Return a copy of players with pg_value, z_<cat>, pg_var, value and dollars added.

    players needs player_id, minutes, games and one per-game column for each category in cfg["weights"].
    """
    return _value(players, cfg)[0]


def category_scale(players, cfg):
    """Mean and standard deviation of each category in the player pool of the last pass of value_players().

    players is the same input as for value_players(). The result is a DataFrame with the rows "mean" and "std"
    and one column for each category in cfg["weights"]. Give it to pg_value().
    """
    return _value(players, cfg)[1]


def pg_value(line, scale, cfg):
    """Per-game value of a per-game stat line: the z-score of each category x its weight in cfg["weights"].

    line is a Series (one stat line, the result is a float) or a DataFrame (one stat line in each row, the result
    is a Series). It needs one per-game column for each category in cfg["weights"]: pts, reb, ast, threes
    (3-pointers made), blk and stl with the default config. Rename other names first, for example Yahoo's 3PTM
    to threes. Other columns have no effect. Use per-game stats, not totals.
    scale comes from category_scale(). With the scale of the draft pool, the result is the pg_value of
    value_players(). It does not include replacement level or games played.
    """
    weights = pd.Series(cfg["weights"])
    z = _z(line, scale, weights.index)
    return (z * weights).sum(axis=z.ndim - 1)


def _value(players, cfg):
    """value_players() and the category scale of its last pass."""
    df = players.copy()
    pool_size = cfg["league"]["teams"] * cfg["league"]["roster_spots"]
    pool_ids = df.nlargest(pool_size, "minutes").player_id
    for n in range(PASSES):
        scale = _score(df, cfg, pool_ids, rank_by="pg_value" if n == 0 else "value")
        pool_ids = df.nlargest(pool_size, "value").player_id
    df["dollars"] = _dollars(df.value, cfg)
    return df, scale


def _z(line, scale, cats):
    """z-score of each category in cats."""
    return (line[cats] - scale.loc["mean", cats]) / scale.loc["std", cats]


def _dollars(value, cfg):
    """Auction dollars for each player. The dollars of the bought players add up to teams x budget."""
    teams, a = cfg["league"]["teams"], cfg["auction"]
    ranked = value.sort_values(ascending=False)
    n = teams * a["spots"]
    bought, replacement = ranked.index[:n], ranked.iloc[n]
    # The waiver tier in _score uses a different cutoff, so value can be below 0 for a bought player
    above = value[bought] - replacement
    spare = teams * a["budget"] - n * a["min_bid"]
    dollars = pd.Series(0.0, index=value.index)
    dollars[bought] = a["min_bid"] + spare * above / above.sum()
    return dollars


def _score(df, cfg, pool_ids, rank_by):
    """One pass. Changes df and returns the category scale of the pool.

    rank_by="value" uses the value from the pass before to find the waiver tier.
    """
    weights = pd.Series(cfg["weights"])
    pool = df[df.player_id.isin(pool_ids)]
    scale = pd.DataFrame({"mean": pool[weights.index].mean(), "std": pool[weights.index].std()}).T
    z = _z(df, scale, weights.index)
    df["pg_value"] = (z * weights).sum(axis=1)
    for cat in weights.index:
        df["z_" + cat] = z[cat]

    # Replacement level: average player in the first waiver tier
    pool_size = len(pool_ids)
    tier = df.sort_values(rank_by, ascending=False).iloc[pool_size : pool_size + cfg["league"]["teams"]]
    df["pg_var"] = df.pg_value - tier.pg_value.mean()

    g = cfg["games"]
    played = (df.games / g["full_season"]).clip(upper=1)
    value = df.pg_var * played ** g["power"]
    # Do not reward a player below replacement for missing games
    df["value"] = np.where(df.pg_var < 0, df.pg_var, value)
    return scale
