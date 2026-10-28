"""The free-agent list reads of one planning run (adds/plan.py): read_lists() and its helpers. It writes no file.

read_lists() reads the free agents that a plan can add, from Yahoo and from the same-day cache (adds/cache.py):
1. read_team_free_agents(): the free agents of the read teams, all pages of the list filtered by team. First the
   projected view ("projected pass"), then the recent view ("recent pass").
2. read_market_free_agents(): the full free-agent list (the free-agent market), MARKET_PAGES pages at most, each page
   in both views ("market pages"). The guard stops the read after a page with no new player above the replacement
   value (rank 15) of the free agents read before that page (#92). market_line() says how many pages the run read
   and why it stopped.
3. read_waiver_list(): the players on waivers (W), each with his clear day, in both views ("waiver list").
The views: the projection for the next 7 days (PROJECTED) and the averages of the last 14 days (RECENT).
Each list page parses one time (readers.parse()), for the players and for the "Next 25" link (#93).
recent_weight_limit() and skips_recent_view() tell the run when to skip the recent view (#90). The run then reads
the projected view only, and recent_skip_line() says so.
unique_free_agents() keeps each player one time, in the list order: team lists, market, waivers (#92).
"""

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from fantasyhoops.adds.blend import RECENT_DAYS, recent_weight
from fantasyhoops.adds.cache import get_all
from fantasyhoops.adds.readers import has_next_page, parse, read_free_agents, read_waiver_players
from fantasyhoops.adds.teams import yahoo_id
from fantasyhoops.adds.value import REPLACEMENT_RANK

MAX_PAGES = 10  # pages of 25 free agents for each team. The planner stops after this number.
MARKET_PAGES = 3  # pages of 25 free agents of the full list at most: the top 75 by Yahoo's rank (#92)
WAIVER_PAGES = 6  # pages of 25 players of the full waiver list at most
PROJECTED, RECENT = "S_PS7", "S_AL14"  # the views of the free-agent list: next 7 days (totals), last 14 days (averages)
RECENT_SKIP_WEIGHT = 0.0  # [adds] recent_skip_weight if config.toml has none: never skip the recent view


@dataclass(frozen=True)
class FreeAgentLists:
    """The result of read_lists().

    free_agents: the FreeAgents of the projected view, each player one time. recent: the FreeAgents of the recent
    view, each player one time, or empty if the run skips the recent view. market: the MarketRead of the market
    pages. market_line: market_line() of market.
    """

    free_agents: list
    recent: list
    market: object
    market_line: str


def read_lists(yahoo, recent_yahoo, teams, today, values, skip, part):
    """Read the free-agent lists of one planning run. Give the FreeAgentLists.

    yahoo: the session.League. recent_yahoo: the reader of the pages in the recent view (cache.PageCache.recent()).
    teams: the NBA teams (ESPN codes) whose team lists the run reads. today: the date of the run.
    values: the guard's function (FreeAgents, recent FreeAgents) -> Options. skip: True if the run skips the recent
    view (skips_recent_view()). part: timing.Timings.part. Each sub-step row keeps its name, order and pages (#89).
    """
    # The team lists come first in both views, so the guard of the market read has their blended values.
    with part("projected pass", yahoo):
        team_fas = read_team_free_agents(yahoo, teams)
    # The recent view does not change during a day, so its team lists and market pages use the cache (#91).
    # The FA status and the injury flags come only from the projected view of this run (blend.py).
    with part("recent pass", yahoo):
        team_recent = [] if skip else read_team_free_agents(recent_yahoo, teams, RECENT)
    # The values of the team lists are outside the sub-steps, so the rows stay comparable with #89.
    # Only the guard's values of the new players of each page are in the "market pages" row.
    known = known_values(team_fas, team_recent, values)
    with part("market pages", yahoo):
        market = read_market_free_agents(yahoo, not skip, team_fas, team_recent, values, known, recent_yahoo)
    with part("waiver list", yahoo):
        waivers = read_waiver_list(yahoo, today)
        waivers_recent = [] if skip else read_waiver_list(yahoo, today, RECENT)
    # The list order of unique_free_agents() stays: team lists, market, waivers (#92).
    return FreeAgentLists(
        free_agents=unique_free_agents(team_fas + market.projected + waivers),
        recent=[] if skip else unique_free_agents(team_recent + market.recent + waivers_recent),
        market=market,
        market_line=market_line(market),
    )


