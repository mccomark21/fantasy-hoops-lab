"""The shared types and the team ranking of the adds planner.

- Option: a free agent (or a holder) with his values. waiver_options() gives the options on waivers.
- StreamSpot: a roster spot that a plan can fill.
- rank_teams() ranks the NBA teams by the open days that they cover. teams_to_read() gives the teams whose free agents
  the run reads.
- counted_games(): the started games of a player on the rest list (adds/rest.py) count less on a second night.
The team plan (adds/team_plan.py, #140) uses these. The module writes no files.
"""

from dataclasses import dataclass

from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.trends import Trend

TEAMS_TO_READ = 8  # the teams with the most open days. The planner reads the free agents of these teams.
DIGITS = 6  # the plan score rounds the started games to this number of decimals, so that equal sums tie


def counted_games(rests, days):
    """The started games that one game on each of days counts in total: 1 for each game, or the count of a rest day.

    rests: ((day, count), ...), for example Option.rest_games. A day here can be a date or an open-day index.
    """
    counts = dict(rests)
    return sum(counts.get(d, 1.0) for d in days)


@dataclass(frozen=True)
class Option:
    """A free agent, or the holder of a stream spot, with his values.

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
        """The value that puts the options in order: the blended value."""
        return self.projected_value if self.blended_value is None else self.blended_value

    @property
    def match(self):
        """The matchup value. The blended value if the run did not compute a matchup value."""
        return self.value if self.matchup_value is None else self.matchup_value


def waiver_options(options):
    """The options on waivers (W) who have a value, best value first. The page lists these."""
    return sorted((o for o in options if o.player.on_waivers and o.value is not None), key=lambda o: -o.value)


@dataclass(frozen=True)
class StreamSpot:
    """A roster spot that the team plan can fill with a new player.

    holder: the Option of the player who holds the spot now and who can be dropped, or None for an empty spot.
    A holder plays in the spot until the plan adds a player to it. The add drops him.
    """

    holder: Option | None = None


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
    ranks = [
        TeamRank(
            team=t,
            open_days=tuple(d.date for d in open_days if t in games[d.date]),
            open_slots=sum(len(d.open) for d in open_days if t in games[d.date]),
        )
        for t in teams
    ]
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
