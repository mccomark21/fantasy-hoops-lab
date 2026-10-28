import csv
import json
import re
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from fantasyhoops.adds import cache as page_cache
from fantasyhoops.adds import page, readers, timing
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.plan import print_plan, recent_weight_limit, skips_recent_view
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamWindow
from fantasyhoops.adds.readers import Adds, FreeAgent, Player, Week
from fantasyhoops.adds.role_up import Absence
from fantasyhoops.core import common, tokens
from tests.adds.test_page import SKIP_LINE, WEEK, option, run_time, text

MON = date(2027, 1, 4)


def test_each_window_option_shows_its_games_next_week(capsys):
    first, second = Option(Player("First", "PHI", ("SF",)), 1.0), Option(Player("Second", "PHI", ("C",)), 0.5)
    window = TeamWindow(
        spot=0, team="PHI", add_day=MON, last_day=MON, started=(MON,), player=first, options=(first, second)
    )
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
    reads = [
        (lambda y: command.read_team_free_agents(y, ["PHI", "BOS"]), "free_agents_phi.html"),
        (lambda y: command.read_team_free_agents(y, ["PHI"], command.RECENT), "free_agents_phi_recent.html"),
        (command.read_market_free_agents, "free_agents.html"),  # a "Next 25" link on each page: 3 pages in each view
        (lambda y: command.read_waiver_list(y, date(2026, 10, 21)), "waivers.html"),
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
            sum(f"stat1={command.PROJECTED}" in p for p in self.paths),
            sum(f"stat1={command.RECENT}" in p for p in self.paths),
        )


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
    lists = {
        (command.PROJECTED, 0): [_agent("Good", 30.0), _agent("Low", 5.0)],
        (command.PROJECTED, 1): [_agent("Low Two", 12.0), _agent("Team 3", 30.0)],
    }
    yahoo = SyntheticPages(monkeypatch, lists)
    market = command.read_market_free_agents(yahoo, recent, _team_lists(15), [], blended)
    # Page 1 has Good (value 4.0) above the 15th-best value (2.0). Page 2 has only Low Two (0.4) as a new player.
    # Team 3 is on a team list, so he is not new.
    assert (market.pages, market.stop) == (2, "guard")
    assert [f.player.name for f in market.projected] == ["Good", "Low", "Low Two", "Team 3"]
    assert len(yahoo.paths) == (4 if recent else 2)
    assert command.market_line(market) == (
        "Market: 2 of 3 pages. Page 2 had no new player above the replacement value (the free agent at rank 15 of "
        "the players read before it)."
    )


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
    lists = {
        (command.PROJECTED, 0): [_agent("Hot", 12.0)],
        (command.RECENT, 0): [_agent("Hot", 40.0, games=14)],
        (command.PROJECTED, 1): [_agent("Cold", 5.0)],
        (command.RECENT, 1): [_agent("Cold", 5.0, games=14)],
    }
    # The team lists have 15 players at 20 points (value 2.0) in both views. The bar is 2.0.
    found, found_recent = _team_lists(15), _team_lists(15)
    with_recent = command.read_market_free_agents(
        SyntheticPages(monkeypatch, lists), True, found, found_recent, blended
    )
    assert (with_recent.pages, with_recent.stop) == (2, "guard")  # Hot is above the bar by his blended value
    # The run gives the values of the team lists to the market read (known), as main() does. The result is the same.
    known = command.known_values(found, found_recent, blended)
    assert (
        command.read_market_free_agents(SyntheticPages(monkeypatch, lists), True, found, found_recent, blended, known)
        == with_recent
    )
    # While the run skips the recent view (#90), the blended value is the projected value: Hot (0.4) is below 2.0.
    skipped = command.read_market_free_agents(SyntheticPages(monkeypatch, lists), False, found, [], blended)
    assert (skipped.pages, skipped.stop, skipped.recent) == (1, "guard", [])


def test_the_market_line_names_the_last_page_of_the_list():
    market = command.MarketRead([], [], 2, "end")
    assert command.market_line(market) == "Market: 2 of 3 pages. Page 2 was the last page of the list."


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
        return self.many if f"ET_{command.yahoo_id('BOS')}&" in path or "eteam" not in path else self.one

    def _get_many(self, paths):
        self.batches.append(list(paths))
        return [self.get(path) for path in paths]


def test_the_team_lists_read_page_1_of_all_teams_together_and_then_the_next_pages_of_the_teams_that_have_one():
    yahoo = TeamPages()
    command.read_team_free_agents(yahoo, ["PHI", "BOS", "NY"])
    assert [len(batch) for batch in yahoo.batches] == [3] + [1] * (command.MAX_PAGES - 1)
    assert all(p.endswith("&count=0") for p in yahoo.batches[0])
    assert yahoo.batches[1] == [command.free_agent_path("BOS", 25)]


