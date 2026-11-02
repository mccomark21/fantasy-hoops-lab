"""The League page at /league/ (#218): the playoff value, the starts and the open slots of each team of the league.

It writes output/league/index.html and the font in output/league/fonts/.

The design is in docs/league/README.md and in the owner decisions of 2026-11-02 on #218. The page has one row for
each team. The core of each other team is its best [playoffs] core players by value started (bestCore() of
core/starts.js). Your row uses the core that you saved on the Playoffs page (localStorage key playoffs.STORE_KEY),
else your best core. The stream spots fill the open slots of the core (streamFill() of core/starts.js). Each open slot
that they fill is worth v, the mean Val of the best [league_page] v_free_agents free agents of the run.
The page data (page_data()) holds the playoff days, the pool of the Playoffs page, v and the records of the Yahoo
standings. league.js draws the page in the browser. core/starts.js gives each lineup number. The page inlines both
scripts.
The planning run (adds/plan.py) reads the standings (read_records()), calls write_site() after the Playoffs page and
publishes the folder at /league/. The trade run does not write the page. Its publish keeps /league/.
Each column header except Team and Record has a description (#227): notes() of league.js gives the text of the
header tooltip and of the closed "Column meanings" list below the table. The footer has only the data line.
"""

import html
import json
from pathlib import Path

from fantasyhoops.core import common
from fantasyhoops.core import publish as site
from fantasyhoops.core.lineup import ENGINE_JS
from fantasyhoops.core.roster import PAGE_STYLE as ROSTER_STYLE
from fantasyhoops.playoffs import page as playoffs_page

CURRENT = "league"  # the page in the site menu and its folder on the site (publish.TOOLS)
SCRIPT = Path(__file__).parent / "league.js"


def folder():
    """The page folder: output/league, from common.OUT at the time of the call."""
    return common.OUT / CURRENT


def read_records(league):
    """{team name: record (W-L-T)} from the standings of the Yahoo league home page, or {} if the read fails.

    league: a session.League. The read is one more page load of the planning run. A failed read (a changed page, a
    page that does not load, a Yahoo timeout or a network error) prints a warning, and the page shows no records.
    A Yahoo block (YahooBlocked) is not caught. #107 says that a block stops the planning run.
    """
    from fantasyhoops.adds.readers import read_standings
    from fantasyhoops.adds.session import HOME_PATH, YahooBlocked

    try:
        return read_standings(league.get(HOME_PATH))
    except YahooBlocked:
        raise  # #107: a Yahoo block stops the planning run, with no more Yahoo loads
    except Exception as error:  # noqa: BLE001 - the records are optional, so a failure gives a page with no records
        print(
            "Warning: the run could not read the standings for the League page "
            f"({type(error).__name__}: {error}). The League page shows no records."
        )
        return {}


def stream_value(players, count):
    """(v, the free agents of v): v is the mean value of the count best free agents of players (pool() records).

    A free agent is a player with no owner. With no free agent, v is 0.
    """
    free = sorted((p for p in players if not p["owner"]), key=lambda p: -p["value"])[:count]
    return (sum(p["value"] for p in free) / len(free) if free else 0.0), free


def team_records(players, standings):
    """{team name: record} for each owner of players. A team that the standings do not name gets None.

    The name must match the owner name of the player file. A second check ignores the case and the outer spaces.
    """
    folded = {k.strip().casefold(): v for k, v in standings.items()}
    owners = sorted({p["owner"] for p in players if p["owner"]})
    return {t: standings.get(t, folded.get(t.strip().casefold())) for t in owners}


def page_data(records, days, cfg, made, standings=None):
    """The data of the page as a dict. records: the players of the player file. days: roster.playoff_days().

    made: the date of the player file, for example "2026-11-01". standings: read_records(), or None.
    """
    base = playoffs_page.page_data(records, days, cfg, made)
    v, free = stream_value(base["players"], cfg["league_page"]["v_free_agents"])
    keep = ("made", "key", "core", "slots", "util", "quality_bonus", "weeks", "span", "days", "players")
    data = {k: base[k] for k in keep}
    data.update(
        roster_spots=cfg["league"]["roster_spots"],
        adds=cfg["league"]["adds"],
        v=round(v, 4),
        v_count=cfg["league_page"]["v_free_agents"],
        v_players=[{"name": p["name"], "value": p["value"]} for p in free],
        records=team_records(base["players"], standings or {}),
    )
    return data


