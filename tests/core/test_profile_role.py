import json
import re
import shutil
import subprocess

import pandas as pd
import pytest

from fantasyhoops.core import chart, profile, profile_role
from fantasyhoops.core.publish import shell
from fantasyhoops.players import page, role

CFG = {
    "league": {"teams": 14},
    "players": {"role": {"window": 3, "band_min": 3, "flag_min": 5, "prior_games": 4, "band_sd": 2}},
}
SPREAD = 5.37

# Node runs the card script and the Role script with no DOM, then prints the SVG of each role.
DRIVER = r"""
globalThis.window = globalThis;
globalThis.document = { addEventListener() {}, getElementById() { return null; } };
globalThis.addEventListener = () => {};
const src = require("fs").readFileSync(0, "utf8");
const [code, roles] = src.split("@@ROLES@@");
eval(code);
console.log(JSON.stringify(JSON.parse(roles).map(r => ({ svg: LabCard.role.draw(r).svg, heads: LabCard.role.heads(r) }))));
"""


def series(minutes, close_every=0, usg=True):
    n = len(minutes)
    rows = pd.DataFrame(
        {
            "date": pd.date_range("2026-10-21", periods=n, freq="2D"),
            "opponent": ["SA"] * n,
            "started": [i % 2 == 0 for i in range(n)],
            "minutes": minutes,
            "close_game": [bool(close_every) and i % close_every == 0 for i in range(n)],
            "competitive_minutes": [m - (i % 4) * 2.5 for i, m in enumerate(minutes)],
            "usg": [18.0 + i % 7 for i in range(n)] if usg else [float("nan")] * n,
        }
    )
    return role.role_record(rows, SPREAD, CFG)


ACE = [24.3, 21.7, 29.2, 34.1, 39.5]
ROLES = {
    "one": series([31.0]),
    "two": series(ACE[:2]),
    "three": series(ACE[:3]),
    "four": series([10.0, 10.0, 40.0, 40.0]),
    "five": series(ACE, close_every=2),
    "up": series([20.0] * 8 + [40.0] * 3, close_every=3),
    "back": series([30.0] * 6 + [12.0] * 3 + [30.0] * 3),
    "down": series([40.0] * 8 + [20.0] * 3),
    "season": series([28 + 9 * ((i * 7) % 5 - 2) / 2 for i in range(82)], close_every=4),
    "no usage": series([30.0, 31.0, 29.0], usg=False),
}