def test_the_team_lists_give_the_free_agents_in_the_same_order_with_and_without_reads_together():
    teams = ["PHI", "BOS", "NY"]
    together = command.read_team_free_agents(TeamPages(), teams)
    assert together == command.read_team_free_agents(TeamPages(together=False), teams)
    # Team by team: the 10 pages of BOS come between the page of PHI and the page of NY.
    one = command.read_team_free_agents(TeamPages(), ["PHI"])
    assert together[: len(one)] == one and together[-len(one) :] == one


@pytest.mark.parametrize("recent", [True, False])
def test_the_market_read_reads_the_two_views_of_a_page_together_and_no_page_ahead(recent):
    yahoo = TeamPages()
    command.read_market_free_agents(yahoo, recent)
    assert [len(batch) for batch in yahoo.batches] == [2 if recent else 1] * command.MARKET_PAGES


# The tests of plan.main(). run_command() runs it with fakes (#128: from tests/adds/test_page.py).


def test_the_command_prints_the_waiver_players_and_uses_one_after_his_clear_day(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue. The waiver player clears on Mon, so the plan adds him on Tue. The DEN free agent has no
    # game. He is the replacement free agent (value 0.1), so the market value of the waiver player is +0.20.
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    run_command(monkeypatch, tmp_path, [], publish=False, options=[claim, option("Den Guy", "DEN", 0.1)])
    out = capsys.readouterr().out
    assert "Waiver players (a claim is not sure, and it uses an add):" in out
    assert "Phi Claim (PHI) SF  clears Mon 01/04, first plan day Tue 01/05, Val +0.20" in out
    # The page shows the same Val.
    assert "Phi Claim W PHI SF Mon 1/4 Tue 1/5 +0.20" in text(page.page_path().read_text(encoding="utf-8"))
    assert "Spot 1: PHI Tue 01/05 to Tue 01/05" in out
    assert "1. Phi Claim W (waiver claim, not sure)" in out
    assert command.free_agent_path(None, 25, status="W").startswith("players?status=W&")


def test_the_command_writes_the_page_and_publishes_it(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=True)
    path = page.page_path()
    assert published == [(command.ROOT, "adds", path)]
    out = capsys.readouterr().out
    assert f"Wrote the plan page: {path}" in out
    assert "Plan page: best plan for one roster spot: +2 started games with 1 add." in out
    assert command.URL in out and command.URL.endswith("/adds/")
    assert "+Phi One (PHI) add Mon – starts Mon & Tue" in text(path.read_text(encoding="utf-8"))
    assert "Aggressive plan: the same as the schedule plan." in out
    assert (path.parent / "fonts" / "archivo-latin.woff2").read_bytes() == tokens.FONT.read_bytes()
    assert (path.parent / "fonts" / "OFL.txt").read_bytes() == tokens.LICENSE.read_bytes()


def test_the_command_prints_the_comparison_and_shows_the_plans_for_one_roster_spot(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue, BOS plays Mon. The schedule plan takes 2 games of the weak PHI player. The aggressive
    # plan takes 1 game of the better BOS player: 9 above an empty slot (-10) is more than 2 x 4.
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0)]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options)
    out = capsys.readouterr().out
    assert "Schedule plan: 2 started games with 1 add" in out
    assert "Aggressive plan: 1 started game with 1 add" in out
    lines = [line.split() for line in out[out.index("Comparison:") :].splitlines()[1:7]]
    assert lines == [
        ["Schedule", "Aggressive"],
        ["Adds", "1", "1"],
        ["Started", "games", "2", "1"],
        ["Blended", "value", "-12.00", "-1.00"],
        ["Value", "above", "an", "empty", "slot", "+8.00", "+9.00"],
        ["Matchup", "value", "above", "empty", "+8.00", "+9.00"],
    ]
    # The read_league() of this test gives no matchup scores, so all weights are 1.
    assert "the planner did not find the category scores" in out
    # Each row of the page has different players: the PHI player first (2 games), then the BOS player (1 game).
    shown = text(page.page_path().read_text(encoding="utf-8"))
    assert "Comparison" not in shown and "Aggressive" not in shown
    assert "+Phi Weak (PHI) add Mon – starts Mon & Tue" in shown and "+Bos Good (BOS) add Mon – starts Mon" in shown
    assert "  1. +2 started games with 1 add" in out and "  2. +1 started games with 1 add" in out


def test_the_command_does_not_publish_with_no_publish(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=False)
    assert published == []
    assert page.page_path().exists()
    assert "did not publish" in capsys.readouterr().out


def test_the_command_counts_a_second_night_of_a_player_on_the_rest_list_as_less_than_1_game(
    monkeypatch, tmp_path, capsys
):
    # PHI plays Mon and Tue. Phi One is on the rest list, and [adds] rest_chance is 0.5.
    run_command(monkeypatch, tmp_path, [], publish=False, rests={"phi one"})
    out = capsys.readouterr().out
    assert "Schedule plan: 1.5 started games with 1 add" in out
    assert "Started games: 1.5 (Mon 01/04, Tue 01/05 b2b)." in out
    assert "  1. +1.5 started games with 1 add" in out
    assert 'class="b2b"' in page.page_path().read_text(encoding="utf-8")


