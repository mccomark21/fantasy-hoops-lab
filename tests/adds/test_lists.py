from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from fantasyhoops.adds import lists, readers, timing
from fantasyhoops.adds.lists import recent_weight_limit, skips_recent_view
from fantasyhoops.adds.plan import value_options
from fantasyhoops.adds.readers import Player

MON = date(2027, 1, 4)
TODAY = date(2026, 10, 21)
PARTS = ["projected pass", "recent pass", "market pages", "waiver list"]


class ListPages:
    """A fake session.League with the fixture HTML of each list: the team lists (one page each), the market list
    (a "Next 25" link on each page) and the waiver list (one page). It counts the pages and keeps their paths."""

    def __init__(self):
        self.pages, self.paths = 0, []

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        if "status=W" in path:
            name = "waivers.html"
        elif "eteam=" not in path:
            name = "free_agents.html"
        else:
            name = "free_agents_phi_recent.html" if lists.RECENT in path else "free_agents_phi.html"
        return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def _read(tmp_path, skip):
    """read_lists() of PHI and BOS in a timed step "Yahoo reads". Give (FreeAgentLists, League, StepTimes)."""
    yahoo, timings = ListPages(), timing.Timings(path=tmp_path / "timings.csv")
    with timings.step("Yahoo reads"):
        found = lists.read_lists(yahoo, yahoo, ["PHI", "BOS"], TODAY, lambda fas, rec: [], skip, timings.part)
    return found, yahoo, timings.steps


def _kind(path):
    """The list and the view of a page path, for example "team S_PS7"."""
    kind = "waiver" if "status=W" in path else "team" if "eteam=" in path else "market"
    return f"{kind} {lists.RECENT if lists.RECENT in path else lists.PROJECTED}"


def test_read_lists_reads_the_lists_in_order_and_times_each_sub_step(tmp_path):
    found, yahoo, steps = _read(tmp_path, skip=False)
    p, r = lists.PROJECTED, lists.RECENT
    # The team lists in both views, each market page in both views, the waiver list in both views (#92).
    assert [_kind(path) for path in yahoo.paths] == (
        [f"team {p}"] * 2 + [f"team {r}"] * 2 + [f"market {p}", f"market {r}"] * 3 + [f"waiver {p}", f"waiver {r}"]
    )
    assert [(s.step, s.pages) for s in steps] == [
        ("Yahoo reads", 12),
        ("Yahoo reads: projected pass", 2),
        ("Yahoo reads: recent pass", 2),
        ("Yahoo reads: market pages", 6),
        ("Yahoo reads: waiver list", 2),
    ]
    assert (found.market.pages, found.market.stop) == (3, "limit")
    assert found.market_line == lists.market_line(found.market)
    # Each player one time, in the list order: team lists, market, waivers.
    names = [(f.player.name, f.player.team) for f in found.free_agents]
    assert len(names) == len(set(names)) and found.recent
    assert any(f.player.on_waivers for f in found.free_agents[-5:])


def test_read_lists_without_the_recent_view_keeps_the_sub_step_rows(tmp_path):
    found, yahoo, steps = _read(tmp_path, skip=True)
    assert not [path for path in yahoo.paths if lists.RECENT in path]
    assert [s.step.removeprefix("Yahoo reads: ") for s in steps[1:]] == PARTS
    assert [s.pages for s in steps[1:]] == [2, 0, 3, 1]
    assert found.recent == [] and found.market.recent == []


