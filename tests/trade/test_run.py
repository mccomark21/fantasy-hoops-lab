import csv
import html
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.adds.session import PageNotReady, YahooBlocked
from fantasyhoops.adds.teams import YAHOO_TEAMS, espn_code
from fantasyhoops.core import common, roster as roster_page
from fantasyhoops.core import publish as site
from fantasyhoops.trade import run
from fantasyhoops.trade.deadline import SETTINGS_PATH
from fantasyhoops.trade.reads import TradeInputs
from fantasyhoops.trade.rostered import RosteredRead
from fantasyhoops.trade.suggest import Suggestion, Suggestions, TradePlayer, TradeSettings

FIXTURES = Path(__file__).parent / "fixtures"
TEAM_PAGE = Path(__file__).parents[1] / "adds" / "fixtures" / "team.html"
NOW = datetime(2026, 10, 29, 9, 30)


class Yahoo:
    """A fake session.League: the team page of the adds tests, and the rostered pages and settings of #148."""

    def __init__(self, team):
        self.team, self.paths, self.pages = str(team), [], 0
        self.settings = (FIXTURES / "league_settings.html").read_text(encoding="utf-8")
        self.error = None  # an error that each get() raises, for the tests of a failed Yahoo read

    def get(self, path):
        self.paths.append(path)
        self.pages += 1
        if self.error:
            raise self.error
        if path == self.team:
            return TEAM_PAGE.read_text(encoding="utf-8")
        if path == SETTINGS_PATH:
            return self.settings
        view = "projected" if "stat1=S_PS7" in path else "recent"
        page = int(path.rsplit("count=", 1)[1]) // 25 + 1
        return (FIXTURES / f"rostered_{view}_{page}.html").read_text(encoding="utf-8")


def playoff_days(cfg):
    teams = frozenset(espn_code(t) for t in YAHOO_TEAMS)
    out = []
    for week in cfg["playoffs"]["weeks"]:
        start = pd.Timestamp(week["start"]).date()
        out += [roster_page.Day(start + timedelta(days=d), week["name"], False, teams) for d in range(7)]
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
    assert not (tmp_path / "roster").exists()  # the run does not make the Roster page
    assert f"Wrote the trade page: {page}" in out
    assert "Publish: skipped (--no-publish)." in out
    with open(tmp_path / "trade" / "timings.csv", encoding="utf-8") as f:
        steps = [r["step"] for r in csv.DictReader(f)]
    assert steps[:5] == [
        "Local files",
        "Yahoo reads",
        "Yahoo reads: settings",
        "Yahoo reads: team page",
        "Yahoo reads: rostered list",
    ]
    assert steps[5:] == ["Score", "Page"]


def test_the_run_publishes_the_page_to_trade_keeps_the_other_pages_and_prints_the_url(
    fake_run, tmp_path, monkeypatch, capsys
):
    """#151, #172: python -m fantasyhoops.trade publishes /trade/. The publish keeps the other folders."""
    calls = []
    monkeypatch.setattr(site, "publish", lambda *args, **kwargs: calls.append((args, kwargs)))
    run.main([])
    ((args, kwargs),) = calls
    assert args == (common.ROOT, "trade", tmp_path / "trade" / "index.html")
    assert kwargs == {"cfg": kwargs["cfg"]}  # no more_tools: the run publishes only /trade/
    out = capsys.readouterr().out
    assert f"Published the trade page to {site.URL}trade/." in out


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


def test_a_name_of_the_offer_list_that_is_not_on_your_roster_gets_a_warning():
    settings = TradeSettings(frozenset(), (0.95, 1.10), 8, 3, 20, ("Here Guy", "Gone Guy"))
    read = RosteredRead([], [], {}, [], False)
    inputs = TradeInputs(read, date(2027, 3, 4), "")
    lines = run.warnings([TradePlayer("Here Guy", "ATL", ("C",), value=1.0)], inputs, (), settings)
    assert lines == ["Warning: these players of the [trade] offer list are not on your roster: Gone Guy."]


def test_the_trade_section_of_the_config_has_no_deadline():
    trade = common.load_config()["trade"]
    assert trade == {
        "untouchable": ["Cooper Flagg"],
        "offer": ["Rudy Gobert", "Matas Buzelis", "Coby White"],
        "value_band": [0.95, 1.10],
        "kept": 8,
        "per_player": 3,
        "rows": 20,
    }


def test_the_run_prints_the_offered_players_and_the_page_shows_them(fake_run, tmp_path, capsys, monkeypatch):
    cfg = common.load_config()
    cfg["trade"]["offer"] = ["Rudy Gobert", "Coby White", "Gone Guy"]
    monkeypatch.setattr(run, "load_config", lambda: cfg)
    run.main(["--no-publish"])
    out = capsys.readouterr().out
    text = (tmp_path / "trade" / "index.html").read_text(encoding="utf-8")
    assert "Offered: Coby White, Rudy Gobert (config [trade] offer)." in out
    assert '<div class="offer" id="offer"><p>Offered: Coby White, Rudy Gobert (config [trade] offer).</p>' in text
    line = "Warning: these players of the [trade] offer list are not on your roster: Gone Guy."
    assert line in out and f"<li>{html.escape(line)}</li>" in text


# The edge states of #153.

PAST = "<html><body><table><tr><td>Trade End Date:</td><td>Mon, Mar 2, 2026</td></tr></table></body></html>"
NO_DEADLINE = "<html><body><table><tr><td>Max Teams:</td><td>14</td></tr></table></body></html>"


