import csv
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

from fantasyhoops.adds import cache as page_cache
from fantasyhoops.adds import page, timing
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.matchup import Matchup, matchup_weights, read_matchup
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamRank, TeamWindow
from fantasyhoops.adds.readers import Adds, FreeAgent, Player, Week
from fantasyhoops.adds.role_up import Absence
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


def render(**kw):
    return page.render(
        DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2], OPTIONS, RANKING, ["PHI"], WEEK[0], replacement=0.5, **kw
    )


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
    shown = text(render(matchup=m, weights=weights))
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
    html = render(matchup=m, weights=matchup_weights(m, cfg, share_left=5 / 6))
    shown = text(html)
    assert "The planner did not find the category scores" not in shown
    assert "PTS 24 45 -21 1.00" in shown and "REB 4 17 -13 0.99" in shown and "BLK 0 3 -3 0.95" in shown
    assert "Opponent" not in html


def test_the_opponent_name_is_not_on_the_page():
    # The page is public (ADR 2). The name must not be in the HTML, the script or its data.
    m = Matchup("Secret Rival Team", {"pts": 300}, {"pts": 290})
    html = render(matchup=m, weights={"pts": 1.0})
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
    shown = text(render(roles=roles, minutes_rise=4.0, flags=load_config()["adds"]["flags"]))
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
    html = render(roles=roles, minutes_rise=4.0)
    assert "Starts 1/5 (Inconsistent) · Closes 0/4" in html
    assert "Closes 0/4 (" not in html  # no closer flag: no word after the closes
    assert "Starts 5/5 (New) · Closes 4/4 (Regular)" in html


def test_the_page_has_no_role_legend_with_no_rotation_log():
    assert "Min: his mean minutes" not in text(render())


def test_the_page_holds_the_free_agent_data_as_safe_json():
    html = render()
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert json.loads(raw)["players"][1]["name"] == "Phi & One"
    evil = page.render(DATA, DAYS, GAMES, SPOTS, [], [option("</script><b>", "PHI", 1.0)], today=WEEK[0])
    assert "</script><b>" not in evil and "http" not in evil


def test_the_page_explains_why_there_is_no_plan():
    assert "No adds left this week (5 of 5 used)" in text(
        page.render(command.LeagueData([], Adds(5, 5), DATA.week), DAYS, GAMES, SPOTS, [], today=WEEK[0])
    )
    assert "No stream spots" in text(page.render(DATA, DAYS, GAMES, [], [], today=WEEK[0]))
    assert "No free agent that the planner read" in text(page.render(DATA, DAYS, GAMES, SPOTS, [], today=WEEK[0]))
    # No options: no free-agent table and no script.
    assert "fa-data" not in page.render(DATA, DAYS, GAMES, SPOTS, [], today=WEEK[0])


CLAIM = Option(Player("Claim Guy", "CHI", ("C",), clear_day=WEEK[1]), 1.2)


def test_the_page_lists_the_waiver_players_with_the_clear_day():
    html = page.render(
        DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2], OPTIONS + [CLAIM], RANKING, ["PHI"], WEEK[0], replacement=0.5
    )
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
    shown = text(page.render(DATA, DAYS, GAMES, SPOTS, [row], [CLAIM], today=WEEK[0]))
    assert "+Claim Guy W (CHI) add Wed, clears Tue – starts Sat & Sun" in shown
    assert "W: a waiver claim. It is not sure" in shown


