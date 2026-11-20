"""The Luck page (#254): the rows, the owners, the filter, the sort and the page HTML.

1. page_rows() keeps the players with a ready category, sorted with the most unlucky first.
2. The owner of each player comes from the player file. A player who is not in it is a free agent.
3. The page has the site menu item, the 4 filter chips with their counts and no placeholder.
4. Each z shows its sign in the text.
5. In Chromium, a chip filters the rows and a header click sorts them.
"""

import copy
import json
import math
import re

import pandas as pd
import pytest

from fantasyhoops.core import common
from fantasyhoops.core import publish as site
from fantasyhoops.luck import page
from fantasyhoops.players import luck
from tests.core.test_roster import browser_page

CFG = copy.deepcopy(common.load_config())


def stats(rows):
    """A frame in the shape of data/nba_stats.csv. rows: (name, team, gp, {cat: (makes, chances)})."""
    out = []
    for i, (name, team, gp, cats) in enumerate(rows):
        rec = {"nba_id": i + 1, "name": name, "name_key": common.name_key(name), "team": team, "gp": gp}
        for cat in luck.CATEGORIES:
            rec[f"{cat}_makes"], rec[f"{cat}_chances"] = cats.get(cat, (math.nan, math.nan))
        out.append(rec)
    return pd.DataFrame(out)


# Al Mine is unlucky in REB, Bo Other is lucky, Cy Free is not in the player file, Di Few has 3 games (not ready).
CURRENT = stats(
    [
        ("Al Mine", "DAL", 10, {"reb": (40, 100), "blk": (10, 50)}),
        ("Bo Other", "BOS", 10, {"reb": (70, 100)}),
        ("Cy Free", "NO", 10, {"reb": (55, 100)}),
        ("Di Few", "ORL", 3, {"reb": (90, 100)}),
    ]
)
RECORDS = [
    {"slug": "al-mine", "name": "Al Mine", "owner": "TradeMark", "mine": True},
    {"slug": "bo-other", "name": "Bo Other", "owner": "Lamb Chops", "mine": False},
    {"slug": "di-few", "name": "Di Few", "owner": None, "mine": False},
]


def rows():
    return page.page_rows(luck.luck_table(CURRENT, None, CFG), RECORDS)


def html_page():
    return page.render(rows(), CFG, "2026-11-20", "2026-11-20")


def test_the_rows_have_the_ready_players_with_the_most_unlucky_first():
    got = rows()
    assert [r["name"] for r in got] == ["Al Mine", "Cy Free", "Bo Other"]
    assert [r["luck"] for r in got] == sorted(r["luck"] for r in got)
    assert got[0]["luck"] < 0 < got[-1]["luck"]


def test_the_owner_comes_from_the_player_file():
    got = {r["name"]: r for r in rows()}
    assert (got["Al Mine"]["group"], got["Al Mine"]["slug"]) == ("mine", "al-mine")
    assert (got["Bo Other"]["group"], got["Bo Other"]["owner"]) == ("other", "Lamb Chops")
    assert (got["Cy Free"]["group"], got["Cy Free"]["slug"]) == ("fa", None)
    assert page.owners([{"name": "Dö Free", "owner": None, "slug": "x"}]) == {"do free": (None, "fa", "x")}


def test_a_z_shows_its_sign_in_the_text():
    assert page.z_text(1.234) == "+1.23"
    assert page.z_text(-0.4) == "−0.40"
    assert page.z_text(0.0) == "0.00"
    assert page.z_text(None) == "–"


def test_the_page_has_the_menu_item_the_chips_and_no_placeholder():
    text = html_page()
    assert site.TOOLS["luck"][0] == "Luck"
    assert '<li><a href="../luck/" aria-current="page">Luck</a></li>' in text
    assert "<title>Luck · Fantasy Hoops Lab</title>" in text
    chips = re.findall(r'data-own="(\w+)" aria-pressed="(\w+)">([^<]+)<small>(\d+)</small>', text)
    assert chips == [
        ("all", "true", "All players", "3"),
        ("mine", "false", "My team", "1"),
        ("other", "false", "Other teams", "1"),
        ("fa", "false", "Free agents", "1"),
    ]
    assert not re.findall(r"__[A-Z0-9_]+__", text)


