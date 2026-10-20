"""The plan page: one HTML file in output/adds/ for use on a phone. The design is in docs/adds/README.md.

render() makes the page from the data of one planning run. Each section of the page comes from one small function.
A section shows only the parts that exist. The fields that later tickets add are optional:
- Option: recent_value, blended_value and trend. The options table gets a column for each field that one option
  or more has (not None).
- TeamWindow: drop, the text of the drop trade-off.
- Plan: blended_value, the blended value of the started games.
- render(): aggressive (a second Plan), warnings (text lines, for example the core warning) and contingencies
  (text lines, one for each contingency plan).
The page has inline CSS and no scripts. The colours and the font are the colours and the font of the draft board.
"""
import html
from datetime import date

from fantasyhoops.core.common import OUT as _OUT

OUT = _OUT / "adds"
PAGE = OUT / "adds_plan.html"
TITLE = "Weekly adds plan"
RANKING_ROWS = 12  # the teams in the ranking table
# The optional values of an Option: (attribute, column header, title of the header).
OPTION_VALUES = (
    ("projected_value", "Proj", "Projected value: Yahoo's projection for the next 7 days"),
    ("recent_value", "Recent", "Recent value: the averages of the last 14 days"),
    ("blended_value", "Blend", "Blended value: the projected line moved toward the recent line"),
)


def _e(text):
    return html.escape(str(text))


def _day(d):
    """For example "Tue 10/20"."""
    return f"{d:%a} {d.month}/{d.day}"


def _count(n, word):
    """For example "1 add" and "2 adds"."""
    return f"{n} {word}" + ("" if n == 1 else "s")


def _value(v):
    return "—" if v is None else f"{v:+.2f}"


def _player(p):
    status = f' <span class="status" title="{_e(p.status_name or p.status)}">{_e(p.status)}</span>' if p.status else ""
    return f"{_e(p.name)}{status}"


def _first_day(window, days):
    """The first day of a team window: its add day, or the first day of the plan for the window of a holder."""
    return window.add_day or days[0].date


def _stat(value, label, key=False):
    return f'<div class="stat{" key" if key else ""}"><b>{_e(value)}</b><span>{_e(label)}</span></div>'


def header(data, days, spots, plan, today):
    """The title, the fantasy week and the main numbers of the plan."""
    week, adds = data.week, data.adds
    lines = [f"<h1>{TITLE}</h1>"]
    if data.next_week:
        lines.append(f"<p>Today is the last day of week {week.number - 1}. This page plans the next week.</p>")
    window = f" Planning window: {_day(days[0].date)} to {_day(days[-1].date)}." if days else ""
    lines.append(f"<p>Week {week.number}: {_day(week.start)} to {_day(week.end)}.{window} "
                 f"Made on {_day(today)}.</p>")
    stats = [_stat(f"{adds.left} of {adds.limit}", "adds left"), _stat(len(spots), "stream spots")]
    if plan is not None:
        stats = [_stat(plan.started_games, "started games", key=True), _stat(plan.adds, "adds used"), *stats]
        blended = getattr(plan, "blended_value", None)
        if blended is not None:
            stats.append(_stat(f"{blended:+.1f}", "blended value"))
    lines.append(f'<div class="stats">{"".join(stats)}</div>')
    out = [p.name + (f" ({p.status})" if p.status else "") for p in data.roster if p.out]
    if out:
        lines.append(f'<p>Out (does not play): {_e(", ".join(out))}.</p>')
    return "\n".join(lines)


def warnings_section(warnings):
    """The warnings, for example the core warning. Nothing if there are none."""
    items = "".join(f"<li>{_e(w)}</li>" for w in warnings)
    return f'<section class="warning"><ul>{items}</ul></section>' if items else ""