def render(data, cfg):
    """The HTML of the League page. data: page_data(). cfg: the config ([league] teams for the menu)."""
    weeks = data["weeks"]
    digits = "".join(c for c in weeks[-1] if c.isdigit())
    first = weeks[0][:1].upper() + weeks[0][1:]
    n_days = len(data["days"])
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    script = (
        f'<script type="application/json" id="lg-data">{text}</script>\n'
        f"<script>\n{ENGINE_JS.read_text(encoding='utf-8')}\n{SCRIPT.read_text(encoding='utf-8')}\n"
        'League.start(document, JSON.parse(document.getElementById("lg-data").textContent));\n</script>'
    )
    style = (ROSTER_STYLE + "\n" + playoffs_page.STYLE + "\n" + STYLE).replace("__DAYS1__", str(n_days + 1))
    foot = FOOT.replace("__MADE__", playoffs_page._made_text(data["made"])).replace(
        "__WEEKS__", f"{weeks[0][2:]} to {digits}"
    )
    teams = len({p["owner"] for p in data["players"] if p["owner"]})
    return (
        site.shell(PAGE_HTML.replace("__STYLE__", style.replace("__DAYS__", str(n_days))), CURRENT, cfg)
        .replace("__WEEKS__", f"{first}–{digits}")
        .replace("__SPAN__", html.escape(data["span"]))
        .replace("__TEAMS__", str(teams))
        .replace("__NOTE__", note(data))
        .replace("__FOOT__", foot)
        .replace("__DATA__", script)
    )


def note(data):
    """The rules line above the table, with the core size, the add limit and v."""
    return (
        f"Each team: the best {data['core']} players by value started alone (the Playoffs page rule). Your row: the "
        f"core that you saved on the Playoffs page, else the best {data['core']}. Stream spots: "
        f"{data['roster_spots']} roster spots minus the core. Each week the streams fill the open slots that the "
        f"stream spots and {data['adds']} adds can reach, heavy nights first. A stream player fills only the "
        f"positions that fit on his first start. v = {data['v']:.2f}, the mean Val of the top {data['v_count']} free "
        'agents: <span id="fa-list"></span>.'
    )


def write_site(player_file, days, cfg, standings=None):
    """Write the League page in folder() from the player file of the run. Return the page path.

    player_file: the path of players.json (players/page.py write_site()). days: roster.playoff_days().
    standings: read_records(), or None. The return value is the more_tools entry of publish.publish().
    """
    content = json.loads(Path(player_file).read_text(encoding="utf-8"))
    data = page_data(content["players"], days, cfg, content["meta"]["made"], standings)
    return site.write_page(folder() / "index.html", render(data, cfg))


# The data line under the table. The column descriptions are in notes() of league.js (#227).
FOOT = "Data: the planning run of __MADE__, the Yahoo standings and the NBA schedule, playoff weeks __WEEKS__."

