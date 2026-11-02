"""The Playoffs page (#214): the page data, the page HTML and the page script.

1. page_data() gives each pool player a number value: the Val, else the proj_val, else 0 (review nit 1 of #216).
2. The page HTML has the site menu item, the controls and both scripts.
3. In Node, the page script gives the best core, the headline, the grid rows and the Starts, Open slots and NBA
   games rows from valueStarted() of core/starts.js. The R switch, the core size, Save and Reset change the state.
4. In Chromium, the page has no sideways scroll at 390 px, and Save and Reset use localStorage.
"""

import copy
import json
import re
import shutil
import subprocess
from datetime import date

import pytest

from fantasyhoops.core import common, publish as site
from fantasyhoops.core.lineup import ENGINE_JS
from fantasyhoops.core.roster import Day
from fantasyhoops.playoffs import page
from tests.core.test_roster import browser_page

CFG = copy.deepcopy(common.load_config())
CFG["playoffs"]["core"] = 3
CFG["quality_games"]["bonus"] = 0.1
CFG["trade"]["untouchable"] = ["Al Dal"]
CFG["trade"]["value_band"] = [0.95, 1.10]

# Two weeks of two days. 3/9 and 3/16 are light nights and the second night of a back-to-back of their teams.
DAYS = [
    Day(date(2027, 3, 8), "wk19", False, frozenset({"DAL", "NO", "ORL", "BOS"})),
    Day(date(2027, 3, 9), "wk19", True, frozenset({"DAL", "NO"}), frozenset({"DAL", "NO"})),
    Day(date(2027, 3, 15), "wk20", False, frozenset({"ORL", "DAL", "NO", "BOS"})),
    Day(date(2027, 3, 16), "wk20", True, frozenset({"ORL", "BOS"}), frozenset({"ORL"})),
]


def record(name, team, pos, val=None, proj_val=None, owner=None, mine=False, rests=0):
    slug = name.lower().replace(" ", "-")
    return dict(
        slug=slug, name=name, team=team, pos=pos, owner=owner, mine=mine, val=val, proj_val=proj_val, rests_b2b=rests
    )


RECORDS = [
    record("Al Dal", "DAL", "SF", 7.0, owner="Me", mine=True),
    record("Bo No", "NO", "PG", 5.0, owner="Me", mine=True, rests=1),
    record("Cy Orl", "ORL", "C", 4.0, owner="Me", mine=True),
    record("Di Orl", "ORL", "PF", None, 3.0, owner="Me", mine=True),
    record("Ed Dal", "DAL", "SF", 1.0, owner="Me", mine=True),
    record("Fa Bos", "BOS", "PG/SG", 6.0, owner="Lamb Chops"),
    record("Gus Free", "NO", "", None, None),
    record("Hé Accent", "BOS", "C", 2.0),
]


# The pool of the Best swaps tests (#215), with the core of the page: Al Dal (untouchable), Cy Orl and Bo No.
# Value started alone: Al Dal 21.7, Cy Orl 12.4, Bo No 10 (2 starts, he rests on 3/9).
SWAP_RECORDS = RECORDS + [
    record("Ivy Bos", "BOS", "PG", 5.2, owner="Lamb Chops"),  # in the band of Bo No: gain 6.12, schedule 5.72
    record("Jo Free", "BOS", "PF", 4.5),  # for Bo No: gain 3.95, schedule 3.95 + 0.5 x 2 = 4.95
    record("Lu Bos", "BOS", "C", 9.0, owner="Lamb Chops"),  # in no value band of the core: no row
    record("Kai Free", "BOS", "C", 9.0),  # a free agent has no band. For Bo No: gain 17.9, schedule 17.9 - 4 x 2
]


def data(records=RECORDS):
    return page.page_data(records, DAYS, CFG, "2026-10-31")


def test_each_pool_player_gets_a_number_value_with_its_mark():
    """Review nit 1 of #216: the page gives val, else proj_val, so no null value reaches valueStarted()."""
    players = {p["id"]: p for p in data()["players"]}
    assert [p["id"] for p in data()["players"]] == [r["slug"] for r in RECORDS]
    assert (players["al-dal"]["value"], players["al-dal"]["mark"]) == (7.0, "")
    assert (players["di-orl"]["value"], players["di-orl"]["mark"]) == (3.0, page.PROJ)
    assert (players["gus-free"]["value"], players["gus-free"]["mark"]) == (0.0, page.NO_VAL)
    assert all(isinstance(p["value"], float) for p in players.values())
    assert players["fa-bos"]["pos"] == ["PG", "SG"] and players["gus-free"]["pos"] == []
    assert players["bo-no"]["rests_b2b"] == 1 and players["fa-bos"]["owner"] == "Lamb Chops"


