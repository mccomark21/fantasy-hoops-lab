import re
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.core import chart, profile, publish, roster as roster_page, tokens
from fantasyhoops.core.roster import NO_GAME, REST, SITS, START, Day, RosterPlayer, lineup_fit, playoff_days, render

SLOTS = ["PG", "C"]  # 2 position slots + Util = 3 starters a day
MON = date(2027, 3, 8)


def day(n, week, teams, quality=False, b2b=()):
    return Day(MON + timedelta(days=n), week, quality, frozenset(teams), frozenset(b2b))


# Two weeks of two days. Day 1 is the second night of a back-to-back for AAA. Day 3 is a quality day.
DAYS = [
    day(0, "wk19", {"AAA", "BBB", "CCC"}),
    day(1, "wk19", {"AAA", "BBB"}, b2b={"AAA"}),
    day(2, "wk20", {"BBB", "CCC"}),
    day(3, "wk20", {"AAA"}, quality=True),
]

# Rank order: Guard (PG), Big (C, on IL), Second guard (PG, rests on back-to-backs), Third guard (PG), Wing (no slot).
PLAYERS = [
    RosterPlayer("Third Guard", "BBB", ("PG",), "BN", rank=40),
    RosterPlayer("Guard One", "AAA", ("PG",), "PG", rank=10),
    RosterPlayer("Second Guard", "AAA", ("PG", "SG"), "BN", rank=30, rests_b2b=True),
    RosterPlayer("Big Man", "CCC", ("C",), "IL", status="O", rank=20),
    RosterPlayer("No Rank", "BBB", ("SF",), "BN"),
]


def test_the_fit_puts_the_il_player_in_the_pool_and_the_higher_rank_first():
    fit = lineup_fit(PLAYERS, DAYS, SLOTS)
    assert [p.name for p in fit.players] == ["Guard One", "Big Man", "Second Guard", "Third Guard", "No Rank"]
    # Day 0: Guard One (PG), Big Man (C, IL), Second Guard (Util). Third Guard and No Rank sit.
    # Day 1: AAA on a second night: Second Guard rests. Guard One (PG), Third Guard (Util). No Rank sits.
    # Day 2: Big Man (C), Third Guard (PG), No Rank (Util).
    # Day 3: Guard One (PG), Second Guard (Util). Quality day with 1 open slot (C).
    assert fit.marks == [
        [START, START, NO_GAME, START],
        [START, NO_GAME, START, NO_GAME],
        [START, REST, NO_GAME, START],
        [SITS, START, START, NO_GAME],
        [SITS, SITS, START, NO_GAME],
    ]
    assert fit.started == [3, 2, 3, 2]
    assert fit.holes == [0, 0, 0, 1]
    assert fit.lost() == {"No Rank": 2, "Third Guard": 1}


def test_the_week_cells_count_no_rest_night_as_a_game():
    fit = lineup_fit(PLAYERS, DAYS, SLOTS)
    second = [p.name for p in fit.players].index("Second Guard")
    assert fit.player_week(second, "wk19") == (1, 1, 0)
    assert fit.player_week(second, "wk20") == (1, 1, 1)
    assert fit.player_week(second) == (2, 2, 1)


def test_used_and_vs_ideal_use_the_math_of_the_draft_board():
    fit = lineup_fit(PLAYERS, DAYS, SLOTS)
    # Used: started / the games of the players with no rest nights.
    # wk19 games: Guard 2, Big 1, Second 1 (rest night out), Third 2, No Rank 2 = 8. Started 3 + 2 = 5.
    # vs ideal: min(5 players x 2 games (the most of any team), 3 slots x 2 game days) = 6.
    assert fit.team_week("wk19") == (5, 8, 6)
    # wk20 games: Guard 1, Big 1, Second 1, Third 1, No Rank 1 = 5. Started 3 + 2 = 5.
    # vs ideal: min(5 x 1, 3 x 2) = 5.
    assert fit.team_week("wk20") == (5, 5, 5)
    assert fit.team_week() == (10, 13, 11)


def test_a_day_with_no_nba_game_is_not_in_the_ideal():
    days = [*DAYS[:2], day(2, "wk19", set())]
    assert lineup_fit(PLAYERS, days, SLOTS).team_week("wk19") == (5, 8, 6)


CFG = {
    "league": {"slots": SLOTS, "espn_season": 2027, "teams": 14},
    "flags": {"avoid_week_games": 1},
}


