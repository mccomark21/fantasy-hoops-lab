"""Tests of League.get() with a fake page and a fake fetch. The tests open no browser and use no network."""

from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fantasyhoops.adds.readers import has_next_page, parse, read_free_agents, read_waiver_players

from fantasyhoops.adds.session import (
    MAX_REQUESTS,
    SCORE_WAIT_SECONDS,
    SITE,
    League,
    PageNotReady,
    UnknownPage,
    YahooBlocked,
    has_element,
    raw_fetcher,
    raw_kind,
    ready_selectors,
)
from fantasyhoops.adds.trends import read_trends

TEAM = "table#statTable0 tbody tr[data-pos]"
PLAYERS = "div.players table tbody tr"
DAYS = "a.Navtarget[href]"
SCORES = "table.Datatable tbody tr"
TRENDS = "table.Tst-table tbody tr"
OVERVIEW = '[data-tst="fantasy-team-overview-name"]'


class FakeResponse:
    """The part of a Playwright response that League uses."""

    def __init__(self, status):
        self.status = status


class FakePage:
    """The part of a Playwright page that League uses.

    missing: selectors that never appear. statuses: the HTTP status of each visit in sequence, then 200.
    """

    def __init__(self, missing=(), statuses=()):
        self.url = ""
        self.missing = set(missing)
        self.statuses = list(statuses)
        self.visits = []
        self.waits = []

    def goto(self, url, wait_until, timeout):
        self.url = url
        self.visits.append(url)
        return FakeResponse(self.statuses.pop(0) if self.statuses else 200)

    def wait_for_selector(self, selector, state, timeout):
        self.waits.append((selector, state, timeout))
        if selector in self.missing:
            raise PlaywrightTimeout(f"Timeout {timeout}ms exceeded.")

    def content(self):
        return "<html>page</html>"


@pytest.mark.parametrize(
    "path, required, optional",
    [
        ("10", (TEAM,), (OVERVIEW,)),
        ("matchup?mid1=10", (DAYS,), (SCORES,)),
        ("matchup?week=2&mid1=10", (DAYS,), (SCORES,)),
        ("players?status=FA&pos=P&count=25", (PLAYERS,), ()),
        ("players?status=W&pos=P&count=0", (PLAYERS,), ()),
        ("players?status=T&pos=P&stat1=S_PS7&count=0", (PLAYERS,), ()),
        ("settings", (), ("table tbody tr",)),
        ("buzzindex?date=2026-10-21&pos=ALL&src=combined&bimtab=A&trendtab=O&sort=BI_A&sdir=1", (TRENDS,), ()),
    ],
)
def test_ready_selectors_name_the_elements_that_the_reader_needs(path, required, optional):
    assert ready_selectors(path) == (required, optional)


@pytest.mark.parametrize("path", ["", "transactions", "standings"])
def test_ready_selectors_of_a_page_with_no_known_kind_raise_an_error_that_names_the_path(path):
    with pytest.raises(UnknownPage) as error:
        ready_selectors(path)
    assert repr(path) in str(error.value)


def test_get_waits_for_the_element_of_the_page_and_not_for_networkidle():
    page = FakePage()  # the fake has no wait_for_load_state, so a networkidle wait fails the test
    html = League(page, 22820, wait_seconds=7).get("players?status=FA&count=0")
    assert html == "<html>page</html>"
    assert page.waits == [(PLAYERS, "attached", 7000)]


def test_get_of_the_matchup_page_waits_for_the_day_links_and_the_score_rows():
    page = FakePage()
    League(page, 22820, wait_seconds=7).get("matchup?mid1=10")
    assert page.waits == [(DAYS, "attached", 7000), (SCORES, "attached", 500)]


def test_get_of_a_matchup_page_with_no_score_table_gives_the_page():
    # The next-week page on the last day of a week and the page before the first games have no score table.
    page = FakePage(missing={SCORES})
    assert League(page, 22820).get("matchup?week=2&mid1=10") == "<html>page</html>"


def test_a_matchup_page_with_no_score_table_waits_less_than_the_old_2_s_for_it():
    # #93: the wait was 2 s. In the live check of 2026-10-21, the score table appeared 0.1 s or less after the day links.
    page = FakePage(missing={SCORES})
    League(page, 22820).get("matchup?week=2&mid1=10")
    score_waits = [timeout for selector, _, timeout in page.waits if selector == SCORES]
    assert score_waits == [SCORE_WAIT_SECONDS * 1000] == [500]


def test_get_of_a_matchup_page_with_no_day_links_raises_an_error():
    page = FakePage(missing={DAYS})
    with pytest.raises(PageNotReady):
        League(page, 22820).get("matchup?mid1=10")


