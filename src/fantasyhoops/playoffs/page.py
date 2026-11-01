"""The Playoffs page at /playoffs/ (#214): model the playoff core of your team. It writes output/playoffs/index.html
and the font in output/playoffs/fonts/.

The design is in docs/wiki/playoffs-page-design-2026-11-01.md (decisions 1 to 15). The page opens on the best core of
your roster, the [playoffs] core players with the highest value started (config.toml). A search adds any player of
the pool, the players of the shared player file (players.json, players/page.py). An R switch marks a player as a
rester. Save keeps the core and the R switches in the browser (localStorage). Reset goes back to the best core.
The page data (page_data()) holds the playoff days and a short record of each pool player. playoffs.js draws the
page in the browser. valueStarted() of core/starts.js (#213) gives each number. The page inlines both scripts.
The value of a player is his Val, else his proj_val with the "proj" mark (decision 14), else 0 with no Val ("–").
So no null value goes to valueStarted().
The planning run (adds/plan.py) calls write_site() after the Players page and publishes the folder at /playoffs/.
The trade run does not write the page. Its publish keeps /playoffs/.
"""

import html
import json
from datetime import date
from pathlib import Path

from fantasyhoops.core import common
from fantasyhoops.core import publish as site
from fantasyhoops.core.lineup import ENGINE_JS, UTIL
from fantasyhoops.core.roster import PAGE_STYLE as ROSTER_STYLE

CURRENT = "playoffs"  # the page in the site menu and its folder on the site (publish.TOOLS)
SCRIPT = Path(__file__).parent / "playoffs.js"
STORE_KEY = "fhl-playoffs"  # the localStorage key of the saved core
PROJ, NO_VAL = "proj", "none"  # the marks of a value from the projection and of a player with no value


def folder():
    """The page folder: output/playoffs, from common.OUT at the time of the call."""
    return common.OUT / CURRENT


def player_value(record):
    """(value, mark) of a record of the player file: the Val, else the proj_val with PROJ, else 0 with NO_VAL."""
    if record.get("val") is not None:
        return record["val"], ""
    if record.get("proj_val") is not None:
        return record["proj_val"], PROJ
    return 0.0, NO_VAL


def pool(records):
    """The pool players of the page: a short record of each player of the player file, in the order of the file.

    A record has id (the slug), name, team, pos (a list of positions), owner, mine, value, mark and rests_b2b.
    """
    out = []
    for r in records:
        value, mark = player_value(r)
        out.append(
            {
                "id": r["slug"],
                "name": r["name"],
                "team": r["team"],
                "pos": [p for p in (r.get("pos") or "").split("/") if p],
                "owner": r.get("owner"),
                "mine": bool(r.get("mine")),
                "value": round(value, 3),
                "mark": mark,
                "rests_b2b": int(r.get("rests_b2b") or 0),
            }
        )
    return out


def span(days):
    """The dates of the playoff days, for example "Mar 8–28" or "Mar 29–Apr 4"."""
    first, last = days[0].date, days[-1].date
    if first.month == last.month:
        return f"{first:%b} {first.day}–{last.day}"
    return f"{first:%b} {first.day}–{last:%b} {last.day}"


def page_data(records, days, cfg, made):
    """The data of the page as a dict. records: the players of the player file. days: roster.playoff_days().

    made: the date of the player file, for example "2026-10-31".
    """
    players = pool(records)
    teams = sorted({p["team"] for p in players} | {""})
    return {
        "made": made,
        "key": STORE_KEY,
        "core": cfg["playoffs"]["core"],
        "slots": list(cfg["league"]["slots"]),
        "util": UTIL,
        "quality_bonus": cfg["quality_games"]["bonus"],
        "weeks": list(dict.fromkeys(d.week for d in days)),
        "span": span(days),
        "days": [
            {
                "date": f"{d.date:%Y-%m-%d}",
                "week": d.week,
                "quality": bool(d.quality),
                "games": len(d.teams) // 2,
                "teams": sorted(d.teams),
                "b2b": sorted(d.b2b),
            }
            for d in days
        ],
        "players": players,
        "bands": {t: site.band_style(t or None) for t in teams},
    }


def _made_text(made):
    """The date of the data for the page foot, for example "Sat 10/31"."""
    d = date.fromisoformat(made)
    return f"{d:%a} {d.month}/{d.day}"


