"""Season value (#222, #248): the custom value of a player on his Basketball Monster projection.

Each page that shows Val reads it from this module. No page computes it. The owner downloads the rest-of-season
projections export of Basketball Monster (BBM) by hand into data/Projections_<date>.csv. The box scores do not feed
Season value (owner decision of 2026-11-18, #248). The formula:
1. Per-game value: pg_value() of core/valuation.py on the per-game line of the newest projections file. The
   category scale is the scale of the projections file.
2. Availability: the games factor of the draft formula, (share of games) ^ [games] power. share = projected
   rest-of-season games / the remaining games of his NBA team, at most 1. The remaining games are the games of
   data/schedule.csv on and after the date of the projections file. His NBA team: the team in data/name_overrides.csv,
   else his team in data/rosters.csv. A player with no team gets the mean remaining games of all teams. With no
   schedule, the share is projected games / [games] full_season.
3. Val = per-game value minus the replacement value. A Val above 0 gets the availability factor. A Val below 0 does
   not, as in core/valuation.py. The replacement value is the per-game value of the replacement free agent of the
   planning run (adds/value.py season_replacement()).
A projection row gets its Yahoo name from data/name_overrides.csv, as in players/data.py.
basis_text() names the date of the projections file. stale_warning() warns when the file is older than
[season_value] stale_days.
read_season_lines() reads the newest projections file, data/schedule.csv, data/rosters.csv and
data/name_overrides.csv. The module writes no files.
"""

import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

from fantasyhoops.core import common
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.valuation import category_scale, pg_value, projection_lines

SOURCE = "Basketball Monster"


@dataclass(frozen=True)
class SeasonLine:
    """The season value of one player before the replacement value.

    name: his Yahoo name if data/name_overrides.csv gives one, else the projection name.
    games: his projected rest-of-season games. pg_value: the per-game value of the projection.
    share: the share of games (0 to 1) for the availability factor.
    team_games: the remaining games of his NBA team (0 with no team).
    """

    name: str
    games: int
    pg_value: float
    share: float
    team_games: int = 0


def line_val(line, replacement, power):
    """The Val of a SeasonLine: pg_value - replacement, times share ^ power when it is above 0. power: [games] power."""
    above = line.pg_value - replacement
    return above if above < 0 else above * line.share**power


def remaining_games(sched, since):
    """{NBA team (ESPN code): its games on and after the date since} of data/schedule.csv (one row for each team in
    each game)."""
    dates = pd.to_datetime(sched.date).dt.date
    return {str(t): int(n) for t, n in sched.team[dates >= since].value_counts().items()}


def season_lines(projections, overrides, cfg, scale=None, rosters=None, remaining=None):
    """{Yahoo name key: SeasonLine} of the rows of a projections table with games > 0.

    projections: a rest-of-season projections table. overrides: data/name_overrides.csv as text (dtype=str,
    fillna("")). scale: the category scale. None: the scale of the projections (category_scale()).
    rosters: data/rosters.csv (espn_name, team). None: no rosters. remaining: remaining_games(). None or {}: the
    share is games / [games] full_season.
    Two rows with one key: the row with the higher per-game value stays, as in players/data.py (pg_var).
    """
    df = projections[projections.games > 0]
    if df.empty:
        return {}
    df = projection_lines(df)
    if scale is None:
        scale = category_scale(df, cfg)
    if rosters is None:
        rosters = pd.DataFrame(columns=["espn_name", "team"])
    remaining = remaining or {}
    default = sum(remaining.values()) / len(remaining) if remaining else cfg["games"]["full_season"]
    df["pg"] = pg_value(df, scale, cfg)
    yahoo_names = dict(zip(overrides.player_id, overrides.yahoo_name))
    fixes = {str(r.player_id): r for r in overrides.itertuples()}
    teams = dict(zip(rosters.espn_name.map(name_key), rosters.team))
    out = {}
    for row in df.sort_values("pg", ascending=False).itertuples():
        fix = fixes.get(str(row.player_id))
        shown = yahoo_names.get(str(row.player_id)) or f"{row.first_name} {row.last_name}"
        espn = getattr(fix, "espn_name", "") or f"{row.first_name} {row.last_name}"
        team = getattr(fix, "team", "") or teams.get(name_key(espn))
        team_games = remaining.get(team, 0) if team else 0
        share = min(row.games / (team_games or default), 1.0)
        line = SeasonLine(shown, int(row.games), float(row.pg), float(share), int(team_games))
        out.setdefault(name_key(shown), line)
    return out


def projections_date(path):
    """The date in the name of a projections file (Projections_2026-11-18.csv), else the date of its last change."""
    found = re.search(r"\d{4}-\d{2}-\d{2}", path.name)
    if found:
        return date.fromisoformat(found.group())
    return date.fromtimestamp(path.stat().st_mtime)


def _newest_date(cfg):
    """The date of the newest projections file, or None with no file."""
    try:
        return projections_date(latest_projections(cfg))
    except FileNotFoundError:
        return None


def stale_warning(cfg, today=None):
    """The warning line when the newest projections file is older than [season_value] stale_days, else None."""
    made = _newest_date(cfg)
    if made is None:
        return None
    age = ((today or date.today()) - made).days
    if age <= cfg["season_value"]["stale_days"]:
        return None
    return f"Warning: the projections file is {age} days old. Download a new {SOURCE} export."


def read_season_lines(cfg):
    """season_lines() of the newest projections file. {} with no projections file, because the category scale comes
    from it. With no data/schedule.csv, the share uses [games] full_season."""
    try:
        path = latest_projections(cfg)
    except FileNotFoundError:
        return {}
    projections = pd.read_csv(path)
    overrides_path = common.DATA / "name_overrides.csv"
    overrides = (
        pd.read_csv(overrides_path, dtype=str).fillna("")
        if overrides_path.exists()
        else pd.DataFrame(columns=["player_id", "name", "espn_name", "yahoo_name", "team"])
    )
    rosters_path = common.DATA / "rosters.csv"
    rosters = pd.read_csv(rosters_path) if rosters_path.exists() else None
    sched_path = common.DATA / "schedule.csv"
    remaining = remaining_games(pd.read_csv(sched_path), projections_date(path)) if sched_path.exists() else {}
    return season_lines(projections, overrides, cfg, rosters=rosters, remaining=remaining)


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


def basis_text(cfg, today=None):
    """The one-line basis of Val on each page: the source and the date of the projections file, then
    stale_warning() when the file is old."""
    made = _newest_date(cfg)
    if made is None:
        return f"Val = the per-game value of the {SOURCE} projection."
    warning = stale_warning(cfg, today)
    text = f"Val = the per-game value of the {SOURCE} projection of {made:%Y-%m-%d}."
    return f"{text} {warning}" if warning else text
