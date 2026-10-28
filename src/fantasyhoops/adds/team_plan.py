"""The team plan (#140): the adds of the week as NBA teams and open slots. It names no player.

The design is in docs/adds/README.md, "The team plan". The module writes no files.

team_plan() finds the adds that give your stream spots the most started games. If two plans have the same started
games, the plan with fewer adds wins. If the adds are also the same, the plan whose last teams have more games next
week wins. The free agents are not an input. An add is a player of one NBA team who can fill each open slot. After the
search, each add gets its slots and its teams:
- slots: the open slots that the new player can fill on each day that he starts (slots_of()). "Util" means any
  position.
- teams: each NBA team that plays on the add day and gives the plan the same score (teams_of()). These teams fit the
  add equally. The run reads their free agents, so the free-agent table has the players of the plan.

The inputs are plain data, so the tests need no Yahoo pages:
- days: the Days of the planning window from slots.open_slots_by_day(), made from the roster WITHOUT the players in
  the stream spots. games: {day: set of NBA teams that play}, from slots.team_games().
- spots: one planner.StreamSpot for each stream spot. A spot is empty or holds a player who can be dropped. A holder
  plays in his spot until the first add to it. A holder on the rest list counts less on a second night
  (planner.counted_games()). An Out holder has no games.

The search (_Search) looks at the open days in order. On each open day, each spot keeps its player or takes a new
team that plays that day. It sees a player only as his key: the open days that are left on which his team plays, his
positions and his rest days. Two teams with the same open days are the same choice. A team whose open days are all in
the open days of another team is never a better choice, so the search does not try it. The search counts its calls
and its unique states in timing.WORK (#85).

Next week (#60): the last player of each spot can stay next week. Each game of his team next week counts next_weight
in the last tiebreak. In the search, each game next week is one more open day of the key after the last open day.
"""

from dataclasses import dataclass
from datetime import date
from functools import cache
from itertools import combinations
from typing import NamedTuple

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import DIGITS, counted_games
from fantasyhoops.core.lineup import best_lineup

UTIL = "Util"  # the slot label of an add that fits any position


class Key(NamedTuple):
    """A player as the search sees him on open day k.

    days: the open days from k on which he plays, then one index from len(open days) up for each game next week.
    positions: his positions, sorted. A new player has all positions. rests: (open day, count) for each open day of
    days on which a game counts less than 1.
    """

    days: tuple
    positions: tuple
    rests: tuple = ()


EMPTY = Key((), ())  # the key of an empty spot, or of a player with no games on the open days that are left


@dataclass(frozen=True)
class TeamAdd:
    """One add of the team plan.

    spot: the index of the stream spot, from 0. day: the add day, the first day that he starts. last_day: the last day
    that he holds the spot: the day before the next add to the spot, or the last day of the planning window.
    slots: the open slots that he can fill on each day that he starts, in slot order, or ("Util",) for any position.
    teams: the NBA teams that fit the add equally, sorted. starts: the days that he starts with each team of teams.
    mixed: True if the teams of the add start on different days. Then starts holds only the days of all teams.
    """

    spot: int
    day: date
    last_day: date
    slots: tuple
    teams: tuple
    starts: tuple
    mixed: bool = False


@dataclass(frozen=True)
class TeamPlan:
    """The team plan: its adds in order of day, then spot. started_games: the counted started games of the stream
    spots. next_games: next_weight x the games next week of the last player of each spot."""

    adds: tuple
    started_games: float
    next_games: float = 0.0


@dataclass(frozen=True)
class _Member:
    """A player in a stream spot: a holder (his Option) or a new player of team (holder None)."""

    team: str
    positions: tuple
    rests: tuple = ()
    out: bool = False
    holder: object = None


def _holder(option):
    p = option.player
    return _Member(p.team, tuple(sorted(p.positions)), option.rest_games, p.out, option)


def team_plan(days, games, spots, adds_left, slots, next_week=None, next_weight=0.0):
    """The best TeamPlan for the stream spots. It uses adds_left adds or fewer.

    slots: the position slots, cfg["league"]["slots"]. next_week: {NBA team: its games next week}
    (slots.next_week_games()). next_weight: [adds] next_week_weight. With no next_week or a weight of 0, the next-week
    tiebreak is off.
    """
    search = _Search(days, games, [s.holder for s in spots], slots, next_week if next_weight else None, next_weight)
    return search.plan(adds_left)