def test_get_of_a_page_with_no_known_kind_raises_an_error_that_names_the_url_and_opens_no_page():
    page = FakePage()
    with pytest.raises(UnknownPage) as error:
        League(page, 22820).get("transactions")
    assert f"{SITE}/nba/22820/transactions" in str(error.value)
    assert page.visits == []


def test_get_names_the_page_and_the_element_when_the_element_does_not_appear():
    page = FakePage(missing={TEAM})
    with pytest.raises(PageNotReady) as error:
        League(page, 22820, wait_seconds=5).get("10")
    message = str(error.value)
    assert f"{SITE}/nba/22820/10" in message
    assert TEAM in message
    assert "5 s" in message


class SignInPage(FakePage):
    """A page whose first visit goes to the Yahoo sign-in, as when the session has expired."""

    def goto(self, url, wait_until, timeout):
        response = super().goto(url, wait_until, timeout)
        if len(self.visits) == 1:
            self.url = "https://login.yahoo.com/"
        return response

    def wait_for_url(self, url, timeout):
        pass


def test_get_counts_each_page_that_it_opens():
    league = League(FakePage(), 22820)
    assert league.pages == 0
    league.get("10")
    league.get("players?status=FA&pos=P&count=0")
    assert league.pages == 2


def test_a_page_after_a_sign_in_counts_one_time(capsys):
    page = SignInPage()
    league = League(page, 22820)
    league.get("10")
    assert len(page.visits) == 2  # the sign-in opens the page again
    assert league.pages == 1


def test_a_path_with_no_known_page_kind_counts_no_page():
    league = League(FakePage(), 22820)
    with pytest.raises(UnknownPage):
        league.get("transactions")
    assert league.pages == 0


@pytest.mark.parametrize("status", [999, 429])
def test_get_of_a_blocked_page_raises_yahoo_blocked_with_no_wait_for_an_element(status):
    page = FakePage(statuses=[status])
    with pytest.raises(YahooBlocked) as error:
        League(page, 22820).get("players?status=FA&count=0")
    assert not isinstance(error.value, PageNotReady)
    assert page.waits == []
    assert len(page.visits) == 1


@pytest.mark.parametrize("status", [999, 429])
def test_the_block_message_gives_the_status_and_the_url_and_says_that_yahoo_blocked_the_requests(status):
    with pytest.raises(YahooBlocked) as error:
        League(FakePage(statuses=[status]), 22820).get("10")
    message = str(error.value)
    assert f"HTTP {status}" in message
    assert f"{SITE}/nba/22820/10" in message
    assert "Yahoo blocked the requests" in message
    assert "run stopped" in message


def test_get_of_a_page_with_status_200_gives_the_page():
    page = FakePage(statuses=[200])
    assert League(page, 22820).get("10") == "<html>page</html>"
    assert page.waits == [(TEAM, "attached", 10000), (OVERVIEW, "attached", 500)]


def test_a_team_page_with_no_overview_gives_the_page():
    # The overview wait is optional (#142): the read continues, and the page gives no record.
    page = FakePage(missing={OVERVIEW})
    assert League(page, 22820).get("10") == "<html>page</html>"
    assert page.waits == [(TEAM, "attached", 10000), (OVERVIEW, "attached", 500)]


def test_get_of_a_page_with_no_response_gives_the_page():
    # page.goto() gives None when the page loads no new document, for example a change of the URL hash only.
    class NoResponsePage(FakePage):
        def goto(self, url, wait_until, timeout):
            super().goto(url, wait_until, timeout)

    assert League(NoResponsePage(), 22820).get("10") == "<html>page</html>"


def test_a_sign_in_gives_the_page_as_before():
    page = SignInPage()
    assert League(page, 22820).get("10") == "<html>page</html>"
    assert page.waits == [(TEAM, "attached", 10000), (OVERVIEW, "attached", 500)]


def test_a_block_after_the_sign_in_raises_yahoo_blocked_with_no_wait_for_an_element(capsys):
    page = SignInPage(statuses=[200, 999])
    with pytest.raises(YahooBlocked) as error:
        League(page, 22820).get("10")
    assert "HTTP 999" in str(error.value)
    assert len(page.visits) == 2
    assert page.waits == []


# Raw requests (#108). The fake fetch gives (status, final URL, HTML) for each URL and opens no network.

PLAYERS_HTML = '<div class="players"><table><tbody><tr><td>row</td></tr></tbody></table></div>'
RAW_HTML = {
    "players": PLAYERS_HTML,
    "buzzindex": '<table class="Tst-table"><tbody><tr></tr></tbody></table>',
}