def test_the_command_marks_the_role_up_free_agents_in_the_window_options(monkeypatch, tmp_path, capsys):
    absent = [Absence("Star Wing", "PHI", WEEK[0] - timedelta(days=2), 1, ("SF", "PF"))]
    options = [option("Phi One", "PHI", 0.3), option("Phi Guard", "PHI", 0.2, ("PG",))]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options, absences=absent)
    out = capsys.readouterr().out
    assert "Role up: Star Wing (PHI) is absent. Free agents at his positions: Phi One." in out
    lines = out.splitlines()
    assert next(line for line in lines if "1. Phi One" in line).endswith("role up: Star Wing absent")
    assert not next(line for line in lines if "2. Phi Guard" in line).endswith("absent")
    assert "Star Wing is absent. Role up: Phi One (PHI)." in text(page.page_path().read_text(encoding="utf-8"))


def test_the_command_marks_the_free_agents_who_play_on_an_open_day_early_next_week(monkeypatch, tmp_path, capsys):
    # The week is Mon and Tue. Next week starts on Wed, and PHI plays then. The roster is empty, so all slots are open.
    run_command(monkeypatch, tmp_path, [], publish=False, extra_games=[(WEEK[2], "PHI")])
    html = page.page_path().read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Wed open"]
    assert "he has a game next Wednesday 1/6" in text(html)


def test_on_the_last_day_of_the_week_the_mark_checks_the_days_after_the_planned_week(monkeypatch, tmp_path):
    # read_league() moves data.week forward to Wed and Thu. So the mark checks Fri and Sat, not Wed.
    league = command.LeagueData(roster=[], adds=Adds(0, 5), week=Week(13, tuple(WEEK[2:4])), next_week=True)
    run_command(
        monkeypatch, tmp_path, [], publish=False, league=league, extra_games=[(WEEK[2], "PHI"), (WEEK[4], "PHI")]
    )
    html = page.page_path().read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Fri open"]
    assert "next Friday 1/8" in text(html) and "next Saturday 1/9" in text(html)


STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
    "absence read",
    "value options",
    "schedule search",
    "drop trade-offs",
    "aggressive search",
    "spot plans",
    "contingency plans",
    "role read",
    "page write and publish",
]
SEARCH_STEPS = {"schedule search", "drop trade-offs", "aggressive search", "spot plans"}
NO_READ_STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
    "contingency plans",
    "role read",
    "page write and publish",
]
YAHOO_PARTS = [
    "browser start",
    "league and matchup pages",
    "projected pass",
    "recent pass",
    "market pages",
    "waiver list",
    "trends",
]


def rows_of(steps, parts):
    """The step names of the rows of one run: each step, and after the Yahoo reads its sub-steps."""
    out = []
    for name in steps:
        out.append(name)
        if name == "Yahoo reads":
            out += [f"Yahoo reads: {p}" for p in parts]
    return out


ROWS = rows_of(STEPS, YAHOO_PARTS)
NO_READ_ROWS = rows_of(NO_READ_STEPS, YAHOO_PARTS[:2])  # no free agent read, so only the first 2 sub-steps


