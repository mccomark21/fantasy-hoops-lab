"""Weekly adds planner: python -m fantasyhoops.adds.plan. The design is in docs/adds/README.md.

One planning run:
1. read_league(): open Edge with the saved Yahoo session and read your team page and the matchup page.
   On the last day of a fantasy week, it reads the next week and plans that whole week with all its adds.
   The matchup page also gives the category scores of the current matchup (adds/matchup.py).
2. open_slots_by_day(): find the open starting slots on each day of the planning window.
3. rank_teams(): rank the NBA teams by the open days that they cover.
4. read_lists(): read the free-agent lists (adds/lists.py, #129): the team lists of the best teams, the full
   free-agent list (the market, with its guard, #92) and the waiver list. It reads two views of each list: the
   projection for the next 7 days and the averages of the last 14 days. The read order and the list order are in
   adds/lists.py. The function times its own sub-steps (step 12).
   The recent view does not change during a day. Its team lists and market pages come from the same-day cache in
   output/adds/cache/ if an earlier run of the day read them (adds/cache.py, #91). The waiver list and the
   projected view always come from Yahoo. --no-cache: each page comes from Yahoo and replaces the cached page.
   recent_weight_limit() gives the largest possible blend weight w from data/schedule.csv. While it is below
   [adds] recent_skip_weight, the run skips the recent view (#90). The values then use the projection only, and the
   page and the terminal say so (recent_skip_line()).
5. read_week_trends(): read Transaction Trends for each day of this week up to today. The page of a day before
   today comes from the cache if a run read it before: yesterday's page until the end of today, an older page for
   good. The page of today comes from Yahoo (#91).
   read_absences(): find the absent starters in the rotation log. mark_role_ups() marks the free agents at their
   positions (adds/role_up.py). The mark changes no value.
6. schedule_plan(): choose the team windows for the stream spots. matchup_plan(): the same search with the
   aggressive score and the matchup values (matchup_weights()). spot_plans(): the best plans for one roster spot,
   the rows of the plan page.
   Before the plans, with_rests() marks the rest games of the players on the rest list (adds/rest.py).
   Both plans get a bonus for the games next week of the last players in the stream spots (next_week_games()).
7. contingency_plans(): a contingency plan for each game day of each flagged player.
8. read_roles(): the minutes, starts and closes of each free agent from the rotation log (adds/roles.py).
   The run does not update the log. Without data/rotation_log.csv, the page has no role lines.
9. next_week_window(): find the open slots of your kept roster on the first days of next week
   ([adds] next_week_open_days). The free-agent table of the page marks each free agent who fits one (#76).
10. One PlanningRun holds the results of the steps above (#128). print_report() prints the terminal report from it:
    the open slots, the stream spots, the team ranking, the schedule plan with the drops and the warnings, the
    aggressive plan, the comparison of the two plans, the plans for one roster spot and the contingency plans.
11. page.render() makes the plan page from the same PlanningRun. The run writes the page in output/adds/ and
    publishes the site at /adds/. --no-publish: no publish.
    Before the plan page, build_home() writes the home page in output/home/ (adds/home.py, #120). The publish puts
    it at the root of the site. --no-publish also skips the home page.
    The page and the terminal show how many pages came from the cache (PageCache.line()).
12. Time each step (adds/timing.py, #85). The terminal shows each step when it starts and its time when it ends.
    The report prints after the role read, so its lines come after the step lines of steps 7 and 8.
    The page shows the Run time table. Each step appends its row to output/adds/timings.csv when it ends.
    The Yahoo reads step also times its sub-steps and counts their Yahoo pages (#89): browser start, league and
    matchup pages, projected pass, recent pass, market pages, waiver list and trends.
Settings: [adds] and [league] in config.toml. The rest list: rests_b2b of the [risk] file.
NBA schedule: data/schedule.csv (fetch/espn.py).
"""

import argparse
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from datetime import date

from fantasyhoops.adds import page, timing
from fantasyhoops.adds.cache import PageCache
from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.contingency import contingency_plans, game_times
from fantasyhoops.adds.home import build_home
from fantasyhoops.adds.lists import read_lists, recent_skip_line, recent_weight_limit, skips_recent_view
from fantasyhoops.adds.drops import choose_stream_spots, kept_roster, season_values, value_warnings
from fantasyhoops.adds.matchup import matchup_weights, read_matchup, weighted_cfg
from fantasyhoops.adds.planner import StreamSpot, rank_teams, schedule_plan, teams_to_read
from fantasyhoops.adds.roles import read_roles
from fantasyhoops.adds.readers import Adds, read_adds, read_roster, read_week
from fantasyhoops.adds.rest import DEFAULT_REST_CHANCE, games_text, read_rest_names, second_nights, with_rests
from fantasyhoops.adds.role_up import mark_role_ups, read_absences
from fantasyhoops.adds.session import WAIT_SECONDS, open_league
from fantasyhoops.adds.spots import spot_plans
from fantasyhoops.adds.slots import (
    NEXT_WEEK_OPEN_DAYS,
    next_week_games,
    next_week_window,
    open_slots_by_day,
    planning_window,
    plans_next_week,
    team_games,
)
from fantasyhoops.adds.trends import read_week_trends, trend_days
from fantasyhoops.adds.value import projection_scale, replacement_value
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import ROOT, load_config
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.schedule import read_schedule

