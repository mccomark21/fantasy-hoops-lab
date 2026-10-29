import csv
import json
import re
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from fantasyhoops.adds import cache as page_cache
from fantasyhoops.adds import lists, page, timing
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.readers import Adds, FreeAgent, Player, Week
from fantasyhoops.adds.drops import SeasonValue
from fantasyhoops.adds import week_file
from fantasyhoops.adds.role_up import Absence
from fantasyhoops.core import common, tokens
from fantasyhoops.core.common import name_key
from tests.adds.test_page import SKIP_LINE, WEEK, option, run_time, text

MON = date(2027, 1, 4)


def test_the_command_shows_the_waiver_players_on_the_page(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue. The waiver player clears on Mon, so the plan adds him on Tue. The DEN free agent has no
    # game. He is the replacement free agent (value 0.1), so the market value of the waiver player is +0.20.
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    runs = report_runs(monkeypatch)
    run_command(monkeypatch, tmp_path, [], publish=False, options=[claim, option("Den Guy", "DEN", 0.1)])
    assert "PHI Phi Claim W PHI · SF Mon 1/4 Tue 1/5 +0.20" in text(page.free_agents_path().read_text(encoding="utf-8"))
    # #140: the team plan uses no free agent. It recommends PHI, the team of the waiver player.
    assert [a.teams for a in runs[0].plan.adds] == [("PHI",)]
    assert "Waiver players" not in capsys.readouterr().out  # #130: the page shows them, the terminal does not
    assert lists.free_agent_path(None, 25, status="W").startswith("players?status=W&")


def test_the_command_writes_the_page_and_publishes_it(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=True)
    path, free_agents = page.page_path(), page.free_agents_path()
    # #165: one publish puts the plan page at /adds/ and the Free agents page at /free-agents/.
    assert published == [(command.ROOT, "adds", path, {"free-agents": free_agents})]
    out = capsys.readouterr().out
    assert f"Wrote the plan page: {path}" in out
    assert "<h1>Free agents</h1>" in free_agents.read_text(encoding="utf-8")
    assert command.URL in out and command.URL.endswith("/adds/")
    assert "+Util PHI" in text(path.read_text(encoding="utf-8"))
    assert out.splitlines() == [
        "",
        f"Wrote the plan page: {path}",
        f"Wrote the Free agents page: {free_agents}",
        "Team plan: Add 1, Mon 1/4: +Util PHI. Starts Mon & Tue.",
        f"Published the plan page to {command.URL}. GitHub can take a few minutes to show the new page.",
    ]
    assert (path.parent / "fonts" / "archivo-latin.woff2").read_bytes() == tokens.FONT.read_bytes()
    assert (path.parent / "fonts" / "OFL.txt").read_bytes() == tokens.LICENSE.read_bytes()


def test_the_page_shows_the_team_plan_and_no_player_plan(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue, BOS plays Mon. #140: the plan names the team PHI, not a player.
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0)]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options)
    out = capsys.readouterr().out
    html = page.page_path().read_text(encoding="utf-8")
    shown = text(html)
    for output in (out, shown):
        assert "Best plans for one roster spot" not in output and "Contingency" not in output
        assert "Aggressive" not in output and "Schedule plan" not in output
    assert '<section id="plan"><h2>Team plan</h2>' in html and "+Util PHI" in shown
    assert "?days=2027-01-04,2027-01-05&amp;pos=&amp;teams=PHI&amp;" in html


def test_the_command_does_not_publish_with_no_publish(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=False)
    assert published == []
    assert page.page_path().exists()
    assert "did not publish" in capsys.readouterr().out


def test_the_command_marks_a_second_night_of_a_player_on_the_rest_list(monkeypatch, tmp_path):
    # PHI plays Mon and Tue. Phi One is on the rest list, and [adds] rest_chance is 0.5.
    runs = report_runs(monkeypatch)
    run_command(monkeypatch, tmp_path, [], publish=False, rests={"phi one"})
    assert 'class="b2b"' in page.free_agents_path().read_text(encoding="utf-8")
    assert runs[0].options[0].rest_games == ((WEEK[1], 0.5),)
    # #140: the team plan names no player, so the rest list does not change it.
    assert runs[0].plan.started_games == 2


