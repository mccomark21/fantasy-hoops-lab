import re
from dataclasses import replace
from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pandas as pd

from fantasyhoops.adds import plan as command
from fantasyhoops.adds import skyline_plan
from fantasyhoops.adds.planner import StreamSpot
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.adds.team_plan import UTIL, TeamAdd, TeamPlan, team_plan
from fantasyhoops.adds.week_file import SavedAdd, WeekRecord
from fantasyhoops.core.skyline import week_facts

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]
CFG = {
    "league": {"slots": SLOTS},
    "quality_games": {"max_games_per_day": 6},
    "skyline": {"max_adds": 4, "scarce_teams": 5, "anchor_max_games": 4, "heavy_max_teams": 3},
}
# A small fixed schedule (from the grid tests of #140). The kept roster (6 BOS players) fills each slot on Thu.
# PHI plays Mon and Tue. CHI plays Wed, Thu, Sat and Sun. DEN plays Fri. MIA plays Mon, Wed and Fri.
TEAMS = {
    WEEK[0]: {"PHI", "MIA"},
    WEEK[1]: {"PHI"},
    WEEK[2]: {"CHI", "MIA"},
    WEEK[3]: {"CHI", "BOS"},
    WEEK[4]: {"DEN", "MIA"},
    WEEK[5]: {"CHI"},
    WEEK[6]: {"CHI"},
}
SCHED = pd.DataFrame(
    [(str(d), t) for d, teams in TEAMS.items() for t in sorted(teams)] + [(str(WEEK[1]), "ATL")],
    columns=["date", "team"],
)
ROSTER = [Player(f"B{i}", "BOS", (p,)) for i, p in enumerate(["PG", "SG", "SF", "PF", "C", "C"])]
SPOTS = [StreamSpot(), StreamSpot()]


def run(adds_left=4, spots=SPOTS, today=MON, **fields):
    """A PlanningRun of the fixed schedule, with the ladder of skyline_plan.ladder_plans()."""
    games = {d: t for d, t in TEAMS.items() if d >= today}
    days = open_slots_by_day(ROSTER, games, SLOTS)
    ladder = skyline_plan.ladder_plans(days, games, spots, adds_left, SLOTS, CFG)
    data = command.LeagueData(roster=ROSTER, adds=Adds(5 - adds_left, 5), week=Week(12, tuple(WEEK)))
    base = command.PlanningRun(
        data=data,
        days=days,
        games=games,
        spots=spots,
        today=today,
        cfg=CFG,
        skyline=week_facts(SCHED, MON, CFG),
        ladder=ladder,
    )
    return replace(base, **fields)


def links(html):
    """(the query, the text label) of each leg link of the desktop layout in the light theme."""
    wide = re.search(r'<div class="sky-wide"><div class="sky-light">(.*?)</div>', html, re.S).group(1)
    return [
        ({k: v[0] for k, v in parse_qs(urlsplit(h.replace("&amp;", "&")).query, keep_blank_values=True).items()}, a)
        for h, a in re.findall(r'<a href="([^"]+)" aria-label="([^"]+)">', wide)
    ]


def test_rung_n_is_the_team_plan_with_n_adds_for_n_up_to_the_adds_left_and_4():
    r = run()
    assert len(r.ladder) == 4
    for n, plan in enumerate(r.ladder, start=1):
        assert plan == team_plan(r.days, r.games, SPOTS, n, SLOTS)
    rungs, _ = skyline_plan.roster_rungs(r.skyline, r.ladder, CFG)
    assert [x.games for x in rungs] == [p.started_games for p in r.ladder]
    for rung, plan in zip(rungs, r.ladder):
        # Each add is one leg: from the add day to the last day that the new player holds the spot.
        got = sorted((WEEK[leg.first], WEEK[leg.last - 1], leg.teams, leg.pattern) for leg in rung.legs)
        assert got == sorted((a.day, a.last_day, a.teams, a.starts) for a in plan.adds)
    # 2 adds left: 2 rungs. [skyline] max_adds caps the rungs.
    assert len(run(adds_left=2).ladder) == 2
    assert len(run(adds_left=5).ladder) == 4
    three = {**CFG, "skyline": {**CFG["skyline"], "max_adds": 3}}
    r = run(adds_left=5)
    assert len(skyline_plan.ladder_plans(r.days, r.games, SPOTS, 5, SLOTS, three)) == 3


