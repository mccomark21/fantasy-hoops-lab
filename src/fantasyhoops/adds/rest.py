"""Rest risk on back-to-backs: the second nights in the planning window and the players who can rest on them.

A second night is a game of a team on the day after a game of the same team. A game on the day before the planning
window counts too. The rest list is the rests_b2b column of the [risk] file of config.toml, the list of the draft
tools. For a player on the list, one game on a second night counts 1 - [adds] rest_chance started games.
The draft tools do not change: there, rests_b2b changes only the playoff columns. The module writes no files.
"""

from dataclasses import replace
from datetime import timedelta

import pandas as pd

from fantasyhoops.core.common import ROOT, name_key

DEFAULT_REST_CHANCE = 0.5  # [adds] rest_chance if config.toml does not set it. config.toml sets the same value.


def second_nights(sched, days):
    """{day: set of the NBA teams (ESPN codes) on the second night of a back-to-back} for each day in days.

    sched: data/schedule.csv, one row for each team in each game.
    """
    dates = pd.to_datetime(sched.date).dt.date
    return {d: set(sched.team[dates == d]) & set(sched.team[dates == d - timedelta(days=1)]) for d in days}


def rest_names(risk):
    """The name keys (core.common.name_key) of the players with rests_b2b = 1 in a risk table (name, rests_b2b)."""
    return {name_key(n) for n, rests in zip(risk.name, risk.rests_b2b.fillna(0)) if rests}


def read_rest_names(cfg):
    """rest_names() of the [risk] file. An empty set if the file does not exist."""
    path = ROOT / cfg["risk"]["file"]
    return rest_names(pd.read_csv(path)) if path.exists() else set()


def with_rests(options, names, nights, chance):
    """The options, each player on the rest list with his rest_games: (day, 1 - chance) for each second night.

    names: from rest_names(). nights: from second_nights(). chance: [adds] rest_chance, the chance that he rests on
    a second night. A player who is not on the list, or who has no second night, does not change. With chance 0,
    no player changes.
    """
    out = []
    for o in options:
        rest = tuple((d, 1 - chance) for d in sorted(nights) if o.player.team in nights[d])
        out.append(replace(o, rest_games=rest) if chance and rest and name_key(o.player.name) in names else o)
    return out
