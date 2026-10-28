import json
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest

from fantasyhoops.adds import lists, page, timing
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.contingency import Contingency
from fantasyhoops.adds.matchup import Matchup, matchup_weights, read_matchup
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamRank, TeamWindow
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.roles import Role
from fantasyhoops.adds.slots import Day
from fantasyhoops.adds.spots import SpotPlan
from fantasyhoops.core import publish as site
from fantasyhoops.core import tokens
from fantasyhoops.core.common import load_config

MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]
DAYS = [Day(d, 5, (), (), ("PG", "Util") if i in (0, 1, 3, 5) else ()) for i, d in enumerate(WEEK)]
DATA = command.LeagueData(
    roster=[Player("Hurt Guy", "BOS", ("PG",), status="O")],
    adds=Adds(used=1, limit=5),
    week=Week(number=12, days=tuple(WEEK)),
)


def option(name, team, value, positions=("SF",), status="", recent=None):
    return Option(Player(name, team, positions, status=status), value, recent_value=recent)


HOLDER = option("Old Streamer", "MIA", -0.5)
SPOTS = [StreamSpot(), StreamSpot(HOLDER)]
PHI, CHI = option("Phi & One", "PHI", 0.31), option("Chi One", "CHI", -0.40, ("PF",), "Q")
# PHI plays Mon, Tue and Sat. CHI plays Sat and Sun. MIA plays Mon.
GAMES = {WEEK[0]: {"PHI", "MIA"}, WEEK[1]: {"PHI"}, WEEK[5]: {"PHI", "CHI"}, WEEK[6]: {"CHI"}}
# Row 1: the empty spot, PHI from Mon, then CHI on Sun. Row 2: the spot of Old Streamer, PHI from Tue.
ROW1 = SpotPlan(
    SPOTS[0],
    Plan(
        windows=(
            TeamWindow(0, "PHI", WEEK[0], WEEK[5], (WEEK[0], WEEK[1], WEEK[5]), PHI, (PHI,)),
            TeamWindow(0, "CHI", WEEK[6], WEEK[6], (WEEK[6],), CHI, (CHI,)),
        ),
        started_games=4,
        adds=2,
    ),
    4,
)
ROW2 = SpotPlan(
    SPOTS[1],
    Plan(
        windows=(
            TeamWindow(0, "MIA", None, WEEK[0], (WEEK[0],), HOLDER, ()),
            TeamWindow(0, "PHI", WEEK[1], WEEK[6], (WEEK[1], WEEK[5]), PHI, (PHI,)),
        ),
        started_games=3,
        adds=1,
    ),
    2,
)
RANKING = [TeamRank("PHI", (WEEK[0], WEEK[1], WEEK[5]), 6), TeamRank("DAL", (WEEK[3],), 2)]
OPTIONS = [
    PHI,
    CHI,
    option("Hurt FA", "PHI", 2.0, status="O"),
    option("Star", "PHI", 2.5, ("C",), recent=2.0),
    option("No Value", "PHI", None),
]


# BASE: the fewest fields of a PlanningRun. RUN: the test defaults of a page with plans and free agents.
LEAGUE = {"league": {"teams": 14}}  # the team count of the site menu (#132)
BASE = command.PlanningRun(data=DATA, days=DAYS, games=GAMES, spots=SPOTS, today=WEEK[0], cfg=LEAGUE)
RUN = replace(BASE, rows=[ROW1, ROW2], options=OPTIONS, ranking=RANKING, read=["PHI"], replacement=0.5)


def render(run=RUN, **fields):
    """The page of run (default: RUN), with the fields of fields changed."""
    return page.render(replace(run, **fields))


def text(html):
    """The visible text of a page, with single spaces. The script and its data are not visible."""
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    parts = []
    parser = HTMLParser()
    parser.handle_data = parts.append
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parts))


def run_time(html):
    """The HTML of the Run time section."""
    return re.search(r'<details class="notes" id="run-time">.*?</details>', html, re.S).group(0)


def plan_rows(html):
    """The day rows of the plans. A spot line comes before each one (#114)."""
    return re.findall(r'<tr class="days[^"]*">(.*?)</tr>', html)


def test_each_row_shows_the_started_games_of_each_day_and_the_add_days():
    rows = plan_rows(render())
    cells = [re.findall(r"<td(?: class=\"on\")?>(?:<b>)?(\d|·|<i>\+</i>)(<i>\+</i>)?", row)[:7] for row in rows]
    assert cells[0] == [("1", "<i>+</i>"), ("1", ""), ("·", ""), ("·", ""), ("·", ""), ("1", ""), ("1", "<i>+</i>")]
    assert cells[1] == [("·", ""), ("1", "<i>+</i>"), ("·", ""), ("·", ""), ("·", ""), ("1", ""), ("·", "")]


def test_each_row_shows_its_adds_its_gain_and_its_moves():
    html = render()
    rows = plan_rows(html)
    assert re.findall(r'<td class="total">([^<]*)</td>', rows[0]) == ["2", "+4"]
    assert re.findall(r'<td class="total">([^<]*)</td>', rows[1]) == ["1", "+2"]
    shown = text(html)
    assert "+Phi &amp; One" in html and "Phi & One" not in html.split("<script")[0]
    assert "+Phi & One (PHI) add Mon – starts Mon, Tue & Sat +Chi One Q (CHI) add Sun – starts Sun" in shown
    assert "+Phi & One (PHI) add Tue – starts Tue & Sat" in shown
    # The spot line above the row names the drop, so the Moves cell does not (#114).
    assert "drop" not in "".join(re.findall(r'<td class="moves">(.*?)</td>', html))
    assert "An add for today helps only if his game has not started." in shown