def test_the_command_marks_the_role_up_free_agents_on_the_page(monkeypatch, tmp_path):
    absent = [Absence("Star Wing", "PHI", WEEK[0] - timedelta(days=2), 1, ("SF", "PF"))]
    options = [option("Phi One", "PHI", 0.3), option("Phi Guard", "PHI", 0.2, ("PG",))]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options, absences=absent)
    assert "Star Wing is absent. Role up: Phi One (PHI)." in text(page.free_agents_path().read_text(encoding="utf-8"))


def test_the_command_marks_the_free_agents_who_play_on_an_open_day_early_next_week(monkeypatch, tmp_path, capsys):
    # The week is Mon and Tue. Next week starts on Wed, and PHI plays then. The roster is empty, so all slots are open.
    run_command(monkeypatch, tmp_path, [], publish=False, extra_games=[(WEEK[2], "PHI")])
    html = page.free_agents_path().read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Wed open"]
    assert "he has a game next Wednesday 1/6" in text(html)


def test_on_the_last_day_of_the_week_the_mark_checks_the_days_after_the_planned_week(monkeypatch, tmp_path):
    # read_league() moves data.week forward to Wed and Thu. So the mark checks Fri and Sat, not Wed.
    league = command.LeagueData(roster=[], adds=Adds(0, 5), week=Week(13, tuple(WEEK[2:4])), next_week=True)
    run_command(
        monkeypatch, tmp_path, [], publish=False, league=league, extra_games=[(WEEK[2], "PHI"), (WEEK[4], "PHI")]
    )
    html = page.free_agents_path().read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Fri open"]
    assert "next Friday 1/8" in text(html) and "next Saturday 1/9" in text(html)


STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
    "absence read",
    "value options",
    "team plan",
    "role read",
    "page write and publish",
]
SEARCH_STEPS = {"team plan"}
NO_READ_STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
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