def timing_rows(tmp_path):
    with open(timing.timings_path(), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_the_command_prints_each_step_when_it_starts_and_its_time_when_it_ends(monkeypatch, tmp_path, capsys):
    run_command(monkeypatch, tmp_path, [], publish=False)
    lines = capsys.readouterr().out.splitlines()
    for name in STEPS:
        start = lines.index(f"Step: {name} ...")
        end = next(i for i, line in enumerate(lines) if re.fullmatch(rf"Step: {re.escape(name)}: \d+\.\d\d s.*", line))
        assert start < end
    assert any("timings.csv" in line for line in lines)


def test_the_command_appends_one_row_for_each_step_to_the_timings_file(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False)
    run_command(monkeypatch, tmp_path, [], publish=False)
    columns, rows = timing_rows(tmp_path)
    assert columns == ["run_at", "days", "open_days", "adds_left", "step", "seconds", "calls", "states", "pages"]
    assert [r["step"] for r in rows] == ROWS + ROWS
    first = rows[: len(ROWS)]
    assert len({r["run_at"] for r in first}) == 1
    assert {(r["days"], r["open_days"], r["adds_left"]) for r in rows} == {("2", "2", "1")}
    for r in rows:
        assert re.fullmatch(r"\d+\.\d\d", r["seconds"])
        if r["step"] in SEARCH_STEPS:  # drop trade-offs: 0 searches, because no stream spot has a holder
            assert int(r["calls"]) >= int(r["states"]) >= (r["step"] != "drop trade-offs")
        else:
            assert r["calls"] == r["states"] == ""
        # Only the Yahoo reads and its sub-steps have pages. The fake League of the test opens no page.
        assert r["pages"] == ("0" if r["step"].startswith("Yahoo reads") else "")


def test_a_step_that_does_not_run_writes_no_row(monkeypatch, tmp_path):
    # No adds left, so the run reads no free agent and runs no search.
    league = command.LeagueData(roster=[], adds=Adds(5, 5), week=Week(12, tuple(WEEK[:2])))
    run_command(monkeypatch, tmp_path, [], publish=False, league=league)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == NO_READ_ROWS
    assert all(r["calls"] == r["states"] == "" for r in rows)


def test_each_sub_step_of_the_yahoo_reads_counts_its_pages(monkeypatch, tmp_path, capsys):
    pages = {
        "league": 2,
        ("team", command.PROJECTED): 5,
        ("market", command.PROJECTED): 3,
        ("waiver", command.PROJECTED): 1,
        ("team", command.RECENT): 4,
        ("market", command.RECENT): 3,
        ("waiver", command.RECENT): 1,
        "trends": 3,
    }
    yahoo = run_command(monkeypatch, tmp_path, [], publish=False, pages=pages)
    # The team lists in both views, each market page in both views, the waiver list in both views (#92).
    market = [f"market {command.PROJECTED}", f"market {command.RECENT}"] * 3
    assert (
        yahoo.paths
        == ["league"] * 2
        + [f"team {command.PROJECTED}"] * 5
        + [f"team {command.RECENT}"] * 4
        + market
        + [f"waiver {command.PROJECTED}", f"waiver {command.RECENT}"]
        + ["trends"] * 3
    )
    _, rows = timing_rows(tmp_path)
    found = {r["step"]: r["pages"] for r in rows if r["step"].startswith("Yahoo reads")}
    assert found == {
        "Yahoo reads": "22",
        "Yahoo reads: browser start": "0",
        "Yahoo reads: league and matchup pages": "2",
        "Yahoo reads: projected pass": "5",
        "Yahoo reads: market pages": "6",
        "Yahoo reads: waiver list": "2",
        "Yahoo reads: recent pass": "4",
        "Yahoo reads: trends": "3",
    }
    out = capsys.readouterr().out
    assert re.search(r"Step: Yahoo reads: \d+\.\d\d s, 22 pages", out)
    assert re.search(r"  Yahoo reads: market pages: \d+\.\d\d s, 6 pages", out)


def test_an_old_timings_file_stays_readable(monkeypatch, tmp_path):
    old = (
        "run_at,days,open_days,adds_left,step,seconds,calls,states\n"
        "2026-10-26T09:00:00,2,2,1,schedule search,1.50,40,12\n"
    )
    timing.timings_path().parent.mkdir(parents=True)
    timing.timings_path().write_text(old, encoding="utf-8")
    run_command(monkeypatch, tmp_path, [], publish=False)
    columns, rows = timing_rows(tmp_path)
    assert columns == timing.COLUMNS
    assert rows[0] == {
        "run_at": "2026-10-26T09:00:00",
        "days": "2",
        "open_days": "2",
        "adds_left": "1",
        "step": "schedule search",
        "seconds": "1.50",
        "calls": "40",
        "states": "12",
        "pages": "",
    }
    assert [r["step"] for r in rows[1:]] == ROWS


def test_a_run_that_stops_keeps_the_rows_of_the_finished_steps(monkeypatch, tmp_path):
    def stop(*args):
        raise KeyboardInterrupt  # the owner stops the run with Ctrl+C during the spot plans

    monkeypatch.setattr(command, "spot_plans", stop)
    with pytest.raises(KeyboardInterrupt):
        run_command(monkeypatch, tmp_path, [], publish=False)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == ROWS[: ROWS.index("spot plans")]
    assert {(r["days"], r["open_days"], r["adds_left"]) for r in rows} == {("2", "2", "1")}


def test_the_page_shows_the_run_time_table(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False)
    html = page.page_path().read_text(encoding="utf-8")
    table = re.search(r"<summary>Run time</summary>.*?<tbody>(.*?)</tbody>", html, re.S).group(1)
    assert "<th>Pages</th>" in html
    rows = re.findall(r"<tr>(.*?)</tr>", table)
    cells = [re.findall(r"<td[^>]*>([^<]*)</td>", row) for row in rows]
    # The page write ends after the page is written. A sub-step row shows the sub-step name below the Yahoo reads.
    assert [c[0] for c in cells] == [r.removeprefix("Yahoo reads: ") for r in ROWS[:-1]]
    subs = [c[0] for row, c in zip(rows, cells) if row.startswith('<td class="name sub">')]
    assert subs == YAHOO_PARTS
    for name, seconds, calls, states, pages in cells:
        assert re.fullmatch(r"\d+\.\d\d", seconds)
        assert (calls != "" and states != "") == (name in SEARCH_STEPS)
        assert (pages != "") == (name == "Yahoo reads" or name in YAHOO_PARTS)


def test_the_timers_change_no_plan(monkeypatch, tmp_path, capsys):
    options = [option("Phi One", "PHI", 0.3), option("Bos One", "BOS", 0.2), option("Phi Two", "PHI", 0.1, ("C",))]
    league = command.LeagueData(roster=[], adds=Adds(2, 5), week=Week(12, tuple(WEEK[:2])))
    runs = report_runs(monkeypatch)
    for timed in (True, False):
        monkeypatch.setattr(common, "OUT", tmp_path / str(timed))
        run_command(monkeypatch, tmp_path, [], publish=False, options=options, league=league, timed=timed)
    timed_run, untimed_run = runs
    assert timed_run.plan is not None
    assert timed_run == untimed_run
    assert not (tmp_path / "False" / "adds" / "timings.csv").exists()
    # The run with no timers comes second, after the last step line of the timed run. It prints no step line.
    assert "Step:" not in capsys.readouterr().out.split("Step: page write and publish:")[-1]


class ListPages:
    """A fake session.League that gives the HTML of the fixtures for the free-agent lists and the waiver list."""

    def __init__(self):
        self.pages, self.paths = 0, []

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        if "status=W" in path:
            name = "waivers.html"
        elif "eteam=" not in path:
            name = "free_agents.html"  # it has a "Next 25" link, so the run reads all MARKET_PAGES pages
        else:
            name = "free_agents_phi_recent.html" if command.RECENT in path else "free_agents_phi.html"
        return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def options_of(fas, recent):
    """An Option for each free agent, with values from his projected points and his recent points."""
    points = {f.player.name: f.line.get("pts", 0.0) for f in recent}
    return [Option(f.player, f.line.get("pts", 0.0) / 10 - 1, recent_value=points.get(f.player.name)) for f in fas]


@pytest.mark.parametrize("settings", [{}, {"recent_skip_weight": 0.3}])
def test_one_parse_of_each_list_page_changes_no_plan(monkeypatch, tmp_path, settings):
    league = command.LeagueData(roster=[], adds=Adds(2, 5), week=Week(12, tuple(WEEK[:2])))
    found = {}
    runs = report_runs(monkeypatch)
    real_parse = command.parse
    for once in (True, False):
        inputs = []
        if not once:
            # The read before #93: each reader gets the HTML and parses it again.
            monkeypatch.setattr(command, "parse", lambda html: html)
        yahoo = run_command(
            monkeypatch,
            tmp_path / str(once),
            [],
            publish=False,
            league=league,
            yahoo=ListPages(),
            settings=settings,
            options=lambda fas, recent: (inputs.append((fas, recent)), options_of(fas, recent))[1],
        )
        found[once] = (runs[-1], inputs, yahoo.paths)
        monkeypatch.setattr(command, "parse", real_parse)
    run, inputs, paths = found[True]
    assert run.plan and run.plan.windows
    fas, recent = inputs[0]
    # With the recent view skipped (#90), the run reads only the projected view, and recent is empty.
    views = 1 if settings else 2
    assert fas and bool(recent) == (views == 2)
    assert len(paths) == views * (2 + command.MARKET_PAGES + 1)  # 2 team pages, the market and the waivers
    assert found[True] == found[False]


def run_command(
    monkeypatch,
    tmp_path,
    published,
    publish,
    options=None,
    rests=None,
    absences=(),
    extra_games=(),
    league=None,
    timed=True,
    pages=None,
    yahoo=None,
    settings=None,
    free_agents=None,
    market=None,
    today=None,
    cache=False,
    home=None,
):
    """Run plan.main() with no Yahoo session, no schedule file and site.publish replaced. Return the FakeLeague.

    The page, timings.csv and the page cache go in common.OUT. The autouse fixture of tests/conftest.py points it at
    tmp_path, so run_command patches no path. timed: the timed argument of plan.main().
    today: the date of the run (default: WEEK[0]). cache: the cache argument of plan.main(). The default is False,
    because the fake readers open the same path for each page, and a cache would give the second page.
    pages: the pages that each fake reader opens, by "league", "trends" or (reader, view). The readers are "team",
    "market" and "waiver". None: no reader opens a page.

    rests: the name keys of the rest list. With rests, [adds] rest_chance is 0.5.
    extra_games: (day, team) for each more game of the schedule, for example a game next week.
    league: the LeagueData that read_league() gives. None: week 12 (Mon and Tue), 4 of 5 adds used.
    yahoo: a fake League with the HTML of the list pages. The run then uses the real readers of the lists, and options
    is a function of the free agents and the recent free agents. None: a FakeLeague and fake readers of the lists.
    settings: more [adds] settings, for example {"recent_skip_weight": 0.3}.
    free_agents: {view: FreeAgents} that the fake team reader gives. The run then values them with the real
    value_options() and a scale of pts only, and the market and waiver readers give no free agents.
    market: the MarketRead that the fake market reader gives. None: no market free agents.
    home: the build_home() of the run (adds/home.py). None: a function that makes no home page.
    """
    lists = yahoo is None
    yahoo = yahoo or FakeLeague()
    pages = pages or {}

    @contextmanager
    def no_yahoo(league, wait_seconds):
        yield yahoo

    def reader(name, result):
        """A fake reader that opens the pages of name (and of its view) and gives result."""

        def read(league, *args, **kw):
            view = command.RECENT if command.RECENT in (*args, *kw.values()) else command.PROJECTED
            key, path = ((name, view), f"{name} {view}") if name in ("team", "market", "waiver") else (name, name)
            for _ in range(pages.get(key, 0)):
                league.get(path)
            if isinstance(result, dict):
                return list(result.get(view, ()))
            return result() if callable(result) else result

        return read

    import pandas as pd

    games = [(WEEK[0], "PHI"), (WEEK[0], "BOS"), (WEEK[1], "PHI"), *extra_games]
    sched = pd.DataFrame({"date": [str(d) for d, _ in games], "team": [t for _, t in games]})
    cfg = {
        "league": {"slots": ["PG", "SG", "SF", "PF", "C"], "roster_spots": 10},
        "adds": {"league": 1, "team": 1, **({"rest_chance": 0.5} if rests else {}), **(settings or {})},
        "weights": {"pts": 1.0},
    }
    monkeypatch.setattr(command, "read_rest_names", lambda cfg: set(rests or ()))
    monkeypatch.setattr(command, "load_config", lambda: cfg)
    monkeypatch.setattr(command, "read_schedule", lambda: sched)
    monkeypatch.setattr(command, "open_league", no_yahoo)
    league = league or command.LeagueData(roster=[], adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2])))
    monkeypatch.setattr(command, "read_league", reader("league", league))
    monkeypatch.setattr(command, "season_values", lambda cfg: {})
    monkeypatch.setattr(command, "stream_spots", lambda roster, cfg, values=None: [StreamSpot()])
    if lists:
        monkeypatch.setattr(command, "read_team_free_agents", reader("team", free_agents or list))
        monkeypatch.setattr(command, "read_market_free_agents", market_reader(pages, market))
        monkeypatch.setattr(command, "read_waiver_list", reader("waiver", list))
    monkeypatch.setattr(command, "read_week_trends", reader("trends", dict))
    monkeypatch.setattr(command, "read_roles", lambda players, cfg, today: {})
    options = options or [option("Phi One", "PHI", 0.3)]
    if free_agents is None:
        monkeypatch.setattr(
            command,
            "value_options",
            lambda fas, cfg, recent=(), matchup_cfg=None, scale=None: (
                options(fas, recent) if callable(options) else options
            ),
        )
    scale = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"]) if free_agents is not None else None
    monkeypatch.setattr(command, "projection_scale", lambda cfg: scale)
    monkeypatch.setattr(command, "empty_slot_value", lambda cfg, scale=None: -10.0)
    monkeypatch.setattr(command, "read_absences", lambda today, cfg: list(absences))
    monkeypatch.setattr(command, "build_home", home or (lambda *args: None))
    # A home page goes last in the record of the publish.
    monkeypatch.setattr(
        command.site, "publish", lambda *a, home=None: published.append(a if home is None else (*a, home))
    )
    command.main(today=today or WEEK[0], publish=publish, timed=timed, cache=cache)
    return yahoo


