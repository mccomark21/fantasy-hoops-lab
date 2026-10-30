import re

import pytest

from fantasyhoops.core import card_cats, chart, profile
from fantasyhoops.players import page

CFG = {"league": {"teams": 14}}
META = {"rostered": 1, "free_agents": 1}
G = card_cats.GEOMETRY
CY = G["T"] + G["ROW"] / 2  # the track of the first row


def row(cat, w, k, proj, now, line=2.0, raw=2.5, shrunk=2.2, nw=0.5):
    return {"cat": cat, "w": w, "k": k, "proj": proj, "now": now, "line": line, "raw": raw, "shrunk": shrunk, "nw": nw}


# The cats of Ace Bailey on the data of 2026-10-29 (players/categories.py).
ACE = {
    "n": 5,
    "pool": 140,
    "rows": [
        row("PTS", 1.0, 4, 33.2, 35.4, 15.56, 14.2, 14.81, 0.56),
        row("REB", 1.0, 4, 25.4, 63.2, 4.01, 8.0, 6.23, 0.56),
        row("AST", 1.0, 4, 11.1, 19.6, 2.1, 2.4, 2.26, 0.56),
        row("3PM", 0.7, 10, 57.5, 58.9, 2.03, 1.6, 1.88, 0.33),
        row("BLK", 0.65, 10, 67.5, 81.8, 0.81, 1.6, 1.07, 0.33),
        row("STL", 0.5, 15, 22.5, 4.6, 0.84, 0.0, 0.63, 0.25),
    ],
    "gap": {"cat": "REB", "now": 63, "proj": 25},
}


def record(name, cats=None, signals=()):
    out = {
        "slug": profile.slug(name),
        "name": name,
        "team": "UTAH",
        "pos": "SF",
        "owner": None,
        "mine": False,
        "val": 1.0,
        "games": 5,
        "signals": list(signals),
    }
    if cats is not None:
        out["cats"] = cats
    return out


def open_card(site, records, hash=""):
    pg = site.open("players", page.render(CFG, META), records=records, hash=hash)
    pg.locator("#pc-name").wait_for()
    return pg


def x(v):
    return G["L"] + (G["W"] - G["L"] - G["R"]) * v / 100


def texts(pg, root="#pc-q-cats"):
    return pg.eval_on_selector_all(
        f"{root} svg text",
        "ns => ns.map(n => [n.textContent, +n.getAttribute('x'), +n.getAttribute('y'),"
        " n.getAttribute('text-anchor') || 'start', n.getAttribute('class')])",
    )


def test_the_modal_of_each_page_has_the_categories_fill():
    text = profile.modal()
    assert "LabCard.fill.cats = " in text and card_cats.STYLE in text
    assert (
        text.index("window.LabCard = ")
        < text.index("LabCard.fill.cats = ")
        < text.index('getElementById("lab-pmodal")')
    )
    assert f'"apart": {chart.NOW_PROJ_APART}' in card_cats.script()


def test_the_chart_has_6_dot_on_track_rows_and_passes_the_style_and_overlap_checks(modal_site):
    pg = open_card(modal_site, [record("Ace Bailey", ACE)])
    q = "#pc-q-cats"
    pg.locator(f"{q} svg").wait_for()
    assert "percentile of the 140-player pool" in pg.locator(f"{q} h3").inner_text()
    for cls in ("lab-c-track", "lab-c-conn", "lab-c-proj", "lab-c-hero-dot", "lab-c-hit"):
        assert pg.locator(f"{q} svg .{cls}").count() == 6, cls
    assert pg.locator(f"{q} svg .lab-c-ref").count() == 1  # the 50th pct line, no gridlines
    found = texts(pg)
    labels = [t[0] for t in found]
    assert labels[:4] == ["0", "50th pct", "100", "per game"]
    # Each row: the category, its punt weight from the config weights, the per-game value and the projection.
    assert ["×1.00", "×1.00", "×1.00", "×0.70", "×0.65", "×0.50"] == [t for t in labels if t.startswith("×")]
    assert {"PTS", "REB", "AST", "3PM", "BLK", "STL", "14.2", "proj 15.6", "0.0", "proj 0.8"} <= set(labels)
    assert labels.count("now") == 1 and labels.count("proj") == 1  # only the first row labels its dots
    # The REB row: the hollow projection dot at 25.4 and the "now" dot at 63.2.
    dots = pg.eval_on_selector_all(
        f"{q} svg circle", "ns => ns.map(n => [n.getAttribute('class'), +n.getAttribute('cx'), +n.getAttribute('r')])"
    )
    assert dots[2] == ["lab-c-proj", pytest.approx(x(25.4), abs=0.01), 4]
    assert dots[3] == ["lab-c-hero-dot", pytest.approx(x(63.2), abs=0.01), 5]
    assert pg.locator(f"{q} .lab-c-state").inner_text() == (
        "5 games: the season line has 56% of the weight for PTS, 25% for STL."
    )
    content = pg.content()
    assert chart.style_problems(content) == [] and chart.label_overlaps(content) == []
    assert not re.search(r"legend", pg.locator(q).inner_html())