def page():
    stats = {"gp": 3, "min": 30.0, "pts": 25.0, "reb": 5.33, "ast": 6.33, "threes": 1.67, "stl": 3.67, "blk": 1.67}
    players = [p if p.name != "Guard One" else RosterPlayer(**{**p.__dict__, "stats": stats}) for p in PLAYERS]
    return render(players, DAYS, CFG, week=2, adds=(2, 5), today=date(2026, 10, 28), team_name="TradeMark™")


def test_the_page_shows_the_roster_in_rank_order_with_the_il_flag_and_the_stats():
    text = page()
    names = re.findall(r'<th class="pl" scope="row"><b><a class="lab-pname" [^>]*>([^<]+)</a></b>', text)
    assert names == ["Guard One", "Big Man", "Second Guard", "Third Guard", "No Rank"]
    assert (
        '<b><a class="lab-pname" href="#player=big-man" data-player="big-man">Big Man</a></b> <em class="flag" title="On IL now. Counts in the playoff starts.">IL</em>'
        in text
    )
    assert '<tr class="il">' in text and '<details class="m-p il">' in text
    assert '<td class="n s1">3</td><td class="n">30.0</td><td class="n">25.0</td><td class="n">5.3</td>' in text
    assert '<td class="rk">–</td>' in text  # No Rank
    assert "<h1>TradeMark<sup>™</sup></h1>" in text
    assert '<strong class="red">2</strong> of 5 adds used' in text


def test_the_page_shows_the_totals_rows_with_the_bands_of_pctclass():
    text = page()
    assert "<b>Team starts</b>" in text and ">Team starts</th>" in text
    assert "Used (started / games) · 10/13 · 77%" in text
    assert "vs ideal · 10/11 · 91%" in text
    # wk19 Used 5/8 = 63% (below 70%), wk20 Used 5/5 = 100% (90% or more), total 10/13 = 77% (70% to 89%)
    assert '<span class="pc p1">' in text and "<b>63%</b>" in text and "(less than 70%)" in text
    assert '<span class="pc p3">' in text and "<b>100%</b>" in text
    assert '<span class="pc p2">' in text and "(70% to 89%)" in text
    assert "3 starts lost to a full lineup (Rank 2, Guard 1) · 1 open slot on quality days" in text


def test_a_week_with_few_games_has_the_red_box_and_the_text():
    text = page()
    # [flags] avoid_week_games = 1: the wk19 cell of Big Man (1 game) has the box. T cells have no box.
    assert '1<s aria-hidden="true">/<span class="few">1</span></s>' in text
    assert "starts of 1 game, 2 or fewer games" in text


def test_the_day_grid_marks_the_quality_day_and_the_rest_night():
    text = page()
    assert '<th scope="col" class="d q"><abbr title="Thursday March 11, quality day">T</abbr><u>11</u></th>' in text
    assert 'aria-label="Tue Mar 9: rests on back-to-back"' in text
    assert '<th scope="col" class="d wk1"><abbr title="Wednesday March 10">W</abbr><u>10</u></th>' in text