def market_reader(pages, result=None):
    """A fake read_market_free_agents(). It opens the market pages of pages (see run_command()).

    Page by page, it opens the projected page, then the recent page if the run reads the recent view.
    result: the MarketRead that it gives. None: a MarketRead with no free agents.
    """

    def read(league, recent=True, *args, **kw):
        projected, recent_pages = pages.get(("market", command.PROJECTED), 0), pages.get(("market", command.RECENT), 0)
        for n in range(max(projected, recent_pages if recent else 0)):
            if n < projected:
                league.get(f"market {command.PROJECTED}")
            if recent and n < recent_pages:
                league.get(f"market {command.RECENT}")
        return result or command.MarketRead([], [], max(projected, 1), "end")

    return read


class FakeLeague:
    """The part of session.League that the timers use: get() counts the pages, as League.get() does."""

    def __init__(self, html=""):
        self.pages, self.paths, self.html = 0, [], html

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        return self.html


# The recent view skip (#90). The schedule of run_command() gives PHI 1 game from 14 days ago to today (Mon),
# so the largest possible w is 1 / 14.
SKIP = {"recent_skip_weight": 0.3}
# One page of PHI free agents with no next page. The real readers read it for each list and each view.
PHI_PAGE = (Path(__file__).parent / "fixtures" / "free_agents_phi.html").read_text(encoding="utf-8")


