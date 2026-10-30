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
from fantasyhoops.adds.matchup import Matchup, matchup_weights, read_matchup
from fantasyhoops.adds.planner import Option, StreamSpot, TeamRank
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.roles import Role
from fantasyhoops.adds.slots import Day
from fantasyhoops.adds.team_plan import UTIL
from fantasyhoops.adds.week_file import SavedAdd, WeekRecord
from fantasyhoops.core import roster as roster_page
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
# The team plan of the run of Mon (#140). Row 1: +SF PHI on Mon, then +PF CHI on Sun. Row 2: +Util from 8 teams on Tue.
EIGHT = ("ATL", "BKN", "BOS", "GS", "IND", "LAC", "LAL", "ORL")
ADDS = (
    SavedAdd(1, WEEK[0], ("SF",), ("PHI",), (WEEK[0], WEEK[1], WEEK[5])),
    SavedAdd(2, WEEK[1], (UTIL,), EIGHT, (WEEK[1], WEEK[5])),
    SavedAdd(1, WEEK[6], ("PF",), ("CHI",), (WEEK[6],)),
)
RECORD = WeekRecord(runs=(WEEK[0],), adds=ADDS)
WEEK_GAMES = {d: n for d, n in zip(WEEK, (12, 4, 9, 6, 2, 10, 4))}
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
RUN = replace(
    BASE, record=RECORD, week_games=WEEK_GAMES, options=OPTIONS, ranking=RANKING, read=["PHI"], replacement=0.5
)


def render(run=RUN, **fields):
    """The page of run (default: RUN), with the fields of fields changed."""
    return page.render(replace(run, **fields))


def fa(run=RUN, **fields):
    """The Free agents page (#165) of run (default: RUN), with the fields of fields changed."""
    return page.render_free_agents(replace(run, **fields))


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


def test_the_page_shows_the_week_and_the_adds_left():
    shown = text(render())
    assert "Week 12: Mon 1/4 to Sun 1/10" in shown and "4 of 5 adds left" in shown and "2 stream spots" in shown
    assert "Out (does not play): Hurt Guy (O)" in shown


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
    # One column for each category, and the rows You, Opp, Margin and Weight (#144).
    assert "PTS 3PTM BLK You 300 40 8 Opp 290 25 10 Margin +10 +15 -2 Weight 1.00 0.50 1.00" in shown
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
    assert "PTS REB AST 3PTM BLK ST You 24 4 9 4 0 1 Opp 45 17 14 5 3 1" in shown
    assert "Margin -21 -13 -5 -1 -3 +0 Weight 1.00 0.99 1.00 1.00 0.95 1.00" in shown
    assert "Opponent" not in html


# A matchup of each state (#144), with the margins of config.toml for a whole week (share_left 1).
MU_CFG = {
    "weights": {c: 1.0 for c in ("pts", "reb", "ast", "threes", "blk", "stl")},
    "adds": {
        "matchup": {
            "close": {"pts": 40, "reb": 15, "ast": 10, "threes": 5, "blk": 3, "stl": 3},
            "large": {"pts": 120, "reb": 45, "ast": 30, "threes": 15, "blk": 9, "stl": 9},
            "min_weight": 0.5,
        }
    },
}
# PTS +10: close. REB -45: a large deficit. AST +20: a lead. 3PTM +15: a large lead. BLK -4: a deficit. ST 0: tied.
MU = Matchup(
    "Rival",
    {"pts": 410, "reb": 150, "ast": 120, "threes": 45, "blk": 10, "stl": 20},
    {"pts": 400, "reb": 195, "ast": 100, "threes": 30, "blk": 14, "stl": 20},
)
MU_RUN = replace(
    RUN, data=replace(DATA, matchup=MU), weights=matchup_weights(MU, MU_CFG, 1.0), cfg={**LEAGUE, **MU_CFG}
)


def matchup_rows(html):
    """{row label: [the class of each cell]} of the matchup table."""
    table = re.search(r'<table class="mu">.*?</table>', html, re.S).group(0)
    rows = re.findall(r'<th scope="row" class="name">(\w+)</th>(.*?)</tr>', table)
    return {label: re.findall(r'<td(?: class="([^"]*)")?>', cells) for label, cells in rows}


def test_the_margin_and_the_weight_cells_get_the_class_of_the_state_of_the_category():
    html = page.render(MU_RUN)
    rows = matchup_rows(html)
    assert rows["Margin"] == ["", "trail big", "lead", "lead big", "trail", ""]
    # Weights: 1, 0.5, 0.75, 0.5, 0.92 and 1. The steps: w1 above 0.83, w2 above 0.67, w3 to 0.5.
    assert rows["Weight"] == ["w0", "w3", "w2", "w3", "w1", "w0"]
    assert rows["You"] == [""] * 6
    assert 'id="mu-key"' in html and "a deficit" in text(html)
    # The matchup section is above the team plan (#144).
    assert html.index('<section id="matchup">') < html.index('id="plan"')