def test_a_timed_run_writes_the_step_rows_and_prints_no_step_line(monkeypatch, tmp_path, capsys):
    # #130: the step times go only to timings.csv and to the Run time table of the page.
    run_command(monkeypatch, tmp_path, [], publish=False)
    assert [r["step"] for r in timing_rows(tmp_path)[1]] == ROWS
    out = capsys.readouterr().out
    assert "Step:" not in out and "timings.csv" not in out and " s, " not in out


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
        if r["step"] in SEARCH_STEPS:
            assert int(r["calls"]) >= int(r["states"]) >= 1
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
        ("team", lists.PROJECTED): 5,
        ("market", lists.PROJECTED): 3,
        ("waiver", lists.PROJECTED): 1,
        ("team", lists.RECENT): 4,
        ("market", lists.RECENT): 3,
        ("waiver", lists.RECENT): 1,
        "trends": 3,
    }
    yahoo = run_command(monkeypatch, tmp_path, [], publish=False, pages=pages)
    # The team lists in both views, each market page in both views, the waiver list in both views (#92).
    market = [f"market {lists.PROJECTED}", f"market {lists.RECENT}"] * 3
    assert (
        yahoo.paths
        == ["league"] * 2
        + [f"team {lists.PROJECTED}"] * 5
        + [f"team {lists.RECENT}"] * 4
        + market
        + [f"waiver {lists.PROJECTED}", f"waiver {lists.RECENT}"]
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
    assert "Yahoo reads" not in capsys.readouterr().out


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
    def stop(*args, **kw):
        raise KeyboardInterrupt  # the owner stops the run with Ctrl+C during the team plan

    monkeypatch.setattr(command, "team_plan", stop)
    with pytest.raises(KeyboardInterrupt):
        run_command(monkeypatch, tmp_path, [], publish=False)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == ROWS[: ROWS.index("team plan")]
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
    assert timed_run.plan.adds
    assert timed_run == untimed_run
    assert not (tmp_path / "False" / "adds" / "timings.csv").exists()
    assert "Step:" not in capsys.readouterr().out


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
            name = "free_agents_phi_recent.html" if lists.RECENT in path else "free_agents_phi.html"
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
    real_parse = lists.parse
    for once in (True, False):
        inputs = []
        if not once:
            # The read before #93: each reader gets the HTML and parses it again.
            monkeypatch.setattr(lists, "parse", lambda html: html)
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
        monkeypatch.setattr(lists, "parse", real_parse)
    run, inputs, paths = found[True]
    assert run.plan.adds
    fas, recent = inputs[0]
    # With the recent view skipped (#90), the run reads only the projected view, and recent is empty.
    views = 1 if settings else 2
    assert fas and bool(recent) == (views == 2)
    assert len(paths) == views * (2 + lists.MARKET_PAGES + 1)  # 2 team pages, the market and the waivers
    assert found[True] == found[False]


def test_a_timed_run_with_the_real_list_reads_has_the_sub_step_rows_of_89(monkeypatch, tmp_path):
    # #129: read_lists() times its own sub-steps. The rows keep the names, the order and the pages of #89.
    run_command(monkeypatch, tmp_path, [], publish=False, yahoo=ListPages(), settings=BOTH)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == ROWS
    found = {r["step"].removeprefix("Yahoo reads: "): r["pages"] for r in rows if r["step"].startswith("Yahoo reads")}
    assert found == {
        "Yahoo reads": "12",
        "browser start": "0",
        "league and matchup pages": "0",
        "projected pass": "2",
        "recent pass": "2",
        "market pages": "6",
        "waiver list": "2",
        "trends": "0",
    }


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
    values=None,
):
    """Run plan.main() with no Yahoo session, no schedule file and site.publish replaced. Return the FakeLeague.

    The page, timings.csv and the page cache go in common.OUT. The autouse fixture of tests/conftest.py points it at
    tmp_path, so run_command patches no path. timed: the timed argument of plan.main().
    today: the date of the run (default: WEEK[0]). cache: the cache argument of plan.main(). The default is False,
    because the fake readers open the same path for each page, and a cache would give the second page.
    pages: the pages that each fake reader opens, by "league", "trends" or (list, view). The lists are "team",
    "market" and "waiver" (lists_reader()). None: no reader opens a page.

    rests: the name keys of the rest list. With rests, [adds] rest_chance is 0.5.
    extra_games: (day, team) for each more game of the schedule, for example a game next week.
    league: the LeagueData that read_league() gives. None: week 12 (Mon and Tue), 4 of 5 adds used.
    yahoo: a fake League with the HTML of the list pages. The run then uses the real readers of the lists, and options
    is a function of the free agents and the recent free agents. None: a FakeLeague and a fake read_lists().
    settings: more [adds] settings, for example {"recent_skip_weight": 0.3}.
    free_agents: {view: FreeAgents} of the team lists of the fake read_lists(). The run then values them with the real
    value_options() and a scale of pts only, and the market and waiver lists give no free agents.
    market: the MarketRead of the fake read_lists(). None: no market free agents.
    home: the build_home() of the run (adds/home.py). None: a function that makes no home page.
    values: the season values of drops.season_values(). None: no player has a season value.
    """
    fake_lists = yahoo is None
    yahoo = yahoo or FakeLeague()
    pages = pages or {}

    @contextmanager
    def no_yahoo(league, wait_seconds):
        yield yahoo

    def reader(name, result):
        """A fake reader that opens the pages of name (and of its view) and gives result."""

        def read(league, *args, **kw):
            for _ in range(pages.get(name, 0)):
                league.get(name)
            return result() if callable(result) else result

        return read

    import pandas as pd

    games = [(WEEK[0], "PHI"), (WEEK[0], "BOS"), (WEEK[1], "PHI"), *extra_games]
    sched = pd.DataFrame({"date": [str(d) for d, _ in games], "team": [t for _, t in games]})
    cfg = {
        "league": {"slots": ["PG", "SG", "SF", "PF", "C"], "roster_spots": 10, "teams": 14},
        "adds": {"league": 1, "team": 1, **({"rest_chance": 0.5} if rests else {}), **(settings or {})},
        "weights": {"pts": 1.0},
    }
    monkeypatch.setattr(command, "read_rest_names", lambda cfg: set(rests or ()))
    monkeypatch.setattr(command, "load_config", lambda: cfg)
    monkeypatch.setattr(command, "read_schedule", lambda: sched)
    monkeypatch.setattr(command, "open_league", no_yahoo)
    league = league or command.LeagueData(roster=[], adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2])))
    monkeypatch.setattr(command, "read_league", reader("league", league))
    monkeypatch.setattr(command, "season_values", lambda cfg: values or {})
    monkeypatch.setattr(command, "stream_spots", lambda roster, cfg, values=None: [StreamSpot()])
    if fake_lists:
        monkeypatch.setattr(command, "read_lists", lists_reader(pages, free_agents or {}, market))
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
    monkeypatch.setattr(command, "read_absences", lambda today, cfg: list(absences))
    monkeypatch.setattr(command, "build_home", home or (lambda *args: None))

    # A home page goes after the pages in the record of the publish, then the more_tools of the publish (#165).
    def fake_publish(*a, home=None, cfg, more_tools=None):
        published.append((*a, *([home] if home is not None else []), *([more_tools] if more_tools else [])))

    monkeypatch.setattr(command.site, "publish", fake_publish)
    command.main(today=today or WEEK[0], publish=publish, timed=timed, cache=cache)
    return yahoo


