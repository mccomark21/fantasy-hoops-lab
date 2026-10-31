import json
import re
from datetime import date

import pandas as pd

from fantasyhoops.adds.readers import Player
from fantasyhoops.core import chart, common, profile
from fantasyhoops.core import publish as site
from fantasyhoops.players import categories, data, page, value
from fantasyhoops.players.data import Played, Projected
from fantasyhoops.trade.rostered import RosteredPlayer, RosteredRead

CFG = {"league": {"teams": 14, "projections": "data/Projections_*.csv"}}
# The cats of Ace Bailey on the data of 2026-10-29 (players/categories.py), with the REB gap.
CATS = {
    "n": 5,
    "pool": 140,
    "rows": [
        {
            "cat": "PTS",
            "w": 1.0,
            "k": 4,
            "proj": 33.2,
            "now": 35.4,
            "line": 15.56,
            "raw": 14.2,
            "shrunk": 14.81,
            "nw": 0.56,
        },
        {
            "cat": "REB",
            "w": 1.0,
            "k": 4,
            "proj": 25.4,
            "now": 63.2,
            "line": 4.01,
            "raw": 8.0,
            "shrunk": 6.23,
            "nw": 0.56,
        },
    ],
    "gap": {"cat": "REB", "now": 63, "proj": 25},
}
OWNERS = [
    RosteredPlayer(Player("Ace Bailey", "UTAH", ("SF", "PF")), 0, {}, 1, "Lamb Chops"),
    RosteredPlayer(Player("Karl-Anthony Towns", "NY", ("PF", "C")), 0, {}, 3, "Doncic Go"),
]


def write(monkeypatch, root=None):
    """write_site() with fixture owners, projections and games. root: the repo root of the data files (common.ROOT).

    No root: a folder with no data files, so the page has no box scores and no projections file.
    """
    root = root or common.OUT / "no-data"
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "DATA", root / "data")
    projected = {"ace bailey": Projected("Ace Bailey", "UTAH", ("SF",), 0.52)}
    monkeypatch.setattr(data, "read_projected", lambda cfg: (projected, "Projections_2026-10-12.csv"))
    played = {"fa five": Played("Fa Five", "BOS", 5)}
    monkeypatch.setattr(data, "read_played", lambda: (played, "2026-10-20", "2026-10-28"))
    monkeypatch.setattr(categories, "read_categories", lambda cfg: {"ace bailey": CATS})
    read = RosteredRead(OWNERS, [], {}, [], True)
    return page.write_site(read, 1, CFG, date(2026, 10, 30), replacement=None)


def test_write_site_writes_the_page_the_player_file_and_the_font(monkeypatch):
    index, files = write(monkeypatch)
    assert index == common.OUT / "players" / "index.html" and files == (common.OUT / "players" / "players.json",)
    content = json.loads(files[0].read_text(encoding="utf-8"))
    assert content["meta"] == {
        "made": "2026-10-30",
        "rostered": 2,
        "free_agents": 1,
        "min_games": 5,
        "projections": "Projections_2026-10-12.csv",
        "log_first": "2026-10-20",
        "log_last": "2026-10-28",
        "replacement_rank": 15,
        "has_val": False,
        "value": None,
    }
    assert [p["slug"] for p in content["players"]] == ["ace-bailey", "fa-five", "karl-anthony-towns"]
    ace = content["players"][0]
    assert ace["cats"] == CATS and "cats" not in content["players"][1]
    assert ace["signals"] == [
        {"kind": "Projection gap", "quadrant": "cats", "up": True, "text": "REB above projection: percentile 63 vs 25"}
    ]
    assert content["bands"]["UTAH"] == site.band_style("UTAH") and content["bands"][""] == site.band_style(None)
    assert (index.parent / "fonts" / "archivo-latin.woff2").exists()
    html = index.read_text(encoding="utf-8")
    assert "3 players: 2 rostered and 1 free agents." in html
    assert html.count(chart.CHART_STYLE) == 1 and html.count('id="lab-pmodal"') == 1
    assert '<a href="../players/" aria-current="page">Players</a>' in html
    assert '"min_games"' not in html  # the page reads the shared file, it does not hold the players


def test_the_menu_and_the_page_head_describe_the_players_page():
    assert site.TOOLS["players"][0] == "Players" and "report card" in site.TOOLS["players"][1]
    html = page.render(CFG, {"rostered": 1, "free_agents": 0})
    assert "<title>Players</title>" in html and site.page_meta("players", "Players") in html
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", html.split("</nav>")[0])[-1] == "Players"