def test_margin_class_and_weight_class():
    assert page.margin_class(10, 1.0, 0.5) == "" and page.margin_class(0, 0.5, 0.5) == ""
    assert page.margin_class(-20, 0.7, 0.5) == "trail" and page.margin_class(50, 0.5, 0.5) == "lead big"
    assert [page.weight_class(w, 0.5) for w in (1.0, 0.9, 0.8, 0.6, 0.5)] == ["w0", "w1", "w2", "w3", "w3"]


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
        fa(roles=roles, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0, "flags": load_config()["adds"]["flags"]}})
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
    html = fa(roles=roles, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0}})
    assert "Starts 1/5 (Inconsistent) · Closes 0/4" in html
    assert "Closes 0/4 (" not in html  # no closer flag: no word after the closes
    assert "Starts 5/5 (New) · Closes 4/4 (Regular)" in html


def test_the_page_has_no_role_legend_with_no_rotation_log():
    assert "Min: his mean minutes" not in text(fa())


def test_the_page_holds_the_free_agent_data_as_safe_json():
    html = fa()
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert json.loads(raw)["players"][1]["name"] == "Phi & One"
    evil = fa(BASE, options=[option("</script><b>", "PHI", 1.0)])
    assert "</script><b>" not in evil and "http" not in evil.split("</head>")[1]


def test_the_page_explains_why_there_is_no_plan():
    assert "No adds left this week (5 of 5 used)" in text(
        render(BASE, data=command.LeagueData([], Adds(5, 5), DATA.week))
    )
    assert "No stream spots" in text(render(BASE, spots=[]))
    assert "No NBA team gives a started game in an open slot." in text(render(BASE))
    # No options: no free-agent table and no script.
    assert "fa-data" not in render(BASE)


CLAIM = Option(Player("Claim Guy", "CHI", ("C",), clear_day=WEEK[1]), 1.2)


def test_the_page_lists_the_waiver_players_with_the_clear_day():
    html = fa(options=OPTIONS + [CLAIM])
    shown = text(html)
    assert "Waiver players" in shown
    assert "CHI Claim Guy W CHI · C Tue 1/5 Wed 1/6 +0.70" in shown
    # The free-agent table holds only the players with status FA.
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert "Claim Guy" not in [p["name"] for p in json.loads(raw)["players"]]


# A roster of one player for the Roster page: one playoff day.
HOME_ARGS = (
    [roster_page.RosterPlayer("Guard One", "BOS", ("PG",), "PG", rank=1)],
    [roster_page.Day(WEEK[0], "wk19", False, frozenset({"BOS"}), frozenset())],
    {"league": {"slots": ["PG"], "espn_season": 2027, "teams": 14}, "flags": {"avoid_week_games": 1}},
)


def test_the_home_page_and_the_adds_page_get_the_table_css_from_the_same_source():
    """#143: publish.TABLE_STYLE is the one source of the table CSS. No page holds a copy of its rules."""
    adds_html = fa(options=OPTIONS + [CLAIM])
    home_html = site.shell(roster_page.PAGE_HTML, "home", LEAGUE)
    for html in (adds_html, home_html):
        assert html.count(site.TABLE_STYLE) == 1
    for own in (page.HTML, roster_page.PAGE_HTML):
        assert "__TABLE_CSS__" in own
        for rule in (".lab-t td.band", ".lab-t .pl b", ".lab-t th.pl"):
            assert rule not in own.replace("__TABLE_CSS__", ""), rule
    assert '<table class="desk lab-t">' in roster_page.render(*HOME_ARGS)
    assert (
        '<table class="fa lab-t" id="fa-table">' in adds_html and '<table class="wv lab-t" id="wv-table">' in adds_html
    )


def test_the_waiver_table_has_the_team_band_and_the_player_cell_of_the_roster_table():
    html = fa(options=OPTIONS + [CLAIM])
    table = html.split('id="wv-table">')[1].split("</table>")[0]
    assert f'<td class="band" style="{site.band_style("CHI")}">CHI</td>' in table
    assert (
        '<th class="pl" scope="row"><b><a class="lab-pname" href="#player=claim-guy" data-player="claim-guy">Claim Guy</a></b> <span class="status"'
        in table
    )
    assert "<small>CHI · C</small></th>" in table


def test_the_page_has_no_waiver_section_with_no_waiver_players():
    assert "Waiver players" not in text(fa())


def test_the_page_shows_the_site_menu_with_the_adds_plan_current():
    html = render()
    assert (
        html.index('<body class="lab">') < html.index('<nav class="lab-menu"') < html.index('<main class="lab-main">')
    )
    assert (
        '<a href="../adds/" aria-current="page">Adds plan</a>' in html
        and '<a href="../roster/">Roster</a>' in html
        and '<a href="../">Home</a>' in html
    )
    assert ">Auto</button>" in html and ">Light</button>" in html and ">Dark</button>" in html
    assert html.index("<h1>") > html.index("</nav>")
    assert html.rstrip().endswith(f"{site.MENU_SCRIPT}\n</body>\n</html>")


def test_the_page_sets_the_saved_theme_in_the_head_and_uses_the_shared_tokens():
    head = render().split("</head>")[0]
    assert tokens.HEAD in head and head.index(tokens.THEME_SCRIPT) < head.index("<style>")
    assert "font-family: Archivo" in head and "var(--lab-face)" in head


