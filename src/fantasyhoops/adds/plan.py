"""Weekly adds planner: python -m fantasyhoops.adds.plan. The design is in docs/adds/README.md.

One planning run:
1. read_league(): open Edge with the saved Yahoo session and read your team page and the matchup page.
2. open_slots_by_day(): find the open starting slots on each day of the planning window.
3. print_open_slots(): print a table of the days.
The schedule plan and the other later steps come after step 2.
Settings: [adds] and [league] slots in config.toml. NBA schedule: data/schedule.csv (fetch/espn.py).
"""
from dataclasses import dataclass
from datetime import date

from fantasyhoops.adds.readers import read_adds, read_roster, read_week
from fantasyhoops.adds.session import open_league
from fantasyhoops.adds.slots import open_slots_by_day, planning_window, roster_spots_used, team_games
from fantasyhoops.core.common import load_config
from fantasyhoops.core.schedule import read_schedule


@dataclass(frozen=True)
class LeagueData:
    """What one planning run reads from Yahoo: your roster (a list of Player), your Adds and the current Week."""
    roster: list
    adds: object
    week: object


def read_league(cfg):
    """Read your team page and the matchup page of the current week from Yahoo."""
    league, team = cfg["adds"]["league"], cfg["adds"]["team"]
    with open_league(league) as yahoo:
        team_page = yahoo.get(str(team))
        matchup_page = yahoo.get(f"matchup?mid1={team}")
    return LeagueData(roster=read_roster(team_page), adds=read_adds(team_page), week=read_week(matchup_page))


def _day(d):
    return f"{d:%a %m/%d}"


def _player(p):
    status = f" {p.status}" if p.status else ""
    return f"{p.name}{status}"


def print_open_slots(data, days, cfg):
    """Print the header and the table: each day, your players with a game, their slots and the open slots."""
    week, adds, roster = data.week, data.adds, data.roster
    il = sum(p.on_il for p in roster)
    print(f"Yahoo league {cfg['adds']['league']}, team {cfg['adds']['team']}. "
          f"Week {week.number}: {_day(week.start)} to {_day(week.end)}.")
    print(f"Adds: {adds.used} of {adds.limit} used, {adds.left} left. "
          f"Roster spots: {roster_spots_used(roster)} of {cfg['league']['roster_spots']} used (IL: {il}).")
    out = [_player(p) for p in roster if p.out]
    print(f"Out (does not play): {', '.join(out) or 'none'}")
    if not days:
        print("The fantasy week is over. There are no days to plan.")
        return
    print(f"Planning window: {_day(days[0].date)} to {_day(days[-1].date)} ({len(days)} days).")

    width = max([len(_player(p)) for p in roster] + [10])
    for day in days:
        print()
        print(f"{_day(day.date)}  {day.nba_games} NBA games  open slots: {len(day.open)}"
              + (f" ({', '.join(day.open)})" if day.open else ""))
        for slot, p in day.starters:
            print(f"  {slot:<5} {_player(p):<{width}}  {p.team:<4}  {','.join(p.positions)}")
        for p in day.bench:
            print(f"  {'BN':<5} {_player(p):<{width}}  {p.team:<4}  {','.join(p.positions):<8}  (his slots are full)")
    total = sum(len(d.open) for d in days)
    print()
    print(f"Open slots in the planning window: {total}, on {sum(bool(d.open) for d in days)} of {len(days)} days.")


def main(today=None):
    cfg = load_config()
    data = read_league(cfg)
    window = planning_window(data.week, today or date.today())
    days = open_slots_by_day(data.roster, team_games(read_schedule(), window), cfg["league"]["slots"])
    print_open_slots(data, days, cfg)


if __name__ == "__main__":
    main()
