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
from fantasyhoops.core.common import load_config
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
        # One leg for each add day, with the teams of the adds of that day. The legs do not overlap.
        days = sorted({a.day for a in plan.adds})
        assert [WEEK[leg.first] for leg in rung.legs] == days
        assert [leg.last for leg in rung.legs] == [WEEK.index(d) for d in days[1:]] + [7]
        for leg in rung.legs:
            here = [a for a in plan.adds if a.day == WEEK[leg.first]]
            assert leg.teams == tuple(sorted({t for a in here for t in a.teams}))
    # 2 adds left: 2 rungs. [skyline] max_adds caps the rungs.
    assert len(run(adds_left=2).ladder) == 2
    assert len(run(adds_left=5).ladder) == 4
    three = {**CFG, "skyline": {**CFG["skyline"], "max_adds": 3}}
    r = run(adds_left=5)
    assert len(skyline_plan.ladder_plans(r.days, r.games, SPOTS, 5, SLOTS, three)) == 3


def test_a_rung_is_one_row_of_legs_with_no_overlap_cut_at_each_add_day():
    """Owner, 2026-11-05: the ladder shows the rung columns of the post, with no overlapping legs."""
    chi = TeamAdd(1, WEEK[2], WEEK[6], ("PF",), ("CHI",), (WEEK[2], WEEK[5], WEEK[6]))
    plans = (
        TeamPlan((chi,), 3.0),
        TeamPlan((TeamAdd(0, WEEK[0], WEEK[6], (UTIL,), ("PHI",), (WEEK[0], WEEK[1])), chi), 5.0),
        TeamPlan((TeamAdd(0, WEEK[2], WEEK[6], ("C",), ("MIA",), (WEEK[2], WEEK[4])), chi), 5.0),
    )
    week = week_facts(SCHED, MON, CFG)
    rungs, adds_of = skyline_plan.roster_rungs(week, plans, CFG)
    spans = [[(leg.first, leg.last, leg.teams, leg.games) for leg in r.legs] for r in rungs]
    assert spans == [
        [(2, 7, ("CHI",), 3)],
        # Mon to Tue: the PHI add. Wed to Sun: the CHI add. The PHI player has no start after Tue.
        [(0, 2, ("PHI",), 2), (2, 7, ("CHI",), 3)],
        # 2 adds on Wed: one leg with the teams of both adds, and the starts of both players.
        [(2, 7, ("CHI", "MIA"), 5)],
    ]
    two = rungs[1]
    assert two.gain == 2 and not two.zero_gain and not two.replan and two.plus_one == (WEEK[0], WEEK[1])
    assert rungs[2].zero_gain and rungs[2].replan
    assert [len(adds) for _, adds in adds_of.values()] == [1, 1, 1, 2]


def test_each_leg_links_to_the_free_agents_page_with_the_filters_of_its_add_and_has_a_text_label():
    html = skyline_plan.plan_section(run())
    found = links(html)
    rungs, adds_of = skyline_plan.roster_rungs(run().skyline, run().ladder, CFG)
    groups = [adds for _, adds in adds_of.values()]
    assert len(found) == len(groups) >= 4
    want = sorted(
        (
            ",".join(sorted({d.isoformat() for a in g for d in a.starts})),
            "" if any(a.slots == (UTIL,) for a in g) else ",".join(s for s in SLOTS if any(s in a.slots for a in g)),
            ",".join(sorted({t for a in g for t in a.teams})),
        )
        for g in groups
    )
    assert sorted((q["days"], q["pos"], q["teams"]) for q, _ in found) == want
    assert all(label.endswith("Show these free agents.") for _, label in found)
    assert "1 add: on Wed add any position from CHI. Starts Wed, Sat &amp; Sun. Show these free agents." in html
    # The phone ladder has the same links. The skyline panels have none.
    assert html.count('<a href="../free-agents/?') == 4 * len(groups)  # 2 layouts x 2 themes
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


def test_the_week_number_comes_from_the_week_calendar_of_config_toml():
    """#236: the calendar of [weeks] gives the week number (Jan 4, 2027 is week 11). Without it: the Yahoo number."""
    calendar = {**CFG, "weeks": load_config()["weeks"]}
    assert "Week 11 · 2027" in skyline_plan.plan_section(run(cfg=calendar))
    assert "Week 12 · 2027" in skyline_plan.plan_section(run())


