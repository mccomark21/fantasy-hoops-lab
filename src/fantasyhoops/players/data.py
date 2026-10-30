"""The players of the Players page and of the player modal (#186), and the fields of each player.

The rule: each rostered player of the league, and each free agent with a projected value or with MIN_GAMES or more
games in the rotation log. player_records() applies the rule.
- The rostered players come from the Yahoo rostered list of all teams (trade/rostered.py), with their fantasy team.
- A projected value is a row with games in the newest projections file. Val is the projected value per game above
  replacement (pg_var of core/valuation.py). A player with no projection has no Val.
- The games are the ESPN games of a player in data/rotation_log.csv.
The names match after common.name_key(). data/name_overrides.csv gives the Yahoo name of a projection or ESPN name
that does not match (core/identity.py).
signals() gives the signal chips of a player from SIGNAL_RULES. The quadrant issues (#187 to #189) add their rules.
The module reads the data files in read_projected() and read_played(). It writes no files.
"""

from dataclasses import dataclass

import pandas as pd

from fantasyhoops.core import common, profile
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.identity import YAHOO_COLS, link_players, yahoo_keys
from fantasyhoops.core.rotation import read_log
from fantasyhoops.core.valuation import value_players
from fantasyhoops.draft.rankings import STATS

MIN_GAMES = 5  # a free agent with this many games in the rotation log or more is on the page
OVERRIDE_COLUMNS = ["player_id", "name", "espn_name", "yahoo_name", "team"]


@dataclass(frozen=True)
class Owned:
    """A rostered player: his Yahoo name, NBA team and positions, his fantasy team (owner) and mine (your team)."""

    name: str
    team: str
    positions: tuple
    owner: str
    mine: bool


@dataclass(frozen=True)
class Projected:
    """A player of the projections file: the name, the NBA team, the Yahoo positions and the Val (pg_var)."""

    name: str
    team: str
    positions: tuple
    value: float


@dataclass(frozen=True)
class Played:
    """A player of the rotation log: his ESPN name, his NBA team in his last game and his games."""

    name: str
    team: str
    games: int


@dataclass(frozen=True)
class Signal:
    """One signal chip of the header: kind (for example "Projection gap"), the quadrant key that it links to
    (profile.QUADRANT_KEYS), up (True for a good sign, False for an alert) and the text."""

    kind: str
    quadrant: str
    up: bool
    text: str


# The signal rules. Each rule takes a player record and gives a Signal or None. #187 to #189 add their rules.
SIGNAL_RULES = ()


def signals(record, rules=SIGNAL_RULES):
    """The signals of a player record from rules, in rule order, profile.MAX_SIGNALS at most, as dicts for the file.

    A Signal with a quadrant that is not in profile.QUADRANT_KEYS raises a ValueError.
    """
    out = []
    for rule in rules:
        found = rule(record)
        if found is None:
            continue
        if found.quadrant not in profile.QUADRANT_KEYS:
            raise ValueError(f"The signal {found.kind!r} links to {found.quadrant!r}, which is not a quadrant.")
        out.append({"kind": found.kind, "quadrant": found.quadrant, "up": found.up, "text": found.text})
    return out[: profile.MAX_SIGNALS]


def owned_players(rostered, own_team):
    """{name_key: Owned} of the rostered list. rostered: the RosteredPlayers of all teams. own_team: your team ID."""
    out = {}
    for r in rostered:
        p = r.player
        out.setdefault(name_key(p.name), Owned(p.name, p.team, tuple(p.positions), r.team_name, r.team_id == own_team))
    return out


def read_overrides():
    """data/name_overrides.csv as text, or an empty table if the file does not exist."""
    path = common.DATA / "name_overrides.csv"
    if not path.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)
    return pd.read_csv(path, dtype=str).fillna("")


def _optional_csv(name, columns):
    path = common.DATA / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)


