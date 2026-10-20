"""Contingency plans: how to fill the slot of a flagged player who is ruled out just before his game.

A flagged player has a status that does not make him an Out player, for example Q, D or P. He gets one plan for
each day on which he starts in the lineup of the main plan. A day on which he sits on the bench needs no plan.
A healthy player and an Out player get no plan.

1. Lineup move: the planner makes the lineup of that day again without him. The players of the stream spots
   in the main plan are in the lineup. If the number of starters stays the same, a bench player takes the slot.
2. Late add: if no move works, a free agent whose game starts later that day takes the slot. He goes to an
   empty stream spot, or he replaces a streamer who does not start that day. The plan shows the cost: one add,
   and the started games of the team window that the drop ends early.

The game times come from the time column of data/schedule.csv (US Eastern time, fetch/espn.py). An old file has
no time column. Then the plan lists all the free agents who fit, and you check the game times yourself.
The main plan does not keep an add back for contingency plans.
"""
from dataclasses import dataclass
from datetime import date

import pandas as pd

from fantasyhoops.core.lineup import best_lineup

LATE_ADDS = 3  # free agents to show for each late add


@dataclass(frozen=True)
class Contingency:
    """The contingency plan for one flagged player on one day.

    time: the start of his game (US Eastern, "19:30"), or None if the schedule has no time.
    move: the bench player who takes his slot, or None if no lineup move works.
    late_adds: (Option, start time or None) for the best free agents who can take his slot, best value first.
    Empty if a move works or no free agent fits.
    drop: the TeamWindow of the streamer to drop for the late add. None for an empty stream spot.
    lost: the started games of the drop window after that day. The late add ends the window, so the plan
    loses them.
    adds_left: the adds left after the main plan. The late add uses one add.
    """
    player: object
    day: date
    time: str | None
    move: object = None
    late_adds: tuple = ()
    drop: object = None
    lost: tuple = ()
    adds_left: int = 0


def game_times(sched):
    """{(day, team): start time "HH:MM", US Eastern} from data/schedule.csv. Empty if the file has no time column."""
    if "time" not in sched.columns:
        return {}
    rows = sched.dropna(subset=["time"])
    return {(d, t): str(s) for d, t, s in zip(pd.to_datetime(rows.date).dt.date, rows.team, rows.time)}


def flagged(player):
    """True for a flagged player: he has a status, and the status does not make him an Out player."""
    return bool(player.status) and not player.out


def contingency_plans(days, games, plan, spots, free_agents, adds_left, slots, times=None):
    """A Contingency for each day on which a flagged player starts in the lineup of the main plan.

    days and games: the same as for planner.schedule_plan(). plan: the main Plan, or None if there is no plan.
    spots: the number of stream spots. free_agents: an Option for each free agent.
    adds_left: the adds left before the main plan. slots: cfg["league"]["slots"]. times: from game_times().
    """
    times = times or {}
    windows = plan.windows if plan else ()
    left = adds_left - (plan.adds if plan else 0)
    in_plan = {w.player for w in windows}
    fas = sorted((o for o in free_agents if o.value is not None and not o.player.out and o not in in_plan),
                 key=lambda o: -o.value)
    out = []
    for day in days:
        roster = [p for _, p in day.starters] + list(day.bench)
        here = _windows_on(windows, day.date, days[0].date)
        streamers = sorted((w.player for w in here if w.player.player.team in games[day.date]),
                           key=lambda o: -o.value)
        lineup = roster + [o.player for o in streamers]
        starters = _starters(lineup, slots)
        for p in roster:
            if not flagged(p) or p not in starters:
                continue
            others = [q for q in lineup if q is not p]
            time = times.get((day.date, p.team))
            after = _starters(others, slots)
            if len(after) == len(starters):
                move = next(q for q in others if q in after and q not in starters)
                out.append(Contingency(p, day.date, time, move=move, adds_left=left))
            else:
                out.append(_late_add(p, day, time, others, len(starters), here, spots, games, fas, slots, times,
                                     left))
    return out


def _late_add(p, day, time, others, count, here, spots, games, fas, slots, times, left):
    """The Contingency with a late add: the cheapest drop for which free agents fit, and the best of them."""
    later = [o for o in fas if o.player.team in games[day.date] and _later(times.get((day.date, o.player.team)), time)]
    # The drops, cheapest first: an empty stream spot, then each streamer by the started games that he loses.
    drops = [None] if len({w.spot for w in here}) < spots else []
    drops += sorted(here, key=lambda w: (len(_lost(w, day.date)), w.player.value))
    for drop in drops:
        kept = [q for q in others if drop is None or q is not drop.player.player]
        fits = [o for o in later if len(_starters(kept + [o.player], slots)) == count]
        if fits:
            return Contingency(p, day.date, time, drop=drop, lost=_lost(drop, day.date) if drop else (),
                               late_adds=tuple((o, times.get((day.date, o.player.team))) for o in fits[:LATE_ADDS]),
                               adds_left=left)
    return Contingency(p, day.date, time, adds_left=left)


def _windows_on(windows, d, first):
    """The team windows that hold a player on day d. A holder window starts on the first day of the plan."""
    return [w for w in windows if (w.add_day or first) <= d <= w.last_day]


def _starters(players, slots):
    """The players who start, as a set. players: Players in order of preference."""
    return {players[i] for i in best_lineup([set(q.positions) for q in players], slots)}


def _lost(window, d):
    return tuple(s for s in window.started if s > d)


def _later(start, than):
    """True if a game that starts at start can be later than a game that starts at than. True if a time is unknown."""
    return start is None or than is None or start > than


def print_contingencies(plans):
    """Print the contingency plans after the main plan."""
    print()
    if not plans:
        print("Contingency plans: none. No flagged player starts in the planning window.")
        return
    print("Contingency plans: if a flagged player is ruled out just before his game.")
    for c in plans:
        for line in contingency_lines(c):
            print(line)


def contingency_lines(c):
    """The text of one contingency plan, one line for each item."""
    lines = []
    start = f", game at {c.time} ET" if c.time else ""
    lines.append(f"  {c.day:%a %m/%d}  {c.player.name} {c.player.status} ({c.player.team}{start}):")
    if c.move:
        lines.append(f"      Lineup move: start {c.move.name} ({c.move.team}, {','.join(c.move.positions)}) "
                     f"from the bench.")
        return lines
    if not c.late_adds:
        lines.append("      No lineup move works, and no free agent who was read can take his slot.")
        return lines
    drop = " to an empty stream spot" if c.drop is None else f", drop {c.drop.player.player.name} ({c.drop.team})"
    lines.append(f"      No lineup move works. Late add{drop}:")
    for n, (o, t) in enumerate(c.late_adds, 1):
        when = f"game at {t} ET" if t else f"check that his game starts after {c.player.name}'s game"
        lines.append(f"        {n}. {o.player.name}  {o.player.team}  {','.join(o.player.positions)}  "
                     f"value {o.value:+.2f}  ({when})")
    ends = ("no team window ends early" if c.drop is None else
            f"the {c.drop.team} window ends early and loses {len(c.lost)} started game"
            + ("" if len(c.lost) == 1 else "s") + (f" ({', '.join(f'{d:%a %m/%d}' for d in c.lost)})"
                                                     if c.lost else ""))
    lines.append(f"      Cost: 1 add ({c.adds_left} left after the main plan), {ends}.")
    if c.adds_left <= 0:
        lines.append("      The main plan uses all the adds, so this add takes an add from the main plan.")
    return lines