def test_the_page_css_has_no_colors_of_its_own():
    """#117: the colors come from core/tokens.py. The page CSS uses only var(--...)."""
    # The theme-color tags (#166) take the lab-blue values of core/tokens.py.
    css = re.sub(r'<meta name="theme-color"[^>]*>', "", render().split("</head>")[0].replace(tokens.HEAD, ""))
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", page.SCRIPT)


def test_the_page_marks_the_second_game_of_each_back_to_back():
    # PHI plays Mon and Tue, so Tue is a second night. CHI plays Sat and Sun, so Sun is a second night.
    nights = {WEEK[1]: {"PHI"}, WEEK[6]: {"CHI"}}
    assert "second game of a back-to-back" in text(fa(nights=nights))
    data = page.free_agent_data(OPTIONS, DAYS, GAMES, replacement=0.5, nights=nights)
    assert data["players"][2]["b2b"] == [False, False, False, False, False, False, True]  # Chi One
    assert data["players"][1]["b2b"] == [False, True, False, False, False, False, False]  # Phi & One


def test_the_free_agent_data_and_the_page_show_the_role_up_mark_and_the_absent_teammate():
    marked = replace(PHI, role_up=("Star Wing",))
    data = page.free_agent_data([marked, CHI], DAYS, GAMES, replacement=0.5)
    assert [p["role_up"] for p in data["players"]] == [["Star Wing"], []]
    shown = text(fa(BASE, options=[marked, CHI]))
    assert "Role up" in shown
    assert "Star Wing is absent. Role up: Phi & One (PHI)." in shown
    assert "role up" in page.SCRIPT


def test_the_page_has_no_role_up_section_with_no_mark():
    assert "Role up" not in text(fa())


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
    html = fa(next_days=early, next_games=early_games)
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
    html = fa(next_days=[Day(nmon, 4, (), (), ("SF", "Util"))], next_games={nmon: {"PHI"}})
    data = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    script = html.split('<script type="application/json" id="fa-data">')[1].split("<script>")[1].split("</script>")[0]
    # A small page: the elements that the script uses, with the JSON data of the page.
    code = (
        f"const DATA_TEXT = {json.dumps(data)};\n"
        "const els = {}; const el = () => ({innerHTML: '', textContent: '', querySelectorAll: () => []});\n"
        "global.location = {search: '', hash: '', pathname: ''};\n"
        "global.document = {getElementById: id => id === 'fa-data' ? {textContent: DATA_TEXT}"
        " : (els[id] = els[id] || el())};\n"
        f"{script}\nprocess.stdout.write(els['fa-table'].innerHTML);"
    )
    table = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True, encoding="utf-8").stdout
    rows = {
        re.search(r'<th class="pl" scope="row"><b>(?:<a [^>]*>)?([^<]*)', row).group(1).strip(): row
        for row in re.findall(r"<tr>(.*?)</tr>", table)
        if '<th class="pl" scope="row">' in row
    }
    assert '<span class="flag next">Mon open</span>' in rows["Phi &amp; One"]
    assert '<span class="flag next">' not in rows["Chi One"]


def test_the_page_has_no_next_week_mark_with_no_days_to_check():
    html = fa()
    assert "next Monday" not in text(html)
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert all(p["next_open"] == [] for p in data["players"])


def test_the_page_has_no_run_time_table_with_no_step_times():
    assert "Run time" not in render()
    html = render(timings=[timing.StepTime("team plan", 1.234, 1200, 300)])
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
        "global.location = {search: '', hash: '', pathname: ''};\n"
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
    els = run_script(fa())
    table = els["fa-table"]
    assert '<caption class="vh">Free agents, sorted by Val, highest first</caption>' in table
    assert (
        '<th class="sort s1" aria-sort="descending"><button type="button" data-sort="value">Val'
        '<span aria-hidden="true"> ▼</span></button></th>'
    ) in table
    assert '<th class="sort "><button type="button" data-sort="match">Match</button></th>' in table
    assert table.count("aria-sort") == 1
    assert 'role="img" aria-label="game in an open slot"' in table and 'role="img" aria-label="game"' in table
    # Mon has 2 open slots and 5 NBA games. The aria-label keeps the date and the two counts apart.
    assert 'aria-label="Mon 1/4, 2 open slots, 5 NBA games">Mon 1/4<small>2 open · 5 NBA</small>' in els["day-chips"]


def test_the_free_agent_count_is_a_polite_live_region():
    assert '<p class="count" id="fa-count" aria-live="polite" tabindex="-1"></p>' in fa()


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
        pg.set_content(fa())
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
        pg.set_content(fa())
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
        pg.set_content(fa())
        tree = pg.locator("#fa-table").aria_snapshot()
        assert 'img "game in an open slot"' in tree and 'img "game"' in tree
        assert pg.get_by_role("table", name="Free agents, sorted by Val, highest first").count() == 1
        assert pg.locator("#fa-count").get_attribute("aria-live") == "polite"


