"""Open starting slots: the slots that your roster cannot fill on each day of the planning window.

Status rules (docs/adds/README.md):
- An Out player (Out, Out for Season, Not Active or suspended) does not play.
- A player on IL cannot start and takes no roster spot. So his spot is a stream spot.
- Each other player plays every game of his NBA team.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from fantasyhoops.core.lineup import starting_slots

UTIL = "Util"


@dataclass(frozen=True)
class Day:
    """One day of the planning window.

    starters: (slot, Player) for each player who starts, in slot order.
    bench: the players with a game who do not start, because the slots that they can fill are full.
    open: the starting slots that no player fills, in slot order.
    """
    date: date
    nba_games: int
    starters: tuple
    bench: tuple
    open: tuple


def planning_window(week, today):
    """The days from today to the last day of the fantasy week. No days if the week is over."""
    first = max(today, week.start)
    return [first + timedelta(days=i) for i in range((week.end - first).days + 1)]


def plans_next_week(week, today):
    """True on the last day of the fantasy week (or later). The planner then plans the whole next week.

    The adds of the next week are the full weekly limit, because the count resets at the start of each week.
    """
    return today >= week.end


def team_games(sched, days):
    """{day: set of the NBA teams (ESPN codes) that play that day} from data/schedule.csv."""
    dates = pd.to_datetime(sched.date).dt.date
    return {d: set(sched.team[dates == d]) for d in days}


def next_week_games(sched, week, days=7):
    """{NBA team (ESPN code): its games in the days after the last day of week} from data/schedule.csv.

    days: the length of next week. The planner does not read the dates of next week from Yahoo, so it uses 7.
    """
    dates = pd.to_datetime(sched.date).dt.date
    after = (dates > week.end) & (dates <= week.end + timedelta(days=days))
    return sched.team[after].value_counts().to_dict()


def roster_spots_used(roster):
    """The players who take a roster spot: all players who are not on IL."""
    return sum(not p.on_il for p in roster)


def open_slots_by_day(roster, games, slots):
    """A Day for each day in games ({day: set of teams}, see team_games()).

    roster: Players in order of preference, best first. The order chooses who starts when two players want the
    same slot. It does not change the open slots. slots: the position slots, cfg["league"]["slots"].
    """
    order = [*slots, UTIL]
    out = []
    for day, teams in sorted(games.items()):
        playing = [p for p in roster if p.team in teams and not p.out and not p.on_il]
        filled = starting_slots([set(p.positions) for p in playing], slots)
        starters = sorted(((slot, playing[i]) for i, slot in filled.items()), key=lambda s: order.index(s[0]))
        out.append(Day(
            date=day,
            nba_games=len(teams) // 2,
            starters=tuple(starters),
            bench=tuple(p for i, p in enumerate(playing) if i not in filled),
            open=tuple(s for s in order if s not in filled.values()),
        ))
    return out
