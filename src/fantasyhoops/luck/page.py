"""The Luck page at /luck/ (#254): the luck of each player in each category. It writes output/luck/index.html and the
font in output/luck/fonts/.

The numbers come from players/luck.py: the chances, the makes and the expected makes a game, and the luck z of each
category, then the overall luck. The page shows each player with a ready category (players/luck.py is_ready()).
The owner of a player comes from the shared player file of the run (players.json, players/page.py), by name_key().
A player who is not on a fantasy roster is a free agent.
The filter: All players, My team, Other teams, Free agents. The default sort is the overall luck, the most unlucky
first. A click on the header of Luck or of a z sorts by that column. A second click turns the order.
The sign of each z is in its text, so the page never shows good or bad by color alone.
The planning run (adds/plan.py) calls write_site() after the Players page and publishes the folder at /luck/.
With no data/nba_stats.csv, or a file that the module cannot read, write_site() writes no page. Then the publish
keeps the /luck/ folder of the site.
"""

import html
import json
import math
from pathlib import Path

from fantasyhoops.core import common
from fantasyhoops.core import publish as site
from fantasyhoops.core.common import name_key
from fantasyhoops.players import luck

CURRENT = "luck"  # the page in the site menu and its folder on the site (publish.TOOLS)
GROUPS = {"all": "All players", "mine": "My team", "other": "Other teams", "fa": "Free agents"}
STRONG = 2.0  # a z this far from 0 or more is bold
MINUS = "−"


def folder():
    """The page folder: output/luck, from common.OUT at the time of the call."""
    return common.OUT / CURRENT


def owners(records):
    """{name_key: (owner, group, slug)} of the records of the player file. group: "mine", "other" or "fa"."""
    out = {}
    for r in records:
        group = "mine" if r.get("mine") else "other" if r.get("owner") else "fa"
        out.setdefault(name_key(r["name"]), (r.get("owner"), group, r.get("slug")))
    return out


