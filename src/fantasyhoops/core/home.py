"""The Home page of the site at / (#172): what each page of the site does, the story of the project and the league.

The owner approved the sample of 2026-10-29 (docs/wiki/about-home-page-2026-10-29.md). The page holds no live data.
The examples of the pages are fixed rows with the caption "Example". The league facts come from config.toml.
The page names no league platform and no data source by name (owner change of 2026-10-29). It says "the league
site" and "public NBA stats".

publish.shell() gives the head, the icon and the preview tags, the menu and the menu script (#132, #166).
publish.publish() puts the page at the root of the site at each publish (core/publish.py).
render() gives the page HTML. write() writes output/home/index.html with publish.write_page(), which also writes the
font to fonts/ next to the page. Run python -m fantasyhoops.core.home to write the page with no publish.
"""

import html

from fantasyhoops.core import common, tokens
from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.core import publish as site

REPO_URL = "https://github.com/mccomark21/fantasy-hoops-lab"
# The scoring categories of the league. The value math uses the 6 categories of [weights] in config.toml.
CATEGORIES = ("PTS", "REB", "AST", "3PM", "BLK", "STL")
PUNTED = ("FG%", "FT%", "TO")
ARROW = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h9M8 3.5 12.5 8 8 12.5"/></svg>'
EXAMPLE_TEAMS = ("DAL", "MIN", "TOR", "CHA")  # the NBA teams of the example rows


def _band(team):
    """The style attribute of an example team band: the team color and its text color (core/tokens.py)."""
    color = tokens.TEAM_COLORS[team]
    return f"--team:{color};--team-ink:{tokens.team_ink(color)}"


def _week_number(name):
    """The number of a playoff week name, for example 19 for "wk19"."""
    return int("".join(c for c in name if c.isdigit()))


def facts(cfg):
    """The league facts of the page from cfg (config.toml), as {placeholder: text}."""
    league = cfg["league"]
    weeks = cfg["playoffs"]["weeks"]
    first, last = _week_number(weeks[0]["name"]), _week_number(weeks[-1]["name"])
    season = league["espn_season"]
    return {
        "__TEAMS__": str(league["teams"]),
        "__BUDGET__": str(cfg["auction"]["budget"]),
        "__SLOTS__": ", ".join(league["slots"]),
        "__BENCH__": str(league["roster_spots"] - len(league["slots"]) - 1),
        "__ADDS__": str(league["adds"]),
        "__WEEKS__": f"{first} to {last}",
        "__DAYS__": str(sum((w["end"] - w["start"]).days + 1 for w in weeks)),
        "__KEPT__": str(cfg["trade"]["kept"]),
        "__SEASON__": f"{season - 1}–{str(season)[2:]}",
        "__PUNTED__": f"{', '.join(PUNTED[:-1])} and {PUNTED[-1]}",
        "__PUNTS__": " ".join(f"<s>{html.escape(p)}</s>" for p in PUNTED),
        "__PUNT_COUNT__": str(len(PUNTED)),
        "__CATEGORIES__": ", ".join(CATEGORIES),
        "__CAT_COUNT__": str(len(CATEGORIES)),
        "__ALL_COUNT__": str(len(CATEGORIES) + len(PUNTED)),
    }


def render(cfg):
    """The HTML of the Home page. cfg: the config. It gives the league facts and the team count of the site menu."""
    text = site.shell(PAGE_HTML, "home", cfg)
    for key, value in facts(cfg).items():
        text = text.replace(key, value)
    for team in EXAMPLE_TEAMS:
        text = text.replace(f"__BAND_{team}__", _band(team))
    return text.replace("__ARROW__", ARROW).replace("__REPO__", REPO_URL)


def page_path():
    """The page file: output/home/index.html, from common.OUT at the time of the call."""
    return common.OUT / "home" / "index.html"


def write(text, path=None):
    """Write the page to path (default page_path()) with the font next to it. Return the path."""
    return site.write_page(path or page_path(), text)


