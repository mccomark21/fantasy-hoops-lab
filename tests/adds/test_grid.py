import re
from dataclasses import replace
from datetime import date, timedelta

from fantasyhoops.adds import grid
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.planner import StreamSpot
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.adds.team_plan import UTIL, team_plan
from fantasyhoops.adds.week_file import SavedAdd, WeekRecord, assign_rows, merged

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2026, 10, 26)
WEEK = [MON + timedelta(days=i) for i in range(7)]
WED = WEEK[2]
SIX = ("ATL", "CLE", "MEM", "NO", "POR", "SAC")
FOUR = ("ATL", "CLE", "MEM", "SAC")
EIGHT = ("BKN", "BOS", "GS", "IND", "LAC", "LAL", "ORL", "TOR")
# The run of Wed: Mon and Tue are past. Row 1: the Mon add (past), +SG/PF from 6 teams on Thu, +Util from 8 teams
# on Sun. Row 2: the Tue add (past), +PF from 4 teams on Thu.
ADDS = (
    SavedAdd(1, WEEK[0], ("SG",), ("OKC",), (WEEK[0], WEEK[1])),
    SavedAdd(2, WEEK[1], ("PG", "SG"), ("POR", "SAC"), (WEEK[1],)),
    SavedAdd(1, WEEK[3], ("SG", "PF"), SIX, (WEEK[3], WEEK[5])),
    SavedAdd(2, WEEK[3], ("PF",), FOUR, (WEEK[3], WEEK[5])),
    SavedAdd(1, WEEK[6], (UTIL,), EIGHT, (WEEK[6],)),
)
GAMES = dict(zip(WEEK, (9, 4, 12, 3, 10, 7, 4)))


def run(record=WeekRecord(runs=(WEEK[0], WEEK[1], WED), adds=ADDS), today=WED, **fields):
    days = open_slots_by_day([], {d: set() for d in WEEK if d >= today}, SLOTS)
    data = command.LeagueData(roster=[], adds=Adds(2, 5), week=Week(44, tuple(WEEK)))
    base = command.PlanningRun(
        data=data, days=days, games={}, spots=[StreamSpot()], today=today, record=record, week_games=GAMES
    )
    return replace(base, **fields)


def section(**fields):
    return grid.plan_section(run(**fields))