def records():
    out = []
    for n, (name, owner) in enumerate([("Ace Bailey", "Lamb Chops"), ("Karl-Anthony Towns", None), ("Fa Five", None)]):
        out.append(
            {
                "slug": profile.slug(name),
                "name": name,
                "team": "NY",
                "pos": "C",
                "owner": owner,
                "mine": False,
                "val": 3.0 - n,
                "games": 5,
                "signals": [],
            }
        )
    return out


def test_at_1440_by_900_the_header_and_the_4_quadrants_fit_with_no_page_scroll(modal_site):
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 2}), records=records())
    pg.locator("#pc-name").wait_for()
    assert pg.evaluate("location.hash") == "#ace-bailey"  # no hash: the first player
    assert pg.evaluate("document.documentElement.scrollHeight") <= 900
    quads = [q.bounding_box() for q in pg.locator("#pp-card .lc-q").all()]
    assert len(quads) == 4 and quads[0]["y"] == quads[1]["y"] and quads[0]["x"] < quads[1]["x"]
    assert max(q["y"] + q["height"] for q in quads) <= 900
    assert chart.style_problems(pg.content()) == []


def test_below_800px_the_quadrants_stack(modal_site):
    modal_site.page.set_viewport_size({"width": 390, "height": 844})
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 2}), records=records())
    pg.locator("#pc-name").wait_for()
    quads = [q.bounding_box() for q in pg.locator("#pp-card .lc-q").all()]
    assert len({round(q["x"]) for q in quads}) == 1 and [q["y"] for q in quads] == sorted(q["y"] for q in quads)
    assert pg.evaluate("document.documentElement.scrollWidth") <= 390


def test_the_search_finds_a_player_and_the_hash_keeps_the_pick_on_load_back_and_forward(modal_site):
    pg = modal_site.open(
        "players", page.render(CFG, {"rostered": 1, "free_agents": 2}), records=records(), hash="#fa-five"
    )
    pg.locator("#pc-name").wait_for()
    assert pg.locator("#pc-name").text_content() == "Fa Five"
    assert pg.title() == "Fa Five · Players · Fantasy Hoops Lab"
    pg.fill("#pp-q", "towns")
    pg.press("#pp-q", "Enter")
    pg.wait_for_function("document.getElementById('pc-name').textContent === 'Karl-Anthony Towns'")
    assert pg.evaluate("location.hash") == "#karl-anthony-towns"
    pg.go_back()
    pg.wait_for_function("document.getElementById('pc-name').textContent === 'Fa Five'")
    pg.go_forward()
    pg.wait_for_function("document.getElementById('pc-name').textContent === 'Karl-Anthony Towns'")
    pg.fill("#pp-q", "nobody")
    pg.press("#pp-q", "Enter")
    assert pg.locator("#pp-msg").text_content() == "No player on this page has that name."
    assert pg.evaluate("location.hash") == "#karl-anthony-towns"


class FailingReader:
    def __init__(self, error):
        self.error = error

    def get(self, path):
        raise self.error


def test_each_failed_owner_read_gives_none_and_a_warning(capsys):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    from fantasyhoops.adds.session import PageNotReady

    for error in (PlaywrightTimeout("Timeout"), ConnectionError("down"), PageNotReady("no table"), OSError("reset")):
        assert page.read_owners(FailingReader(error), True) is None
        assert f"({type(error).__name__}: " in capsys.readouterr().out


def test_the_players_page_has_its_own_tooltip_card_outside_the_closed_dialog(modal_site):
    """The modal tooltip sits in the dialog (build note 3). A closed dialog hides it, so the page has its own."""
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 2}), records=records())
    pg.locator("#pc-name").wait_for()
    assert pg.evaluate("LabCard.tip(document.getElementById('pp-card')).id") == "lab-tt-page"
    pg.evaluate(
        "(() => { const t = LabCard.tip(document.getElementById('pp-card'));"
        " t.textContent = 'Oct 28 vs SA'; t.style.left = '300px'; t.style.top = '300px'; t.hidden = false; })()"
    )
    assert pg.locator("#lab-tt-page").is_visible()
    pg.goto(modal_site.url + "players/#player=ace-bailey")
    pg.locator("#lab-pm-name").wait_for()
    assert pg.evaluate("LabCard.tip(document.getElementById('lab-pm-card')).id") == "lab-tt"


def test_a_yahoo_block_in_the_owner_read_is_not_caught():
    """#107: a Yahoo block stops the planning run."""
    import pytest

    from fantasyhoops.adds.session import YahooBlocked

    with pytest.raises(YahooBlocked):
        page.read_owners(FailingReader(YahooBlocked("HTTP 999")), True)


