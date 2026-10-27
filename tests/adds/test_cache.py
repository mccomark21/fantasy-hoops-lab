from datetime import date, datetime, timedelta

from fantasyhoops.adds.cache import DAY, KEPT, PageCache
from fantasyhoops.adds.trends import read_week_trends, trends_path

MON = date(2027, 1, 4)


def page(rows):
    """A Transaction Trends page with rows of (name, adds, drops), as in test_trends.py."""
    body = "".join(
        f'<tr><td></td><td><div class="ysf-player-name"><a class="name" title="{n}">{n}</a>'
        f'<span class="D-b"><span class="Fz-xxs">PHI - C</span></span></div></td><td></td><td>FA</td>'
        f'<td>1%</td><td>1%</td><td>{a}</td><td>{d}</td><td>0</td><td>{a + d}</td><td></td></tr>'
        for n, a, d in rows)
    return ('<table class="Tst-table"><thead><tr><th></th><th>Player</th><th></th><th>Roster Status</th>'
            '<th>% Ros</th><th>% Start</th><th>Adds</th><th>Drops</th><th>Trades</th><th>Total</th><th></th>'
            f'</tr></thead><tbody>{body}</tbody></table>')


class Pages:
    """A fake session.League: get() counts the pages and gives the HTML of html(path)."""

    def __init__(self, html=lambda path: f"<p>{path}</p>"):
        self.pages, self.paths, self.html = 0, [], html

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        return self.html(path)


def clock(hour, minute):
    return lambda: datetime(2027, 1, 4, hour, minute)


def test_a_day_entry_is_good_until_the_end_of_the_day(tmp_path):
    first, yahoo = PageCache(MON, folder=tmp_path, clock=clock(9, 14)), Pages()
    assert first.day(yahoo).get("players?a") == "<p>players?a</p>"
    second = PageCache(MON, folder=tmp_path, clock=clock(11, 0))
    assert second.day(yahoo).get("players?a") == "<p>players?a</p>"
    assert yahoo.paths == ["players?a"]  # the second run asks Yahoo for no page
    assert second.hits == {DAY: 1, KEPT: 0}
    assert second.line() == "The recent view: 1 page from the cache of 2027-01-04 09:14."
    next_day = PageCache(MON + timedelta(days=1), folder=tmp_path)
    next_day.day(yahoo).get("players?a")
    assert yahoo.paths == ["players?a"] * 2
    assert next_day.line() is None


def test_the_run_deletes_the_day_entries_of_earlier_days(tmp_path):
    PageCache(MON, folder=tmp_path).day(Pages()).get("players?a")
    PageCache(MON, folder=tmp_path).kept(Pages()).get("buzzindex?b")
    tuesday = PageCache(MON + timedelta(days=1), folder=tmp_path)
    tuesday.remove_old_days()
    assert not (tmp_path / DAY / "2027-01-04").exists()
    assert len(list((tmp_path / KEPT).iterdir())) == 1  # a kept entry stays


def test_no_cache_reads_from_yahoo_and_replaces_the_entry(tmp_path):
    yahoo = Pages()
    PageCache(MON, folder=tmp_path, clock=clock(9, 0)).day(yahoo).get("players?a")
    bypass = PageCache(MON, use=False, folder=tmp_path, clock=clock(10, 30))
    bypass.day(yahoo).get("players?a")
    assert yahoo.paths == ["players?a"] * 2
    assert bypass.line() is None
    later = PageCache(MON, folder=tmp_path)
    later.day(yahoo).get("players?a")
    assert later.line() == "The recent view: 1 page from the cache of 2027-01-04 10:30."


def test_the_page_count_counts_only_the_pages_from_yahoo(tmp_path):
    yahoo = Pages()
    PageCache(MON, folder=tmp_path).day(yahoo).get("players?a")
    PageCache(MON, folder=tmp_path).day(yahoo).get("players?a")
    assert yahoo.pages == 1


def test_old_trends_pages_come_from_the_cache_and_the_page_of_today_from_yahoo(tmp_path):
    days = [MON, MON + timedelta(days=1), MON + timedelta(days=2)]
    html = {trends_path(d): page([("Phi One", n + 1, 0)]) for n, d in enumerate(days)}
    yahoo = Pages(lambda path: html[path])
    # Tuesday: Mon from Yahoo (then kept), Tue (today) from Yahoo.
    tuesday = PageCache(days[1], folder=tmp_path)
    read_week_trends(yahoo, days[:2], tuesday.kept(yahoo))
    assert yahoo.paths == [trends_path(days[1]), trends_path(days[0])]
    # Wednesday: Mon from the cache, Tue from Yahoo (then kept), Wed (today) from Yahoo.
    yahoo.paths = []
    wednesday = PageCache(days[2], folder=tmp_path)
    trends = read_week_trends(yahoo, days, wednesday.kept(yahoo))
    assert yahoo.paths == [trends_path(days[2]), trends_path(days[1])]
    assert wednesday.line() == "Transaction Trends: 1 page of earlier days from the cache."
    assert trends["Phi One"].adds_week == 1 + 2 + 3
    # A second run on Wednesday: Mon and Tue from the cache. Today always comes from Yahoo.
    yahoo.paths = []
    read_week_trends(yahoo, days, PageCache(days[2], folder=tmp_path).kept(yahoo))
    assert yahoo.paths == [trends_path(days[2])]


def test_a_cache_file_of_another_path_is_not_used(tmp_path):
    cache, yahoo = PageCache(MON, folder=tmp_path), Pages()
    cache.day(yahoo).get("players?a")
    file = next((tmp_path / DAY / "2027-01-04").iterdir())
    file.write_text(file.read_text(encoding="utf-8").replace("players?a", "players?z"), encoding="utf-8")
    PageCache(MON, folder=tmp_path).day(yahoo).get("players?a")
    assert yahoo.paths == ["players?a"] * 2
