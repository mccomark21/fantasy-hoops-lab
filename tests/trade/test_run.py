import csv
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.adds.teams import YAHOO_TEAMS, espn_code
from fantasyhoops.core import common, home
from fantasyhoops.core import publish as site
from fantasyhoops.trade import run
from fantasyhoops.trade.deadline import SETTINGS_PATH
from fantasyhoops.trade.reads import TradeInputs
from fantasyhoops.trade.rostered import RosteredRead
from fantasyhoops.trade.suggest import Suggestion, Suggestions, TradePlayer

FIXTURES = Path(__file__).parent / "fixtures"
TEAM_PAGE = Path(__file__).parents[1] / "adds" / "fixtures" / "team.html"
NOW = datetime(2026, 10, 29, 9, 30)


class Yahoo:
    """A fake session.League: the team page of the adds tests, and the rostered pages and settings of #148."""

    def __init__(self, team):
        self.team, self.paths, self.pages = str(team), [], 0

    def get(self, path):
        self.paths.append(path)
        self.pages += 1
        if path == self.team:
            return TEAM_PAGE.read_text(encoding="utf-8")
        if path == SETTINGS_PATH:
            return (FIXTURES / "league_settings.html").read_text(encoding="utf-8")
        view = "projected" if "stat1=S_PS7" in path else "recent"
        page = int(path.rsplit("count=", 1)[1]) // 25 + 1
        return (FIXTURES / f"rostered_{view}_{page}.html").read_text(encoding="utf-8")


def playoff_days(cfg):
    teams = frozenset(espn_code(t) for t in YAHOO_TEAMS)
    out = []
    for week in cfg["playoffs"]["weeks"]:
        start = pd.Timestamp(week["start"]).date()
        out += [home.Day(start + timedelta(days=d), week["name"], False, teams) for d in range(7)]
    return out


@pytest.fixture
def fake_run(tmp_path, monkeypatch):
    """The run with fakes for Yahoo and the local files. Output goes to tmp_path. A publish fails the test."""
    cfg = common.load_config()
    yahoo = Yahoo(cfg["adds"]["team"])
    monkeypatch.setattr(common, "OUT", tmp_path)
    scale = pd.DataFrame({k: [0.0, 1.0] for k in cfg["weights"]}, index=["mean", "std"])
    local = run.LocalFiles(playoff_days(cfg), {}, {}, scale, False)
    monkeypatch.setattr(run, "read_local_files", lambda cfg, today: local)
    monkeypatch.setattr(run, "read_risk", lambda names, cfg: {})

    @contextmanager
    def league(*args):
        yield yahoo

    monkeypatch.setattr(run, "open_league", league)

    def no_publish(*args, **kwargs):
        raise AssertionError("The trade run must not publish.")

    monkeypatch.setattr(site, "publish", no_publish)
    return yahoo


def test_the_run_writes_the_trade_page_and_the_timings_and_does_not_publish(fake_run, tmp_path, capsys):
    run.main(["--no-publish"])
    out = capsys.readouterr().out
    page = tmp_path / "trade" / "index.html"
    assert page.exists()
    text = page.read_text(encoding="utf-8")
    assert "<h1>Trades</h1>" in text and "Starts count your 8 kept players." in text
    assert "Rosters: 5 pages read from Yahoo at" in text
    assert not (tmp_path / "home").exists()  # the run does not touch the home page
    assert f"Wrote the trade page: {page}" in out
    assert "Publish: skipped (--no-publish)." in out
    with open(tmp_path / "trade" / "timings.csv", encoding="utf-8") as f:
        steps = [r["step"] for r in csv.DictReader(f)]
    assert steps[:4] == [
        "Local files",
        "Yahoo reads",
        "Yahoo reads: team page",
        "Yahoo reads: rostered list and settings",
    ]
    assert steps[4:] == ["Score", "Page"]


def test_a_second_run_reads_the_rostered_pages_from_the_cache(fake_run, tmp_path):
    run.main(["--no-publish"])
    first = len(fake_run.paths)
    run.main(["--no-publish"])
    assert len(fake_run.paths) - first == 1  # only the team page
    assert "Rosters: 5 pages from the cache of " in (tmp_path / "trade" / "index.html").read_text(encoding="utf-8")