def test_the_page_data_has_the_days_the_settings_of_the_config_and_the_bands():
    d = data()
    assert d["core"] == 3 and d["quality_bonus"] == 0.1 and d["slots"] == CFG["league"]["slots"] and d["util"] == 1
    assert d["weeks"] == ["wk19", "wk20"] and d["span"] == "Mar 8–16"
    assert d["days"][1] == {
        "date": "2027-03-09",
        "week": "wk19",
        "quality": True,
        "games": 1,
        "teams": ["DAL", "NO"],
        "b2b": ["DAL", "NO"],
    }
    assert d["bands"]["DAL"] == site.band_style("DAL") and d["bands"][""] == site.band_style(None)
    # Decision 18: [trade] value_band and untouchable of config.toml, the same settings as the Trades page.
    assert d["band"] == [0.95, 1.10] and d["untouchable"] == ["al-dal"]


def test_the_page_has_the_menu_item_the_controls_and_the_scripts():
    html = page.render(data(), CFG)
    assert site.TOOLS["playoffs"][0] == "Playoffs"
    assert '<li><a href="../playoffs/" aria-current="page">Playoffs</a></li>' in html
    assert (
        "<title>Playoffs · Fantasy Hoops Lab</title>" in html
        and site.page_meta("playoffs", "Playoffs · Fantasy Hoops Lab") in html
    )
    assert '<input id="n" type="number" min="1" value="3">' in html and ">Reset to best 3</button>" in html
    assert "<strong>Wk19–20</strong> · Mar 8–16" in html and "Data: the planning run of Sat 10/31" in html
    assert ENGINE_JS.read_text(encoding="utf-8") in html and page.SCRIPT.read_text(encoding="utf-8") in html
    assert html.count('id="lab-pmodal"') == 1 and 'id="grid"' in html and 'id="mob"' in html
    assert '<h2 id="h-sw">Best swaps</h2>\n<div id="sw"></div>' in html
    assert not re.findall(r"__[A-Z0-9_]+__", html)


def test_write_site_reads_the_player_file_and_writes_the_page(tmp_path):
    file = tmp_path / "players.json"
    file.write_text(json.dumps({"meta": {"made": "2026-10-31"}, "players": RECORDS}), encoding="utf-8")
    path = page.write_site(file, DAYS, CFG)
    assert path == common.OUT / "playoffs" / "index.html" and (path.parent / "fonts").exists()
    assert '"id":"al-dal"' in path.read_text(encoding="utf-8")


# The page script in Node: argv the page script. stdin: {data, steps}. Each step changes the state, then the
# driver keeps the view. A step is ["open", saved], ["n", n], ["rest", id], ["pick", id], ["core", ids], ["reset"],
# ["filter", owner filter] or ["swap", [id in, id out]]. swaps: the rows of the Best swaps list of each filter.
DRIVER = """
const P = require(process.argv[1]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { data, steps } = JSON.parse(text);
  const m = P.model(data);
  let st = P.open(m, null);
  const out = [];
  for (const [kind, arg] of steps) {
    if (kind === "open") st = P.open(m, arg);
    if (kind === "n") { st.n = arg; st.core = P.bestCore(m, st, arg); }
    if (kind === "rest") st.rest[arg] = !(arg in st.rest ? st.rest[arg] : !!m.byId[arg].rests_b2b);
    if (kind === "pick") P.pick(m, st, arg);
    if (kind === "core") st.core = arg;
    if (kind === "reset") P.reset(m, st);
    if (kind === "filter") st.filter = arg;
    if (kind === "swap") P.swap(m, st, arg[0], arg[1]);
    if (kind === "search") { out.push(P.search(m, arg).map(p => p.id)); continue; }
    const v = P.view(m, st);
    out.push({ state: { ...st }, total: v.score.total, marks: v.score.marks, days: v.score.days, html: v,
      light: Object.fromEntries(st.core.map(id => [id, P.lightNights(m, st, id)])),
      swaps: Object.fromEntries(["fa", "other", "all"].map(f => [f, P.swaps(m, st, f)])) });
  }
  process.stdout.write(JSON.stringify(out));
});
"""

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")