# A long week (owner, 2026-11-05): 14 days, Nov 30 to Dec 13, 2026. CHI plays each Sat, Sun and Tue. MIA plays each
# Wed and Thu. One add of CHI on Sat Dec 5 holds its spot to Dec 13. One add of MIA on Wed Dec 9.
LONG = [date(2026, 11, 30) + timedelta(days=i) for i in range(14)]
LONG_SCHED = pd.DataFrame(
    [(str(d), "CHI") for d in LONG if d.weekday() in (5, 6, 1)]
    + [(str(d), "MIA") for d in LONG if d.weekday() in (2, 3)]
    + [(str(d), "ATL") for d in LONG],
    columns=["date", "team"],
)
CHI_SAT = TeamAdd(0, LONG[5], LONG[13], ("PF",), ("CHI",), (LONG[5], LONG[6], LONG[8], LONG[12], LONG[13]))
MIA_WED = TeamAdd(1, LONG[9], LONG[13], ("C",), ("MIA",), (LONG[9], LONG[10]))


def long_run(**fields):
    days = open_slots_by_day([], {d: set() for d in LONG[4:]}, SLOTS)
    data = command.LeagueData(roster=[], adds=Adds(0, 5), week=Week(7, tuple(LONG)))
    cfg = {**CFG, "weeks": load_config()["weeks"]}
    base = command.PlanningRun(
        data=data,
        days=days,
        games={},
        spots=SPOTS,
        today=LONG[4],
        cfg=cfg,
        skyline=skyline_plan.skyline_weeks(LONG_SCHED, data.week, cfg),
        ladder=(TeamPlan((CHI_SAT,), 5.0), TeamPlan((CHI_SAT, MIA_WED), 7.0)),
    )
    return replace(base, **fields)


def test_a_long_week_has_2_skylines_and_a_leg_that_crosses_the_seam_continues_in_the_second_half():
    run = long_run()
    assert [w.days[0] for w in run.skyline] == [LONG[0], LONG[7]]
    first, second = (skyline_plan.roster_rungs(w, run.ladder, run.cfg, run.skyline)[0] for w in run.skyline)
    # The first half: the CHI leg from Sat to Sun.
    assert [[(x.first, x.last, x.teams, x.games) for x in r.legs] for r in first] == [
        [(5, 7, ("CHI",), 2)],
        [(5, 7, ("CHI",), 2)],
    ]
    # The second half: the CHI leg continues on Monday. In rung 2, the MIA add on Wed starts a new leg.
    assert [[(x.first, x.last, x.teams, x.games) for x in r.legs] for r in second] == [
        [(0, 7, ("CHI",), 3)],
        [(0, 2, ("CHI",), 1), (2, 7, ("MIA",), 4)],
    ]
    # Both halves show the same rung totals: the games and the light-night starts of the whole matchup.
    totals = [[(r.games, r.light, r.gain, r.plus_one) for r in half] for half in (first, second)]
    assert totals[0] == totals[1]
    html = skyline_plan.plan_section(run)
    assert '<p class="sky-dates">Week 7, part 1 of 2: Nov 30 – Dec 6, 2026</p>' in html
    assert '<p class="sky-dates">Week 7, part 2 of 2: Dec 7–13, 2026</p>' in html
    assert html.index("part 1 of 2") < html.index('id="sk-page-20261130"') < html.index("part 2 of 2")
    assert html.index("part 2 of 2") < html.index('id="sk-page-20261207"')
    # The phone panels of the 2 halves follow in order: light, then dark, for each half.
    phone = re.findall(r'<svg [^>]*id="sk-(phone-[a-z]+)-(\d+)', html)
    assert phone == [
        ("phone-skyline", "20261130"),
        ("phone-ladder", "20261130"),
        ("phone-skyline", "20261130"),
        ("phone-ladder", "20261130"),
        ("phone-skyline", "20261207"),
        ("phone-ladder", "20261207"),
        ("phone-skyline", "20261207"),
        ("phone-ladder", "20261207"),
    ]
    # The CHI leg of the second half links to the filters of the CHI add.
    assert html.count("2 adds: on Sat add PF from CHI.") == 2 * 2 * 2  # 2 halves x 2 layouts x 2 themes