def test_the_command_prints_the_waiver_players_and_uses_one_after_his_clear_day(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue. The waiver player clears on Mon, so the plan adds him on Tue. The DEN free agent has no
    # game. He is the replacement free agent (value 0.1), so the market value of the waiver player is +0.20.
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    run_command(monkeypatch, tmp_path, [], publish=False, options=[claim, option("Den Guy", "DEN", 0.1)])
    out = capsys.readouterr().out
    assert "Waiver players (a claim is not sure, and it uses an add):" in out
    assert "Phi Claim (PHI) SF  clears Mon 01/04, first plan day Tue 01/05, Val +0.20" in out
    # The page shows the same Val.
    assert "Phi Claim W PHI SF Mon 1/4 Tue 1/5 +0.20" in text((tmp_path / "adds_plan.html").read_text(encoding="utf-8"))
    assert "Spot 1: PHI Tue 01/05 to Tue 01/05" in out
    assert "1. Phi Claim W (waiver claim, not sure)" in out
    assert command.free_agent_path(None, 25, status="W").startswith("players?status=W&")


def test_the_command_writes_the_page_and_publishes_it(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=True)
    path = tmp_path / "adds_plan.html"
    assert published == [(command.ROOT, "adds", path)]
    out = capsys.readouterr().out
    assert f"Wrote the plan page: {path}" in out
    assert "Plan page: best plan for one roster spot: +2 started games with 1 add." in out
    assert command.URL in out and command.URL.endswith("/adds/")
    assert "+Phi One (PHI) add Mon – starts Mon & Tue" in text(path.read_text(encoding="utf-8"))
    assert "Aggressive plan: the same as the schedule plan." in out
    assert (tmp_path / "fonts" / "archivo-latin.woff2").read_bytes() == tokens.FONT.read_bytes()
    assert (tmp_path / "fonts" / "OFL.txt").read_bytes() == tokens.LICENSE.read_bytes()


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


def test_the_command_prints_the_comparison_and_shows_the_plans_for_one_roster_spot(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue, BOS plays Mon. The schedule plan takes 2 games of the weak PHI player. The aggressive
    # plan takes 1 game of the better BOS player: 9 above an empty slot (-10) is more than 2 x 4.
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0)]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options)
    out = capsys.readouterr().out
    assert "Schedule plan: 2 started games with 1 add" in out
    assert "Aggressive plan: 1 started game with 1 add" in out
    lines = [line.split() for line in out[out.index("Comparison:") :].splitlines()[1:7]]
    assert lines == [
        ["Schedule", "Aggressive"],
        ["Adds", "1", "1"],
        ["Started", "games", "2", "1"],
        ["Blended", "value", "-12.00", "-1.00"],
        ["Value", "above", "an", "empty", "slot", "+8.00", "+9.00"],
        ["Matchup", "value", "above", "empty", "+8.00", "+9.00"],
    ]
    # The read_league() of this test gives no matchup scores, so all weights are 1.
    assert "the planner did not find the category scores" in out
    # Each row of the page has different players: the PHI player first (2 games), then the BOS player (1 game).
    shown = text((tmp_path / "adds_plan.html").read_text(encoding="utf-8"))
    assert "Comparison" not in shown and "Aggressive" not in shown
    assert "+Phi Weak (PHI) add Mon – starts Mon & Tue" in shown and "+Bos Good (BOS) add Mon – starts Mon" in shown
    assert "  1. +2 started games with 1 add" in out and "  2. +1 started games with 1 add" in out


def test_the_command_does_not_publish_with_no_publish(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=False)
    assert published == []
    assert (tmp_path / "adds_plan.html").exists()
    assert "did not publish" in capsys.readouterr().out


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
    html = page.render(DATA, DAYS, GAMES, SPOTS, [row], OPTIONS, today=WEEK[0])
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
    html = page.render(DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2, row3], OPTIONS, today=WEEK[0])
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


def test_the_command_counts_a_second_night_of_a_player_on_the_rest_list_as_less_than_1_game(
    monkeypatch, tmp_path, capsys
):
    # PHI plays Mon and Tue. Phi One is on the rest list, and [adds] rest_chance is 0.5.
    run_command(monkeypatch, tmp_path, [], publish=False, rests={"phi one"})
    out = capsys.readouterr().out
    assert "Schedule plan: 1.5 started games with 1 add" in out
    assert "Started games: 1.5 (Mon 01/04, Tue 01/05 b2b)." in out
    assert "  1. +1.5 started games with 1 add" in out
    assert 'class="b2b"' in (tmp_path / "adds_plan.html").read_text(encoding="utf-8")


def test_the_free_agent_data_and_the_page_show_the_role_up_mark_and_the_absent_teammate():
    marked = replace(PHI, role_up=("Star Wing",))
    data = page.free_agent_data([marked, CHI], DAYS, GAMES, replacement=0.5)
    assert [p["role_up"] for p in data["players"]] == [["Star Wing"], []]
    shown = text(page.render(DATA, DAYS, GAMES, SPOTS, [], [marked, CHI], today=WEEK[0]))
    assert "Role up" in shown
    assert "Star Wing is absent. Role up: Phi & One (PHI)." in shown
    assert "role up" in page.SCRIPT


def test_the_page_has_no_role_up_section_with_no_mark():
    assert "Role up" not in text(render())


def test_the_command_marks_the_role_up_free_agents_in_the_window_options(monkeypatch, tmp_path, capsys):
    absent = [Absence("Star Wing", "PHI", WEEK[0] - timedelta(days=2), 1, ("SF", "PF"))]
    options = [option("Phi One", "PHI", 0.3), option("Phi Guard", "PHI", 0.2, ("PG",))]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options, absences=absent)
    out = capsys.readouterr().out
    assert "Role up: Star Wing (PHI) is absent. Free agents at his positions: Phi One." in out
    lines = out.splitlines()
    assert next(line for line in lines if "1. Phi One" in line).endswith("role up: Star Wing absent")
    assert not next(line for line in lines if "2. Phi Guard" in line).endswith("absent")
    assert "Star Wing is absent. Role up: Phi One (PHI)." in text(
        (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    )


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


def test_the_command_marks_the_free_agents_who_play_on_an_open_day_early_next_week(monkeypatch, tmp_path, capsys):
    # The week is Mon and Tue. Next week starts on Wed, and PHI plays then. The roster is empty, so all slots are open.
    run_command(monkeypatch, tmp_path, [], publish=False, extra_games=[(WEEK[2], "PHI")])
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Wed open"]
    assert "he has a game next Wednesday 1/6" in text(html)


def test_on_the_last_day_of_the_week_the_mark_checks_the_days_after_the_planned_week(monkeypatch, tmp_path):
    # read_league() moves data.week forward to Wed and Thu. So the mark checks Fri and Sat, not Wed.
    league = command.LeagueData(roster=[], adds=Adds(0, 5), week=Week(13, tuple(WEEK[2:4])), next_week=True)
    run_command(
        monkeypatch, tmp_path, [], publish=False, league=league, extra_games=[(WEEK[2], "PHI"), (WEEK[4], "PHI")]
    )
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1))
    assert data["players"][0]["next_open"] == ["Fri open"]
    assert "next Friday 1/8" in text(html) and "next Saturday 1/9" in text(html)


STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
    "absence read",
    "value options",
    "schedule search",
    "drop trade-offs",
    "aggressive search",
    "spot plans",
    "contingency plans",
    "role read",
    "page write and publish",
]
SEARCH_STEPS = {"schedule search", "drop trade-offs", "aggressive search", "spot plans"}
NO_READ_STEPS = [
    "schedule read",
    "season values",
    "Yahoo reads",
    "contingency plans",
    "role read",
    "page write and publish",
]
YAHOO_PARTS = [
    "browser start",
    "league and matchup pages",
    "projected pass",
    "recent pass",
    "market pages",
    "waiver list",
    "trends",
]


def rows_of(steps, parts):
    """The step names of the rows of one run: each step, and after the Yahoo reads its sub-steps."""
    out = []
    for name in steps:
        out.append(name)
        if name == "Yahoo reads":
            out += [f"Yahoo reads: {p}" for p in parts]
    return out


ROWS = rows_of(STEPS, YAHOO_PARTS)
NO_READ_ROWS = rows_of(NO_READ_STEPS, YAHOO_PARTS[:2])  # no free agent read, so only the first 2 sub-steps


def timing_rows(tmp_path):
    with open(tmp_path / "timings.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_the_command_prints_each_step_when_it_starts_and_its_time_when_it_ends(monkeypatch, tmp_path, capsys):
    run_command(monkeypatch, tmp_path, [], publish=False)
    lines = capsys.readouterr().out.splitlines()
    for name in STEPS:
        start = lines.index(f"Step: {name} ...")
        end = next(i for i, line in enumerate(lines) if re.fullmatch(rf"Step: {re.escape(name)}: \d+\.\d\d s.*", line))
        assert start < end
    assert any("timings.csv" in line for line in lines)


def test_the_command_appends_one_row_for_each_step_to_the_timings_file(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False)
    run_command(monkeypatch, tmp_path, [], publish=False)
    columns, rows = timing_rows(tmp_path)
    assert columns == ["run_at", "days", "open_days", "adds_left", "step", "seconds", "calls", "states", "pages"]
    assert [r["step"] for r in rows] == ROWS + ROWS
    first = rows[: len(ROWS)]
    assert len({r["run_at"] for r in first}) == 1
    assert {(r["days"], r["open_days"], r["adds_left"]) for r in rows} == {("2", "2", "1")}
    for r in rows:
        assert re.fullmatch(r"\d+\.\d\d", r["seconds"])
        if r["step"] in SEARCH_STEPS:  # drop trade-offs: 0 searches, because no stream spot has a holder
            assert int(r["calls"]) >= int(r["states"]) >= (r["step"] != "drop trade-offs")
        else:
            assert r["calls"] == r["states"] == ""
        # Only the Yahoo reads and its sub-steps have pages. The fake League of the test opens no page.
        assert r["pages"] == ("0" if r["step"].startswith("Yahoo reads") else "")


def test_a_step_that_does_not_run_writes_no_row(monkeypatch, tmp_path):
    # No adds left, so the run reads no free agent and runs no search.
    league = command.LeagueData(roster=[], adds=Adds(5, 5), week=Week(12, tuple(WEEK[:2])))
    run_command(monkeypatch, tmp_path, [], publish=False, league=league)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == NO_READ_ROWS
    assert all(r["calls"] == r["states"] == "" for r in rows)


def test_each_sub_step_of_the_yahoo_reads_counts_its_pages(monkeypatch, tmp_path, capsys):
    pages = {
        "league": 2,
        ("team", command.PROJECTED): 5,
        ("market", command.PROJECTED): 3,
        ("waiver", command.PROJECTED): 1,
        ("team", command.RECENT): 4,
        ("market", command.RECENT): 3,
        ("waiver", command.RECENT): 1,
        "trends": 3,
    }
    yahoo = run_command(monkeypatch, tmp_path, [], publish=False, pages=pages)
    # The team lists in both views, each market page in both views, the waiver list in both views (#92).
    market = [f"market {command.PROJECTED}", f"market {command.RECENT}"] * 3
    assert (
        yahoo.paths
        == ["league"] * 2
        + [f"team {command.PROJECTED}"] * 5
        + [f"team {command.RECENT}"] * 4
        + market
        + [f"waiver {command.PROJECTED}", f"waiver {command.RECENT}"]
        + ["trends"] * 3
    )
    _, rows = timing_rows(tmp_path)
    found = {r["step"]: r["pages"] for r in rows if r["step"].startswith("Yahoo reads")}
    assert found == {
        "Yahoo reads": "22",
        "Yahoo reads: browser start": "0",
        "Yahoo reads: league and matchup pages": "2",
        "Yahoo reads: projected pass": "5",
        "Yahoo reads: market pages": "6",
        "Yahoo reads: waiver list": "2",
        "Yahoo reads: recent pass": "4",
        "Yahoo reads: trends": "3",
    }
    out = capsys.readouterr().out
    assert re.search(r"Step: Yahoo reads: \d+\.\d\d s, 22 pages", out)
    assert re.search(r"  Yahoo reads: market pages: \d+\.\d\d s, 6 pages", out)


def test_an_old_timings_file_stays_readable(monkeypatch, tmp_path):
    old = (
        "run_at,days,open_days,adds_left,step,seconds,calls,states\n"
        "2026-10-26T09:00:00,2,2,1,schedule search,1.50,40,12\n"
    )
    (tmp_path / "timings.csv").write_text(old, encoding="utf-8")
    run_command(monkeypatch, tmp_path, [], publish=False)
    columns, rows = timing_rows(tmp_path)
    assert columns == timing.COLUMNS
    assert rows[0] == {
        "run_at": "2026-10-26T09:00:00",
        "days": "2",
        "open_days": "2",
        "adds_left": "1",
        "step": "schedule search",
        "seconds": "1.50",
        "calls": "40",
        "states": "12",
        "pages": "",
    }
    assert [r["step"] for r in rows[1:]] == ROWS


def test_a_run_that_stops_keeps_the_rows_of_the_finished_steps(monkeypatch, tmp_path):
    def stop(*args):
        raise KeyboardInterrupt  # the owner stops the run with Ctrl+C during the spot plans

    monkeypatch.setattr(command, "spot_plans", stop)
    with pytest.raises(KeyboardInterrupt):
        run_command(monkeypatch, tmp_path, [], publish=False)
    _, rows = timing_rows(tmp_path)
    assert [r["step"] for r in rows] == ROWS[: ROWS.index("spot plans")]
    assert {(r["days"], r["open_days"], r["adds_left"]) for r in rows} == {("2", "2", "1")}


def test_the_page_shows_the_run_time_table(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False)
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    table = re.search(r"<summary>Run time</summary>.*?<tbody>(.*?)</tbody>", html, re.S).group(1)
    assert "<th>Pages</th>" in html
    rows = re.findall(r"<tr>(.*?)</tr>", table)
    cells = [re.findall(r"<td[^>]*>([^<]*)</td>", row) for row in rows]
    # The page write ends after the page is written. A sub-step row shows the sub-step name below the Yahoo reads.
    assert [c[0] for c in cells] == [r.removeprefix("Yahoo reads: ") for r in ROWS[:-1]]
    subs = [c[0] for row, c in zip(rows, cells) if row.startswith('<td class="name sub">')]
    assert subs == YAHOO_PARTS
    for name, seconds, calls, states, pages in cells:
        assert re.fullmatch(r"\d+\.\d\d", seconds)
        assert (calls != "" and states != "") == (name in SEARCH_STEPS)
        assert (pages != "") == (name == "Yahoo reads" or name in YAHOO_PARTS)


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


def test_the_timers_change_no_plan(monkeypatch, tmp_path, capsys):
    options = [option("Phi One", "PHI", 0.3), option("Bos One", "BOS", 0.2), option("Phi Two", "PHI", 0.1, ("C",))]
    league = command.LeagueData(roster=[], adds=Adds(2, 5), week=Week(12, tuple(WEEK[:2])))
    found = {}
    for timed in (True, False):
        plans, pages = [], []
        real_print_plan, real_render = command.print_plan, page.render
        monkeypatch.setattr(
            command, "print_plan", lambda plan, *a, **kw: (plans.append(plan), real_print_plan(plan, *a, **kw))
        )
        monkeypatch.setattr(page, "render", lambda *a, **kw: (pages.append((a, kw)), real_render(*a, **kw))[1])
        run_command(monkeypatch, tmp_path / str(timed), [], publish=False, options=options, league=league, timed=timed)
        args, kw = pages[0]
        kw.pop("timings")
        found[timed] = (plans, args, kw)
        monkeypatch.setattr(command, "print_plan", real_print_plan)
        monkeypatch.setattr(page, "render", real_render)
    assert found[True][0] and found[True][0][0] is not None
    assert found[True] == found[False]
    assert not (tmp_path / "False" / "timings.csv").exists()
    # The run with no timers comes second, after the last step line of the timed run. It prints no step line.
    assert "Step:" not in capsys.readouterr().out.split("Step: page write and publish:")[-1]


class ListPages:
    """A fake session.League that gives the HTML of the fixtures for the free-agent lists and the waiver list."""

    def __init__(self):
        self.pages, self.paths = 0, []

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        if "status=W" in path:
            name = "waivers.html"
        elif "eteam=" not in path:
            name = "free_agents.html"  # it has a "Next 25" link, so the run reads all MARKET_PAGES pages
        else:
            name = "free_agents_phi_recent.html" if command.RECENT in path else "free_agents_phi.html"
        return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def options_of(fas, recent):
    """An Option for each free agent, with values from his projected points and his recent points."""
    points = {f.player.name: f.line.get("pts", 0.0) for f in recent}
    return [Option(f.player, f.line.get("pts", 0.0) / 10 - 1, recent_value=points.get(f.player.name)) for f in fas]


@pytest.mark.parametrize("settings", [{}, {"recent_skip_weight": 0.3}])
def test_one_parse_of_each_list_page_changes_no_plan(monkeypatch, tmp_path, settings):
    league = command.LeagueData(roster=[], adds=Adds(2, 5), week=Week(12, tuple(WEEK[:2])))
    found = {}
    for once in (True, False):
        plans, pages, inputs = [], [], []
        real_print_plan, real_render, real_parse = command.print_plan, page.render, command.parse
        monkeypatch.setattr(
            command, "print_plan", lambda plan, *a, **kw: (plans.append(plan), real_print_plan(plan, *a, **kw))
        )
        monkeypatch.setattr(page, "render", lambda *a, **kw: (pages.append((a, kw)), real_render(*a, **kw))[1])
        if not once:
            # The read before #93: each reader gets the HTML and parses it again.
            monkeypatch.setattr(command, "parse", lambda html: html)
        yahoo = run_command(
            monkeypatch,
            tmp_path / str(once),
            [],
            publish=False,
            league=league,
            yahoo=ListPages(),
            settings=settings,
            options=lambda fas, recent: (inputs.append((fas, recent)), options_of(fas, recent))[1],
        )
        args, kw = pages[0]
        kw.pop("timings")
        found[once] = (plans, args, kw, inputs, yahoo.paths)
        for name, real in (("print_plan", real_print_plan), ("parse", real_parse)):
            monkeypatch.setattr(command, name, real)
        monkeypatch.setattr(page, "render", real_render)
    plans, _, _, inputs, paths = found[True]
    assert plans and plans[0].windows
    fas, recent = inputs[0]
    # With the recent view skipped (#90), the run reads only the projected view, and recent is empty.
    views = 1 if settings else 2
    assert fas and bool(recent) == (views == 2)
    assert len(paths) == views * (2 + command.MARKET_PAGES + 1)  # 2 team pages, the market and the waivers
    assert found[True] == found[False]


def run_command(
    monkeypatch,
    tmp_path,
    published,
    publish,
    options=None,
    rests=None,
    absences=(),
    extra_games=(),
    league=None,
    timed=True,
    pages=None,
    yahoo=None,
    settings=None,
    free_agents=None,
    market=None,
    today=None,
    cache=False,
    home=None,
):
    """Run plan.main() with no Yahoo session, no schedule file and site.publish replaced. Return the FakeLeague.

    The page, timings.csv and the page cache (cache/) go in tmp_path. timed: the timed argument of plan.main().
    today: the date of the run (default: WEEK[0]). cache: the cache argument of plan.main(). The default is False,
    because the fake readers open the same path for each page, and a cache would give the second page.
    pages: the pages that each fake reader opens, by "league", "trends" or (reader, view). The readers are "team",
    "market" and "waiver". None: no reader opens a page.

    rests: the name keys of the rest list. With rests, [adds] rest_chance is 0.5.
    extra_games: (day, team) for each more game of the schedule, for example a game next week.
    league: the LeagueData that read_league() gives. None: week 12 (Mon and Tue), 4 of 5 adds used.
    yahoo: a fake League with the HTML of the list pages. The run then uses the real readers of the lists, and options
    is a function of the free agents and the recent free agents. None: a FakeLeague and fake readers of the lists.
    settings: more [adds] settings, for example {"recent_skip_weight": 0.3}.
    free_agents: {view: FreeAgents} that the fake team reader gives. The run then values them with the real
    value_options() and a scale of pts only, and the market and waiver readers give no free agents.
    market: the MarketRead that the fake market reader gives. None: no market free agents.
    home: the build_home() of the run (adds/home.py). None: a function that makes no home page.
    """
    lists = yahoo is None
    yahoo = yahoo or FakeLeague()
    pages = pages or {}

    @contextmanager
    def no_yahoo(league, wait_seconds):
        yield yahoo

    def reader(name, result):
        """A fake reader that opens the pages of name (and of its view) and gives result."""

        def read(league, *args, **kw):
            view = command.RECENT if command.RECENT in (*args, *kw.values()) else command.PROJECTED
            key, path = ((name, view), f"{name} {view}") if name in ("team", "market", "waiver") else (name, name)
            for _ in range(pages.get(key, 0)):
                league.get(path)
            if isinstance(result, dict):
                return list(result.get(view, ()))
            return result() if callable(result) else result

        return read

    import pandas as pd

    games = [(WEEK[0], "PHI"), (WEEK[0], "BOS"), (WEEK[1], "PHI"), *extra_games]
    sched = pd.DataFrame({"date": [str(d) for d, _ in games], "team": [t for _, t in games]})
    cfg = {
        "league": {"slots": ["PG", "SG", "SF", "PF", "C"], "roster_spots": 10},
        "adds": {"league": 1, "team": 1, **({"rest_chance": 0.5} if rests else {}), **(settings or {})},
        "weights": {"pts": 1.0},
    }
    monkeypatch.setattr(command, "read_rest_names", lambda cfg: set(rests or ()))
    monkeypatch.setattr(command, "load_config", lambda: cfg)
    monkeypatch.setattr(command, "read_schedule", lambda: sched)
    monkeypatch.setattr(command, "open_league", no_yahoo)
    league = league or command.LeagueData(roster=[], adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2])))
    monkeypatch.setattr(command, "read_league", reader("league", league))
    monkeypatch.setattr(command, "season_values", lambda cfg: {})
    monkeypatch.setattr(command, "stream_spots", lambda roster, cfg, values=None: [StreamSpot()])
    if lists:
        monkeypatch.setattr(command, "read_team_free_agents", reader("team", free_agents or list))
        monkeypatch.setattr(command, "read_market_free_agents", market_reader(pages, market))
        monkeypatch.setattr(command, "read_waiver_list", reader("waiver", list))
    monkeypatch.setattr(command, "read_week_trends", reader("trends", dict))
    monkeypatch.setattr(command, "read_roles", lambda players, cfg, today: {})
    options = options or [option("Phi One", "PHI", 0.3)]
    if free_agents is None:
        monkeypatch.setattr(
            command,
            "value_options",
            lambda fas, cfg, recent=(), matchup_cfg=None, scale=None: (
                options(fas, recent) if callable(options) else options
            ),
        )
    scale = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"]) if free_agents is not None else None
    monkeypatch.setattr(command, "projection_scale", lambda cfg: scale)
    monkeypatch.setattr(command, "empty_slot_value", lambda cfg, scale=None: -10.0)
    monkeypatch.setattr(command, "read_absences", lambda today, cfg: list(absences))
    monkeypatch.setattr(page, "PAGE", tmp_path / "adds_plan.html")
    monkeypatch.setattr(timing, "TIMINGS", tmp_path / "timings.csv")
    monkeypatch.setattr(page_cache, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(command, "build_home", home or (lambda *args: None))
    # A home page goes last in the record of the publish.
    monkeypatch.setattr(
        command.site, "publish", lambda *a, home=None: published.append(a if home is None else (*a, home))
    )
    command.main(today=today or WEEK[0], publish=publish, timed=timed, cache=cache)
    return yahoo


def market_reader(pages, result=None):
    """A fake read_market_free_agents(). It opens the market pages of pages (see run_command()).

    Page by page, it opens the projected page, then the recent page if the run reads the recent view.
    result: the MarketRead that it gives. None: a MarketRead with no free agents.
    """

    def read(league, recent=True, *args, **kw):
        projected, recent_pages = pages.get(("market", command.PROJECTED), 0), pages.get(("market", command.RECENT), 0)
        for n in range(max(projected, recent_pages if recent else 0)):
            if n < projected:
                league.get(f"market {command.PROJECTED}")
            if recent and n < recent_pages:
                league.get(f"market {command.RECENT}")
        return result or command.MarketRead([], [], max(projected, 1), "end")

    return read


class FakeLeague:
    """The part of session.League that the timers use: get() counts the pages, as League.get() does."""

    def __init__(self, html=""):
        self.pages, self.paths, self.html = 0, [], html

    def get(self, path):
        self.pages += 1
        self.paths.append(path)
        return self.html


# The recent view skip (#90). The schedule of run_command() gives PHI 1 game from 14 days ago to today (Mon),
# so the largest possible w is 1 / 14.
SKIP = {"recent_skip_weight": 0.3}
# One page of PHI free agents with no next page. The real readers read it for each list and each view.
PHI_PAGE = (Path(__file__).parent / "fixtures" / "free_agents_phi.html").read_text(encoding="utf-8")


def test_below_the_setting_the_run_reads_no_page_of_the_recent_view(monkeypatch, tmp_path):
    yahoo = run_command(monkeypatch, tmp_path, [], publish=False, settings=SKIP, yahoo=FakeLeague(PHI_PAGE))
    assert any(f"stat1={command.PROJECTED}" in path for path in yahoo.paths)
    assert not [path for path in yahoo.paths if f"stat1={command.RECENT}" in path]


@pytest.mark.parametrize("weight", [0.0, 1 / 14])
def test_at_or_above_the_setting_the_run_reads_both_views(monkeypatch, tmp_path, weight):
    yahoo = run_command(
        monkeypatch, tmp_path, [], publish=False, settings={"recent_skip_weight": weight}, yahoo=FakeLeague(PHI_PAGE)
    )
    projected = [path for path in yahoo.paths if f"stat1={command.PROJECTED}" in path]
    recent = [path for path in yahoo.paths if f"stat1={command.RECENT}" in path]
    assert len(projected) == 4  # the lists of PHI and BOS, the market list and the waiver list
    assert recent == [path.replace(command.PROJECTED, command.RECENT) for path in projected]


def _free_agents():
    """FreeAgents of PHI and BOS in the projected view and in the recent view, each recent row with games."""
    names = [("Phi Big", "PHI", ("C",), 18.0), ("Phi Wing", "PHI", ("SF",), 12.0), ("Bos Guard", "BOS", ("PG",), 15.0)]
    projected = [FreeAgent(Player(n, t, pos), 3, {"pts": pts}) for n, t, pos, pts in names]
    recent = [FreeAgent(Player(n, t, pos), 4, {"pts": 30.0 - pts}) for n, t, pos, pts in names]
    return projected, recent


def _plans(monkeypatch, tmp_path, recent, settings):
    """The printed plans and the page.render() arguments of one run: (plans, args, skip line, other keywords)."""
    plans, pages = [], []
    real_print_plan, real_render = command.print_plan, page.render
    monkeypatch.setattr(
        command, "print_plan", lambda plan, *a, **kw: (plans.append(plan), real_print_plan(plan, *a, **kw))
    )
    monkeypatch.setattr(page, "render", lambda *a, **kw: (pages.append((a, kw)), real_render(*a, **kw))[1])
    projected, _ = _free_agents()
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=settings,
        free_agents={command.PROJECTED: projected, command.RECENT: recent},
    )
    monkeypatch.setattr(command, "print_plan", real_print_plan)
    monkeypatch.setattr(page, "render", real_render)
    args, kw = pages[0]
    kw.pop("timings")
    return plans, args, kw.pop("recent_skip"), kw


