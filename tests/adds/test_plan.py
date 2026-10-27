from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from fantasyhoops.adds import plan as command
from fantasyhoops.adds import readers
from fantasyhoops.adds.plan import print_plan, recent_weight_limit, skips_recent_view
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamWindow
from fantasyhoops.adds.readers import Adds, Player

MON = date(2027, 1, 4)


def test_each_window_option_shows_its_games_next_week(capsys):
    first, second = Option(Player("First", "PHI", ("SF",)), 1.0), Option(Player("Second", "PHI", ("C",)), 0.5)
    window = TeamWindow(spot=0, team="PHI", add_day=MON, last_day=MON, started=(MON,), player=first,
                        options=(first, second))
    plan = Plan(windows=(window,), started_games=1, adds=1, value=1.0, next_games=2.0, next_value=2.0)
    print_plan(plan, [StreamSpot()], Adds(used=0, limit=5), MON, next_week={"PHI": 4})
    lines = capsys.readouterr().out.splitlines()
    assert "next week 4 games" in next(line for line in lines if "First" in line)
    assert "next week 4 games" in next(line for line in lines if "Second" in line)
    assert any("Next week: the last players in the stream spots have 4 games" in line for line in lines)


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
    reads = [(lambda y: command.read_team_free_agents(y, ["PHI", "BOS"]), "free_agents_phi.html"),
             (lambda y: command.read_team_free_agents(y, ["PHI"], command.RECENT), "free_agents_phi_recent.html"),
             (command.read_market_free_agents, "free_agents.html"),  # a "Next 25" link on each page: 3 pages in each view
             (lambda y: command.read_waiver_list(y, date(2026, 10, 21)), "waivers.html")]
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
    games = [(day(15), "PHI"), (day(14), "PHI"), (day(7), "PHI"), (day(0), "PHI"), (MON + timedelta(days=1), "PHI"),
             (day(3), "BOS"), (day(2), "BOS")]
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
        return (sum(f"stat1={command.PROJECTED}" in p for p in self.paths),
                sum(f"stat1={command.RECENT}" in p for p in self.paths))


@pytest.mark.parametrize("recent", [True, False])
def test_the_market_read_reads_at_most_3_pages_in_each_view(recent):
    yahoo = ViewPages(FREE_AGENTS_HTML)
    market = command.read_market_free_agents(yahoo, recent)
    assert command.MARKET_PAGES == 3
    assert yahoo.views() == (3, 3 if recent else 0)
    assert (market.pages, market.stop) == (3, "limit")
    assert market.projected and bool(market.recent) == recent
    # Page by page: the projected page, then the recent page of the same offset.
    if recent:
        assert [p.replace(command.RECENT, command.PROJECTED) for p in yahoo.paths[1::2]] == yahoo.paths[::2]


def test_the_waiver_read_still_reads_up_to_6_pages():
    yahoo = Pages(FREE_AGENTS_HTML)
    command.read_waiver_list(yahoo, date(2026, 10, 21))
    assert command.WAIVER_PAGES == 6 and yahoo.pages == 6


def _agent(name, pts, games=3, status=""):
    """A FreeAgent of PHI with a line of pts points. pts None: no line."""
    return readers.FreeAgent(Player(name, "PHI", ("SF",), status=status), games, {} if pts is None else {"pts": pts})


class SyntheticPages:
    """A fake League and fake page readers: page n of a view gives the FreeAgents of lists[(view, n)].

    Each page has a "Next 25" link.
    """

    def __init__(self, monkeypatch, lists):
        self.paths = []
        monkeypatch.setattr(command, "parse", lambda html: html)
        monkeypatch.setattr(command, "has_next_page", lambda page: True)
        monkeypatch.setattr(command, "read_free_agents", lambda page, totals=True: list(lists.get(page, [])))

    def get(self, path):
        self.paths.append(path)
        view = command.RECENT if command.RECENT in path else command.PROJECTED
        return view, int(path.rsplit("count=", 1)[1]) // 25


