"""Season value (#222): the custom value of a player on his season-to-date stats, blended with his projection.

Each page that shows Val reads it from this module. No page computes it. The formula:
1. Per-game value: pg_value() of core/valuation.py on his season-to-date per-game line of data/box_scores.csv (only
   the rows with played True). The category scale is the scale of the projections file, so a few games do not
   move the scale.
2. Blend: per-game value = w x season-to-date value + (1 - w) x projection value. w = min(games played,
   blend_games) / blend_games, with [season_value] blend_games in config.toml. A player with 0 games gets the
   projection value. A player with no projection gets the season-to-date value.
3. Availability: the games factor of the draft formula, (share of games) ^ [games] power. The season share is
   games played / the games of his NBA team so far. The projection share is projected games / [games] full_season.
   The two shares blend with the same w.
4. Val = per-game value minus the replacement value. A Val above 0 gets the availability factor. A Val below 0 does
   not, as in core/valuation.py. The replacement value is the per-game value of the replacement free agent of the
   planning run (adds/value.py season_replacement()).
The names match as in players/data.py: a projection row gets its Yahoo name from data/name_overrides.csv, and a
box-score name maps to its Yahoo name with core/identity.py yahoo_keys().
read_season_lines() reads the newest projections file, data/box_scores.csv and data/name_overrides.csv. The module
writes no files.
"""

from dataclasses import dataclass

import pandas as pd

from fantasyhoops.core import common
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.identity import yahoo_keys
from fantasyhoops.core.valuation import category_scale, pg_value, projection_lines

# The column of each category of [weights] in data/box_scores.csv
BOX_COLUMNS = {"pts": "pts", "reb": "reb", "ast": "ast", "threes": "fg3m", "blk": "blk", "stl": "stl"}


@dataclass(frozen=True)
class SeasonLine:
    """The season value of one player before the replacement value.

    name: his Yahoo name if data/name_overrides.csv gives one, else the projection name or the ESPN name.
    games: his games played in the box scores. weight: the blend weight w of the season-to-date line.
    pg_value: the blended per-game value. share: the blended share of games (0 to 1) for the availability factor.
    """

    name: str
    games: int
    weight: float
    pg_value: float
    share: float


def blend_games(cfg):
    """[season_value] blend_games of config.toml: from this number of games, Val uses the season-to-date line only."""
    return cfg["season_value"]["blend_games"]


def blend_weight(games, cfg):
    """The weight w of the season-to-date line: min(games, blend_games) / blend_games."""
    n = blend_games(cfg)
    return min(games, n) / n


def line_val(line, replacement, power):
    """The Val of a SeasonLine: pg_value - replacement, times share ^ power when it is above 0. power: [games] power."""
    above = line.pg_value - replacement
    return above if above < 0 else above * line.share**power


def _projected(projections, overrides, cfg, scale):
    """{Yahoo name key: (name, per-game value, share)} of the projection rows with games > 0.

    Two rows with one key: the row with the higher per-game value stays, as in players/data.py (pg_var).
    """
    df = projections[projections.games > 0]
    if df.empty:
        return {}
    df = projection_lines(df)
    df["pg"] = pg_value(df, scale, cfg)
    yahoo_names = dict(zip(overrides.player_id, overrides.yahoo_name))
    df["shown"] = [
        yahoo_names.get(str(i)) or f"{f} {last}" for i, f, last in zip(df.player_id, df.first_name, df.last_name)
    ]
    df["share"] = (df.games / cfg["games"]["full_season"]).clip(upper=1).astype(float)
    out = {}
    for row in df.sort_values("pg", ascending=False).itertuples():
        out.setdefault(name_key(row.shown), (row.shown, float(row.pg), float(row.share)))
    return out


def _played(box, overrides, cfg, scale):
    """{Yahoo name key: (name, games, per-game value, share)} of the box-score rows with played True.

    share: his games / the games of his NBA team in his last game so far, 1 at most. Two ESPN IDs with one key: the ID
    with more games stays.
    """
    rows = box[box.played.astype(str).str.lower() == "true"]
    if rows.empty:
        return {}
    team_games = box.groupby("team").game_id.nunique()
    to_yahoo = yahoo_keys(overrides)
    cats = list(cfg["weights"])
    out = {}
    for _, own in rows.sort_values("date").groupby("player_id", sort=False):
        last = own.iloc[-1]
        key = name_key(last.player)
        key = to_yahoo.get(key, key)
        games = int(own.game_id.nunique())
        line = pd.Series({c: own[BOX_COLUMNS[c]].sum() / games for c in cats})
        share = min(games / float(team_games.get(last.team, games)), 1.0)
        if key not in out or games > out[key][1]:
            out[key] = (str(last.player), games, float(pg_value(line, scale, cfg)), share)
    return out


