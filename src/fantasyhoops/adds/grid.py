"""The text and the links of the team plan adds: the terminal line of an add and the Free agents link (#140, #165).

Until #236, this module drew the week grid of the plan page. The Schedule Skyline (adds/skyline_plan.py) replaces it.
- add_text() gives the line of one add for the terminal summary.
- fa_link() gives the link to the Free agents page with the filters of an add: days (the dates), pos (the slots,
  empty for Util), teams and from (the text of the line above the table). The script of that page (page.SCRIPT) sets
  the filters.
- CSS: the style of the filter line of the Free agents page.
The module writes no files.
"""

from urllib.parse import urlencode

TEAM_COUNT_AT = (
    6  # [adds] team_count_at if config.toml does not set it: from this number of teams, a line gives a count
)
FA_PAGE = "../free-agents/"  # the Free agents page, from the Adds plan page (#165)


def _days(days):
    """For example "Thu & Sat"."""
    names = [f"{d:%a}" for d in days]
    return " & ".join(filter(None, [", ".join(names[:-1]), names[-1]])) if names else ""


def team_count_at(cfg):
    """[adds] team_count_at of cfg, or TEAM_COUNT_AT."""
    return cfg.get("adds", {}).get("team_count_at", TEAM_COUNT_AT)


def slot_text(slots):
    """For example "SG/PF", or "Util" for any position."""
    return "/".join(slots)


def teams_text(teams, count_at):
    """For example "ATL CLE", or "8 teams" with count_at teams or more."""
    return f"{len(teams)} teams" if len(teams) >= count_at else " ".join(teams)


def add_text(add, count_at):
    """The terminal line of one SavedAdd, for example "Add 1, Thu 10/29: +SG/PF ATL CLE. Starts Thu & Sat.\""""
    return (
        f"Add {add.row}, {add.day:%a} {add.day.month}/{add.day.day}: +{slot_text(add.slots)} "
        f"{teams_text(add.teams, count_at)}. Starts {_days(add.starts)}."
    )


def fa_link(days=(), pos="", teams=(), source=""):
    """The link to the Free agents page with the filters of an add, for example
    "../free-agents/?days=2027-01-07,2027-01-09&pos=PF&teams=CHI&from=Add+2...". days: dates. pos: the slots,
    joined with ",", or "" for Util. teams: NBA team codes. source: the text of the line above the table."""
    query = {"days": ",".join(d.isoformat() for d in days), "pos": pos, "teams": ",".join(teams), "from": source}
    return f"{FA_PAGE}?{urlencode(query, safe=',')}"


CSS = """
.from { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; font-size: 13px; color: var(--fg);
        border: 1.5px solid var(--q); padding: 5px 10px; margin: 0 0 8px; }
.from[hidden] { display: none; }
.from a { font-weight: 700; }
#fa, #plan { scroll-margin-top: 8px; }
@media (max-width: 899px) { #fa, #plan { scroll-margin-top: 56px; } }
#team-chips button.chip { font-size: 12px; padding: 3px 6px; min-height: 28px; }
"""
