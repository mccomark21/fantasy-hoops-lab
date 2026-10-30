"""The Players page at /players/ and the shared player file (#186). It writes output/players/index.html,
output/players/players.json and the font in output/players/fonts/.

The page is a 4-quadrant report card of one player, not a scrolling page. A search box picks the player and the URL
hash keeps the pick (/players/#<slug>). The card comes from core/profile.py, the same card as the player modal of the
Roster, Free agents and Trades pages. The page reads the shared player file, profile.DATA_FILE, as the modal does.
The player file holds the players of players/data.py: each rostered player of the league, and each free agent with a
projected value or 5 or more games.
The planning run (adds/plan.py) calls write_site() and publishes the folder at /players/ with its own folders.
The trade run does not write the page, because it reads no free-agent list and so has no Val of the Free agents page.
Its publish keeps /players/.
"""

import json

from fantasyhoops.adds.value import REPLACEMENT_RANK
from fantasyhoops.core import common, profile
from fantasyhoops.core import publish as site
from fantasyhoops.players import categories, data

CURRENT = "players"  # the page in the site menu and its folder on the site (publish.TOOLS)


def folder():
    """The page folder: output/players, from common.OUT at the time of the call."""
    return common.OUT / CURRENT


def read_owners(reader, skip_recent):
    """The RosteredRead of all teams from the Yahoo rostered list, or None if the read fails.

    reader: a reader with get(path), for example cache.PageCache.rostered(). skip_recent: True while
    lists.skips_recent_view() skips the recent view, as for the free-agent lists. Then the read has the projected
    view only.
    A failed read (a changed page, a page that does not load, a Yahoo timeout or a network error) prints a warning.
    The planning run then continues, and its publish keeps the /players/ folder of the site.
    A Yahoo block (YahooBlocked) is not caught. #107 says that a block stops the planning run.
    """
    from fantasyhoops.adds.session import YahooBlocked
    from fantasyhoops.trade.rostered import read_rostered

    try:
        return read_rostered(reader, None, skip_recent=skip_recent)
    except YahooBlocked:
        raise  # #107: a Yahoo block stops the planning run, with no more Yahoo loads
    except Exception as error:  # noqa: BLE001 - each failure of this optional read keeps the old page
        print(
            "Warning: the run could not read the rostered list for the Players page "
            f"({type(error).__name__}: {error}). The publish keeps the old Players page."
        )
        return None


def player_file(records, made, projections, log_first=None, log_last=None, replacement=None):
    """The shared player file as a dict: meta, the team band of each NBA team of the players and the players.

    records: players/data.player_records(). made: the date of the owners. projections: the projections file name, or
    None.
    log_first, log_last: the first and the last date of the rotation log, or None.
    replacement: the replacement value of the run. None: no Val.
    """
    teams = sorted({r["team"] for r in records} | {""})
    rostered = sum(r["owner"] is not None for r in records)
    return {
        "meta": {
            "made": f"{made:%Y-%m-%d}",
            "rostered": rostered,
            "free_agents": len(records) - rostered,
            "min_games": data.MIN_GAMES,
            "projections": projections,
            "log_first": log_first,
            "log_last": log_last,
            "replacement_rank": REPLACEMENT_RANK,
            "has_val": replacement is not None,
        },
        "bands": {t: site.band_style(t or None) for t in teams},
        "players": records,
    }


def count_text(meta):
    """The count line of the page, for example "512 players: 196 rostered and 316 free agents."."""
    total = meta["rostered"] + meta["free_agents"]
    return f"{total} players: {meta['rostered']} rostered and {meta['free_agents']} free agents."


def render(cfg, meta):
    """The HTML of the Players page. cfg: the config ([league] teams for the menu). meta: the meta of player_file()."""
    return site.shell(PAGE, CURRENT, cfg).replace("__COUNT__", count_text(meta))


def write_site(rostered, own_team, cfg, made, options=(), replacement=None, scale=None):
    """Write the Players page and the player file in folder(). Return (page path, (player file path,)).

    rostered: the RosteredRead of all teams (read_owners()). own_team: your team ID ([adds] team).
    made: the date of the rostered list. options, replacement, scale: the free-agent Options, the replacement value
    and the category scale of the planning run, for the Val (data.market_values()). replacement None: no Val.
    The return value is the more_tools entry of publish.publish().
    """
    projected, projections = data.read_projected(cfg)
    played, first, last = data.read_played()
    values = {} if replacement is None else data.market_values(rostered, options, replacement, scale, cfg)
    extras = {key: {"cats": cats} for key, cats in categories.read_categories(cfg).items()}
    records = data.player_records(
        data.owned_players(rostered.projected, own_team), projected, played, values, extras=extras
    )
    content = player_file(records, made, projections, first, last, replacement)
    out = folder()
    out.mkdir(parents=True, exist_ok=True)
    path = out / profile.DATA_FILE
    path.write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return site.write_page(out / "index.html", render(cfg, content["meta"])), (path,)


