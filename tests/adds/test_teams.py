import pytest

from fantasyhoops.adds.teams import YAHOO_TEAMS, espn_code

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