def test_the_plans_with_the_recent_view_skipped_are_the_plans_with_recent_weight_0(monkeypatch, tmp_path):
    _, recent = _free_agents()
    plans, args, line, kw = _plans(monkeypatch, tmp_path / "skip", recent, SKIP)
    zero = _plans(monkeypatch, tmp_path / "zero", [replace(f, games=0) for f in recent], {"recent_skip_weight": 0.0})
    assert line and zero[2] is None
    assert plans and plans[0] is not None and plans[0].windows
    assert args[4]  # the best plans for one roster spot
    # The schedule plan, the aggressive plan, the best plans for one roster spot and the options are equal.
    assert (plans, args, kw) == (zero[0], zero[1], zero[3])
    # Without the skip, the recent lines of the test data move the values. So the test can see a difference.
    read = _plans(monkeypatch, tmp_path / "read", recent, {"recent_skip_weight": 0.0})
    assert [o.value for o in read[1][5]] != [o.value for o in args[5]]


SKIP_LINE = (
    "The run skipped the recent view (last 14 days). The most games of one team from 14 days ago to today "
    "is 1, so w is 0.07 at most. This is below [adds] recent_skip_weight (0.3). The values use the projection "
    "only. A player with no projection is not a candidate."
)


@pytest.mark.parametrize("settings", [{}, SKIP])
def test_the_page_and_the_terminal_show_the_market_read(monkeypatch, tmp_path, capsys, settings):
    # The fake market read of run_command() reads 2 pages, and page 2 is the last page of the list.
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=settings,
        pages={("market", command.PROJECTED): 2, ("market", command.RECENT): 2},
    )
    line = "Market: 2 of 3 pages. Page 2 was the last page of the list."
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    assert line in text(run_time(html))  # in the Run time section, not above the free-agent table (#118)
    assert line not in text(html.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    assert line in capsys.readouterr().out


def test_the_market_free_agents_of_each_view_reach_the_free_agent_lists(monkeypatch, tmp_path):
    projected = FreeAgent(Player("Market One", "PHI", ("SF",)), 3, {"pts": 14.0})
    recent = FreeAgent(Player("Market One", "PHI", ("SF",)), 5, {"pts": 22.0})
    inputs = []
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        market=command.MarketRead([projected], [recent], 1, "end"),
        options=lambda fas, rec: (inputs.append((list(fas), list(rec))), options_of(fas, rec))[1],
    )
    # The last call of value_options() gives the options of the plans: the free agents of each view.
    assert inputs[-1] == ([projected], [recent])