def lists_reader(pages, free_agents, market=None):
    """A fake lists.read_lists(). It opens the pages of pages (see run_command()) in the read order of read_lists(),
    in the same sub-steps, and gives a FreeAgentLists.

    free_agents: {view: FreeAgents} of the team lists. market: the MarketRead of the market pages. None: a MarketRead
    with no free agents. The waiver list gives no free agents.
    """

    def open_pages(league, name, view, count=None):
        for _ in range(pages.get((name, view), 0) if count is None else count):
            league.get(f"{name} {view}")

    def read(yahoo, recent_yahoo, teams, today, values, skip, part):
        p, r = lists.PROJECTED, lists.RECENT
        team_fas, team_recent = list(free_agents.get(p, ())), [] if skip else list(free_agents.get(r, ()))
        with part("projected pass", yahoo):
            open_pages(yahoo, "team", p)
        with part("recent pass", yahoo):
            if not skip:
                open_pages(recent_yahoo, "team", r)
        with part("market pages", yahoo):
            # Page by page: the projected page, then the recent page if the run reads the recent view.
            projected, recent_pages = pages.get(("market", p), 0), 0 if skip else pages.get(("market", r), 0)
            for n in range(max(projected, recent_pages)):
                open_pages(yahoo, "market", p, int(n < projected))
                open_pages(yahoo, "market", r, int(n < recent_pages))
            read_market = market or lists.MarketRead([], [], max(projected, 1), "end")
        with part("waiver list", yahoo):
            open_pages(yahoo, "waiver", p)
            if not skip:
                open_pages(yahoo, "waiver", r)
        return lists.FreeAgentLists(
            free_agents=lists.unique_free_agents(team_fas + read_market.projected),
            recent=[] if skip else lists.unique_free_agents(team_recent + read_market.recent),
            market=read_market,
            market_line=lists.market_line(read_market),
        )

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
    assert any(f"stat1={lists.PROJECTED}" in path for path in yahoo.paths)
    assert not [path for path in yahoo.paths if f"stat1={lists.RECENT}" in path]


@pytest.mark.parametrize("weight", [0.0, 1 / 14])
def test_at_or_above_the_setting_the_run_reads_both_views(monkeypatch, tmp_path, weight):
    yahoo = run_command(
        monkeypatch, tmp_path, [], publish=False, settings={"recent_skip_weight": weight}, yahoo=FakeLeague(PHI_PAGE)
    )
    projected = [path for path in yahoo.paths if f"stat1={lists.PROJECTED}" in path]
    recent = [path for path in yahoo.paths if f"stat1={lists.RECENT}" in path]
    assert len(projected) == 4  # the lists of PHI and BOS, the market list and the waiver list
    assert recent == [path.replace(lists.PROJECTED, lists.RECENT) for path in projected]


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
        free_agents={lists.PROJECTED: projected, lists.RECENT: recent},
    )
    return runs[0]


def test_the_plans_with_the_recent_view_skipped_are_the_plans_with_recent_weight_0(monkeypatch, tmp_path):
    _, recent = _free_agents()
    skip = _plans(monkeypatch, tmp_path / "skip", recent, SKIP)
    zero = _plans(monkeypatch, tmp_path / "zero", [replace(f, games=0) for f in recent], {"recent_skip_weight": 0.0})
    assert skip.recent_skip and zero.recent_skip is None
    assert skip.plan.adds
    # The team plan, the warnings and the options are equal.
    # The settings and the skip line are different.
    assert replace(skip, cfg=None, recent_skip=None) == replace(zero, cfg=None)
    # Without the skip, the recent lines of the test data move the values. So the test can see a difference.
    read = _plans(monkeypatch, tmp_path / "read", recent, {"recent_skip_weight": 0.0})
    assert [o.value for o in read.options] != [o.value for o in skip.options]


