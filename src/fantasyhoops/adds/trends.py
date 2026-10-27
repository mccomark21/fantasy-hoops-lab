"""The trend of each free agent: his adds across all Yahoo leagues, from Transaction Trends (/nba/<league>/buzzindex).

The page shows one day (date=). It has no view for a week, so "this week" is the sum of the pages of the days of
the week up to today. Each page shows 50 players only. A player who is not on the page of a day counts 0 adds
that day. The trend is evidence and the last tiebreak of the options. It never changes the plan score.
"""

from dataclasses import dataclass
from datetime import timedelta

from bs4 import BeautifulSoup

from fantasyhoops.adds.readers import read_player


@dataclass(frozen=True)
class Trend:
    """The adds and drops of one player across all Yahoo leagues: today and in the days of this week up to today."""

    adds_today: int
    adds_week: int
    drops_today: int = 0
    drops_week: int = 0


def trends_path(day):
    """The path of Transaction Trends for one day: the available players with the most adds first."""
    return f"buzzindex?date={day:%Y-%m-%d}&pos=ALL&src=combined&bimtab=A&trendtab=O&sort=BI_A&sdir=1"


def trend_days(week, today, next_week=False):
    """The days of this week up to today. On the last day of a week (next_week), week is the next week, so the
    days are today and the 6 days before it."""
    if next_week:
        return [today - timedelta(days=n) for n in range(6, -1, -1)]
    return [d for d in week.days if d <= today] or [today]


def _count(text):
    return int(text.replace(",", "")) if text.replace(",", "").isdigit() else 0


def _column(header, name):
    """The index of the first column whose header starts with name. The sorted column also has a sort icon."""
    return next(i for i, text in enumerate(header) if text.split()[:1] == [name])


def read_trends(html):
    """{player name: (adds, drops)} from one page of Transaction Trends."""
    table = BeautifulSoup(html, "html.parser").select_one("table.Tst-table")
    if table is None:
        raise ValueError("The Transaction Trends page has no player table (table.Tst-table).")
    header = [th.get_text(" ", strip=True) for th in table.select("thead tr")[-1].find_all("th")]
    adds, drops = _column(header, "Adds"), _column(header, "Drops")
    out = {}
    for row in table.select("tbody tr"):
        block = row.select_one(".ysf-player-name")
        if block is None or block.select_one("a.name") is None:
            continue
        cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
        out[read_player(block).name] = (_count(cells[adds]), _count(cells[drops]))
    return out


def week_trends(pages):
    """{player name: Trend} from the pages of Transaction Trends of this week. pages: the HTML of each day,
    TODAY FIRST. A player who is on no page has no Trend."""
    days = [read_trends(html) for html in pages]
    out = {}
    for name in set().union(*days):
        today = days[0].get(name, (0, 0))
        out[name] = Trend(
            adds_today=today[0],
            adds_week=sum(d.get(name, (0, 0))[0] for d in days),
            drops_today=today[1],
            drops_week=sum(d.get(name, (0, 0))[1] for d in days),
        )
    return out


def read_week_trends(yahoo, days, old=None):
    """{player name: Trend} from Yahoo: one page of Transaction Trends for each day, today (the last day) first.

    old: a function day -> the reader of the page of a day before today, for example cache.PageCache.trends()
    (#91). None: yahoo. The page of today always comes from yahoo, because it changes during the day.
    """
    days = sorted(days, reverse=True)
    return week_trends([(yahoo if n == 0 or old is None else old(d)).get(trends_path(d)) for n, d in enumerate(days)])