def grid(plan, days, spots):
    """The grid of stream spots × days: the team of each window, the add days and the days with a started game."""
    if not days:
        return ""
    head = "".join(f'<th title="{d.nba_games} NBA games">{d.date:%a}<br><small>{d.date.month}/{d.date.day}</small></th>'
                   for d in days)
    open_row = "".join(f'<td class="{"open" if d.open else "full"}" title="{_e(", ".join(d.open) or "no open slots")}">'
                       f'{len(d.open)}</td>' for d in days)
    rows = [f'<tr class="slots"><th>Open</th>{open_row}</tr>']
    windows = plan.windows if plan is not None else ()
    for s in range(len(spots)):
        cells = []
        for d in days:
            here = [w for w in windows if w.spot == s and _first_day(w, days) <= d.date <= w.last_day]
            if not here:
                cells.append('<td class="empty">·</td>')
                continue
            w = here[0]
            cls = "on" if d.date in w.started else "hold"
            add = '<i title="Latest add day">+</i>' if d.date == w.add_day else ""
            cells.append(f'<td class="{cls}">{add}{_e(w.team)}</td>')
        rows.append(f"<tr><th>Spot {s + 1}</th>{''.join(cells)}</tr>")
    return (f'<section><h2>Stream spots by day</h2>\n<table class="grid"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>\n'
            '<p class="legend"><span class="key on">PHX</span> started game '
            '<span class="key hold">PHX</span> in the spot, no started game '
            '<span class="key">+</span> latest add day. Open: the open starting slots of the day.</p></section>')


def _columns(options):
    """The value columns that one option or more has: (attribute, header, title)."""
    cols = [c for c in OPTION_VALUES if any(getattr(o, c[0], None) is not None for o in options)]
    if any(getattr(o, "trend", None) is not None for o in options):
        cols.append(("trend", "Trend", "Adds across all Yahoo leagues, from Transaction Trends"))
    return cols