def main():
    """Write the Home page to output/home/index.html with no publish, and print the path."""
    print(f"Wrote the Home page: {write(render(common.load_config()))}")


PAGE_STYLE = """/* The Home page (#172). Colors only from the tokens. */
.hm { max-width: 1000px; box-sizing: border-box;
  padding: 24px max(28px, env(safe-area-inset-right)) 40px max(28px, env(safe-area-inset-left));
  font: 400 15px/1.5 var(--lab-face); font-variant-numeric: tabular-nums; }
.hm *, .hm *::before, .hm *::after { box-sizing: border-box; }
.hm a { color: var(--mark); text-underline-offset: 3px; text-decoration-thickness: 1px; }
.hm a:hover { text-decoration-thickness: 2px; }
.hm a:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }
.hm-top h1 { margin: 0; padding-bottom: 12px; border-bottom: 3px solid var(--mark); color: var(--mark);
  font-weight: 900; font-stretch: 66%; font-size: clamp(36px, 5vw, 56px); line-height: .9;
  text-transform: uppercase; text-wrap: balance; }
.hm-lede { max-width: 58ch; margin: 14px 0 0; font-size: 17px; line-height: 1.45; text-wrap: pretty; }
.hm-sec { margin-top: 44px; }
.hm-sec h2 { margin: 0 0 4px; padding-bottom: 6px; border-bottom: 2px solid var(--mark);
  font-weight: 900; font-stretch: 75%; font-size: 19px; line-height: 1.1; text-transform: uppercase; }

/* One ruled row for each page: the text at the left, an example of the page at the right. */
.pg { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: 32px; align-items: start;
  padding: 22px 0 24px; border-bottom: 1px solid var(--lab-rule); }
.pg-text { max-width: 46ch; }
.pg h3 { margin: 0; font-weight: 900; font-stretch: 66%; font-size: 30px; line-height: 1; text-transform: uppercase; }
.pg h3 a { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
.pg h3 a:hover { text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 4px; }
.pg h3 svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2.4;
  transition: transform .2s cubic-bezier(.16, 1, .3, 1); }
.pg h3 a:hover svg { transform: translateX(3px); }
.pg-job { margin: 8px 0 6px; font-weight: 800; font-size: 16px; line-height: 1.35; }
.pg-text p:not(.pg-job) { margin: 0; color: var(--lab-mute); }
.pg-fig { margin: 4px 0 0; min-width: 0; }
.pg-fig figcaption { margin-top: 8px; font-size: 12px; color: var(--lab-mute); }
@media (max-width: 1099px) { .pg { grid-template-columns: 1fr; gap: 16px; } .pg-text { max-width: 62ch; } }
@media (prefers-reduced-motion: reduce) { .pg h3 svg { transition: none; } }

/* Roster example. */
.sp-roster td.band, .sp-fa td.band { width: 46px; }
.sp-roster td.rk { width: 38px; }
.sp-roster tbody td { font-size: 14px; }
.sp-roster b { font-weight: 800; }
.sp-roster .lost { color: var(--lab-red); }

/* Adds plan example: a small week grid. */
.sp-grid { display: grid; grid-template-columns: 52px repeat(7, minmax(0, 1fr)); font-size: 12px; }
.sp-grid > span { --t: 0%; background: color-mix(in srgb, var(--mark) var(--t), var(--lab-stock)); }
.sp-grid > .g-lab { background: none; font-weight: 800; font-size: 11px; display: flex; align-items: center; }
.sp-grid .g-day { text-align: center; padding: 6px 0 2px; font-weight: 900; font-stretch: 75%; font-size: 14px; }
.sp-grid .g-n { text-align: center; padding: 2px 0 8px; font-weight: 800; font-size: 14px; border-bottom: 2px solid var(--lab-ink); }
.sp-grid .g-lab.rule { border-bottom: 2px solid var(--lab-ink); }
.sp-grid .past { background: color-mix(in srgb, var(--lab-mute) 10%, var(--lab-stock)); color: var(--lab-mute); font-weight: 400; }
.sp-grid .g-c { height: 62px; display: flex; align-items: center; position: relative; }
.sp-grid .g-c.start::before { content: ""; position: absolute; left: 50%; right: 0; top: calc(50% - 3px); height: 6px; background: var(--lab-ink); }
.g-add { position: relative; z-index: 1; display: flex; flex-direction: column; justify-content: center; width: calc(100% - 4px);
  margin: 0 2px; height: 52px; background: var(--lab-stock); border: 1.5px solid var(--lab-ink); border-top-width: 3px;
  text-align: center; font-size: 11px; color: var(--mark); }
.g-add u { text-underline-offset: 2px; }
.g-add b { font-weight: 900; font-stretch: 75%; font-size: 13px; color: var(--lab-ink); display: block; }
.g-band { width: 100%; height: 6px; background: var(--lab-ink); display: flex; justify-content: center; align-items: center; }
.g-band i { width: 16px; height: 16px; background: var(--lab-ink); }

/* Free agents example: day chips and one row. */
.sp-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.chip { display: inline-flex; flex-direction: column; align-items: center; padding: 5px 10px; border: 1.5px solid var(--lamp-off);
  background: var(--lab-stock); font-weight: 800; font-size: 13px; line-height: 1.2; }
.chip small { font-weight: 400; font-size: 11px; color: var(--lab-mute); }
.chip.on { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
.chip.on small { color: var(--lab-stock); }
.sp-fa thead td.sorted { box-shadow: inset 0 -3px 0 var(--mark); }
.flag { display: inline-block; vertical-align: 3px; padding: 0 3px; border: 1.5px solid var(--lab-ink); font-size: 11px; font-weight: 800; line-height: 1.3; }

/* Trades example: one suggestion. */
.sp-trade { display: grid; grid-template-columns: 22px minmax(0, 1fr) minmax(0, 1fr) auto; align-items: stretch;
  border-top: 2px solid var(--mark); border-bottom: 1px solid var(--lab-rule); }
.t-rk { align-self: center; color: var(--lab-red); font-weight: 900; font-stretch: 75%; font-size: 21px; }
.t-side { display: flex; min-width: 0; }
.t-band { flex: none; width: 46px; display: flex; align-items: center; justify-content: center; background: var(--team); color: var(--team-ink);
  font-weight: 900; font-stretch: 70%; font-size: 17px; }
.t-nm { padding: 8px 6px 8px 8px; min-width: 0; line-height: 1; }
.t-nm small, .t-tot small { display: block; font-size: 11px; font-weight: 800; color: var(--mark); margin-bottom: 4px; }
.t-nm b { font-weight: 900; font-stretch: 66%; font-size: 17px; text-transform: uppercase; }
.t-tot { padding: 8px 0 8px 10px; text-align: right; line-height: 1; white-space: nowrap; }
.t-tot b { font-weight: 900; font-size: 18px; }
.t-tot em { font-style: normal; font-weight: 800; font-size: 13px; }
.t-bar { display: block; margin: 6px 0 0 auto; width: 52px; height: 6px; background: var(--mark); }

/* About: the story and the league table. */
.ab { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 40px; padding-top: 18px; align-items: start; }
.ab-story p { margin: 0 0 14px; max-width: 62ch; font-size: 16px; line-height: 1.55; text-wrap: pretty; }
.lg { width: 100%; border-collapse: collapse; font-size: 14px; }
.lg caption { text-align: left; padding-bottom: 6px; border-bottom: 2px solid var(--mark); color: var(--mark);
  font-weight: 900; font-stretch: 75%; font-size: 15px; text-transform: uppercase; }
.lg th, .lg td { text-align: left; vertical-align: top; padding: 8px 8px 8px 0; border-bottom: 1px solid var(--lab-rule); }
.lg th { width: 92px; font-size: 12px; font-weight: 800; padding-top: 10px; }
.lg tr:nth-child(even) > * { background: var(--zebra); }
.lg tr > :first-child { padding-left: 8px; }
.punt { display: block; color: var(--lab-mute); font-size: 13px; }
@media (max-width: 1099px) { .ab { grid-template-columns: 1fr; gap: 24px; } .lg { max-width: 480px; } }

/* How it works. */
.how { margin: 16px 0 0; padding: 0; list-style: none; counter-reset: s; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
.how li { counter-increment: s; color: var(--lab-mute); }
.how li::before { content: counter(s); display: block; margin-bottom: 6px; color: var(--mark); font-weight: 900; font-stretch: 75%; font-size: 26px; line-height: 1; }
.how b { color: var(--lab-ink); font-weight: 800; }
.hm-note { margin: 22px 0 0; padding: 10px 12px; border: 1px solid var(--vrule); max-width: 70ch; font-size: 14px; color: var(--lab-mute); }
@media (max-width: 799px) { .how { grid-template-columns: 1fr; gap: 14px; } }
.hm-foot { margin-top: 44px; padding-top: 10px; border-top: 3px solid var(--mark); display: flex; justify-content: space-between; gap: 12px;
  flex-wrap: wrap; font-size: 13px; color: var(--lab-mute); }
.hm-foot a { font-weight: 800; }

@media (max-width: 599px) {
  .hm { padding-left: max(16px, env(safe-area-inset-left)); padding-right: max(16px, env(safe-area-inset-right)); }
  .hm-lede { font-size: 16px; }
  .hm-sec { margin-top: 36px; }
  .pg h3 { font-size: 26px; }
  .sp-roster .wk { display: none; }
  .sp-grid { grid-template-columns: 40px repeat(7, minmax(0, 1fr)); }
  .g-add { width: calc(100% - 2px); margin: 0 1px; }
  .g-add b { font-size: 11px; font-stretch: 66%; }
  .g-band i { width: 13px; height: 13px; }
  .sp-roster td:last-child { border-left: 1px solid var(--vrule); }
  .sp-trade { grid-template-columns: 22px minmax(0, 1fr) auto; }
  .sp-trade .t-side + .t-side { grid-column: 2; grid-row: 2; border-top: 1px solid var(--lab-stock); }
  .sp-trade .t-rk { grid-row: 1 / 3; }
  .sp-trade .t-tot { grid-column: 3; grid-row: 1 / 3; align-self: center; }
}"""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fantasy Hoops Lab</title>
__HEAD__
<style>
__TABLE_CSS__
__STYLE__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main hm">