class _Search:
    """The search for one set of inputs. k is the index of an open day in self.open. i is the index of a day."""

    def __init__(self, days, games, holders, slots, next_week=None, next_weight=0.0):
        self.days, self.games, self.slots = days, games, slots
        self.next_week, self.next_weight = next_week or {}, next_weight
        self.open = [i for i, d in enumerate(days) if d.open]
        self.holders = [_holder(h) if h else None for h in holders]
        self.every = tuple(sorted(slots))  # the positions of a new player
        # choices[k]: (key, team) for the teams that play on open day k, one for each key, with no team whose open
        # days are all in the open days of another team.
        self.choices = []
        for k in range(len(self.open)):
            teams = sorted(self.games[self.days[self.open[k]].date])
            keys = {}
            for t in teams:
                keys.setdefault(self.key(_Member(t, self.every), k), t)
            ranked = sorted(keys.items(), key=lambda kt: (-len(kt[0].days), kt[1]))
            kept = []
            for key, team in ranked:
                if not any(set(key.days) <= set(other.days) for other, _ in kept):
                    kept.append((key, team))
            self.choices.append(kept)

    def key(self, member, k):
        """The Key of a member on open day k. An Out holder has no games."""
        if member is None or member.out:
            return EMPTY
        return self._key(member.team, member.positions, member.rests, k)

    @cache
    def _key(self, team, positions, rest_games, k):
        dates = [self.days[self.open[j]].date for j in range(k, len(self.open))]
        days = tuple(j for j, d in enumerate(dates, k) if team in self.games[d])
        counts = dict(rest_games)
        rests = tuple((j, counts[dates[j - k]]) for j in days if dates[j - k] in counts)
        days += tuple(range(len(self.open), len(self.open) + self.next_week.get(team, 0)))
        return Key(days, positions, rests) if days else EMPTY

    def _base(self, i):
        """The positions of the kept players who play on day i: the starters, then the bench."""
        day = self.days[i]
        return [set(p.positions) for _, p in day.starters] + [set(p.positions) for p in day.bench]

    @cache
    def count(self, k, keys):
        """(counted started games, starters) of the stream spots on open day k, for a sorted tuple of keys.

        The players with the highest count get the slots first."""
        base = self._base(self.open[k])
        playing = sorted((key for key in keys if key.days[:1] == (k,)), key=lambda key: -counted_games(key.rests, [k]))
        lineup = best_lineup(base + [set(key.positions) for key in playing], self.slots)
        started = [playing[j - len(base)] for j in lineup if j >= len(base)]
        return sum(counted_games(key.rests, [k]) for key in started), len(started)

    def moves(self, k, occ, adds):
        """The choices on open day k: (new keys, removed keys, added keys). Each added player starts on day k."""
        yield occ, (), ()
        for n in range(1, min(adds, len(occ)) + 1):
            for removed in sorted(set(combinations(occ, n))):
                kept = list(occ)
                for key in removed:
                    kept.remove(key)
                for added in self._picks(k, kept, n, 0):
                    yield tuple(sorted(kept + list(added))), removed, added

    def _picks(self, k, kept, n, first):
        """The ways to add n players, each one a new starter on open day k, from choices[k][first:]."""
        if n == 0:
            yield ()
            return
        now = self.count(k, tuple(sorted(kept)))[1]
        for c in range(first, len(self.choices[k])):
            key = self.choices[k][c][0]
            if self.count(k, tuple(sorted(kept + [key])))[1] == now + 1:
                for rest in self._picks(k, kept + [key], n - 1, c):
                    yield (key, *rest)

    @staticmethod
    def score(started, adds, ahead):
        """The plan score as a sort key, higher is better. It rounds the games, so that equal sums tie."""
        return round(started, DIGITS), -adds, round(ahead, DIGITS)

    def plan(self, adds_left):
        work = timing.WORK

        def best(k, occ, adds):
            """Count one call in timing.WORK, cache hits included, then give computed(k, occ, adds)."""
            work.tick()
            return computed(k, occ, adds)

        @cache
        def computed(k, occ, adds):
            """(started games, adds, next games, moves) for open days k and later. moves: (k, removed keys, added
            keys). After the last open day, the open days of each key are its games next week."""
            work.state()
            if k == len(self.open):
                return 0, 0, sum(self.next_weight * len(key.days) for key in occ), ()
            top = None
            for keys, removed, added in self.moves(k, occ, adds):
                started, spent, ahead, moves = best(
                    k + 1, tuple(sorted(_next(key, k) for key in keys)), adds - len(added)
                )
                found = (
                    started + self.count(k, keys)[0],
                    spent + len(added),
                    ahead,
                    ((k, removed, added), *moves) if added else moves,
                )
                if top is None or self.score(*found[:3]) > self.score(*top[:3]):
                    top = found
            return top

        start = tuple(sorted(self.key(h, 0) for h in self.holders))
        return self._plan(self._timelines(best(0, start, adds_left)[-1]))

    def _timelines(self, moves):
        """For each spot: the list of (member, index of the first day). A holder starts on day 0."""
        spots = [[(h, 0)] if h else [] for h in self.holders]
        for k, removed, added in moves:
            held = [self.key(t[-1][0], k) if t else EMPTY for t in spots]
            free = []
            for key in removed:
                free.append(next(s for s in range(len(spots)) if s not in free and held[s] == key))
            for s, key in zip(free, added):
                team = next(t for key2, t in self.choices[k] if key2 == key)
                spots[s].append((_Member(team, self.every), self.open[k]))
        return spots

    def starters(self, i, here):
        """The spots whose player starts on day i, as a set. here: {spot: member} of the players in the spots."""
        day = self.days[i].date
        playing = sorted(
            (s for s, m in here.items() if not m.out and m.team in self.games[day]),
            key=lambda s: (-counted_games(here[s].rests, [day]), s),
        )
        base = self._base(i)
        lineup = best_lineup(base + [set(here[s].positions) for s in playing], self.slots)
        return {playing[j - len(base)] for j in lineup if j >= len(base)}

    def started(self, spots):
        """{(spot, n): days with a started game} of member n of each spot, for the timelines of the spots."""
        out = {}
        for i in range(len(self.days)):
            here = {}
            for s, timeline in enumerate(spots):
                current = [n for n, (_, first) in enumerate(timeline) if first <= i]
                if current:
                    here[s] = current[-1]
            members = {s: spots[s][n][0] for s, n in here.items()}
            for s in self.starters(i, members):
                out.setdefault((s, here[s]), []).append(self.days[i].date)
        return out

    def totals(self, spots):
        """(counted started games, next games) of the timelines of the spots."""
        started = self.started(spots)
        games = sum(counted_games(spots[s][n][0].rests, days) for (s, n), days in started.items())
        last = [t[-1][0] for t in spots if t and not t[-1][0].out]
        return games, sum(self.next_weight * self.next_week.get(m.team, 0) for m in last)

    def _plan(self, spots):
        total, ahead = self.totals(spots)
        adds = []
        fixed = [list(t) for t in spots]  # the timelines, with the slots of each add that has its slots
        found = []
        for s, timeline in enumerate(spots):
            for n, (m, first) in enumerate(timeline):
                if m.holder is None:
                    found.append((first, s, n))
        for first, s, n in sorted(found):
            teams, starts, mixed = self.teams_of(spots, s, n, total, ahead)
            slots = self.slots_of(fixed, s, n, starts)
            fixed[s][n] = (_Member(fixed[s][n][0].team, self._positions(slots)), first)
            last = spots[s][n + 1][1] - 1 if n + 1 < len(spots[s]) else len(self.days) - 1
            adds.append(TeamAdd(s, self.days[first].date, self.days[last].date, slots, teams, starts, mixed))
        return TeamPlan(adds=tuple(adds), started_games=total, next_games=ahead)

    def teams_of(self, spots, s, n, total, ahead):
        """(teams, starts, mixed) of member n of spot s (see TeamAdd). A team fits if it plays on the add day, starts
        on the add day and gives the plan the same score."""
        first = spots[s][n][1]
        day = self.days[first].date
        teams, days = [], []
        for team in sorted(self.games[day]):
            swapped = [list(t) for t in spots]
            swapped[s][n] = (_Member(team, self.every), first)
            started = self.started(swapped).get((s, n), [])
            games, next_games = self.totals(swapped)
            if day in started and self.score(games, 0, next_games) >= self.score(total, 0, ahead):
                teams.append(team)
                days.append(set(started))
        common_days = set.intersection(*days)
        return tuple(teams), tuple(sorted(common_days)), any(d != common_days for d in days)

    def slots_of(self, spots, s, n, starts):
        """The slots of member n of spot s: the positions with which he starts on each day of starts, and with which
        the stream spots keep their starters. The other new players keep the slots that they got before. ("Util",) if
        each position fits. With no position that fits each day, the positions that fit one day or more."""
        i_of = {d.date: i for i, d in enumerate(self.days)}
        member, first = spots[s][n]
        each, some = set(self.slots), set()
        for day in starts:
            i = i_of[day]
            here = {}
            for t, timeline in enumerate(spots):
                current = [m for m, f in timeline if f <= i]
                if current:
                    here[t] = current[-1]
            want = len(self.starters(i, here))
            fits = set()
            for p in self.slots:
                here[s] = _Member(member.team, (p,))
                started = self.starters(i, here)
                if s in started and len(started) == want:
                    fits.add(p)
            here[s] = member
            each &= fits
            some |= fits
        if each == set(self.slots):
            return (UTIL,)
        return tuple(p for p in self.slots if p in (each or some))

    def _positions(self, slots):
        return self.every if slots == (UTIL,) else tuple(sorted(slots))


def _next(key, k):
    """The key on open day k + 1."""
    days = key.days[1:] if key.days[:1] == (k,) else key.days
    rests = tuple(r for r in key.rests if r[0] > k)
    return Key(days, key.positions, rests) if days else EMPTY