def options_table(window):
    """The window options of one team window, best first. The player of the plan has a mark."""
    if not window.options:
        return ""
    cols = _columns(window.options)
    head = "".join(f'<th title="{_e(title)}">{_e(name)}</th>' for _, name, title in cols)
    rows = []
    for n, o in enumerate(window.options, 1):
        values = "".join(f"<td>{_value(getattr(o, a)) if a != 'trend' else _e(o.trend)}</td>"
                         for a, _, _ in cols)
        pick = ' class="pick"' if o == window.player else ""
        rows.append(f'<tr{pick}><td>{n}</td><td class="name">{_player(o.player)}</td>'
                    f'<td>{_e(",".join(o.player.positions))}</td>{values}</tr>')
    return (f'<table class="options"><thead><tr><th>#</th><th class="name">Window options</th><th>Pos</th>{head}'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table>')


def window_card(window, days):
    """One team window: its spot, its team and days, its add day, its started games and its options."""
    first = _first_day(window, days)
    span = _day(first) if first == window.last_day else f"{_day(first)} – {_day(window.last_day)}"
    add = (f"Latest add day: <b>{_day(window.add_day)}</b>." if window.add_day
           else f"{_player(window.player.player)} holds the spot now. No add.")
    started = ", ".join(f"{d:%a}" for d in window.started) or "none"
    lines = [f'<article class="window"><h3>Spot {window.spot + 1} · {_e(window.team)} '
             f'<span class="span">{span}</span></h3>',
             f"<p>{add} {_count(len(window.started), 'started game')} ({started}).</p>"]
    drop = getattr(window, "drop", None)
    if drop:
        lines.append(f'<p class="drop">{_e(drop)}</p>')
    lines.append(options_table(window))
    lines.append("</article>")
    return "\n".join(lines)


def plan_section(plan, days, spots, adds, today, title="Schedule plan"):
    """A plan: one card for each team window. A short message if there is no plan."""
    if not spots:
        body = ("<p>No stream spots. All roster spots hold a player, and the planner does not drop players yet. "
                "There are no adds to plan.</p>")
    elif not adds.left:
        body = f"<p>No adds left this week ({adds.used} of {adds.limit} used). There are no adds to plan.</p>"
    elif plan is None:
        body = f"<p>{_count(len(spots), 'stream spot')}, but no open day. There are no adds to plan.</p>"
    elif not plan.windows:
        body = "<p>No free agent of the teams that the planner read gives a started game.</p>"
    else:
        body = (f"<p>{_count(plan.started_games, 'started game')} with {_count(plan.adds, 'add')}.</p>\n"
                + "\n".join(window_card(w, days) for w in plan.windows))
        if any(w.add_day == today for w in plan.windows):
            body += ("\n<p class=\"muted\">An add for today helps only if his game has not started. "
                     "The schedule has no game times.</p>")
    return f"<section><h2>{_e(title)}</h2>\n{body}</section>"


def comparison(plans):
    """The plans side by side: adds, started games and blended value. plans: (name, Plan). Needs two plans or more."""
    plans = [(name, p) for name, p in plans if p is not None]
    if len(plans) < 2:
        return ""
    rows = [("Adds", [p.adds for _, p in plans]), ("Started games", [p.started_games for _, p in plans])]
    blended = [getattr(p, "blended_value", None) for _, p in plans]
    if any(b is not None for b in blended):
        rows.append(("Blended value", [_value(b) for b in blended]))
    head = "".join(f"<th>{_e(name)}</th>" for name, _ in plans)
    body = "".join(f'<tr><th class="name">{label}</th>{"".join(f"<td>{_e(v)}</td>" for v in values)}</tr>'
                   for label, values in rows)
    return (f'<section><h2>Comparison</h2>\n<table class="compare"><thead><tr><th></th>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></section>")


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
            "<p>The planner finds the days with open starting slots. It ranks the NBA teams by the open days that "
            "they play on. Then it chooses free agents on those teams. The plan gets the most started games with "
            "the fewest adds.</p>\n"
            "<p>The value of a player is his value per game in the 6 categories that this league counts. "
            "A value below 0 is normal for a free agent.</p></details>")


def render(data, days, spots, plan, ranking=(), read=(), today=None, *, aggressive=None, warnings=(),
           contingencies=()):
    """The plan page as HTML text.

    data: the LeagueData of the run (week, adds, roster, next_week). days: the Days of the planning window.
    spots: the StreamSpots. plan: the schedule Plan, or None. ranking: the TeamRanks. read: the teams whose
    free agents the run read. aggressive: the aggressive Plan, or None. warnings and contingencies: text lines.
    """
    today = today or date.today()
    sections = [
        header(data, days, spots, plan, today),
        warnings_section(warnings),
        grid(plan, days, spots),
        comparison([("Schedule", plan), ("Aggressive", aggressive)]),
        plan_section(plan, days, spots, data.adds, today),
        plan_section(aggressive, days, spots, data.adds, today, "Aggressive plan") if aggressive is not None else "",
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
.grid { table-layout: fixed; border: 1px solid var(--line); font-size: 12px; }
.grid th, .grid td { text-align: center; padding: 4px 1px; }
.grid th:first-child { width: 17%; text-align: left; padding-left: 4px; }
.grid small { color: var(--muted); font-weight: 400; }
.grid td.on { background: color-mix(in srgb, var(--good) 35%, transparent); font-weight: 700; }
.grid td.hold { color: var(--muted); background: var(--head); }
.grid td.empty, .grid td.full { color: var(--muted); }
.grid td.open { color: var(--q); font-weight: 700; }
.grid tr.slots th, .grid tr.slots td { background: var(--head); }
.grid i { font-style: normal; color: var(--q); font-weight: 700; }
.legend { font-size: 12px; margin-top: 6px; }
.key { display: inline-block; padding: 0 4px; border-radius: 4px; font-weight: 700; color: var(--q); }
.key.on { background: color-mix(in srgb, var(--good) 35%, transparent); color: var(--fg); }
.key.hold { background: var(--head); color: var(--muted); font-weight: 400; }
.window { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin: 0 0 10px; }
.window .span { font-weight: 400; color: var(--muted); font-size: 13px; }
.window p { margin: 0 0 6px; }
.window p b { color: var(--fg); }
.drop { color: var(--fg); }
.options { font-size: 13px; }
.options tr.pick td { background: color-mix(in srgb, var(--q) 12%, var(--bg)); }
.options tr.pick td.name { font-weight: 600; }
.status { display: inline-block; padding: 0 4px; border-radius: 4px; background: var(--warn); color: #1c1917;
          font-size: 11px; font-weight: 700; }
.compare, .ranking { font-size: 13px; }
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