def test_each_control_shows_a_focus_outline_in_light_and_dark_mode():
    with browser_page() as pg:
        pg.set_content(fa())
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
        pg.set_content(fa(timings=[timing.StepTime("Yahoo reads", 1.0)]))
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
    # The matchup table (MU, #144) has each margin state and each weight step.
    # #165: the plan page has the matchup table and Run time. The Free agents page has the chips and the tables.
    nights = {WEEK[1]: {"PHI"}}
    fields = dict(
        options=OPTIONS + [CLAIM],
        nights=nights,
        cfg={**LEAGUE, "adds": {**MU_CFG["adds"], "minutes_rise": 3}},
        timings=[timing.StepTime("Yahoo reads", 1.0)],
    )
    plan, html = render(MU_RUN, **fields), fa(MU_RUN, **fields)
    assert html.count('class="b2b"') >= 1 and ">W</span>" in html
    assert all(f'class="{c}"' in plan for c in ("lead", "trail big", "lead big", "trail", "w0", "w1", "w2", "w3"))
    with browser_page() as pg:
        for doc in (plan, html):
            pg.set_content(doc)
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
    fields = dict(market=MARKET, cache=CACHE, recent_skip=SKIP_LINE, timings=[timing.StepTime("Yahoo reads", 1.0)])
    html = render(**fields)
    section = fa(**fields).split("<h2>Free agents</h2>")[1]
    # #165: Run time is on the plan page. The skip note links to it.
    assert "Run time" not in fa(**fields).split("<h2>Free agents</h2>")[1].split('id="skip-note"')[0]
    assert 'href="../adds/#run-time"' in page.SKIP_NOTE
    above_filters = section.split('id="day-chips"')[0]
    # Only the hidden line of the plan filters (issue 140) is above the filters.
    assert text(re.sub(r'<p class="from" id="fa-from" hidden>.*?</p>', "", above_filters)).strip() == ""
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
    assert 'id="skip-note"' not in fa()


def test_the_page_has_no_side_stripe_border():
    # The styles of the adds page. A 1px rule between the stats is a separator, not a stripe. The site menu of
    # core/publish.py has its own styles.
    assert not re.search(r"border-(left|right)\s*:\s*(?!0\b|1px)\d", page.HTML)
    assert ".skip { font-size: 13px; color: var(--fg); border: 1.5px solid" in page.HTML


def test_the_key_of_the_dots_and_the_flags_is_above_the_free_agent_table():
    nmon = WEEK[6] + timedelta(days=1)
    html = fa(next_days=[Day(nmon, 4, (), (), ("SF", "Util"))], next_games={nmon: {"PHI"}})
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
    assert "MIN+" not in re.search(r'id="fa-key">(.*?)</p>', fa()).group(1)
    role = Role(26.0, 20.0, 4, 3, 1, 2, True)
    html = fa(roles={("Phi One", "PHI"): role}, cfg={**LEAGUE, "adds": {"minutes_rise": 4.0}})
    assert "MIN+</span> more minutes" in re.search(r'id="fa-key">(.*?)</p>', html).group(1)


def test_the_legends_are_75_characters_wide_at_most():
    assert ".legend { font-size: 12px; margin-top: 6px; max-width: 75ch; }" in render()


def test_with_no_match_the_page_shows_a_message_and_a_button_that_clears_the_days():
    with browser_page() as pg:
        pg.set_content(fa())
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
        pg.set_content(fa())
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


# The team plan (#140): the week grid of a run on Wed. Mon and Tue are past and show the saved adds of their runs.
# Row 1 has a long list of 5 teams, so its cell must wrap. Row 1 on Sun has the count of 8 teams.
GRID_ADDS = (
    SavedAdd(1, WEEK[0], ("SG",), ("MIA",), (WEEK[0], WEEK[1])),
    SavedAdd(2, WEEK[1], ("PG", "SG"), ("POR", "SAC"), (WEEK[1],)),
    SavedAdd(1, WEEK[3], ("SG", "PF"), ("ATL", "CLE", "MEM", "PHI", "SAC"), (WEEK[3], WEEK[5])),
    SavedAdd(2, WEEK[3], ("PF",), ("CHI",), (WEEK[3], WEEK[5])),
    SavedAdd(1, WEEK[6], (UTIL,), EIGHT, (WEEK[6],)),
)
# The run also has the matchup of each state (MU, #144), so the fit test and the contrast test check its table.
GRID_RUN = replace(
    MU_RUN, today=WEEK[2], days=DAYS[2:], record=WeekRecord(runs=(WEEK[0], WEEK[1], WEEK[2]), adds=GRID_ADDS)
)

# The matchup table (#144): the 6 category columns and each cell are inside the page, and no cell scrolls sideways.
MATCHUP_FIT = r"""width => {
  const bad = [], table = document.querySelector("#matchup table.mu"), t = table.getBoundingClientRect();
  if (t.left < 0 || t.right > width) bad.push(`the table is ${t.left} to ${t.right}`);
  if (table.querySelectorAll("thead th[scope=col]").length !== 6) bad.push("not 6 category columns");
  table.querySelectorAll("th, td").forEach(c => {
    const r = c.getBoundingClientRect();
    if (r.right > t.right + 0.5 || c.scrollWidth > c.clientWidth + 1) bad.push(`"${c.textContent}" leaves its cell`);
  });
  return bad;
}"""

# The tables of the Roster look (#143): the run of GRID_RUN, with a free agent and a waiver player with a long name.
LONG = option("Nickeil Alexander-Walker", "PHI", 0.8, ("SG", "SF"))
WAIVER = Option(Player("Jonas Valanciunas", "CHI", ("C",), clear_day=WEEK[3]), 0.9)
TABLE_RUN = replace(GRID_RUN, options=GRID_RUN.options + [LONG, WAIVER])