<header class="hm-top">
<h1>Fantasy Hoops Lab</h1>
<p class="hm-lede">Custom fantasy basketball tools for one league. Each page of this site helps me make one \
decision of the season: how my roster fits the playoffs, who to add, and which trade to make.</p>
</header>

<section class="hm-sec" aria-labelledby="pages-h">
<h2 id="pages-h">The pages</h2>

<article class="pg">
<div class="pg-text">
<h3><a href="roster/">Roster__ARROW__</a></h3>
<p class="pg-job">Who is on my team, and how many playoff games each player can start.</p>
<p>The players are in my custom-rank order. Each row has the season stats per game. For each playoff week \
(weeks __WEEKS__), the page counts the games that each player can start in the best lineup. A day grid shows who \
fits the lineup on each of the __DAYS__ playoff days. The last rows compare the team starts with the games of my \
players and with the ideal count.</p>
</div>
<figure class="pg-fig" aria-hidden="true">
<table class="lab-t sp-roster">
<thead><tr><td class="l">Team</td><td>Rk</td><td class="l">Player</td><td>PTS</td><td class="wk s1">Wk19</td>\
<td class="wk">Wk20</td><td class="wk">Wk21</td><td>T</td></tr></thead>
<tbody>
<tr><td class="band" style="__BAND_DAL__">DAL</td><td class="rk">12</td><th class="pl"><b>Cooper Flagg</b>\
<small>DAL · SG/SF/PF</small></th><td class="n"><b>25.2</b></td><td class="wk s1"><b>4</b>/4</td>\
<td class="wk"><b>4</b>/4</td><td class="wk"><b>4</b>/4</td><td><b>12</b>/12</td></tr>
<tr><td class="band" style="__BAND_MIN__">MIN</td><td class="rk">69</td><th class="pl"><b>Rudy Gobert</b>\
<small>MIN · C</small></th><td class="n"><b>6.6</b></td><td class="wk s1"><b class="lost">3</b>/4</td>\
<td class="wk"><b>2</b>/2</td><td class="wk"><b class="lost">2</b>/4</td><td><b class="lost">7</b>/10</td></tr>
</tbody>
</table>
<figcaption>Example rows. Starts / games for each playoff week.</figcaption>
</figure>
</article>