@pytest.mark.parametrize("now, proj", [(35.4, 33.2), (70, 20), (20, 70), (50, 55), (55, 50), (0, 2), (100, 98)])
def test_the_now_and_proj_labels_follow_the_label_rule(modal_site, now, proj):
    cats = {**ACE, "rows": [row("PTS", 1.0, 4, proj, now), *ACE["rows"][1:]]}
    pg = open_card(modal_site, [record("Ace Bailey", cats)])
    pg.locator("#pc-q-cats svg").wait_for()
    found = {t[0]: t for t in texts(pg) if t[0] in ("now", "proj")}
    want_now, want_proj = chart.now_proj(x(now), x(proj), CY)
    assert found["now"][1:4] == [pytest.approx(want_now[0], abs=0.01), want_now[1], want_now[2]]
    assert found["proj"][1:4] == [pytest.approx(want_proj[0], abs=0.01), want_proj[1], want_proj[2]]
    assert found["now"][4] == "lab-c-label" and found["proj"][4] == "lab-c-tick"
    assert chart.label_overlaps(pg.content()) == []


def test_a_player_with_no_projection_shows_the_no_data_box(modal_site):
    pg = open_card(modal_site, [record("Ace Bailey", ACE), record("Fa Five")], hash="#fa-five")
    box = pg.locator("#pc-q-cats .lc-body .lab-c-empty")
    assert box.inner_text() == card_cats.NO_DATA == "No projection: no category ranks."
    assert pg.locator("#pc-q-cats svg").count() == 0
    assert "percentile of" not in pg.locator("#pc-q-cats h3").inner_text()


def test_a_player_with_no_game_shows_his_projection_as_now(modal_site):
    rows = [{**r, "now": r["proj"], "raw": None, "nw": 0} for r in ACE["rows"]]
    pg = open_card(modal_site, [record("Ace Bailey", {**ACE, "n": 0, "rows": rows, "gap": None})])
    assert pg.locator("#pc-q-cats .lab-c-state").inner_text() == "No games yet: now is the projection."
    assert "–" in [t[0] for t in texts(pg)]
    assert chart.label_overlaps(pg.content()) == []


def test_a_row_shows_the_tooltip_card_on_hover_and_on_focus(modal_site):
    pg = open_card(modal_site, [record("Ace Bailey", ACE)])
    hit = pg.locator("#pc-q-cats .lab-c-hit").nth(1)
    hit.hover()
    tip = pg.locator("#lab-tt-page")
    tip.wait_for(state="visible")
    assert tip.locator(".lab-tt-ctx").inner_text() == "REB · punt weight 1.00"
    assert (
        tip.locator(".lab-tt-num").inner_text() == "63rd"
        and tip.locator(".lab-tt-lab").inner_text() == "percentile now"
    )
    rows = tip.locator(".lab-tt-rows").inner_text().split("\n")
    assert [r.strip() for r in rows if r.strip()] == [
        "Projection",
        "25th",
        "Per game now",
        "8.0 (shrunk 6.2)",
        "Season weight",
        "56% after 5 games",
    ]
    # The card sits beside the marks of the row, not over them.
    card, mark = tip.bounding_box(), pg.locator("#pc-q-cats .lab-c-hero-dot").nth(1).bounding_box()
    assert card["x"] >= mark["x"] + mark["width"] or card["x"] + card["width"] <= mark["x"]
    assert hit.get_attribute("aria-describedby") == "lab-tt-page"
    assert hit.get_attribute("aria-label").startswith("REB · punt weight 1.00. percentile now 63rd. Projection 25th.")
    pg.mouse.move(5, 5)
    tip.wait_for(state="hidden")
    pg.locator("#pc-q-cats .lab-c-hit").first.focus()
    tip.wait_for(state="visible")
    assert tip.locator(".lab-tt-ctx").inner_text() == "PTS · punt weight 1.00"
    pg.keyboard.press("Escape")
    tip.wait_for(state="hidden")


def test_in_the_modal_the_first_escape_hides_the_card_and_the_next_closes_the_modal(modal_site):
    pg = open_card(modal_site, [record("Ace Bailey", ACE)], hash="#player=ace-bailey")
    pg.locator("#lab-pm-q-cats svg").wait_for()
    pg.locator("#lab-pm-q-cats .lab-c-hit").nth(4).focus()
    tip = pg.locator("#lab-tt")
    tip.wait_for(state="visible")
    assert tip.locator(".lab-tt-ctx").inner_text() == "BLK · punt weight 0.65"
    pg.keyboard.press("Escape")
    tip.wait_for(state="hidden")
    assert pg.evaluate("document.getElementById('lab-pmodal').open")
    pg.keyboard.press("Escape")
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")


def test_with_the_chart_the_card_fits_at_1440_by_900(modal_site):
    pg = open_card(modal_site, [record("Ace Bailey", ACE)])
    pg.locator("#pc-q-cats svg").wait_for()
    assert pg.evaluate("document.documentElement.scrollHeight") <= 900
    modal_site.page.set_viewport_size({"width": 390, "height": 844})
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390
