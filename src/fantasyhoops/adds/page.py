"""The plan page: one HTML file in output/adds/ for use on a phone. The design is in docs/adds/README.md.

render() makes the page from the data of one planning run. Each section of the page comes from one small function.
A section shows only the parts that exist. The two main sections:
- Best plans for one roster spot: the SpotPlans of adds/spots.py, as a table of days.
- Free agents: a table with filters for days and positions. The page holds its data as JSON, and one inline
  script fills the table. The values are market values: the value above a replacement free agent (adds/value.py).
A third section lists the waiver players (W) with their clear days.
The page has inline CSS and no files from other sites. The colours and the font are the colours and the font of the
draft board.
"""
import html
import json
from datetime import date, timedelta

from fantasyhoops.adds.value import REPLACEMENT_RANK
from fantasyhoops.core.common import OUT as _OUT

OUT = _OUT / "adds"
PAGE = OUT / "adds_plan.html"
TITLE = "Weekly adds plan"
RANKING_ROWS = 12  # the teams in the ranking table
FREE_AGENT_ROWS = 10  # the rows of the free-agent table: the best players for the filters
FLAG = 1.5  # the market value from which a free agent gets the "FA?" mark
POSITIONS = ("PG", "SG", "SF", "PF", "C")  # the position filters


def _e(text):
    return html.escape(str(text))


def _day(d):
    """For example "Tue 10/20"."""
    return f"{d:%a} {d.month}/{d.day}"


def _player(p):
    status = f' <span class="status" title="{_e(p.status_name or p.status)}">{_e(p.status)}</span>' if p.status else ""
    if p.clear_day:
        status += f' <span class="status" title="Waiver claim, not sure. Clears {_day(p.clear_day)}.">W</span>'
    return f"{_e(p.name)}{status}"


CLAIM_NOTE = ("W: a waiver claim. It is not sure: a team with a higher waiver priority can claim him first. "
              "A claim uses an add.")


def _stat(value, label):
    return f'<div class="stat"><b>{_e(value)}</b><span>{_e(label)}</span></div>'


def header(data, days, spots, today):
    """The title, the fantasy week, the adds left, the stream spots and the players who are out."""
    week, adds = data.week, data.adds
    lines = [f"<h1>{TITLE}</h1>"]
    if data.next_week:
        lines.append(f"<p>Today is the last day of week {week.number - 1}. This page plans the next week.</p>")
    window = f" Planning window: {_day(days[0].date)} to {_day(days[-1].date)}." if days else ""
    lines.append(f"<p>Week {week.number}: {_day(week.start)} to {_day(week.end)}.{window} "
                 f"Made on {_day(today)}.</p>")
    stats = [_stat(f"{adds.left} of {adds.limit}", "adds left"), _stat(len(spots), "stream spots")]
    lines.append(f'<div class="stats">{"".join(stats)}</div>')
    out = [p.name + (f" ({p.status})" if p.status else "") for p in data.roster if p.out]
    if out:
        lines.append(f'<p>Out (does not play): {_e(", ".join(out))}.</p>')
    return "\n".join(lines)


def warnings_section(warnings):
    """The warnings, for example the core warning. Nothing if there are none."""
    items = "".join(f"<li>{_e(w)}</li>" for w in warnings)
    return f'<section class="warning"><ul>{items}</ul></section>' if items else ""


def _and(words):
    """For example "Tue, Thu & Sun"."""
    return " & ".join(filter(None, [", ".join(words[:-1]), words[-1]])) if words else ""


def _day_head(d):
    """A day column header: "Tue" and "10/20". On a phone, the page shows only the first letter."""
    name = f"{d:%a}"
    return f'<th>{name[0]}<span class="long">{name[1:]}</span><br><small>{d.month}/{d.day}</small></th>'


def _moves(row):
    """The moves of a SpotPlan: one line for each add, then the drop."""
    lines = [f'<div>+{_player(w.player.player)} ({_e(w.team)}) <span>– {_and([f"{d:%a}" for d in w.started])}</span>'
             f"</div>" for w in row.added]
    if row.spot.holder:
        lines.append(f"<div><span>drop {_e(row.spot.holder.player.name)}</span></div>")
    return "".join(lines)