<article class="pg">
<div class="pg-text">
<h3><a href="adds/">Adds plan__ARROW__</a></h3>
<p class="pg-job">How to use the __ADDS__ adds of this fantasy week.</p>
<p>The planner finds the open starting slots on each day of the week. It recommends the NBA teams and the \
positions to add in each stream spot, and the day to add them. It does not pick the player. The week grid shows \
each add and the days that the new player starts. Above the grid, the matchup table shows the category totals of \
my team and my opponent.</p>
</div>
<figure class="pg-fig" aria-hidden="true">
<div class="sp-grid">
<span class="g-lab"></span>
<span class="g-day past">M</span><span class="g-day past">T</span><span class="g-day past">W</span>\
<span class="g-day" style="--t:10%">T</span><span class="g-day" style="--t:33%">F</span>\
<span class="g-day" style="--t:23%">S</span><span class="g-day" style="--t:13%">S</span>
<span class="g-lab rule">Games</span>
<span class="g-n past">9</span><span class="g-n past">4</span><span class="g-n past">12</span>\
<span class="g-n" style="--t:10%">3</span><span class="g-n" style="--t:33%">10</span>\
<span class="g-n" style="--t:23%">7</span><span class="g-n" style="--t:13%">4</span>
<span class="g-lab">Add 1</span>
<span class="g-c past"></span><span class="g-c past"></span><span class="g-c past"></span>
<span class="g-c start" style="--t:10%"><span class="g-add"><b>+SG/<wbr>PF</b><u>SAC</u></span></span>
<span class="g-c" style="--t:33%"><span class="g-band"><i></i></span></span>
<span class="g-c" style="--t:23%"><span class="g-band"></span></span>
<span class="g-c" style="--t:13%"><span class="g-band"><i></i></span></span>
</div>
<figcaption>Example add. The band shows the days he holds the spot. A square is a start.</figcaption>
</figure>
</article>