def draw(roles):
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    code = profile.card_script() + "\n" + profile_role.script()
    out = subprocess.run(
        ["node", "-e", DRIVER],
        input=code + "\n@@ROLES@@" + json.dumps(roles),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def drawn():
    return dict(zip(ROLES, draw(list(ROLES.values()))))


def texts(svg):
    return [re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<text\b[^>]*>(.*?)</text>", svg)]


@pytest.mark.parametrize("name", list(ROLES))
def test_each_chart_passes_the_style_check_and_the_label_overlap_check(drawn, name):
    svg = drawn[name]["svg"]
    assert chart.style_problems(svg) == []
    assert chart.label_overlaps(svg) == []


def test_the_marks_of_the_role_chart(drawn):
    svg = drawn["five"]["svg"]
    assert svg.count('class="lab-c-game"') == 5  # a game dot for the total minutes of each game
    assert svg.count('class="lab-c-hero"') == 1 and svg.count('class="lab-c-hero-dot"') == 1
    assert svg.count('class="lab-c-second"') == 1  # the competitive minutes
    assert svg.count('class="lab-c-band"') == 1
    assert svg.count('class="lab-c-hit"') == 5 and svg.count('class="lab-c-cross"') == 1
    labels = texts(svg)
    assert "3-game 34.3" in labels and "competitive 39.5" in labels and "game 39.5" in labels
    assert any(t.startswith("normal range ") for t in labels)
    assert [t for t in labels if t.startswith("Oct") or t.startswith("Nov")] == [
        "Oct 21",
        "Oct 23",
        "Oct 25",
        "Oct 27",
        "Oct 29",
    ]
    for kind, radius in (("game", "3.5"), ("hero-dot", "4")):
        assert re.search(rf'class="lab-c-{kind}"[^>]* r="{radius}"', svg)


def test_under_3_games_no_band_and_no_hero_line(drawn):
    for name in ("one", "two"):
        svg = drawn[name]["svg"]
        assert "lab-c-band" not in svg and "lab-c-hero" not in svg and "normal range" not in svg
    assert ROLES["two"]["state"] == ["Too few games for a range:", "2 of 3."]


def test_with_one_hero_point_the_chart_draws_the_hero_dot_only(drawn):
    svg = drawn["three"]["svg"]
    assert 'class="lab-c-hero-dot"' in svg and 'class="lab-c-hero"' not in svg


def test_with_3_or_4_games_the_band_shows_but_no_flag(drawn):
    for name in ("three", "four"):
        assert "lab-c-band" in drawn[name]["svg"] and "out" not in "".join(texts(drawn[name]["svg"]))


def test_a_range_exit_gets_the_out_label(drawn):
    assert "▲ out" in texts(drawn["up"]["svg"])
    assert "▼ out" in texts(drawn["down"]["svg"])
    # In "back", the dip sits at the bottom of the plot between the lines, so no side is clear: no label.
    assert ROLES["back"]["exits"] == [[8, "down"]] or ROLES["back"]["exits"] == [(8, "down")]
    assert re.search(r'class="lab-c-exit"[^>]*>▲ out<', drawn["up"]["svg"])


def test_with_many_games_the_dates_do_not_touch(drawn):
    svg = drawn["season"]["svg"]
    dates = [t for t in texts(svg) if re.match(r"[A-Z][a-z]{2} \d", t)]
    assert 8 <= len(dates) < 82 and dates[-1] == ROLES["season"]["games"][-1]["d"]
    assert svg.count('class="lab-c-game"') == 82


def test_the_head_labels_give_the_usage_and_the_close_game_minutes(drawn):
    five = ROLES["five"]
    assert five["close_n"] == 3 and five["usg_last"] is not None
    heads = drawn["five"]["heads"]
    delta = five["usg_last"] - five["usg"]
    arrow = "▲" if delta >= 0 else "▼"
    assert f"USG <b>{round(five['usg'])}%</b> {arrow} " in heads and "last 3" in heads
    assert f"Close <b>3 of 5</b>: {five['close_min']:.1f} min ({five['other_min']:.1f} other)" in heads
    assert "USG <b>–</b>" in drawn["no usage"]["heads"]
    assert "(too few games for a trend)" in drawn["two"]["heads"]
    assert "Close <b>0 of 2</b>" in drawn["two"]["heads"]


# The chart in the browser: the Players page and the modal


def record(name, found):
    return {
        "slug": profile.slug(name),
        "name": name,
        "team": "UTAH",
        "pos": "SF/PF",
        "owner": None,
        "mine": False,
        "val": 1.0,
        "games": len(found["games"]) if found else 0,
        "role": found,
        "signals": [],
    }


def test_the_players_page_draws_the_role_quadrant_with_its_tooltip(modal_site):
    records = [record("Ace Bailey", ROLES["five"]), record("No Games", None), record("Up Guy", ROLES["up"])]
    pg = modal_site.open("players", page.render(CFG, {"rostered": 0, "free_agents": 3}), records=records)
    pg.locator("#pc-q-role svg.lab-chart").wait_for()
    head = pg.locator("#pc-h-role").inner_text()
    assert head.lower().startswith("role") and "USG" in head and "Close 3 of 5" in head
    assert pg.locator("#pc-q-role .lab-c-state").inner_text().startswith("Range = mean ± ")
    # The methods note has the Role line of METHODS.
    assert "Role. Minutes and competitive minutes" in pg.locator("#pp-card .lc-pop").text_content()
    assert chart.style_problems(pg.content()) == [] and chart.label_overlaps(pg.content()) == []
    # At 1440 x 900, the card still fits with no page scroll.
    assert pg.evaluate("document.documentElement.scrollHeight") <= 900
    # A mouse on a game column shows the shared tooltip card and the crosshair.
    hit = pg.locator("#pc-q-role .lab-c-hit").nth(4)
    hit.hover()
    tip = pg.locator("#lab-tt-page")
    assert tip.is_visible()
    assert tip.locator(".lab-tt-ctx").inner_text() == "Oct 29 vs SA · start · close game"
    assert (
        tip.locator(".lab-tt-num").inner_text() == "39.5 min" and tip.locator(".lab-tt-lab").inner_text() == "minutes"
    )
    assert tip.locator(".lab-tt-rows dt").all_inner_texts() == ["Competitive", "3-game avg", "Usage"]
    assert pg.locator("#pc-q-role .lab-c-cross").get_attribute("visibility") == "visible"
    tb, hb = tip.bounding_box(), hit.bounding_box()
    assert tb["x"] + tb["width"] <= hb["x"] + hb["width"] / 2 or tb["x"] >= hb["x"] + hb["width"] / 2  # beside it
    pg.mouse.move(5, 5)
    assert tip.is_hidden()
    # The first game has no 3-game average yet. Focus shows the card, and Esc hides it.
    pg.locator("#pc-q-role .lab-c-hit").first.focus()
    assert tip.locator(".lab-tt-rows dd").nth(1).inner_text() == "needs 3 games"
    assert pg.locator("#pc-q-role .lab-c-hit").first.get_attribute("aria-describedby") == "lab-tt-page"
    pg.keyboard.press("Escape")
    assert tip.is_hidden()
    # A player with no games gets the dashed box. A range exit gets the label and the signal text is up to #186.
    pg.evaluate("location.hash = 'no-games'")
    pg.locator("#pc-q-role .lab-c-empty").wait_for()
    assert "No games in the rotation log" in pg.locator("#pc-q-role").inner_text()
    pg.evaluate("location.hash = 'up-guy'")
    pg.locator("#pc-q-role .lab-c-exit").wait_for()
    assert pg.locator("#pc-q-role .lab-c-state").inner_text() == ROLES["up"]["state"][1]


def test_in_the_modal_the_first_esc_hides_the_tooltip_and_the_second_closes_the_modal(modal_site):
    links = f"<p><b>{profile.name_link('Ace Bailey')}</b></p>"
    template = '<html><head><meta charset="utf-8"><title>Test</title>__HEAD__</head><body class="lab">__MENU__'
    body = f"<main class='lab-main'>{links}</main>__PLAYER_MODAL__\n__SCRIPT__</body></html>"
    pg = modal_site.open("roster", shell(template + body, "roster", CFG), records=[record("Ace Bailey", ROLES["five"])])
    pg.locator('a.lab-pname[data-player="ace-bailey"]:visible').first.click()
    pg.locator("#lab-pm-q-role svg.lab-chart").wait_for()
    pg.locator("#lab-pm-q-role .lab-c-hit").nth(2).focus()
    assert pg.locator("#lab-tt").is_visible()
    pg.keyboard.press("Escape")
    assert pg.locator("#lab-tt").is_hidden() and pg.evaluate("document.getElementById('lab-pmodal').open")
    assert pg.locator("#lab-pm-q-role .lab-c-cross").get_attribute("visibility") == "hidden"
    pg.keyboard.press("Escape")
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    assert chart.style_problems(pg.content()) == []