def test_the_page_shows_why_the_market_read_stopped():
    lines = [
        command.market_line(command.MarketRead([], [], 2, "guard")),
        command.market_line(command.MarketRead([], [], 3, "limit")),
    ]
    assert lines == [
        "Market: 2 of 3 pages. Page 2 had no new player above the replacement value (the free agent at "
        "rank 15 of the players read before it).",
        "Market: 3 of 3 pages (the limit).",
    ]
    for line in lines:
        html = page.render(DATA, DAYS, GAMES, SPOTS, [], [PHI], today=MON, market=line)
        assert f'<p class="legend" id="market-read">{line}</p>' in html
    assert 'id="market-read"' not in page.render(DATA, DAYS, GAMES, SPOTS, [], [PHI], today=MON)


def test_the_page_and_the_terminal_say_that_the_run_skipped_the_recent_view(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=SKIP,
        free_agents={command.PROJECTED: projected, command.RECENT: recent},
    )
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    above = text(html.split("<h2>Free agents</h2>")[1].split('id="fa-table"')[0])
    # Above the free-agent table: one short sentence. The full line is in the Run time section (#118).
    assert page.SKIP_NOTE in above and SKIP_LINE not in above
    assert SKIP_LINE in text(run_time(html))
    assert SKIP_LINE in capsys.readouterr().out


