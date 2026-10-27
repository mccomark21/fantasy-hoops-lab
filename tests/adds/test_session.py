"""Tests of League.get() with a fake page. The tests open no browser and use no network."""

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fantasyhoops.adds.session import SCORE_WAIT_SECONDS, SITE, League, PageNotReady, UnknownPage, ready_selectors

TEAM = "table#statTable0 tbody tr[data-pos]"
PLAYERS = "div.players table tbody tr"
DAYS = "a.Navtarget[href]"
SCORES = "table.Datatable tbody tr"
TRENDS = "table.Tst-table tbody tr"


class FakePage:
    """The part of a Playwright page that League uses. missing: selectors that never appear."""

    def __init__(self, missing=()):
        self.url = ""
        self.missing = set(missing)
        self.visits = []
        self.waits = []

    def goto(self, url, wait_until, timeout):
        self.url = url
        self.visits.append(url)

    def wait_for_selector(self, selector, state, timeout):
        self.waits.append((selector, state, timeout))
        if selector in self.missing:
            raise PlaywrightTimeout(f"Timeout {timeout}ms exceeded.")

    def content(self):
        return "<html>page</html>"


@pytest.mark.parametrize(
    "path, required, optional",
    [
        ("10", (TEAM,), ()),
        ("matchup?mid1=10", (DAYS,), (SCORES,)),
        ("matchup?week=2&mid1=10", (DAYS,), (SCORES,)),
        ("players?status=FA&pos=P&count=25", (PLAYERS,), ()),
        ("players?status=W&pos=P&count=0", (PLAYERS,), ()),
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
        super().goto(url, wait_until, timeout)
        if len(self.visits) == 1:
            self.url = "https://login.yahoo.com/"

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