class Pages:
    """A fake session.League that gives the HTML of one fixture for each page and counts the pages."""

    def __init__(self, name):
        self.html = (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")
        self.pages = 0

    def get(self, path):
        self.pages += 1
        return self.html


def test_the_read_of_each_list_page_parses_the_page_one_time(monkeypatch):
    parses = []

    class CountedSoup(BeautifulSoup):
        def __init__(self, *args, **kw):
            parses.append(1)
            super().__init__(*args, **kw)

    monkeypatch.setattr(readers, "BeautifulSoup", CountedSoup)
    reads = [
        (lambda y: lists.read_team_free_agents(y, ["PHI", "BOS"]), "free_agents_phi.html"),
        (lambda y: lists.read_team_free_agents(y, ["PHI"], lists.RECENT), "free_agents_phi_recent.html"),
        (lists.read_market_free_agents, "free_agents.html"),  # a "Next 25" link on each page: 3 pages in each view
        (lambda y: lists.read_waiver_list(y, date(2026, 10, 21)), "waivers.html"),
    ]
    for read, name in reads:
        parses.clear()
        yahoo = Pages(name)
        assert read(yahoo)
        assert yahoo.pages and len(parses) == yahoo.pages, name


def _schedule(games):
    """A schedule with one row for each (day, team) game."""
    return pd.DataFrame({"date": [str(d) for d, _ in games], "team": [t for _, t in games]})


def test_the_weight_limit_counts_the_games_of_the_busiest_team_from_14_days_ago_to_today():
    def day(n):
        return MON - timedelta(days=n)

    games = [
        (day(15), "PHI"),
        (day(14), "PHI"),
        (day(7), "PHI"),
        (day(0), "PHI"),
        (MON + timedelta(days=1), "PHI"),
        (day(3), "BOS"),
        (day(2), "BOS"),
    ]
    assert recent_weight_limit(_schedule(games), MON) == (3, 3 / 14)
    assert recent_weight_limit(_schedule([]), MON) == (0, 0.0)


def test_the_run_skips_the_recent_view_only_below_the_setting():
    assert skips_recent_view(4 / 14, {"adds": {"recent_skip_weight": 0.3}})
    assert not skips_recent_view(0.3, {"adds": {"recent_skip_weight": 0.3}})
    assert not skips_recent_view(5 / 14, {"adds": {"recent_skip_weight": 0.3}})
    assert not skips_recent_view(0.0, {"adds": {}})  # no setting: never skip


# The market read and its guard (#92).
FREE_AGENTS_HTML = "free_agents.html"  # a "Next 25" link on each page


class ViewPages(Pages):
    """A fake League that gives the same fixture for each page and keeps the path of each page."""

    def __init__(self, name):
        super().__init__(name)
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        return super().get(path)

    def views(self):
        """The pages of each view: (projected pages, recent pages)."""
        return (
            sum(f"stat1={lists.PROJECTED}" in p for p in self.paths),
            sum(f"stat1={lists.RECENT}" in p for p in self.paths),
        )


@pytest.mark.parametrize("recent", [True, False])
def test_the_market_read_reads_at_most_3_pages_in_each_view(recent):
    yahoo = ViewPages(FREE_AGENTS_HTML)
    market = lists.read_market_free_agents(yahoo, recent)
    assert lists.MARKET_PAGES == 3
    assert yahoo.views() == (3, 3 if recent else 0)
    assert (market.pages, market.stop) == (3, "limit")
    assert market.projected and bool(market.recent) == recent
    # Page by page: the projected page, then the recent page of the same offset.
    if recent:
        assert [p.replace(lists.RECENT, lists.PROJECTED) for p in yahoo.paths[1::2]] == yahoo.paths[::2]


def test_the_waiver_read_still_reads_up_to_6_pages():
    yahoo = Pages(FREE_AGENTS_HTML)
    lists.read_waiver_list(yahoo, date(2026, 10, 21))
    assert lists.WAIVER_PAGES == 6 and yahoo.pages == 6


def _agent(name, pts, games=3, status=""):
    """A FreeAgent of PHI with a line of pts points. pts None: no line."""
    return readers.FreeAgent(Player(name, "PHI", ("SF",), status=status), games, {} if pts is None else {"pts": pts})


class SyntheticPages:
    """A fake League and fake page readers: page n of a view gives the FreeAgents of page_lists[(view, n)].

    Each page has a "Next 25" link.
    """

    def __init__(self, monkeypatch, page_lists):
        self.paths = []
        monkeypatch.setattr(lists, "parse", lambda html: html)
        monkeypatch.setattr(lists, "has_next_page", lambda page: True)
        monkeypatch.setattr(lists, "read_free_agents", lambda page, totals=True: list(page_lists.get(page, [])))

    def get(self, path):
        self.paths.append(path)
        view = lists.RECENT if lists.RECENT in path else lists.PROJECTED
        return view, int(path.rsplit("count=", 1)[1]) // 25


SCALE = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"])  # value = (pts - 10) / 5
CFG = {"weights": {"pts": 1.0}}


def blended(fas, recent):
    """The real values of the run (value_options()) with a scale of pts only."""
    return value_options(fas, CFG, recent, scale=SCALE)


def _team_lists(n, pts=20.0):
    """n team-list free agents with a projected line of pts (value 2.0 for 20 points) and no recent games."""
    return [_agent(f"Team {i}", pts) for i in range(n)]


@pytest.mark.parametrize("recent", [True, False])
def test_the_guard_stops_after_a_page_with_no_new_player_above_the_replacement_value(monkeypatch, recent):
    page_lists = {
        (lists.PROJECTED, 0): [_agent("Good", 30.0), _agent("Low", 5.0)],
        (lists.PROJECTED, 1): [_agent("Low Two", 12.0), _agent("Team 3", 30.0)],
    }
    yahoo = SyntheticPages(monkeypatch, page_lists)
    market = lists.read_market_free_agents(yahoo, recent, _team_lists(15), [], blended)
    # Page 1 has Good (value 4.0) above the 15th-best value (2.0). Page 2 has only Low Two (0.4) as a new player.
    # Team 3 is on a team list, so he is not new.
    assert (market.pages, market.stop) == (2, "guard")
    assert [f.player.name for f in market.projected] == ["Good", "Low", "Low Two", "Team 3"]
    assert len(yahoo.paths) == (4 if recent else 2)
    assert lists.market_line(market) == (
        "Market: 2 of 3 pages. Page 2 had no new player above the replacement value (the free agent at rank 15 of "
        "the players read before it)."
    )


@pytest.mark.parametrize("recent", [True, False])
def test_with_fewer_than_15_free_agents_with_a_value_the_guard_does_not_stop(monkeypatch, recent):
    # The market players have no projection and no recent games, so they have no value.
    page_lists = {(lists.PROJECTED, n): [_agent(f"None {n}", None, games=0)] for n in range(3)}
    found = _team_lists(14) + [_agent("Out", 25.0, status="O")]  # an Out player does not count
    market = lists.read_market_free_agents(SyntheticPages(monkeypatch, page_lists), recent, found, [], blended)
    assert (market.pages, market.stop) == (3, "limit")
    assert lists.market_line(market) == "Market: 3 of 3 pages (the limit)."
    # With 15 team-list free agents with a value, the guard stops after page 1.
    market = lists.read_market_free_agents(
        SyntheticPages(monkeypatch, page_lists), recent, _team_lists(15), [], blended
    )
    assert (market.pages, market.stop) == (1, "guard")


def test_the_guard_uses_the_blended_value_and_the_projected_value_without_the_recent_view(monkeypatch):
    # Hot: projected 12 points (value 0.4), 14 recent games at 40 points. Blended with w = 1: 40 points (value 6.0).
    page_lists = {
        (lists.PROJECTED, 0): [_agent("Hot", 12.0)],
        (lists.RECENT, 0): [_agent("Hot", 40.0, games=14)],
        (lists.PROJECTED, 1): [_agent("Cold", 5.0)],
        (lists.RECENT, 1): [_agent("Cold", 5.0, games=14)],
    }
    # The team lists have 15 players at 20 points (value 2.0) in both views. The bar is 2.0.
    found, found_recent = _team_lists(15), _team_lists(15)
    with_recent = lists.read_market_free_agents(
        SyntheticPages(monkeypatch, page_lists), True, found, found_recent, blended
    )
    assert (with_recent.pages, with_recent.stop) == (2, "guard")  # Hot is above the bar by his blended value
    # The run gives the values of the team lists to the market read (known), as main() does. The result is the same.
    known = lists.known_values(found, found_recent, blended)
    assert (
        lists.read_market_free_agents(
            SyntheticPages(monkeypatch, page_lists), True, found, found_recent, blended, known
        )
        == with_recent
    )
    # While the run skips the recent view (#90), the blended value is the projected value: Hot (0.4) is below 2.0.
    skipped = lists.read_market_free_agents(SyntheticPages(monkeypatch, page_lists), False, found, [], blended)
    assert (skipped.pages, skipped.stop, skipped.recent) == (1, "guard", [])


def test_the_market_line_names_the_last_page_of_the_list():
    market = lists.MarketRead([], [], 2, "end")
    assert lists.market_line(market) == "Market: 2 of 3 pages. Page 2 was the last page of the list."


# The reads that go together (#108).
FIXTURES = Path(__file__).parent / "fixtures"


class TeamPages:
    """A fake League: the lists of BOS and of the market have a "Next 25" link on each page. The other lists have
    one page.

    together: True gives get_many(), which keeps each batch of paths. False: get() only.
    """

    def __init__(self, together=True):
        self.many = (FIXTURES / FREE_AGENTS_HTML).read_text(encoding="utf-8")
        self.one = (FIXTURES / "free_agents_phi.html").read_text(encoding="utf-8")
        self.batches = []
        if together:
            self.get_many = self._get_many

    def get(self, path):
        return self.many if f"ET_{lists.yahoo_id('BOS')}&" in path or "eteam" not in path else self.one

    def _get_many(self, paths):
        self.batches.append(list(paths))
        return [self.get(path) for path in paths]


def test_the_team_lists_read_page_1_of_all_teams_together_and_then_the_next_pages_of_the_teams_that_have_one():
    yahoo = TeamPages()
    lists.read_team_free_agents(yahoo, ["PHI", "BOS", "NY"])
    assert [len(batch) for batch in yahoo.batches] == [3] + [1] * (lists.MAX_PAGES - 1)
    assert all(p.endswith("&count=0") for p in yahoo.batches[0])
    assert yahoo.batches[1] == [lists.free_agent_path("BOS", 25)]


def test_the_team_lists_give_the_free_agents_in_the_same_order_with_and_without_reads_together():
    teams = ["PHI", "BOS", "NY"]
    together = lists.read_team_free_agents(TeamPages(), teams)
    assert together == lists.read_team_free_agents(TeamPages(together=False), teams)
    # Team by team: the 10 pages of BOS come between the page of PHI and the page of NY.
    one = lists.read_team_free_agents(TeamPages(), ["PHI"])
    assert together[: len(one)] == one and together[-len(one) :] == one


@pytest.mark.parametrize("recent", [True, False])
def test_the_market_read_reads_the_two_views_of_a_page_together_and_no_page_ahead(recent):
    yahoo = TeamPages()
    lists.read_market_free_agents(yahoo, recent)
    assert [len(batch) for batch in yahoo.batches] == [2 if recent else 1] * lists.MARKET_PAGES