# The free-agent table and the waiver table (#143): each table is inside the page, and each child box of a cell
# is inside the cell, with no sideways scroll of a cell.
TABLE_FIT = r"""width => {
  const bad = [], inside = (r, c) => r.left >= c.left - 0.5 && r.right <= c.right + 0.5
    && r.top >= c.top - 0.5 && r.bottom <= c.bottom + 0.5;
  ["#fa-table", "#wv-table"].forEach(id => {
    const table = document.querySelector(id), t = table.getBoundingClientRect();
    if (t.left < 0 || t.right > width) bad.push(`${id} is ${t.left} to ${t.right}`);
    table.querySelectorAll("thead th, thead td, tbody th, tbody td").forEach(c => {
      const box = c.getBoundingClientRect();
      if (c.scrollWidth > c.clientWidth + 1) bad.push(`${id}: "${c.textContent}" scrolls sideways`);
      c.querySelectorAll("*").forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width || r.height) && !inside(r, box)) bad.push(`${id}: "${el.textContent}" leaves its cell`);
      });
    });
  });
  return bad;
}"""


# For each add cell and each band cell: each child box must be inside the cell box and inside the add box.
FIT = r"""() => {
  const bad = [], inside = (r, c) => r.left >= c.left - 0.5 && r.right <= c.right + 0.5
    && r.top >= c.top - 0.5 && r.bottom <= c.bottom + 0.5;
  document.querySelectorAll("#plan td.add, #plan td.band").forEach((td, i) => {
    const c = td.getBoundingClientRect();
    td.querySelectorAll("*").forEach(el => {
      const r = el.getBoundingClientRect();
      if ((r.width || r.height) && !inside(r, c)) bad.push(`cell ${i}: "${el.textContent.trim()}" leaves the cell`);
    });
    td.querySelectorAll(".addc").forEach(box => {
      const k = box.getBoundingClientRect();
      box.querySelectorAll("*").forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width || r.height) && !inside(r, k)) bad.push(`cell ${i}: "${el.textContent.trim()}" leaves the add box`);
      });
      if (box.scrollHeight > box.clientHeight + 1 || box.scrollWidth > box.clientWidth + 1)
        bad.push(`cell ${i}: the content is larger than the add box`);
    });
    if (td.scrollWidth > td.clientWidth + 1) bad.push(`cell ${i} scrolls sideways`);
  });
  return bad;
}"""


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_each_add_cell_and_band_fits_its_cell_and_the_page_has_no_horizontal_scroll(width):
    with browser_page(width=width) as pg:
        # #165: the free-agent table and the waiver table are on the Free agents page.
        pg.set_content(page.render_free_agents(TABLE_RUN))
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(TABLE_FIT, width) == [], (width, theme)
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme, "free agents")
            assert pg.evaluate(CONTRAST) == [], (width, theme, "free agents")
        pg.set_content(page.render(TABLE_RUN))
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(FIT) == [], (width, theme)
            assert pg.evaluate(MATCHUP_FIT, width) == [], (width, theme)
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme)
            # The 7 columns of the week fit, with no sideways scroll of the grid.
            assert pg.locator("#plan thead th[scope=col]").count() == 8
            box = pg.locator("#plan table.week").bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width, (width, theme)
        # The long team list wraps inside its cell: the row grows, and each team is on its own line.
        teams = pg.locator("#plan a.addc").nth(0).locator(".who span")
        tops = teams.evaluate_all("els => els.map(e => e.getBoundingClientRect().top)")
        assert len(tops) == 5 and tops == sorted(tops) and len(set(tops)) == 5


# The contrast of each text of an element (and its children) against the solid background behind it.
CELL_CONTRAST = r"""root => {
  const rgb = s => { const p = s.match(/[\d.]+/g).map(Number);
    return s.startsWith("color(") ? [p[0] * 255, p[1] * 255, p[2] * 255, p[3] ?? 1] : [p[0], p[1], p[2], p[3] ?? 1]; };
  const lum = c => c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor);
    if (c[3] > 0.99) return c; } return [255, 255, 255, 1]; };
  const out = [];
  [root, ...root.querySelectorAll("*")].forEach(el => {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own || !el.getClientRects().length) return;
    const r = ratio(rgb(getComputedStyle(el).color), bgOf(el));
    if (r < 4.5) out.push(`"${el.textContent.trim()}" ${r.toFixed(2)}`);
  });
  return out;
}"""