URL = site.URL + "adds/"


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


@dataclass(frozen=True)
class PlanningRun:
    """What one planning run gives the plan page (page.render()) and the terminal summary (print_summary()).

    cfg: the settings of config.toml. today: the date of the run. data: the LeagueData. days: the Days of the
    planning window. games: {day: set of NBA teams that play}. nights: from rest.second_nights().
    spots: the StreamSpots. ranking: the TeamRanks. read: the teams whose free agents the run read. options: the
    Options of the free agents. replacement, match_replacement: the value and the matchup value of a replacement free
    agent, or None. weights: the matchup weights, or None if the run read no free agents.
    warnings: text lines (drops.value_warnings()). rows: the SpotPlans of the best plans for one roster spot.
    contingencies: the Contingency plans. roles: {(name, team): Role}, or None with no rotation log.
    next_days, next_games: the Days and the games of the first days of next week (slots.next_week_window()).
    timings: the timing.StepTimes of the run. recent_skip, market, cache: the run lines, or None.
    """

    data: object
    days: list
    games: dict
    spots: list
    today: date = None
    cfg: dict = field(default_factory=dict)
    nights: dict = None
    ranking: list = ()
    read: list = ()
    options: list = ()
    replacement: float = None
    match_replacement: float = None
    weights: dict = None
    warnings: list = ()
    rows: list = ()
    contingencies: list = ()
    roles: dict = None
    next_days: list = ()
    next_games: dict = None
    timings: tuple = ()
    recent_skip: str = None
    market: str = None
    cache: str = None


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
    return LeagueData(
        roster=read_roster(team_page),
        adds=adds,
        week=week,
        next_week=next_week,
        matchup=read_matchup(matchup_page, team),
    )


def stream_spots(roster, cfg, values=None):
    """The stream spots: the empty spots, then the lowest non-core players up to [adds] stream_spots.

    values: from drops.season_values(). If None, the function reads the projections file. See drops.py.
    """
    return choose_stream_spots(roster, cfg, season_values(cfg) if values is None else values)


def value_options(free_agents, cfg, recent=(), matchup_cfg=None, scale=None):
    """An Option for each FreeAgent, with his projected, recent, blended and matchup values (adds/blend.py).

    recent: the FreeAgents of the recent view of the same lists. matchup_cfg: cfg with the matchup weights.
    scale: from projection_scale(). If None, the function reads the projections file.
    """
    scale = projection_scale(cfg) if scale is None else scale
    return blended_options(free_agents, recent, scale, cfg, matchup_cfg)


def with_trends(options, trends):
    """The options, each with his Trend from trends ({player name: Trend}). None if he is not in trends."""
    return [replace(o, trend=trends.get(o.player.name)) for o in options]


def _count(n, word):
    """For example "1 add", "2 adds" and "1.5 started games"."""
    return f"{games_text(n)} {word}" + ("" if n == 1 else "s")


def print_summary(run):
    """Print the warnings of a PlanningRun (drops.value_warnings()), one line each. publish_page() prints the page
    path, the best plan and the URL. The page shows all other results of the run (#130)."""
    for line in run.warnings:
        print(line)


def publish_page(path, rows, cfg, publish=True, home=None):
    """Print the path and the best row of the plan page, then publish the site with the page at /adds/.

    home: the home page (adds/home.py) for the root of the site, or None. cfg: the config of the run.
    """
    print()
    print(f"Wrote the plan page: {path}")
    if rows:
        print(
            f"Plan page: best plan for one roster spot: {games_text(rows[0].gain, sign=True)} started games with "
            f"{_count(rows[0].plan.adds, 'add')}."
        )
    if not publish:
        print("The run did not publish the page (--no-publish).")
        return
    site.publish(ROOT, "adds", path, home=home, cfg=cfg)
    print(f"Published the plan page to {URL}. GitHub can take a few minutes to show the new page.")