@pytest.mark.parametrize("settings", [{}, SKIP])
def test_the_page_shows_the_market_read_and_the_terminal_does_not(monkeypatch, tmp_path, capsys, settings):
    # The fake read_lists() of run_command() reads 2 market pages, and page 2 is the last page of the list.
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=settings,
        pages={("market", lists.PROJECTED): 2, ("market", lists.RECENT): 2},
    )
    line = "Market: 2 of 3 pages. Page 2 was the last page of the list."
    html = page.page_path().read_text(encoding="utf-8")
    assert line in text(run_time(html))  # in the Run time section, not above the free-agent table (#118)
    free = page.free_agents_path().read_text(encoding="utf-8")
    assert line not in text(free.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    assert line not in capsys.readouterr().out  # #130


def test_the_market_free_agents_of_each_view_reach_the_free_agent_lists(monkeypatch, tmp_path):
    projected = FreeAgent(Player("Market One", "PHI", ("SF",)), 3, {"pts": 14.0})
    recent = FreeAgent(Player("Market One", "PHI", ("SF",)), 5, {"pts": 22.0})
    inputs = []
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        market=lists.MarketRead([projected], [recent], 1, "end"),
        options=lambda fas, rec: (inputs.append((list(fas), list(rec))), options_of(fas, rec))[1],
    )
    # The last call of value_options() gives the options of the plans: the free agents of each view.
    assert inputs[-1] == ([projected], [recent])


def test_the_page_says_that_the_run_skipped_the_recent_view(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=SKIP,
        free_agents={lists.PROJECTED: projected, lists.RECENT: recent},
    )
    html = page.page_path().read_text(encoding="utf-8")
    free = page.free_agents_path().read_text(encoding="utf-8")
    above = text(free.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    # Above the free-agent table: one short sentence. The full line is in the Run time section (#118).
    assert text(page.SKIP_NOTE) in above and SKIP_LINE not in above
    assert SKIP_LINE in text(run_time(html))
    assert SKIP_LINE not in capsys.readouterr().out  # #130


def test_a_run_with_the_recent_view_has_no_skip_line(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch, tmp_path, [], publish=False, free_agents={lists.PROJECTED: projected, lists.RECENT: recent}
    )
    html = page.page_path().read_text(encoding="utf-8") + page.free_agents_path().read_text(encoding="utf-8")
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
        return self.recent_html if lists.RECENT in path else html


def _recent_lists(paths):
    """The paths of the team-filtered lists and the market pages in the recent view (not the waiver list)."""
    return [p for p in paths if f"stat1={lists.RECENT}" in p and "status=W" not in p]


def test_a_second_run_on_the_same_day_reads_the_recent_view_from_the_cache(monkeypatch, tmp_path, capsys):
    first = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    assert len(_recent_lists(first.paths)) == 3  # PHI, BOS and the market page
    assert "from the cache" not in capsys.readouterr().out
    assert 'id="cache-read"' not in page.page_path().read_text(encoding="utf-8")
    second = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    assert _recent_lists(second.paths) == []
    # The run never takes the league pages, the projected view or the waiver list from the cache.
    assert second.paths == [p for p in first.paths if p not in _recent_lists(first.paths)]
    assert [p for p in second.paths if "status=W" in p and lists.RECENT in p]
    _, rows = timing_rows(tmp_path)
    recent = [r["pages"] for r in rows if r["step"] == "Yahoo reads: recent pass"]
    assert recent == ["2", "0"]  # the page count counts only the pages from Yahoo
    html = page.page_path().read_text(encoding="utf-8")
    line = (
        r'<p class="legend" id="cache-read">The recent view: 3 pages from the cache of \d{4}-\d\d-\d\d \d\d:\d\d\.</p>'
    )
    assert re.search(line, run_time(html))
    assert "from the cache" not in capsys.readouterr().out  # #130


def test_a_run_on_the_next_day_reads_the_recent_view_from_yahoo(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True)
    tuesday = run_command(
        monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=RecentViewPages(), cache=True, today=WEEK[1]
    )
    projected = [p for p in tuesday.paths if f"stat1={lists.PROJECTED}" in p and "status=W" not in p]
    assert projected and _recent_lists(tuesday.paths) == [p.replace(lists.PROJECTED, lists.RECENT) for p in projected]
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
    """Record the PlanningRun of each print_summary() call of plan.main(). Give the list of the runs."""
    runs, real = [], command.print_summary
    monkeypatch.setattr(command, "print_summary", lambda run: (runs.append(run), real(run))[1])
    return runs


def test_the_terminal_shows_only_the_page_path_the_team_plan_and_the_warnings(monkeypatch, tmp_path, capsys):
    """#130: a fixed run with each section of the page. The terminal prints the summary lines and no other line.
    <page> stands for the path of the page. #140: one line for each add of the team plan."""
    roster = [Player("Flag Guy", "PHI", ("PG",), status="Q"), Player("Hurt Guy", "BOS", ("C",), status="O")]
    league = command.LeagueData(roster=roster, adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2])))
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0, ("PG",)), claim]
    absent = [Absence("Star Wing", "PHI", WEEK[0] - timedelta(days=2), 1, ("SF", "PF"))]
    runs = report_runs(monkeypatch)
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        options=options,
        absences=absent,
        rests={"phi weak"},
        league=league,
        settings={"core": ["Flag Guy"]},
        values={name_key("Flag Guy"): SeasonValue(200, -7.0)},
        pages={("market", lists.PROJECTED): 2, ("market", lists.RECENT): 2},
    )
    (run,) = runs
    assert run.warnings and run.market
    out = capsys.readouterr().out.replace(str(page.page_path()), "<page>")
    out = out.replace(str(page.free_agents_path()), "<free agents>")
    assert out.splitlines() == [
        "",
        "Wrote the plan page: <page>",
        "Wrote the Free agents page: <free agents>",
        "Team plan: Add 1, Mon 1/4: +Util PHI. Starts Mon & Tue.",
        "The run did not publish the page (--no-publish).",
        *run.warnings,
    ]
    # The page still shows the sections that the terminal report showed before #130.
    html = text(page.page_path().read_text(encoding="utf-8") + page.free_agents_path().read_text(encoding="utf-8"))
    for line in (*run.warnings, run.market, "Star Wing is absent."):
        assert line in html