<article class="pg">
<div class="pg-text">
<h3><a href="free-agents/">Free agents__ARROW__</a></h3>
<p class="pg-job">The player for each add.</p>
<p>The table lists the free agents of the last planning run, with their value, their recent stats and their games \
on each day. Filter by day, position and team, then sort by value or by games. Flags mark an unusual value (FA?), \
a rise in minutes (MIN+) and a role up (UP). A click on an add in the Adds plan opens this page with those filters \
set. The page also lists the waiver players.</p>
</div>
<figure class="pg-fig" aria-hidden="true">
<div class="sp-chips">
<span class="chip">Thu 10/29<small>4 open · 3 NBA</small></span>
<span class="chip on">Fri 10/30<small>1 open · 10 NBA</small></span>
<span class="chip">Sat 10/31<small>2 open · 7 NBA</small></span>
</div>
<table class="lab-t sp-fa">
<thead><tr><td class="l">Team</td><td class="l">Player</td><td class="sorted">Val▼</td><td>Gms</td></tr></thead>
<tbody>
<tr><td class="band" style="__BAND_TOR__">TOR</td><th class="pl"><b>Ja’Kobe Walter</b> <span class="flag">FA?</span>\
<small>TOR · PG/SG</small></th><td class="n">+1.63</td><td class="n">2</td></tr>
</tbody>
</table>
<figcaption>Example filter and row.</figcaption>
</figure>
</article>

