"""The schedule plan: the team windows that give your stream spots the most started games with the fewest adds.

The aggressive plan uses the same search with another score: aggressive_score(), the value of the started games
above an empty slot. The design of both plans is in docs/adds/README.md, "The plans".

The inputs are plain data, so the tests need no Yahoo pages:
- days: the Days of the planning window from slots.open_slots_by_day(), made from the roster WITHOUT the players
  in the stream spots. games: {day: set of NBA teams that play}, from slots.team_games().
- spots: one StreamSpot for each stream spot. A spot is empty or holds a player who can be dropped.
- free_agents: one Option for each free agent, with his values. A waiver player (Player.clear_day) is a candidate
  only on the days after his clear day. His add is a waiver claim, and it uses one add.

The search (_Search) looks at the open days only, in order. On each open day, each spot keeps its player or takes
a new free agent who starts that day. An add on a day when the new player does not start is never better than
the same add on his first started game, so the search tries only those adds. The search tries all the other
choices. To keep it fast, it sees a player only as his key: the open days that are left on which his team plays,
his positions and his rest days. Two players with the same key give the same started games, and a cache holds the
best result for each day, set of keys and adds left. For the value tiebreak, each key in the search also holds the
value of the player (see _Search). The search does not know which players were dropped earlier in the
week, so a plan can use the same key twice. The plan then takes a different player with that key when one exists.

Rest risk (adds/rest.py): a game of a player on the rest list on the second night of a back-to-back counts less
than 1 started game (counted_games()). So the started games of a plan can be a fraction.

Next week (#60): a player who holds a stream spot on the last day of the week can stay on the roster next week.
With next_week ({team: games next week}) and next_weight, he adds next_weight x his games next week to the
next-week totals of the plan (next_games, next_value). The schedule score uses them as the last tiebreak. The
aggressive score adds their value above an empty slot, never less than 0. In the search, each game next week is
one more open day of the key after the last open day, so the search knows the next-week games of each spot at
the end of the week.

Run time (#85): each search counts its calls of best() and its unique states in timing.WORK. The counts change
no plan.
"""
import math
from dataclasses import dataclass, replace
from datetime import date
from functools import cache
from itertools import combinations
from typing import NamedTuple

from fantasyhoops.adds import timing
from fantasyhoops.adds.readers import Player, available_on
from fantasyhoops.adds.trends import Trend
from fantasyhoops.core.lineup import best_lineup

TEAMS_TO_READ = 8  # the teams with the most open days. The planner reads the free agents of these teams.
OPTIONS = 3  # window options for each team window
DIGITS = 6  # the plan score rounds the started games to this number of decimals, so that equal sums tie


def counted_games(rests, days):
    """The started games that one game on each of days counts in total: 1 for each game, or the count of a rest day.

    rests: ((day, count), ...), for example Option.rest_games. A day here can be a date or an open-day index.
    """
    counts = dict(rests)
    return sum(counts.get(d, 1.0) for d in days)


class Key(NamedTuple):
    """A player as the search sees him on open day k (see _Search).

    days: the open days from k on which he can start. positions: his positions, sorted. rests: (open day, count)
    for each open day of days on which a game counts less than 1. value: his value for the plan score.
    """
    days: tuple
    positions: tuple
    rests: tuple
    value: float

    @property
    def base(self):
        """The key with no value: (days, positions, rests)."""
        return self.days, self.positions, self.rests


EMPTY = Key((), (), (), 0.0)  # the key of an empty spot, or of a player with no games on the open days that are left


@dataclass(frozen=True)
class Option:
    """A free agent that a plan can add, with his values.

    projected_value: the per-game value of Yahoo's projection for the next 7 days. None if Yahoo has no projection.
    recent_value: the per-game value of his averages in the last 14 days. None if he has no games in those days.
    blended_value: the per-game value of the blended line (adds/blend.py). None if he has no projection and no
    recent games. An Option made without a blended value uses the projected value.
    trend: his Trend from Transaction Trends. None if he is not on the pages of this week.
    matchup_value: the per-game value of the blended line with the matchup weights (adds/matchup.py). None if the
    run did not compute it.
    rest_games: ((day, count), ...) for each second night of a back-to-back on which he can rest (adds/rest.py).
    A game on that day counts count started games. Empty for a player who is not on the rest list.
    role_up: the names of the absent starters on his NBA team who share one of his positions (adds/role_up.py).
    """
    player: Player
    projected_value: float | None
    recent_value: float | None = None
    blended_value: float | None = None
    trend: Trend | None = None
    matchup_value: float | None = None
    rest_games: tuple = ()
    role_up: tuple = ()

    @property
    def value(self):
        """The value that puts the options in order and breaks ties between plans: the blended value."""
        return self.projected_value if self.blended_value is None else self.blended_value

    @property
    def match(self):
        """The matchup value. The blended value if the run did not compute a matchup value."""
        return self.value if self.matchup_value is None else self.matchup_value