def test_the_page_shows_the_week_and_the_open_slots():
    shown = text(render())
    assert "Week 12: Mon 1/4 to Sun 1/10" in shown and "4 of 5 adds left" in shown and "2 stream spots" in shown
    assert "Out (does not play): Hurt Guy (O)" in shown
    assert re.search(r'<tr class="open"><th>Open</th>(<td[^>]*>2</td><td[^>]*>2</td><td[^>]*>0</td>)', render())


def test_the_free_agent_data_has_market_values_and_the_days_of_each_player():
    data = page.free_agent_data(OPTIONS, DAYS, GAMES, replacement=0.5)
    names = [p["name"] for p in data["players"]]
    # Best value first. An Out player and a player with no value are not in the table.
    assert names == ["Star", "Phi & One", "Chi One"]
    star = data["players"][0]
    assert (star["value"], star["recent"]) == (2.0, 1.5)
    # Chi One plays Sat and Sun. Sat has open PG and Util slots (Util takes all positions), Sun has none.
    chi = data["players"][2]
    assert chi["plays"] == [False, False, False, False, False, True, True]
    assert chi["fits"] == [False, False, False, False, False, True, False]
    assert [d["open"] for d in data["days"]] == [2, 2, 0, 2, 0, 2, 0]
    assert data["rows"] == 10 and data["flag"] == page.FLAG


def test_the_free_agent_data_has_the_matchup_value_next_to_the_value():
    shooter = Option(Player("Shooter", "PHI", ("SF",)), 1.0, matchup_value=0.4)
    data = page.free_agent_data([shooter, PHI], DAYS, GAMES, replacement=0.5, match_replacement=0.2)
    assert [(p["value"], p["match"]) for p in data["players"]] == [(0.5, 0.2), (-0.19, 0.11)]


def test_the_page_shows_the_matchup_score_and_the_weight_of_each_category():
    m = Matchup("Rival & Co", {"pts": 300, "threes": 40, "blk": 8}, {"pts": 290, "threes": 25, "blk": 10})
    weights = {"pts": 1.0, "threes": 0.5, "blk": 1.0}
    shown = text(render(data=replace(DATA, matchup=m), weights=weights))
    # The page is public, so it does not show the name of the opponent.
    assert "Rival" not in shown and "your opponent in this matchup" in shown
    assert "3PTM 40 25 +15 0.50" in shown and "PTS 300 290 +10 1.00" in shown and "BLK 8 10 -2 1.00" in shown
    assert "The planner did not find the category scores" in text(render(weights=weights))
    # A run with no weights (no free agents read) shows no matchup section.
    assert "Matchup" not in text(render())


def test_the_page_shows_the_matchup_weights_from_the_live_score_table():
    # The matchup page of 2026-10-21 (#73). The week has 6 days, and the planning window is 2026-10-21 to 10-25.
    # The margins are the first values of config.toml (#59), fixed here so that a change to config.toml has no effect.
    cats = ("pts", "reb", "ast", "threes", "blk", "stl")
    cfg = {
        "weights": {c: 1.0 for c in cats},
        "adds": {
            "matchup": {
                "close": {"pts": 40, "reb": 15, "ast": 10, "threes": 5, "blk": 3, "stl": 3},
                "large": {"pts": 120, "reb": 45, "ast": 30, "threes": 15, "blk": 9, "stl": 9},
                "min_weight": 0.5,
            }
        },
    }
    fixture = Path(__file__).parent / "fixtures" / "matchup_scores_live.html"
    m = read_matchup(fixture.read_text(encoding="utf-8"), team=10)
    html = render(data=replace(DATA, matchup=m), weights=matchup_weights(m, cfg, share_left=5 / 6))
    shown = text(html)
    assert "The planner did not find the category scores" not in shown
    assert "PTS 24 45 -21 1.00" in shown and "REB 4 17 -13 0.99" in shown and "BLK 0 3 -3 0.95" in shown
    assert "Opponent" not in html


def test_the_opponent_name_is_not_on_the_page():
    # The page is public (ADR 2). The name must not be in the HTML, the script or its data.
    m = Matchup("Secret Rival Team", {"pts": 300}, {"pts": 290})
    html = render(data=replace(DATA, matchup=m), weights={"pts": 1.0})
    assert "Secret" not in html and "Rival" not in html
    assert "300" in text(html)


def test_the_free_agent_data_has_the_minutes_the_starts_and_the_closes():
    roles = {
        ("Phi & One", "PHI"): Role(
            minutes_last5=28.04,
            minutes_14d=22.0,
            games=4,
            starts=3,
            closes=1,
            close_games=2,
            rise=True,
            starter="Regular",
            closer="New",
        ),
        ("Star", "PHI"): Role(
            minutes_last5=30.0, minutes_14d=None, games=0, starts=0, closes=0, close_games=0, rise=False
        ),
    }
    players = {p["name"]: p for p in page.free_agent_data(OPTIONS, DAYS, GAMES, 0.5, roles=roles)["players"]}
    assert players["Phi & One"]["role"] == "Min 28.0 L5, 22.0 14d (+6.0) · Starts 3/4 (Regular) · Closes 1/2 (New)"
    assert players["Phi & One"]["rise"]
    assert players["Star"]["role"] == "Min 30.0 L5, no games in 14d · Starts 0/0 · Closes 0/0"
    assert not players["Star"]["rise"]
    # A player who is not in the rotation log has no role text.
    assert players["Chi One"]["role"] is None and not players["Chi One"]["rise"]
    shown = text(
        render(roles=roles, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0, "flags": load_config()["adds"]["flags"]}})
    )
    assert "Min: his mean minutes in his last 5 games (L5) and in the last 14 days (14d)" in shown
    assert "MIN+ L5 is 4 minutes or more above 14d" in shown
    assert "The word after Starts is the starter flag, from his last 10 games (5 or more)." in shown
    assert "from the last 8 close games of his team (4 or more)" in shown
    assert "Regular: 70% or more. Inconsistent: 20% or more." in shown