def plans_section(rows, days, spots, adds, today):
    """The best plans for one roster spot: one row for each SpotPlan, one column for each day, then the adds,
    the games gained and the moves. A short message if there is no plan."""
    title = "<h2>Best plans for one roster spot</h2>"
    if not spots:
        return (f"<section>{title}\n<p>No stream spots. All roster spots hold a player, and [adds] stream_spots is 0. "
                "There are no adds to plan.</p></section>")
    if not adds.left:
        return (f"<section>{title}\n<p>No adds left this week ({adds.used} of {adds.limit} used). "
                "There are no adds to plan.</p></section>")
    if not days:
        return f"<section>{title}\n<p>The fantasy week is over. There are no days to plan.</p></section>"
    if not rows:
        return f"<section>{title}\n<p>No free agent that the planner read gives a started game.</p></section>"
    head = "".join(_day_head(d.date) for d in days)
    open_row = "".join(f'<td title="{_e(", ".join(d.open) or "no open slots")}">{len(d.open)}</td>' for d in days)
    body = [f'<tr class="open"><th>Open</th>{open_row}<td></td><td></td><td></td></tr>']
    for n, row in enumerate(rows, 1):
        cells = []
        for d in days:
            started = sum(d.date in w.started for w in row.added)
            add = "<i>+</i>" if any(w.add_day == d.date for w in row.added) else ""
            cells.append(f'<td class="on"><b>{started}{add}</b></td>' if started
                         else f"<td>{add or '·'}</td>")
        body.append(f'<tr><th>{n}</th>{"".join(cells)}<td class="total">{row.plan.adds}</td>'
                    f'<td class="total">{row.gain:+d}</td><td class="moves">{_moves(row)}</td></tr>')
    note = ""
    if any(w.add_day == today for row in rows for w in row.added):
        note = '\n<p class="muted">An add for today helps only if his game has not started.</p>'
    if any(w.player.player.clear_day for row in rows for w in row.added):
        note += f'\n<p class="muted">{CLAIM_NOTE}</p>'
    return (f'<section>{title}\n<table class="plans"><thead><tr><th></th>{head}<th class="total">Adds</th>'
            f'<th class="total">Gms</th><th class="moves">Moves</th></tr></thead><tbody>{"".join(body)}</tbody></table>\n'
            '<p class="legend">Each row is a plan for one roster spot, with different players in each row. A row can '
            'use more than one add in the same spot. A cell shows a started game of a new player. '
            '<i>+</i> marks a latest add day. Gms: the started games of the new players minus the started games that '
            f"the dropped player loses.</p>{note}</section>")


def free_agent_data(options, days, games, replacement):
    """The data of the free-agent table: the days and one row for each option who plays, best value first.

    A value is a market value: the value minus replacement. plays: his team plays on the day. fits: he plays and
    one of the open slots of the day takes one of his positions (Util takes all positions).
    """
    def market(v):
        return None if v is None or replacement is None else round(v - replacement, 2)

    players = []
    for o in sorted((o for o in options if not o.player.out and o.value is not None), key=lambda o: -o.value):
        p = o.player
        plays = [p.team in games.get(d.date, ()) for d in days]
        fits = [on and any(s in d.open for s in (*p.positions, "Util")) for on, d in zip(plays, days)]
        players.append({"name": p.name, "team": p.team, "pos": list(p.positions), "status": p.status,
                        "value": market(o.value), "recent": market(o.recent_value),
                        "trend": o.trend.adds_today if o.trend else None, "plays": plays, "fits": fits})
    return {"days": [{"label": f"{d.date:%a}", "md": f"{d.date.month}/{d.date.day}", "nba": d.nba_games,
                      "open": len(d.open)} for d in days],
            "players": players, "positions": list(POSITIONS), "flag": FLAG, "rows": FREE_AGENT_ROWS}


def free_agents_section(options, days, games, replacement):
    """The free-agent table with its filters. A script fills the table from the data. Nothing with no options.

    The table holds only the players with status FA. The waiver players are in waivers_section().
    """
    options = [o for o in options if not o.player.clear_day]
    if not options or not days:
        return ""
    data = json.dumps(free_agent_data(options, days, games, replacement), ensure_ascii=False).replace("</", "<\\/")
    return ('<section><h2>Free agents</h2>\n'
            '<div class="filters" id="day-chips"></div>\n<div class="filters" id="pos-chips"></div>\n'
            '<label class="toggle"><input type="checkbox" id="fit-only" checked> Only games that fill an open slot'
            '</label>\n<p class="count" id="fa-count"></p>\n<table class="fa" id="fa-table"></table>\n'
            '<p class="legend"><span class="dot fit"></span> game in an open slot that he can fill '
            '<span class="dot game"></span> game, no open slot for him. Val: blended value per game above a '
            f'replacement free agent (0 = the free agent at rank {REPLACEMENT_RANK} by value). A filter does not '
            'change Val. Gms: his games on the selected days. '
            '<span class="flag">FA?</span> a value this high is unusual for a free agent.</p>\n'
            f'<script type="application/json" id="fa-data">{data}</script>\n<script>{SCRIPT}</script></section>')