STAT_KEYS = ["pts", "reb", "ast", "threes", "stl", "blk"]
QUAD_CFG = {**CFG, "weights": dict.fromkeys(STAT_KEYS, 1.0)}
QUAD_CFG["players"] = {
    "value": {"window": 3, "band_min": 3, "flag_min": 5, "prior_games": 4, "band_sd": 2, "consistency_min_games": 5}
}
SCALE = pd.DataFrame({c: [1.0, 1.0] for c in STAT_KEYS}, index=["mean", "std"])


def quadrant_data(root, names, games):
    """data/box_scores.csv with games games of each name, and a projections file with each name."""
    (root / "data").mkdir(parents=True)
    box = [
        {
            "game_id": str(100 + g),
            "date": f"2026-10-{20 + g}",
            "team": "NY",
            "opponent": "SA",
            "player_id": str(i),
            "player": name,
            "starter": True,
            "played": True,
            **{"pts": 2 + i + g % 3, "reb": 1, "ast": 1, "fg3m": 1, "stl": 1, "blk": 1},
        }
        for i, name in enumerate(names)
        for g in range(games)
    ]
    pd.DataFrame(box).to_csv(root / "data" / "box_scores.csv", index=False)
    rows = [
        {"player_id": i, "first_name": n.split()[0], "last_name": n.split()[1], "games": 10, "minutes": 300 - i}
        for i, n in enumerate(names)
    ]
    stats = {"field_goals": 40, "threes": 10, "free_throws": 10, "offensive_rebounds": 10, "defensive_rebounds": 10}
    stats |= {"assists": 10, "steals": 10, "blocks": 10}
    projections = pd.DataFrame(rows).assign(**stats)
    projections.to_csv(root / "data" / "Projections_2026-10-12.csv", index=False)


def test_the_quadrants_add_the_value_block_the_comps_and_the_consistency_signal(monkeypatch, tmp_path):
    names = ["Ace Bailey", "Bo Two", "Cy Three", "Di Four", "Ed Five", "Fa Six", "Gu Seven"]
    root = tmp_path / "repo"
    quadrant_data(root, names, 5)
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "DATA", root / "data")
    found = [{"slug": profile.slug(n), "name": n, "val": 1.0 + i, "signals": []} for i, n in enumerate(names)]
    meta = page.add_quadrants(found, QUAD_CFG, date(2026, 10, 30), SCALE, 0.0)
    assert meta["spike"] == 1.0 and meta["window"] == 3  # 7 Vals: the top-30 level is the last one
    ace = found[0]
    assert ace["value"]["n"] == 5 and ace["value"]["svg"].startswith('<svg class="lab-chart"')
    assert len(ace["comps"]) == 5 and ace["comps"][0]["slug"] == "bo-two"
    assert ace["signals"] == [{"kind": "Consistency", "quadrant": "value", "up": True, "text": "Spikes: 5 of 5 games"}]


def test_with_no_val_the_value_quadrant_says_so_and_the_comps_stay(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    quadrant_data(root, ["Ace Bailey", "Bo Two"], 2)
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "DATA", root / "data")
    found = [{"slug": profile.slug(n), "name": n, "val": None, "signals": []} for n in ("Ace Bailey", "Bo Two")]
    assert page.add_quadrants(found, QUAD_CFG, date(2026, 10, 30), SCALE, None) is None
    assert found[0]["value"] == {"n": 0, "empty": value.NO_VAL}
    assert [c["slug"] for c in found[0]["comps"]] == ["bo-two"]
    # No scale (a run with no projections file): no value chart and no comps.
    assert page.add_quadrants(found, QUAD_CFG, date(2026, 10, 30), None, None) is None
    assert found[0]["value"] == {"n": 0, "empty": value.NO_VAL} and found[0]["comps"] is None


def quadrant_records():
    """The records() players and 2 more, each with a Value block and comps. Ace Bailey has 4 games, the others 5."""
    from tests.players.test_value import ACE, ACE_SD, games

    extra = [("bo-two", "Bo Two"), ("cy-three", "Cy Three")]
    out = records() + [
        {"slug": s, "name": n, "team": "BOS", "pos": "PG", "owner": None, "mine": False, "val": 0.5, "games": 5}
        for s, n in extra
    ]
    for i, r in enumerate(out):
        n = 4 if i == 0 else 5
        r["value"] = value.value_block(games(n), ACE[:n], ACE_SD, 4.0)
        others = [o for o in out if o is not r]
        r["comps"] = [{"slug": o["slug"], "dist": 0.5 + j, "cat": "REB", "diff": -1.19} for j, o in enumerate(others)]
    return out