def test_the_page_shows_the_starter_flag_and_the_closer_flag_in_the_html():
    roles = {
        ("Phi & One", "PHI"): Role(
            minutes_last5=20.0,
            minutes_14d=20.0,
            games=5,
            starts=1,
            closes=0,
            close_games=4,
            rise=False,
            starter="Inconsistent",
            closer=None,
        ),
        ("Star", "PHI"): Role(
            minutes_last5=30.0,
            minutes_14d=30.0,
            games=5,
            starts=5,
            closes=4,
            close_games=4,
            rise=False,
            starter="New",
            closer="Regular",
        ),
    }
    html = render(roles=roles, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0}})
    assert "Starts 1/5 (Inconsistent) · Closes 0/4" in html
    assert "Closes 0/4 (" not in html  # no closer flag: no word after the closes
    assert "Starts 5/5 (New) · Closes 4/4 (Regular)" in html


def test_the_page_has_no_role_legend_with_no_rotation_log():
    assert "Min: his mean minutes" not in text(render())


def test_the_page_holds_the_free_agent_data_as_safe_json():
    html = render()
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert json.loads(raw)["players"][1]["name"] == "Phi & One"
    evil = render(BASE, options=[option("</script><b>", "PHI", 1.0)])
    assert "</script><b>" not in evil and "http" not in evil


def test_the_page_explains_why_there_is_no_plan():
    assert "No adds left this week (5 of 5 used)" in text(
        render(BASE, data=command.LeagueData([], Adds(5, 5), DATA.week))
    )
    assert "No stream spots" in text(render(BASE, spots=[]))
    assert "No free agent that the planner read" in text(render(BASE))
    # No options: no free-agent table and no script.
    assert "fa-data" not in render(BASE)


CLAIM = Option(Player("Claim Guy", "CHI", ("C",), clear_day=WEEK[1]), 1.2)


def test_the_page_lists_the_waiver_players_with_the_clear_day():
    html = render(options=OPTIONS + [CLAIM])
    shown = text(html)
    assert "Waiver players" in shown
    assert "Claim Guy W CHI C Tue 1/5 Wed 1/6 +0.70" in shown
    # The free-agent table holds only the players with status FA.
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert "Claim Guy" not in [p["name"] for p in json.loads(raw)["players"]]


def test_the_page_has_no_waiver_section_with_no_waiver_players():
    assert "Waiver players" not in text(render())


def test_a_move_marks_a_waiver_claim():
    row = SpotPlan(
        SPOTS[0],
        Plan(
            windows=(TeamWindow(0, "CHI", WEEK[2], WEEK[6], (WEEK[5], WEEK[6]), CLAIM, (CLAIM,)),),
            started_games=2,
            adds=1,
        ),
        2,
    )
    shown = text(render(BASE, rows=[row], options=[CLAIM]))
    assert "+Claim Guy W (CHI) add Wed, clears Tue – starts Sat & Sun" in shown
    assert "W: a waiver claim. It is not sure" in shown


def test_the_page_shows_the_site_menu_with_the_adds_plan_current():
    html = render()
    assert (
        html.index('<body class="lab">') < html.index('<nav class="lab-menu"') < html.index('<main class="lab-main">')
    )
    assert '<a href="../adds/" aria-current="page">Adds plan</a>' in html and '<a href="../">Roster</a>' in html
    assert ">Auto</button>" in html and ">Light</button>" in html and ">Dark</button>" in html
    assert html.index("<h1>") > html.index("</nav>")
    assert html.rstrip().endswith(f"{site.MENU_SCRIPT}\n</body>\n</html>")


def test_the_page_sets_the_saved_theme_in_the_head_and_uses_the_shared_tokens():
    head = render().split("</head>")[0]
    assert tokens.HEAD in head and head.index(tokens.THEME_SCRIPT) < head.index("<style>")
    assert "font-family: Archivo" in head and "var(--lab-face)" in head


def test_the_page_css_has_no_colors_of_its_own():
    """#117: the colors come from core/tokens.py. The page CSS uses only var(--...)."""
    css = render().split("</head>")[0].replace(tokens.HEAD, "")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", page.SCRIPT)


def test_the_page_marks_the_second_game_of_each_back_to_back():
    # PHI plays Mon and Tue, so Tue is a second night. CHI plays Sat and Sun, so Sun is a second night.
    nights = {WEEK[1]: {"PHI"}, WEEK[6]: {"CHI"}}
    rows = plan_rows(render(nights=nights))
    marks = [
        [bool(re.search(r'class="b2b"', cell)) for cell in re.findall(r"<td[^>]*>.*?</td>", row)[:7]] for row in rows
    ]
    assert marks[0] == [False, True, False, False, False, False, True]
    assert marks[1] == [False, True, False, False, False, False, False]
    assert "second game of a back-to-back" in text(render(nights=nights))
    data = page.free_agent_data(OPTIONS, DAYS, GAMES, replacement=0.5, nights=nights)
    assert data["players"][2]["b2b"] == [False, False, False, False, False, False, True]  # Chi One
    assert data["players"][1]["b2b"] == [False, True, False, False, False, False, False]  # Phi & One


