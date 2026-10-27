import pandas as pd

from fantasyhoops.core.identity import espn_keys, link_players, yahoo_keys

PLAYERS = pd.DataFrame(
    {
        "player_id": [1, 2, 3, 4, 5, 6],
        "name": ["Exact Match", "Luka Doncic", "Alexandre Sarr", "Free Agent", "Lu Dort", "Not Anywhere"],
    },
    index=[10, 11, 12, 13, 14, 15],
)

ROSTERS = pd.DataFrame(
    {
        "espn_name": ["Exact Match", "Luka Dončić", "Alex Sarr", "Lu Dort"],
        "team": ["BOS", "LAL", "WSH", "OKC"],
    }
)

YAHOO = pd.DataFrame(
    {
        "yahoo_id": [101, 102, 103, 105],
        "name": ["Exact Match", "Luka Dončić Jr.", "Alex Sarr", "Luguentz Dort"],
        "team": ["BOS", "LAL", "WAS", "OKC"],
        "positions": ["C", "PG,SG", "PF,C", "SG"],
        "status": ["", "", "INJ", ""],
        "yahoo_rank": [1, 2, 3, 5],
        "pct_drafted": [100, 100, 90, 50],
        "yahoo_cost": [50.0, 60.0, 10.0, 2.0],
        "yahoo_value": [40, 55, 8, 1],
        "adp": [1.5, 2.0, 30.0, 120.0],
    }
)

OVERRIDES = pd.DataFrame(
    {
        "player_id": ["3", "4", "5"],
        "name": ["Alexandre Sarr", "Free Agent", "Lu Dort"],
        "espn_name": ["Alex Sarr", "", ""],
        "yahoo_name": ["Alex Sarr", "", "Luguentz Dort"],
        "team": ["", "MIA", ""],
    }
)


def linked():
    return link_players(PLAYERS, ROSTERS, YAHOO, OVERRIDES)


def test_index_is_the_players_index():
    assert list(linked().index) == list(PLAYERS.index)


def test_exact_match():
    row = linked().loc[10]
    assert (row.team, row.yahoo_id, row.pos, row.yahoo_cost) == ("BOS", 101, "C", 50.0)


def test_accent_and_suffix_match():
    row = linked().loc[11]
    assert (row.team, row.yahoo_id, row.pos) == ("LAL", 102, "PG/SG")


def test_override_names():
    row = linked().loc[12]
    assert (row.team, row.yahoo_id, row.status) == ("WSH", 103, "INJ")


def test_override_team_without_names():
    row = linked().loc[13]
    assert row.team == "MIA"
    assert pd.isna(row.yahoo_id) and row.pos == "—"


def test_yahoo_only_override_keeps_espn_match():
    row = linked().loc[14]
    assert (row.team, row.yahoo_id) == ("OKC", 105)


def test_espn_and_yahoo_miss():
    row = linked().loc[15]
    assert pd.isna(row.team)
    assert pd.isna(row.yahoo_id) and row.pos == "—"


def test_espn_keys_map_each_yahoo_name_to_its_espn_name():
    # Lu Dort: the ESPN name is the projection name. Alex Sarr: the same name in both sources, so no row.
    assert espn_keys(OVERRIDES) == {"luguentz dort": "lu dort"}


def test_yahoo_keys_map_each_espn_name_to_its_yahoo_name():
    # The same override rows as espn_keys(), in the other direction.
    assert yahoo_keys(OVERRIDES) == {"lu dort": "luguentz dort"}