def test_after_the_deadline_the_run_reads_no_roster_and_writes_and_publishes_the_deadline_page(
    fake_run, tmp_path, monkeypatch, capsys
):
    fake_run.settings = PAST
    calls = []
    monkeypatch.setattr(site, "publish", lambda *args, **kwargs: calls.append((args, kwargs)))
    run.main([])
    assert fake_run.paths == [SETTINGS_PATH]  # no team page and no rostered page
    text = (tmp_path / "trade" / "index.html").read_text(encoding="utf-8")
    line = "The trade deadline was Monday, March 2, 2026. Yahoo accepts no more trades this season."
    assert f'<div class="empty" id="deadline"><p>{line}</p></div>' in text
    assert "Suggested trades" not in text and 'id="builder"' not in text
    assert '<a href="../roster/">Roster</a>' in text  # the Roster link of the site menu stays
    ((args, kwargs),) = calls
    assert args[1] == "trade" and set(kwargs) == {"cfg"}
    out = capsys.readouterr().out
    assert line in out and f"Published the trade page to {site.URL}trade/." in out


def test_on_the_deadline_day_the_run_still_suggests_trades():
    today = datetime(2026, 3, 2).date()
    assert not run.deadline_passed(today, today)
    assert run.deadline_passed(today, today + timedelta(days=1))
    assert not run.deadline_passed(None, today)


def test_with_no_deadline_the_run_continues_and_the_page_and_the_terminal_show_the_warning(fake_run, tmp_path, capsys):
    fake_run.settings = NO_DEADLINE
    run.main(["--no-publish"])
    out = capsys.readouterr().out
    warning = [line for line in out.splitlines() if line.startswith("Warning: no trade deadline.")]
    assert len(warning) == 1 and 'no "Trade End Date"' in warning[0]
    text = (tmp_path / "trade" / "index.html").read_text(encoding="utf-8")
    assert '<ul class="warn" id="warnings"' in text
    assert "<li>Warning: no trade deadline. The league settings page has no &quot;Trade End Date&quot;." in text
    assert "<strong>Not found</strong>" in text and "Suggested trades" in text


def test_a_player_with_no_match_gets_a_warning_line_and_goes_last_in_the_lineup_order():
    from fantasyhoops.adds.drops import SeasonValue

    known = TradePlayer("Known Guy", "ATL", ("PG",), rank=40)
    lost = TradePlayer("Lost Guy", "BOS", ("PG",))
    ranks, risk, pre = {"known guy": 40}, {"known guy": 1}, {"known guy": SeasonValue(10, 0.5)}
    lines = run.missing_data([lost, known, lost], ranks, risk, pre)
    assert lines == [
        "Warning: these players have no rank and go last in the lineup order: Lost Guy.",
        "Warning: these players are not in the [risk] file and get rests_b2b 0: Lost Guy.",
        "Warning: these players are not in the projections file and have no Pre value: Lost Guy.",
    ]
    order = roster_page.rank_order([lost.roster_player(), known.roster_player()])
    assert [p.name for p in order] == ["Known Guy", "Lost Guy"]


def test_a_missing_data_line_with_many_players_gives_the_count_and_the_first_three_names():
    players = [TradePlayer(f"Lost {n}", "BOS", ("PG",)) for n in "ABCDEFGHIJK"]
    lines = run.missing_data(players, {}, {}, {})
    assert lines[0] == (
        "Warning: these players have no rank and go last in the lineup order: "
        "11 players, such as Lost A, Lost B and Lost C."
    )
    assert all("11 players, such as Lost A, Lost B and Lost C." in line for line in lines)


def test_a_missing_data_line_with_few_players_names_all_of_them():
    players = [TradePlayer(f"Lost {n}", "BOS", ("PG",)) for n in "ABC"]
    line = run.missing_data(players[:2], {}, {}, {})[0]
    assert line.endswith(": Lost A and Lost B.") and "such as" not in line
    line = run.missing_data(players, {}, {}, {})[0]
    assert line.endswith(": Lost A, Lost B and Lost C.") and "such as" not in line


def test_the_run_prints_the_missing_data_lines_and_the_page_lists_them(fake_run, tmp_path, capsys):
    run.main(["--no-publish"])  # the fake run has no ranks, no risk file and no projections file
    out = capsys.readouterr().out
    line = next(x for x in out.splitlines() if x.startswith("Warning: these players have no rank"))
    text = (tmp_path / "trade" / "index.html").read_text(encoding="utf-8")
    assert f"<li>{html.escape(line)}</li>" in text


def test_the_risk_read_leaves_out_the_names_that_are_not_in_the_risk_file(tmp_path, monkeypatch):
    (tmp_path / "risk.csv").write_text("name,team,inj_risk,rests_b2b\nRest Guy,ATL,low,1\n", encoding="utf-8")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr("fantasyhoops.draft.rankings.ROOT", tmp_path)
    assert run.read_risk(["Rest Guy", "Lost Guy"], {"risk": {"file": "risk.csv"}}) == {"rest guy": 1}


@pytest.mark.parametrize("error", [YahooBlocked("Yahoo blocked the session."), PageNotReady("No table.")])
def test_a_yahoo_read_failure_stops_the_run_with_the_error_and_no_publish(fake_run, tmp_path, error):
    fake_run.error = error  # fake_run fails the test on a publish
    with pytest.raises(SystemExit) as stop:
        run.main([])
    assert isinstance(stop.value, run.YahooReadFailed)
    assert str(error) in str(stop.value) and "The run did not publish." in str(stop.value)
    assert not (tmp_path / "trade" / "index.html").exists()


def test_a_sign_in_that_does_not_finish_stops_the_run_with_no_publish(fake_run, tmp_path):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    fake_run.error = PlaywrightTimeout("Timeout 600000ms exceeded.")
    with pytest.raises(run.YahooReadFailed, match="Timeout 600000ms exceeded"):
        run.main([])
    assert not (tmp_path / "trade" / "index.html").exists()