def test_a_fractional_gain_shows_one_decimal():
    row = SpotPlan(ROW2.spot, ROW2.plan, 1.5)
    html = render(BASE, rows=[row], options=OPTIONS)
    assert re.findall(r'<td class="total">([^<]*)</td>', plan_rows(html)[0]) == ["1", "+1.5"]


def spot_lines(html):
    """The text of each spot line of the plans: the row number, the spot and the same-spot mark (#114)."""
    return [text(line).strip() for line in re.findall(r'<tr class="spot[^"]*">(.*?)</tr>', html)]


def test_each_plan_row_shows_its_roster_spot_above_the_days():
    html = page.plans_section([ROW1, ROW2], DAYS, SPOTS, DATA.adds, WEEK[0])
    assert spot_lines(html) == ["1 open spot", "2 drop Old Streamer"]
    # The spot line comes before the days of its row, and the row number spans both lines.
    assert re.search(r'<tr class="spot z"><th rowspan="2">1</th><td colspan="10"><b>open spot</b></td></tr>'
                     r'<tr class="days z">', html)  # fmt: skip
    assert 'class="same"' not in html


def test_a_row_that_uses_the_same_spot_as_a_row_above_it_has_a_text_mark():
    other = option("Other Guy", "CHI", 0.2)
    row3 = SpotPlan(
        SPOTS[1], replace(ROW2.plan, windows=(ROW2.plan.windows[0], replace(ROW1.plan.windows[1], player=other))), 1
    )
    html = page.plans_section([ROW2, ROW1, row3], DAYS, SPOTS, DATA.adds, WEEK[0])
    assert spot_lines(html) == ["1 drop Old Streamer", "2 open spot", "3 drop Old Streamer same spot as row 1"]
    assert '<span class="same">same spot as row 1</span>' in html
    assert 'The mark "same spot as row 1" shows that a row uses the spot of row 1' in text(html)


def test_rows_that_use_more_open_spots_than_the_roster_has_share_a_spot():
    spots = [StreamSpot(), StreamSpot()]  # two open spots
    rows = [ROW1, replace(ROW1, gain=3), replace(ROW1, gain=2)]
    html = page.plans_section(rows, DAYS, spots, DATA.adds, WEEK[0])
    assert spot_lines(html) == ["1 open spot", "2 open spot", "3 open spot same spot as row 1"]
    one = page.plans_section(rows[:2], DAYS, SPOTS, DATA.adds, WEEK[0])
    assert spot_lines(one) == ["1 open spot", "2 open spot same spot as row 1"]


def test_each_add_shows_its_add_day_before_its_started_days():
    html = page.plans_section([ROW1, ROW2], DAYS, SPOTS, DATA.adds, WEEK[0])
    moves = [text(m).strip() for m in re.findall(r'<td class="moves">(.*?)</td>', html)]
    assert moves == [
        "+Phi & One (PHI) add Mon – starts Mon, Tue & Sat +Chi One Q (CHI) add Sun – starts Sun",
        "+Phi & One (PHI) add Tue – starts Tue & Sat",
    ]
    assert '<span class="add">add Tue</span>' in html
    # The + mark stays in the day grid.
    assert plan_rows(html)[1].count("<i>+</i>") == 1


def test_a_waiver_claim_shows_its_add_day_its_w_flag_and_its_clear_day():
    row = SpotPlan(SPOTS[0], Plan((TeamWindow(0, "CHI", WEEK[2], WEEK[6], (WEEK[5],), CLAIM, (CLAIM,)),), 1, 1), 1)
    html = page.plans_section([row], DAYS, SPOTS, DATA.adds, WEEK[0])
    assert ">W</span>" in html and '<span class="add">add Wed, clears Tue</span>' in html


def test_at_390px_the_plans_have_no_horizontal_scroll_and_show_the_spot_and_the_add_day():
    row3 = SpotPlan(SPOTS[1], replace(ROW2.plan, windows=(ROW2.plan.windows[0], replace(ROW1.plan.windows[1]))), 1)
    html = render(BASE, rows=[ROW1, ROW2, row3], options=OPTIONS)
    with browser_page(width=390) as pg:
        pg.set_content(html)
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate("document.documentElement.scrollWidth") <= 390, theme
            for selector in ("tr.spot b", ".plans .same", ".plans span.add"):
                boxes = pg.locator(selector).evaluate_all(
                    "els => els.map(e => { const r = e.getBoundingClientRect();"
                    " return [r.left, r.right, r.width, getComputedStyle(e).visibility]; })"
                )
                assert boxes, selector
                for left, right, width, visibility in boxes:
                    assert width > 0 and left >= 0 and right <= 390 and visibility == "visible", (selector, theme)
            assert pg.evaluate(CONTRAST) == [], theme


def test_the_free_agent_data_and_the_page_show_the_role_up_mark_and_the_absent_teammate():
    marked = replace(PHI, role_up=("Star Wing",))
    data = page.free_agent_data([marked, CHI], DAYS, GAMES, replacement=0.5)
    assert [p["role_up"] for p in data["players"]] == [["Star Wing"], []]
    shown = text(render(BASE, options=[marked, CHI]))
    assert "Role up" in shown
    assert "Star Wing is absent. Role up: Phi & One (PHI)." in shown
    assert "role up" in page.SCRIPT