BAND_CONTRAST = r"""() => {
  const rgb = s => { const p = s.match(/[\d.]+/g).map(Number);
    return s.startsWith("color(") ? [p[0] * 255, p[1] * 255, p[2] * 255] : p.slice(0, 3); };
  const lum = c => c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const out = [];
  document.querySelectorAll("#plan td.band").forEach((td, i) => {
    const bg = rgb(getComputedStyle(td).backgroundColor), bar = td.querySelector(".bar"), mk = td.querySelector(".mk");
    const pairs = [["band", getComputedStyle(bar, "::before").backgroundColor]];
    if (mk) pairs.push(["mark", getComputedStyle(mk).backgroundColor]);
    pairs.forEach(([name, c]) => { const r = ratio(rgb(c), bg); if (r < 4.5) out.push(`${name} ${i} ${r.toFixed(2)}`); });
  });
  return out;
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_each_add_cell_day_header_band_and_mark_has_4_5_to_1_in_each_state_and_theme(width):
    with browser_page(width=width) as pg:
        pg.set_content(page.render(TABLE_RUN))
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")

            def check(state, el):
                cell = el.evaluate_handle("e => e.closest('td, th')")
                assert pg.evaluate(CELL_CONTRAST, cell) == [], (theme, width, state, el.text_content())

            links = pg.locator("#plan a")
            assert links.count() == 3 + 5  # the adds of Thu (2) and Sun, and the day headers of Wed to Sun
            # #165: a plan cell is a link to the Free agents page, so it has no selected state.
            for i in range(links.count()):
                el = links.nth(i)
                el.scroll_into_view_if_needed()
                pg.mouse.move(0, 0)
                check("default", el)
                el.hover()
                check("hover", el)
                pg.mouse.move(0, 0)
                el.focus()
                pg.keyboard.press("Shift+Tab")
                pg.keyboard.press("Tab")
                assert pg.evaluate("getComputedStyle(document.activeElement).outlineStyle") == "solid"
                check("focus", el)
                el.evaluate("e => e.blur()")
            for past in (pg.locator("#plan .addc.was"), pg.locator("#plan thead th.past")):
                assert past.count() == 2
                for j in range(past.count()):
                    check("past", past.nth(j))
            assert pg.evaluate(BAND_CONTRAST) == [], (theme, width)
            # Each cell of the matchup table and its key (#144): each color of the Margin row and the Weight row.
            matchup = pg.locator("#matchup")
            assert matchup.locator("td.lead, td.trail, td.w0, td.w1, td.w2, td.w3").count() == 10
            assert pg.evaluate(CELL_CONTRAST, matchup.element_handle()) == [], (theme, width, "matchup")
            assert pg.locator("#plan td.band.past .mk").count() == 1  # the Mon add starts on Tue (past)
        # Each text of the free-agent table and the waiver table (#143) on the Free agents page (#165): the bands,
        # the names, the tags and the values.
        pg.set_content(page.render_free_agents(TABLE_RUN))
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            for table in ("#fa-table", "#wv-table"):
                assert pg.evaluate(CELL_CONTRAST, pg.locator(table).element_handle()) == [], (theme, width, table)


# The chart audit of the adds page (#190). Row 1 has its first add on Fri, so the grid has empty add cells on Wed and
# Thu, which are not past. Row 2 has a past add on Tue and an add on Thu with a band and a start square.
AUDIT_RUN = replace(
    TABLE_RUN,
    record=WeekRecord(
        runs=(WEEK[0], WEEK[1], WEEK[2]),
        adds=(
            SavedAdd(2, WEEK[1], ("PG",), ("POR",), (WEEK[1],)),
            SavedAdd(1, WEEK[4], ("SG", "PF"), ("ATL", "CLE"), (WEEK[4], WEEK[5])),
            SavedAdd(2, WEEK[3], ("PF",), ("CHI",), (WEEK[3], WEEK[5])),
        ),
    ),
)

# The computed look of each of the 7 spots of the audit, from the plan page in a browser.
AUDIT_LOOK = r"""() => {
  const css = (sel, prop, pseudo) => { const el = document.querySelector(sel);
    return el ? getComputedStyle(el, pseudo || null)[prop] : "missing"; };
  // The lab-stock ground in the color form of a heat cell: a 0% mix of mark.
  const probe = document.createElement("i");
  probe.style.background = "color-mix(in srgb, var(--mark) 0%, var(--lab-stock))"; document.body.append(probe);
  const stockRgb = getComputedStyle(probe).backgroundColor; probe.remove();
  const empty = [...document.querySelectorAll("#plan tr.add td:not(.past):not(.add):not(.band)")];
  return {
    empty: empty.length, emptyGrounds: [...new Set(empty.map(td => getComputedStyle(td).backgroundColor))],
    stock: stockRgb,
    gamesRule: css("#plan tr.games td", "borderBottomWidth"),
    gamesWeight: css("#plan tr.games td", "fontWeight"),
    addBorder: css("#plan a.addc", "borderTopWidth") + " " + css("#plan a.addc", "borderLeftWidth"),
    pastBorder: css("#plan .addc.was", "borderTopWidth"),
    muZebra: css("#matchup tbody tr:nth-child(even) td", "backgroundColor"),
    muHeadRule: css("#matchup thead th", "borderBottomWidth"),
    h2Rule: css("#plan h2", "borderBottomWidth"),
    band: css("#plan td.band:not(.past) .bar", "height", "::before"),
    square: css("#plan td.band:not(.past) .mk", "width"),
  };
}"""


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_the_plan_page_shows_the_7_changes_of_the_chart_audit(width):
    """#190: the heat stops at an empty add cell, a 1px Games rule, a 1px add cell border, a plain matchup table, a
    1px heading rule, a 2px band with a 10px square (8px below 600px) and regular Games numbers."""
    with browser_page(width=width) as pg:
        pg.set_content(page.render(AUDIT_RUN))
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            look = pg.evaluate(AUDIT_LOOK)
            assert look["empty"] >= 2 and look["emptyGrounds"] == [look["stock"]], (theme, look)
            assert look["gamesRule"] == "1px" and look["gamesWeight"] == "400", (theme, look)
            assert look["addBorder"] == "1px 1px" and look["pastBorder"] == "1px", (theme, look)
            assert look["muZebra"] == "rgba(0, 0, 0, 0)" and look["muHeadRule"] == "1px", (theme, look)
            assert look["h2Rule"] == "1px", (theme, look)
            assert look["band"] == "2px" and look["square"] == ("10px" if width >= 600 else "8px"), (theme, look)
            assert pg.evaluate(BAND_CONTRAST) == [], (theme, width)
            assert pg.evaluate(FIT) == [] and pg.evaluate("document.documentElement.scrollWidth") <= width


def test_the_plan_page_has_the_shared_chart_style_and_passes_its_check():
    """#190 adopts the shared chart style of #185 on the plan page. The plan page has no player modal."""
    from fantasyhoops.core import chart

    html = page.render(AUDIT_RUN)
    assert chart.CHART_STYLE in html and "__CHART_CSS__" not in html and "__PAGE_CSS__" not in html
    assert chart.style_problems(html) == [] and chart.label_overlaps(html) == []
    assert "lab-pmodal" not in html


