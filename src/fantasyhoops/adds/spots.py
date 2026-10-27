"""Plans for one roster spot: the rows of "Best plans for one roster spot" on the plan page.

Each row is the best plan for ONE stream spot. It can use more than one add in that spot, for example player A
on Tue and Wed, then player B from Thu. The other stream players stay in their spots. Each row uses players that
the rows above it do not use, so the rows are alternatives. The design is in docs/adds/README.md, "The plans".
"""

from dataclasses import dataclass

from fantasyhoops.adds.drops import kept_roster
from fantasyhoops.adds.planner import DIGITS, schedule_plan
from fantasyhoops.adds.slots import open_slots_by_day

ROWS = 3  # the rows of the table


@dataclass(frozen=True)
class SpotPlan:
    """The best plan for one stream spot.

    spot: the StreamSpot. plan: the Plan of that spot alone, with one add or more. gain: the started games of the
    plan minus the started games of the spot with no add (the games of its holder, or 0 for an empty spot). A fraction
    if a player on the rest list starts on a second night of a back-to-back.
    """

    spot: object
    plan: object
    gain: float

    @property
    def added(self):
        """The team windows of the new players, in order of day."""
        return [w for w in self.plan.windows if w.add_day]


def _spot_plan(roster, spot, games, options, adds_left, slots):
    days = open_slots_by_day(kept_roster(roster, [spot]), games, slots)
    plan = schedule_plan(days, games, [spot], options, adds_left, slots)
    base = schedule_plan(days, games, [spot], options, 0, slots)
    return SpotPlan(spot, plan, round(plan.started_games - base.started_games, DIGITS))


def spot_plans(roster, spots, games, options, adds_left, slots, rows=ROWS):
    """The best SpotPlans, best first: the most games gained, then the fewest adds, then the highest value.

    roster: your Players. spots: the StreamSpots. games: {day: set of NBA teams that play} of the planning window.
    options: the Options of the free agents. Each row tries each spot and keeps the best plan. A row with no add
    ends the list, so it can have fewer than rows SpotPlans.
    """
    out, used = [], set()
    while len(out) < rows and adds_left:
        pool = [o for o in options if o.player.name not in used]
        tries = [_spot_plan(roster, s, games, pool, adds_left, slots) for s in spots]
        tries = [t for t in tries if t.plan.adds]
        if not tries:
            break
        best = max(tries, key=lambda t: (t.gain, -t.plan.adds, t.plan.value))
        out.append(best)
        used |= {w.player.player.name for w in best.added}
    return out