def test_the_page_has_no_role_up_section_with_no_mark():
    assert "Role up" not in text(render())


def test_the_free_agent_data_marks_a_game_on_an_open_day_early_next_week():
    # Next Mon has an open PG slot. Next Tue has no open slot. PHI plays both days, CHI plays Tue only.
    nmon, ntue = WEEK[6] + timedelta(days=1), WEEK[6] + timedelta(days=2)
    early = [Day(nmon, 4, (), (), ("PG",)), Day(ntue, 6, (), (), ())]
    early_games = {nmon: {"PHI"}, ntue: {"PHI", "CHI"}}
    guard = option("Phi Guard", "PHI", 0.4, ("PG",))
    data = page.free_agent_data(
        [guard, PHI, CHI], DAYS, GAMES, replacement=0.5, next_days=early, next_games=early_games
    )
    # Phi Guard fills the open PG slot on Mon. Phi & One (SF) does not fit it. Chi One plays only on Tue (no open slot).
    assert [p["next_open"] for p in data["players"]] == [["Mon open"], [], []]


def test_the_page_shows_the_next_week_mark_in_the_free_agent_table():
    nmon = WEEK[6] + timedelta(days=1)
    early, early_games = [Day(nmon, 4, (), (), ("SF", "Util"))], {nmon: {"PHI"}}
    html = render(next_days=early, next_games=early_games)
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert {p["name"]: p["next_open"] for p in data["players"]}["Phi & One"] == ["Mon open"]
    assert "p.next_open" in page.SCRIPT and 'class="flag next"' in page.SCRIPT
    assert (
        '<span class="flag next">Mon open</span>: he has a game next Monday 1/11, and your core players leave a '
        "slot open that he can fill (2 open slots)."
    ) in html


def test_the_page_script_draws_the_next_week_badge_in_the_free_agent_row():
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    nmon = WEEK[6] + timedelta(days=1)
    html = render(next_days=[Day(nmon, 4, (), (), ("SF", "Util"))], next_games={nmon: {"PHI"}})
    data = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    script = html.split('<script type="application/json" id="fa-data">')[1].split("<script>")[1].split("</script>")[0]
    # A small page: the elements that the script uses, with the JSON data of the page.
    code = (
        f"const DATA_TEXT = {json.dumps(data)};\n"
        "const els = {}; const el = () => ({innerHTML: '', textContent: '', querySelectorAll: () => []});\n"
        "global.document = {getElementById: id => id === 'fa-data' ? {textContent: DATA_TEXT}"
        " : (els[id] = els[id] || el())};\n"
        f"{script}\nprocess.stdout.write(els['fa-table'].innerHTML);"
    )
    table = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True, encoding="utf-8").stdout
    rows = {
        re.match(r'<td class="name">([^<]*)', row).group(1).strip(): row
        for row in re.findall(r"<tr>(.*?)</tr>", table)
        if row.startswith('<td class="name">')
    }
    assert '<span class="flag next">Mon open</span>' in rows["Phi &amp; One"]
    assert '<span class="flag next">' not in rows["Chi One"]


def test_the_page_has_no_next_week_mark_with_no_days_to_check():
    html = render()
    assert "next Monday" not in text(html)
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert all(p["next_open"] == [] for p in data["players"])


def test_the_page_has_no_run_time_table_with_no_step_times():
    assert "Run time" not in render()
    html = render(timings=[timing.StepTime("schedule search", 1.234, 1200, 300)])
    assert "<td>1.23</td><td>1,200</td><td>300</td><td></td>" in html


def test_the_run_time_table_shows_the_pages_of_the_yahoo_reads_and_its_sub_steps():
    html = render(
        timings=[
            timing.StepTime("Yahoo reads", 31.34, pages=33),
            timing.StepTime("Yahoo reads: market pages", 7.5, pages=12, parent="Yahoo reads"),
        ]
    )
    assert '<td class="name">Yahoo reads</td><td>31.34</td><td></td><td></td><td>33</td>' in html
    assert '<td class="name sub">market pages</td><td>7.50</td><td></td><td></td><td>12</td>' in html


SKIP_LINE = (
    "The run skipped the recent view (last 14 days). The most games of one team from 14 days ago to today "
    "is 1, so w is 0.07 at most. This is below [adds] recent_skip_weight (0.3). The values use the projection "
    "only. A player with no projection is not a candidate."
)


def test_the_page_shows_why_the_market_read_stopped():
    lines = [
        lists.market_line(lists.MarketRead([], [], 2, "guard")),
        lists.market_line(lists.MarketRead([], [], 3, "limit")),
    ]
    assert lines == [
        "Market: 2 of 3 pages. Page 2 had no new player above the replacement value (the free agent at "
        "rank 15 of the players read before it).",
        "Market: 3 of 3 pages (the limit).",
    ]
    for line in lines:
        html = render(BASE, options=[PHI], market=line)
        assert f'<p class="legend" id="market-read">{line}</p>' in html
    assert 'id="market-read"' not in render(BASE, options=[PHI])


