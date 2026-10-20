from datetime import date
from pathlib import Path

import pytest

from fantasyhoops.adds.readers import Player, read_adds, read_roster, read_week

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_read_roster_gives_each_player_in_page_order():
    roster = read_roster(fixture("team.html"))
    # 10 players. The empty BN row and the empty IL row are not players.
    assert [p.name for p in roster] == [
        "Derrick White", "Cooper Flagg", "Matas Buzelis", "Brandon Miller", "Onyeka Okongwu", "Paolo Banchero",
        "Dejounte Murray", "Coby White", "Immanuel Quickley", "Rudy Gobert"]
    assert [p.slot for p in roster] == ["PG", "SG", "SF", "PF", "C", "Util", "BN", "BN", "BN", "BN"]


def test_read_roster_maps_the_team_and_splits_the_positions():
    roster = {p.name: p for p in read_roster(fixture("team.html"))}
    assert roster["Cooper Flagg"] == Player("Cooper Flagg", "DAL", ("SG", "SF", "PF"), "SG")
    # Yahoo NOP is ESPN NO.
    assert roster["Dejounte Murray"].team == "NO"


def test_read_roster_reads_the_status():
    roster = {p.name: p for p in read_roster(fixture("team.html"))}
    coby = roster["Coby White"]
    assert (coby.status, coby.status_name, coby.out, coby.on_il) == ("Q", "Questionable", False, False)
    assert roster["Derrick White"].status == ""


def test_read_roster_reads_an_out_player_on_il():
    # The status markup of an Out player is from the free-agent list of the same day.
    html = fixture("team.html").replace(
        '<tr data-pos="BN"><td class="player"><div class="ysf-player-name Nowrap Relative Lh-xs">\n'
        '<a class="Nowrap name F-link playernote" title="Rudy Gobert">Rudy Gobert</a>',
        '<tr data-pos="IL"><td class="player"><div class="ysf-player-name Nowrap Relative Lh-xs">\n'
        '<a class="Nowrap name F-link playernote" title="Rudy Gobert">Rudy Gobert</a>'
        '<span class="ysf-player-status Nowrap F-injury Fz-xxs"><span class="Pstart-sm" title="Out">O</span></span>')
    gobert = read_roster(html)[-1]
    assert (gobert.slot, gobert.status, gobert.out, gobert.on_il) == ("IL", "O", True, True)


def test_out_for_season_is_out():
    assert Player("A", "BOS", ("C",), status="OFS", status_name="Out for Season").out
    assert not Player("A", "BOS", ("C",), status="NA", status_name="Not Active").out


def test_read_roster_with_no_roster_table():
    with pytest.raises(ValueError, match="roster table"):
        read_roster("<html><body></body></html>")


def test_read_adds():
    adds = read_adds(fixture("team.html"))
    assert (adds.used, adds.limit, adds.left) == (0, 5, 5)


def test_read_week_gives_the_days_of_the_current_week():
    week = read_week(fixture("matchup.html"))
    assert week.number == 1
    # Week 1 is Tuesday to Sunday.
    assert (week.start, week.end, len(week.days)) == (date(2026, 10, 20), date(2026, 10, 25), 6)