def waivers_section(options, replacement):
    """The waiver players (W), best value first: the clear day, the first day for a plan and the market value.

    Nothing if no option is on waivers.
    """
    waivers = sorted((o for o in options if o.player.clear_day and o.value is not None), key=lambda o: -o.value)
    if not waivers:
        return ""

    def market(v):
        return "—" if replacement is None else f"{v - replacement:+.2f}"

    rows = "".join(f'<tr><td class="name">{_player(o.player)}</td><td class="name">{_e(o.player.team)}</td>'
                   f'<td class="name">{_e(",".join(o.player.positions))}</td><td>{_day(o.player.clear_day)}</td>'
                   f'<td>{_day(o.player.clear_day + timedelta(days=1))}</td><td>{market(o.value)}</td></tr>'
                   for o in waivers)
    return ('<section><h2>Waiver players</h2>\n'
            '<table class="ranking"><thead><tr><th class="name">Player</th><th class="name">Team</th>'
            '<th class="name">Pos</th><th>Clears</th><th>First day</th><th>Val</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>\n'
            '<p class="legend">First day: the first day that a plan can use him, the day after he clears waivers. '
            f'Val: the same value as in the free-agent table. {CLAIM_NOTE}</p></section>')


def contingency_section(contingencies):
    """The contingency plans, one text line each. Nothing if there are none."""
    items = "".join(f"<li>{_e(c)}</li>" for c in contingencies)
    return f"<section><h2>Contingency plans</h2>\n<ul>{items}</ul></section>" if items else ""


def ranking_section(ranking, read):
    """The NBA teams by the open days that they cover. A * marks the teams whose free agents the planner read."""
    if not ranking:
        return ""
    rows = "".join(f'<tr><td class="name">{"*" if r.team in read else ""}{_e(r.team)}</td><td>{len(r.open_days)}</td>'
                   f'<td>{r.open_slots}</td><td class="name">{_e(" ".join(f"{d:%a}" for d in r.open_days))}</td></tr>'
                   for r in ranking[:RANKING_ROWS])
    more = (f'<p class="muted">{len(ranking) - RANKING_ROWS} more teams play on an open day.</p>'
            if len(ranking) > RANKING_ROWS else "")
    return ('<details class="notes"><summary>NBA teams by open days</summary>\n'
            '<table class="ranking"><thead><tr><th class="name">Team</th><th>Days</th><th>Slots</th>'
            f'<th class="name">Open days</th></tr></thead><tbody>{rows}</tbody></table>\n'
            f'<p class="muted">* = the planner read the free agents of this team.</p>{more}</details>')


def method_note():
    """A short note on the method for a reader who does not play in the league."""
    return ('<details class="notes"><summary>How the plan works</summary>\n'
            "<p>This is one team in a Yahoo fantasy basketball league. Each day, the team starts up to 6 players. "
            "A player scores only on a day when his NBA team plays and he is in a starting slot.</p>\n"
            "<p>The team keeps its core players all season. The other roster spots are stream spots. "
            "The league gives 5 adds each week, so the team can change the players in the stream spots.</p>\n"
            "<p>The planner finds the days with open starting slots. For each stream spot, it finds the free agents "
            "who give the most started games with the fewest adds. Each row of the plans is one roster spot.</p>\n"
            "<p>The value of a player is his value per game in the 6 categories that this league counts, above a "
            f"replacement free agent: 0 is the value of the free agent at rank {REPLACEMENT_RANK}.</p></details>")


def render(data, days, games, spots, rows, options=(), ranking=(), read=(), today=None, *, replacement=None,
           warnings=(), contingencies=()):
    """The plan page as HTML text.

    data: the LeagueData of the run (week, adds, roster, next_week). days: the Days of the planning window.
    games: {day: set of NBA teams that play}. spots: the StreamSpots. rows: the SpotPlans (adds/spots.py).
    options: the Options of the free agents. ranking: the TeamRanks. read: the teams whose free agents the run
    read. replacement: the value of a replacement free agent (value.replacement_value()), or None.
    warnings and contingencies: text lines.
    """
    today = today or date.today()
    sections = [
        header(data, days, spots, today),
        warnings_section(warnings),
        plans_section(rows, days, spots, data.adds, today),
        free_agents_section(options, days, games, replacement),
        waivers_section(options, replacement),
        contingency_section(contingencies),
        ranking_section(ranking, read),
        method_note(),
    ]
    return HTML.replace("__TITLE__", TITLE).replace("__BODY__", "\n".join(s for s in sections if s))


