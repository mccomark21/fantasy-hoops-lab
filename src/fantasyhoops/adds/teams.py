"""Yahoo NBA team codes and the ESPN codes of data/schedule.csv (fetch/espn.py)."""

# The Yahoo codes that are not the same as the ESPN codes. The other 24 codes are the same in both sources.
_DIFFERENT = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}

YAHOO_TEAMS = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM",
    "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}


def espn_code(yahoo):
    """The ESPN code of a Yahoo team code, for example "SAS" -> "SA". An unknown code raises ValueError."""
    if yahoo not in YAHOO_TEAMS:
        raise ValueError(f"Unknown Yahoo team code: {yahoo!r}. Add it to adds/teams.py.")
    return _DIFFERENT.get(yahoo, yahoo)