def free_agent_path(team, offset=0, view=PROJECTED, status="FA"):
    """The path of one page of the free-agent list of one NBA team (ESPN code), with the stats of the view.

    team None: the full list of all teams. status "W": the list of the players on waivers.
    """
    eteam = f"&eteam=ET_{yahoo_id(team)}" if team else ""
    return f"players?status={status}&pos=P&cut_type=33&myteam=0&sort=OR&sdir=1&stat1={view}{eteam}&count={offset}"


def read_team_free_agents(yahoo, teams, view=PROJECTED):
    """The FreeAgents of the NBA teams (ESPN codes), from all pages of the free-agent list of each team.

    view: PROJECTED (Yahoo's projection for the next 7 days) or RECENT (the averages of the last 14 days).
    The run reads page 1 of all teams together, then the next page of each team that has one (#108). The order of
    the FreeAgents stays: team by team, page by page.
    """
    found = {team: [] for team in teams}
    open_teams = list(found)
    for page_number in range(MAX_PAGES):
        if not open_teams:
            break
        pages = get_all([(yahoo, free_agent_path(team, 25 * page_number, view)) for team in open_teams])
        more = []
        for team, html in zip(open_teams, pages):
            parsed = parse(html)
            found[team] += read_free_agents(parsed, totals=view == PROJECTED)
            if has_next_page(parsed):
                more.append(team)
        open_teams = more
    return [f for team_fas in found.values() for f in team_fas]


@dataclass(frozen=True)
class MarketRead:
    """The result of the market read: the FreeAgents of each view and why the read stopped.

    projected, recent: the FreeAgents of the market pages in each view. recent is empty without the recent view.
    pages: the market pages that the run read in each view. stop: "guard", "limit" (MARKET_PAGES) or "end" (the
    last page of the list).
    """

    projected: list
    recent: list
    pages: int
    stop: str


def _playing_values(options):
    """The values of the options who play and have a value: the players that value.replacement_value() counts."""
    return [o.value for o in options if o.value is not None and not o.player.out]


def known_values(found, found_recent, values):
    """The values of the free agents of found (each player one time) who play and have a value.

    found, found_recent, values: see read_market_free_agents(). The run computes them before the market read, so the
    "market pages" sub-step does not time this work (#92).
    """
    return _playing_values(values(unique_free_agents(list(found)), list(found_recent)))