def test_the_free_agents_page_has_the_shared_chart_style_once_and_passes_its_check():
    """#193: the two checks of #185 on the Free agents page. The page head has the shared chart style once, so the
    player modal (#186) has no copy of it. The h2 rule stays 2px, because the page has no chart panel.
    """
    from fantasyhoops.core import chart, profile

    text = page.render_free_agents(AUDIT_RUN)
    assert chart.style_problems(text) == [] and chart.label_overlaps(text) == []
    assert text.count(chart.CHART_STYLE) == 1 and "__CHART_CSS__" not in text and "__PAGE_CSS__" not in text
    assert text.index(chart.CHART_STYLE) < text.index("</head>")
    assert profile.modal(chart_css=False) in text
    assert "h2 { border-bottom-width" not in text


SITE = "http://lab.test/"  # a fake origin for the site in the browser tests of #165


@contextmanager
def site_pages(run, width=390):
    """A browser page with the plan page at /adds/ and the Free agents page at /free-agents/ of run, on SITE."""
    pages = {"adds/": page.render(run), "free-agents/": page.render_free_agents(run)}
    with browser_page(width=width) as pg:

        def serve(route):
            path = route.request.url.removeprefix(SITE).split("?")[0].split("#")[0]
            if path in pages:
                route.fulfill(status=200, content_type="text/html", body=pages[path])
            else:
                route.fulfill(status=404, body="not found")

        pg.route(f"{SITE}**", serve)
        yield pg


def test_a_click_on_an_add_opens_the_free_agents_page_with_the_day_the_position_and_the_team_filters():
    with site_pages(GRID_RUN) as pg:
        pg.goto(f"{SITE}adds/")
        assert pg.locator("#fa-table").count() == 0  # #165: the plan page has no free-agent table
        pg.locator("#plan a.addc").nth(2).click()  # Add 2 on Thu: +PF CHI, starts Thu and Sat (row 2)
        pg.wait_for_url(f"{SITE}free-agents/?**")
        assert "days=2027-01-07,2027-01-09" in pg.url
        pressed = pg.locator('button.chip[aria-pressed="true"]').all_inner_texts()
        assert [t.split("\n")[0] for t in pressed] == ["Thu 1/7", "Sat 1/9", "PF", "CHI"]
        assert pg.locator("#fa-from").is_visible()
        assert pg.locator("#fa-from-text").inner_text() == "Filters from the team plan: Add 2, Thu: +PF CHI."
        assert pg.locator("#fa-from a").get_attribute("href") == "../adds/#plan"
        assert "(teams: CHI)" in pg.locator("#fa-count").inner_text()
        assert pg.evaluate("document.activeElement.id") == "fa-count"
        # Back to the team plan opens the plan on the plan page.
        pg.locator("#fa-from a").click()
        pg.wait_for_url(f"{SITE}adds/#plan")
        # A day header sets only the day.
        pg.get_by_role("link", name="Show free agents who play Sat 1/9").click()
        pg.wait_for_url(f"{SITE}free-agents/?**")
        pressed = pg.locator('button.chip[aria-pressed="true"]').all_inner_texts()
        assert [t.split("\n")[0] for t in pressed] == ["Sat 1/9"]
        # Util clears the position filter.
        pg.goto(f"{SITE}adds/")
        pg.locator("#plan a.addc").nth(1).click()  # Add 1 on Sun: +Util from 8 teams
        pg.wait_for_url(f"{SITE}free-agents/?**")
        assert pg.locator('#pos-chips button[aria-pressed="true"]').count() == 0
        assert "(teams: ATL, BKN, BOS, GS, IND, LAC, LAL, ORL)" in pg.locator("#fa-count").inner_text()
        # Reset filters clears the team filter and the line, and removes the filters from the URL.
        pg.locator("#fa-reset").click()
        assert pg.locator('button.chip[aria-pressed="true"]').count() == 0
        assert not pg.locator("#fa-from").is_visible()
        assert pg.url == f"{SITE}free-agents/"


