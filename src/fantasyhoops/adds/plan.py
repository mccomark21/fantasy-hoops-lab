"""Weekly adds planner: python -m fantasyhoops.adds.plan. The design is in docs/adds/README.md.

One planning run:
1. read_league(): open Edge with the saved Yahoo session and read your team page and the matchup page.
   On the last day of a fantasy week, it reads the next week and plans that whole week with all its adds.
   The matchup page also gives the category scores of the current matchup (adds/matchup.py).
2. open_slots_by_day(): find the open starting slots on each day of the planning window.
3. rank_teams(): rank the NBA teams by the open days that they cover.
4. read_team_free_agents(): read the free agents of the best teams, all pages of the list filtered by team.
   read_market_free_agents(): read the first MARKET_PAGES pages of the full free-agent list (the free-agent market).
   read_waiver_list(): read the players on waivers (W), each with his clear day.
   It reads two views of each list: the projection for the next 7 days and the averages of the last 14 days.
5. read_week_trends(): read Transaction Trends for each day of this week up to today.
6. schedule_plan(): choose the team windows for the stream spots. matchup_plan(): the same search with the
   aggressive score and the matchup values (matchup_weights()). spot_plans(): the best plans for one roster spot,
   the rows of the plan page.
7. Print the open slots, the stream spots, the team ranking, the schedule plan with the drops and the warnings,
   the aggressive plan, the comparison of the two plans and the plans for one roster spot.
8. contingency_plans(): print a contingency plan for each game day of each flagged player.
9. Write the plan page in output/adds/ (adds/page.py) and publish the site at /adds/. --no-publish: no publish.
Settings: [adds] and [league] in config.toml. NBA schedule: data/schedule.csv (fetch/espn.py).
"""
import argparse
from dataclasses import dataclass, replace
from datetime import date, timedelta

from fantasyhoops.adds import page
from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.contingency import contingency_lines, contingency_plans, game_times, print_contingencies
from fantasyhoops.adds.drops import (choose_stream_spots, drop_trade_offs, kept_roster, print_stream_spots,
                                     season_values, value_warnings)
from fantasyhoops.adds.matchup import (matchup_lines, matchup_plan, matchup_score, matchup_spots,
                                       matchup_weights, read_matchup, weighted_cfg)
from fantasyhoops.adds.planner import (rank_teams, schedule_plan, teams_to_read, value_above_empty,
                                       waiver_options)
from fantasyhoops.adds.readers import (Adds, has_next_page, read_adds, read_free_agents, read_roster,
                                       read_waiver_players, read_week)
from fantasyhoops.adds.session import open_league
from fantasyhoops.adds.spots import spot_plans
from fantasyhoops.adds.slots import (open_slots_by_day, planning_window, plans_next_week, roster_spots_used,
                                     team_games)
from fantasyhoops.adds.teams import yahoo_id
from fantasyhoops.adds.trends import read_week_trends, trend_days
from fantasyhoops.adds.value import empty_slot_value, market_value, projection_scale, replacement_value
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import ROOT, load_config
from fantasyhoops.core.schedule import read_schedule

RANKING_ROWS = 12  # the teams that the ranking prints
MAX_PAGES = 10  # pages of 25 free agents for each team. The planner stops after this number.
MARKET_PAGES = 6  # pages of 25 free agents of the full list: the top 150 by Yahoo's rank
URL = site.URL + "adds/"
PROJECTED, RECENT = "S_PS7", "S_AL14"  # the views of the free-agent list: next 7 days (totals), last 14 days (averages)


@dataclass(frozen=True)
class LeagueData:
    """What one planning run reads from Yahoo: your roster (a list of Player), your Adds and the Week to plan.

    next_week: True if today is the last day of the current week, so that the run plans the next week.
    matchup: the matchup.Matchup of the week to plan, or None if the matchup page shows no category scores.
    """
    roster: list
    adds: object
    week: object
    next_week: bool = False
    matchup: object = None