def test_each_run_writes_the_week_file_and_a_later_run_keeps_the_past_day(monkeypatch, tmp_path):
    # #140: the run of Mon recommends +Util PHI on Mon. The run of Tue keeps the Mon add, and the page shows it as past.
    league = command.LeagueData(roster=[], adds=Adds(3, 5), week=Week(12, tuple(WEEK[:2])))
    run_command(monkeypatch, tmp_path, [], publish=False, league=league)
    monday = week_file.read_record(WEEK[0])
    assert week_file.week_path(WEEK[0]) == common.OUT / "adds" / "week_plan_2027-01-04.json"
    assert monday.runs == (WEEK[0],)
    assert [(a.row, a.day, a.slots, a.teams) for a in monday.adds] == [(1, WEEK[0], ("Util",), ("PHI",))]
    run_command(monkeypatch, tmp_path, [], publish=False, league=league, today=WEEK[1])
    tuesday = week_file.read_record(WEEK[0])
    assert tuesday.runs == (WEEK[0], WEEK[1])
    assert tuesday.adds[0] == monday.adds[0]
    assert [a.day for a in tuesday.adds] == [WEEK[0], WEEK[1]]
    html = page.page_path().read_text(encoding="utf-8")
    assert '<td class="add past"><span class="addc was"' in html
    assert "No saved plan" not in html


def test_a_run_with_no_adds_left_writes_a_week_file_with_no_add(monkeypatch, tmp_path):
    league = command.LeagueData(roster=[], adds=Adds(5, 5), week=Week(12, tuple(WEEK[:2])))
    run_command(monkeypatch, tmp_path, [], publish=False, league=league, today=WEEK[1])
    record = week_file.read_record(WEEK[0])
    assert (record.runs, record.adds) == ((WEEK[1],), ())
    assert "No saved plan for Mon." in page.page_path().read_text(encoding="utf-8")


class TeamAndMatchup:
    """A fake session.League that gives the fixture team page with the team overview, and the matchup page."""

    def get(self, path):
        fixtures = Path(__file__).parent / "fixtures"
        if path.startswith("matchup"):
            return (fixtures / "matchup.html").read_text(encoding="utf-8")
        overview = (fixtures / "team_record.html").read_text(encoding="utf-8").split("<body>")[1].split("</body>")[0]
        return (fixtures / "team.html").read_text(encoding="utf-8").replace("<body>", "<body>" + overview)


def test_read_league_reads_the_record_from_the_team_page():
    cfg = {"adds": {"team": 10}}
    data = command.read_league(TeamAndMatchup(), cfg, date(2026, 10, 21))
    assert data.record == "4-2-1" and len(data.roster) == 10