def test_below_the_setting_the_run_reads_no_page_of_the_recent_view(monkeypatch, tmp_path):
    yahoo = run_command(monkeypatch, tmp_path, [], publish=False, settings=SKIP, yahoo=FakeLeague(PHI_PAGE))
    assert any(f"stat1={command.PROJECTED}" in path for path in yahoo.paths)
    assert not [path for path in yahoo.paths if f"stat1={command.RECENT}" in path]


@pytest.mark.parametrize("weight", [0.0, 1 / 14])
def test_at_or_above_the_setting_the_run_reads_both_views(monkeypatch, tmp_path, weight):
    yahoo = run_command(
        monkeypatch, tmp_path, [], publish=False, settings={"recent_skip_weight": weight}, yahoo=FakeLeague(PHI_PAGE)
    )
    projected = [path for path in yahoo.paths if f"stat1={command.PROJECTED}" in path]
    recent = [path for path in yahoo.paths if f"stat1={command.RECENT}" in path]
    assert len(projected) == 4  # the lists of PHI and BOS, the market list and the waiver list
    assert recent == [path.replace(command.PROJECTED, command.RECENT) for path in projected]


def _free_agents():
    """FreeAgents of PHI and BOS in the projected view and in the recent view, each recent row with games."""
    names = [("Phi Big", "PHI", ("C",), 18.0), ("Phi Wing", "PHI", ("SF",), 12.0), ("Bos Guard", "BOS", ("PG",), 15.0)]
    projected = [FreeAgent(Player(n, t, pos), 3, {"pts": pts}) for n, t, pos, pts in names]
    recent = [FreeAgent(Player(n, t, pos), 4, {"pts": 30.0 - pts}) for n, t, pos, pts in names]
    return projected, recent