def test_a_run_with_the_recent_view_has_no_skip_line(monkeypatch, tmp_path, capsys):
    projected, recent = _free_agents()
    run_command(
        monkeypatch, tmp_path, [], publish=False, free_agents={command.PROJECTED: projected, command.RECENT: recent}
    )
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    assert "<h2>Free agents</h2>" in html
    assert "skipped the recent view" not in text(html)
    assert 'class="skip"' not in html
    assert "skipped the recent view" not in capsys.readouterr().out


# The same-day cache of Yahoo pages (#91). BOTH: the run reads both views (no skip).
BOTH = {"recent_skip_weight": 0.0}
# The recent view of PHI with the Q players marked O.
PHI_RECENT_OUT = (
    (Path(__file__).parent / "fixtures" / "free_agents_phi_recent.html")
    .read_text(encoding="utf-8")
    .replace('title="Questionable">Q<', 'title="Out">O<')
)


class ViewPages(FakeLeague):
    """A fake League: the recent view gives recent_html, all other pages PHI_PAGE. No page has a next page."""

    def __init__(self, recent_html=PHI_PAGE):
        super().__init__(PHI_PAGE)
        self.recent_html = recent_html

    def get(self, path):
        html = super().get(path)
        return self.recent_html if command.RECENT in path else html