def test_without_the_schedule_the_run_stops_with_the_file_and_the_fetch_command(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA", tmp_path)
    with pytest.raises(SystemExit) as stop:
        run.schedule()
    assert "schedule.csv" in str(stop.value) and "python -m fantasyhoops.fetch.espn" in str(stop.value)


def test_the_read_time_line_names_the_cache_time_or_the_yahoo_time():
    cached = datetime(2026, 10, 28, 9, 14)
    assert run.rostered_line(16, 16, cached, NOW) == "Rosters: 16 pages from the cache of 2026-10-28 09:14."
    assert run.rostered_line(0, 16, None, NOW) == "Rosters: 16 pages read from Yahoo at 2026-10-29 09:30."
    assert run.rostered_line(1, 3, cached, NOW) == (
        "Rosters: 1 page from the cache of 2026-10-28 09:14, 2 pages read from Yahoo at 2026-10-29 09:30."
    )


class Read:
    def __init__(self, projected, recent=()):
        self.projected, self.recent = projected, list(recent)


def test_the_values_come_from_the_rostered_list_or_the_preseason_value_with_the_pre_mark():
    from fantasyhoops.adds.readers import Player
    from fantasyhoops.adds.drops import SeasonValue
    from fantasyhoops.trade.rostered import RosteredPlayer

    cfg = common.load_config()
    scale = pd.DataFrame({k: [0.0, 1.0] for k in cfg["weights"]}, index=["mean", "std"])
    line = {k: 1.0 for k in cfg["weights"]}
    mine_row = RosteredPlayer(Player("Own Guard", "ATL", ("PG",)), 3, line, 10, "Mine")
    their_row = RosteredPlayer(Player("Their Wing", "BOS", ("SF",)), 3, {}, 4, "Rivals")
    roster = [Player("Own Guard", "ATL", ("PG",), slot="PG"), Player("Own Hurt", "CHI", ("C",), slot="IL")]
    pre = {"own hurt": SeasonValue(100, -0.5), "their wing": SeasonValue(50, 0.7)}
    mine, others = run.trade_players(roster, Read([mine_row, their_row]), 10, {}, {}, pre, scale, cfg)
    assert [(p.name, p.mark, p.slot) for p in mine] == [("Own Guard", "", "PG"), ("Own Hurt", "pre", "IL")]
    assert mine[1].value == -0.5 and mine[0].value == pytest.approx(sum(cfg["weights"].values()))
    assert [(p.name, p.value, p.mark, p.team_name) for p in others] == [("Their Wing", 0.7, "pre", "Rivals")]


def test_the_best_line_and_the_warnings():
    give = TradePlayer("Give Guy", "ATL", ("PG",), value=1.0)
    get = TradePlayer("Get Guy", "BOS", ("PG",), value=1.05, team_name="Rivals")
    best = Suggestion(give, get, (8, 8, 8), (9, 8, 8), 1, 0, 0.05, -0.05)
    assert run.best_line(Suggestions((8, 8, 8), [], [best], 1, 1, 1)) == (
        "Best: give Give Guy, get Get Guy (Rivals): 24 -> 25 playoff starts (+1), value +0.05."
    )
    assert run.best_line(Suggestions((8, 8, 8), [], [], 1, 0, 0)) == "No trade raises your playoff starts."
    read = RosteredRead([], [], {}, ["Lost Row"], False)
    lines = run.warnings([TradePlayer("No Value", "ATL", ("C",))], TradeInputs(read, None, "No date."))
    assert lines == [
        "Warning: no trade deadline. No date.",
        "Warning: 1 rows of the rostered list have no team link.",
        "Warning: these players of your team have no value and are not in a trade: No Value.",
    ]


def test_the_trade_section_of_the_config_has_no_deadline():
    trade = common.load_config()["trade"]
    assert trade == {
        "untouchable": ["Cooper Flagg"],
        "value_band": [0.95, 1.10],
        "kept": 8,
        "per_player": 3,
        "rows": 20,
    }
