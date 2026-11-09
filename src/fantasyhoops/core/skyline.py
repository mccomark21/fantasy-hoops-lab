"""Schedule Skyline: the team-agnostic facts of one fantasy week (Mon to Sun) of the NBA schedule.

week_facts() gives the games per night, the light nights, the add ladder for one stream spot, the anchor nights and
the week type. The adds page and the Bluesky image draw these facts. This module draws nothing and writes no files.
The settings are [quality_games] max_games_per_day, [quality_games] light_night_weight and [skyline] in config.toml.

The ladder score: each game counts 1, and each game on a light night counts light_night_weight. The adds team plan
uses the same weight (adds/team_plan.py). With a weight of 1, the light-night games only break ties.

All counts come from one count: the NBA games of each night (the rows of data/schedule.csv ÷ 2).
"""

from dataclasses import dataclass
from datetime import timedelta
from itertools import combinations

import pandas as pd

from fantasyhoops.core.common import load_config

DAYS = 7

# The week types, in the order of the check. The first match sets the type.
DEAD_DAY, ANCHOR, HEAVY_TEAM, STREAM = "dead-day", "anchor", "heavy-team", "stream"


@dataclass(frozen=True)
class Leg:
    """The days from first to last (last exclusive, 0 = Monday) that one team holds the stream spot.

    teams: the teams with the best score (see the module text), then the most light-night games, in the leg. The
    teams with the largest group of the same game days come first. pattern: the game days of that group (the dots of
    the poster).
    b2b: the back-to-back pairs of each team in teams. decisive_b2b: the back-to-back pairs of pattern that the
    poster names, or () when the leg does not depend on a back-to-back. dot_teams: the teams whose game days are
    pattern, or None when each team of teams has these days.
    """

    first: int
    last: int
    games: int
    light: int
    teams: tuple
    pattern: tuple
    scarce: bool
    b2b: dict
    decisive_b2b: tuple
    dot_teams: tuple = None

    @property
    def team_count(self):
        return len(self.teams)

    @property
    def named(self):
        """The teams that the poster names: the teams of a scarce leg whose game days are the dots, else ().

        Decision (2026-11-08, owner): a chip names only a team whose game days match the dots. The other teams with
        the same score play on other days, so the poster leaves them out."""
        if not self.scarce:
            return ()
        return self.teams if self.dot_teams is None else self.dot_teams

    @property
    def others(self):
        """The teams of a scarce leg with the same score on other days than the dots: teams that named leaves out."""
        return tuple(t for t in self.teams if t not in self.named) if self.scarce else ()


@dataclass(frozen=True)
class Rung:
    """The plan for one stream spot with a number of adds.

    cuts: the day indexes where a new leg starts, without 0. best_games: the most games for this number of adds
    with any split. replan: the rung does not keep the legs of the rung above. plus_one: the game days that the
    extra add buys.
    """

    adds: int
    cuts: tuple
    legs: tuple
    games: int
    light: int
    gain: int
    zero_gain: bool
    replan: bool
    plus_one: tuple
    best_games: int


@dataclass(frozen=True)
class Week:
    """The facts of one week. games, light and no_games have one item for each day, Monday first.

    scale_max: the top of the skyline scale in games, the busiest night or the light-night limit. dead_span:
    (first, last exclusive) of the longest dead run, or None. heavy_teams: the teams of a heavy-team week.
    """

    start: object
    days: tuple
    games: tuple
    light: tuple
    no_games: tuple
    light_max: int
    scale_max: int
    rungs: tuple
    anchors: tuple
    dead_span: tuple
    heavy_teams: tuple
    week_type: str


