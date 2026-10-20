"""Weekly adds planner: python -m fantasyhoops.adds.plan. The design is in docs/adds/README.md.

One planning run:
1. read_league(): open Edge with the saved Yahoo session and read your team page and the matchup page.
   On the last day of a fantasy week, it reads the next week and plans that whole week with all its adds.
2. open_slots_by_day(): find the open starting slots on each day of the planning window.
3. rank_teams(): rank the NBA teams by the open days that they cover.
4. read_team_free_agents(): read the free agents of the best teams, all pages of the list filtered by team.
5. read_week_trends(): read Transaction Trends for each day of this week up to today.
6. schedule_plan(): choose the team windows for the stream spots.
7. Print the open slots, the stream spots, the team ranking, the schedule plan with the drops and the warnings.
8. contingency_plans(): print a contingency plan for each game day of each flagged player.
9. Write the plan page in output/adds/ (adds/page.py) and publish the site at /adds/. --no-publish: no publish.
Settings: [adds] and [league] in config.toml. NBA schedule: data/schedule.csv (fetch/espn.py).
"""
import argparse
from dataclasses import dataclass, replace
from datetime import date

from fantasyhoops.adds import page
from fantasyhoops.adds.contingency import contingency_lines, contingency_plans, game_times, print_contingencies
from fantasyhoops.adds.drops import (choose_stream_spots, drop_trade_offs, kept_roster, print_stream_spots,
                                     season_values, value_warnings)
from fantasyhoops.adds.planner import Option, rank_teams, schedule_plan, teams_to_read
from fantasyhoops.adds.readers import Adds, has_next_page, read_adds, read_free_agents, read_roster, read_week
from fantasyhoops.adds.session import open_league
from fantasyhoops.adds.slots import (open_slots_by_day, planning_window, plans_next_week, roster_spots_used,
                                     team_games)
from fantasyhoops.adds.teams import yahoo_id
from fantasyhoops.adds.trends import read_week_trends, trend_days
from fantasyhoops.adds.value import line_value, projection_scale
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import ROOT, load_config
from fantasyhoops.core.schedule import read_schedule

RANKING_ROWS = 12  # the teams that the ranking prints
MAX_PAGES = 10  # pages of 25 free agents for each team. The planner stops after this number.
URL = site.URL + "adds/"


@dataclass(frozen=True)
class LeagueData:
    """What one planning run reads from Yahoo: your roster (a list of Player), your Adds and the Week to plan.

    next_week: True if today is the last day of the current week, so that the run plans the next week.
    """
    roster: list
    adds: object
    week: object
    next_week: bool = False


def read_league(yahoo, cfg, today):
    """Read your team page and the matchup page of the week to plan from Yahoo.

    On the last day of a week, the week to plan is the next week, and all the adds of the weekly limit are left.
    """
    team = cfg["adds"]["team"]
    team_page = yahoo.get(str(team))
    week, adds = read_week(yahoo.get(f"matchup?mid1={team}")), read_adds(team_page)
    next_week = plans_next_week(week, today)
    if next_week:
        week = read_week(yahoo.get(f"matchup?week={week.number + 1}&mid1={team}"))
        adds = Adds(used=0, limit=adds.limit)
    return LeagueData(roster=read_roster(team_page), adds=adds, week=week, next_week=next_week)


def free_agent_path(team, offset=0):
    """The path of one page of the free-agent list of one NBA team (ESPN code), with Yahoo's 7-day projection."""
    return (f"players?status=FA&pos=P&cut_type=33&myteam=0&sort=OR&sdir=1&stat1=S_PS7"
            f"&eteam=ET_{yahoo_id(team)}&count={offset}")


def read_team_free_agents(yahoo, teams):
    """The FreeAgents of the NBA teams (ESPN codes), from all pages of the free-agent list of each team."""
    out = []
    for team in teams:
        for page in range(MAX_PAGES):
            html = yahoo.get(free_agent_path(team, 25 * page))
            out += read_free_agents(html)
            if not has_next_page(html):
                break
    return out


def stream_spots(roster, cfg, values=None):
    """The stream spots: the empty spots, then the lowest non-core players up to [adds] stream_spots.

    values: from drops.season_values(). If None, the function reads the projections file. See drops.py.
    """
    return choose_stream_spots(roster, cfg, season_values(cfg) if values is None else values)


def value_options(free_agents, cfg):
    """An Option for each FreeAgent, with the projected value of his per-game line."""
    scale = projection_scale(cfg)
    return [Option(f.player, line_value(f.line, scale, cfg)) for f in free_agents]


def with_trends(options, trends):
    """The options, each with his Trend from trends ({player name: Trend}). None if he is not in trends."""
    return [replace(o, trend=trends.get(o.player.name)) for o in options]


def _day(d):
    return f"{d:%a %m/%d}"


def _days(dates):
    return ", ".join(_day(d) for d in dates) or "none"


def _count(n, word):
    """For example "1 add" and "2 adds"."""
    return f"{n} {word}" + ("" if n == 1 else "s")


def _player(p):
    status = f" {p.status}" if p.status else ""
    return f"{p.name}{status}"


def _trend(trend):
    """For example "adds today 228, this week 1500". A dash if the player is not on Transaction Trends."""
    return f"adds today {trend.adds_today}, this week {trend.adds_week}" if trend else "adds -"


def print_open_slots(data, days, cfg):
    """Print the header and the table: each day, your players with a game, their slots and the open slots."""
    week, adds, roster = data.week, data.adds, data.roster
    il = sum(p.on_il for p in roster)
    if data.next_week:
        print(f"Today is the last day of week {week.number - 1}. The planner plans the next week.")
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