class FakeFetch:
    """A fetch for League: each call is one batch of raw requests.

    statuses: {path end: status}. redirects: the number of reads that go to the Yahoo sign-in first.
    """

    def __init__(self, statuses=None, redirects=0, html=None):
        self.batches, self.statuses, self.redirects, self.html = [], statuses or {}, redirects, html

    def __call__(self, urls):
        self.batches.append(list(urls))
        out = []
        for url in urls:
            path = url.split("/nba/22820/", 1)[1]
            status = next((s for end, s in self.statuses.items() if path.endswith(end)), 200)
            if self.redirects:
                self.redirects -= 1
                out.append((200, "https://login.yahoo.com/?done=x", "<html>sign in</html>"))
                continue
            kind = next(k for k in RAW_HTML if path.startswith(k))
            out.append((status, url, self.html if self.html is not None else RAW_HTML[kind] + path))
        return out


RAW_PATHS = [
    "players?status=FA&pos=P&count=0",
    "players?status=W&pos=P&count=0",
    "buzzindex?date=2026-10-21&pos=ALL&src=combined&bimtab=A&trendtab=O&sort=BI_A&sdir=1",
]


@pytest.mark.parametrize("path", RAW_PATHS)
def test_with_fetch_the_list_and_trends_pages_come_from_raw_requests_and_open_no_edge_page(path):
    page, fetch = FakePage(), FakeFetch()
    league = League(page, 22820, fetch=fetch)
    assert league.get(path).endswith(path)
    assert fetch.batches == [[f"{SITE}/nba/22820/{path}"]]
    assert page.visits == [] and page.waits == []
    assert league.pages == 1


@pytest.mark.parametrize("path, waits", [("10", [TEAM, OVERVIEW]), ("matchup?mid1=10", [DAYS, SCORES])])
def test_with_fetch_the_team_page_and_the_matchup_pages_come_from_edge(path, waits):
    # In the live check of 2026-10-27 20:10, the raw matchup page had no score table during NBA games (#108).
    page, fetch = FakePage(), FakeFetch()
    league = League(page, 22820, fetch=fetch)
    assert league.get(path) == "<html>page</html>"
    assert fetch.batches == []
    assert page.visits == [f"{SITE}/nba/22820/{path}"]
    assert [selector for selector, _, _ in page.waits] == waits


def test_get_many_reads_at_most_4_raw_pages_at_a_time_and_gives_the_pages_in_order():
    fetch = FakeFetch()
    league = League(FakePage(), 22820, fetch=fetch)
    paths = [f"players?status=FA&count={25 * n}" for n in range(9)]
    pages = league.get_many(paths)
    assert [len(batch) for batch in fetch.batches] == [4, 4, 1]
    assert MAX_REQUESTS == 4
    assert [p.split("</div>")[1] for p in pages] == paths
    assert league.pages == 9


def test_get_many_reads_the_team_page_in_edge_and_the_other_pages_raw():
    page, fetch = FakePage(), FakeFetch()
    league = League(page, 22820, fetch=fetch)
    path = "players?status=FA&count=0"
    pages = league.get_many(["10", path])
    assert pages[0] == "<html>page</html>"
    assert pages[1].endswith(path)
    assert page.visits == [f"{SITE}/nba/22820/10"]
    assert fetch.batches == [[f"{SITE}/nba/22820/{path}"]]
    assert league.pages == 2


@pytest.mark.parametrize("status", [999, 429])
def test_a_raw_page_with_a_block_status_raises_yahoo_blocked_and_reads_no_more_pages(status):
    page, fetch = FakePage(), FakeFetch(statuses={"count=25": status})
    league = League(page, 22820, fetch=fetch)
    paths = [f"players?status=FA&count={25 * n}" for n in range(6)]
    with pytest.raises(YahooBlocked) as error:
        league.get_many(paths)
    message = str(error.value)
    assert f"HTTP {status}" in message
    assert f"{SITE}/nba/22820/players?status=FA&count=25" in message
    assert "Yahoo blocked the requests" in message
    assert len(fetch.batches) == 1  # the second batch does not start
    assert page.visits == []


def test_a_raw_page_that_goes_to_the_sign_in_uses_edge_for_the_sign_in_and_reads_the_page_again(capsys):
    page, fetch = SignInPage(), FakeFetch(redirects=1)
    league = League(page, 22820, fetch=fetch)
    path = "players?status=FA&count=0"
    assert league.get(path).endswith(path)
    url = f"{SITE}/nba/22820/{path}"
    assert page.visits == [url]  # Edge opens the page, goes to the sign-in and waits for it
    assert fetch.batches == [[url], [url]]
    assert league.pages == 1
    assert "Sign in to Yahoo" in capsys.readouterr().out


