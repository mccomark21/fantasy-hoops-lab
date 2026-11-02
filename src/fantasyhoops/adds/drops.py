"""Core list, stream spots and drops. The design is in docs/adds/README.md, "Core and drops".

The stream spots are the empty roster spots (spots freed by IL included), then, up to [adds] stream_spots, the
rostered players with the lowest Val who are not core. The planner keeps all other players. It never
drops a core player, also when he is Out. A drop is a suggestion, never an order.

Val is the Season value of core/season_value.py (#222). season_ranks() gives the rank and the Val of each player for
choose_stream_spots() and value_warnings(). A player with no season line has the lowest value.
"""

from dataclasses import dataclass

from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.slots import roster_spots_used
from fantasyhoops.core.common import name_key

NO_VALUE = float("-inf")  # the value of a holder with no season line: lower than all values


@dataclass(frozen=True)
class SeasonValue:
    """The value of a player from season_ranks(): rank = his rank by Val (1 = best), value = his Val."""

    rank: int
    value: float


def season_ranks(season):
    """{name key: SeasonValue} of the Val of each player of a core/season_value.SeasonValues. {} with no replacement."""
    vals, ranks = season.vals(), season.ranks()
    return {key: SeasonValue(ranks[key], vals[key]) for key in ranks}


def season_value(player, values):
    """The SeasonValue of a Player, or None if values has no entry for his name."""
    return values.get(name_key(player.name))


def is_core(player, cfg):
    """True if the player is in [adds] core of config.toml. The names match after name_key()."""
    return name_key(player.name) in {name_key(n) for n in cfg["adds"]["core"]}


def choose_stream_spots(roster, cfg, values):
    """The stream spots: a list of StreamSpot, the empty spots first.

    roster: your Players. values: from season_ranks(). The holders are the players with the lowest value who are not
    core and not on IL, lowest first. A player who is not in values comes first.
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
    """A warning for each streamer with a higher Val than your lowest core player.

    A streamer is a free agent of options (planner.Option) who fits an add of the team plan: he plays for one of its
    teams and has one of its slots ("Util": any position). adds: the TeamAdds of team_plan.TeamPlan (#140). The
    warnings are in order of Val, best first. values: from season_ranks(), for the free agents and the roster.

    If no core player is on the roster, the comparison uses your lowest kept player: the lowest player who is not
    on IL and not in a stream spot. Players who are not in values are not in the comparison.
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
    fits = [
        (season_value(o.player, values).value, o.player)
        for o in options
        if season_value(o.player, values) and not o.player.out and any(_fits(o.player, a) for a in adds)
    ]
    for value, fa in sorted(fits, key=lambda f: -f[0]):
        if value > lowest and fa not in seen:
            seen.add(fa)
            out.append(
                f"Warning: {fa.name} ({fa.team}) has a Val of {value:+.2f}. "
                f"Your lowest {kind}, {player.name}, has a Val of {lowest:+.2f}. "
                f"You can make {fa.name} core."
            )
    return out


def _fits(player, add):
    """True if player plays for a team of add and has one of its slots. "Util" takes all positions."""
    return player.team in add.teams and ("Util" in add.slots or bool(set(player.positions) & set(add.slots)))
