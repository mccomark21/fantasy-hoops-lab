"""Core list, stream spots and drops. The design is in docs/adds/README.md, "Core and drops".

The stream spots are the empty roster spots (spots freed by IL included), then, up to [adds] stream_spots, the
rostered players with the lowest season value who are not core. The planner keeps all other players. It never
drops a core player, also when he is Out. A drop is a suggestion with its trade-off, never an order.

Season value: rostered players are not on the free-agent list. So their rank and value come from the season
projections file of the draft tools: pg_value of core/valuation.py, and the rank by pg_value (pg_rank on the
draft board). The free-agent values use the same category scale (adds/value.py), so the numbers compare.
A player who is not in the projections file has the lowest value.
"""

from dataclasses import dataclass

import pandas as pd

from fantasyhoops.adds.planner import DIGITS, Option, StreamSpot, counted_games, schedule_plan
from fantasyhoops.adds.rest import games_text
from fantasyhoops.adds.slots import open_slots_by_day, roster_spots_used
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


@dataclass(frozen=True)
class Drop:
    """A suggested drop: the add of window drops holder, and the plan gets gain more started games this week.

    gain: the started games of the plan minus the started games of the best plan that keeps the holder. Both counts
    include the started games of the holder and of the players who are kept. A fraction if a player on the rest
    list starts on a second night of a back-to-back.
    season: the SeasonValue of the holder, or None if he is not in the projections file.
    """

    window: object
    holder: object
    season: SeasonValue | None
    gain: float

    def text(self):
        """For example "Drop Quickley (rank 90, season value -0.52) -> PHX Thu 01/07 to Sun 01/10: +2 started
        games this week." """
        w = self.window
        season = (
            f"rank {self.season.rank}, season value {self.season.value:+.2f}"
            if self.season
            else "not in the projections file"
        )
        games = "game" if self.gain == 1 else "games"
        return (
            f"Drop {self.holder.name} ({season}) -> {w.team} {w.add_day:%a %m/%d} to {w.last_day:%a %m/%d}: "
            f"{games_text(self.gain, sign=True)} started {games} this week."
        )


def drop_trade_offs(plan, roster, spots, games, free_agents, adds_left, slots, values):
    """A Drop for each holder that the plan drops.

    The arguments are the arguments of schedule_plan(), and roster is the full roster (with the holders).
    For each drop, the function makes the best plan that keeps the holder: he goes back to the roster, and his
    stream spot is not in the plan.
    """
    out = []
    base = _roster_starts(kept_roster(roster, spots), games, slots)
    for s, spot in enumerate(spots):
        added = [w for w in plan.windows if w.spot == s and w.add_day is not None]
        if not spot.holder or not added:
            continue
        others = spots[:s] + spots[s + 1 :]
        days = open_slots_by_day(kept_roster(roster, others), games, slots)
        kept = schedule_plan(days, games, others, free_agents, adds_left, slots)
        kept_starts = kept.started_games + _roster_starts(kept_roster(roster, others), games, slots, spots) - base
        gain = round(plan.started_games - kept_starts, DIGITS)
        out.append(
            Drop(window=added[0], holder=spot.holder.player, season=season_value(spot.holder.player, values), gain=gain)
        )
    return out


def _roster_starts(roster, games, slots, spots=()):
    """The counted started games of the players on the roster in the days of games.

    spots: the StreamSpots. A holder on the roster counts his games with his rest games (planner.counted_games()),
    the same count as in the plan. Each other player counts each game as 1.
    """
    rests = {s.holder.player: s.holder.rest_games for s in spots if s.holder}
    return sum(
        counted_games(rests.get(p, ()), [d.date])
        for d in open_slots_by_day(roster, games, slots)
        for _, p in d.starters
    )


def value_warnings(plan, roster, spots, cfg, values):
    """A warning for each streamer (a window option) with a higher value than your lowest core player.

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
    for w in plan.windows:
        for o in w.options if w.add_day is not None else ():
            if o.value is not None and o.value > lowest and o.player not in seen:
                seen.add(o.player)
                out.append(
                    f"Warning: {o.player.name} ({o.player.team}) has a value of {o.value:+.2f}. "
                    f"Your lowest {kind}, {player.name}, has a season value of {lowest:+.2f}. "
                    f"You can make {o.player.name} core."
                )
    return out


def print_stream_spots(spots, values):
    """Print the stream spots and the player who holds each spot."""
    print()
    print(f"Stream spots: {len(spots)}. The open slots above do not count the players in the stream spots.")
    for n, spot in enumerate(spots, 1):
        if not spot.holder:
            print(f"  Spot {n}: empty.")
            continue
        p = spot.holder.player
        season = season_value(p, values)
        about = (
            f"rank {season.rank}, season value {season.value:+.2f}"
            if season
            else "not in the projections file, so he has the lowest value"
        )
        status = f" {p.status}" if p.status else ""
        print(f"  Spot {n}: {p.name}{status} ({p.team}, {about}). The plan can drop him.")