def _recent_lists(paths):
    """The paths of the team-filtered lists and the market pages in the recent view (not the waiver list)."""
    return [p for p in paths if f"stat1={command.RECENT}" in p and "status=W" not in p]


def test_a_second_run_on_the_same_day_reads_the_recent_view_from_the_cache(monkeypatch, tmp_path, capsys):
    first = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True)
    assert len(_recent_lists(first.paths)) == 3  # PHI, BOS and the market page
    assert "from the cache" not in capsys.readouterr().out
    assert 'id="cache-read"' not in (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    second = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True)
    assert _recent_lists(second.paths) == []
    # The run never takes the league pages, the projected view or the waiver list from the cache.
    assert second.paths == [p for p in first.paths if p not in _recent_lists(first.paths)]
    assert [p for p in second.paths if "status=W" in p and command.RECENT in p]
    _, rows = timing_rows(tmp_path)
    recent = [r["pages"] for r in rows if r["step"] == "Yahoo reads: recent pass"]
    assert recent == ["2", "0"]  # the page count counts only the pages from Yahoo
    line = re.search(r"The recent view: 3 pages from the cache of \d{4}-\d\d-\d\d \d\d:\d\d\.", capsys.readouterr().out)
    assert line
    html = (tmp_path / "adds_plan.html").read_text(encoding="utf-8")
    assert f'<p class="legend" id="cache-read">{line.group(0)}</p>' in run_time(html)


