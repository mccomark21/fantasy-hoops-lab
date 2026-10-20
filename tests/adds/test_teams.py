import pytest

from fantasyhoops.adds.teams import YAHOO_IDS, YAHOO_TEAMS, espn_code, yahoo_id

# The 30 team codes of data/schedule.csv (fetch/espn.py), checked on 2026-10-20.
ESPN_TEAMS = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS", "HOU", "IND", "LAC", "LAL", "MEM",
    "MIA", "MIL", "MIN", "NO", "NY", "OKC", "ORL", "PHI", "PHX", "POR", "SA", "SAC", "TOR", "UTAH", "WSH",
}


def test_each_yahoo_code_maps_to_one_espn_code():
    assert {espn_code(t) for t in YAHOO_TEAMS} == ESPN_TEAMS


def test_codes_that_differ():
    assert [espn_code(t) for t in ["SAS", "NYK", "GSW", "NOP", "UTA", "WAS", "PHI"]] == \
        ["SA", "NY", "GS", "NO", "UTAH", "WSH", "PHI"]


def test_unknown_code():
    with pytest.raises(ValueError, match="Unknown Yahoo team code"):
        espn_code("SEA")


def test_yahoo_id_of_each_espn_code():
    assert set(YAHOO_IDS) == YAHOO_TEAMS
    assert sorted(yahoo_id(t) for t in ESPN_TEAMS) == list(range(1, 31))
    assert (yahoo_id("PHI"), yahoo_id("SA")) == (20, 24)