def test_a_block_after_the_sign_in_of_a_raw_page_raises_yahoo_blocked(capsys):
    class BlockAfter(FakeFetch):
        def __call__(self, urls):
            if self.batches:
                self.batches.append(list(urls))
                return [(999, urls[0], "Request denied")]
            return super().__call__(urls)

    with pytest.raises(YahooBlocked):
        League(SignInPage(), 22820, fetch=BlockAfter(redirects=1)).get("players?status=FA&count=0")


def test_a_raw_page_that_still_goes_to_the_sign_in_after_the_sign_in_raises_an_error(capsys):
    with pytest.raises(PageNotReady) as error:
        League(SignInPage(), 22820, fetch=FakeFetch(redirects=2)).get("players?status=FA&count=0")
    assert "login.yahoo.com" in str(error.value)


@pytest.mark.parametrize("path", RAW_PATHS)
def test_a_raw_page_with_no_element_for_its_reader_raises_an_error_that_names_the_page(path):
    with pytest.raises(PageNotReady) as error:
        League(FakePage(), 22820, fetch=FakeFetch(html="<html>other page</html>")).get(path)
    assert f"{SITE}/nba/22820/{path}" in str(error.value)


@pytest.mark.parametrize(
    "path, element",
    [
        ("players?status=FA", "players"),
        ("matchup?mid1=10", None),
        ("buzzindex?date=2026-10-21", "Tst-table"),
        ("10", None),
    ],
)
def test_raw_kind_names_the_element_of_each_raw_page_kind_and_none_for_a_page_from_edge(path, element):
    assert raw_kind(path) == element


def test_has_element_finds_a_class_among_other_classes_and_not_a_longer_class():
    assert has_element('<div class="Grid players Mb-sm">', "players")
    assert has_element("<a class='Navtarget' href='x'>", "Navtarget")
    assert not has_element('<div class="playersx">', "players")
    assert not has_element("<p>players</p>", "players")


class FakeResponseText:
    def __init__(self, url):
        self.status, self.url, self.disposed = 200, url, False

    def text(self):
        return f"<p>{self.url}</p>"

    def dispose(self):
        self.disposed = True


class FakeRequest:
    """A sync APIRequestContext with no private names of Playwright: raw_fetcher() reads one URL at a time."""

    def __init__(self):
        self.urls, self.responses = [], []

    def get(self, url, timeout):
        self.urls.append(url)
        self.responses.append(FakeResponseText(url))
        return self.responses[-1]


def test_raw_fetcher_with_no_private_names_of_playwright_reads_one_url_at_a_time():
    request = FakeRequest()
    fetch = raw_fetcher(request)
    assert fetch(["u1", "u2"]) == [(200, "u1", "<p>u1</p>"), (200, "u2", "<p>u2</p>")]
    assert request.urls == ["u1", "u2"]
    assert all(r.disposed for r in request.responses)


# The raw HTML gives the same rows as the HTML of Edge, for each page kind of RAW (#108).
# tests/adds/fixtures/raw_vs_rendered/ holds pairs from 2026-10-27, cut to the parts that the readers use. The
# rendered list pages are the raw pages rendered in Edge with each Yahoo Fantasy request stopped. The rendered
# Transaction Trends page comes from Edge in the planning run of 2026-10-27 19:52.
PAIRS = Path(__file__).parent / "fixtures" / "raw_vs_rendered"
DAY = date(2026, 10, 27)


def _list_rows(html):
    parsed = parse(html)
    return read_free_agents(parsed, totals=True), has_next_page(parsed)


def _waiver_rows(html):
    parsed = parse(html)
    return read_waiver_players(parsed, DAY, totals=True), has_next_page(parsed)


@pytest.mark.parametrize(
    "kind, read",
    [("team_list", _list_rows), ("market", _list_rows), ("waivers", _waiver_rows), ("trends", read_trends)],
)
def test_the_raw_html_gives_the_same_rows_as_the_html_of_edge(kind, read):
    raw = read((PAIRS / f"{kind}_raw.html").read_text(encoding="utf-8"))
    rendered = read((PAIRS / f"{kind}_rendered.html").read_text(encoding="utf-8"))
    assert raw == rendered
    assert len(raw[0] if isinstance(raw, tuple) else raw) == 4  # the fixtures keep 4 rows


def test_the_raw_market_page_has_the_next_page_link():
    assert _list_rows((PAIRS / "market_raw.html").read_text(encoding="utf-8"))[1]
