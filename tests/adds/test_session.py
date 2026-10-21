"""Tests of League.get() with a fake page. The tests open no browser and use no network."""
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fantasyhoops.adds.session import SITE, League, PageNotReady, ready_selector


class FakePage:
    """The part of a Playwright page that League uses. missing: selectors that never appear."""

    def __init__(self, missing=()):
        self.url = ""
        self.missing = set(missing)
        self.waits = []

    def goto(self, url, wait_until, timeout):
        self.url = url

    def wait_for_selector(self, selector, state, timeout):
        self.waits.append((selector, state, timeout))
        if selector in self.missing:
            raise PlaywrightTimeout(f"Timeout {timeout}ms exceeded.")

    def content(self):
        return "<html>page</html>"


@pytest.mark.parametrize("path, selector", [
    ("10", "table#statTable0 tbody tr[data-pos]"),
    ("matchup?mid1=10", "a.Navtarget[href]"),
    ("matchup?week=2&mid1=10", "a.Navtarget[href]"),
    ("players?status=FA&pos=P&count=25", "div.players table"),
    ("players?status=W&pos=P&count=0", "div.players table"),
])
def test_ready_selector_names_the_element_that_the_reader_needs(path, selector):
    assert ready_selector(path) == selector


def test_ready_selector_of_a_page_with_no_reader_is_none():
    assert ready_selector("") is None


def test_get_waits_for_the_element_of_the_page_and_not_for_networkidle():
    page = FakePage()  # the fake has no wait_for_load_state, so a networkidle wait fails the test
    html = League(page, 22820, wait_seconds=7).get("players?status=FA&count=0")
    assert html == "<html>page</html>"
    assert page.waits == [("div.players table", "attached", 7000)]


def test_get_of_a_page_with_no_reader_does_not_wait():
    page = FakePage()
    League(page, 22820).get()
    assert page.waits == []


def test_get_names_the_page_and_the_element_when_the_element_does_not_appear():
    page = FakePage(missing={"table#statTable0 tbody tr[data-pos]"})
    with pytest.raises(PageNotReady) as error:
        League(page, 22820, wait_seconds=5).get("10")
    message = str(error.value)
    assert f"{SITE}/nba/22820/10" in message
    assert "table#statTable0 tbody tr[data-pos]" in message
    assert "5 s" in message