# The top line and the card. At 1440 x 900, the top line, the header and the 4 quadrants fit with no page scroll.
STYLE = """/* The Players page (issue 186): a top line with the search, then the player card. */
.pp { padding: 12px max(24px, env(safe-area-inset-right)) 16px max(24px, env(safe-area-inset-left));
  font: 400 13px/1.35 var(--lab-face); color: var(--lab-ink); }
.pp-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; margin-bottom: 10px; font-size: 12px;
  color: var(--lab-mute); }
.pp-top h1 { margin: 0; color: var(--mark); font-weight: 900; font-stretch: 66%; font-size: 24px; line-height: 1;
  text-transform: uppercase; }
.pp-find { display: flex; align-items: center; gap: 6px; font-weight: 800; color: var(--lab-ink); }
.pp-find input { width: 220px; min-height: 28px; padding: 3px 6px; border: 1.5px solid var(--lamp-off); border-radius: 0;
  background: var(--lab-stock); color: var(--lab-ink); font: 400 13px/1.2 var(--lab-face); }
.pp-find input:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.pp-msg { margin: 0; color: var(--lab-red); font-weight: 800; }
.pp-msg:empty { display: none; }
.pp-count { margin: 0 0 0 auto; }
@media (max-width: 799px) {
  .pp { padding: 12px 14px 32px; }
  .pp-find input { width: 100%; }
  .pp-find { flex: 1 1 100%; }
  .pp-count { margin-left: 0; }
}"""

# The search box and the hash. "#<slug>" picks a player. A "#player=<slug>" hash belongs to the modal.
SCRIPT = r"""<script>
(() => {
  const root = document.getElementById("pp-card"), q = document.getElementById("pp-q");
  const msg = document.getElementById("pp-msg"), list = document.getElementById("pp-names");
  LabCard.load().then(d => {
    list.innerHTML = d.players.map(p => `<option value="${LabCard.esc(p.name)}">`).join("");
    let shown = null;
    const show = p => {
      shown = p.slug;
      LabCard.render(root, p, d, "pc");
      document.title = `${p.name} · Players · Fantasy Hoops Lab`;
    };
    const route = () => {
      if (location.hash.startsWith("#player=")) { if (!shown && d.players.length) show(d.players[0]); return; }
      const p = d.bySlug.get(location.hash.slice(1));
      if (p) show(p);
      else if (d.players.length) location.replace("#" + d.players[0].slug);
      else root.innerHTML = '<p class="lc-msg">The player file has no players.</p>';
    };
    const go = () => {
      const v = q.value.trim().toLowerCase();
      if (!v) return;
      const p = d.players.find(x => x.name.toLowerCase() === v) || d.players.find(x => x.name.toLowerCase().includes(v));
      if (!p) { msg.textContent = "No player on this page has that name."; return; }
      msg.textContent = ""; q.value = "";
      location.hash = p.slug;
    };
    q.addEventListener("change", go);
    q.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    window.addEventListener("hashchange", route);
    route();
  }, () => { root.innerHTML = '<p class="lc-msg">The player file did not load. Try again later.</p>'; });
})();
</script>"""

PAGE = (
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Players</title>
__HEAD__
<style>
__CHART_CSS__
"""
    + STYLE
    + """
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main pp">
<div class="pp-top">
<h1>Players</h1>
<label class="pp-find">Find a player <input type="search" id="pp-q" list="pp-names" autocomplete="off" placeholder="Name"></label>
<datalist id="pp-names"></datalist>
<p class="pp-msg" id="pp-msg" aria-live="polite"></p>
<p class="pp-count">__COUNT__</p>
</div>
<div class="lab-card" id="pp-card"><p class="lc-msg">Loading the player file…</p></div>
<div class="lab-tt" id="lab-tt-page" role="tooltip" hidden></div>
</main>
__PLAYER_MODAL__
__SCRIPT__
"""
    + SCRIPT
    + """
</body>
</html>
"""
)