def test_the_table_is_sorted_by_luck_and_has_4_columns_for_each_category():
    text = html_page()
    assert text.index("Al Mine") < text.index("Cy Free") < text.index("Bo Other")
    assert '<th class="s1" scope="col" data-key="lk" aria-sort="ascending"><button type="button">Luck</button>' in text
    assert text.count('<button type="button">z</button>') == len(luck.CATEGORIES)
    for label in ("STL", "BLK", "AST", "REB", "3PM"):
        assert f'scope="colgroup">{label}</th>' in text
    row = re.search(r'<tr data-own="mine">.*?</tr>', text).group(0)
    assert '<a href="../players/#al-mine">Al Mine</a>' in row and "My team · 10 GP" in row
    assert row.count("<td") == 2 + 4 * len(luck.CATEGORIES)  # the band, the luck, then 4 for each category
    assert 'title="Not ready">–</td>' in row  # STL has no chances
    free = re.search(r'<tr data-own="fa">.*?</tr>', text).group(0)
    assert "Free agent · 10 GP" in free and "<a " not in free


def test_the_rules_line_names_the_settings():
    text = html_page()
    s = luck.settings(CFG)
    assert f"A category is ready with {s['min_games']} games" in text and f"REB {s['min_chances']['reb']}" in text


def test_write_site_reads_the_stats_and_the_player_file(tmp_path):
    data = tmp_path / "data"
    (data / "nba_stats").mkdir(parents=True)
    CURRENT.to_csv(data / "nba_stats.csv", index=False)
    (data / "nba_stats" / "2026-11-20.csv").write_text("", encoding="utf-8")
    file = tmp_path / "players.json"
    file.write_text(json.dumps({"meta": {"made": "2026-11-20"}, "players": RECORDS}), encoding="utf-8")
    path = page.write_site(file, CFG, data)
    assert path == common.OUT / "luck" / "index.html" and (path.parent / "fonts").exists()
    text = path.read_text(encoding="utf-8")
    assert "<dt>NBA.com stats</dt><dd><strong>2026-11-20</strong></dd>" in text and "Al Mine" in text


def test_write_site_with_no_stats_writes_no_page(tmp_path, capsys):
    assert page.write_site(tmp_path / "players.json", CFG, tmp_path) is None
    assert "No data/nba_stats.csv" in capsys.readouterr().out
    assert not (common.OUT / "luck").exists()


def test_write_site_with_a_bad_stats_file_writes_no_page(tmp_path, capsys):
    (tmp_path / "nba_stats.csv").write_text("nba_id,name\n1,X\n", encoding="utf-8")
    assert page.write_site(tmp_path / "players.json", CFG, tmp_path) is None
    assert "Warning: the run could not make the Luck page (KeyError" in capsys.readouterr().out


def test_a_chip_filters_the_rows_and_a_header_sorts_them(tmp_path):
    path = tmp_path / "luck.html"
    path.write_text(html_page(), encoding="utf-8")
    with browser_page(1280) as pg:
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(path.as_uri())

        def shown():
            return pg.eval_on_selector_all("#lk tbody tr:not([hidden]) th.pl b", "els => els.map(e => e.textContent)")

        assert shown() == ["Al Mine", "Cy Free", "Bo Other"]
        pg.click('button.chip[data-own="fa"]')
        assert shown() == ["Cy Free"]
        assert pg.get_attribute('button.chip[data-own="fa"]', "aria-pressed") == "true"
        pg.click('button.chip[data-own="all"]')
        pg.click('th[data-key="lk"] button')  # a second click: the most lucky first
        assert shown() == ["Bo Other", "Cy Free", "Al Mine"]
        assert pg.get_attribute('th[data-key="lk"]', "aria-sort") == "descending"
        pg.click('th[data-key="1"] button')  # BLK z: only Al Mine has one, the rows with no z go last
        assert shown()[0] == "Al Mine"
        assert errors == []


@pytest.mark.parametrize("width", [390])
def test_the_page_has_no_page_scroll_on_a_phone(tmp_path, width):
    path = tmp_path / "luck.html"
    path.write_text(html_page(), encoding="utf-8")
    with browser_page(width) as pg:
        pg.goto(path.as_uri())
        assert pg.evaluate("document.documentElement.scrollWidth") <= width