def test_the_value_and_comps_quadrants_draw_the_sample_look_with_tooltips(modal_site):
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 4}), records=quadrant_records())
    pg.locator("#pc-name").wait_for()
    value_q = pg.locator("#pc-q-value")
    assert value_q.locator("h3 .lc-lab").inner_text() == "Duds 1 of 4 (25%) · Spikes 1 of 4 (25%)"
    assert value_q.locator("svg.lab-chart").count() == 1
    state = value_q.locator(".lab-c-state").inner_text()
    assert state.startswith("Too few games for a flag: 4 of 5.") and state.endswith("One game moves a rate 25 points.")
    content = pg.content()
    assert chart.style_problems(content) == [] and chart.label_overlaps(content) == []
    # A mouse on a game column shows the card right of the mark, and the crosshair.
    value_q.locator(".lab-c-hit").nth(1).hover()
    tip = pg.locator("#lab-tt-page")
    tip.wait_for(state="visible")
    assert tip.locator(".lab-tt-ctx").inner_text() == "Oct 21 vs SA · bench"
    assert tip.locator(".lab-tt-num").inner_text() == "−3.37"
    assert tip.locator(".lab-tt-lab").inner_text() == "value · dud"
    assert tip.locator("dt").all_inner_texts() == ["PTS · REB · AST", "3PM · STL · BLK", "3-game avg"]
    assert value_q.locator(".lab-c-cross").get_attribute("visibility") == "visible"
    hit, card = value_q.locator(".lab-c-hit").nth(1).bounding_box(), tip.bounding_box()
    assert card["x"] > hit["x"] + hit["width"] / 2
    pg.mouse.move(5, 5)
    tip.wait_for(state="hidden")
    assert value_q.locator(".lab-c-cross").get_attribute("visibility") == "hidden"
    # The keyboard: each game column is a tab stop with the card text as its aria-label.
    first = value_q.locator(".lab-c-hit").first
    assert first.get_attribute("tabindex") == "0" and first.get_attribute("aria-describedby") == "lab-tt-page"
    assert first.get_attribute("aria-label").startswith("Oct 20 vs SA · start. value +1.95. PTS · REB · AST 12 · 5 · 3")
    first.focus()
    tip.wait_for(state="visible")
    pg.keyboard.press("Escape")
    tip.wait_for(state="hidden")
    # Comps: the rows in file order (nearest first) with Val, owner or FA and the biggest difference.
    rows = pg.locator("#pc-q-comps tbody tr")
    assert rows.count() == 4 and pg.locator("#pc-q-comps h3 .lc-lab").inner_text() == "nearest 4 on the blended line"
    assert rows.first.locator("th small").inner_text() == "C · FA"
    assert rows.first.locator("td").all_inner_texts()[1:] == ["+2.00", "REB −1.19"]
    rows.first.hover()
    tip.wait_for(state="visible")
    assert tip.locator(".lab-tt-ctx").inner_text() == "Karl-Anthony Towns · FA"
    assert tip.locator("dd").all_inner_texts() == ["REB −1.19 z", "0.50", "+3.00"]
    assert tip.locator("dt").all_inner_texts()[2] == "Bailey's Val"


def test_the_value_and_comps_quadrants_fit_in_the_modal_and_the_page_at_1440_by_900(modal_site):
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 4}), records=quadrant_records())
    pg.locator("#pc-name").wait_for()
    assert pg.evaluate("document.documentElement.scrollHeight") <= 900
    pg.goto(modal_site.url + "players/#player=ace-bailey")
    pg.locator("#lab-pm-name").wait_for()
    fit = pg.evaluate(
        "(() => { const d = document.getElementById('lab-pmodal'); return [d.scrollHeight, d.clientHeight]; })()"
    )
    assert fit[0] <= fit[1], fit
    pg.locator("#lab-pm-card .lab-c-hit").first.hover()
    pg.locator("#lab-tt").wait_for(state="visible")
    pg.keyboard.press("Escape")  # the first Escape hides the card, and the modal stays open
    pg.locator("#lab-tt").wait_for(state="hidden")
    assert pg.evaluate("document.getElementById('lab-pmodal').open")
    assert pg.locator("#lab-pm-card .lab-c-cross").get_attribute("visibility") == "hidden"


def test_a_player_with_no_block_gets_the_empty_boxes(modal_site):
    found = records()
    found[0]["value"] = {"n": 0, "empty": value.NO_GAMES}
    found[0]["comps"] = None
    pg = modal_site.open("players", page.render(CFG, {"rostered": 1, "free_agents": 2}), records=found)
    pg.locator("#pc-name").wait_for()
    assert pg.locator("#pc-q-value .lab-c-empty").inner_text() == value.NO_GAMES
    assert pg.locator("#pc-q-comps .lab-c-empty").inner_text() == "No projection and no recent games: no comps."
