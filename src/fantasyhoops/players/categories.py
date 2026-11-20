"""The data of the Categories quadrant of the player card (#188): a percentile for each weighted category.

Each category of [weights] in config.toml gets two percentiles (decision 4 of
docs/wiki/player-profile-design-2026-10-29.md):
1. "proj": the per-game projection of the player, ranked among the projections of the pool.
2. "now": the season line of the player, shrunk toward a target, ranked among the shrunk lines of the pool.
The pool is the valuation pool of core/valuation.py: the top teams x roster_spots players by projected value.
The shrunk line is (n x season + k x target) / (n + k). n is the number of games that he played in
data/box_scores.csv. k is the shrinkage strength in games, from [players.categories] shrink in config.toml.
The target (#253): for STL, BLK, AST, REB and 3PM, the expected makes per game of players/luck.py when the category
is ready there. Else, and always for PTS, the target is the projection per game.
A pool player with no game has his target as his shrunk line.
A percentile is the mid-rank percentile: 100 x (players below + half of the players equal) / pool size.

projection_gap() is the signal rule of the quadrant (players/data.py SIGNAL_RULES).
read_categories() reads the projections file, data/box_scores.csv, data/name_overrides.csv and the NBA.com stats
files of players/luck.py. The module writes no files.
"""

import pandas as pd

from fantasyhoops.core import common
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.identity import yahoo_keys
from fantasyhoops.core.valuation import value_players
from fantasyhoops.draft.rankings import STATS
from fantasyhoops.players import luck

# The name of each category of [weights] on the card, and its column in data/box_scores.csv.
LABELS = {"pts": "PTS", "reb": "REB", "ast": "AST", "threes": "3PM", "blk": "BLK", "stl": "STL"}
BOX_COLUMNS = {"pts": "pts", "reb": "reb", "ast": "ast", "threes": "fg3m", "blk": "blk", "stl": "stl"}
GAP_KIND = "Projection gap"  # the kind of the signal chip
EXPECTED, PROJECTION = "expected", "proj"  # the "toward" value of a row: the source of its target


def settings(cfg):
    """[players.categories] of config.toml: shrink ({category: games}), gap_points and gap_games."""
    return cfg["players"]["categories"]


def projected_lines(projections, overrides, cfg):
    """(the per-game projection of each player, the name keys of the pool).

    projections: a projections table. overrides: data/name_overrides.csv as text. The result has one row for each
    Yahoo name key, with one column for each category of cfg["weights"]. Two rows with one key: the row with the
    higher value stays. The pool is the top teams x roster_spots name keys by value (core/valuation.py).
    """
    df = projections[projections.games > 0].copy()
    if df.empty:
        return pd.DataFrame(columns=list(cfg["weights"])), []
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    df = value_players(df, cfg)
    yahoo_names = dict(zip(overrides.player_id, overrides.yahoo_name))
    names = [yahoo_names.get(str(i)) or f"{f} {last}" for i, f, last in zip(df.player_id, df.first_name, df.last_name)]
    df["key"] = [name_key(n) for n in names]
    pool_size = cfg["league"]["teams"] * cfg["league"]["roster_spots"]
    # One row for each key: the row with the higher value. The pool then has pool_size different players.
    lines = df.sort_values("value", ascending=False).drop_duplicates("key").set_index("key")
    return lines[list(cfg["weights"])], lines.index[:pool_size].tolist()


def season_lines(box, overrides, cats):
    """(the per-game season line of each player, his games) from a box-score table, by Yahoo name key.

    box: data/box_scores.csv. Only the rows with played True count. cats: the categories, for example
    list(cfg["weights"]). The result has one column for each category and the column "games".
    """
    rows = box[box.played.astype(str).str.lower() == "true"]
    if rows.empty:
        return pd.DataFrame(columns=[*cats, "games"])
    to_yahoo = yahoo_keys(overrides)
    keys = rows.player.map(name_key)
    rows = rows.assign(key=keys.map(lambda k: to_yahoo.get(k, k)))
    sums = rows.groupby("key")[[BOX_COLUMNS[c] for c in cats]].sum()
    sums.columns = cats
    games = rows.groupby("key").game_id.nunique()
    return sums.div(games, axis=0).assign(games=games)


def expected_lines(table, overrides, cats):
    """The expected makes per game of each player, by Yahoo name key, in the ready categories only.

    table: luck.luck_table() or luck.read_luck(), or None. The result has one column for each category of cats that
    luck.CATEGORIES has. A category that is not ready is NaN. Two rows with one key: the row with more games stays.
    """
    cols = [c for c in cats if c in luck.CATEGORIES]
    if table is None or table.empty:
        return pd.DataFrame(columns=cols)
    to_yahoo = yahoo_keys(overrides)
    keys = table.name_key.map(lambda k: to_yahoo.get(k, k))
    rows = table.assign(key=keys).sort_values("gp", ascending=False).drop_duplicates("key").set_index("key")
    out = pd.DataFrame(index=rows.index)
    for cat in cols:
        ready = rows[f"{cat}_ready"].fillna(False).astype(bool)
        out[cat] = rows[f"{cat}_expected_pg"].where(ready)
    return out


