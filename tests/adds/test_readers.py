from datetime import date, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from fantasyhoops.adds.readers import (Player, has_next_page, read_adds, read_free_agents, read_roster,
                                       read_waiver_players, read_week)

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


def test_out_for_season_not_active_and_suspended_are_out():
    assert Player("A", "BOS", ("C",), status="OFS", status_name="Out for Season").out
    assert Player("A", "BOS", ("C",), status="NA", status_name="Not Active").out
    assert Player("A", "BOS", ("C",), status="SUSP", status_name="Suspended").out
    assert Player("A", "BOS", ("C",), status="X", status_name="Suspension").out
    assert not Player("A", "BOS", ("C",), status="Q", status_name="Questionable").out
    assert not Player("A", "BOS", ("C",), status="P", status_name="Probable").out


def test_read_free_agents_divides_the_totals_by_the_games():
    fas = {f.player.name: f for f in read_free_agents(fixture("free_agents.html"))}
    assert list(fas) == ["Khaman Maluach", "Kevin Porter Jr.", "Moussa Diabaté", "Jrue Holiday", "Jusuf Nurkić"]
    maluach = fas["Khaman Maluach"]
    assert (maluach.player.team, maluach.player.positions, maluach.games) == ("PHX", ("C",), 3.0)
    # The page shows 26.3 points, 25.8 rebounds and 1.3 3-pointers in 3 games.
    assert maluach.line == pytest.approx(
        {"pts": 26.3 / 3, "reb": 25.8 / 3, "ast": 2.5 / 3, "threes": 1.3 / 3, "blk": 4.8 / 3, "stl": 1.5 / 3})
    holiday = fas["Jrue Holiday"]
    assert (holiday.player.team, holiday.player.status, holiday.games) == ("POR", "Q", 2.0)


def test_read_free_agents_with_no_projection():
    fas = {f.player.name: f for f in read_free_agents(fixture("free_agents.html"))}
    # Yahoo shows "-" for a player with no projection, and 0.0 for a player who is out.
    porter, nurkic = fas["Kevin Porter Jr."], fas["Jusuf Nurkić"]
    assert (porter.games, porter.line, porter.player.status, porter.player.out) == (0, {}, "NA", True)
    assert (nurkic.games, nurkic.line, nurkic.player.out) == (0, {}, True)


def test_read_free_agents_keeps_the_full_name_and_maps_the_team():
    fas = read_free_agents(fixture("free_agents_phi.html"))
    assert [(f.player.name, f.player.team, f.player.positions) for f in fas] == [
        ("Anfernee Simons", "PHI", ("PG", "SG")), ("Adem Bona", "PHI", ("C",)),
        ("Kentavious Caldwell-Pope", "PHI", ("SG", "SF")), ("Rayan Rupert", "PHI", ("SG", "SF"))]


def test_read_recent_free_agents_with_no_games():
    # On 2026-10-20 no player had a game in the last 14 days: Yahoo shows "-" in all stat cells.
    fas = read_free_agents(fixture("free_agents_phi_recent.html"), totals=False)
    assert [(f.player.name, f.player.team, f.games, f.line) for f in fas] == [
        ("Anfernee Simons", "PHI", 0, {}), ("Adem Bona", "PHI", 0, {}),
        ("Kentavious Caldwell-Pope", "PHI", 0, {}), ("Rayan Rupert", "PHI", 0, {})]


def test_read_recent_free_agents_keeps_the_averages():
    # The recent view shows per-game averages, so the reader does not divide them by GP*. The numbers are made up.
    soup = BeautifulSoup(fixture("free_agents_phi_recent.html"), "html.parser")
    header = [th.get_text(strip=True) for th in soup.select("thead th")]
    cells = soup.select("tbody tr")[0].find_all("td")
    for name, text in {"GP*": "7", "PTS": "18.5", "REB": "4.0", "AST": "5.5", "3PTM": "2.5", "ST": "1.0",
                       "BLK": "0.5"}.items():
        cells[header.index(name)].div.string = text
    simons = read_free_agents(str(soup), totals=False)[0]
    assert (simons.games, simons.line) == (
        7, {"pts": 18.5, "reb": 4.0, "ast": 5.5, "threes": 2.5, "stl": 1.0, "blk": 0.5})


def test_read_free_agents_skips_players_on_waivers():
    html = fixture("free_agents_phi.html").replace("<td><div>FA</div></td>", "<td><div>W</div></td>", 1)
    assert "Anfernee Simons" not in [f.player.name for f in read_free_agents(html)]


def waiver_page(cell):
    """The PHI page with the Roster Status cell of Anfernee Simons changed to cell, for example "W (Oct 22)"."""
    return fixture("free_agents_phi.html").replace("<td><div>FA</div></td>", f"<td><div>{cell}</div></td>", 1)


def test_read_waiver_players_reads_the_clear_day():
    # The live list of 2026-10-21 showed "W (Oct 22)" in the Roster Status cell.
    was = read_waiver_players(waiver_page("W (Oct 22)"), today=date(2026, 10, 21))
    assert [(w.player.name, w.player.clear_day) for w in was] == [("Anfernee Simons", date(2026, 10, 22))]
    assert (was[0].player.team, was[0].games) == ("PHI", 4.0)


def test_read_free_agents_gives_no_clear_day():
    fas = read_free_agents(waiver_page("W (Oct 22)"))
    assert "Anfernee Simons" not in [f.player.name for f in fas]
    assert all(f.player.clear_day is None for f in fas)


def test_a_clear_day_in_january_is_in_the_next_year():
    was = read_waiver_players(waiver_page("W (Jan 2)"), today=date(2026, 12, 31))
    assert was[0].player.clear_day == date(2027, 1, 2)


def test_a_waiver_player_with_no_clear_day_is_skipped():
    assert read_waiver_players(waiver_page("W"), today=date(2026, 10, 21)) == []


def test_a_waiver_player_is_available_from_the_day_after_his_clear_day():
    wed = date(2026, 10, 21)
    claim = Player("A", "BOS", ("C",), clear_day=wed)
    assert [claim.available(wed - timedelta(days=1)), claim.available(wed), claim.available(wed + timedelta(days=1))]         == [False, False, True]
    assert Player("B", "BOS", ("C",)).available(wed)


def test_has_next_page():
    assert has_next_page(fixture("free_agents.html"))
    assert not has_next_page(fixture("free_agents_phi.html"))


def test_read_free_agents_with_no_table():
    with pytest.raises(ValueError, match="no player table"):
        read_free_agents("<html><body></body></html>")


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
