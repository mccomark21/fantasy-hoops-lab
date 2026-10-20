"""The schedule plan: the team windows that give your stream spots the most started games with the fewest adds.

The inputs are plain data, so the tests need no Yahoo pages:
- days: the Days of the planning window from slots.open_slots_by_day(), made from the roster WITHOUT the players
  in the stream spots. games: {day: set of NBA teams that play}, from slots.team_games().
- spots: one StreamSpot for each stream spot. A spot is empty or holds a player who can be dropped.
- free_agents: one Option for each free agent, with his values.

The search (_Search) looks at the open days only, in order. On each open day, each spot keeps its player or takes
a new free agent who starts that day. An add on a day when the new player does not start is never better than
the same add on his first started game, so the search tries only those adds. The search tries all the other
choices. To keep it fast, it sees a player only as his key: the open days that are left on which his team plays,
and his positions. Two players with the same key give the same started games, and a cache holds the best result
for each day, set of keys and adds left. For the value tiebreak, each key in the search also holds the value of
the player (see _Search). The search does not know which players were dropped earlier in the
week, so a plan can use the same key twice. The plan then takes a different player with that key when one exists.
"""
from dataclasses import dataclass
from datetime import date
from functools import cache
from itertools import combinations

from fantasyhoops.adds.readers import Player
from fantasyhoops.core.lineup import best_lineup

TEAMS_TO_READ = 8  # the teams with the most open days. The planner reads the free agents of these teams.
OPTIONS = 3  # window options for each team window
EMPTY = ((), (), 0.0)  # the key of an empty spot, or of a player with no games on the open days that are left


@dataclass(frozen=True)
class Option:
    """A free agent that a plan can add, with his values.

    projected_value: the per-game value of Yahoo's projection for the next 7 days. None if Yahoo has no projection.
    recent_value: the per-game value of his averages in the last 14 days. None if he has no games in those days.
    blended_value: the per-game value of the blended line (adds/blend.py). None if he has no projection and no
    recent games. An Option made without a blended value uses the projected value.
    """
    player: Player
    projected_value: float | None
    recent_value: float | None = None
    blended_value: float | None = None

    @property
    def value(self):
        """The value that puts the options in order and breaks ties between plans: the blended value."""
        return self.projected_value if self.blended_value is None else self.blended_value


@dataclass(frozen=True)
class StreamSpot:
    """A roster spot that a plan can fill with free agents.

    holder: the Option of the player who holds the spot now and who can be dropped, or None for an empty spot.
    A holder plays in the spot until the plan adds a player to it. The add drops him.
    """
    holder: Option | None = None


@dataclass(frozen=True)
class TeamWindow:
    """A run of days in which one stream spot holds a player from one NBA team.

    spot: the index of the stream spot, from 0.
    add_day: the latest day for the add that keeps all the started games of the window. None for the window of
    a holder (no add).
    last_day: the last day of the window: the day before the next add to the spot, or the last day of the plan.
    started: the days of the window with a started game.
    player: the player that the search used. options: the best free agents on the team who fit the window (the
    plan keeps all its started games with him), best value first. The list has OPTIONS players or fewer.
    """
    spot: int
    team: str
    add_day: date | None
    last_day: date
    started: tuple
    player: Option
    options: tuple


@dataclass(frozen=True)
class Plan:
    """A plan for the stream spots: its team windows in order of spot and day, its started games and its adds.

    value: the total blended value of the started games (the sum of Option.value for each started game).
    """
    windows: tuple
    started_games: int
    adds: int
    value: float = 0.0

    @property
    def score(self):
        return plan_score(self.started_games, self.adds, self.value)


def plan_score(started_games, adds, value=0.0):
    """The plan score as a sort key, higher is better: the most started games, then the fewest adds, then the
    highest total blended value of the started games."""
    return started_games, -adds, value


@dataclass(frozen=True)
class TeamRank:
    """One NBA team in the ranking: the open days that it plays on and the open slots of those days."""
    team: str
    open_days: tuple
    open_slots: int


def rank_teams(days, games):
    """The NBA teams that play on an open day, by open days covered, then open slots covered, then name."""
    open_days = [d for d in days if d.open]
    teams = set().union(*(games[d.date] for d in open_days))
    ranks = [TeamRank(team=t,
                      open_days=tuple(d.date for d in open_days if t in games[d.date]),
                      open_slots=sum(len(d.open) for d in open_days if t in games[d.date])) for t in teams]
    return sorted(ranks, key=lambda r: (-len(r.open_days), -r.open_slots, r.team))


