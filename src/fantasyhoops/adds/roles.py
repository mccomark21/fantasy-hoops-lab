"""The role of each free agent from the rotation log: his minutes trend, his starts and his closes in close games.

core/rotation.py reads the log (data/rotation_log.csv and data/rotation_scores.csv). fetch/rotation.py writes it.
- Minutes trend: his mean minutes in his last 5 games, and in his games of the last 14 days (today - 14 to
  yesterday). The change is the first minus the second. A change of [adds] minutes_rise or more gets a mark.
- Starts: his starts in his games of the last 14 days.
- Closes: his closes in the close games of his NBA team in the last 14 days. core/rotation.py defines a close game.
- Starter flag and closer flag: core/role_flags.py, over his last games and the last close games of his team.
The role is a mark only. It does not change the blended value or the plan. This module writes no file.
"""

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from fantasyhoops.adds.blend import RECENT_DAYS
from fantasyhoops.core.common import DATA, name_key
from fantasyhoops.core.identity import espn_keys
from fantasyhoops.core.role_flags import role_flags
from fantasyhoops.core.rotation import LOG, SCORES, player_games, read_log, read_scores

LAST_GAMES = 5  # the games of the short minutes window
OVERRIDES = DATA / "name_overrides.csv"


@dataclass(frozen=True)
class Role:
    """The role of one player. minutes_14d is None if he has no game in the last 14 days."""

    minutes_last5: float
    minutes_14d: float | None
    games: int  # his games in the last 14 days
    starts: int  # his starts in those games
    closes: int  # his closes in the close games of his team in the last 14 days
    close_games: int  # the close games of his team in the last 14 days
    rise: bool  # the change is [adds] minutes_rise or more
    starter: str | None = None  # the starter flag of core/role_flags.py: New, Regular, Inconsistent or None
    closer: str | None = None  # the closer flag of core/role_flags.py

    @property
    def change(self):
        """The mean minutes of the last 5 games minus the mean minutes of the last 14 days. None with no recent game."""
        return None if self.minutes_14d is None else self.minutes_last5 - self.minutes_14d


def _espn_ids(games, players, overrides):
    """{(name, team): ESPN player_id} for each Player that the log has. The names match after name_key() and the
    overrides. If two players have the same key, the player with games for the NBA team of the Player wins. If
    none of them has games for that team, the Player gets no ID. One player with the key always matches, because
    a player can change teams."""
    keys = espn_keys(overrides) if overrides is not None else {}
    by_key = games.assign(key=games.player.map(name_key)).groupby("key")
    out = {}
    for p in players:
        key = keys.get(name_key(p.name), name_key(p.name))
        if key not in by_key.groups:
            continue
        rows = by_key.get_group(key)
        if rows.player_id.nunique() > 1:
            rows = rows[rows.team == p.team]
            if rows.empty:
                continue
        out[(p.name, p.team)] = rows.sort_values("date").player_id.iloc[-1]
    return out


def player_roles(players, stints, scores, cfg, today, overrides=None):
    """{(name, team): Role} for each Player (adds/readers.py) that the log has. A player who is not in it has no Role.

    stints and scores: the frames of core/rotation.py read_log() and read_scores(). today: the run day. The log
    holds only final games, so the windows end yesterday. overrides: data/name_overrides.csv (dtype=str, fillna("")).
    """
    start = pd.Timestamp(today - timedelta(days=RECENT_DAYS))
    end = pd.Timestamp(today)
    games = player_games(stints, scores, cfg)
    games = games[games.date < end].sort_values("date")
    # The close games of each team come from the player games, so close_games() runs once. Each team game has
    # player rows, so this gives the same games as core/rotation.py team_games().
    teams = games[["game_id", "date", "team", "close_game"]].drop_duplicates()
    teams = teams[(teams.date >= start) & teams.close_game]
    rise = cfg["adds"]["minutes_rise"]
    out = {}
    for player, pid in _espn_ids(games, players, overrides).items():
        mine = games[games.player_id == pid]
        recent = mine[mine.date >= start]
        close = teams[teams.team == player[1]].game_id
        last5 = float(mine.minutes.tail(LAST_GAMES).mean())
        mean14 = float(recent.minutes.mean()) if len(recent) else None
        starter, closer = role_flags(games, pid, player[1], cfg["adds"]["flags"])
        out[player] = Role(
            minutes_last5=last5,
            minutes_14d=mean14,
            games=len(recent),
            starts=int(recent.started.sum()),
            closes=int(recent[recent.game_id.isin(close)].closed.sum()),
            close_games=len(close),
            rise=mean14 is not None and last5 - mean14 >= rise,
            starter=starter,
            closer=closer,
        )
    return out


def read_roles(players, cfg, today):
    """{(name, team): Role} from the rotation log. Empty if data/rotation_log.csv or data/rotation_scores.csv is
    missing. The planning run does not update the log: run python -m fantasyhoops.fetch.rotation first."""
    if not LOG.exists() or not SCORES.exists():
        return {}
    overrides = pd.read_csv(OVERRIDES, dtype=str).fillna("") if OVERRIDES.exists() else None
    return player_roles(players, read_log(LOG), read_scores(SCORES), cfg, today, overrides)