def _runs(flags):
    """(first, last exclusive) of each run of True in flags."""
    out, i = [], 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j < len(flags) and flags[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def _pairs(days):
    """The back-to-back pairs of a sorted list of game days."""
    return tuple((a, b) for a, b in zip(days, days[1:]) if (b - a).days == 1)


class _Ladder:
    """The exact search for one stream spot that is open each day. A split is a tuple of boundaries (0, ..., 7)."""

    def __init__(self, days, plays, light, cfg):
        self.days, self.plays, self.light = days, plays, light
        self.extra = cfg["quality_games"].get("light_night_weight", 1.0) - 1  # the extra score of a light-night game
        self.scarce = cfg["skyline"]["scarce_teams"]
        self._legs = {}

    def leg(self, a, b):
        if (a, b) not in self._legs:
            self._legs[a, b] = self._leg(a, b)
        return self._legs[a, b]

    def _leg(self, a, b):
        window = self.days[a:b]
        pat = {t: tuple(d for d in window if d in ds) for t, ds in self.plays.items()}
        counts = {t: (len(p), sum(self.light[d] for d in p)) for t, p in pat.items()}
        score = {t: (g + self.extra * lt, lt) for t, (g, lt) in counts.items()}
        top_score = max(score.values(), default=(0, 0))
        tied = sorted(t for t, s in score.items() if s == top_score) if top_score[0] else []
        games, light = counts[tied[0]] if tied else (0, 0)
        groups = {}
        for t in tied:
            groups.setdefault(pat[t], []).append(t)
        # The dots follow the largest group of teams with the same game days. On a tie, the earliest days win.
        top = max(groups, key=lambda p: (len(groups[p]), [-self.days.index(d) for d in p]), default=())
        teams = tuple(groups.get(top, [])) + tuple(t for t in tied if t not in groups.get(top, []))
        b2b = {t: _pairs(pat[t]) for t in teams}
        scarce = 0 < len(teams) <= self.scarce
        # A scarce leg depends on a back-to-back when each of its teams needs one, and 5 or fewer teams in the league
        # have one in the leg. In a leg of 2 days, 2 games are always a back-to-back, so the poster does not name it.
        have = sum(bool(_pairs(p)) for p in pat.values())
        decisive = scarce and b - a >= 3 and all(b2b[t] for t in teams) and have <= self.scarce
        return Leg(
            a, b, games, light, teams, top, scarce, b2b, _pairs(top) if decisive else (), tuple(groups.get(top, []))
        )

    def legs(self, split):
        return [self.leg(a, b) for a, b in zip(split, split[1:])]

    def score(self, split):
        """((score, light-night games), tiebreak). score: the games, with the extra score of the light-night games.
        The tiebreak: fewer legs with no games, then wider legs."""
        legs = self.legs(split)
        widths = [x.team_count for x in legs if x.games] or [0]
        light = sum(x.light for x in legs)
        total = (sum(x.games for x in legs) + self.extra * light, light)
        return total, (-sum(not x.games for x in legs), min(widths), sum(widths))

    def best(self, n, prev=None):
        """The best split with n legs. On a tie, the split that keeps the most boundaries of prev."""
        cands = [(0, *c, DAYS) for c in combinations(range(1, DAYS), n - 1)]
        top = max(self.score(s)[0] for s in cands)
        ties = [s for s in cands if self.score(s)[0] == top]
        keep = (lambda s: len(set(s) & set(prev))) if prev else (lambda s: 0)
        return max(ties, key=lambda s: (keep(s), self.score(s)[1]))

    def nested(self, prev):
        """The best split that keeps the boundaries of prev and splits one leg."""
        cands = [tuple(sorted((*prev, c))) for a, b in zip(prev, prev[1:]) for c in range(a + 1, b)]
        return max(cands, key=self.score)

    def splits(self, max_adds):
        """[(split, replan)] for 1 to max_adds adds, with the rung rule "nested when free"."""
        seq = [((0, DAYS), False)]
        for n in range(2, max_adds + 1):
            prev = seq[-1][0]
            cand, best = self.nested(prev), self.best(n, prev)
            if self.score(cand)[0] >= self.score(best)[0]:
                seq.append((cand, False))
            else:
                seq.append((best, True))
        return seq


def _covered(legs):
    return {d for x in legs if x.games for d in x.pattern}


def _rungs(ladder, light, max_adds):
    out = []
    for n, (split, replan) in enumerate(ladder.splits(max_adds), start=1):
        legs = tuple(ladder.legs(split))
        games, lt = sum(x.games for x in legs), sum(x.light for x in legs)
        gain, plus_one = 0, ()
        if out:
            gain = games - out[-1].games
            if gain > 0:
                # One bought day for each gained game: light nights first, then the earliest days.
                new = sorted(_covered(legs) - _covered(out[-1].legs), key=lambda d: (not light[d], d))
                plus_one = tuple(sorted(new[:gain]))
        best = sum(x.games for x in ladder.legs(ladder.best(n)))
        out.append(Rung(n, split[1:-1], legs, games, lt, gain, bool(out) and gain <= 0, replan, plus_one, best))
    return tuple(out)


def week_facts(sched, start, cfg=None):
    """The Week that starts on Monday start. sched: data/schedule.csv, one row for each team in each game.

    A day with no rows has 0 games, so a week with missing days gives a result. cfg: load_config() when None.
    """
    cfg = cfg or load_config()
    sk = cfg["skyline"]
    light_max = cfg["quality_games"]["max_games_per_day"]
    days = tuple(start + timedelta(i) for i in range(DAYS))
    dates = pd.to_datetime(sched["date"]).dt.date
    week = sched[dates.isin(days)].assign(day=dates)
    # The one count: NBA games per night. Each game has one row for each team.
    games = tuple(int((week.day == d).sum()) // 2 for d in days)
    count = dict(zip(days, games))
    light = {d: 0 < count[d] <= light_max for d in days}
    plays = {t: set(week.day[week.team == t]) for t in sorted(sched.team.unique())}

    ladder = _Ladder(days, plays, light, cfg)
    rungs = _rungs(ladder, light, sk["max_adds"])

    # Anchor nights: light nights with few games that the scarce legs of the ladder use. At most 2.
    use = {}
    for rung in rungs:
        for leg in rung.legs:
            if leg.scarce:
                for d in leg.pattern:
                    use[d] = use.get(d, 0) + 1
    cands = [d for d in days if light[d] and count[d] <= sk["anchor_max_games"] and use.get(d)]
    anchors = tuple(sorted(sorted(cands, key=lambda d: (-use[d], count[d], d))[:2]))

    # Dead runs: 2 or more no-game days in a row, else 3 or more days in a row with light_max games or fewer.
    zero = _runs([g == 0 for g in games])
    low = _runs([g <= light_max for g in games])
    dead = [r for r in zero if r[1] - r[0] >= 2] or [r for r in low if r[1] - r[0] >= 3]
    dead_span = max(dead, key=lambda r: r[1] - r[0]) if dead else None

    # Heavy teams: a few teams play the most games, and the 1-add leg has only those teams.
    most = max((len(p) for p in plays.values()), default=0)
    top = tuple(t for t, p in plays.items() if most and len(p) == most)
    heavy = top if len(top) <= sk["heavy_max_teams"] and set(rungs[0].legs[0].teams) <= set(top) else ()

    kind = DEAD_DAY if dead_span else ANCHOR if anchors else HEAVY_TEAM if heavy else STREAM
    if kind != HEAVY_TEAM:
        heavy = ()
    return Week(
        start,
        days,
        games,
        tuple(light[d] for d in days),
        tuple(g == 0 for g in games),
        light_max,
        max(*games, light_max),
        rungs,
        anchors,
        dead_span,
        heavy,
        kind,
    )
