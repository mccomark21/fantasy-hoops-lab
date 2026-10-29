from datetime import date
from pathlib import Path

from fantasyhoops.adds.cache import ROSTERED, PageCache
from fantasyhoops.adds.lists import PROJECTED
from fantasyhoops.trade.deadline import SETTINGS_PATH
from fantasyhoops.trade.reads import read_trade_inputs, report

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 28)
OWN_TEAM = 10


class Yahoo:
    """A fake session.League: get() gives the fixture page of the path and keeps each path."""

    def __init__(self, settings=None):
        self.paths = []
        self.settings = settings

    def get(self, path):
        self.paths.append(path)
        if path == SETTINGS_PATH:
            return self.settings or (FIXTURES / "league_settings.html").read_text(encoding="utf-8")
        view = "projected" if f"stat1={PROJECTED}" in path else "recent"
        page = int(path.rsplit("count=", 1)[1]) // 25 + 1
        return (FIXTURES / f"rostered_{view}_{page}.html").read_text(encoding="utf-8")


def test_a_second_read_on_the_same_day_uses_the_cache_and_no_cache_reads_again(tmp_path):
    yahoo = Yahoo()
    first = read_trade_inputs(PageCache(TODAY, folder=tmp_path), yahoo, OWN_TEAM, False, TODAY)
    assert first.deadline == date(2027, 2, 4)
    assert len(yahoo.paths) == 5  # 2 pages of each view and the settings page
    second_cache = PageCache(TODAY, folder=tmp_path)
    second = read_trade_inputs(second_cache, yahoo, OWN_TEAM, False, TODAY)
    assert len(yahoo.paths) == 5  # all pages came from the cache
    assert second_cache.hits[ROSTERED] == 5
    assert second == first
    bypass = PageCache(TODAY, use=False, folder=tmp_path)
    read_trade_inputs(bypass, yahoo, OWN_TEAM, False, TODAY)
    assert len(yahoo.paths) == 10  # --no-cache reads each page again
    assert bypass.hits[ROSTERED] == 0


def test_a_missing_deadline_does_not_stop_the_read_and_names_the_cache_folder(tmp_path):
    inputs = read_trade_inputs(
        PageCache(TODAY, folder=tmp_path), Yahoo(settings="<p>Settings</p>"), OWN_TEAM, False, TODAY
    )
    assert inputs.deadline is None
    assert 'no "Trade End Date"' in inputs.deadline_error
    assert str(tmp_path / ROSTERED / "2026-10-28") in inputs.deadline_error
    assert len(inputs.rostered.projected) == 5
    lines = report(inputs)
    assert lines[-1].startswith("Trade deadline: not found.")


def test_the_report_gives_the_pages_of_each_view_the_teams_and_the_team_links(tmp_path):
    inputs = read_trade_inputs(PageCache(TODAY, folder=tmp_path), Yahoo(), OWN_TEAM, False, TODAY)
    lines = report(inputs)
    assert lines[0] == "Projected view: 2 pages, 5 players of other teams."
    assert lines[1] == "Recent view: 2 pages, 5 players of other teams."
    assert lines[2] == "Teams: 4."
    assert "  Team 3: Dunk Dynasty (2 players)" in lines
    assert "Rows with no team link: 0. Each row has a team link with a team ID." in lines
    assert lines[-1] == "Trade deadline: 2027-02-04."