def option_order(option):
    """The sort key of the options, best first: the highest value, then the most adds this week, then today.

    The trend is only a tiebreak between options. It never changes the plan score.
    """
    t = option.trend or Trend(0, 0)
    return -option.value, -t.adds_week, -t.adds_today


def waiver_options(options):
    """The options on waivers (W) who have a value, best value first. The terminal and the page list these."""
    return sorted((o for o in options if o.player.on_waivers and o.value is not None), key=lambda o: -o.value)


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

    started_games: the counted started games (counted_games() of each player). A fraction if a player
    on the rest list starts on a second night.
    value: the total blended value of the started games (the sum of Option.value x the count of each started game).
    next_games: next_weight x the games next week of the players who hold a stream spot on the last day of the
    week. next_value: the sum of next_weight x his games next week x his value, for each of these players.
    """
    windows: tuple
    started_games: float
    adds: int
    value: float = 0.0
    next_games: float = 0.0
    next_value: float = 0.0

    @property
    def totals(self):
        """The arguments of a score function: (started games, adds, value, next games, next value)."""
        return self.started_games, self.adds, self.value, self.next_games, self.next_value

    @property
    def score(self):
        return plan_score(*self.totals)


def plan_score(started_games, adds, value=0.0, next_games=0.0, next_value=0.0):
    """The plan score as a sort key, higher is better: the most started games, then the fewest adds, then the
    highest total blended value of the started games, then the most weighted games next week (Plan.next_games).
    The started games can be a fraction. The score rounds them and the next-week games to DIGITS decimals, so that
    the same games in a different order give a tie. next_value: not used. A score function takes it, see
    aggressive_score()."""
    return round(started_games, DIGITS), -adds, value, round(next_games, DIGITS)


def aggressive_score(empty_value):
    """The score of the aggressive plan, as a function for schedule_plan(score=...).

    The score is the sum of the value above an empty slot of each started game: the total blended value minus
    empty_value for each started game. empty_value is the value of a stat line of zeros (value.empty_slot_value()),
    so each started game counts more than 0, and a better player counts more. Ties go to the plan with fewer
    adds, then to the plan with more started games.
    The next-week bonus adds the value above an empty slot of the weighted games next week (Plan.next_games and
    Plan.next_value). The bonus is never less than 0, so it never lowers the part of the score from this week.
    """
    def score(started_games, adds, value=0.0, next_games=0.0, next_value=0.0):
        bonus = max(0.0, next_value - empty_value * next_games)
        return value - empty_value * started_games + bonus, -adds, round(started_games, DIGITS)
    return score


def aggressive_plan(days, games, spots, free_agents, adds_left, slots, empty_value, next_week=None,
                    next_weight=0.0):
    """The best Plan by aggressive_score(empty_value). It uses adds_left adds or fewer.

    The arguments are the arguments of schedule_plan(). A holder with no season value (not in the projections
    file) gets empty_value, the lowest value, so that the plan does not keep him as an average player.
    """
    spots = [StreamSpot(replace(s.holder, projected_value=empty_value, blended_value=None))
             if s.holder and not _finite(s.holder.value) else s for s in spots]
    return schedule_plan(days, games, spots, free_agents, adds_left, slots, score=aggressive_score(empty_value),
                         next_week=next_week, next_weight=next_weight)


def next_week_totals(windows, next_week, next_weight):
    """(next games, next value) of a plan (see Plan) from its team windows.

    The last window of each spot holds the player on the last day of the week. A player who is Out gets no games.
    next_week: {team: games next week}, or None for no bonus.
    """
    last = [w.player for w in {w.spot: w for w in windows}.values() if not w.player.player.out]
    ahead = [next_weight * (next_week or {}).get(o.player.team, 0) for o in last]
    return sum(ahead), sum(g * _value(o) for g, o in zip(ahead, last))


def value_above_empty(plan, empty_value):
    """The aggressive score of a Plan: the total value of its started games above an empty slot."""
    return plan.value - empty_value * plan.started_games


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


def schedule_plan(days, games, spots, free_agents, adds_left, slots, score=plan_score, next_week=None,
                  next_weight=0.0):
    """The best Plan by score() for the stream spots. It uses adds_left adds or fewer.

    days, games, spots and free_agents: see the module docstring. A free agent who is out or who has no
    value is not a candidate. slots: the position slots, cfg["league"]["slots"].
    score: a function (started games, adds, total value of the started games, next games, next value) -> sort
    key, higher is better (see Plan.totals). The search adds these numbers over the days and the spots, so the key
    must depend only on their totals.
    next_week: {NBA team: its games next week} (slots.next_week_games()). next_weight: the part of a game this week
    that a game next week is worth, [adds] next_week_weight. With no next_week or a weight of 0, there is no bonus.
    """
    search = _Search(days, games, spots, free_agents, slots, score, next_week if next_weight else None, next_weight)
    return search.plan(adds_left)


def _finite(value):
    return value is not None and math.isfinite(value)


def _value(option):
    """The value of an Option for the plan score. 0 for a holder with no value or with no season value (-inf)."""
    return option.value if _finite(option.value) else 0.0


class _Search:
    """The search for one set of inputs. k is the index of an open day in self.open. i is the index of a day.

    A key here is (open days, positions, rest days, value): the key of the module docstring and the value of the
    player. rest days: (open day, count) for each open day of the key on which a game counts less than 1.
    For each base key (open days, positions, rest days), the search gives an added player the best value of the
    free agents with that base key who are not in a spot now.
    The open days of a key also hold one index from len(self.open) up for each game of his team next week. No
    real open day has these indexes, so the started games do not change.
    """

    def __init__(self, days, games, spots, free_agents, slots, score=plan_score, next_week=None, next_weight=0.0):
        self.days, self.games, self.slots, self.score = days, games, slots, score
        self.next_week, self.next_weight = next_week or {}, next_weight
        self.open = [i for i, d in enumerate(days) if d.open]
        self.holders = [s.holder for s in spots]
        self.fas = sorted((o for o in free_agents if o.value is not None and not o.player.out), key=option_order)
        # groups[k]: (base key, values of the free agents with that base key, best first) for the free agents who
        # play on open day k, in order of the best value with that base key.
        self.groups = []
        for k in range(len(self.open)):
            group = {}
            for o in self.fas:
                base = self.key(o, k).base
                if base[0][:1] == (k,):
                    group.setdefault(base, []).append(o.value)
            self.groups.append(list(group.items()))

    def plays(self, option, i):
        p, day = option.player, self.days[i].date
        return not p.out and p.available(day) and p.team in self.games[day]

    def key(self, option, k):
        """The key of a player on open day k: (the open days from k on which his team plays, his positions, his
        rest days, value).

        An Out player has no games. Only a holder can be Out, because the search skips Out free agents.
        A waiver player has no games on his clear day and before it.
        """
        p = option.player
        if p.out:
            return EMPTY
        return self._key(p.team, tuple(sorted(p.positions)), option.rest_games, k, _value(option), p.clear_day)

    @cache
    def _key(self, team, positions, rest_games, k, value, clear_day):
        dates = [self.days[self.open[j]].date for j in range(k, len(self.open))]
        days = tuple(j for j, d in enumerate(dates, k) if team in self.games[d] and available_on(clear_day, d))
        counts = dict(rest_games)
        rests = tuple((j, counts[dates[j - k]]) for j in days if dates[j - k] in counts)
        days += tuple(range(len(self.open), len(self.open) + self.next_week.get(team, 0)))
        return Key(days, positions, rests, value) if days else EMPTY

    @cache
    def count(self, k, keys):
        """(counted started games, their total value, starters) of the stream spots on open day k, for a sorted
        tuple of keys. starters: the number of players who start.

        The players with the highest count get the slots first, then the players with the higher value."""
        i = self.open[k]
        base = [set(p.positions) for _, p in self.days[i].starters] + [set(p.positions) for p in self.days[i].bench]
        playing = sorted((key for key in keys if key.days[:1] == (k,)),
                         key=lambda key: (-counted_games(key.rests, [k]), -key.value))
        lineup = best_lineup(base + [set(key.positions) for key in playing], self.slots)
        started = [playing[j - len(base)] for j in lineup if j >= len(base)]
        counts = [counted_games(key.rests, [k]) for key in started]
        return sum(counts), sum(c * key.value for c, key in zip(counts, started)), len(started)

    @staticmethod
    def _free_value(base, values, kept):
        """The best value of the free agents with this base key who are not in kept, or None if all are in kept."""
        held = [key.value for key in kept if key.base == base]
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
        now = self.count(k, tuple(sorted(kept)))[2]
        for g in range(first, len(self.groups[k])):
            base, values = self.groups[k][g]
            value = self._free_value(base, values, kept)
            key = Key(*base, value)
            if value is not None and self.count(k, tuple(sorted(kept + [key])))[2] == now + 1:
                for rest in self._picks(k, kept + [key], n - 1, g):
                    yield (key, *rest)

    def plan(self, adds_left):
        work = timing.WORK

        def best(k, occ, adds):
            """Count one call in timing.WORK, cache hits included, then give computed(k, occ, adds)."""
            work.tick()
            return computed(k, occ, adds)

        @cache
        def computed(k, occ, adds):
            """(started games, adds, value, next games, next value, moves) for open days k and later.

            value: the total value of the started games. next games, next value: see Plan. moves: (k, removed
            keys, added keys). After the last open day, the open days of each key are its games next week.
            Each call computes one unique state, and timing.WORK counts it."""
            work.state()
            if k == len(self.open):
                ahead = [self.next_weight * len(key.days) for key in occ]
                return 0, 0, 0.0, sum(ahead), sum(g * key.value for g, key in zip(ahead, occ)), ()
            top = None
            for keys, removed, added in self.moves(k, occ, adds):
                started, spent, value, *ahead, moves = best(k + 1, tuple(sorted(_next(key, k) for key in keys)),
                                                            adds - len(added))
                count, day_value, _ = self.count(k, keys)
                found = (started + count, spent + len(added), value + day_value, *ahead,
                         ((k, removed, added), *moves) if added else moves)
                if top is None or self.score(*found[:5]) > self.score(*top[:5]):
                    top = found
            return top

        start = tuple(sorted(self.key(h, 0) if h else EMPTY for h in self.holders))
        return self._plan(self._timelines(best(0, start, adds_left)[-1]))

    def _timelines(self, moves):
        """For each spot: the list of (Option, index of the first day). A holder starts on day 0."""
        spots = [[(h, 0)] if h else [] for h in self.holders]
        values = [_value(h) if h else 0.0 for h in self.holders]  # the value that the search gave each spot now
        used = {h for h in self.holders if h}
        for k, removed, added in moves:
            now = [t[-1][0] if t else None for t in spots]
            held = [Key(*self.key(o, k).base, v) if o and self.key(o, k) != EMPTY else EMPTY
                    for o, v in zip(now, values)]
            free = []
            for key in removed:
                free.append(next(s for s in range(len(now)) if s not in free and held[s] == key))
            for s, key in zip(free, added):
                # The best free agent with this base key who is not in a spot now. A player who was not in the plan
                # before comes first, because Yahoo puts a dropped player on waivers. Of those, a player with the
                # value that the search used comes first.
                fits = [o for o in self.fas if self.key(o, k).base == key.base and o not in now]
                same = [o for o in fits if o.value == key.value]
                o = next((o for o in same + fits if o not in used), (same + fits)[0])
                used.add(o)
                now[s], values[s] = o, key.value
                spots[s].append((o, self.open[k]))
        return spots

    def starters(self, i, players):
        """The players who start on day i, as a set. players: the players in the stream spots on day i.

        The players with the highest count get the slots first, then the players with the higher value (see count())."""
        day = self.days[i].date
        playing = sorted((o for o in players if self.plays(o, i)),
                         key=lambda o: (-counted_games(o.rest_games, [day]), -_value(o)))
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
        total = _counted(started)
        used = {o for timeline in spots for o, _ in timeline}
        windows = []
        for s, timeline in enumerate(spots):
            for n, (o, first) in enumerate(timeline):
                holder = n == 0 and o is self.holders[s]
                last = timeline[n + 1][1] - 1 if n + 1 < len(timeline) else len(self.days) - 1
                if last < first:
                    continue  # a holder whom the plan drops on the first day has no window
                windows.append(TeamWindow(
                    spot=s, team=o.player.team,
                    add_day=None if holder else self.days[first].date,
                    last_day=self.days[last].date,
                    started=tuple(started.get((s, o), ())),
                    player=o,
                    options=() if holder else self._options(spots, s, n, used, total)))
        next_games, next_value = next_week_totals(windows, self.next_week, self.next_weight)
        return Plan(windows=tuple(windows), started_games=total, adds=sum(w.add_day is not None for w in windows),
                    value=sum(_value(o) * counted_games(o.rest_games, days) for (_, o), days in started.items()),
                    next_games=next_games, next_value=next_value)

    def _options(self, spots, s, n, used, total):
        """The best free agents on the team of window n of spot s with whom the plan keeps all its counted started
        games."""
        o, first = spots[s][n]
        fits = []
        for other in self.fas:
            if other.player.team != o.player.team or (other in used and other != o):
                continue
            swapped = [list(t) for t in spots]
            swapped[s][n] = (other, first)
            if round(_counted(self._started(swapped)), DIGITS) >= round(total, DIGITS):
                fits.append(other)
        return tuple(fits[:OPTIONS])


def _counted(started):
    """The counted started games of {(spot, Option): days with a started game}."""
    return sum(counted_games(o.rest_games, days) for (_, o), days in started.items())


def _next(key, k):
    """The key on open day k + 1."""
    days = key.days[1:] if key.days[:1] == (k,) else key.days
    rests = tuple(r for r in key.rests if r[0] > k)
    return Key(days, key.positions, rests, key.value) if days else EMPTY
