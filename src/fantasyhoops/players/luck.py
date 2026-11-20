"""The luck of each player in each category (#254): his makes this season against the makes that his chances expect.

Chances and makes come from the NBA.com stats files (fetch/nba_stats.py, docs/fetch/README.md):
STL = steals of deflections, BLK = blocks of contested 2-point shots, AST = assists of potential assists,
REB = rebounds of rebound chances, 3PM = 3-pointers made of 3-pointers attempted. PTS has no chance stat.

For each category, with n = chances this season and y = makes this season:
1. The baseline rate p0 comes from his row of the past season. p0 = (y_prev + k x league_prev) / (n_prev + k),
   multiplied by league_now / league_prev. The ratio removes a change of the league rate between the seasons,
   for example the new count of rebound chances in 2026-27. With no row of the past season, p0 = league_now.
2. Expected = n x p0.
3. Luck z = (y - n x p0) / sd. sd is the beta-binomial spread: n x p0 x (1 - p0) x (w + n) / (w + 1), square root,
   with w = n_prev + k (or k with no past row). The (w + n) / (w + 1) part is the doubt about p0. A negative z is
   unlucky.
4. A category is ready with min_games games or more and min_chances[category] chances or more. Only a ready
   category gets a z.
5. Overall luck = the sum of the ready z / the square root of their count (Stouffer). No ready category gives none.

The settings are in [players.luck] in config.toml: k, min_games and min_chances.
by_name_key() gives the luck row of a player by name_key(). The Luck page and the Free agents page (#255) use it,
so that both pages show the same value for one player. z_text() gives the text of a z on both pages.
read_luck() reads data/nba_stats.csv and data/nba_stats_<past season>.csv. The module writes no files.
"""

import math

import pandas as pd

from fantasyhoops.core import common

CATEGORIES = ("stl", "blk", "ast", "reb", "threes")  # the keys of [weights] in config.toml
LABELS = {"stl": "STL", "blk": "BLK", "ast": "AST", "reb": "REB", "threes": "3PM"}
RATE_LIMITS = (0.001, 0.999)  # p0 stays in this range, so that the spread is above 0
MINUS = "−"


def settings(cfg):
    """The [players.luck] settings of cfg as a dict: k, min_games and min_chances."""
    luck = cfg["players"]["luck"]
    return {"k": dict(luck["k"]), "min_games": luck["min_games"], "min_chances": dict(luck["min_chances"])}


def nba_season(espn_season):
    """The NBA.com season text from the ESPN season (the year that the season ends): 2027 -> "2026-27"."""
    return f"{espn_season - 1}-{espn_season % 100:02d}"


def league_rates(frame):
    """{category: the makes of all players / the chances of all players}. A row with no chances adds nothing."""
    rates = {}
    for cat in CATEGORIES:
        rows = frame[frame[f"{cat}_chances"].notna() & frame[f"{cat}_makes"].notna()]
        chances = rows[f"{cat}_chances"].sum()
        rates[cat] = rows[f"{cat}_makes"].sum() / chances if chances > 0 else None
    return rates


def _missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def baseline(prev_makes, prev_chances, k, league_prev, league_now):
    """(p0, w): the baseline rate and its weight in chances.

    prev_makes, prev_chances: his row of the past season, or None (or NaN) when he has no row.
    p0 = (prev_makes + k x league_prev) / (prev_chances + k) x league_now / league_prev, and w = prev_chances + k.
    With no past row, or no league rate of the past season, p0 = league_now and w = k.
    """
    if _missing(prev_makes) or _missing(prev_chances) or not league_prev:
        p0, weight = league_now, k
    else:
        p0 = (prev_makes + k * league_prev) / (prev_chances + k) * league_now / league_prev
        weight = prev_chances + k
    return min(max(p0, RATE_LIMITS[0]), RATE_LIMITS[1]), weight


def luck_z(makes, chances, p0, weight):
    """(makes - chances x p0) / the beta-binomial spread. weight: the w of baseline(). None with no chances."""
    if _missing(chances) or _missing(makes) or chances <= 0:
        return None
    variance = chances * p0 * (1 - p0) * (weight + chances) / (weight + 1)
    return (makes - chances * p0) / math.sqrt(variance)