def projected_players(projections, rosters, yahoo, overrides, cfg):
    """{Yahoo name key: Projected} of the rows of a projections table with games > 0.

    rosters, yahoo, overrides: data/rosters.csv, data/yahoo_players.csv and data/name_overrides.csv (core/identity.py)
    for the NBA team and the positions. Two rows with one key: the row with the higher Val is in the result.
    """
    df = projections[projections.games > 0].copy()
    if df.empty:
        return {}
    df["name"] = df.first_name + " " + df.last_name
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    df = value_players(df, cfg).join(link_players(df, rosters, yahoo, overrides))
    yahoo_names = dict(zip(overrides.player_id, overrides.yahoo_name))
    out = {}
    for row in df.sort_values("pg_var", ascending=False).itertuples():
        name = yahoo_names.get(str(row.player_id)) or row.name
        team = row.team if isinstance(row.team, str) else ""
        positions = tuple(row.pos.split("/")) if row.pos and row.pos != "—" else ()
        out.setdefault(name_key(name), Projected(name, team, positions, float(row.pg_var)))
    return out


def read_projected(cfg):
    """(projected_players() of the newest projections file, the file name). ({}, None) with no projections file."""
    try:
        path = latest_projections(cfg)
    except FileNotFoundError:
        return {}, None
    found = projected_players(
        pd.read_csv(path),
        _optional_csv("rosters.csv", ["espn_name", "team"]),
        _optional_csv("yahoo_players.csv", ["name", "positions", *(c for c in YAHOO_COLS if c != "pos")]),
        read_overrides(),
        cfg,
    )
    return found, path.name


def played_players(log, overrides):
    """{Yahoo name key: Played} of a rotation log table (core/rotation.py read_log()). The games are the game IDs."""
    if log.empty:
        return {}
    to_yahoo = yahoo_keys(overrides)
    out = {}
    for _, rows in log.sort_values("date").groupby("player_id", sort=False):
        last = rows.iloc[-1]
        key = name_key(last.player)
        key = to_yahoo.get(key, key)
        found = Played(last.player, last.team, int(rows.game_id.nunique()))
        if key not in out or found.games > out[key].games:
            out[key] = found
    return out


def read_played():
    """played_players() of data/rotation_log.csv. No log gives {}. Also the first and last date of the log, or None."""
    path = common.DATA / "rotation_log.csv"
    if not path.exists():
        return {}, None, None
    log = read_log(path)
    if log.empty:
        return {}, None, None
    return played_players(log, read_overrides()), f"{log.date.min():%Y-%m-%d}", f"{log.date.max():%Y-%m-%d}"


def player_records(owned, projected, played, rules=SIGNAL_RULES):
    """The players of the page and the file, as dicts, by Val (no Val last), then by name.

    owned, projected, played: {name_key: Owned}, {name_key: Projected} and {name_key: Played}.
    The list has each owned player, and each other player in projected or with MIN_GAMES or more games in played.
    A record has slug, name, team, pos, owner (None for a free agent), mine, val, games and signals.
    """
    keys = list(owned)
    keys += [k for k in dict.fromkeys([*projected, *played]) if k not in owned and _qualifies(k, projected, played)]
    records, slugs = [], set()
    for key in keys:
        own, proj, play = owned.get(key), projected.get(key), played.get(key)
        name = own.name if own else proj.name if proj else play.name
        record = {
            "slug": profile.slug(name),
            "name": name,
            "team": (own.team if own else play.team if play else proj.team) or "",
            "pos": "/".join(own.positions if own else proj.positions if proj else ()),
            "owner": own.owner if own else None,
            "mine": bool(own and own.mine),
            "val": round(proj.value, 2) if proj else None,
            "games": play.games if play else 0,
        }
        if not record["slug"] or record["slug"] in slugs:
            continue
        slugs.add(record["slug"])
        record["signals"] = signals(record, rules)
        records.append(record)
    return sorted(records, key=lambda r: (r["val"] is None, -(r["val"] or 0), r["name"]))


def _qualifies(key, projected, played):
    return key in projected or (key in played and played[key].games >= MIN_GAMES)