def render(data, cfg):
    """The HTML of the Playoffs page. data: page_data(). cfg: the config ([league] teams for the menu)."""
    weeks = data["weeks"]
    digits = "".join(c for c in weeks[-1] if c.isdigit())
    first = weeks[0][:1].upper() + weeks[0][1:]
    n_days = len(data["days"])
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    script = (
        f'<script type="application/json" id="po-data">{text}</script>\n'
        f"<script>\n{ENGINE_JS.read_text(encoding='utf-8')}\n{SCRIPT.read_text(encoding='utf-8')}\n"
        'Playoffs.start(document, JSON.parse(document.getElementById("po-data").textContent));\n</script>'
    )
    slots = len(cfg["league"]["slots"]) + UTIL
    foot = FOOT.replace("__MADE__", _made_text(data["made"])).replace("__SLOTS__", str(slots))
    foot = foot.replace("__BONUS__", f"{round(data['quality_bonus'] * 100)}%")
    style = (ROSTER_STYLE + "\n" + STYLE).replace("__DAYS1__", str(n_days + 1)).replace("__DAYS__", str(n_days))
    return (
        site.shell(PAGE_HTML.replace("__STYLE__", style), CURRENT, cfg)
        .replace("__WEEKS__", f"{first}–{digits}")
        .replace("__SPAN__", html.escape(data["span"]))
        .replace("__N__", str(data["core"]))
        .replace("__DAYS__", str(n_days))
        .replace("__FOOT__", foot)
        .replace("__DATA__", script)
    )


def write_site(player_file, days, cfg):
    """Write the Playoffs page in folder() from the player file of the run. Return the page path.

    player_file: the path of players.json (players/page.py write_site()). days: roster.playoff_days().
    The return value is the more_tools entry of publish.publish().
    """
    content = json.loads(Path(player_file).read_text(encoding="utf-8"))
    data = page_data(content["players"], days, cfg, content["meta"]["made"])
    return site.write_page(folder() / "index.html", render(data, cfg))


FOOT = (
    "Data: the planning run of __MADE__ and the NBA schedule. Val: the per-game Val of the Free agents page. "
    "A player with no Val gets a Val from his projection, with the proj tag. Each day, the core players start in "
    "Val order, highest first, in __SLOTS__ slots. Value started: the sum of the Val of each started game, with "
    "__BONUS__ more on a light night (6 or fewer NBA games). Starts lost: core games that sit because the lineup is "
    "full. Open slots: the empty slots that a stream player can fill. A player with the R tag rests on the second "
    "night of each back-to-back. The R switch does not change the rest list. Save keeps the core in this browser."
)