def run_script(html):
    """The free-agent table that the page script draws in Node, with a small fake page."""
    data = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    script = html.split('<script type="application/json" id="fa-data">')[1].split("<script>")[1].split("</script>")[0]
    code = (
        f"const DATA_TEXT = {json.dumps(data)};\n"
        "const els = {}; const el = () => ({innerHTML: '', textContent: '', querySelectorAll: () => []});\n"
        "global.document = {getElementById: id => id === 'fa-data' ? {textContent: DATA_TEXT}"
        " : (els[id] = els[id] || el())};\n"
        f"{script}\nprocess.stdout.write(JSON.stringify(Object.fromEntries("
        "Object.entries(els).map(([k, v]) => [k, v.innerHTML || v.textContent]))));"
    )
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True, encoding="utf-8").stdout
    return json.loads(out)


def test_the_page_script_puts_a_button_in_each_sort_header_and_names_the_chips_and_the_dots():
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    els = run_script(render())
    table = els["fa-table"]
    assert '<caption class="vh">Free agents, sorted by Val, highest first</caption>' in table
    assert (
        '<th class="sort " aria-sort="descending"><button type="button" data-sort="value">Val'
        '<span aria-hidden="true"> ▼</span></button></th>'
    ) in table
    assert '<th class="sort "><button type="button" data-sort="match">Match</button></th>' in table
    assert table.count("aria-sort") == 1
    assert 'role="img" aria-label="game in an open slot"' in table and 'role="img" aria-label="game"' in table
    # Mon has 2 open slots and 5 NBA games. The aria-label keeps the date and the two counts apart.
    assert 'aria-label="Mon 1/4, 2 open slots, 5 NBA games">Mon 1/4<small>2 open · 5 NBA</small>' in els["day-chips"]


def test_the_free_agent_count_is_a_polite_live_region():
    assert '<p class="count" id="fa-count" aria-live="polite"></p>' in render()


