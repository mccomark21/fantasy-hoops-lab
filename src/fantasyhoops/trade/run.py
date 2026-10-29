"""The trade run (#150): read Yahoo, score the 1-for-1 trades, write the trade page and publish it to /trade/ (#151).

Run it with: python -m fantasyhoops.trade (add --no-publish to only write the page, and --no-cache to read each
rostered page from Yahoo again).
The run reads your team page (readers.read_roster()) for your roster and IL slots, and the rostered list and the
league settings through the same-day cache (trade/reads.py). It scores the trades with trade/suggest.py and writes
output/trade/index.html (trade/page.py). It times its steps in output/trade/timings.csv (adds/timing.py).
The publish (publish_page()) puts the page at /trade/ on gh-pages and keeps the home page there (keep_home=True).
With --no-publish, the run does not change gh-pages.
Edge states (#153):
1. The run reads the league settings first. After the trade deadline, it does not read your team page or the
   rostered list. It writes and publishes a short page with the deadline line (page.render_deadline()).
2. With no trade deadline, the run continues. The terminal and the page show a warning.
3. A player with no match in the rankings, the [risk] file or the projections file gets a warning line.
4. When the run cannot read Yahoo, it stops with the error (YahooReadFailed) and does not publish.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.cache import ROSTERED, PageCache
from fantasyhoops.adds.drops import season_values
from fantasyhoops.adds.home import read_ranks
from fantasyhoops.adds.lists import recent_weight_limit, skips_recent_view
from fantasyhoops.adds.readers import read_roster
from fantasyhoops.adds.session import WAIT_SECONDS, PageNotReady, YahooBlocked, open_league
from fantasyhoops.adds.timing import Timings
from fantasyhoops.adds.value import projection_scale
from fantasyhoops.core import common, home
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import load_config, name_key
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.schedule import read_schedule
from fantasyhoops.draft.rankings import load_risk
from fantasyhoops.trade import page
from fantasyhoops.trade.reads import TradeInputs, read_deadline
from fantasyhoops.trade.rostered import read_rostered
from fantasyhoops.trade.suggest import TradePlayer, TradeSettings, player_value, suggest

SCHEDULE_FETCH = "python -m fantasyhoops.fetch.espn"
# The errors of a Yahoo read that stop the run: a block, a page that did not load, a sign-in that did not finish.
YAHOO_ERRORS = (YahooBlocked, PageNotReady, PlaywrightTimeout)


class YahooReadFailed(SystemExit):
    """The run could not read Yahoo. It stops and does not publish, so the last good page stays on the site."""


def yahoo_failed(error):
    """The YahooReadFailed of a Yahoo error: the error, and the line that the run did not publish."""
    return YahooReadFailed(
        f"The trade run could not read Yahoo: {type(error).__name__}: {error} "
        "The run did not publish. The last good page stays on the site."
    )


def deadline_passed(deadline, today):
    """True if today is after the trade deadline. On the deadline day, Yahoo still accepts trades."""
    return deadline is not None and today > deadline


class MissingSchedule(SystemExit):
    """data/schedule.csv does not exist. The run cannot find the playoff days."""


def timings_path():
    """The timings file of the trade run: output/trade/timings.csv, from common.OUT at the time of the call."""
    return common.OUT / "trade" / "timings.csv"


def schedule():
    """data/schedule.csv. Without the file, the run stops with a message that names the file and the fetch command."""
    path = common.DATA / "schedule.csv"
    if not path.exists():
        raise MissingSchedule(f"The trade run needs {path} for the playoff days. Make the file with: {SCHEDULE_FETCH}")
    return read_schedule()


@dataclass(frozen=True)
class LocalFiles:
    """The data of the run from local files. days: the playoff days (home.playoff_days()). ranks: {name_key: rank}.

    pre: drops.season_values(). scale: value.projection_scale(). skip_recent: True if the read skips the recent view.
    """

    days: list
    ranks: dict
    pre: dict
    scale: object
    skip_recent: bool


def read_local_files(cfg, today):
    """The LocalFiles of the run: data/schedule.csv, the custom ranks and the projections file."""
    sched = schedule()
    return LocalFiles(
        days=home.playoff_days(sched, cfg),
        ranks=read_ranks(cfg, sched),
        pre=season_values(cfg),
        scale=projection_scale(cfg),
        skip_recent=skips_recent_view(recent_weight_limit(sched, today)[1], cfg),
    )


def trade_players(roster, read, own_team, ranks, risk, pre, scale, cfg):
    """(your TradePlayers, the TradePlayers of the other teams).

    roster: your adds Players from your team page. read: the rostered.RosteredRead of all teams, yours too.
    own_team: your team ID. ranks: {name_key: rank}. risk: {name_key: rests_b2b}. pre: drops.season_values().
    scale: adds/value.projection_scale(). The value is the blended value of both views of the rostered list, else
    the preseason pg_value with the mark "pre".
    """
    blended = {}
    for o in blended_options(read.projected, read.recent, scale, cfg):
        blended[(o.player.name, o.player.team)] = o.blended_value
        blended.setdefault(name_key(o.player.name), o.blended_value)

    def make(p, slot="", team_id=None, team_name=""):
        key = name_key(p.name)
        found = blended.get((p.name, p.team), blended.get(key))
        pg = pre[key].value if key in pre else None
        value, mark = player_value(found, pg)
        return TradePlayer(
            name=p.name,
            team=p.team,
            positions=tuple(p.positions),
            slot=slot,
            status=p.status,
            value=value,
            mark=mark,
            pg=pg,
            rank=ranks.get(key),
            rests_b2b=bool(risk.get(key, 0)),
            team_id=team_id,
            team_name=team_name,
        )

    mine = [make(p, slot=p.slot, team_id=own_team) for p in roster]
    others = [make(r.player, team_id=r.team_id, team_name=r.team_name) for r in read.projected if r.team_id != own_team]
    return mine, others


def read_risk(names, cfg):
    """{name_key(name): rests_b2b} of the names in the [risk] file (draft/rankings.py).

    A name that is not in the file is not in the result. trade_players() then gives him rests_b2b 0.
    """
    series = pd.Series(list(names))
    known = set(pd.read_csv(common.ROOT / cfg["risk"]["file"]).name.map(name_key))
    risk = load_risk(series, cfg).rests_b2b
    return {name_key(n): int(r) for n, r in zip(series, risk) if name_key(n) in known}


def missing_data(players, ranks, risk, pre):
    """The warning lines of the players with no match in a data file, by common.name_key(). One line for each file.

    players: the TradePlayers of both sides. ranks: {name_key: rank}. risk: {name_key: rests_b2b} of the names in
    the [risk] file. pre: {name_key: SeasonValue} of the projections file. A name shows once in each line.
    """
    files = [
        (ranks, "these players have no rank and go last in the lineup order"),
        (risk, "these players are not in the [risk] file and get rests_b2b 0"),
        (pre, "these players are not in the projections file and have no Pre value"),
    ]
    out = []
    for found, text in files:
        names = list(dict.fromkeys(p.name for p in players if name_key(p.name) not in found))
        if names:
            out.append(f"Warning: {text}: {', '.join(names)}.")
    return out


def rostered_line(hits, total, read_time, now):
    """The read time of the rostered pages on the page, for example
    "Rosters: 16 pages from the cache of 2026-10-28 09:14."

    hits: the pages from the cache. total: the pages of the read. read_time: the earliest read time of a cached page.
    now: the time of the run, the read time of the pages from Yahoo.
    """
    fresh = total - hits
    if hits and not fresh:
        return f"Rosters: {_pages(total)} from the cache of {read_time:%Y-%m-%d %H:%M}."
    if not hits:
        return f"Rosters: {_pages(total)} read from Yahoo at {now:%Y-%m-%d %H:%M}."
    return (
        f"Rosters: {_pages(hits)} from the cache of {read_time:%Y-%m-%d %H:%M}, "
        f"{_pages(fresh)} read from Yahoo at {now:%Y-%m-%d %H:%M}."
    )


def _pages(n):
    return f"{n} page" + ("" if n == 1 else "s")


def best_line(result):
    """The terminal line of the best suggestion, or "No trade raises your playoff starts."."""
    if not result.rows:
        return page.EMPTY
    s = result.rows[0]
    return (
        f"Best: give {s.give.name}, get {s.get.name} ({s.get.team_name}): "
        f"{sum(s.before)} -> {sum(s.after)} playoff starts (+{s.gain}), value {s.dv:+.2f}."
    )


def warnings(mine, inputs, missing=()):
    """The warning lines of the run: the trade deadline, rows with no team link, your players with no value and the
    lines of missing_data()."""
    out = []
    if inputs.deadline is None:
        out.append(f"Warning: no trade deadline. {inputs.deadline_error}")
    if inputs.rostered.no_link:
        out.append(f"Warning: {len(inputs.rostered.no_link)} rows of the rostered list have no team link.")
    none = [p.name for p in mine if p.value is None]
    if none:
        out.append(f"Warning: these players of your team have no value and are not in a trade: {', '.join(none)}.")
    return out + list(missing)


def publish_page(path, cfg, publish=True):
    """Publish the trade page to /trade/ and print the URL. The home page of gh-pages stays (keep_home=True).

    publish False (--no-publish): print that the run did not publish.
    """
    if not publish:
        print("Publish: skipped (--no-publish).")
        return
    site.publish(common.ROOT, page.CURRENT, path, cfg=cfg, keep_home=True)
    print(f"Published the trade page to {site.URL}{page.CURRENT}/. GitHub can take a few minutes to show the new page.")


def main(argv=None):
    """The trade run (see the module docstring)."""
    parser = argparse.ArgumentParser(description="Suggest 1-for-1 trades and write the trade page.")
    parser.add_argument("--no-publish", action="store_true", help="Write the page and do not publish it.")
    parser.add_argument("--no-cache", action="store_true", help="Read each rostered page from Yahoo again.")
    args = parser.parse_args(argv)
    cfg = load_config()
    made = datetime.now().replace(microsecond=0)
    today = made.date()
    settings = TradeSettings.from_config(cfg)
    weeks = common.weeks(cfg)
    own = cfg["adds"]["team"]
    timings = Timings(path=timings_path())
    timings.window([], "")  # the trade run has no planning window, so the window columns stay empty
    with timings.step("Local files"):
        local = read_local_files(cfg, today)
    pages = PageCache(today, use=not args.no_cache)
    pages.remove_old_days()
    roster = None
    try:
        with timings.step("Yahoo reads"):
            with open_league(cfg["adds"]["league"], cfg["adds"].get("page_wait", WAIT_SECONDS)) as yahoo:
                reader = pages.rostered(yahoo)
                with timings.part("settings", yahoo):
                    deadline, error = read_deadline(pages, reader, today)
                if not deadline_passed(deadline, today):
                    with timings.part("team page", yahoo):
                        roster = read_roster(yahoo.get(str(own)))
                    with timings.part("rostered list", yahoo):
                        # own_team None: the read keeps the rows of your team too, for the blended values.
                        rostered = read_rostered(reader, None, local.skip_recent)
    except YAHOO_ERRORS as failed:
        raise yahoo_failed(failed) from failed
    if roster is None:
        with timings.step("Page"):
            path = page.write(page.render_deadline(cfg, made, deadline))
        print(f"Wrote the trade page: {path}")
        print(page.deadline_line(deadline))
        publish_page(path, cfg, publish=not args.no_publish)
        print(f"Timings: {timings_path()}")
        return
    inputs = TradeInputs(rostered, deadline, error)
    with timings.step("Score"):
        names = [p.name for p in roster] + [r.player.name for r in inputs.rostered.projected]
        risk = read_risk(names, cfg)
        mine, others = trade_players(roster, inputs.rostered, own, local.ranks, risk, local.pre, local.scale, cfg)
        result = suggest(mine, others, local.days, cfg["league"]["slots"], weeks, settings)
    lines = warnings(mine, inputs, missing_data(mine + others, local.ranks, risk, local.pre))
    with timings.step("Page"):
        total = sum(inputs.rostered.pages.values()) + 1  # the rostered pages of each view and the settings page
        line = rostered_line(pages.hits[ROSTERED], total, pages.rostered_time, made)
        builder = page.builder_data(result, mine, others, local.days, cfg["league"]["slots"], weeks, settings)
        html = page.render(result, weeks, cfg, made, today, inputs.deadline, line, builder, lines)
        path = page.write(html)
    print(f"Wrote the trade page: {path}")
    print(f"Suggestions: {len(result.rows)}. {best_line(result)}")
    publish_page(path, cfg, publish=not args.no_publish)
    for w in lines:
        print(w)
    print(f"Timings: {timings_path()}")


if __name__ == "__main__":
    use_utf8_output()
    main()