def test_a_run_on_the_next_day_reads_the_recent_view_from_yahoo(monkeypatch, tmp_path):
    run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True)
    tuesday = run_command(
        monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True, today=WEEK[1]
    )
    projected = [p for p in tuesday.paths if f"stat1={command.PROJECTED}" in p and "status=W" not in p]
    assert projected and _recent_lists(tuesday.paths) == [
        p.replace(command.PROJECTED, command.RECENT) for p in projected
    ]
    assert [d.name for d in (tmp_path / "cache" / "day").iterdir()] == [f"{WEEK[1]:%Y-%m-%d}"]


def test_no_cache_reads_each_page_from_yahoo(monkeypatch, tmp_path, capsys):
    first = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True)
    bypass = run_command(monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=False)
    assert bypass.paths == first.paths
    assert "from the cache" not in capsys.readouterr().out


def test_the_status_comes_from_the_projected_view_of_this_run(monkeypatch, tmp_path):
    import pandas as pd

    from fantasyhoops.adds.blend import blended_options

    scale, cfg = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"]), {"weights": {"pts": 1.0}}
    recents, renders = [], []

    def options(fas, recent):
        recents.append(recent)
        return blended_options(fas, recent, scale, cfg)

    real_render = page.render
    monkeypatch.setattr(page, "render", lambda *a, **kw: (renders.append(a), real_render(*a, **kw))[1])
    # The first run caches a recent view in which the Q players are O.
    run_command(
        monkeypatch,
        tmp_path,
        [],
        publish=False,
        settings=BOTH,
        yahoo=ViewPages(PHI_RECENT_OUT),
        cache=True,
        options=options,
    )
    second = run_command(
        monkeypatch, tmp_path, [], publish=False, settings=BOTH, yahoo=ViewPages(), cache=True, options=options
    )
    assert _recent_lists(second.paths) == []
    cached = {f.player.status for f in recents[-1]}
    assert "O" in cached and "Q" not in cached  # the recent view came from the cache
    statuses = {o.player.status for o in renders[-1][5]}
    assert "Q" in statuses and "O" not in statuses


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
    html = page.render(
        DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2, claim_row], OPTIONS + [CLAIM], RANKING, ["PHI"], WEEK[0],
        replacement=0.5, nights=nights, minutes_rise=3, timings=[timing.StepTime("Yahoo reads", 1.0)],
    )  # fmt: skip
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
    html = render(roles={("Phi One", "PHI"): role}, minutes_rise=4.0)
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