def _value(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def page_rows(table, records):
    """One dict for each player of table (luck.luck_table()) with a ready category, the most unlucky first.

    Each dict: name, team, gp, owner (the fantasy team name, or None), group, slug (or None), luck, and for each
    category <cat>_chances_pg, <cat>_makes_pg, <cat>_expected_pg and <cat>_z (None when not ready).
    """
    found = owners(records)
    rows = []
    for r in table[table["luck_count"] > 0].to_dict("records"):
        owner, group, slug = found.get(r["name_key"], (None, "fa", None))
        row = {"name": r["name"], "team": r["team"], "gp": int(r["gp"]), "owner": owner, "group": group, "slug": slug}
        row["luck"] = _value(r["luck"])
        for cat in luck.CATEGORIES:
            for part in ("chances_pg", "makes_pg", "expected_pg", "z"):
                row[f"{cat}_{part}"] = _value(r[f"{cat}_{part}"])
        rows.append(row)
    return sorted(rows, key=lambda row: row["luck"])


def stats_date(data_dir=None):
    """The date of the newest dated copy of the NBA.com stats (data/nba_stats/<YYYY-MM-DD>.csv), or None."""
    files = sorted(((data_dir or common.DATA) / "nba_stats").glob("????-??-??.csv"))
    return files[-1].stem if files else None


def z_text(z):
    """The z with its sign, for example "+1.23" or "−0.40". None gives an en dash."""
    if z is None:
        return "–"
    sign = "+" if z > 0 else MINUS if z < 0 else ""
    return f"{sign}{abs(z):.2f}"


def _z_cell(z, cls=""):
    strong = " st" if z is not None and abs(z) >= STRONG else ""
    title = "" if z is not None else ' title="Not ready"'
    sort = "" if z is None else f' data-v="{z:.4f}"'
    return f'<td class="z{cls}{strong}"{sort}{title}>{z_text(z)}</td>'


def _num(v, digits):
    return "–" if v is None else f"{v:.{digits}f}"


def row_html(row):
    """The <tr> of one player."""
    owner = "My team" if row["group"] == "mine" else row["owner"] or "Free agent"
    name = html.escape(row["name"])
    if row["slug"]:
        name = f'<a href="../players/#{html.escape(row["slug"])}">{name}</a>'
    cells = [
        f'<td class="band" style="{site.band_style(row["team"])}">{html.escape(row["team"] or "")}</td>',
        f'<th class="pl" scope="row"><b>{name}</b><small>{html.escape(owner)} · {row["gp"]} GP</small></th>',
        _z_cell(row["luck"], " ov s1"),
    ]
    for cat in luck.CATEGORIES:
        digits = 2 if cat in ("stl", "blk") else 1
        cells.append(f'<td class="s1">{_num(row[f"{cat}_chances_pg"], 1)}</td>')
        cells.append(f"<td>{_num(row[f'{cat}_makes_pg'], digits)}</td>")
        cells.append(f"<td>{_num(row[f'{cat}_expected_pg'], digits)}</td>")
        cells.append(_z_cell(row[f"{cat}_z"]))
    return f'<tr data-own="{row["group"]}">{"".join(cells)}</tr>'


def _sort_head(label, key, sorted_now=False):
    state = ' aria-sort="ascending"' if sorted_now else ""
    return f'<th scope="col" data-key="{key}"{state}><button type="button">{label}</button></th>'


def table_html(rows):
    """The table: a group row with the categories, a head row, then a row for each player."""
    groups = '<th colspan="2"></th><th class="s1"></th>' + "".join(
        f'<th colspan="4" class="s1 grp" scope="colgroup">{luck.LABELS[c]}</th>' for c in luck.CATEGORIES
    )
    heads = ['<th scope="col" class="l">Team</th>', '<th scope="col" class="l">Player</th>']
    heads.append(_sort_head("Luck", "lk", True).replace("<th ", '<th class="s1" ', 1))
    for i, cat in enumerate(luck.CATEGORIES):
        heads += ['<th scope="col" class="s1">Ch/g</th>', '<th scope="col">Act/g</th>', '<th scope="col">Exp/g</th>']
        heads.append(_sort_head("z", str(i)))
    body = "\n".join(row_html(r) for r in rows)
    return (
        f'<table class="lab-t lkt" id="lk"><thead><tr class="grp">{groups}</tr><tr>{"".join(heads)}</tr></thead>'
        f"<tbody>\n{body}\n</tbody></table>"
    )


def chips_html(rows):
    """The filter chips, with the count of players of each group."""
    counts = {g: sum(r["group"] == g for r in rows) for g in GROUPS}
    counts["all"] = len(rows)
    return "".join(
        f'<button type="button" class="chip" data-own="{g}" aria-pressed="{str(g == "all").lower()}">'
        f"{label}<small>{counts[g]}</small></button>"
        for g, label in GROUPS.items()
    )


def note(cfg):
    """The rules line above the table, with the settings of [players.luck]."""
    s = luck.settings(cfg)
    chances = ", ".join(f"{luck.LABELS[c]} {s['min_chances'][c]}" for c in luck.CATEGORIES)
    return (
        "Luck z = (makes − expected makes) / the spread of chance. Expected = chances × his baseline rate: his "
        "2025-26 rate, shrunk toward the league rate and scaled to the league rate of this season. A negative z is "
        "unlucky. Luck = the sum of the ready z / the square root of their count. "
        f"A category is ready with {s['min_games']} games and these chances: {chances}. "
        "A dash: not ready. Bold: 2 or more from 0."
    )


def render(rows, cfg, made, stats_made):
    """The HTML of the Luck page. rows: page_rows(). made: the date of the player file. stats_made: stats_date()."""
    foot = (
        "Data: the NBA.com stats of "
        f"{stats_made or 'an unknown date'} and the owners of the planning run of {made}. Chances: STL deflections, "
        "BLK contested 2-point shots, AST potential assists, REB rebound chances, 3PM 3-point attempts. "
        "Ch/g, Act/g, Exp/g: chances, makes and expected makes a game."
    )
    return (
        site.shell(PAGE_HTML.replace("__STYLE__", STYLE), CURRENT, cfg)
        .replace("__COUNT__", str(len(rows)))
        .replace("__DATE__", html.escape(stats_made or "–"))
        .replace("__NOTE__", html.escape(note(cfg)))
        .replace("__CHIPS__", chips_html(rows))
        .replace("__TABLE__", table_html(rows))
        .replace("__FOOT__", html.escape(foot))
        .replace("__DATA__", f"<script>\n{SCRIPT}\n</script>")
    )


def write_site(player_file, cfg, data_dir=None):
    """Write the Luck page in folder() from the player file of the run. Return the page path, or None.

    player_file: the path of players.json (players/page.py write_site()). data_dir: the folder of nba_stats.csv
    (default data/). None: no data/nba_stats.csv, so no page. The return value is the more_tools entry of
    publish.publish().
    A file that the module cannot read prints a warning and gives None, so the planning run continues.
    """
    try:
        table = luck.read_luck(cfg, data_dir)
    except Exception as error:  # noqa: BLE001 - an optional page: a bad stats file keeps the old page
        print(f"Warning: the run could not make the Luck page ({type(error).__name__}: {error}). The publish keeps it.")
        return None
    if table is None:
        print("No data/nba_stats.csv: the run wrote no Luck page. The publish keeps the old Luck page.")
        return None
    content = json.loads(Path(player_file).read_text(encoding="utf-8"))
    rows = page_rows(table, content["players"])
    text = render(rows, cfg, content["meta"]["made"], stats_date(data_dir))
    return site.write_page(folder() / "index.html", text)


STYLE = """/* The Luck page (#254): the head of the Roster page, the filter chips and the luck table. */
.lk { color: var(--lab-ink); font: 400 13px/1.25 var(--lab-face); font-variant-numeric: tabular-nums;
  padding-block: 16px 32px; padding-left: max(28px, env(safe-area-inset-left));
  padding-right: max(28px, env(safe-area-inset-right)); }
.lk .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 28px; padding-bottom: 12px;
  border-bottom: 3px solid var(--mark); }
.lk .head h1 { margin: 0; color: var(--mark); font-weight: 900; font-stretch: 66%; font-size: clamp(32px, 4vw, 44px);
  line-height: .9; text-transform: uppercase; }
.lk .meta { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 0; margin: 0; font-size: 13px; }
.lk .meta div { padding: 0 16px; border-left: 1px solid var(--lab-rule); }
.lk .meta dt { color: var(--lab-mute); font-size: 12px; margin-bottom: 3px; }
.lk .meta dd { margin: 0; }
.lk .meta strong { font-weight: 800; font-size: 15px; }
.lk .foot { max-width: 84ch; margin: 10px 0 0; font-size: 12px; line-height: 1.45; color: var(--lab-mute); }
.lk .scroll { position: relative; scrollbar-color: var(--mark) var(--zebra); }
.lk .scroll:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }
.lk .q { margin: 10px 0 0; font-size: 13px; color: var(--lab-mute); max-width: 84ch; line-height: 1.45; }
.lk .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 0; }
.lk button.chip { font: inherit; font-size: 13px; font-weight: 700; padding: 4px 9px; min-height: 32px;
  border: 1.5px solid var(--lamp-off); border-radius: 0; background: var(--lab-stock); color: var(--lab-ink);
  cursor: pointer; text-align: left; }
.lk button.chip small { display: block; color: var(--lab-mute); font-size: 11px; font-weight: 400; }
.lk button.chip:hover { border-color: var(--lab-ink); }
.lk button.chip[aria-pressed="true"] { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
.lk button.chip[aria-pressed="true"] small { color: var(--lab-stock); }
.lk button.chip:focus-visible, .lkt thead button:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.lk .scroll.lks { display: block; overflow-x: auto; margin-top: 12px; }
table.lkt { min-width: 1240px; }
.lkt thead th { white-space: nowrap; }
.lkt thead tr.grp th { border-bottom: 0; padding-bottom: 2px; font-size: 12px; color: var(--lab-ink); }
.lkt thead tr.grp th.grp { text-align: center; }
.lkt thead th button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
.lkt thead th button:hover { text-decoration: underline; }
.lkt thead th[aria-sort] { box-shadow: inset 0 -3px 0 var(--mark); }
.lkt thead th[aria-sort="ascending"] button::after { content: " ▲"; font-size: 9px; }
.lkt thead th[aria-sort="descending"] button::after { content: " ▼"; font-size: 9px; }
.lkt td.band { width: 44px; }
.lkt th.pl { min-width: 190px; }
.lkt th.pl a { color: inherit; text-decoration: none; }
.lkt th.pl a:hover { text-decoration: underline; }
.lkt td.z { font-weight: 400; }
.lkt td.z.st { font-weight: 800; }
.lkt td.ov { font-weight: 900; font-stretch: 75%; font-size: 19px; }
.lkt td[title] { color: var(--lab-mute); }
.lk .empty { margin: 12px 0 0; color: var(--lab-mute); }
@media (max-width: 899px) {
  .lk { padding-block: 16px 24px; padding-left: max(16px, env(safe-area-inset-left));
    padding-right: max(16px, env(safe-area-inset-right)); }
  .lk .meta div:first-child { padding-left: 0; border-left: 0; }
  .lkt td.ov { font-size: 17px; }
}"""

# The filter and the sort. A sort or a filter puts the shown rows first, so the zebra rows stay in order.
SCRIPT = r"""(() => {
  const table = document.getElementById("lk"), body = table.tBodies[0];
  const rows = [...body.rows], chips = [...document.querySelectorAll(".lk button.chip")];
  const heads = [...table.querySelectorAll("thead th[data-key]")], empty = document.getElementById("lk-empty");
  let group = "all", key = "lk", dir = 1;
  const cell = (tr, k) => {
    const td = k === "lk" ? tr.querySelector("td.ov") : tr.querySelectorAll("td.z:not(.ov)")[Number(k)];
    return td && td.dataset.v !== undefined ? Number(td.dataset.v) : null;
  };
  const draw = () => {
    const order = rows.slice().sort((a, b) => {
      const x = cell(a, key), y = cell(b, key);
      if (x === null || y === null) return (x === null) - (y === null);
      return dir * (x - y);
    });
    const shown = order.filter(tr => group === "all" || tr.dataset.own === group);
    order.forEach(tr => { tr.hidden = !shown.includes(tr); });
    shown.concat(order.filter(tr => tr.hidden)).forEach(tr => body.appendChild(tr));
    empty.hidden = shown.length > 0;
    heads.forEach(th => {
      if (th.dataset.key === key) th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });
  };
  chips.forEach(b => b.addEventListener("click", () => {
    group = b.dataset.own;
    chips.forEach(c => c.setAttribute("aria-pressed", c === b));
    draw();
  }));
  heads.forEach(th => th.querySelector("button").addEventListener("click", () => {
    if (key === th.dataset.key) dir = -dir; else { key = th.dataset.key; dir = 1; }
    draw();
  }));
})();"""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Luck · Fantasy Hoops Lab</title>
__HEAD__
<style>
__TABLE_CSS__
__STYLE__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main lk">
<header class="head">
<h1>Luck</h1>
<dl class="meta">
<div><dt>NBA.com stats</dt><dd><strong>__DATE__</strong></dd></div>
<div><dt>Players</dt><dd><strong>__COUNT__</strong></dd></div>
</dl>
</header>
<p class="q">__NOTE__</p>
<div class="chips" role="group" aria-label="Players">__CHIPS__</div>
<div class="scroll lks" tabindex="0" role="region" aria-label="Luck table">__TABLE__</div>
<p class="empty" id="lk-empty" hidden>No player of this group has a ready category.</p>
<p class="foot">__FOOT__</p>
</main>
__SCRIPT__
__DATA__
</body>
</html>
"""
