"""Yahoo NBA team codes and the ESPN codes of data/schedule.csv (fetch/espn.py)."""

# The Yahoo codes that are not the same as the ESPN codes. The other 24 codes are the same in both sources.
_DIFFERENT = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}

YAHOO_TEAMS = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
    "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}


# The Yahoo team IDs of the team filter on the free-agent list (eteam=ET_<id>), from select#eteamselect.
YAHOO_IDS = {
    "ATL": 1, "BOS": 2, "NOP": 3, "CHI": 4, "CLE": 5, "DAL": 6, "DEN": 7, "DET": 8, "GSW": 9, "HOU": 10,
    "IND": 11, "LAC": 12, "LAL": 13, "MIA": 14, "MIL": 15, "MIN": 16, "BKN": 17, "NYK": 18, "ORL": 19, "PHI": 20,
    "PHX": 21, "POR": 22, "SAC": 23, "SAS": 24, "OKC": 25, "UTA": 26, "WAS": 27, "TOR": 28, "MEM": 29, "CHA": 30,
}


def espn_code(yahoo):
    """The ESPN code of a Yahoo team code, for example "SAS" -> "SA". An unknown code raises ValueError."""
    if yahoo not in YAHOO_TEAMS:
        raise ValueError(f"Unknown Yahoo team code: {yahoo!r}. Add it to adds/teams.py.")
    return _DIFFERENT.get(yahoo, yahoo)


def yahoo_id(espn):
    """The Yahoo team ID of an ESPN team code, for example "SA" -> 24. An unknown code raises ValueError."""
    for yahoo, team_id in YAHOO_IDS.items():
        if espn_code(yahoo) == espn:
            return team_id
    raise ValueError(f"Unknown ESPN team code: {espn!r}. Add it to adds/teams.py.")