def is_ready(games, chances, min_games, min_chances):
    """True with min_games games or more and min_chances chances or more."""
    if _missing(games) or _missing(chances):
        return False
    return games >= min_games and chances >= min_chances


def overall(zs):
    """Stouffer: the sum of the z / the square root of their count. None values do not count. None if none."""
    values = [z for z in zs if not _missing(z)]
    return sum(values) / math.sqrt(len(values)) if values else None


def luck_table(current, previous, cfg):
    """One row for each player of current: the luck of each category and the overall luck.

    current, previous: frames in the shape of data/nba_stats.csv. previous can be None (no file of the past season).
    The columns: nba_id, name, name_key, team, gp, then for each category <cat>_chances_pg, <cat>_makes_pg,
    <cat>_expected_pg, <cat>_p0, <cat>_ready and <cat>_z (NaN when not ready), then luck (NaN with no ready
    category) and luck_count (the number of ready categories).
    """
    s = settings(cfg)
    now = league_rates(current)
    before = league_rates(previous) if previous is not None else dict.fromkeys(CATEGORIES)
    past = previous.set_index("nba_id") if previous is not None else None
    out = []
    for row in current.itertuples(index=False):
        rec = {key: getattr(row, key) for key in ("nba_id", "name", "name_key", "team", "gp")}
        prev = past.loc[row.nba_id] if past is not None and row.nba_id in past.index else None
        zs = []
        for cat in CATEGORIES:
            makes, chances = getattr(row, f"{cat}_makes"), getattr(row, f"{cat}_chances")
            prev_makes = prev[f"{cat}_makes"] if prev is not None else None
            prev_chances = prev[f"{cat}_chances"] if prev is not None else None
            if now[cat] is None:  # no player has chances in this category
                p0, weight = math.nan, None
            else:
                p0, weight = baseline(prev_makes, prev_chances, s["k"][cat], before[cat], now[cat])
            ready = weight is not None and is_ready(row.gp, chances, s["min_games"], s["min_chances"][cat])
            z = luck_z(makes, chances, p0, weight) if ready else None
            games = row.gp if row.gp else math.nan
            rec[f"{cat}_chances_pg"] = chances / games
            rec[f"{cat}_makes_pg"] = makes / games
            rec[f"{cat}_expected_pg"] = chances * p0 / games
            rec[f"{cat}_p0"] = p0
            rec[f"{cat}_ready"] = ready
            rec[f"{cat}_z"] = math.nan if z is None else z
            zs.append(z)
        luck = overall(zs)
        rec["luck"] = math.nan if luck is None else luck
        rec["luck_count"] = sum(z is not None for z in zs)
        out.append(rec)
    return pd.DataFrame(out)


def by_name_key(table):
    """{name_key: the row of table as a dict}. table: luck_table() or read_luck(). None gives {}.

    A fantasy name finds its luck row by common.name_key(). With two rows of one key, the first row stays.
    A value that is NaN in table is None in the dict.
    """
    if table is None:
        return {}
    out = {}
    for rec in table.to_dict("records"):
        out.setdefault(rec["name_key"], {k: None if _missing(v) else v for k, v in rec.items()})
    return out


def z_text(z):
    """The z with its sign and 2 decimals, for example "+1.23" or "−0.40". None (or NaN) gives an en dash."""
    if _missing(z):
        return "–"
    sign = "+" if z > 0 else MINUS if z < 0 else ""
    return f"{sign}{abs(z):.2f}"


def read_luck(cfg, data_dir=None):
    """luck_table() of the files in data_dir (default data/). None when data/nba_stats.csv is missing.

    The past season comes from [league] espn_season: 2027 reads data/nba_stats_2025-26.csv. A missing file of the
    past season gives each player the league rate of this season as p0.
    """
    folder = data_dir or common.DATA
    current_file = folder / "nba_stats.csv"
    if not current_file.exists():
        return None
    past_file = folder / f"nba_stats_{nba_season(cfg['league']['espn_season'] - 1)}.csv"
    previous = pd.read_csv(past_file) if past_file.exists() else None
    return luck_table(pd.read_csv(current_file), previous, cfg)