@contextmanager
def browser_page(width=720):
    """A Chromium page from Playwright. The test skips if Chromium is not installed (as in CI)."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Error as e:
            pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")
        try:
            yield browser.new_page(viewport={"width": width, "height": 900})
        finally:
            browser.close()


def test_a_keyboard_user_sorts_each_column_and_the_focus_stays_on_the_sort_button():
    with browser_page() as pg:
        pg.set_content(render())
        for name, key in (("Match", "match"), ("Recent", "recent"), ("Gms", "games"), ("Val", "value")):
            pg.get_by_role("button", name=name, exact=True).focus()
            pg.keyboard.press("Enter")
            th = pg.locator("th.sort[aria-sort]")
            assert th.count() == 1 and th.get_attribute("aria-sort") == "descending"
            assert th.locator("button").get_attribute("data-sort") == key
            assert "▼" in th.inner_text()
            assert pg.evaluate("document.activeElement.dataset.sort") == key
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.dataset.sort") == "match"
        pg.keyboard.press("Space")
        assert pg.locator("th.sort[aria-sort] button").get_attribute("data-sort") == "match"


def test_a_chip_press_toggles_the_chip_and_keeps_the_focus_on_it():
    with browser_page() as pg:
        pg.set_content(render())
        sf = pg.get_by_role("button", name="SF", exact=True)
        sf.focus()
        pg.keyboard.press("Enter")
        assert sf.get_attribute("aria-pressed") == "true"
        assert pg.evaluate("document.activeElement.textContent") == "SF"
        pg.keyboard.press("Space")
        assert sf.get_attribute("aria-pressed") == "false"
        mon = pg.get_by_role("button", name="Mon 1/4, 2 open slots, 5 NBA games", exact=True)
        mon.focus()
        pg.keyboard.press("Enter")
        assert mon.get_attribute("aria-pressed") == "true"
        assert pg.evaluate("document.activeElement.textContent").startswith("Mon 1/4")


def test_the_dots_the_count_and_the_caption_read_in_the_accessibility_tree():
    with browser_page() as pg:
        pg.set_content(render())
        tree = pg.locator("#fa-table").aria_snapshot()
        assert 'img "game in an open slot"' in tree and 'img "game"' in tree
        assert pg.get_by_role("table", name="Free agents, sorted by Val, highest first").count() == 1
        assert pg.locator("#fa-count").get_attribute("aria-live") == "polite"


def test_each_control_shows_a_focus_outline_in_light_and_dark_mode():
    with browser_page() as pg:
        pg.set_content(render())
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            for control in ("#day-chips button", "#pos-chips button", "th.sort button", "#fit-only", "summary"):
                pg.locator(control).first.focus()
                pg.keyboard.press("Shift+Tab")
                pg.keyboard.press("Tab")
                style = pg.evaluate(
                    "(() => { const s = getComputedStyle(document.activeElement);"
                    " return [s.outlineStyle, s.outlineWidth, s.outlineColor]; })()"
                )
                assert style[0] == "solid" and style[1] == "2px", (theme, control, style)
                bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                assert style[2] != bg, (theme, control)


def test_at_390px_the_chips_the_checkbox_label_and_the_summaries_are_24px_high_or_more():
    with browser_page(width=390) as pg:
        pg.set_content(render(timings=[timing.StepTime("Yahoo reads", 1.0)]))
        for control in ("#pos-chips button", "label.toggle", "details.notes summary", "th.sort button"):
            heights = pg.locator(control).evaluate_all(
                "els => els.filter(e => e.offsetParent).map(e => e.getBoundingClientRect().height)"
            )
            assert heights and min(heights) >= 24, (control, heights)


# The contrast of each visible text element against the background below it (WCAG 2.2, #115).
# The background is the sum of the backgrounds of the element and its parents, with their alpha.
CONTRAST = r"""() => {
  const rgb = s => { const p = s.match(/[\d.]+/g).map(Number);
    return s.startsWith("color(") ? [p[0] * 255, p[1] * 255, p[2] * 255, p[3] ?? 1] : [p[0], p[1], p[2], p[3] ?? 1]; };
  const over = (t, b) => [0, 1, 2].map(i => t[i] * t[3] + b[i] * (1 - t[3])).concat(1);
  const lum = c => c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const out = [], seen = new Set(), walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    const el = walk.currentNode.parentElement;
    if (!walk.currentNode.textContent.trim() || seen.has(el) || !el.getClientRects().length) continue;
    seen.add(el);
    const chain = []; for (let e = el; e; e = e.parentElement) chain.unshift(e);
    let bg = [255, 255, 255, 1], alpha = 1;
    for (const e of chain) { const s = getComputedStyle(e); bg = over(rgb(s.backgroundColor), bg); alpha *= +s.opacity; }
    const s = getComputedStyle(el), fg = rgb(s.color); fg[3] *= alpha;
    const [a, b] = [lum(over(fg, bg)), lum(bg)], ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700);
    if (ratio < (large ? 3 : 4.5)) out.push(`${el.tagName}.${el.className} "${el.textContent.trim()}" ${ratio.toFixed(2)}`);
  }
  return out;
}"""


def test_each_text_is_4_5_to_1_or_more_in_light_and_dark_mode_with_the_chips_pressed():
    # Tue is a back-to-back night of PHI in row 1, a zebra row. Wed has no open slot (a dashed chip).
    nights = {WEEK[1]: {"PHI"}}
    claim_row = SpotPlan(
        SPOTS[0],
        Plan(
            windows=(TeamWindow(0, "CHI", WEEK[2], WEEK[6], (WEEK[5], WEEK[6]), CLAIM, (CLAIM,)),),
            started_games=2,
            adds=1,
        ),
        2,
    )
    html = render(
        rows=[ROW1, ROW2, claim_row],
        options=OPTIONS + [CLAIM],
        nights=nights,
        cfg={**LEAGUE, "adds": {"minutes_rise": 3}},
        timings=[timing.StepTime("Yahoo reads", 1.0)],
    )
    assert html.count('class="b2b"') >= 2 and ">W</span>" in html
    with browser_page() as pg:
        pg.set_content(html)
        pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(CONTRAST) == [], theme
        wed = pg.locator("#day-chips button.none").first
        wed.click()
        pg.get_by_role("button", name="SF", exact=True).click()
        assert wed.get_attribute("aria-pressed") == "true"
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(CONTRAST) == [], f"{theme}, pressed"


# The run lines, the key and the empty state (#118).
MARKET = "Market: 3 of 3 pages (the limit)."
CACHE = "The recent view: 3 pages from the cache of 2027-01-04 09:14."


def test_the_run_lines_are_in_run_time_and_nothing_about_the_run_is_above_the_filters():
    html = render(market=MARKET, cache=CACHE, recent_skip=SKIP_LINE, timings=[timing.StepTime("Yahoo reads", 1.0)])
    section = html.split("<h2>Free agents</h2>")[1]
    above_filters = section.split('id="day-chips"')[0]
    assert text(above_filters).strip() == ""
    above_table = text(section.split('id="fa-table"')[0])
    for line in (MARKET, CACHE, SKIP_LINE):
        assert line not in above_table
        assert line in text(run_time(html))
    assert '<p class="skip" id="skip-note">' + page.SKIP_NOTE + "</p>" in section.split('id="fa-table"')[0]
    assert 'id="market-read"' in run_time(html) and 'id="cache-read"' in run_time(html)


def test_the_run_lines_show_in_run_time_also_with_no_step_times():
    html = render(market=MARKET)
    assert MARKET in text(run_time(html)) and "<th>Seconds</th>" not in run_time(html)


def test_a_run_with_the_recent_view_has_no_skip_note():
    assert 'id="skip-note"' not in render()


def test_the_page_has_no_side_stripe_border():
    # The styles of the adds page. A 1px rule between the stats is a separator, not a stripe. The site menu of
    # core/publish.py has its own styles.
    assert not re.search(r"border-(left|right)\s*:\s*(?!0\b|1px)\d", page.HTML)
    assert ".skip { font-size: 13px; color: var(--fg); border: 1.5px solid" in page.HTML


def test_the_key_of_the_dots_and_the_flags_is_above_the_free_agent_table():
    nmon = WEEK[6] + timedelta(days=1)
    html = render(next_days=[Day(nmon, 4, (), (), ("SF", "Util"))], next_games={nmon: {"PHI"}})
    section = html.split("<h2>Free agents</h2>")[1]
    key = re.search(r'<p class="key" id="fa-key">(.*?)</p>', section).group(1)
    assert section.index('id="fa-key"') < section.index('id="fa-table"')
    assert text(key) == text(
        "Key: game, open slot game, no open slot 2 back-to-back FA? unusual value UP role up Mon open slot next week"
    )
    assert '<span class="dot fit"></span>' in key and page.B2B in key
    # The long legends are in a <details> below the table.
    notes = section.split('id="fa-table"')[1]
    assert '<details class="notes" id="fa-notes"><summary>Columns and marks</summary>' in notes
    assert "Val: blended value per game" in text(notes.split("</details>")[0])
    assert "he has a game next Monday" in text(notes.split("</details>")[0])


def test_the_key_shows_the_minutes_flag_only_with_role_lines():
    assert "MIN+" not in re.search(r'id="fa-key">(.*?)</p>', render()).group(1)
    role = Role(26.0, 20.0, 4, 3, 1, 2, True)
    html = render(roles={("Phi One", "PHI"): role}, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0}})
    assert "MIN+</span> more minutes" in re.search(r'id="fa-key">(.*?)</p>', html).group(1)


def test_the_legends_are_75_characters_wide_at_most():
    assert ".legend { font-size: 12px; margin-top: 6px; max-width: 75ch; }" in render()


def test_with_no_match_the_page_shows_a_message_and_a_button_that_clears_the_days():
    with browser_page() as pg:
        pg.set_content(render())
        assert pg.locator("#fa-empty").is_hidden()
        # PHI plays on Mon and CHI plays on Sun. No free agent plays on both days.
        pg.get_by_role("button", name="Mon 1/4", exact=False).first.click()
        pg.locator("#day-chips button").nth(6).click()
        assert pg.locator("#fa-empty").is_visible()
        assert pg.locator("#fa-table").is_hidden()
        assert pg.locator("#fa-empty-text").inner_text() == "No free agent plays on all selected days."
        assert pg.locator("#fa-count").inner_text() == "0 free agents match the filters"
        pg.get_by_role("button", name="Clear days").click()
        assert pg.locator("#fa-empty").is_hidden() and pg.locator("#fa-table").is_visible()
        assert pg.locator('#day-chips button[aria-pressed="true"]').count() == 0
        assert pg.evaluate("document.activeElement.textContent").startswith("Mon 1/4")


def test_the_reset_button_restores_the_default_filters_and_sort():
    with browser_page() as pg:
        pg.set_content(render())
        default = pg.locator("#fa-table").inner_html()
        pg.locator("#day-chips button").nth(5).click()
        pg.get_by_role("button", name="SF", exact=True).click()
        pg.locator("#fit-only").uncheck()
        pg.get_by_role("button", name="Gms", exact=True).click()
        assert pg.locator("#fa-table").inner_html() != default
        pg.get_by_role("button", name="Reset filters").click()
        assert pg.locator('button.chip[aria-pressed="true"]').count() == 0
        assert pg.locator("#fit-only").is_checked()
        assert pg.locator("th.sort[aria-sort] button").get_attribute("data-sort") == "value"
        assert pg.locator("#fa-table").inner_html() == default
        assert pg.evaluate("document.activeElement.id") == "fa-reset"


def test_the_page_of_a_fixed_run_is_the_page_of_render_before_the_planning_run(monkeypatch):
    """#128: fixtures/page_before_128.html is the HTML of render() before the PlanningRun, from the same values in
    the old parameters. The page has each section.

    #132: the page is also the same as before publish.shell(). The render reads no config.toml: the team count of
    the menu comes from run.cfg (14 teams, as in config.toml when the fixture was made).
    """
    monkeypatch.setattr(site, "load_config", lambda: pytest.fail("The render read config.toml."))
    nmon = WEEK[6] + timedelta(days=1)
    claim_window = TeamWindow(0, "CHI", WEEK[2], WEEK[6], (WEEK[5], WEEK[6]), CLAIM, (CLAIM,))
    claim_row = SpotPlan(SPOTS[0], Plan(windows=(claim_window,), started_games=2, adds=1), 2)
    flags = {
        "window_games": 10, "min_games": 5, "close_window": 8, "min_close_games": 4, "new_games": 3,
        "new_closes": 2, "regular_share": 0.7, "some_share": 0.2,
    }  # fmt: skip
    flag_guy, flag_two = Player("Flag Guy", "PHI", ("PG",), status="Q"), Player("Flag Two", "CHI", ("C",), status="D")
    run = replace(
        RUN,
        data=replace(DATA, matchup=Matchup("Rival", {"pts": 300, "blk": 8}, {"pts": 290, "blk": 10})),
        rows=[ROW1, ROW2, claim_row],
        options=OPTIONS + [CLAIM, Option(Player("Up Guy", "PHI", ("PF",)), 0.2, role_up=("Star Wing",))],
        warnings=["Warning: a & b."],
        weights={"pts": 1.0, "blk": 0.75},
        match_replacement=0.1,
        nights={WEEK[1]: {"PHI"}},
        contingencies=[
            Contingency(flag_guy, WEEK[1], "19:30", move=Player("Bench", "PHI", ("PG",))),
            Contingency(flag_two, WEEK[5], None, late_adds=((PHI, "21:00"),)),
        ],
        roles={("Phi & One", "PHI"): Role(28.0, 22.0, 4, 3, 1, 2, True, "Regular", "New")},
        cfg={**LEAGUE, "adds": {"minutes_rise": 4.0, "flags": flags}},
        next_days=[Day(nmon, 4, (), (), ("SF", "Util"))],
        next_games={nmon: {"PHI"}},
        timings=[
            timing.StepTime("Yahoo reads", 1.5, pages=3),
            timing.StepTime("Yahoo reads: trends", 0.5, pages=3, parent="Yahoo reads"),
            timing.StepTime("schedule search", 2.25, 100, 40),
        ],
        recent_skip=SKIP_LINE,
        market=MARKET,
        cache="The recent view: 3 pages from the cache.",
    )
    before = (Path(__file__).parent / "fixtures" / "page_before_128.html").read_text(encoding="utf-8")
    assert page.render(run) == before