<article class="pg">
<div class="pg-text">
<h3><a href="trade/">Trades__ARROW__</a></h3>
<p class="pg-job">1-for-1 trades that help in the playoffs.</p>
<p>The trade tool suggests 1-for-1 trades with the other teams. Each suggestion raises my started games in playoff \
weeks __WEEKS__ and keeps my season value. The starts count my __KEPT__ kept players. The page also shows the trade \
deadline. Under the table, a trade builder checks a custom trade, for example 2-for-1, in the browser.</p>
</div>
<figure class="pg-fig" aria-hidden="true">
<div class="sp-trade">
<span class="t-rk">1</span>
<span class="t-side"><span class="t-band" style="__BAND_CHA__">CHA</span><span class="t-nm"><small>You give</small>\
<b>Coby White</b></span></span>
<span class="t-side"><span class="t-band" style="__BAND_DAL__">DAL</span><span class="t-nm"><small>You get</small>\
<b>P.J. Washington</b></span></span>
<span class="t-tot"><small>Playoff starts</small><b>88</b> <em>+5</em><span class="t-bar"></span></span>
</div>
<figcaption>Example suggestion. My playoff starts go from 83 to 88.</figcaption>
</figure>
</article>
</section>

<section class="hm-sec hm-about" aria-labelledby="about-h">
<h2 id="about-h">About this project</h2>
<div class="ab">
<div class="ab-story">
<p>Fantasy basketball is one of my favorite hobbies, and this site is where I play with it. Fantasy Hoops Lab \
started as a set of custom draft rankings for my league. It grew into a site with one page for each big decision \
of the season.</p>
<p>The public apps rank players on all __ALL_COUNT__ categories. My team punts __PUNT_COUNT__ of them: __PUNTED__. \
I wanted rankings and plans built for the __CAT_COUNT__ categories that I try to win. Each tool reads my real league \
and does the math in Python. Then it puts the result here, where I can open it at my desk or on my phone.</p>
<p>These are the tools for one team in one league. The settings, the punted categories and the strategy are mine. \
You are welcome to <a href="__REPO__">read the code</a> and take ideas from it.</p>
</div>
<table class="lg">
<caption>The league</caption>
<tbody>
<tr><th scope="row">Format</th><td>Head-to-head, __TEAMS__ teams</td></tr>
<tr><th scope="row">Draft</th><td>Auction, $__BUDGET__ budget</td></tr>
<tr><th scope="row">Roster</th><td>__SLOTS__, Util and __BENCH__ bench</td></tr>
<tr><th scope="row">Adds</th><td>__ADDS__ each week</td></tr>
<tr><th scope="row">Categories</th><td>__CATEGORIES__<span class="punt">__PUNTS__ punted</span></td></tr>
<tr><th scope="row">Playoffs</th><td>Weeks __WEEKS__</td></tr>
</tbody>
</table>
</div>
</section>

<section class="hm-sec" aria-labelledby="how-h">
<h2 id="how-h">How it works</h2>
<ol class="how">
<li><b>Data.</b> The tools read my league from the league site. The NBA rosters, the schedule and the season stats \
come from public NBA stats. A season projections file gives the projected stats.</li>
<li><b>Analysis.</b> The Python package computes the player values, the lineups, the plans and the trades.</li>
<li><b>Publish.</b> The adds planner and the trade tool write static pages and push them to GitHub Pages.</li>
</ol>
<p class="hm-note">The draft tools (the rankings, the draft board, an auction simulator and a keeper report) are \
local pages. They are not on this site.</p>
</section>

<footer class="hm-foot">
<a href="__REPO__">Code and docs on GitHub</a>
<span>__SEASON__ season</span>
</footer>
</main>
__SCRIPT__
</body>
</html>
""".replace("__STYLE__", PAGE_STYLE)


if __name__ == "__main__":
    use_utf8_output()
    main()
