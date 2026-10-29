from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.adds.blend import blended_options
from fantasyhoops.adds.lists import PROJECTED, RECENT
from fantasyhoops.trade.rostered import (
    read_rostered,
    read_rostered_page,
    rostered_path,
    team_id,
    teams,
)

FIXTURES = Path(__file__).parent / "fixtures"
OWN_TEAM = 10
# A scale with mean 0 and std 1, so the value of a line is pts + reb (as in tests/adds/test_blend.py).
CFG = {"weights": {"pts": 1.0, "reb": 1.0}}
SCALE = pd.DataFrame({"pts": [0.0, 1.0], "reb": [0.0, 1.0]}, index=["mean", "std"])


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class Pages:
    """A fake session.League: get() gives the fixture page of the path and keeps each path."""

    def __init__(self):
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        view = "projected" if f"stat1={PROJECTED}" in path else "recent"
        page = int(path.rsplit("count=", 1)[1]) // 25 + 1
        return fixture(f"rostered_{view}_{page}.html")


def test_the_team_id_comes_from_the_team_link():
    assert team_id("/nba/22820/3") == 3
    assert team_id("https://basketball.fantasysports.yahoo.com/nba/22820/12?week=2") == 12
    assert team_id("/nba/22820/addplayerwatch?mid=10") is None
    assert team_id("https://sports.yahoo.com/nba/players/6412") is None
    assert team_id(None) is None


def test_a_page_keeps_the_players_of_other_teams_with_the_team_id_and_drops_your_team():
    page = read_rostered_page(fixture("rostered_projected_1.html"), OWN_TEAM)
    assert [(p.player.name, p.team_id, p.team_name) for p in page.players] == [
        ("Nikola Jokic", 3, "Dunk Dynasty"),
        ("Stephen Curry", 5, "Splash Bros Inc."),
        ("Victor Wembanyama", 7, "Glass Cleaners"),
    ]
    assert "Cooper Flagg" not in [p.player.name for p in page.players]  # your team (ID 10)
    assert page.no_link == []
    jokic, curry = page.players[0], page.players[1]
    assert jokic.player.team == "DEN" and jokic.player.positions == ("C",)
    assert curry.player.team == "GS" and curry.player.status == "Q"  # the ESPN code of GSW
    assert jokic.games == 3 and jokic.line["pts"] == pytest.approx(28.0)  # the totals of 7 days / GP*


def test_the_recent_view_gives_per_game_averages():
    page = read_rostered_page(fixture("rostered_recent_1.html"), OWN_TEAM, totals=False)
    assert page.players[0].line["pts"] == pytest.approx(29.4)


def test_the_team_id_comes_from_the_link_and_not_from_the_team_name():
    html = fixture("rostered_projected_1.html").replace(">Dunk Dynasty<", ">Splash Bros Inc.<")
    page = read_rostered_page(html, OWN_TEAM)
    assert [p.team_id for p in page.players] == [3, 5, 7]


def test_a_row_with_no_team_link_is_not_kept_and_is_named():
    html = fixture("rostered_projected_1.html").replace('<a href="/nba/22820/3">Dunk Dynasty</a>', "FA")
    page = read_rostered_page(html, OWN_TEAM)
    assert page.no_link == ["Nikola Jokic"]
    assert [p.player.name for p in page.players] == ["Stephen Curry", "Victor Wembanyama"]


def test_an_owner_column_also_holds_the_team_link():
    html = fixture("rostered_projected_1.html").replace("<th>Roster Status</th>", "<th>Owner</th>")
    assert [p.team_id for p in read_rostered_page(html, OWN_TEAM).players] == [3, 5, 7]


def test_a_page_with_no_player_table_or_no_stat_column_gives_a_clear_error():
    with pytest.raises(ValueError, match="no player table"):
        read_rostered_page("<html></html>", OWN_TEAM)
    html = fixture("rostered_projected_1.html").replace("<th>PTS</th>", "<th>Points</th>")
    with pytest.raises(ValueError, match="no column PTS"):
        read_rostered_page(html, OWN_TEAM)


def test_the_read_reads_all_pages_of_both_views():
    yahoo = Pages()
    read = read_rostered(yahoo, OWN_TEAM)
    assert read.pages == {PROJECTED: 2, RECENT: 2}
    assert sorted(yahoo.paths) == sorted(rostered_path(n, view) for n in (0, 25) for view in (PROJECTED, RECENT))
    names = ["Nikola Jokic", "Stephen Curry", "Victor Wembanyama", "Jalen Brunson", "Kevin Porter Jr."]
    assert [p.player.name for p in read.projected] == names
    assert [p.player.name for p in read.recent] == names
    assert not read.skipped_recent
    assert teams(read.projected) == {
        3: ("Dunk Dynasty", 2),
        5: ("Splash Bros Inc.", 1),
        7: ("Glass Cleaners", 1),
        12: ("Fast Break Fund", 1),
    }
    porter = read.projected[-1]
    assert porter.games == 0 and porter.line == {} and porter.player.out


def test_the_read_reads_only_the_projected_view_while_the_recent_view_is_skipped():
    yahoo = Pages()
    read = read_rostered(yahoo, OWN_TEAM, skip_recent=True)
    assert yahoo.paths == [rostered_path(0, PROJECTED), rostered_path(25, PROJECTED)]
    assert read.pages == {PROJECTED: 2}
    assert read.recent == [] and read.skipped_recent
    assert len(read.projected) == 5


def test_the_blend_takes_the_rostered_players_of_both_views():
    read = read_rostered(Pages(), OWN_TEAM)
    options = blended_options(read.projected, read.recent, SCALE, CFG)
    jokic = options[0]
    assert jokic.player.name == "Nikola Jokic"
    assert jokic.projected_value == pytest.approx(28.0 + 13.0)  # the projected line: pts + reb
    assert jokic.recent_value == pytest.approx(29.4 + 12.8)