def test_the_page_uses_the_shared_tokens_the_menu_and_no_colors_of_its_own():
    text = page()
    assert tokens.TOKENS in text
    assert (
        text.split("</nav>")[0].count('<li><a href="') == 6
        and '<a href="../roster/" aria-current="page">Roster</a>' in text
    )
    assert 'href="../adds/">Adds plan</a>' in text and '<a href="../">Home</a>' in text  # #172: /roster/
    style = re.sub(r"/\*.*?\*/", "", roster_page.PAGE_STYLE, flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgb\(", style)
    assert ".flag { font-style: normal; font-size: 11px; font-weight: 800; color: var(--lab-on-red);" in style


def test_the_page_is_the_html_before_the_page_shell():
    """#132: fixtures/home_before_132.html is page() before publish.shell(), with 14 teams in config.toml.

    The render reads no config.toml: the team count of the menu comes from CFG, and core/publish.py has no
    load_config(). #172 moved the page to /roster/ and changed the site menu, so the test compares the page with no
    site menu. #186 made each name a link to the player modal and added the modal, so the test removes both.
    #192 put the shared chart style in the page head, so the test removes it too.
    """
    meta = "\n" + publish.page_meta("roster", "Roster · Fantasy Hoops Lab")  # #166 added the icon and preview tags
    before = (Path(__file__).parent / "fixtures" / "home_before_132.html").read_text(encoding="utf-8")
    menu = re.compile(r'<header class="lab-bar">.*?<div class="lab-scrim" hidden></div>', re.S)
    now = re.sub(r'<a class="lab-pname" [^>]*>([^<]*)</a>', r"\1", page().replace(meta, ""))
    now = now.replace(profile.modal(chart_css=False) + "\n", "").replace(chart.CHART_STYLE + "\n", "")
    assert menu.sub("", now) == menu.sub("", before)
    assert publish.site_menu("roster", 14) in page()


def test_the_page_passes_the_chart_style_check_and_the_label_overlap_check():
    """#192: the two checks of #185. The page head has the shared chart style once, so the modal has no copy of it."""
    text = page()
    assert chart.style_problems(text) == [] and chart.label_overlaps(text) == []
    assert text.count(chart.CHART_STYLE) == 1 and "__CHART_CSS__" not in text
    assert text.index(chart.CHART_STYLE) < text.index("</head>")
    assert profile.modal(chart_css=False) in text


def test_each_team_band_has_text_at_4_5_to_1():
    for color in tokens.TEAM_COLORS.values():
        assert tokens.contrast(color, tokens.team_ink(color)) >= 4.5, color


def test_playoff_days_has_each_date_of_the_weeks():
    sched = pd.DataFrame(
        {
            "date": pd.to_datetime(["2027-03-08", "2027-03-08", "2027-03-09", "2027-03-09"]),
            "team": ["AAA", "BBB", "AAA", "CCC"],
        }
    )
    cfg = {
        "playoffs": {
            "weeks": [{"name": "wk19", "start": date(2027, 3, 8), "end": date(2027, 3, 10)}],
            "week_value": {"3": 1.0},
        },
        "quality_games": {"max_games_per_day": 6, "bonus": 0.1},
        "flags": {"avoid_week_games": 2},
    }
    days = playoff_days(sched, cfg)
    assert [d.date.day for d in days] == [8, 9, 10]
    assert days[1].teams == {"AAA", "CCC"} and days[1].b2b == {"AAA"} and days[1].quality
    assert days[2].teams == frozenset()


@contextmanager
def browser_page(width, scheme="light"):
    """A Chromium page from Playwright. The test skips if Chromium is not installed (as in CI)."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Error as e:
            pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")
        try:
            yield browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
        finally:
            browser.close()


def record_page():
    return render(PLAYERS, DAYS, CFG, week=2, adds=(2, 5), team_name="TradeMark™", record="4-2-1")


def test_the_header_shows_the_record_then_the_week_items():
    text = record_page()
    start = text.index('<header class="head">')
    head = text[start : text.index("</header>", start)]
    assert '<dl class="meta with-rec">' in head
    assert head.index("<h1>") < head.index("<dt>Record</dt>") < head.index("<dt>This week</dt>")
    assert head.index("<dt>This week</dt>") < head.index("<dt>Playoffs</dt>")
    assert '<div class="rec"><dt>Record</dt><dd><strong>4-2-1</strong></dd></div>' in head


def test_the_header_has_no_record_when_the_run_has_none():
    text = page()
    start = text.index('<header class="head">')
    head = text[start : text.index("</header>", start)]
    assert '<dl class="meta">' in head and "Record" not in head and 'class="rec"' not in head


@pytest.mark.parametrize("width", [390, 1280])
def test_the_record_and_the_week_items_follow_the_name(width):
    with browser_page(width) as pg:
        pg.set_content(record_page())
        h1, rec, week, playoffs = (
            pg.locator(sel).bounding_box()
            for sel in ("h1", ".meta .rec", ".meta div:nth-child(2)", ".meta div:nth-child(3)")
        )
        assert pg.evaluate("document.documentElement.scrollWidth") <= width
        if width == 1280:
            # One line: the name, the record, This week and Playoffs, left to right, close to the name.
            assert h1["x"] + h1["width"] <= rec["x"] < week["x"] < playoffs["x"]
            assert rec["x"] - (h1["x"] + h1["width"]) <= 40
            assert all(abs((b["y"] + b["height"]) - (h1["y"] + h1["height"])) <= 12 for b in (rec, week, playoffs))
        else:
            # Below the name: the record at the left, This week and Playoffs stacked at its right.
            assert rec["y"] >= h1["y"] + h1["height"]
            assert week["x"] > rec["x"] and playoffs["x"] == week["x"] and playoffs["y"] > week["y"]


@pytest.mark.parametrize("width", [390, 1280])
def test_the_header_items_are_4_5_to_1_or_more_in_light_and_dark_mode(width):
    from tests.adds.test_page import CONTRAST

    with browser_page(width) as pg:
        pg.set_content(record_page())
        # Check the header only: the record, This week and Playoffs (#142).
        pg.add_style_tag(content="main.roster > :not(header.head) { display: none !important; }")
        assert pg.locator("header.head .rec").is_visible()
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(CONTRAST) == [], theme


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_the_roster_page_has_no_sideways_scroll_and_4_5_to_1_text_in_light_and_dark_mode(width):
    """#140 page tests for the Roster page at /roster/ (#172). The desktop table scrolls inside its own region."""
    from tests.adds.test_page import CONTRAST

    with browser_page(width) as pg:
        pg.set_content(record_page())
        pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme)
            assert pg.evaluate(CONTRAST) == [], (width, theme)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_phone_shows_rows_that_open_and_no_horizontal_scroll(scheme):
    with browser_page(390, scheme) as pg:
        pg.set_content(page())
        assert not pg.locator("table.desk").is_visible()
        row = pg.locator("details.m-p").nth(1)
        assert not row.locator(".m-grid").is_visible()
        row.locator("summary").click()
        assert row.locator(".m-grid").is_visible()
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_desktop_shows_the_table_and_the_red_text_passes_aa(scheme):
    with browser_page(1440, scheme) as pg:
        pg.set_content(page())
        assert pg.locator("table.desk").is_visible() and not pg.locator("section.mob").is_visible()
        colors = pg.evaluate(
            "(() => { const f = getComputedStyle(document.querySelector('th.pl .flag'));"
            " return [f.color, f.backgroundColor]; })()"
        )

        def hex_of(rgb):
            return "#" + "".join(f"{int(x):02x}" for x in re.findall(r"\d+", rgb)[:3])

        assert tokens.contrast(hex_of(colors[0]), hex_of(colors[1])) >= 4.5


# The look of each visible element of the Roster table and of the phone rows: the box and the computed style.
ROSTER_LOOK = r"""() => {
  const props = ["color", "backgroundColor", "fontSize", "fontWeight", "fontStretch", "lineHeight", "textAlign",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth", "borderBottomWidth",
    "borderLeftWidth", "borderBottomColor", "borderLeftColor", "boxShadow", "textTransform", "verticalAlign"];
  document.querySelectorAll("details.m-p").forEach(d => d.open = true);
  // A hidden element (the table on a phone, the phone rows on a desktop) has no box and does not count.
  // The name links of #186 are new. The test compares the other elements.
  return [...document.querySelectorAll(".scroll *, section.mob *")]
    .filter(el => el.getClientRects().length && !el.matches("a.lab-pname")).map(el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return [el.tagName, el.className, Math.round(r.left), Math.round(r.top), Math.round(r.width),
      Math.round(r.height), ...props.map(p => s[p])].join("|");
  });
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_the_shared_table_css_does_not_change_the_roster_table(width):
    """#143: the Roster table and the phone rows look as before the move of their CSS to publish.TABLE_STYLE.

    fixtures/home_before_143.html is page() before #143. Each element has the same box and the same style.
    """
    before = (Path(__file__).parent / "fixtures" / "home_before_143.html").read_text(encoding="utf-8")
    with browser_page(width) as pg:
        for theme in ("light", "dark"):
            looks = []
            for html in (before, page()):
                pg.set_content(html)
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                looks.append([line.replace(" lab-t", "") for line in pg.evaluate(ROSTER_LOOK)])
            assert looks[0] == looks[1], (width, theme)


def test_the_page_has_the_icon_links_and_the_preview_tags():
    """#166, #172: the head of the Roster page has publish.page_meta() of /roster/ with the page title."""
    assert publish.page_meta("roster", "Roster · Fantasy Hoops Lab") in page()


def test_a_player_name_opens_the_player_modal(modal_site):
    """#186: each name of the Roster table is a link that opens the player modal."""
    modal_site.open("roster", page())
    assert modal_site.check_modal() == "guard-one"


def test_on_a_phone_the_name_opens_the_modal_and_the_rest_of_the_row_opens_the_row(modal_site):
    """#186: before #186, a tap on a phone row opened its details. The tap keeps that action. Only the name opens
    the modal."""
    modal_site.page.set_viewport_size({"width": 390, "height": 844})
    pg = modal_site.open("roster", page())
    row = pg.locator("details.m-p").first
    row.locator(".gp").click()
    assert row.evaluate("d => d.open") and not pg.evaluate("document.getElementById('lab-pmodal').open")
    row.locator(".gp").click()
    assert not row.evaluate("d => d.open")
    row.locator("a.lab-pname").click()
    pg.locator("#lab-pm-name").wait_for()
    assert not row.evaluate("d => d.open")
