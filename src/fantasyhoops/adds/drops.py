"""Core list, stream spots and drops. The design is in docs/adds/README.md, "Core and drops".

The stream spots are the empty roster spots (spots freed by IL included), then, up to [adds] stream_spots, the
rostered players with the lowest season value who are not core. The planner keeps all other players. It never
drops a core player, also when he is Out. A drop is a suggestion, never an order.

Season value: rostered players are not on the free-agent list. So their rank and value come from the season
projections file of the draft tools: pg_value of core/valuation.py, and the rank by pg_value (pg_rank on the
draft board). The free-agent values use the same category scale (adds/value.py), so the numbers compare.
A player who is not in the projections file has the lowest value.
"""

from dataclasses import dataclass

import pandas as pd

from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.slots import roster_spots_used
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.core.valuation import value_players
from fantasyhoops.draft.rankings import STATS

NO_VALUE = float("-inf")  # the value of a holder who is not in the projections file: lower than all values


@dataclass(frozen=True)
class SeasonValue:
    """The season value of a player: rank = his rank by pg_value (1 = best), value = his pg_value."""

    rank: int
    value: float


def season_values(cfg):
    """{name_key(name): SeasonValue} for the players in the newest projections file."""
    return rank_players(pd.read_csv(latest_projections(cfg)), cfg)


def rank_players(projections, cfg):
    """{name_key(name): SeasonValue} for the players of a projections DataFrame with games > 0.

    Two players with the same name key: the player with the higher value is in the result.
    """
    df = projections[projections.games > 0].copy()
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    df = value_players(df, cfg).sort_values("pg_value", ascending=False)
    out = {}
    for rank, (first, last, value) in enumerate(zip(df.first_name, df.last_name, df.pg_value), 1):
        out.setdefault(name_key(f"{first} {last}"), SeasonValue(rank, float(value)))
    return out


def season_value(player, values):
    """The SeasonValue of a Player, or None if he is not in the projections file."""
    return values.get(name_key(player.name))


def is_core(player, cfg):
    """True if the player is in [adds] core of config.toml. The names match after name_key()."""
    return name_key(player.name) in {name_key(n) for n in cfg["adds"]["core"]}


def choose_stream_spots(roster, cfg, values):
    """The stream spots: a list of StreamSpot, the empty spots first.

    roster: your Players. values: from season_values(). The holders are the players with the lowest season value
    who are not core and not on IL, lowest first. A player who is not in values comes first.
    """
    empty = cfg["league"]["roster_spots"] - roster_spots_used(roster)
    candidates = [p for p in roster if not p.on_il and not is_core(p, cfg)]
    candidates.sort(key=lambda p: (season_value(p, values) is not None, _value(p, values)))
    holders = candidates[: max(0, cfg["adds"]["stream_spots"] - empty)]
    return [StreamSpot()] * empty + [StreamSpot(Option(p, _value(p, values))) for p in holders]


def _value(player, values):
    season = season_value(player, values)
    return season.value if season else NO_VALUE


def kept_roster(roster, spots):
    """The roster without the holders of the stream spots. Give it to open_slots_by_day()."""
    holders = {s.holder.player for s in spots if s.holder}
    return [p for p in roster if p not in holders]


def value_warnings(options, adds, roster, spots, cfg, values):
    """A warning for each streamer with a higher value than your lowest core player.

    A streamer is a free agent of options (planner.Option) who fits an add of the team plan: he plays for one of its
    teams and has one of its slots ("Util": any position). adds: the TeamAdds of team_plan.TeamPlan (#140). The
    warnings are in order of value, best first.

    If no core player is on the roster, the comparison uses your lowest kept player: the lowest player who is not
    on IL and not in a stream spot. Players who are not in the projections file are not in the comparison.
    """
    core = [p for p in roster if is_core(p, cfg)]
    kind = "core player"
    if not core:
        core, kind = [p for p in kept_roster(roster, spots) if not p.on_il], "kept player"
    rated = [(season_value(p, values).value, p) for p in core if season_value(p, values)]
    if not rated:
        return []
    lowest, player = min(rated, key=lambda r: r[0])
    out, seen = [], set()
    fits = [o for o in options if o.value is not None and not o.player.out and any(_fits(o.player, a) for a in adds)]
    for o in sorted(fits, key=lambda o: -o.value):
        if o.value > lowest and o.player not in seen:
            seen.add(o.player)
            out.append(
                f"Warning: {o.player.name} ({o.player.team}) has a value of {o.value:+.2f}. "
                f"Your lowest {kind}, {player.name}, has a season value of {lowest:+.2f}. "
                f"You can make {o.player.name} core."
            )
    return out


def _fits(player, add):
    """True if player plays for a team of add and has one of its slots. "Util" takes all positions."""
    return player.team in add.teams and ("Util" in add.slots or bool(set(player.positions) & set(add.slots)))