def teams_to_read(ranking, count=TEAMS_TO_READ):
    """The teams whose free agents the planner reads: the first count teams of the ranking.

    The list also gets the best team for each open day that the first teams do not cover.
    """
    teams = [r.team for r in ranking[:count]]
    covered = {d for r in ranking[:count] for d in r.open_days}
    for r in ranking[count:]:
        if set(r.open_days) - covered:
            teams.append(r.team)
            covered |= set(r.open_days)
    return teams


def schedule_plan(days, games, spots, free_agents, adds_left, slots, score=plan_score):
    """The best Plan by score() for the stream spots. It uses adds_left adds or fewer.

    days, games, spots and free_agents: see the module docstring. A free agent who is out or who has no
    value is not a candidate. slots: the position slots, cfg["league"]["slots"].
    score: a function (started games, adds, total value of the started games) -> sort key, higher is better.
    The search adds these three numbers over the days, so the key must depend only on their totals.
    """
    return _Search(days, games, spots, free_agents, slots, score).plan(adds_left)


def _value(option):
    """The value of an Option for the plan score. 0 for a holder with no value."""
    return 0.0 if option.value is None else option.value


class _Search:
    """The search for one set of inputs. k is the index of an open day in self.open. i is the index of a day.

    A key here is (open days, positions, value): the key of the module docstring and the value of the player.
    For each base key (open days, positions), the search gives an added player the best value of the free agents
    with that base key who are not in a spot now.
    """

    def __init__(self, days, games, spots, free_agents, slots, score=plan_score):
        self.days, self.games, self.slots, self.score = days, games, slots, score
        self.open = [i for i, d in enumerate(days) if d.open]
        self.holders = [s.holder for s in spots]
        self.fas = sorted((o for o in free_agents if o.value is not None and not o.player.out),
                          key=lambda o: -o.value)
        # groups[k]: (base key, values of the free agents with that base key, best first) for the free agents who
        # play on open day k, in order of the best value with that base key.
        self.groups = []
        for k in range(len(self.open)):
            group = {}
            for o in self.fas:
                base = self.key(o, k)[:2]
                if base[0][:1] == (k,):
                    group.setdefault(base, []).append(o.value)
            self.groups.append(list(group.items()))

    def plays(self, option, i):
        return option.player.team in self.games[self.days[i].date]

    def key(self, option, k):
        """The key of a player on open day k: (the open days from k on which his team plays, his positions, value)."""
        return self._key(option.player.team, tuple(sorted(option.player.positions)), k, _value(option))

    @cache
    def _key(self, team, positions, k, value):
        days = tuple(j for j in range(k, len(self.open)) if team in self.games[self.days[self.open[j]].date])
        return (days, positions, value) if days else EMPTY

    @cache
    def count(self, k, keys):
        """(started games, their total value) of the stream spots on open day k, for a sorted tuple of keys."""
        i = self.open[k]
        base = [set(p.positions) for _, p in self.days[i].starters] + [set(p.positions) for p in self.days[i].bench]
        playing = sorted((key for key in keys if key[0][:1] == (k,)), key=lambda key: -key[2])
        lineup = best_lineup(base + [set(key[1]) for key in playing], self.slots)
        started = [playing[j - len(base)][2] for j in lineup if j >= len(base)]
        return len(started), sum(started)

    @staticmethod
    def _free_value(base, values, kept):
        """The best value of the free agents with this base key who are not in kept, or None if all are in kept."""
        held = [key[2] for key in kept if key[:2] == base]
        for value in values:
            if value in held:
                held.remove(value)
            else:
                return value
        return None

    def moves(self, k, occ, adds):
        """The choices on open day k: (new keys, removed keys, added keys). Each added player starts on day k."""
        yield occ, (), ()
        for n in range(1, min(adds, len(occ)) + 1):
            for removed in sorted(set(combinations(occ, n))):
                kept = list(occ)
                for key in removed:
                    kept.remove(key)
                for added in self._picks(k, kept, n, 0):
                    if not set(added) & set(removed):
                        yield tuple(sorted(kept + list(added))), removed, added

    def _picks(self, k, kept, n, first):
        """The ways to add n players, each one a new starter on open day k, from groups[k][first:]."""
        if n == 0:
            yield ()
            return
        now = self.count(k, tuple(sorted(kept)))[0]
        for g in range(first, len(self.groups[k])):
            base, values = self.groups[k][g]
            value = self._free_value(base, values, kept)
            key = (*base, value)
            if value is not None and self.count(k, tuple(sorted(kept + [key])))[0] == now + 1:
                for rest in self._picks(k, kept + [key], n - 1, g):
                    yield (key, *rest)

    def plan(self, adds_left):
        @cache
        def best(k, occ, adds):
            """(started games, adds, value, moves) for open days k and later. moves: (k, removed keys, added keys).

            value: the total value of the started games."""
            if k == len(self.open):
                return 0, 0, 0.0, ()
            top = None
            for keys, removed, added in self.moves(k, occ, adds):
                started, spent, value, moves = best(k + 1, tuple(sorted(_next(key, k) for key in keys)),
                                                    adds - len(added))
                count, day_value = self.count(k, keys)
                found = (started + count, spent + len(added), value + day_value,
                         ((k, removed, added), *moves) if added else moves)
                if top is None or self.score(*found[:3]) > self.score(*top[:3]):
                    top = found
            return top

        start = tuple(sorted(self.key(h, 0) if h else EMPTY for h in self.holders))
        return self._plan(self._timelines(best(0, start, adds_left)[3]))

    def _timelines(self, moves):
        """For each spot: the list of (Option, index of the first day). A holder starts on day 0."""
        spots = [[(h, 0)] if h else [] for h in self.holders]
        values = [_value(h) if h else 0.0 for h in self.holders]  # the value that the search gave each spot now
        used = {h for h in self.holders if h}
        for k, removed, added in moves:
            now = [t[-1][0] if t else None for t in spots]
            held = [(*self.key(o, k)[:2], v) if o and self.key(o, k) != EMPTY else EMPTY
                    for o, v in zip(now, values)]
            free = []
            for key in removed:
                free.append(next(s for s in range(len(now)) if s not in free and held[s] == key))
            for s, key in zip(free, added):
                # The best free agent with this base key who is not in a spot now. A player who was not in the plan
                # before comes first, because Yahoo puts a dropped player on waivers. Of those, a player with the
                # value that the search used comes first.
                fits = [o for o in self.fas if self.key(o, k)[:2] == key[:2] and o not in now]
                same = [o for o in fits if o.value == key[2]]
                o = next((o for o in same + fits if o not in used), (same + fits)[0])
                used.add(o)
                now[s], values[s] = o, key[2]
                spots[s].append((o, self.open[k]))
        return spots

    def starters(self, i, players):
        """The players who start on day i, as a set. players: the players in the stream spots on day i."""
        playing = sorted((o for o in players if self.plays(o, i)), key=lambda o: -_value(o))
        base = [set(p.positions) for _, p in self.days[i].starters] + [set(p.positions) for p in self.days[i].bench]
        lineup = best_lineup(base + [set(o.player.positions) for o in playing], self.slots)
        return {playing[j - len(base)] for j in lineup if j >= len(base)}

    def _started(self, spots):
        """{(spot, Option): days with a started game} for the timelines of the spots."""
        out = {}
        for i, day in enumerate(self.days):
            here = {}
            for s, timeline in enumerate(spots):
                current = [o for o, first in timeline if first <= i]
                if current:
                    here[current[-1]] = s
            for o in self.starters(i, here):
                out.setdefault((here[o], o), []).append(day.date)
        return out

    def _plan(self, spots):
        started = self._started(spots)
        total = sum(len(v) for v in started.values())
        used = {o for timeline in spots for o, _ in timeline}
        windows = []
        for s, timeline in enumerate(spots):
            for n, (o, first) in enumerate(timeline):
                holder = n == 0 and o is self.holders[s]
                last = timeline[n + 1][1] - 1 if n + 1 < len(timeline) else len(self.days) - 1
                windows.append(TeamWindow(
                    spot=s, team=o.player.team,
                    add_day=None if holder else self.days[first].date,
                    last_day=self.days[last].date,
                    started=tuple(started.get((s, o), ())),
                    player=o,
                    options=() if holder else self._options(spots, s, n, used, total)))
        return Plan(windows=tuple(windows), started_games=total, adds=sum(w.add_day is not None for w in windows),
                    value=sum(_value(o) * len(d) for (_, o), d in started.items()))

    def _options(self, spots, s, n, used, total):
        """The best free agents on the team of window n of spot s with whom the plan keeps all its started games."""
        o, first = spots[s][n]
        fits = []
        for other in self.fas:
            if other.player.team != o.player.team or (other in used and other != o):
                continue
            swapped = [list(t) for t in spots]
            swapped[s][n] = (other, first)
            if sum(len(v) for v in self._started(swapped).values()) >= total:
                fits.append(other)
        return tuple(fits[:OPTIONS])


def _next(key, k):
    """The key on open day k + 1."""
    days, positions, value = key
    days = days[1:] if days[:1] == (k,) else days
    return (days, positions, value) if days else EMPTY