def _plans(monkeypatch, tmp_path, recent, settings):
    """The PlanningRun of one run with the free agents of _free_agents() and the recent FreeAgents recent."""
    runs = report_runs(monkeypatch)
    projected, _ = _free_agents()
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=settings,
        free_agents={command.PROJECTED: projected, command.RECENT: recent},
    )
    return runs[0]


def test_the_plans_with_the_recent_view_skipped_are_the_plans_with_recent_weight_0(monkeypatch, tmp_path):
    _, recent = _free_agents()
    skip = _plans(monkeypatch, tmp_path / "skip", recent, SKIP)
    zero = _plans(monkeypatch, tmp_path / "zero", [replace(f, games=0) for f in recent], {"recent_skip_weight": 0.0})
    assert skip.recent_skip and zero.recent_skip is None
    assert skip.plan is not None and skip.plan.windows
    assert skip.rows  # the best plans for one roster spot
    # The schedule plan, the aggressive plan, the best plans for one roster spot and the options are equal.
    # The settings and the skip line are different.
    assert replace(skip, cfg=None, recent_skip=None) == replace(zero, cfg=None)
    # Without the skip, the recent lines of the test data move the values. So the test can see a difference.
    read = _plans(monkeypatch, tmp_path / "read", recent, {"recent_skip_weight": 0.0})
    assert [o.value for o in read.options] != [o.value for o in skip.options]


@pytest.mark.parametrize("settings", [{}, SKIP])
def test_the_page_and_the_terminal_show_the_market_read(monkeypatch, tmp_path, capsys, settings):
    # The fake market read of run_command() reads 2 pages, and page 2 is the last page of the list.
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=settings,
        pages={("market", command.PROJECTED): 2, ("market", command.RECENT): 2},
    )
    line = "Market: 2 of 3 pages. Page 2 was the last page of the list."
    html = page.page_path().read_text(encoding="utf-8")
    assert line in text(run_time(html))  # in the Run time section, not above the free-agent table (#118)
    assert line not in text(html.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    assert line in capsys.readouterr().out


def test_the_market_free_agents_of_each_view_reach_the_free_agent_lists(monkeypatch, tmp_path):
    projected = FreeAgent(Player("Market One", "PHI", ("SF",)), 3, {"pts": 14.0})
    recent = FreeAgent(Player("Market One", "PHI", ("SF",)), 5, {"pts": 22.0})
    inputs = []
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        market=command.MarketRead([projected], [recent], 1, "end"),
        options=lambda fas, rec: (inputs.append((list(fas), list(rec))), options_of(fas, rec))[1],
    )
    # The last call of value_options() gives the options of the plans: the free agents of each view.
    assert inputs[-1] == ([projected], [recent])