STYLE = """/* The Playoffs page (#214): the controls, the headline, the week totals, the core grid and the Players table. */
.po .meta .ctl { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 8px; }
.ctl label { display: block; color: var(--lab-mute); font-size: 12px; margin-bottom: 3px; }
.ctl input[type=number] { width: 52px; font: 800 15px/1 var(--lab-face); font-variant-numeric: tabular-nums;
  border: 1.5px solid var(--lamp-off); border-radius: 0; padding: 5px 4px; background: var(--lab-stock); color: var(--lab-ink); }
.btn { font: 800 12px/1 var(--lab-face); border: 1.5px solid var(--lamp-off); border-radius: 0; background: var(--lab-stock);
  color: var(--lab-ink); padding: 7px 10px; cursor: pointer; min-height: 32px; }
.btn:hover { background: var(--zebra); }
.btn.pri { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
.btn:focus-visible, .ctl input:focus-visible, .rb:focus-visible, .x:focus-visible, .srch input:focus-visible,
.res button:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.saved { font-size: 12px; color: var(--lab-mute); align-self: center; }
.stats { display: flex; flex-wrap: wrap; margin: 16px 0 0; row-gap: 10px; }
.stats > div { padding: 0 18px; border-left: 1px solid var(--vrule); }
.stats > div:first-child { padding-left: 0; border-left: 0; }
.stats dt { font-size: 12px; color: var(--lab-mute); margin-bottom: 2px; }
.stats dd { margin: 0; font-weight: 900; font-stretch: 75%; font-size: 24px; line-height: 1.05; }
.stats dd small { font-size: 12px; font-weight: 600; font-stretch: 100%; color: var(--lab-mute); margin-left: 3px; }
.stats .hero dd { font-size: 34px; }
table.wk { border-collapse: collapse; margin-top: 12px; font-size: 13px; font-variant-numeric: tabular-nums; }
table.wk th, table.wk td { padding: 4px 10px; text-align: right; border-bottom: 1px solid var(--lab-rule); }
table.wk thead th { font-size: 11px; font-weight: 800; color: var(--mark); border-bottom: 2px solid var(--mark); }
table.wk th.l { text-align: left; padding-left: 0; }
table.wk tr.t > * { font-weight: 800; border-bottom: 2px solid var(--mark); }
.lay { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px 24px; margin-top: 18px; align-items: start; }
@media (min-width: 1380px) { .lay { grid-template-columns: minmax(0, 1fr) 380px; } }
.po h2 { margin: 0 0 6px; padding-bottom: 4px; border-bottom: 2px solid var(--mark); font-weight: 900; font-stretch: 75%;
  font-size: 19px; line-height: 1.1; text-transform: uppercase; color: var(--lab-ink); }
.po .scroll { margin-top: 0; }
table.desk.pg { min-width: 724px; }
.pg col.c-pl { width: 168px; }
.pg col.c-d { width: 16px; }
.pg .pl small { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pg tfoot td.d { font-size: 12px; font-weight: 800; color: var(--mark); }
.pg tfoot tr.og td.d { font-weight: 400; color: var(--lab-ink); }
.pg tfoot tr > th.lab { text-align: left; padding-left: 10px; font-size: 12px; font-weight: 800; color: var(--mark); }
.pg tfoot tr > * { height: 30px; border-bottom: 1px solid var(--lab-rule); }
.pg tfoot tr.st > * { border-top: 2px solid var(--mark); }
.pg tfoot tr.st td.d { line-height: 1; }
.pg tfoot tr.st td.d small { display: block; font-size: 9px; font-weight: 600; color: var(--lab-mute); }
.pg tfoot tr.og > * { border-bottom: 2px solid var(--mark); }
.pg tfoot td.w { font-size: 13px; font-weight: 800; color: var(--mark); text-align: right; padding-right: 6px; }
.pg tfoot td.w small { display: block; font-size: 10px; font-weight: 600; color: var(--lab-mute); }
.pg tfoot .d.q { background: var(--qcol) !important; }
.pg td.empty { color: var(--lab-mute); text-align: left !important; padding-left: 10px !important; height: 46px; }
.tag { font-style: normal; font-size: 10px; font-weight: 800; border: 1.5px solid var(--lab-ink); padding: 0 3px;
  margin-left: 4px; vertical-align: 2px; color: var(--lab-ink); letter-spacing: 0; text-transform: none; font-stretch: 100%; }
.legend .tag { margin: 0 5px 0 0; vertical-align: 0; }
/* The Players table */
table.pt { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; table-layout: fixed; }
.pt thead th { font-size: 11px; font-weight: 800; color: var(--mark); text-align: right; padding: 0 4px 6px;
  border-bottom: 2px solid var(--mark); vertical-align: bottom; }
.pt thead th.l { text-align: left; }
.pt td, .pt th[scope=row] { border-bottom: 1px solid var(--lab-rule); padding: 4px; text-align: right; height: 44px; }
.pt tbody tr:nth-child(even) > * { background: var(--zebra); }
.pt th[scope=row] { text-align: left; font-weight: 400; line-height: 1.05; }
.pt th[scope=row] b { font-weight: 900; font-stretch: 66%; font-size: 17px; text-transform: uppercase; }
.pt th[scope=row] small { display: block; font-size: 11px; color: var(--lab-mute); margin-top: 2px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.pt col.c-in { width: 30px; } .pt col.c-v { width: 64px; } .pt col.c-q { width: 40px; }
.pt col.c-r { width: 34px; } .pt col.c-x { width: 28px; }
.pt tr.sep > td { height: 26px; text-align: left; font-size: 11px; font-weight: 800; color: var(--mark);
  background: var(--lab-stock) !important; border-bottom: 2px solid var(--mark); padding-top: 10px; vertical-align: bottom; }
.pt tr.out th[scope=row] b { font-weight: 800; }
.pt input[type=checkbox] { width: 16px; height: 16px; accent-color: var(--mark); margin: 0; }
.rb { width: 26px; height: 24px; font: 800 12px/1 var(--lab-face); border: 1.5px solid var(--lamp-off); border-radius: 0;
  background: var(--lab-stock); color: var(--lab-mute); cursor: pointer; padding: 0; }
.rb[aria-pressed=true] { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
.x { width: 24px; height: 24px; border: 0; background: none; color: var(--lab-mute); font: 800 16px/1 var(--lab-face);
  cursor: pointer; padding: 0; }
.x:hover { color: var(--lab-red); }
.srch { position: relative; margin: 0 0 10px; }
.srch label { display: block; font-size: 12px; color: var(--lab-mute); margin-bottom: 3px; }
.srch input { width: 100%; box-sizing: border-box; font: 400 14px/1.2 var(--lab-face); border: 1.5px solid var(--lamp-off);
  border-radius: 0; padding: 7px 8px; background: var(--lab-stock); color: var(--lab-ink); }
.res { position: absolute; z-index: 5; left: 0; right: 0; top: 100%; margin: 0; padding: 0; list-style: none;
  background: var(--lab-stock); border: 1px solid var(--lamp-off); border-top: 0; }
.res button { display: flex; width: 100%; gap: 8px; align-items: baseline; text-align: left; border: 0; background: none;
  color: var(--lab-ink); font: 400 13px/1.2 var(--lab-face); padding: 7px 8px; cursor: pointer; }
.res button:hover, .res button.on { background: var(--zebra); }
.res b { font-weight: 800; } .res span { color: var(--lab-mute); font-size: 12px; } .res em { margin-left: auto;
  font-style: normal; font-weight: 800; }
/* Phone: the tap-to-open rows of the Roster page, with St (starts) and Gms (games) in the row. */
@media (max-width: 899px) {
  .po .meta div { padding-left: 0; border-left: 0; padding-right: 16px; }
  .stats > div { padding: 0 12px; }
  .stats .hero dd { font-size: 28px; }
  table.wk th, table.wk td { padding: 4px 7px; }
  .po .m-head, .po .m-p summary { grid-template-columns: 44px minmax(0, 1fr) 34px 46px 26px; }
  .po .m-head span:nth-child(1) { padding-left: 16px; text-align: left; }
  .po .m-head span:nth-child(2) { padding-left: 10px; text-align: left; }
  .po .m-head span:nth-child(3), .po .m-head span:nth-child(4) { text-align: right; padding-left: 4px; }
  .po .m-p .nm b .lab-pname { display: inline; }
  .m-empty { margin: 10px 16px; color: var(--lab-mute); }
  .m-row { display: grid; grid-template-columns: repeat(var(--days), 1fr); }
  .m-row > span { text-align: center; font-size: 11px; font-weight: 800; padding: 3px 0; }
  .m-row > .q { background: var(--qcol); }
  .m-row > .wk1 { border-left: 1px solid var(--vrule); }
  .m-row.hd > span { font-size: 10px; font-weight: 700; color: var(--lab-mute); line-height: 1.1; padding: 2px 0; }
  .m-row.hd > .q { background: var(--mark); color: var(--lab-stock); }
  .m-row.hd u { display: block; text-decoration: none; color: var(--lab-ink); }
  .m-row.hd > .q u { color: var(--lab-stock); }
  .m-tot .m-row.hd { margin-top: 8px; }
  .m-tot dl dd small { display: block; font-size: 11px; font-weight: 600; color: var(--lab-mute); }
}"""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Playoffs · Fantasy Hoops Lab</title>
__HEAD__
<style>
__TABLE_CSS__
__CHART_CSS__
__STYLE__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main roster po">
<header class="head">
<h1>Playoffs</h1>
<dl class="meta">
<div><dt>Playoffs</dt><dd><strong>__WEEKS__</strong> · __SPAN__</dd></div>
<div class="ctl"><div><label for="n">Core size</label><input id="n" type="number" min="1" value="__N__"></div>
<button class="btn pri" id="save" type="button">Save</button>
<button class="btn" id="reset" type="button">Reset to best __N__</button>
<span class="saved" id="saved" role="status">Not saved</span></div>
</dl>
</header>
<dl class="stats" id="stats" aria-label="Headline"></dl>
<table class="wk" id="wk" aria-label="Totals of each week"></table>
<div class="lay">
<section aria-labelledby="h-grid">
<h2 id="h-grid">Core grid</h2>
<div class="scroll" tabindex="0" role="region" aria-label="Core grid"><table class="desk lab-t pg" id="grid"></table></div>
<section class="mob" id="mob" aria-label="Core grid" style="--days:__DAYS__"></section>
<div class="legend" aria-label="Key"><b>Key</b>
<span><i class="k s"></i>Starts</span>
<span><i class="k b"></i>Game, sits (start lost)</span>
<span><i class="k r"></i>Rests on back-to-back</span>
<span><i class="k n"></i>No game</span>
<span><span class="qsw"></span>Light night (6 or fewer NBA games)</span>
<span><span class="q-key">2 q</span>Games on light nights</span>
<span><em class="tag">R</em>Rests on back-to-backs</span>
<span><em class="tag">proj</em>Val from the projection</span>
</div>
</section>
<section aria-labelledby="h-pl">
<h2 id="h-pl">Players</h2>
<div class="srch"><label for="q">Add a player: your team, free agents or other teams</label>
<input id="q" type="search" autocomplete="off" placeholder="Name" role="combobox" aria-expanded="false" \
aria-controls="res" aria-autocomplete="list">
<ul class="res" id="res" role="listbox" aria-label="Players" hidden></ul></div>
<table class="pt" id="pt"><colgroup><col class="c-in"><col><col class="c-v"><col class="c-q"><col class="c-r">\
<col class="c-x"></colgroup></table>
</section>
</div>
<p class="foot">__FOOT__</p>
</main>
__PLAYER_MODAL__
__SCRIPT__
__DATA__
</body>
</html>
"""