def run(steps, given=None):
    out = subprocess.run(
        ["node", "-e", DRIVER, str(page.SCRIPT)],
        input=json.dumps({"data": given or data(), "steps": steps}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


@needs_node
def test_the_page_opens_on_the_best_core_of_your_players():
    """Decision 11: the N players of your roster with the highest value started. N is [playoffs] core."""
    (v,) = run([["n", 3]])
    # Alone: Al Dal 7 x 2 + 7 x 1.1 = 21.7, Cy Orl 4 x 2 + 4 x 1.1 = 12.4, Bo No 5 x 2 = 10 (he rests on 3/9),
    # Di Orl 3 x 2 + 3 x 1.1 = 9.3
    assert v["state"]["core"] == ["al-dal", "cy-orl", "bo-no"]
    first = run([["open", None]])[0]
    assert first["state"]["core"] == ["al-dal", "cy-orl", "bo-no"] and first["state"]["n"] == 3


@needs_node
def test_the_headline_and_the_grid_come_from_value_started():
    (v,) = run([["open", None]])
    # Al Dal: 3/8, 3/9 (light), 3/15. Cy Orl: 3/8, 3/15, 3/16 (light). Bo No: 3/8, 3/15, and he rests on 3/9.
    total = v["total"]
    assert total.pop("value") == pytest.approx(21.7 + 12.4 + 10)
    assert total == {
        "starts": 8,
        "light_starts": 2,
        "lost": 0,
        "open_heavy": 12 - 6,
        "open_light": 12 - 2,
        "games": 8,
        "ideal": 12,
    }
    assert v["marks"]["bo-no"] == ["s", "r", "s", "n"]
    html = v["html"]
    assert "<dt>Value started</dt><dd>44.1</dd>" in html["stats"]
    assert (
        "<dt>Starts lost</dt><dd>0</dd>" in html["stats"] and "<dd>16<small>6 heavy · 10 light</small>" in html["stats"]
    )
    grid = html["grid"]
    body = grid.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count("<tr>") == 3 and body.index("al-dal") < body.index("bo-no") < body.index("cy-orl")
    assert '<em class="tag" title="Rests on back-to-backs">R</em>' in body
    foot = grid.split("<tfoot>")[1]
    assert [re.search(r'scope="row">([^<]+)<', r).group(1) for r in foot.split("</tr>")[:3]] == [
        "Starts",
        "Open slots",
        "NBA games",
    ]
    # Owner decision of 2026-11-01: starts of the core games, and the ideal of the Roster page (2 games x 3 players
    # each week).
    said = "8 starts of 8 games, ideal 12: 0 lost to slot clashes, 4 below ideal"
    assert (
        f'<td class="w t"><span aria-hidden="true" title="{said}">8<small>of 8</small><small>ideal 12</small>' in foot
    )
    assert f'<span class="vh">{said}</span>' in foot
    assert "<td>4 / 4<small>0 lost to slot clashes</small></td><td>6<small>2 below ideal</small></td>" in html["weeks"]
    assert '<tr class="t"><th class="l" scope="row">Total</th><td>44.1</td><td>8 / 8<small>' in html["weeks"]
    assert "<dd>8<small>/ 8 games · ideal 12</small></dd>" in html["stats"]
    assert '<dd class="sub">0 lost to slot clashes · 4 below ideal</dd>' in html["stats"]
    assert "<small>of 8 games</small><small>ideal 12</small>" in html["phone"]
    assert html["phone"].count('<details class="m-p">') == 3 and "Starts each day, of 6" in html["phone"]
    assert html["reset"] == "Reset to best 3" and html["saved"] == "Not saved"


@needs_node
def test_each_player_shows_a_light_night_count():
    """Decision 6: the light nights with a game that he does not rest."""
    (v,) = run([["open", None]])
    assert v["light"] == {"al-dal": 1, "cy-orl": 1, "bo-no": 0}
    assert "<td>7.0</td><td>1</td>" in v["html"]["players"]


@needs_node
def test_the_players_table_writes_its_colgroup_and_the_separator_rows_span_each_column():
    """Review nit of #217: the column count of the Players table is in one place (PLAYER_COLS of playoffs.js)."""
    (v,) = run([["open", None]])
    players = v["html"]["players"]
    cols = re.search(r"<colgroup>(.*?)</colgroup>", players).group(1).count("<col")
    assert cols == 7 and players.count(f'<tr class="sep"><td colspan="{cols}">') == 2
    assert players.count('<th scope="col"') == cols


@needs_node
def test_the_r_switch_changes_the_starts_on_the_second_night_of_a_back_to_back():
    off, on = run([["rest", "bo-no"], ["rest", "al-dal"]])
    assert off["marks"]["bo-no"] == ["s", "s", "s", "n"] and off["light"]["bo-no"] == 1
    assert on["marks"]["al-dal"] == ["s", "r", "s", "n"] and on["light"]["al-dal"] == 0
    assert on["state"]["rest"] == {"bo-no": False, "al-dal": True}
    assert 'data-rest="al-dal" aria-pressed="true"' in on["html"]["players"]


@needs_node
def test_a_new_core_size_picks_the_core_again():
    (v,) = run([["n", 4]])
    assert v["state"]["core"] == ["al-dal", "cy-orl", "bo-no", "di-orl"] and v["html"]["reset"] == "Reset to best 4"
    assert '<em class="tag">proj</em>' in v["html"]["players"]


@needs_node
def test_the_search_finds_free_agents_and_other_teams_and_a_pick_adds_to_the_core():
    hits, added = run([["search", "he"], ["pick", "fa-bos"]])
    assert hits == ["hé-accent"]  # the accent does not count
    assert run([["search", "free"]])[0] == ["gus-free"] and run([["search", "g"]])[0] == []
    assert added["state"]["core"][-1] == "fa-bos" and added["state"]["added"] == ["fa-bos"]
    assert "Outside the core · 2" in added["html"]["players"] and 'data-drop="fa-bos"' in added["html"]["players"]


@needs_node
def test_reset_clears_the_added_players_the_r_switches_and_the_save():
    saved = {
        "n": 2,
        "core": ["fa-bos", "ed-dal", "no-such-player"],
        "added": ["fa-bos"],
        "rest": {"al-dal": True},
        "saved": "2026-11-01T15:00:00.000Z",
    }
    opened, reset = run([["open", saved], ["reset"]])
    assert opened["state"]["core"] == ["fa-bos", "ed-dal"] and opened["state"]["rest"] == {"al-dal": True}
    assert opened["html"]["saved"].startswith("Saved Sun 11/1") and opened["html"]["reset"] == "Reset to best 2"
    assert reset["state"] == {
        "n": 2,
        "core": ["al-dal", "cy-orl"],
        "added": [],
        "rest": {},
        "saved": None,
        "filter": "all",
    }


@needs_node
def test_the_players_table_shows_the_adds_of_each_player_and_flags_the_weakest_link():
    """Decision 9: Adds = the value started of the core with the player minus without him."""
    (v,) = run([["open", None]])
    players = v["html"]["players"]
    assert (
        '<th scope="col" title="The value started of the core with the player minus without him">Adds</th>' in players
    )
    # The core has no slot clash, so the Adds of a core player is his value started alone.
    assert '<td class="a"><span>+21.7</span></td>' in players and '<td class="a"><span>+12.4</span></td>' in players
    weak = '<td class="a"><span>+10.0</span><br><em class="tag weak" title="The core player with the lowest Adds">'
    assert players.count('class="tag weak"') == 1 and weak in players
    assert players.index('data-core="bo-no"') < players.index(weak) < players.index('data-core="di-orl"')
    # Di Orl outside the core: 3 x 2 + 3 x 1.1 = 9.3 if added
    assert '<td class="a"><span>+9.3</span><small>if added</small></td>' in players


@needs_node
def test_a_core_player_with_a_val_below_0_has_adds_below_0():
    """Review nit 3 of #216: a core player with a Val below 0 still starts. His Adds is below 0, so he is the weakest."""
    given = data([*RECORDS, record("Neg Dal", "DAL", "PF", -2.0, owner="Me", mine=True)])
    (v,) = run([["core", ["al-dal", "cy-orl", "neg-dal"]]], given)
    assert v["marks"]["neg-dal"] == ["s", "s", "s", "n"]
    assert '<td class="a"><span class="neg">−6.2</span><br><em class="tag weak"' in v["html"]["players"]


@needs_node
def test_the_best_swaps_rank_by_schedule_gain_with_an_owner_filter():
    """Decisions 16 to 18 on the pool of SWAP_RECORDS: the rows of each owner filter, gain above 0 only."""
    (v,) = run([["open", None]], data(SWAP_RECORDS))
    pairs = {
        f: [(r["in"], r["out"], round(r["schedule"], 2), round(r["gain"], 2)) for r in rows]
        for f, rows in v["swaps"].items()
    }
    assert pairs["all"] == [
        ("kai-free", "bo-no", 9.9, 17.9),
        ("ivy-bos", "bo-no", 5.72, 6.12),
        ("jo-free", "bo-no", 4.95, 3.95),
    ]
    assert pairs["fa"] == [pairs["all"][0], pairs["all"][2]] and pairs["other"] == [pairs["all"][1]]
    assert all(r["gain"] > 0 for rows in v["swaps"].values() for r in rows)
    html = v["html"]["swaps"]
    assert '<button type="button" class="chip" data-filter="all" aria-pressed="true">All</button>' in html
    assert '<tr class="few"><td colspan="6">Only 3 players have a swap that raises value started.</td></tr>' in html
    row = '<tr tabindex="0" data-swap="kai-free" data-out="bo-no" aria-label="Load the swap: Kai Free in, Bo No out">'
    assert row in html and '<td class="g">+9.9</td><td>+17.9</td><td>+1 <small>(+1 light)</small></td>' in html
    assert "Never swapped out: Al Dal. Free agents: no band." in html
    (fa,) = run([["filter", "fa"]], data(SWAP_RECORDS))
    assert "Only 2 free agents have a swap" in fa["html"]["swaps"] and 'data-swap="ivy-bos"' not in fa["html"]["swaps"]


@needs_node
def test_no_swap_takes_out_an_untouchable_player_for_any_owner():
    """Decision 18: Al Dal is [trade] untouchable. Kai Free for Al Dal raises value started (27.9 - 21.7), but no row
    has it."""
    (v, alone) = run([["open", None], ["core", ["al-dal"]]], data(SWAP_RECORDS))
    assert all(r["out"] != "al-dal" for s in (v, alone) for rows in s["swaps"].values() for r in rows)
    assert alone["swaps"]["all"] == [] and "Only 0 players have a swap" in alone["html"]["swaps"]
    cfg = copy.deepcopy(CFG)
    cfg["trade"]["untouchable"] = []
    (free,) = run([["core", ["al-dal"]]], page.page_data(SWAP_RECORDS, DAYS, cfg, "2026-10-31"))
    assert ("kai-free", "al-dal") in [(r["in"], r["out"]) for r in free["swaps"]["fa"]]


@needs_node
def test_no_other_team_row_has_a_val_outside_the_value_band_of_the_player_out():
    """Decision 18: a player of another team is listed only in the value band of the player out. Free agents: no band."""
    given = data(SWAP_RECORDS)
    (v,) = run([["open", None]], given)
    value = {p["id"]: p["value"] for p in given["players"]}
    owned = {p["id"] for p in given["players"] if p["owner"]}
    band = given["band"]
    for r in v["swaps"]["all"]:
        if r["in"] in owned:
            give = value[r["out"]]
            assert give - (1 - band[0]) * abs(give) <= value[r["in"]] <= give + (band[1] - 1) * abs(give)
    assert "lu-bos" not in {r["in"] for r in v["swaps"]["all"]}  # Lu Bos (Val 9) is in no band of the core
    assert "kai-free" in {r["in"] for r in v["swaps"]["fa"]}  # the free agent with the same Val has no band


@needs_node
def test_a_swap_loads_into_the_core_and_the_grid_and_the_headline_show_the_new_core():
    (before, after) = run([["open", None], ["swap", ["kai-free", "bo-no"]]], data(SWAP_RECORDS))
    assert after["state"]["core"] == ["al-dal", "cy-orl", "kai-free"] and after["state"]["added"] == ["kai-free"]
    assert after["total"]["value"] == pytest.approx(before["total"]["value"] + 17.9)
    assert 'data-player="kai-free"' in after["html"]["grid"] and 'data-player="bo-no"' not in after["html"]["grid"]
    assert f"<dd>{after['total']['value']:.1f}</dd>" in after["html"]["stats"]


def test_the_page_in_chromium_has_no_sideways_scroll_on_a_phone_and_save_and_reset_work(tmp_path):
    path = common.OUT / "playoffs" / "index.html"
    site.write_page(path, page.render(data(), CFG))
    with browser_page(390) as pg:
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(path.as_uri())
        assert pg.evaluate("document.documentElement.scrollWidth") <= 390
        assert pg.locator("#grid").is_hidden() and pg.locator("details.m-p").count() == 3
        assert pg.locator("#stats .hero dd").inner_text() == "44.1"
        pg.locator('[data-rest="al-dal"]').click()
        pg.locator("#save").click()
        assert pg.locator("#saved").inner_text().startswith("Saved")
        pg.reload()
        assert pg.locator('[data-rest="al-dal"]').get_attribute("aria-pressed") == "true"
        assert pg.locator("#saved").inner_text().startswith("Saved")
        pg.locator("#reset").click()
        assert pg.locator('[data-rest="al-dal"]').get_attribute("aria-pressed") == "false"
        assert pg.evaluate("localStorage.getItem('fhl-playoffs')") is None
        assert pg.locator("#saved").inner_text() == "Not saved" and not errors


def test_in_chromium_a_filter_changes_the_best_swaps_and_a_click_on_a_row_loads_the_swap(tmp_path):
    path = common.OUT / "playoffs" / "index.html"
    site.write_page(path, page.render(data(SWAP_RECORDS), CFG))
    with browser_page(1440) as pg:
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(path.as_uri())
        pg.evaluate("localStorage.clear()")
        pg.reload()
        assert pg.locator("#sw tr[data-swap]").count() == 3
        pg.locator('#sw [data-filter="other"]').click()
        assert pg.locator("#sw tr[data-swap]").count() == 1
        assert pg.locator('#sw [data-filter="other"]').get_attribute("aria-pressed") == "true"
        pg.locator('#sw [data-filter="all"]').click()
        pg.locator('#sw tr[data-swap="kai-free"] td').first.click()
        assert pg.locator("#stats .hero dd").inner_text() == "62.0"  # 44.1 + 17.9
        assert pg.locator('#grid [data-player="kai-free"]').count() == 1
        assert pg.locator('#grid [data-player="bo-no"]').count() == 0 and not errors


def test_the_trades_and_playoffs_pages_give_one_value_and_one_value_band_for_one_player():
    """#223: for the same player, the Trades page and the Playoffs page use the same Val and the same value band."""
    from fantasyhoops.adds.readers import Player
    from fantasyhoops.core.season_value import SeasonLine, SeasonValues
    from fantasyhoops.players.data import season_vals
    from fantasyhoops.trade import page as trade_page
    from fantasyhoops.trade.rostered import RosteredPlayer, RosteredRead
    from fantasyhoops.trade.run import trade_players
    from fantasyhoops.trade.suggest import Suggestions, TradeSettings, in_band

    season = SeasonValues({"fa bos": SeasonLine("Fa Bos", 4, 0.4, 2.0, 0.8)}, 0.5, CFG["games"]["power"])
    fa = Player("Fa Bos", "BOS", ("PG", "SG"))
    read = RosteredRead([RosteredPlayer(fa, 0, {}, 4, "Lamb Chops")], [], {}, [], True)
    # The Playoffs page reads the Val of the player file, the Val of season_vals() (players/page.py write_site()).
    val = season_vals(read, (), season)["fa bos"].val
    playoffs = page.page_data([record("Fa Bos", "BOS", "PG/SG", val, owner="Lamb Chops")], DAYS, CFG, "2026-11-01")
    _, others = trade_players([], read, 1, season, {})
    settings = TradeSettings.from_config(CFG)
    trades = trade_page.builder_data(Suggestions((), [], [], 0, 0, 0), [], others, DAYS, ["PG"], ["wk19"], settings)
    assert others[0].value == playoffs["players"][0]["value"] == val == season.val("fa bos")
    assert playoffs["band"] == trades["engine"]["band"] == list(settings.band) == CFG["trade"]["value_band"]
    low, high = val * playoffs["band"][0], val * playoffs["band"][1]  # the band of a Val above 0
    assert in_band(val, low, settings.band) and in_band(val, high, settings.band)
    assert not in_band(val, low - 0.01, settings.band) and not in_band(val, high + 0.01, settings.band)