def read_league(yahoo, cfg, today):
    """Read your team page and the matchup page of the week to plan from Yahoo.

    On the last day of a week, the week to plan is the next week, and all the adds of the weekly limit are left.
    """
    team = cfg["adds"]["team"]
    team_page, matchup_page = yahoo.get(str(team)), yahoo.get(f"matchup?mid1={team}")
    week, adds = read_week(matchup_page), read_adds(team_page)
    next_week = plans_next_week(week, today)
    if next_week:
        matchup_page = yahoo.get(f"matchup?week={week.number + 1}&mid1={team}")
        week = read_week(matchup_page)
        adds = Adds(used=0, limit=adds.limit)
    return LeagueData(roster=read_roster(team_page), adds=adds, week=week, next_week=next_week,
                      matchup=read_matchup(matchup_page, team))


def free_agent_path(team, offset=0, view=PROJECTED, status="FA"):
    """The path of one page of the free-agent list of one NBA team (ESPN code), with the stats of the view.

    team None: the full list of all teams. status "W": the list of the players on waivers.
    """
    eteam = f"&eteam=ET_{yahoo_id(team)}" if team else ""
    return f"players?status={status}&pos=P&cut_type=33&myteam=0&sort=OR&sdir=1&stat1={view}{eteam}&count={offset}"


def read_team_free_agents(yahoo, teams, view=PROJECTED):
    """The FreeAgents of the NBA teams (ESPN codes), from all pages of the free-agent list of each team.

    view: PROJECTED (Yahoo's projection for the next 7 days) or RECENT (the averages of the last 14 days).
    """
    out = []
    for team in teams:
        for page in range(MAX_PAGES):
            html = yahoo.get(free_agent_path(team, 25 * page, view))
            out += read_free_agents(html, totals=view == PROJECTED)
            if not has_next_page(html):
                break
    return out


def read_market_free_agents(yahoo, view=PROJECTED):
    """The FreeAgents of the first MARKET_PAGES pages of the full free-agent list, best Yahoo rank first."""
    out = []
    for page in range(MARKET_PAGES):
        html = yahoo.get(free_agent_path(None, 25 * page, view))
        out += read_free_agents(html, totals=view == PROJECTED)
        if not has_next_page(html):
            break
    return out


def read_waiver_list(yahoo, today, view=PROJECTED):
    """The players on waivers (W) of the first MARKET_PAGES pages of the full waiver list, each with his clear day.

    The waiver list is short (4 players on 2026-10-21), so the run does not read it for each NBA team.
    """
    out = []
    for page in range(MARKET_PAGES):
        html = yahoo.get(free_agent_path(None, 25 * page, view, status="W"))
        out += read_waiver_players(html, today, totals=view == PROJECTED)
        if not has_next_page(html):
            break
    return out


def unique_free_agents(free_agents):
    """The free agents with each player one time: a player on a team page and on the market pages counts once."""
    return list({(f.player.name, f.player.team): f for f in free_agents}.values())


def stream_spots(roster, cfg, values=None):
    """The stream spots: the empty spots, then the lowest non-core players up to [adds] stream_spots.

    values: from drops.season_values(). If None, the function reads the projections file. See drops.py.
    """
    return choose_stream_spots(roster, cfg, season_values(cfg) if values is None else values)


def value_options(free_agents, cfg, recent=(), matchup_cfg=None):
    """An Option for each FreeAgent, with his projected, recent, blended and matchup values (adds/blend.py).

    recent: the FreeAgents of the recent view of the same lists. matchup_cfg: cfg with the matchup weights.
    """
    return blended_options(free_agents, recent, projection_scale(cfg), cfg, matchup_cfg)


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


def _signed(value):
    """A value with its sign, for example "+0.42". "-" for no value."""
    return "-" if value is None else f"{value:+.2f}"


