"""The Comps quadrant of the player card (#189): the COUNT nearest players in weighted z-score space.

- The blended line of a player: his projected per-game line (the newest projections file) moved toward his ESPN line
  of the last RECENT_DAYS days (data/box_scores.csv, through value.read_games()), with adds/blend.blend_line().
  The weight of the ESPN line is his games in those days / RECENT_DAYS, 1 at most. This is the source of the
  approved sample. It needs no Yahoo read, so each player with a projection or recent ESPN games has comps.
- The weighted z-score of a category: (line - pool mean) / pool standard deviation x the category weight of
  config.toml. The pool scale is the scale of the projections file (adds/value.projection_scale()).
- The distance: the Euclidean distance of the weighted z-scores of two players. The nearest come first.
- The biggest difference: the category with the largest |his z - my z|, as "their weighted z minus his".
attach() adds the "comps" list of each player of the player file. The browser script is core/card_value.py.
read_lines() reads the newest projections file. The module writes no files.
"""

import math
from datetime import timedelta

import pandas as pd

from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.identity import yahoo_keys
from fantasyhoops.draft.rankings import STATS

COUNT = 5  # the comps of a player
RECENT_DAYS = 14  # the days of the ESPN line, as the recent line of adds/blend.py
LABELS = {"pts": "PTS", "reb": "REB", "ast": "AST", "threes": "3PM", "stl": "STL", "blk": "BLK"}


def projected_lines(projections, overrides):
    """{Yahoo name key: per-game line} of the rows of a projections table with games > 0.

    overrides: data/name_overrides.csv, for the Yahoo name of a projection row. Two rows with one key: the row
    with more minutes is in the result.
    """
    df = projections[projections.games > 0].copy()
    if df.empty:
        return {}
    yahoo_names = dict(zip(overrides.player_id, overrides.yahoo_name))
    to_yahoo = yahoo_keys(overrides)
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    out = {}
    for row in df.sort_values("minutes", ascending=False).itertuples():
        name = yahoo_names.get(str(row.player_id)) or f"{row.first_name} {row.last_name}"
        key = name_key(name)
        out.setdefault(to_yahoo.get(key, key), {cat: float(getattr(row, cat)) for cat in STATS})
    return out


def recent_line(games, today, days=RECENT_DAYS):
    """(The per-game line of the games in the days before today and on today, the number of those games)."""
    since = today - timedelta(days=days)
    found = [g for g in games if since < g.date <= today]
    if not found:
        return {}, 0
    return {cat: sum(g.line[cat] for g in found) / len(found) for cat in STATS}, len(found)


def blended_lines(projected, games, today):
    """{key: blended line} for each key with a projected line or ESPN games in the last RECENT_DAYS days.

    projected: projected_lines(). games: value.read_games().
    """
    from fantasyhoops.adds.blend import blend_line

    out = {}
    for key in {*projected, *games}:
        recent, n = recent_line(games.get(key, []), today)
        line = blend_line(projected.get(key, {}), recent, n)
        if line:
            out[key] = line
    return out


def read_lines(cfg, overrides, games, today):
    """blended_lines() with the newest projections file. Only the ESPN lines with no projections file."""
    try:
        projections = pd.read_csv(latest_projections(cfg))
    except FileNotFoundError:
        projections = None
    projected = {} if projections is None else projected_lines(projections, overrides)
    return blended_lines(projected, games, today)


def weighted_z(line, scale, cfg):
    """{category: weighted z-score} of a per-game line."""
    weights = cfg["weights"]
    return {c: (line[c] - scale.loc["mean", c]) / scale.loc["std", c] * w for c, w in weights.items()}


def nearest(me, others, count=COUNT):
    """The count nearest of others to me: [(key, distance, category, difference)], nearest first, then by key.

    me: {category: weighted z}. others: {key: {category: weighted z}}. The difference is theirs minus mine in the
    category with the largest absolute difference.
    """
    out = []
    for key, z in others.items():
        diffs = {c: z[c] - me[c] for c in me}
        cat = max(diffs, key=lambda c: abs(diffs[c]))
        out.append((key, math.sqrt(sum(d * d for d in diffs.values())), cat, diffs[cat]))
    return sorted(out, key=lambda t: (t[1], t[0]))[:count]


NO_LINE = "No projection and no recent games: no comps."


def attach(records, lines, overrides, scale, cfg):
    """Add the "comps" list to each record of data.player_records(): [{slug, dist, cat, diff}], or None.

    lines: read_lines(). The comps of a player are the other players of the records with a line. A record links to
    the others by slug, so the file does not repeat their name, team and Val.
    """
    to_yahoo = yahoo_keys(overrides)
    zs = {}
    for r in records:
        key = name_key(r["name"])
        line = lines.get(to_yahoo.get(key, key)) or lines.get(key)
        if line and scale is not None:
            zs[r["slug"]] = weighted_z(line, scale, cfg)
    for r in records:
        me = zs.get(r["slug"])
        if me is None:
            r["comps"] = None
            continue
        others = {slug: z for slug, z in zs.items() if slug != r["slug"]}
        r["comps"] = [
            {
                "slug": slug,
                "dist": round(float(dist), 2),
                "cat": LABELS.get(cat, cat.upper()),
                "diff": round(float(diff), 2),
            }
            for slug, dist, cat, diff in nearest(me, others)
        ]