def targets(proj, expected, cats):
    """(the target of each player and category, True where the target is the expected value).

    proj: the per-game projections. expected: expected_lines(). The target is the expected value where it is
    there. Else it is the projection.
    """
    target, is_expected = proj[cats].astype(float).copy(), pd.DataFrame(False, index=proj.index, columns=cats)
    for cat in cats:
        if expected is None or cat not in expected:
            continue
        exp = pd.to_numeric(expected[cat], errors="coerce").reindex(proj.index)
        is_expected[cat] = exp.notna()
        target[cat] = exp.where(exp.notna(), target[cat])
    return target, is_expected


def percentile(value, population):
    """The mid-rank percentile of value in population: 100 x (values below + half of the values equal) / size."""
    below = sum(v < value for v in population)
    equal = sum(v == value for v in population)
    return float(100 * (below + equal / 2) / len(population))


def _shrunk(target, season, cats, shrink):
    """The shrunk lines of the players of target: (n x season + k x target) / (n + k), and n."""
    games = season.games.reindex(target.index).fillna(0)
    out = pd.DataFrame(index=target.index)
    for cat in cats:
        raw = season[cat].reindex(target.index).fillna(0)
        k = shrink[cat]
        out[cat] = (games * raw + k * target[cat]) / (games + k)
    return out, games


def category_records(proj, pool, season, cfg, expected=None):
    """{name key: the cats of the player file} for each player of proj, the per-game projections.

    pool: the name keys of the pool. season: season_lines(). expected: expected_lines(), or None (each target is
    the projection). The cats have n (the games), pool (the pool size), rows and gap. Each row has cat, w (the punt
    weight), k, proj and now (the percentiles), line (the projection per game), raw (the season per game, or None
    with no game), target, toward ("expected" or "proj": the source of the target), shrunk and nw (the weight of the
    season line).
    gap is the row with the largest gap of gap_points or more percentile points, with gap_games or more games, as
    {cat, now, proj}. Else None.
    """
    cats, conf = list(cfg["weights"]), settings(cfg)
    pool = [k for k in pool if k in proj.index]
    if proj.empty or not pool:
        return {}
    target, is_expected = targets(proj, expected, cats)
    shrunk, games = _shrunk(target, season, cats, conf["shrink"])
    pop_proj = {c: proj.loc[pool, c].tolist() for c in cats}
    pop_now = {c: shrunk.loc[pool, c].tolist() for c in cats}
    out = {}
    for key in proj.index:
        n = int(games[key])
        rows = []
        for cat in cats:
            k = conf["shrink"][cat]
            rows.append(
                {
                    "cat": LABELS.get(cat, cat.upper()),
                    "w": float(cfg["weights"][cat]),
                    "k": k,
                    "proj": round(percentile(proj.at[key, cat], pop_proj[cat]), 1),
                    "now": round(percentile(shrunk.at[key, cat], pop_now[cat]), 1),
                    "line": round(float(proj.at[key, cat]), 2),
                    "raw": round(float(season.at[key, cat]), 2) if n else None,
                    "target": round(float(target.at[key, cat]), 2),
                    "toward": EXPECTED if is_expected.at[key, cat] else PROJECTION,
                    "shrunk": round(float(shrunk.at[key, cat]), 2),
                    "nw": round(n / (n + k), 2),
                }
            )
        out[key] = {"n": n, "pool": len(pool), "rows": rows, "gap": _gap(rows, n, conf)}
    return out


def _gap(rows, n, conf):
    if n < conf["gap_games"]:
        return None
    big = [r for r in rows if abs(r["now"] - r["proj"]) >= conf["gap_points"]]
    if not big:
        return None
    r = max(big, key=lambda r: abs(r["now"] - r["proj"]))
    return {"cat": r["cat"], "now": round(r["now"]), "proj": round(r["proj"])}


def projection_gap(record):
    """The signal rule of the Categories quadrant: a Signal for the gap of the cats of record, or None.

    The text is, for example, "REB above projection: percentile 62 vs 25". Above is a good sign (up).
    """
    from fantasyhoops.players.data import Signal

    gap = (record.get("cats") or {}).get("gap")
    if not gap:
        return None
    up = gap["now"] > gap["proj"]
    text = f"{gap['cat']} {'above' if up else 'below'} projection: percentile {gap['now']} vs {gap['proj']}"
    return Signal(GAP_KIND, "cats", up, text)


def _csv(name, **kwargs):
    path = common.DATA / name
    return pd.read_csv(path, **kwargs) if path.exists() else None


def read_categories(cfg):
    """category_records() from the newest projections file and data/box_scores.csv. {} with no projections file.

    With no box-score file, each player has 0 games, so "now" is his target. With no data/nba_stats.csv, each
    target is the projection.
    """
    try:
        path = latest_projections(cfg)
    except FileNotFoundError:
        return {}
    overrides = _csv("name_overrides.csv", dtype=str)
    overrides = (
        pd.DataFrame(columns=["player_id", "name", "espn_name", "yahoo_name"]) if overrides is None else overrides
    )
    overrides = overrides.fillna("")
    proj, pool = projected_lines(pd.read_csv(path), overrides, cfg)
    box = _csv("box_scores.csv", dtype={"game_id": str, "player_id": str})
    cats = list(cfg["weights"])
    season = pd.DataFrame(columns=[*cats, "games"]) if box is None else season_lines(box, overrides, cats)
    expected = expected_lines(luck.read_luck(cfg), overrides, cats)
    return category_records(proj, pool, season, cfg, expected)
