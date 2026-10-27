from datetime import date, timedelta
from pathlib import Path

import pandas as pd
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
             (command.read_market_free_agents, "free_agents.html"),  # a "Next 25" link on each page: 6 pages
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