def print_ranking(ranking, read):
    """Print the NBA teams by the open days that they cover. A * marks the teams whose free agents the run read."""
    print()
    if not ranking:
        print("NBA teams by open days covered: none, because there are no open days.")
        return
    print("NBA teams by open days covered" + (" (* = free agents read):" if read else ":"))
    for r in ranking[:RANKING_ROWS]:
        mark = "*" if r.team in read else " "
        print(f"  {mark} {r.team:<4}  {_count(len(r.open_days), 'open day') + ',':<12} "
              f"{_count(r.open_slots, 'open slot'):<13} ({_days(r.open_days)})")
    if len(ranking) > RANKING_ROWS:
        print(f"  ... {len(ranking) - RANKING_ROWS} more teams play on an open day.")


def print_plan(plan, spots, adds, today, drops=(), warnings=()):
    """Print the schedule plan: each team window with its add day, its started games and its options.

    drops: the Drops of drops.drop_trade_offs(). Each one prints below its window. warnings: lines to print last.
    """
    print()
    if not spots:
        print("Schedule plan: no stream spots. All roster spots hold a player, and [adds] stream_spots is 0. "
              "There are no adds to plan.")
        return
    if not adds.left:
        print(f"Schedule plan: no adds left this week ({adds.used} of {adds.limit} used). There are no adds to plan.")
        return
    if plan is None:
        print(f"Schedule plan: {len(spots)} stream spots, but no open day. There are no adds to plan.")
        return
    print(f"Schedule plan: {_count(plan.started_games, 'started game')} with {_count(plan.adds, 'add')} "
          f"({_count(len(spots), 'stream spot')}, {_count(adds.left, 'add')} left).")
    if not plan.windows:
        print("  No free agent of the teams read gives a started game.")
    for w in plan.windows:
        if w.add_day:
            print(f"  Spot {w.spot + 1}: {w.team} {_day(w.add_day)} to {_day(w.last_day)}, "
                  f"latest add day {_day(w.add_day)}. Started games: {len(w.started)} ({_days(w.started)}).")
        else:
            print(f"  Spot {w.spot + 1}: {w.player.player.name} ({w.team}) holds the spot to {_day(w.last_day)}. "
                  f"Started games: {len(w.started)} ({_days(w.started)}).")
        for d in drops:
            if d.window == w:
                print(f"      {d.text()}")
        width = max(len(_player(o.player)) for o in w.options) if w.options else 0
        for n, o in enumerate(w.options, 1):
            p = o.player
            print(f"      {n}. {_player(p):<{width}}  {','.join(p.positions):<9}  "
                  f"projected value {o.projected_value:+.2f}  {_trend(o.trend)}")
    if any(w.add_day == today for w in plan.windows):
        print("  Note: an add for today helps only if his game has not started. The schedule has no game times.")
    if plan.windows:
        print("  The add day is the latest day that keeps all the started games of the window. "
              "You can wait until then for injury news.")
        print("  Adds: the adds across all Yahoo leagues, from Transaction Trends. Each day shows the 50 most added "
              "players. A dash: not on the pages of this week.")
    if drops:
        print("  A drop is a suggestion. The plan score counts only the started games of this week. "
              "The rank and the season value show the season cost.")
    for line in warnings:
        print(f"  {line}")


def publish_page(path, plan, publish=True):
    """Print the path and the main numbers of the plan page, then publish the site with the page at /adds/."""
    print()
    print(f"Wrote the plan page: {path}")
    if plan is not None:
        print(f"Plan page: {_count(plan.started_games, 'started game')} with {_count(plan.adds, 'add')}.")
    if not publish:
        print("The run did not publish the page (--no-publish).")
        return
    site.publish(ROOT, "adds", path)
    print(f"Published the plan page to {URL}. GitHub can take a few minutes to show the new page.")


def main(today=None, publish=True):
    cfg = load_config()
    today = today or date.today()
    slots, sched = cfg["league"]["slots"], read_schedule()
    plan, read, options, drops, warnings = None, [], [], [], []
    values = season_values(cfg)
    with open_league(cfg["adds"]["league"]) as yahoo:
        data = read_league(yahoo, cfg, today)
        window = planning_window(data.week, today)
        games = team_games(sched, window)
        spots = stream_spots(data.roster, cfg, values)
        days = open_slots_by_day(kept_roster(data.roster, spots), games, slots)
        ranking = rank_teams(days, games)
        if spots and data.adds.left and ranking:
            read = teams_to_read(ranking)
            free_agents = read_team_free_agents(yahoo, read)
            trends = read_week_trends(yahoo, trend_days(data.week, today, data.next_week))
    if read:
        options = with_trends(value_options(free_agents, cfg), trends)
        plan = schedule_plan(days, games, spots, options, data.adds.left, slots)
        drops = drop_trade_offs(plan, data.roster, spots, games, options, data.adds.left, slots, values)
        warnings = value_warnings(plan, data.roster, spots, cfg, values)
    print_open_slots(data, days, cfg)
    print_stream_spots(spots, values)
    print_ranking(ranking, read)
    print_plan(plan, spots, data.adds, today, drops, warnings)
    contingencies = contingency_plans(days, games, plan, len(spots), options, data.adds.left, slots, game_times(sched))
    print_contingencies(contingencies)
    text = page.render(data, days, spots, plan, ranking, read, today, drops=drops, warnings=warnings,
                       contingencies=[" ".join(line.strip() for line in contingency_lines(c)) for c in contingencies])
    publish_page(page.write(text), plan, publish)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plan the adds of the current fantasy week.")
    parser.add_argument("--no-publish", action="store_true", help="Write the plan page, but do not publish it.")
    main(publish=not parser.parse_args().no_publish)