def write(text, path=None):
    """Write the page text to path (default: PAGE) and return the path."""
    path = path or PAGE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --bg: #fafaf9; --fg: #1c1917; --muted: #78716c; --line: #e7e5e4; --head: #f5f5f4;
        --good: #16a34a; --bad: #dc2626; --warn: #eab308; --avg: #d6d3d1; --q: #7c3aed; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg: #1c1917; --fg: #f5f5f4; --muted: #a8a29e; --line: #44403c;
        --head: #292524; --good: #22c55e; --bad: #ef4444; --warn: #facc15; --avg: #57534e; --q: #a78bfa; }
}
:root[data-theme="dark"] { --bg: #1c1917; --fg: #f5f5f4; --muted: #a8a29e; --line: #44403c;
        --head: #292524; --good: #22c55e; --bad: #ef4444; --warn: #facc15; --avg: #57534e; --q: #a78bfa; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: var(--bg); color: var(--fg);
       font: 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 720px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 20px 0 8px; }
h3 { font-size: 15px; margin: 0 0 4px; }
p { margin: 0 0 8px; color: var(--muted); }
.muted { color: var(--muted); }
.stats { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.stat { display: flex; align-items: baseline; gap: 6px; padding: 2px 10px; border: 1px solid var(--line);
        border-radius: 6px; background: var(--head); }
.stat b { font-size: 17px; font-variant-numeric: tabular-nums; }
.stat span { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.stat.key { border-color: var(--fg); }
.warning { border: 1px solid var(--bad); border-radius: 8px; padding: 4px 12px; margin: 8px 0; }
.warning ul { margin: 0; padding-left: 18px; color: var(--bad); font-weight: 600; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 5px 4px; text-align: right; border-bottom: 1px solid var(--line); }
thead th { background: var(--head); font-weight: 600; }
th.name, td.name { text-align: left; overflow-wrap: anywhere; }
.plans { table-layout: fixed; border: 1px solid var(--line); font-size: 12px; }
.plans th, .plans td { text-align: center; padding: 4px 1px; }
.plans th:first-child { width: 6%; }
.plans .total { width: 9%; font-weight: 700; font-size: 14px; }
.plans thead .total { font-size: 11px; }
.plans .moves { width: 36%; text-align: left; padding: 4px 6px; font-size: 11px; line-height: 1.35; }
.plans td.moves div + div { margin-top: 3px; }
.plans td.moves span { color: var(--muted); }
.plans small { color: var(--muted); font-weight: 400; }
.plans td.on { background: color-mix(in srgb, var(--good) 30%, transparent); }
.plans td b { font-size: 14px; }
.plans tr.open td, .plans tr.open th { background: var(--head); color: var(--q); font-weight: 700; }
i { font-style: normal; color: var(--q); font-weight: 700; }
@media (max-width: 599px) {
  .plans th:first-child { width: 11%; font-size: 10px; }
  .plans .total { width: 8%; }
  .plans thead .total { font-size: 9px; }
  .plans .moves { width: 38%; }
  .plans thead small, .plans .long { display: none; }
}
.legend { font-size: 12px; margin-top: 6px; }
.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
.filters .label { width: 100%; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
button.chip { font: inherit; font-size: 13px; padding: 4px 9px; border: 1px solid var(--line); border-radius: 999px;
              background: var(--bg); color: var(--fg); cursor: pointer; line-height: 1.2; }
button.chip small { display: block; color: var(--muted); font-size: 11px; }
button.chip[aria-pressed="true"] { background: var(--q); border-color: var(--q); color: #fff; }
button.chip[aria-pressed="true"] small { color: #ede9fe; }
button.chip.none { opacity: .55; }
label.toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; margin: 0 0 8px; }
.count { font-size: 12px; margin: 0 0 4px; }
.fa { font-size: 13px; }
.fa th.sort { cursor: pointer; white-space: nowrap; }
.fa th.sort[aria-sort] { color: var(--q); }
.fa th.day, .fa td.day { text-align: center; width: 26px; padding: 5px 0; }
.fa th.day.sel { color: var(--q); }
.fa td.sel { background: color-mix(in srgb, var(--q) 10%, transparent); }
.fa small, .fa .sub { color: var(--muted); font-weight: 400; font-size: 11px; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.dot.fit { background: var(--q); }
.dot.game { border: 1.5px solid var(--muted); }
.flag { display: inline-block; padding: 0 4px; border-radius: 4px; background: var(--good); color: #fff;
        font-size: 11px; font-weight: 700; }
.neg { color: var(--muted); }
.wide { display: none; }
@media (min-width: 600px) { .fa .wide { display: table-cell; } }
.status { display: inline-block; padding: 0 4px; border-radius: 4px; background: var(--warn); color: #1c1917;
          font-size: 11px; font-weight: 700; }
.ranking { font-size: 13px; }
details.notes { margin: 16px 0 8px; color: var(--muted); }
details.notes summary { cursor: pointer; color: var(--fg); font-weight: 600; width: fit-content; }
details.notes p, details.notes table { margin: 6px 0 0; }
</style>
</head>
<body>
<main>
__BODY__
</main>
</body>
</html>
"""

SCRIPT = r"""
const DATA = JSON.parse(document.getElementById("fa-data").textContent);
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const fmt = v => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2);
const state = {days: new Set(), pos: new Set(), fit: true, sort: "value"};
const hits = p => state.fit ? p.fits : p.plays;
const games = p => hits(p).filter((h, i) => h && (!state.days.size || state.days.has(i))).length;
const SORTS = {value: p => p.value, games: p => games(p) * 100 + p.value, recent: p => p.recent ?? -99};
const chip = (label, sub, on, dim) => `<button type="button" class="chip${dim ? " none" : ""}" aria-pressed="${on}">`
  + `${esc(label)}${sub ? `<small>${esc(sub)}</small>` : ""}</button>`;

function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); render(); }

function chips() {
  $("day-chips").innerHTML = `<span class="label">Days (plays on all selected days)</span>` + DATA.days.map((d, i) =>
    chip(`${d.label} ${d.md}`, `${d.open} open · ${d.nba} NBA`, state.days.has(i), !d.open)).join("");
  $("pos-chips").innerHTML = `<span class="label">Positions (any)</span>`
    + DATA.positions.map(p => chip(p, "", state.pos.has(p))).join("");
  $("day-chips").querySelectorAll("button").forEach((b, i) => b.onclick = () => toggle(state.days, i));
  $("pos-chips").querySelectorAll("button").forEach((b, i) => b.onclick = () => toggle(state.pos, DATA.positions[i]));
}

function render() {
  chips();
  const rows = DATA.players.filter(p => [...state.days].every(i => hits(p)[i])
    && (!state.pos.size || p.pos.some(x => state.pos.has(x))))
    .sort((a, b) => SORTS[state.sort](b) - SORTS[state.sort](a));
  $("fa-count").textContent = `Top ${Math.min(DATA.rows, rows.length)} of ${rows.length} free agents that match the filters`;
  const th = (key, label, cls) => `<th class="sort ${cls || ""}" data-sort="${key}"`
    + `${state.sort === key ? ' aria-sort="descending"' : ""}>${label}</th>`;
  const sel = i => state.days.has(i) ? " sel" : "";
  const head = DATA.days.map((d, i) => `<th class="day${sel(i)}">${d.label.slice(0, 2)}<br><small>${d.open}</small></th>`).join("");
  $("fa-table").innerHTML = `<thead><tr><th class="name">Player</th>${th("value", "Val")}${th("recent", "Recent", "wide")}`
    + `${th("games", "Gms")}${head}</tr></thead><tbody>` + rows.slice(0, DATA.rows).map(p =>
      `<tr><td class="name">${esc(p.name)}${p.status ? ` <span class="status">${esc(p.status)}</span>` : ""}`
      + `${p.value >= DATA.flag ? ' <span class="flag">FA?</span>' : ""}`
      + `<div class="sub">${esc(p.team)} · ${esc(p.pos.join(","))}${p.trend ? ` · ${p.trend} adds today` : ""}</div></td>`
      + `<td class="${p.value < 0 ? "neg" : ""}">${fmt(p.value)}</td><td class="wide">${fmt(p.recent)}</td><td>${games(p)}</td>`
      + DATA.days.map((d, i) => `<td class="day${sel(i)}">${p.fits[i] ? '<span class="dot fit"></span>'
        : p.plays[i] ? '<span class="dot game"></span>' : ""}</td>`).join("") + `</tr>`).join("") + `</tbody>`;
  $("fa-table").querySelectorAll("th.sort").forEach(h => h.onclick = () => { state.sort = h.dataset.sort; render(); });
}

$("fit-only").onchange = e => { state.fit = e.target.checked; render(); };
render();
"""
