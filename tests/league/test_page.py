"""The League page (#218): the page data, the page HTML and the page script.

1. page_data() gives v (the mean Val of the best free agents), the records of the standings and the settings.
2. The page HTML has the site menu item, both scripts and no placeholder.
3. In Node, each value of a row comes from valueStarted(), bestCore() and streamFill() of core/starts.js. Your row uses
   the core that you saved on the Playoffs page. The header gives the ranks and the medians of rankMedian().
4. In Chromium, the page draws the table with no error, a header click sorts and a team click opens its core.
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
from fantasyhoops.league import page
from tests.core.test_roster import browser_page

CFG = copy.deepcopy(common.load_config())
CFG["playoffs"]["core"] = 2
CFG["league"]["roster_spots"] = 3
CFG["league"]["adds"] = 1
CFG["quality_games"]["bonus"] = 0.1
CFG["league_page"]["v_free_agents"] = 2

# Two weeks of two days. 3/9 and 3/16 are light nights.
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
    record("Fa Bos", "BOS", "PG/SG", 6.0, owner="Lamb Chops"),
    record("Gi Dal", "DAL", "C", 3.0, owner="Lamb Chops"),
    record("Ho No", "NO", "PF", None, 2.0, owner="Lamb Chops"),
    record("Gus Free", "NO", "SG", 1.5),
    record("Hé Accent", "BOS", "C", 2.5),
    record("Iz Free", "ORL", "PF", 0.5),
]
STANDINGS = {"Me": "3-1-0", "lamb chops ": "1-3-0", "Not A Team": "2-2-0"}


def data(records=RECORDS, standings=STANDINGS):
    return page.page_data(records, DAYS, CFG, "2026-11-01", standings)


def test_v_is_the_mean_val_of_the_best_free_agents():
    """Owner decision 3 of 2026-11-02: v = the mean Val of the top [league_page] v_free_agents free agents."""
    d = data()
    assert d["v"] == pytest.approx((2.5 + 1.5) / 2) and d["v_count"] == 2
    assert d["v_players"] == [{"name": "Hé Accent", "value": 2.5}, {"name": "Gus Free", "value": 1.5}]
    assert page.stream_value([], 10) == (0.0, [])


def test_the_page_data_has_the_records_of_the_standings_and_the_settings():
    d = data()
    # The second check of team_records() ignores the case and the outer spaces. A team of no player gets no row.
    assert d["records"] == {"Lamb Chops": "1-3-0", "Me": "3-1-0"}
    assert data(standings=None)["records"] == {"Lamb Chops": None, "Me": None}
    assert (d["core"], d["roster_spots"], d["adds"], d["key"]) == (2, 3, 1, "fhl-playoffs")
    assert d["weeks"] == ["wk19", "wk20"] and len(d["days"]) == 4 and len(d["players"]) == len(RECORDS)


def test_the_page_has_the_menu_item_the_scripts_and_no_placeholder():
    html = page.render(data(), CFG)
    assert site.TOOLS["league"][0] == "League"
    assert '<li><a href="../league/" aria-current="page">League</a></li>' in html
    assert "<title>League · Fantasy Hoops Lab</title>" in html and site.page_meta(
        "league", "League · Fantasy Hoops Lab"
    )
    assert "<strong>Wk19–20</strong> · Mar 8–16" in html and "<dt>Teams</dt><dd><strong>2</strong></dd>" in html
    assert "Data: the planning run of Sun 11/1" in html and "v = 2.00, the mean Val of the top 2 free agents" in html
    assert ENGINE_JS.read_text(encoding="utf-8") in html and page.SCRIPT.read_text(encoding="utf-8") in html
    assert 'id="lg"' in html and 'id="sum"' in html and 'id="ranks"' in html and 'id="fa-list"' in html
    assert not re.findall(r"__[A-Z0-9_]+__", html)


def test_write_site_reads_the_player_file_and_writes_the_page(tmp_path):
    file = tmp_path / "players.json"
    file.write_text(json.dumps({"meta": {"made": "2026-11-01"}, "players": RECORDS}), encoding="utf-8")
    path = page.write_site(file, DAYS, CFG, {"Me": "3-1-0"})
    assert path == common.OUT / "league" / "index.html" and (path.parent / "fonts").exists()
    assert '"records":{"Lamb Chops":null,"Me":"3-1-0"}' in path.read_text(encoding="utf-8")


def test_a_failed_standings_read_gives_a_league_page_with_no_records(capsys):
    """#218: the records are optional. A failed read prints a warning, and a Yahoo block stops the run (#107)."""
    from fantasyhoops.adds.session import YahooBlocked

    class Failing:
        def __init__(self, error):
            self.error = error

        def get(self, path):
            raise self.error

    assert page.read_records(Failing(ConnectionError("The network is down."))) == {}
    assert (
        "Warning: the run could not read the standings for the League page (ConnectionError" in capsys.readouterr().out
    )
    with pytest.raises(YahooBlocked):
        page.read_records(Failing(YahooBlocked("blocked")))