def main(today=None, publish=True, timed=True, cache=True):
    """One planning run (see the module docstring). timed False: no step times, no timings.csv and no Run time
    table. The plans are the same. cache False (--no-cache): the run reads each page from Yahoo and writes it over
    the cached page (adds/cache.py)."""
    timings = timing.Timings(timed)
    step = timings.step
    cfg = load_config()
    today = today or date.today()
    slots = cfg["league"]["slots"]
    with step("schedule read"):
        sched = read_schedule()
    plan, read, options, warnings, rows, weights, match_replacement = None, [], [], [], [], None, None
    recent, skip_line, market_text = [], None, None
    pages = PageCache(today, use=cache)
    pages.remove_old_days()
    with step("season values"):
        values = season_values(cfg)
    # The category scale of the values. The read is outside every step, as before #92, so the rows stay comparable.
    scale = projection_scale(cfg)
    wait = cfg["adds"].get("page_wait", WAIT_SECONDS)
    part = timings.part
    with step("Yahoo reads"), ExitStack() as browser:
        with part("browser start"):
            yahoo = browser.enter_context(open_league(cfg["adds"]["league"], wait))
        with part("league and matchup pages", yahoo):
            data = read_league(yahoo, cfg, today)
        window = planning_window(data.week, today)
        games, nights = team_games(sched, window), second_nights(sched, window)
        chance = cfg["adds"].get("rest_chance", DEFAULT_REST_CHANCE)
        rests = read_rest_names(cfg) if chance else set()
        spots = [
            StreamSpot(with_rests([s.holder], rests, nights, chance)[0]) if s.holder else s
            for s in stream_spots(data.roster, cfg, values)
        ]
        kept = kept_roster(data.roster, spots)
        days = open_slots_by_day(kept, games, slots)
        timings.window(days, data.adds.left)
        early = next_week_window(data.week, cfg["adds"].get("next_week_open_days", NEXT_WEEK_OPEN_DAYS))
        early_games = team_games(sched, early)
        early_days = open_slots_by_day(kept, early_games, slots)
        ranking = rank_teams(days, games)
        if spots and data.adds.left and ranking:
            read = teams_to_read(ranking)
            most, limit = recent_weight_limit(sched, today)
            skip = skips_recent_view(limit, cfg)
            if skip:
                # No recent rows: the blend uses the projected line only (blend.py). The sub-step rows stay.
                skip_line = recent_skip_line(most, limit, cfg)

            # The read order, the market guard and the list order are in adds/lists.py (#129).
            # The recent view does not change during a day, so its team lists and market pages use the cache (#91).
            def guard_values(fas, rec):
                return value_options(fas, cfg, rec, scale=scale)

            lists = read_lists(yahoo, pages.recent(yahoo), read, today, guard_values, skip, part)
            free_agents, recent, market_text = lists.free_agents, lists.recent, lists.market_line
            with part("trends", yahoo):
                trends = read_week_trends(
                    yahoo, trend_days(data.week, today, data.next_week), lambda day: pages.trends(yahoo, day)
                )
    if read:
        weights = matchup_weights(data.matchup, cfg, len(window) / len(data.week.days))
        mcfg = weighted_cfg(cfg, weights)
        with step("absence read"):
            absences = read_absences(today, cfg)
        with step("value options"):
            options = with_rests(
                with_trends(value_options(free_agents, cfg, recent, mcfg, scale), trends), rests, nights, chance
            )
            options = mark_role_ups(options, absences)
        games_next, weight = next_week_games(sched, data.week), cfg["adds"].get("next_week_weight", 0.0)
        with step("schedule search", search=True):
            plan = schedule_plan(
                days, games, spots, options, data.adds.left, slots, next_week=games_next, next_weight=weight
            )
        warnings = value_warnings(plan, data.roster, spots, cfg, values)
        match_replacement = replacement_value(
            [replace(o, blended_value=o.match) for o in options if not o.player.on_waivers]
        )
        with step("spot plans", search=True):
            rows = spot_plans(data.roster, spots, games, options, data.adds.left, slots)
    cache_text = pages.line()
    with step("contingency plans"):
        contingencies = contingency_plans(
            days, games, plan, len(spots), options, data.adds.left, slots, game_times(sched)
        )
    with step("role read"):
        roles = read_roles([o.player for o in options], cfg, today)
    run = PlanningRun(
        cfg=cfg,
        today=today,
        data=data,
        days=days,
        games=games,
        nights=nights,
        spots=spots,
        ranking=ranking,
        read=read,
        options=options,
        replacement=replacement_value([o for o in options if not o.player.on_waivers]),
        match_replacement=match_replacement,
        weights=weights,
        warnings=warnings,
        rows=rows,
        contingencies=contingencies,
        roles=roles,
        next_days=early_days,
        next_games=early_games,
        recent_skip=skip_line,
        market=market_text,
        cache=cache_text,
    )
    home = None
    if publish:
        # Before the plan page, so that the Run time table of the plan page has this step.
        with step("home page"):
            home = build_home(data, cfg, sched, today)
    with step("page write and publish"):
        # The Run time table shows the steps that ended before the page write.
        text = page.render(replace(run, timings=tuple(timings.steps)))
        publish_page(page.write(text), rows, cfg, publish, home)
    print_summary(run)


if __name__ == "__main__":
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Plan the adds of the current fantasy week.")
    parser.add_argument("--no-publish", action="store_true", help="Write the plan page, but do not publish it.")
    parser.add_argument(
        "--no-cache", action="store_true", help="Read each page from Yahoo, and write it over the cached page."
    )
    args = parser.parse_args()
    main(publish=not args.no_publish, cache=not args.no_cache)