def test_the_free_agents_page_with_no_plan_link_shows_no_filter_line():
    with site_pages(GRID_RUN) as pg:
        pg.goto(f"{SITE}free-agents/")
        assert pg.locator('button.chip[aria-pressed="true"]').count() == 0
        assert not pg.locator("#fa-from").is_visible()


def test_an_old_link_to_the_free_agents_section_of_the_plan_page_forwards_to_the_free_agents_page():
    with site_pages(GRID_RUN) as pg:
        for hash in ("#fa", "#waivers"):
            pg.goto(f"{SITE}adds/{hash}")
            pg.wait_for_url(f"{SITE}free-agents/{hash}")
            assert pg.locator("#fa-table").count() == 1
        # The plan anchor stays on the plan page.
        pg.goto(f"{SITE}adds/#plan")
        assert pg.url == f"{SITE}adds/#plan" and pg.locator("#plan").count() == 1


def test_the_team_filter_has_a_chip_for_each_team_of_the_free_agents():
    with browser_page() as pg:
        pg.set_content(fa())
        assert pg.locator("#team-chips button").all_inner_texts() == ["CHI", "PHI"]
        pg.get_by_role("button", name="CHI", exact=True).click()
        assert pg.locator("#fa-table tbody tr").count() == 1
        assert pg.locator("#fa-count").inner_text().endswith("(teams: CHI)")


def test_the_page_has_the_team_plan_and_no_plans_for_one_roster_spot_and_no_contingency_section():
    html = render()
    shown = text(html)
    assert '<section id="plan"><h2>Team plan</h2>' in html
    assert "Best plans for one roster spot" not in shown and "Contingency" not in shown
    assert 'class="plans"' not in html


def test_the_free_agents_sections_are_on_the_free_agents_page_and_not_on_the_plan_page():
    """#165: the plan page keeps the team plan, the matchup and Run time. The other page has the three sections."""
    run = replace(MU_RUN, options=OPTIONS + [CLAIM, replace(PHI, role_up=("Star Wing",))])
    plan, free = page.render(run), page.render_free_agents(run)
    for section in ('<section id="fa">', '<section id="waivers">', '<section id="role-up">', 'id="fa-data"'):
        assert section in free and section not in plan, section
    for section in ('<section id="plan">', '<section id="matchup">'):
        assert section in plan and section not in free, section
    assert "<h1>Free agents</h1>" in free and "<title>Free agents</title>" in free
    assert '<a href="../adds/#plan">team plan</a>' in free and "Week 12: Mon 1/4 to Sun 1/10." in text(free)
    assert page.FORWARD in plan and page.FORWARD not in free


def test_the_free_agents_page_shows_the_site_menu_with_free_agents_current():
    html = fa()
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", html) == [
        "Home",
        "Roster",
        "Adds plan",
        "Free agents",
        "Trades",
        "Players",
    ]
    assert '<a href="../free-agents/" aria-current="page">Free agents</a>' in html
    assert html.count('aria-current="page"') == 1


def test_the_free_agents_page_with_no_free_agents_says_so():
    html = page.render_free_agents(BASE)
    assert page.NO_FREE_AGENTS in text(html) and 'id="fa-data"' not in html
    assert 'id="fa-none"' not in fa()


def test_the_page_writes_the_free_agents_page_next_to_the_plan_page(monkeypatch, tmp_path):
    monkeypatch.setattr(page.common, "OUT", tmp_path)
    path = page.write_free_agents(fa())
    assert path == tmp_path / "adds" / "free_agents.html" and path.parent == page.page_path().parent
    assert (path.parent / "fonts" / tokens.FONT.name).exists()


def test_the_plan_and_free_agents_pages_have_the_icon_links_and_the_preview_tags():
    """#166: the head of each page has publish.page_meta() with the page title."""
    from fantasyhoops.core import publish

    plan, free = render(), fa()
    plan_title = re.search(r"<title>(.*?)</title>", plan).group(1)
    assert publish.page_meta("adds", plan_title) in plan
    assert publish.page_meta("free-agents", page.FA_TITLE) in free


def test_a_player_name_opens_the_player_modal(modal_site):
    """#186: each name of the Free agents and Waiver players tables is a link that opens the player modal. The page
    script draws the free-agent names, so the name of a free agent has a slug in the page data."""
    html = fa(options=OPTIONS + [CLAIM])
    data = json.loads(html.split('<script type="application/json" id="fa-data">')[1].split("</script>")[0])
    records = [
        {
            "slug": p["slug"],
            "name": p["name"],
            "team": p["team"],
            "pos": "/".join(p["pos"]),
            "owner": None,
            "mine": False,
            "val": p["value"],
            "games": 5,
            "signals": [],
        }
        for p in data["players"]
    ]
    pg = modal_site.open("free-agents", html, records=records)
    assert pg.locator("#fa-table a.lab-pname").count() == len(data["players"])
    assert pg.locator('#wv-table a.lab-pname[data-player="claim-guy"]').count() == 1
    modal_site.check_modal()
    assert "lab-pmodal" not in render()  # not on the Adds plan page