# The page script in Node. argv: the page script and core/starts.js. stdin: {data, saved}. Writes the rows of
# League.rows(), the view and, for each row, valueStarted() and streamFill() of its core from core/starts.js.
DRIVER = """
const L = require(process.argv[1]), S = require(process.argv[2]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { data, saved } = JSON.parse(text);
  const rows = L.rows(data, saved), eng = L.engine(data);
  const check = rows.map(r => {
    const resters = r.source === "saved" ? r.players.filter(p => saved.rest && p.id in saved.rest ? saved.rest[p.id]
      : p.rests_b2b).map(p => p.id) : undefined;
    return { vs: S.valueStarted(r.players, eng, resters).total,
      fill: S.streamFill(r.players, eng, { spots: data.roster_spots - r.players.length, adds: data.adds, resters }) };
  });
  const view = L.view(data, rows, { key: "total", dir: -1, open: "Me" });
  const sorts = Object.fromEntries(["record", "unused", "rate", "team"].map(k =>
    [k, L.sorted(rows, { key: k, dir: k === "unused" || k === "team" ? 1 : -1 }).map(r => r.team)]));
  process.stdout.write(JSON.stringify({ rows, check, view, sorts }));
});
"""

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")


def run(given=None, saved=None):
    out = subprocess.run(
        ["node", "-e", DRIVER, str(page.SCRIPT), str(ENGINE_JS)],
        input=json.dumps({"data": given or data(), "saved": saved}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


@needs_node
def test_each_value_of_a_row_comes_from_value_started_and_stream_fill():
    """#218 acceptance: a test checks one team's row against valueStarted()."""
    out = run()
    rows = {r["team"]: r for r in out["rows"]}
    lamb, check = rows["Lamb Chops"], out["check"][[r["team"] for r in out["rows"]].index("Lamb Chops")]
    # The best 2 by value started alone: Fa Bos 6 + 6 + 6 x 1.1 = 18.6, Gi Dal 3 + 3 x 1.1 + 3 = 9.3. Ho No: 6.2.
    assert [p["id"] for p in lamb["players"]] == ["fa-bos", "gi-dal"] and lamb["source"] == "best"
    assert lamb["value"] == pytest.approx(check["vs"]["value"]) == pytest.approx(18.6 + 9.3)
    assert (
        (lamb["starts"], lamb["games_core"], lamb["lost"])
        == (6, 6, 0)
        == (
            check["vs"]["starts"],
            check["vs"]["games"],
            check["vs"]["lost"],
        )
    )
    assert lamb["perCore"] == pytest.approx(lamb["value"] / 2) and lamb["spots"] == 1
    fill = check["fill"]
    assert (lamb["heavy"], lamb["light"], lamb["open_heavy"], lamb["open_light"]) == (
        fill["heavy"],
        fill["light"],
        check["vs"]["open_heavy"],
        check["vs"]["open_light"],
    )
    assert (lamb["games"], lamb["rate"], lamb["unused"]) == (fill["games"], fill["rate"], fill["unused"])
    v = data()["v"]
    assert lamb["stream"] == pytest.approx(fill["games"] * v)
    assert lamb["total"] == pytest.approx(lamb["value"] + lamb["stream"])
    assert lamb["record"] == "1-3-0" and lamb["out"][0]["id"] == "ho-no"


@needs_node
def test_your_row_uses_the_core_saved_on_the_playoffs_page():
    """Owner decision 1 of 2026-11-02: your row uses the saved core and its R switches, else your best core."""
    mine = next(r for r in run()["rows"] if r["mine"])
    assert [p["id"] for p in mine["players"]] == ["al-dal", "cy-orl"] and mine["source"] == "best"
    # A saved core of 3 with a free agent, and Bo No with no rest: 0 stream spots.
    saved = {"core": ["bo-no", "gus-free", "al-dal", "gone"], "rest": {"bo-no": False}}
    out = run(saved=saved)
    i = next(n for n, r in enumerate(out["rows"]) if r["mine"])
    mine, check = out["rows"][i], out["check"][i]
    assert mine["source"] == "saved" and sorted(p["id"] for p in mine["players"]) == ["al-dal", "bo-no", "gus-free"]
    assert mine["value"] == pytest.approx(check["vs"]["value"])
    # With no rest, Bo No starts on each NO day: 3/8, 3/9 and 3/15.
    assert [p["starts"] for p in mine["players"] if p["id"] == "bo-no"] == [3]
    assert (mine["spots"], mine["heavy"], mine["light"], mine["games"]) == (0, 0, 0, 0)
    assert "your saved Playoffs core" in out["view"]["table"]


@needs_node
def test_the_header_gives_your_ranks_and_the_league_medians():
    """Owner decision of 2026-11-02 on #218: core starts and filled heavy, rank 1 is the most."""
    out = run()
    rows = {r["team"]: r for r in out["rows"]}
    me, lamb = rows["Me"], rows["Lamb Chops"]
    rank = 1 + (lamb["starts"] > me["starts"])
    med = (me["starts"] + lamb["starts"]) / 2
    med_text = str(int(med)) if med == int(med) else f"{med:.1f}"
    assert f"<li><b>Core starts:</b> rank {rank} of 2 (league median {med_text})</li>" in out["view"]["header"]
    assert "<li><b>Filled heavy:</b> rank " in out["view"]["header"]


@needs_node
def test_the_table_has_the_columns_and_each_column_sorts():
    out = run()
    table = out["view"]["table"]
    labels = re.findall(r'<button type="button" data-k="[^"]+">([^<]+)<i', table)
    assert labels == [
        "Team",
        "Record",
        "Core",
        "Val / core",
        "Stream value",
        "Total",
        "Starts",
        "Open heavy",
        "Open light",
        "Stream games",
        "Fill rate",
        "Unused",
    ]
    assert '<tr class="mine on" data-t="Me"' in table and '<em class="tag you">You</em>' in table
    assert '<tr class="det">' in table  # the open team shows its core
    # Record sorts by the win share: Me (3-1-0) first.
    assert out["sorts"]["record"] == ["Me", "Lamb Chops"] and out["sorts"]["team"] == ["Lamb Chops", "Me"]
    rows = {r["team"]: r for r in out["rows"]}
    assert out["sorts"]["unused"] == sorted(rows, key=lambda t: (rows[t]["unused"], -rows[t]["total"]))
    assert re.search(r'<td class="rate">\d+%</td>', table)


def test_the_page_in_chromium_draws_sorts_and_opens_a_team(tmp_path):
    path = common.OUT / "league" / "index.html"
    site.write_page(path, page.render(data(), CFG))
    with browser_page(390) as pg:
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(path.as_uri())
        assert pg.locator("#lg tbody tr[data-t]").count() == 2
        assert pg.locator("#ranks li").count() == 2 and pg.locator("#fa-list").inner_text().startswith("Hé Accent")
        pg.locator('#lg button[data-k="team"]').click()
        assert pg.locator("#lg tbody tr[data-t]").first.get_attribute("data-t") == "Lamb Chops"
        pg.locator('#lg tr[data-t="Me"] th').click()
        assert pg.locator("#lg tr.det").count() == 1 and not errors
