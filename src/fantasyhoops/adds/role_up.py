"""Role up: mark the free agents who can get more minutes because a starter on their NBA team is absent.

The design is in docs/adds/README.md, "Role up". The mark does not change a value or a plan. This module writes no file.
Inputs:
  data/rotation_log.csv and data/rotation_scores.csv (core/rotation.py) - the games of each player and of each team
  data/yahoo_players.csv, data/rosters.csv, data/name_overrides.csv (core/identity.py) - the positions of the starters
Settings: [adds.role_up] in config.toml.
"""
from dataclasses import dataclass, replace
from datetime import date, timedelta

import pandas as pd

from fantasyhoops.core import rotation
from fantasyhoops.core.common import DATA, name_key
from fantasyhoops.core.identity import link_players, yahoo_keys

LOG, SCORES = rotation.LOG, rotation.SCORES
# The files that give the Yahoo positions of the absent starters (core/identity.py).
IDENTITY_FILES = [DATA / "yahoo_players.csv", DATA / "rosters.csv", DATA / "name_overrides.csv"]


@dataclass(frozen=True)
class Absence:
    """A starter who missed the last games of his NBA team in the rotation log.

    name: his ESPN name. team: the ESPN code of his team. first_missed: the day of the first game that he missed.
    missed: the games of his team since his last game. positions: his Yahoo positions. () if Yahoo has no match.
    """
    name: str
    team: str
    first_missed: date
    missed: int
    positions: tuple = ()


def absences(player_games, team_games, today, cfg):
    """The absent starters, from the frames of core/rotation.py: player_games() and team_games().

    A player is absent when his team played a game after his last game. He is a starter when he started more than
    half of his last starter_games games. The mark needs his first missed game on or after today - days, and
    games or fewer missed games. The settings are in [adds.role_up].
    """
    s = cfg["adds"]["role_up"]
    start = pd.Timestamp(today - timedelta(days=s["days"]))
    out = []
    for _, games in player_games.sort_values("date").groupby("player_id", sort=False):
        last = games.iloc[-1]
        missed = team_games[(team_games.team == last.team) & (team_games.date > last.date)].date.sort_values()
        if missed.empty or len(missed) > s["games"] or missed.iloc[0] < start:
            continue
        if games.tail(s["starter_games"]).started.mean() > 0.5:
            out.append(Absence(last.player, last.team, missed.iloc[0].date(), len(missed)))
    return sorted(out, key=lambda a: (a.team, a.name))


def with_positions(found, yahoo, rosters, overrides):
    """The Absences with the Yahoo positions of each player. link_players() of core/identity.py links the names.

    yahoo_keys() of core/identity.py gives the Yahoo name of a player whose ESPN name is in an override row.
    """
    if not found:
        return []
    keys = yahoo_keys(overrides)
    players = pd.DataFrame({"name": [keys.get(name_key(a.name), a.name) for a in found], "player_id": ""})
    # The names are already the Yahoo names, so link_players() gets no override rows.
    pos = link_players(players, rosters, yahoo, overrides.iloc[0:0]).pos
    return [replace(a, positions=() if p == "—" else tuple(p.split("/"))) for a, p in zip(found, pos)]


def mark_role_ups(options, found):
    """The options, each with the names of the absent starters on his team who share one of his positions."""
    def names(p):
        return tuple(a.name for a in found if a.team == p.team and set(a.positions) & set(p.positions)
                     and name_key(a.name) != name_key(p.name))
    return [replace(o, role_up=names(o.player)) for o in options]


def read_absences(today, cfg):
    """The absent starters with their positions, from the files in data/. [] if the rotation log is missing.

    If the log exists but a file of IDENTITY_FILES is missing, the function prints one warning and gives [].
    """
    if not (LOG.exists() and SCORES.exists()):
        return []
    missing = [f.name for f in IDENTITY_FILES if not f.exists()]
    if missing:
        print(f"Warning: no role-up marks. These files are missing in data/: {', '.join(missing)}.")
        return []
    yahoo, rosters, overrides = IDENTITY_FILES
    stints, scores = rotation.read_log(LOG), rotation.read_scores(SCORES)
    found = absences(rotation.player_games(stints, scores, cfg), rotation.team_games(stints, scores, cfg), today, cfg)
    return with_positions(found, pd.read_csv(yahoo), pd.read_csv(rosters),
                          pd.read_csv(overrides, dtype=str).fillna(""))