def rows(html):
    """The cells of each body row: the row label, then one cell for each day."""
    body = re.search(r"<tbody>(.*)</tbody>", html, re.S).group(1)
    return [re.findall(r"<t[hd][ >].*?</t[hd]>", r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", body)]


def test_the_grid_has_a_column_for_each_day_of_the_week_and_the_rows_games_add_1_and_add_2():
    html = section()
    heads = re.findall(r'<th scope="col"[^>]*>(.*?)</th>', re.search(r"<thead>(.*?)</thead>", html).group(1))
    assert len(heads) == 8  # the row label column, then Mon to Sun
    assert [re.search(r'class="long">(\w+)<', h).group(1) for h in heads[1:]] == [f"{d:%a}" for d in WEEK]
    assert '<span class="short">M</span>' in heads[1] and '<span class="long">10/26</span>' in heads[1]
    assert '<span class="short">26</span>' in heads[1]
    labels = [re.sub(r"<[^>]+>", " ", r[0]).split()[:2] for r in rows(html)]
    assert labels == [["Games"], ["Add", "1"], ["Add", "2"]]
    assert "Open" not in html and 'class="open"' not in html


def test_the_games_row_shows_the_games_of_each_day_and_shades_each_column():
    games = rows(section())[0][1:]
    assert [re.sub(r"<[^>]+>", "", c) for c in games] == ["9", "4", "12", "3", "10", "7", "4"]
    # Mon and Tue are past: no shade. The day with the most games (12) gets 40%.
    assert 'class="past"' in games[0] and "--h" not in games[0]
    assert re.findall(r"--h: (\d+)%", "".join(games)) == ["40", "10", "33", "23", "13"]
    assert '<p class="heatkey">Fewer' in section()


def test_an_add_with_5_teams_or_fewer_lists_them_and_with_6_or_more_gives_the_count():
    row1, row2 = rows(section())[1:]
    thu1, thu2, sun = row1[4], row2[4], row1[7]
    assert '<b>+SG/<wbr>PF</b><span class="who"><span class="n">6 teams</span></span>' in thu1
    assert '<b>+PF</b><span class="who"><span>ATL</span><span>CLE</span><span>MEM</span><span>SAC</span></span>' in thu2
    assert '<b>+Util</b><span class="who"><span class="n">8 teams</span></span>' in sun
    # The count rule comes from [adds] team_count_at.
    html = section(cfg={"adds": {"team_count_at": 9}})
    assert "8 teams" not in re.sub(r'aria-label="[^"]*"|href="[^"]*"|title="[^"]*"', "", html)


def test_an_add_cell_links_to_the_free_agents_page_with_the_filters_and_a_text_label():
    thu1, sun = rows(section())[1][4], rows(section())[1][7]
    # #165: the link gives the start days as dates, the slots, the teams and the source of the filters.
    assert (
        '<a class="addc" href="../free-agents/?days=2026-10-29,2026-10-31&amp;pos=SG,PF'
        '&amp;teams=ATL,CLE,MEM,NO,POR,SAC&amp;from=Add+1,+Thu%3A+%2BSG%2FPF+6+teams"'
    ) in thu1
    assert "<button" not in thu1
    assert (
        'aria-label="Add 1, Thu: add SG or PF from 6 teams: ATL, CLE, MEM, NO, POR, SAC. Starts Thu &amp; Sat.' in thu1
    )
    assert "?days=2026-11-01&amp;pos=&amp;teams=BKN,BOS,GS,IND,LAC,LAL,ORL,TOR&amp;" in sun  # Util clears the position
    assert "any position" in sun


def test_a_day_header_that_is_not_past_links_to_the_free_agents_page_with_the_day():
    heads = re.findall(r'<th scope="col"[^>]*>.*?</th>', re.search(r"<thead>(.*?)</thead>", section()).group(1))
    assert "<a " not in heads[1] and 'class="past"' in heads[1] and 'aria-label="Mon 10/26, past"' in heads[1]
    assert ('<a class="dayc" href="../free-agents/?days=2026-10-28&amp;pos=&amp;teams=&amp;from=Wed+10%2F28"') in heads[
        3
    ]
    assert 'aria-label="Show free agents who play Sun 11/1"' in heads[7]


def test_a_past_add_shows_in_a_dashed_cell_with_no_button():
    row1, row2 = rows(section())[1:]
    assert row1[1].startswith('<td class="add past"><span class="addc was" role="img"')
    assert "<a " not in row1[1] and "<span>OKC</span>" in row1[1]
    assert 'aria-label="Recommended for Tue: add PG or SG from POR or SAC. Past."' in row2[2]


def test_the_band_runs_to_the_day_before_the_next_add_and_marks_each_start():
    row1, row2 = rows(section())[1:]

    def band(cell):
        if 'class="band' not in cell:
            return None
        return "start" if 'class="mk"' in cell else "hold"

    # Row 1: Mon add (past), band Tue (start, past) and Wed (no start), Thu add, band Fri (hold) and Sat (start),
    # Sun add.
    assert [band(c) for c in row1[1:]] == [None, "start", "hold", None, "hold", "start", None]
    assert 'class="band past"' in row1[2] and 'class="band"' in row1[3]
    # Row 2: Tue add (past), band Wed, Thu add, band Fri, Sat (start) and Sun.
    assert [band(c) for c in row2[1:]] == [None, None, "hold", None, "hold", "start", "hold"]
    assert '<p class="heatkey spankey">' in section()


def test_the_bands_and_the_marks_of_a_plan_on_a_small_fixed_schedule():
    # The kept roster fills Thu. One spot, 2 adds. PHI plays Mon and Tue. CHI plays Wed, Thu, Sat and Sun. DEN plays Fri.
    games = {
        WEEK[0]: {"PHI"},
        WEEK[1]: {"PHI"},
        WEEK[2]: {"CHI"},
        WEEK[3]: {"CHI", "BOS"},
        WEEK[4]: {"DEN"},
        WEEK[5]: {"CHI"},
        WEEK[6]: {"CHI"},
    }
    roster = [Player(f"B{i}", "BOS", (p,)) for i, p in enumerate(["PG", "SG", "SF", "PF", "C", "C"])]
    days = open_slots_by_day(roster, games, SLOTS)
    plan = team_plan(days, games, [StreamSpot()], 2, SLOTS)
    record = merged(WeekRecord(), MON, plan.adds, assign_rows(plan.adds, [None], []))
    assert [(a.day, a.teams, a.starts) for a in record.adds] == [
        (WEEK[0], ("PHI",), (WEEK[0], WEEK[1])),
        (WEEK[2], ("CHI",), (WEEK[2], WEEK[5], WEEK[6])),
    ]
    html = grid.plan_section(run(record=record, today=MON, days=days))
    cells = rows(html)[1][1:]
    kinds = [
        "add" if 'class="add"' in c else "start" if 'class="mk"' in c else "hold" if "band" in c else "" for c in cells
    ]
    # Thu: CHI plays, but the kept roster fills each slot. Fri: CHI does not play.
    assert kinds == ["add", "start", "add", "hold", "hold", "start", "start"]


def test_with_no_saved_plan_the_past_days_have_blank_add_cells_and_a_line_says_so():
    record = WeekRecord(runs=(WED,), adds=ADDS[2:])
    html = section(record=record)
    assert "No saved plan for Mon and Tue." in html
    assert all(c == '<td class="past"></td>' for r in rows(html)[1:] for c in r[1:3])
    assert "No saved plan" not in section()


def test_a_row_label_counts_its_adds_and_the_lede_counts_the_adds_of_today_and_later():
    html = section()
    assert "Add 1<small>3 adds</small>" in html and "Add 2<small>2 adds</small>" in html
    assert "The plan uses <b>3 of the 3 adds</b> that are left." in html


def test_the_legend_is_collapsed_and_the_keys_stay_visible():
    html = section()
    assert '<details class="notes" id="plan-notes"><summary>How to read the plan</summary>' in html
    assert html.index('class="heatkey spankey"') < html.index('id="plan-notes"')


def test_a_mixed_add_has_a_line_under_the_grid():
    record = WeekRecord(runs=(WED,), adds=(SavedAdd(1, WEEK[3], ("PF",), ("AAA", "BBB"), (WEEK[3],), True),))
    assert "The teams of add 1 on Thu play on different days." in section(record=record)


def test_with_no_free_agent_table_the_cells_are_not_links():
    html = grid.plan_section(run(), interactive=False)
    assert "<a " not in html and 'role="img" aria-label="Add 1, Thu: add SG or PF' in html


def test_add_text_is_the_line_of_one_add_for_the_terminal():
    assert grid.add_text(ADDS[3], 6) == "Add 2, Thu 10/29: +PF ATL CLE MEM SAC. Starts Thu & Sat."
    assert grid.add_text(ADDS[4], 6) == "Add 1, Sun 11/1: +Util 8 teams. Starts Sun."


def test_fa_link_puts_the_filters_in_the_query_of_the_free_agents_page():
    link = grid.fa_link([WEEK[3], WEEK[5]], "PF", ("CHI",), "Add 2, Thu: +PF CHI")
    assert link == "../free-agents/?days=2026-10-29,2026-10-31&pos=PF&teams=CHI&from=Add+2,+Thu%3A+%2BPF+CHI"