def read_market_free_agents(yahoo, recent=True, found=(), found_recent=(), values=None, known=None, recent_yahoo=None):
    """Read the full free-agent list, MARKET_PAGES pages at most, best Yahoo rank first. Give a MarketRead.

    recent: False if the run skips the recent view (#90). The run then reads only the projected view.
    The run reads each page in both views before the guard checks it.
    found, found_recent: the FreeAgents of the team lists in each view, which the run read before the market.
    values: a function (FreeAgents, recent FreeAgents) -> Options, for example value_options(). None: no guard.
    The guard (#92): the run stops after a page with no new player above the replacement value of the free agents
    read before that page. With fewer than REPLACEMENT_RANK free agents with a value before the page, the guard does
    not stop the read. A player who is also on an earlier list is not new.
    known: known_values() of found. None: the function computes it.
    recent_yahoo: the reader of the pages in the recent view, for example cache.PageCache.recent() (#91). None: yahoo.
    """
    recent_yahoo = recent_yahoo or yahoo
    out, out_recent = [], []
    seen = {(f.player.name, f.player.team) for f in found}
    if not values:
        known = []
    elif known is None:
        known = known_values(found, found_recent, values)
    known = list(known)
    for page_number in range(MARKET_PAGES):
        # The guard decides after each page, so the run reads no market page ahead. The two views go together (#108).
        reads = [(yahoo, free_agent_path(None, 25 * page_number, PROJECTED))]
        if recent:
            reads.append((recent_yahoo, free_agent_path(None, 25 * page_number, RECENT)))
        html, *html_recent = get_all(reads)
        parsed = parse(html)
        page_fas = read_free_agents(parsed, totals=True)
        if recent:
            out_recent += read_free_agents(parse(html_recent[0]), totals=False)
        out += page_fas
        new = unique_free_agents([f for f in page_fas if (f.player.name, f.player.team) not in seen])
        seen |= {(f.player.name, f.player.team) for f in new}
        if values:
            new_values = _playing_values(values(new, list(found_recent) + out_recent))
            bar = sorted(known, reverse=True)[REPLACEMENT_RANK - 1] if len(known) >= REPLACEMENT_RANK else None
            known += new_values
            if bar is not None and not any(v > bar for v in new_values):
                return MarketRead(out, out_recent, page_number + 1, "guard")
        if not has_next_page(parsed):
            return MarketRead(out, out_recent, page_number + 1, "end")
    return MarketRead(out, out_recent, MARKET_PAGES, "limit")


def market_line(market):
    """The line of the Run time section of the page that says how many market pages the run read and why it stopped."""
    head = f"Market: {market.pages} of {MARKET_PAGES} pages"
    if market.stop == "guard":
        return (
            f"{head}. Page {market.pages} had no new player above the replacement value (the free agent at rank "
            f"{REPLACEMENT_RANK} of the players read before it)."
        )
    if market.stop == "end":
        return f"{head}. Page {market.pages} was the last page of the list."
    return f"{head} (the limit)."


def read_waiver_list(yahoo, today, view=PROJECTED):
    """The players on waivers (W) of the first WAIVER_PAGES pages of the full waiver list, each with his clear day.

    The waiver list is short (4 players on 2026-10-21), so the run does not read it for each NBA team.
    """
    out = []
    for page_number in range(WAIVER_PAGES):
        parsed = parse(yahoo.get(free_agent_path(None, 25 * page_number, view, status="W")))
        out += read_waiver_players(parsed, today, totals=view == PROJECTED)
        if not has_next_page(parsed):
            break
    return out


def recent_weight_limit(sched, today):
    """The upper limit of the blend weight w before the run reads the recent view: (most games, w at most).

    most games: the most games that one NBA team played from today - RECENT_DAYS days to today, from
    data/schedule.csv. These 15 days hold the window of the recent view with or without today (#90).
    w at most: blend.recent_weight() of the most games. A player who changed teams can have more games (#90).
    """
    dates = pd.to_datetime(sched.date).dt.date
    days = sched[(dates >= today - timedelta(days=RECENT_DAYS)) & (dates <= today)]
    most = int(days.team.value_counts().max()) if len(days) else 0
    return most, recent_weight(most)


def skips_recent_view(limit, cfg):
    """True if the run skips the recent view: the upper limit of w is below [adds] recent_skip_weight."""
    return limit < cfg["adds"].get("recent_skip_weight", RECENT_SKIP_WEIGHT)


def recent_skip_line(most, limit, cfg):
    """The line of the Run time section of the page that says that the run skipped the recent view, and why."""
    return (
        f"The run skipped the recent view (last {RECENT_DAYS} days). The most games of one team from "
        f"{RECENT_DAYS} days ago to today is {most}, so w is {limit:.2f} at most. This is below [adds] "
        f"recent_skip_weight ({cfg['adds'].get('recent_skip_weight', RECENT_SKIP_WEIGHT)}). The values use the "
        "projection only. A player with no projection is not a candidate."
    )


def unique_free_agents(free_agents):
    """The free agents with each player one time: a player on a team page and on the market pages counts once."""
    return list({(f.player.name, f.player.team): f for f in free_agents}.values())