def test_the_page_and_the_terminal_say_that_the_run_skipped_the_recent_view(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=SKIP,
        free_agents={command.PROJECTED: projected, command.RECENT: recent},
    )
    html = page.page_path().read_text(encoding="utf-8")
    above = text(html.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    # Above the free-agent table: one short sentence. The full line is in the Run time section (#118).
    assert page.SKIP_NOTE in above and SKIP_LINE not in above
    assert SKIP_LINE in text(run_time(html))
    assert SKIP_LINE in capsys.readouterr().out


def test_a_run_with_the_recent_view_has_no_skip_line(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch, tmp_path, [], publish=False, free_agents={command.PROJECTED: projected, command.RECENT: recent}
    )
    html = page.page_path().read_text(encoding="utf-8")
    assert "<h2>Free agents</h2>" in html
    assert "skipped the recent view" not in text(html)
    assert 'class="skip"' not in html
    assert "skipped the recent view" not in capsys.readouterr().out


# The same-day cache of Yahoo pages (#91). BOTH: the run reads both views (no skip).
BOTH = {"recent_skip_weight": 0.0}
# The recent view of PHI with the Q players marked O.
PHI_RECENT_OUT = (
    (Path(__file__).parent / "fixtures" / "free_agents_phi_recent.html")
    .read_text(encoding="utf-8")
    .replace('title="Questionable">Q<', 'title="Out">O<')
)


class RecentViewPages(FakeLeague):
    """A fake League: the recent view gives recent_html, all other pages PHI_PAGE. No page has a next page."""

    def __init__(self, recent_html=PHI_PAGE):
        super().__init__(PHI_PAGE)
        self.recent_html = recent_html

    def get(self, path):
        html = super().get(path)
        return self.recent_html if command.RECENT in path else html


def _recent_lists(paths):
    """The paths of the team-filtered lists and the market pages in the recent view (not the waiver list)."""
    return [p for p in paths if f"stat1={command.RECENT}" in p and "status=W" not in p]


def test_a_second_run_on_the_same_day_reads_the_recent_view_from_the_cache(monkeypatch, tmp_path, capsys):
    first = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    assert len(_recent_lists(first.paths)) == 3  # PHI, BOS and the market page
    assert "from the cache" not in capsys.readouterr().out
    assert 'id="cache-read"' not in page.page_path().read_text(encoding="utf-8")
    second = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    assert _recent_lists(second.paths) == []
    # The run never takes the league pages, the projected view or the waiver list from the cache.
    assert second.paths == [p for p in first.paths if p not in _recent_lists(first.paths)]
    assert [p for p in second.paths if "status=W" in p and command.RECENT in p]
    _, rows = timing_rows(tmp_path)
    recent = [r["pages"] for r in rows if r["step"] == "Yahoo reads: recent pass"]
    assert recent == ["2", "0"]  # the page count counts only the pages from Yahoo
    line = re.search(r"The recent view: 3 pages from the cache of \d{4}-\d\d-\d\d \d\d:\d\d\.", capsys.readouterr().out)
    assert line
    html = page.page_path().read_text(encoding="utf-8")
    assert f'<p class="legend" id="cache-read">{line.group(0)}</p>' in run_time(html)


def test_a_run_on_the_next_day_reads_the_recent_view_from_yahoo(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    tuesday = run_command(
        monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True, today=WEEK[1]
    )
    projected = [p for p in tuesday.paths if f"stat1={command.PROJECTED}" in p and "status=W" not in p]
    assert projected and _recent_lists(tuesday.paths) == [
        p.replace(command.PROJECTED, command.RECENT) for p in projected
    ]
    assert [d.name for d in (page_cache.cache_dir() / "day").iterdir()] == [f"{WEEK[1]:%Y-%m-%d}"]


def test_no_cache_reads_each_page_from_yahoo(monkeypatch, tmp_path, capsys):
    first = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    bypass = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=False)
    assert bypass.paths == first.paths
    assert "from the cache" not in capsys.readouterr().out


def test_the_status_comes_from_the_projected_view_of_this_run(monkeypatch, tmp_path):
    import pandas as pd

    from fantasyhoops.adds.blend import blended_options

    scale, cfg = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"]), {"weights": {"pts": 1.0}}
    recents = []

    def options(fas, recent):
        recents.append(recent)
        return blended_options(fas, recent, scale, cfg)

    runs = report_runs(monkeypatch)
    # The first run caches a recent view in which the Q players are O.
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=BOTH,
        yahoo=RecentViewPages(PHI_RECENT_OUT),
        cache=True,
        options=options,
    )
    second = run_command(
        monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True, options=options
    )
    assert _recent_lists(second.paths) == []
    cached = {f.player.status for f in recents[-1]}
    assert "O" in cached and "Q" not in cached  # the recent view came from the cache
    statuses = {o.player.status for o in runs[-1].options}
    assert "Q" in statuses and "O" not in statuses


def report_runs(monkeypatch):
    """Record the PlanningRun of each print_report() call of plan.main(). Give the list of the runs."""
    runs, real = [], command.print_report
    monkeypatch.setattr(command, "print_report", lambda run: (runs.append(run), real(run))[1])
    return runs


def test_the_terminal_report_is_the_terminal_report_before_the_planning_run(monkeypatch, tmp_path, capsys):
    """#128: fixtures/terminal_before_128.txt is the terminal output of this run before the PlanningRun. <page>
    stands for the path of the page. The run has no step times, because their seconds change from run to run."""
    roster = [Player("Flag Guy", "PHI", ("PG",), status="Q"), Player("Hurt Guy", "BOS", ("C",), status="O")]
    league = command.LeagueData(roster=roster, adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2])))
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0, ("PG",)), claim]
    absent = [Absence("Star Wing", "PHI", WEEK[0] - timedelta(days=2), 1, ("SF", "PF"))]
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        options=options,
        absences=absent,
        rests={"phi weak"},
        league=league,
        timed=False,
        settings={"core": []},
        pages={("market", command.PROJECTED): 2, ("market", command.RECENT): 2},
    )
    out = capsys.readouterr().out.replace(str(page.page_path()), "<page>")
    before = (Path(__file__).parent / "fixtures" / "terminal_before_128.txt").read_text(encoding="utf-8")
    assert out == before
    # The report has each section that the fixture names.
    for head in ("Waiver players", "Role up:", "Aggressive plan:", "Comparison:", "Contingency plans:"):
        assert head in out