SCALE = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"])  # value = (pts - 10) / 5
CFG = {"weights": {"pts": 1.0}}


def blended(fas, recent):
    """The real values of the run (value_options()) with a scale of pts only."""
    return command.value_options(fas, CFG, recent, scale=SCALE)


def _team_lists(n, pts=20.0):
    """n team-list free agents with a projected line of pts (value 2.0 for 20 points) and no recent games."""
    return [_agent(f"Team {i}", pts) for i in range(n)]


@pytest.mark.parametrize("recent", [True, False])
def test_the_guard_stops_after_a_page_with_no_new_player_above_the_replacement_value(monkeypatch, recent):
    lists = {(command.PROJECTED, 0): [_agent("Good", 30.0), _agent("Low", 5.0)],
             (command.PROJECTED, 1): [_agent("Low Two", 12.0), _agent("Team 3", 30.0)]}
    yahoo = SyntheticPages(monkeypatch, lists)
    market = command.read_market_free_agents(yahoo, recent, _team_lists(15), [], blended)
    # Page 1 has Good (value 4.0) above the 15th-best value (2.0). Page 2 has only Low Two (0.4) as a new player.
    # Team 3 is on a team list, so he is not new.
    assert (market.pages, market.stop) == (2, "guard")
    assert [f.player.name for f in market.projected] == ["Good", "Low", "Low Two", "Team 3"]
    assert len(yahoo.paths) == (4 if recent else 2)
    assert command.market_line(market) == (
        "Market: 2 of 3 pages. Page 2 had no new player above the replacement value (the free agent at rank 15 of "
        "the players read before it).")


@pytest.mark.parametrize("recent", [True, False])
def test_with_fewer_than_15_free_agents_with_a_value_the_guard_does_not_stop(monkeypatch, recent):
    # The market players have no projection and no recent games, so they have no value.
    lists = {(command.PROJECTED, n): [_agent(f"None {n}", None, games=0)] for n in range(3)}
    found = _team_lists(14) + [_agent("Out", 25.0, status="O")]  # an Out player does not count
    market = command.read_market_free_agents(SyntheticPages(monkeypatch, lists), recent, found, [], blended)
    assert (market.pages, market.stop) == (3, "limit")
    assert command.market_line(market) == "Market: 3 of 3 pages (the limit)."
    # With 15 team-list free agents with a value, the guard stops after page 1.
    market = command.read_market_free_agents(SyntheticPages(monkeypatch, lists), recent, _team_lists(15), [], blended)
    assert (market.pages, market.stop) == (1, "guard")


def test_the_guard_uses_the_blended_value_and_the_projected_value_without_the_recent_view(monkeypatch):
    # Hot: projected 12 points (value 0.4), 14 recent games at 40 points. Blended with w = 1: 40 points (value 6.0).
    lists = {(command.PROJECTED, 0): [_agent("Hot", 12.0)], (command.RECENT, 0): [_agent("Hot", 40.0, games=14)],
             (command.PROJECTED, 1): [_agent("Cold", 5.0)], (command.RECENT, 1): [_agent("Cold", 5.0, games=14)]}
    # The team lists have 15 players at 20 points (value 2.0) in both views. The bar is 2.0.
    found, found_recent = _team_lists(15), _team_lists(15)
    with_recent = command.read_market_free_agents(SyntheticPages(monkeypatch, lists), True, found, found_recent,
                                                  blended)
    assert (with_recent.pages, with_recent.stop) == (2, "guard")  # Hot is above the bar by his blended value
    # While the run skips the recent view (#90), the blended value is the projected value: Hot (0.4) is below 2.0.
    skipped = command.read_market_free_agents(SyntheticPages(monkeypatch, lists), False, found, [], blended)
    assert (skipped.pages, skipped.stop, skipped.recent) == (1, "guard", [])


def test_the_market_line_names_the_last_page_of_the_list():
    market = command.MarketRead([], [], 2, "end")
    assert command.market_line(market) == "Market: 2 of 3 pages. Page 2 was the last page of the list."