def _player(p):
    status = f" {p.status}" if p.status else ""
    claim = " W (waiver claim, not sure)" if p.on_waivers else ""
    return f"{p.name}{status}{claim}"


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


def print_waivers(options, replacement):
    """Print the waiver players, best value first: the clear day, the first day that a plan can use him and Val.

    Val: the market value, the same as on the page. replacement: from value.replacement_value(). Nothing if no
    option is on waivers.
    """
    waivers = waiver_options(options)
    if not waivers:
        return
    print()
    print("Waiver players (a claim is not sure, and it uses an add):")
    for o in waivers:
        p = o.player
        print(f"  {p.name} ({p.team}) {','.join(p.positions)}  clears {_day(p.clear_day)}, "
              f"first plan day {_day(p.clear_day + timedelta(days=1))}, Val {_signed(market_value(o.value, replacement))}")


def print_plan(plan, spots, adds, today, drops=(), warnings=(), title="Schedule plan", notes=True):
    """Print a plan: each team window with its add day, its started games and its options.

    drops: the Drops of drops.drop_trade_offs(). Each one prints below its window. warnings: lines to print last.
    title: the name of the plan. notes: print the notes on the add day and the trend below the plan.
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
    print(f"{title}: {_count(plan.started_games, 'started game')} with {_count(plan.adds, 'add')} "
          f"({_count(len(spots), 'stream spot')}, {_count(adds.left, 'add')} left). "
          f"Blended value of the started games: {_signed(plan.value)}.")
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
                  f"value: projected {_signed(o.projected_value)}, recent {_signed(o.recent_value)}, "
                  f"blended {_signed(o.value)}, matchup {_signed(o.match)}  {_trend(o.trend)}")
    if not notes:
        return
    if any(w.add_day == today for w in plan.windows):
        print("  Note: an add for today helps only if his game has not started.")
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


def print_comparison(plan, aggressive, empty_value, match_empty=None):
    """Print the schedule plan and the aggressive plan side by side: adds, started games and blended value.

    The next rows are the value above an empty slot and the matchup value above an empty slot, the score of the
    aggressive plan. empty_value, match_empty: the value of an empty slot without and with the matchup weights
    (value.empty_slot_value()). match_empty None: the same as empty_value.
    """
    match_empty = empty_value if match_empty is None else match_empty
    if plan is None or aggressive is None:
        return
    rows = [("Adds", plan.adds, aggressive.adds), ("Started games", plan.started_games, aggressive.started_games),
            ("Blended value", _signed(plan.value), _signed(aggressive.value)),
            ("Value above an empty slot", _signed(value_above_empty(plan, empty_value)),
             _signed(value_above_empty(aggressive, empty_value))),
            ("Matchup value above empty", _signed(matchup_score(plan, match_empty)),
             _signed(matchup_score(aggressive, match_empty)))]
    print()
    print("Comparison:")
    print(f"  {'':<26}{'Schedule':>10}{'Aggressive':>12}")
    for label, a, b in rows:
        print(f"  {label:<26}{a:>10}{b:>12}")
    print("  Blended value: the sum of the blended values of the started games. A free agent usually has a value "
          "below 0, so more started games can give a lower sum.")
    print(f"  Value above an empty slot: an empty slot has a value of {empty_value:+.2f}.")
    print(f"  Matchup value above empty: the score of the aggressive plan, with the matchup weights. An empty slot "
          f"has a matchup value of {match_empty:+.2f}.")


def print_spot_plans(rows):
    """Print the best plans for one roster spot: the games gained, the adds and the moves of each row."""
    print()
    print("Best plans for one roster spot:" if rows else "Best plans for one roster spot: none.")
    for n, row in enumerate(rows, 1):
        drop = f", drop {row.spot.holder.player.name}" if row.spot.holder else ""
        print(f"  {n}. {row.gain:+d} started games with {_count(row.plan.adds, 'add')}{drop}")
        for w in row.added:
            print(f"      +{_player(w.player.player)} ({w.team}) {_days(w.started)}, latest add day {_day(w.add_day)}")


def publish_page(path, rows, publish=True):
    """Print the path and the best row of the plan page, then publish the site with the page at /adds/."""
    print()
    print(f"Wrote the plan page: {path}")
    if rows:
        print(f"Plan page: best plan for one roster spot: {rows[0].gain:+d} started games with "
              f"{_count(rows[0].plan.adds, 'add')}.")
    if not publish:
        print("The run did not publish the page (--no-publish).")
        return
    site.publish(ROOT, "adds", path)
    print(f"Published the plan page to {URL}. GitHub can take a few minutes to show the new page.")


def main(today=None, publish=True):
    cfg = load_config()
    today = today or date.today()
    slots, sched = cfg["league"]["slots"], read_schedule()
    plan, aggressive, empty, read, options, drops, warnings, rows = None, None, None, [], [], [], [], []
    weights, match_empty, match_replacement = None, None, None
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
            free_agents = unique_free_agents(read_team_free_agents(yahoo, read) + read_market_free_agents(yahoo)
                                             + read_waiver_list(yahoo, today))
            recent = unique_free_agents(read_team_free_agents(yahoo, read, RECENT)
                                        + read_market_free_agents(yahoo, RECENT) + read_waiver_list(yahoo, today, RECENT))
            trends = read_week_trends(yahoo, trend_days(data.week, today, data.next_week))
    if read:
        scale = projection_scale(cfg)
        weights = matchup_weights(data.matchup, cfg, len(window) / len(data.week.days))
        mcfg = weighted_cfg(cfg, weights)
        options = with_trends(value_options(free_agents, cfg, recent, mcfg), trends)
        spots = matchup_spots(spots, scale, mcfg)
        plan = schedule_plan(days, games, spots, options, data.adds.left, slots)
        drops = drop_trade_offs(plan, data.roster, spots, games, options, data.adds.left, slots, values)
        warnings = value_warnings(plan, data.roster, spots, cfg, values)
        empty, match_empty = empty_slot_value(cfg, scale), empty_slot_value(mcfg, scale)
        aggressive = matchup_plan(days, games, spots, options, data.adds.left, slots, match_empty)
        match_replacement = replacement_value([replace(o, blended_value=o.match) for o in options
                                               if not o.player.on_waivers])
        rows = spot_plans(data.roster, spots, games, options, data.adds.left, slots)
    print_open_slots(data, days, cfg)
    print_stream_spots(spots, values)
    print_ranking(ranking, read)
    replacement = replacement_value([o for o in options if not o.player.on_waivers])
    print_waivers(options, replacement)
    if weights is not None:
        print()
        for line in matchup_lines(data.matchup, weights):
            print(line)
    print_plan(plan, spots, data.adds, today, drops, warnings)
    if aggressive is not None and aggressive.windows == plan.windows:
        print()
        print("Aggressive plan: the same as the schedule plan.")
    elif aggressive is not None:
        print_plan(aggressive, spots, data.adds, today, title="Aggressive plan", notes=False)
    print_comparison(plan, aggressive, empty, match_empty)
    print_spot_plans(rows)
    contingencies = contingency_plans(days, games, plan, len(spots), options, data.adds.left, slots, game_times(sched))
    print_contingencies(contingencies)
    text = page.render(data, days, games, spots, rows, options, ranking, read, today,
                       replacement=replacement, warnings=warnings, matchup=data.matchup,
                       weights=weights, match_replacement=match_replacement,
                       contingencies=[" ".join(line.strip() for line in contingency_lines(c)) for c in contingencies])
    publish_page(page.write(text), rows, publish)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plan the adds of the current fantasy week.")
    parser.add_argument("--no-publish", action="store_true", help="Write the plan page, but do not publish it.")
    main(publish=not parser.parse_args().no_publish)