def season_lines(projections, box, overrides, cfg, scale=None):
    """{Yahoo name key: SeasonLine} of the players of a projections table and a box-score table.

    projections: a projections table. box: data/box_scores.csv as a table. overrides: data/name_overrides.csv as text
    (dtype=str, fillna("")). scale: the category scale. None: the scale of the projections (category_scale()).
    """
    if scale is None:
        scale = category_scale(projection_lines(projections[projections.games > 0]), cfg)
    proj = _projected(projections, overrides, cfg, scale)
    played = _played(box, overrides, cfg, scale) if not box.empty else {}
    out = {}
    for key in dict.fromkeys([*proj, *played]):
        p, s = proj.get(key), played.get(key)
        games = s[1] if s else 0
        if p is None:
            out[key] = SeasonLine(s[0], games, 1.0, s[2], s[3])
            continue
        w = blend_weight(games, cfg) if s else 0.0
        season_pg, season_share = (s[2], s[3]) if s else (0.0, 0.0)
        out[key] = SeasonLine(p[0], games, w, w * season_pg + (1 - w) * p[1], w * season_share + (1 - w) * p[2])
    return out


def read_season_lines(cfg):
    """season_lines() of the newest projections file and data/box_scores.csv. {} with no projections file, because
    the category scale comes from it. With no box-score file, each player has 0 games, so his line is his projection.
    """
    try:
        projections = pd.read_csv(latest_projections(cfg))
    except FileNotFoundError:
        return {}
    path = common.DATA / "box_scores.csv"
    box = pd.read_csv(path, dtype={"game_id": str, "player_id": str}) if path.exists() else pd.DataFrame()
    overrides_path = common.DATA / "name_overrides.csv"
    overrides = (
        pd.read_csv(overrides_path, dtype=str).fillna("")
        if overrides_path.exists()
        else pd.DataFrame(columns=["player_id", "yahoo_name", "espn_name", "name"])
    )
    return season_lines(projections, box, overrides, cfg)


def replacement_of(lines, keys, rank):
    """The per-game value of the player at rank (1 = best) among the lines of keys. With fewer lines than rank: the
    last line. None if no key has a line."""
    values = sorted((lines[k].pg_value for k in dict.fromkeys(keys) if k in lines), reverse=True)
    return values[min(rank, len(values)) - 1] if values else None


def pool_replacement(lines, cfg, rank):
    """An estimate of the replacement value with no free-agent list: the per-game value at rank teams x roster_spots +
    rank among all lines, so the player at rank rank after the rostered pool."""
    pool = cfg["league"]["teams"] * cfg["league"]["roster_spots"]
    return replacement_of(lines, list(lines), pool + rank)


@dataclass(frozen=True)
class SeasonValues:
    """The SeasonLines of a run and its replacement value. val() gives the Val of a player, ranks() his rank.

    lines: {Yahoo name key: SeasonLine}. replacement: the per-game value of the replacement free agent, or None (no
    Val). power: [games] power of config.toml.
    """

    lines: dict
    replacement: float | None
    power: float

    def val(self, key):
        """The Val of the player with the name key, to 2 decimals. None with no line or no replacement value."""
        line = self.lines.get(key)
        if line is None or self.replacement is None:
            return None
        return round(line_val(line, self.replacement, self.power), 2)

    def vals(self):
        """{name key: Val} of each line. {} with no replacement value."""
        if self.replacement is None:
            return {}
        return {key: self.val(key) for key in self.lines}

    def ranks(self):
        """{name key: rank by Val (1 = best)}. Equal Vals keep the order of the lines. {} with no replacement value."""
        vals = self.vals()
        order = sorted(vals, key=lambda k: -line_val(self.lines[k], self.replacement, self.power))
        return {key: rank for rank, key in enumerate(order, 1)}


def basis_text(cfg):
    """The one-line basis of Val on each page."""
    return f"Val = season value to date, blended with the projection until {blend_games(cfg)} games."
