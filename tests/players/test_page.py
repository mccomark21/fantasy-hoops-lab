import json
import re
from datetime import date

from fantasyhoops.adds.readers import Player
from fantasyhoops.core import chart, common, profile
from fantasyhoops.core import publish as site
from fantasyhoops.players import data, page
from fantasyhoops.players.data import Played, Projected
from fantasyhoops.trade.rostered import RosteredPlayer

CFG = {"league": {"teams": 14}}
OWNERS = [
    RosteredPlayer(Player("Ace Bailey", "UTAH", ("SF", "PF")), 0, {}, 1, "Lamb Chops"),
    RosteredPlayer(Player("Karl-Anthony Towns", "NY", ("PF", "C")), 0, {}, 3, "Doncic Go"),
]


def write(monkeypatch):
    projected = {"ace bailey": Projected("Ace Bailey", "UTAH", ("SF",), 0.52)}
    monkeypatch.setattr(data, "read_projected", lambda cfg: (projected, "Projections_2026-10-12.csv"))
    played = {"fa five": Played("Fa Five", "BOS", 5)}
    monkeypatch.setattr(data, "read_played", lambda: (played, "2026-10-20", "2026-10-28"))
    return page.write_site(OWNERS, 1, CFG, date(2026, 10, 30))


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
    }
    assert [p["slug"] for p in content["players"]] == ["ace-bailey", "fa-five", "karl-anthony-towns"]
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
        assert page.read_owners(FailingReader(error)) is None
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
