"""The Yahoo reads of the trade tool (#148): the rostered list in both views and the trade deadline.

read_trade_inputs() reads the pages through the same-day cache (cache.PageCache.rostered(), adds/cache.py). The
cache keeps the raw pages in output/adds/cache/rostered/<YYYY-MM-DD>/, so a fix of a reader can use the real pages.
main() is the live check: it opens Yahoo, reads the pages and prints what it found. It writes only the cache.
Run it with: python -m fantasyhoops.trade.reads (add --no-cache to read each page from Yahoo again).
"""

import argparse
from dataclasses import dataclass
from datetime import date

from fantasyhoops.adds.cache import ROSTERED, PageCache
from fantasyhoops.adds.lists import PROJECTED, RECENT, recent_weight_limit, skips_recent_view
from fantasyhoops.adds.session import WAIT_SECONDS, open_league
from fantasyhoops.core.common import load_config
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core.schedule import read_schedule
from fantasyhoops.trade.deadline import SETTINGS_PATH, TradeDeadlineNotFound, read_trade_deadline
from fantasyhoops.trade.rostered import read_rostered, teams


@dataclass(frozen=True)
class TradeInputs:
    """The result of read_trade_inputs().

    rostered: the rostered.RosteredRead. deadline: the trade deadline, or None if the reader did not find it.
    deadline_error: the message of the reader when it did not find the deadline, else None.
    """

    rostered: object
    deadline: date | None
    deadline_error: str | None


def read_trade_inputs(pages, yahoo, own_team, skip_recent, today):
    """Read the rostered list and the trade deadline. Give TradeInputs.

    pages: the cache.PageCache of the run. yahoo: the session.League. own_team: your team ID ([adds] team).
    skip_recent: see rostered.read_rostered(). today: the day of the run.
    A missing deadline does not stop the read. deadline_error then names the cache folder of the settings page.
    """
    reader = pages.rostered(yahoo)
    rostered = read_rostered(reader, own_team, skip_recent)
    try:
        deadline, error = read_trade_deadline(reader.get(SETTINGS_PATH), today), None
    except TradeDeadlineNotFound as found:
        folder = pages.folder / ROSTERED / f"{today:%Y-%m-%d}"
        deadline, error = None, f"{found} The page is in the cache folder {folder}."
    return TradeInputs(rostered, deadline, error)


def report(inputs):
    """The lines of the live check: the pages of each view, the teams, the rows with no team link and the deadline."""
    read = inputs.rostered
    lines = [f"Projected view: {read.pages[PROJECTED]} pages, {len(read.projected)} players of other teams."]
    if read.skipped_recent:
        lines.append("Recent view: skipped ([adds] recent_skip_weight).")
    else:
        lines.append(f"Recent view: {read.pages[RECENT]} pages, {len(read.recent)} players of other teams.")
    found = teams(read.projected)
    lines.append(f"Teams: {len(found)}.")
    lines += [f"  Team {tid}: {name} ({count} players)" for tid, (name, count) in found.items()]
    if read.no_link:
        lines.append(f"Rows with no team link: {len(read.no_link)} ({', '.join(read.no_link[:10])}).")
    else:
        lines.append("Rows with no team link: 0. Each row has a team link with a team ID.")
    if inputs.deadline:
        lines.append(f"Trade deadline: {inputs.deadline:%Y-%m-%d}.")
    else:
        lines.append(f"Trade deadline: not found. {inputs.deadline_error}")
    return lines


def main(today=None, cache=True):
    """The live check of the trade reads (see the module docstring)."""
    cfg = load_config()
    today = today or date.today()
    _, limit = recent_weight_limit(read_schedule(), today)
    skip = skips_recent_view(limit, cfg)
    pages = PageCache(today, use=cache)
    pages.remove_old_days()
    with open_league(cfg["adds"]["league"], cfg["adds"].get("page_wait", WAIT_SECONDS)) as yahoo:
        inputs = read_trade_inputs(pages, yahoo, cfg["adds"]["team"], skip, today)
        opened = yahoo.pages
    for line in report(inputs):
        print(line)
    print(f"Yahoo pages opened: {opened}. {pages.line() or 'No page came from the cache.'}")


if __name__ == "__main__":
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Read the rostered list and the trade deadline from Yahoo.")
    parser.add_argument(
        "--no-cache", action="store_true", help="Read each page from Yahoo, and write it over the cached page."
    )
    main(cache=not parser.parse_args().no_cache)
