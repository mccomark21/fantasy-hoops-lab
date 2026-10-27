import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from fantasyhoops.adds import cache as page_cache
from fantasyhoops.adds.cache import DAY, KEPT, RECENT, TRENDS, PageCache
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
    assert first.recent(yahoo).get("players?a") == "<p>players?a</p>"
    second = PageCache(MON, folder=tmp_path, clock=clock(11, 0))
    assert second.recent(yahoo).get("players?a") == "<p>players?a</p>"
    assert yahoo.paths == ["players?a"]  # the second run asks Yahoo for no page
    assert second.hits == {RECENT: 1, TRENDS: 0}
    assert second.line() == "The recent view: 1 page from the cache of 2027-01-04 09:14."
    next_day = PageCache(MON + timedelta(days=1), folder=tmp_path)
    next_day.recent(yahoo).get("players?a")
    assert yahoo.paths == ["players?a"] * 2
    assert next_day.line() is None


def test_the_run_deletes_only_the_day_entries_of_earlier_days(tmp_path):
    for day in (MON, MON + timedelta(days=1), MON + timedelta(days=2)):
        PageCache(day, folder=tmp_path).recent(Pages()).get("players?a")
    PageCache(MON, folder=tmp_path).trends(Pages(), MON - timedelta(days=5)).get("buzzindex?b")
    (tmp_path / DAY / "notes").mkdir()
    PageCache(MON + timedelta(days=1), folder=tmp_path).remove_old_days()
    # The earlier day goes. Today, a later day and a folder whose name is not a date stay.
    assert sorted(d.name for d in (tmp_path / DAY).iterdir()) == ["2027-01-05", "2027-01-06", "notes"]
    assert len(list((tmp_path / KEPT).iterdir())) == 1  # a kept entry stays


def test_no_cache_reads_from_yahoo_and_replaces_the_entry(tmp_path):
    yahoo = Pages()
    PageCache(MON, folder=tmp_path, clock=clock(9, 0)).recent(yahoo).get("players?a")
    bypass = PageCache(MON, use=False, folder=tmp_path, clock=clock(10, 30))
    bypass.recent(yahoo).get("players?a")
    assert yahoo.paths == ["players?a"] * 2
    assert bypass.line() is None
    later = PageCache(MON, folder=tmp_path)
    later.recent(yahoo).get("players?a")
    assert later.line() == "The recent view: 1 page from the cache of 2027-01-04 10:30."


def test_the_page_count_counts_only_the_pages_from_yahoo(tmp_path):
    yahoo = Pages()
    PageCache(MON, folder=tmp_path).recent(yahoo).get("players?a")
    PageCache(MON, folder=tmp_path).recent(yahoo).get("players?a")
    assert yahoo.pages == 1


def test_trends_today_from_yahoo_yesterday_for_the_day_older_for_good(tmp_path):
    days = [MON + timedelta(days=n) for n in range(4)]  # Mon to Thu
    html = {trends_path(d): page([("Phi One", n + 1, 0)]) for n, d in enumerate(days)}
    yahoo = Pages(lambda path: html[path])

    def run(today):
        yahoo.paths = []
        cache = PageCache(today, folder=tmp_path)
        cache.remove_old_days()
        week = [d for d in days if d <= today]
        trends = read_week_trends(yahoo, week, lambda day: cache.trends(yahoo, day))
        return cache, trends

    # Tuesday: Tue (today) and Mon (yesterday) from Yahoo.
    run(days[1])
    assert yahoo.paths == [trends_path(days[1]), trends_path(days[0])]
    # Wednesday: Mon (2 days before) is not a kept entry yet, so it comes from Yahoo. Tue is yesterday.
    run(days[2])
    assert yahoo.paths == [trends_path(days[2]), trends_path(days[1]), trends_path(days[0])]
    # A second run on Wednesday: Tue and Mon from the cache. Today always comes from Yahoo.
    cache, trends = run(days[2])
    assert yahoo.paths == [trends_path(days[2])]
    assert cache.line() == "Transaction Trends: 2 pages of earlier days from the cache."
    assert trends["Phi One"].adds_week == 1 + 2 + 3
    # Thursday: Mon is kept for good. The day entry of Tue is gone, and Wed is yesterday.
    run(days[3])
    assert yahoo.paths == [trends_path(days[3]), trends_path(days[2]), trends_path(days[1])]


def _entry_file(tmp_path):
    return next(f for f in (tmp_path / DAY / "2027-01-04").iterdir() if f.suffix == ".json")


@pytest.mark.parametrize("bad", [
    "not json",
    "[1, 2]",
    '{"path": "players?z", "read_at": "2027-01-04T09:00:00", "html": "<p>x</p>"}',
    '{"path": "players?a", "read_at": "not a time", "html": "<p>x</p>"}',
    '{"path": "players?a", "html": "<p>x</p>"}',
    '{"path": "players?a", "read_at": "2027-01-04T09:00:00", "html": 3}',
    '{"path": "players?a", "read_at": 5, "html": "<p>x</p>"}',
])
def test_a_bad_entry_is_a_miss(tmp_path, bad):
    yahoo = Pages()
    PageCache(MON, folder=tmp_path).recent(yahoo).get("players?a")
    _entry_file(tmp_path).write_text(bad, encoding="utf-8")
    later = PageCache(MON, folder=tmp_path)
    assert later.recent(yahoo).get("players?a") == "<p>players?a</p>"
    assert yahoo.paths == ["players?a"] * 2
    assert later.hits == {RECENT: 0, TRENDS: 0} and later.line() is None
    assert json.loads(_entry_file(tmp_path).read_text(encoding="utf-8"))["path"] == "players?a"  # written again


def test_a_failed_write_warns_and_the_run_continues(tmp_path, monkeypatch, capsys):
    def fail(*args):
        raise PermissionError("the file is in use")

    monkeypatch.setattr(page_cache.os, "replace", fail)
    cache, yahoo = PageCache(MON, folder=tmp_path), Pages()
    assert cache.recent(yahoo).get("players?a") == "<p>players?a</p>"
    assert "Warning: the run did not write the page in the cache" in capsys.readouterr().out
    assert not list((tmp_path / DAY / "2027-01-04").iterdir())  # no temporary file stays


def test_each_write_uses_a_unique_temporary_file(tmp_path, monkeypatch):
    parts = []
    real = page_cache.os.replace
    monkeypatch.setattr(page_cache.os, "replace", lambda src, dst: (parts.append(src), real(src, dst)))
    cache = PageCache(MON, folder=tmp_path)
    cache.save(DAY, "players?a", "<p>1</p>")
    cache.save(DAY, "players?a", "<p>2</p>")
    assert len(set(parts)) == 2
    assert PageCache(MON, folder=tmp_path).recent(Pages()).get("players?a") == "<p>2</p>"


def test_the_guide_says_to_use_no_cache_after_the_games_end():
    text = (Path(__file__).parents[2] / "docs" / "adds" / "README.md").read_text(encoding="utf-8")
    assert "does not show the games of that night. After the games end, run the planner with `--no-cache`." in text
