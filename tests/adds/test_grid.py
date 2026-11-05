from datetime import date, timedelta

from fantasyhoops.adds import grid
from fantasyhoops.adds.team_plan import UTIL
from fantasyhoops.adds.week_file import SavedAdd

MON = date(2026, 10, 26)
WEEK = [MON + timedelta(days=i) for i in range(7)]
FOUR = ("ATL", "CLE", "MEM", "SAC")
EIGHT = ("BKN", "BOS", "GS", "IND", "LAC", "LAL", "ORL", "TOR")
# #236: the Schedule Skyline (adds/skyline_plan.py) replaces the week grid. These tests keep the text and the link.
ADDS = {
    3: SavedAdd(2, WEEK[3], ("PF",), FOUR, (WEEK[3], WEEK[5])),
    4: SavedAdd(1, WEEK[6], (UTIL,), EIGHT, (WEEK[6],)),
}


def test_add_text_is_the_line_of_one_add_for_the_terminal():
    assert grid.add_text(ADDS[3], 6) == "Add 2, Thu 10/29: +PF ATL CLE MEM SAC. Starts Thu & Sat."
    assert grid.add_text(ADDS[4], 6) == "Add 1, Sun 11/1: +Util 8 teams. Starts Sun."


def test_fa_link_puts_the_filters_in_the_query_of_the_free_agents_page():
    link = grid.fa_link([WEEK[3], WEEK[5]], "PF", ("CHI",), "Add 2, Thu: +PF CHI")
    assert link == "../free-agents/?days=2026-10-29,2026-10-31&pos=PF&teams=CHI&from=Add+2,+Thu%3A+%2BPF+CHI"