STYLE = """/* The League page (#218): the rules line, the table and the core of a team. */
.lg .q { margin: 10px 0 0; font-size: 13px; color: var(--lab-mute); max-width: 84ch; line-height: 1.45; }
.lg .q b { color: var(--lab-ink); }
.lg .ranks { list-style: none; margin: 12px 0 0; padding: 0; font-size: 13px; line-height: 1.5; }
.lg .ranks b { font-weight: 800; color: var(--mark); }
.lg .scroll.lgs { display: block; overflow-x: auto; margin-top: 16px; }
table.lgt { min-width: 900px; }
.lgt thead th { white-space: nowrap; }
.lgt thead th button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
.lgt thead th button:hover { text-decoration: underline; }
/* The header tooltip (#227): the card of DESIGN.md "Tooltips", with a column name and its description. */
.lg-tt { position: fixed; z-index: 50; pointer-events: none; box-sizing: border-box; min-width: 168px;
  max-width: 260px; padding: 7px 10px 8px; border: 1px solid var(--lamp-off); border-radius: 0;
  background: var(--lab-stock); color: var(--lab-ink); font: 400 12px/1.35 var(--lab-face);
  font-variant-numeric: tabular-nums; text-align: left; white-space: normal; }
.lg-tt[hidden] { display: none; }
.lg-tt .lg-tt-h { color: var(--lab-mute); font-size: 11px; font-weight: 700; }
.lg-tt p { margin: 2px 0 0; }
/* The "Column meanings" list (#227): closed, below the table. */
.lg details.lg-notes { margin: 14px 0 0; font-size: 13px; line-height: 1.45; color: var(--lab-mute); max-width: 84ch; }
.lg details.lg-notes summary { cursor: pointer; color: var(--lab-ink); font-weight: 700; width: fit-content;
  min-height: 28px; padding: 4px 0; box-sizing: border-box; }
.lg details.lg-notes summary:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.lg details.lg-notes p { margin: 4px 0 8px; }
.lg .lg-defs { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; margin: 0; }
.lg .lg-defs dt { color: var(--lab-ink); font-weight: 800; }
.lg .lg-defs dd { margin: 0; }
.lgt thead th button:focus-visible, .lgt tr[data-t]:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: -2px; }
.lgt thead th i { font-style: normal; font-size: 9px; margin-left: 3px; }
.lgt thead th.rkh { width: 34px; }
.lgt tbody tr[data-t] { cursor: pointer; }
.lgt tbody tr[data-t]:hover > * { background: var(--qcol); }
.lgt th.tm { text-align: left; padding-left: 8px; white-space: nowrap; }
.lgt th.tm b { font-weight: 900; font-stretch: 66%; font-size: 19px; text-transform: uppercase; }
.lgt td.total { font-weight: 900; font-stretch: 75%; font-size: 19px; }
.lgt td small { font-size: 11px; color: var(--lab-mute); margin-left: 3px; }
.lgt td.heavy, .lgt td.light { font-weight: 800; }
.lgt .mute { color: var(--lab-mute); }
.lgt tr.mine > * { background: color-mix(in srgb, var(--mark) 12%, var(--lab-stock)) !important; }
.lgt tr.mine > td.rk { box-shadow: inset 4px 0 0 var(--mark); }
.tag.you { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
.lgt tr.det > td { height: auto; text-align: left; padding: 8px 10px 12px 44px; background: var(--lab-stock) !important; }
.lgt tr.det p { margin: 0 0 6px; font-size: 13px; }
.lgt tr.det .outp { color: var(--lab-mute); margin-top: 6px; }
.cp { margin: 0; padding: 0; list-style: none; columns: 2 300px; column-gap: 28px; font-size: 13px; }
.cp li { display: flex; gap: 8px; align-items: baseline; padding: 3px 0; border-bottom: 1px solid var(--lab-rule);
  break-inside: avoid; }
.cp li b { font-weight: 800; } .cp li span { color: var(--lab-mute); font-size: 12px; }
.cp li em { margin-left: auto; font-style: normal; font-weight: 800; font-variant-numeric: tabular-nums; }
.cp li .s { width: 40px; text-align: right; }
@media (max-width: 899px) {
  .lgt th.tm { position: sticky; left: 0; z-index: 1; background: var(--lab-stock); max-width: 140px; overflow: hidden;
    text-overflow: ellipsis; }
  .lgt tbody tr:nth-child(even) > th.tm { background: var(--zebra); }
  .lgt th.tm b { font-size: 16px; }
  .lgt tr.det > td { padding-left: 10px; }
}"""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>League · Fantasy Hoops Lab</title>
__HEAD__
<style>
__TABLE_CSS__
__STYLE__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main roster po lg">
<header class="head">
<h1>League</h1>
<dl class="meta">
<div><dt>Playoffs</dt><dd><strong>__WEEKS__</strong> · __SPAN__</dd></div>
<div><dt>Teams</dt><dd><strong>__TEAMS__</strong></dd></div>
</dl>
</header>
<p class="q">__NOTE__</p>
<dl class="stats" id="sum" aria-label="Your team"></dl>
<ul class="ranks" id="ranks" aria-label="Your ranks"></ul>
<div class="scroll lgs" tabindex="0" role="region" aria-label="League table"><table class="lab-t lgt" id="lg"></table></div>
<details class="lg-notes" id="lg-notes"><summary>Column meanings</summary>
<p>Click a header to sort. Click a team to see its core.</p>
<dl class="lg-defs" id="lg-defs"></dl>
</details>
<p class="foot">__FOOT__</p>
<div class="lg-tt" id="lg-tt" aria-hidden="true" hidden></div>
</main>
__SCRIPT__
__DATA__
</body>
</html>
"""