def test_each_stream_spot_with_an_add_is_one_lane_of_its_rung_in_order_of_the_first_add_day():
    plans = (
        TeamPlan((TeamAdd(1, WEEK[2], WEEK[6], ("PF",), ("CHI",), (WEEK[2], WEEK[5], WEEK[6])),), 3.0),
        TeamPlan(
            (
                TeamAdd(0, WEEK[0], WEEK[1], (UTIL,), ("PHI",), (WEEK[0], WEEK[1])),
                TeamAdd(1, WEEK[2], WEEK[6], ("PF",), ("CHI",), (WEEK[2], WEEK[5], WEEK[6])),
            ),
            5.0,
        ),
    )
    week = week_facts(SCHED, MON, CFG)
    rungs, adds_of = skyline_plan.roster_rungs(week, plans, CFG)
    assert [[[leg.teams for leg in lane] for lane in r.lanes] for r in rungs] == [
        [[("CHI",)]],
        [[("PHI",)], [("CHI",)]],
    ]
    two = rungs[1]
    assert two.gain == 2 and not two.zero_gain and not two.replan and two.plus_one == (WEEK[0], WEEK[1])
    assert {n for n, _ in adds_of.values()} == {1, 2}


def test_each_leg_links_to_the_free_agents_page_with_the_filters_of_its_add_and_has_a_text_label():
    html = skyline_plan.plan_section(run())
    found = links(html)
    adds = [a for plan in run().ladder for a in plan.adds]
    assert len(found) == len(adds) >= 4
    want = sorted(
        (
            ",".join(d.isoformat() for d in a.starts),
            "" if a.slots == (UTIL,) else ",".join(a.slots),
            ",".join(a.teams),
            f"spot {a.spot + 1}, {a.day:%a}",
        )
        for a in adds
    )
    got = sorted(
        (q["days"], q["pos"], q["teams"], q["from"].split(": ")[0].split("adds, ")[-1].split("add, ")[-1])
        for q, _ in found
    )
    assert got == want
    assert all(label.endswith("Show these free agents.") for _, label in found)
    assert "spot 1: on Mon add any position from MIA. Starts Mon, Wed &amp; Fri. Show these free agents." in html
    # The phone ladder has the same links. The skyline panels have none.
    assert html.count('<a href="../free-agents/?') == 4 * len(adds)  # 2 layouts x 2 themes
    assert 'role="group"' in html


def test_with_no_free_agent_table_the_legs_are_not_links():
    html = skyline_plan.plan_section(run(), interactive=False)
    assert "<a " not in html and "Tap a block" not in html


def test_the_section_has_the_desktop_layout_and_the_phone_panels_in_both_themes():
    html = skyline_plan.plan_section(run())
    assert html.count('class="skyline skyline-page"') == 2
    assert html.count('class="skyline skyline-phone-skyline"') == 2
    assert html.count('class="skyline skyline-phone-ladder"') == 2
    assert 'id="sk-page-20270104"' in html and 'id="sk-page-20270104-dark"' in html
    assert '<section id="plan"><h2 class="vh">Schedule Skyline</h2>' in html
    assert '<details class="notes" id="plan-notes"><summary>How to read the Skyline</summary>' in html


def test_with_no_adds_left_a_line_says_so_and_the_ladder_is_the_one_open_spot():
    html = skyline_plan.plan_section(run(adds_left=0))
    assert "No adds left this week (5 of 5 used). There are no adds to plan." in html
    assert "The ladder shows one open spot on each day, not your roster." in html
    assert "<a " not in html and html.count('class="skyline skyline-page"') == 2
    html = skyline_plan.plan_section(run(spots=[]))
    assert "No stream spots." in html


def test_the_lines_under_the_skyline_name_the_past_adds_the_days_with_no_plan_and_an_add_for_today():
    record = WeekRecord(runs=(WEEK[0],), adds=(SavedAdd(1, WEEK[0], ("SG",), ("PHI",), (WEEK[0], WEEK[1])),))
    html = skyline_plan.plan_section(run(today=WEEK[2], record=record))
    assert "<li>Add 1, Mon 1/4: +SG PHI. Starts Mon &amp; Tue.</li>" in html
    assert "No saved plan for Tue." in html
    assert "An add for today helps only if his game has not started." in html


def test_a_mixed_add_has_a_line_under_the_skyline():
    mixed = TeamAdd(0, WEEK[2], WEEK[6], ("PF",), ("CHI", "MIA"), (WEEK[2],), mixed=True)
    html = skyline_plan.plan_section(run(ladder=(TeamPlan((mixed,), 1.0),)))
    assert "The teams of the add on Wed (CHI MIA) play on different days." in html
