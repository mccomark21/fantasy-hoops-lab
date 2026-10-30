"""The plan page and the Free agents page: two HTML files in output/adds/ for use on a phone. The design is in
docs/adds/README.md.

render() makes the plan page and render_free_agents() makes the Free agents page (#165), from one PlanningRun
(adds/plan.py). Each section of a page comes from one small function. A section shows only the parts that exist.
The plan page (output/adds/adds_plan.html, published at /adds/) has these main sections:
- Team plan: the week grid of adds/grid.py (#140). It shows the adds of the team plan (adds/team_plan.py) and the
  saved adds of the past days (adds/week_file.py). A click on an add or a day opens the Free agents page with the
  filters of the add or the day in the URL.
- Matchup: the category scores of the current matchup and the weight of each category (adds/matchup.py).
- Run time: see below.
An old link to the Free agents section of the plan page (adds/#fa or adds/#waivers) forwards to the Free agents page.
The Free agents page (output/adds/free_agents.html, published at /free-agents/) has these sections:
- Free agents: a table with filters for days, positions and teams. The page holds its data as JSON, and one inline
  script fills the table. The script reads the filters of a plan link from the URL.
  The values are market values: the value above a replacement free agent (adds/value.py).
  Each player has a role line from the rotation log: minutes, starts and closes (adds/roles.py), with the
  starter flag and the closer flag (core/role_flags.py).
  A mark such as "Mon open" names each of the first days of next week on which he plays and fills an open slot (#76).
- Waiver players: the waiver players (W) with their clear days.
- Role up: the absent starters and the free agents at their positions (adds/role_up.py).
The Free agents table and the Waiver players table have the look of the Roster table of the Roster page (#143): a
team band, the player cell, and the head and row style of publish.TABLE_STYLE, the one source of the table CSS.
A small "2" marks each game on the second night of a back-to-back (adds/rest.py), in the free-agent table.
The Run time table shows the time of each step of the run (adds/timing.py, #85), with the sub-steps of the Yahoo
reads and their Yahoo pages below the Yahoo reads row (#89). The Run time section also holds the lines about the run:
the market read, the pages from the cache and the skip of the recent view (#118).
The page has inline CSS and no files from other sites. The colors and the font come from core/tokens.py, and the site
menu comes from core/publish.py (#117). publish.shell() gives the head, the menu and the menu script (#132).
write() and write_free_agents() use publish.write_page(), which also writes the font file to fonts/ next to the page.
"""

import html
import json
from dataclasses import replace
from datetime import date, timedelta

from fantasyhoops.adds import grid
from fantasyhoops.adds.planner import waiver_options
from fantasyhoops.adds.readers import STAT_COLUMNS
from fantasyhoops.adds.value import REPLACEMENT_RANK, market_value
from fantasyhoops.core import publish as site
from fantasyhoops.core import common

TITLE = "Weekly adds plan"
FA_TITLE = "Free agents"  # the title of the Free agents page (#165)
PLAN_LINK = "../adds/#plan"  # the team plan, from the Free agents page
RANKING_ROWS = 12  # the teams in the ranking table
FREE_AGENT_ROWS = 10  # the rows of the free-agent table: the best players for the filters
FLAG = 1.5  # the market value from which a free agent gets the "FA?" mark
POSITIONS = ("PG", "SG", "SF", "PF", "C")  # the position filters
B2B = '<sup class="b2b" title="second game of a back-to-back">2</sup>'  # the mark of a second night


def _e(text):
    return html.escape(str(text))


def _day(d):
    """For example "Tue 10/20"."""
    return f"{d:%a} {d.month}/{d.day}"


def _status(p):
    """The status tags after the name of a player: his status (for example O), and W for a waiver player."""
    status = f' <span class="status" title="{_e(p.status_name or p.status)}">{_e(p.status)}</span>' if p.status else ""
    if p.on_waivers:
        status += f' <span class="status" title="Waiver claim, not sure. Clears {_day(p.clear_day)}.">W</span>'
    return status


CLAIM_NOTE = (
    "W: a waiver claim. It is not sure: a team with a higher waiver priority can claim him first. A claim uses an add."
)


def _stat(value, label):
    return f'<div class="stat"><b>{_e(value)}</b><span>{_e(label)}</span></div>'


def header(data, days, spots, today):
    """The title, the fantasy week, the adds left, the stream spots and the players who are out."""
    week, adds = data.week, data.adds
    lines = [f"<h1>{TITLE}</h1>"]
    if data.next_week:
        lines.append(f"<p>Today is the last day of week {week.number - 1}. This page plans the next week.</p>")
    window = f" Planning window: {_day(days[0].date)} to {_day(days[-1].date)}." if days else ""
    lines.append(f"<p>Week {week.number}: {_day(week.start)} to {_day(week.end)}.{window} Made on {_day(today)}.</p>")
    stats = [_stat(f"{adds.left} of {adds.limit}", "adds left"), _stat(len(spots), "stream spots")]
    lines.append(f'<div class="stats">{"".join(stats)}</div>')
    out = [p.name + (f" ({p.status})" if p.status else "") for p in data.roster if p.out]
    if out:
        lines.append(f"<p>Out (does not play): {_e(', '.join(out))}.</p>")
    return "\n".join(lines)


def warnings_section(warnings):
    """The warnings, for example the core warning. Nothing if there are none."""
    items = "".join(f"<li>{_e(w)}</li>" for w in warnings)
    return f'<section class="warning"><ul>{items}</ul></section>' if items else ""


def margin_class(margin, weight, min_weight):
    """The class of a Margin cell (#144): "" for a close margin (weight 1), "lead" or "trail" for a lead or a
    deficit outside the close margin, and " big" after it for a large margin (weight min_weight or less).

    The weight comes from the margin (matchup.category_weight()), so the weight tells if the margin is close or large.
    """
    if weight >= 1.0 or margin == 0:
        return ""
    side = "lead" if margin > 0 else "trail"
    return f"{side} big" if weight <= min_weight else side


def weight_class(weight, min_weight):
    """The class of a Weight cell (#144): "w0" for weight 1 (bold ink), then "w1", "w2" and "w3" in 3 equal steps
    from 1 down to min_weight. Each step is closer to the muted text color.
    """
    if weight >= 1.0:
        return "w0"
    step = (1.0 - min_weight) / 3
    return "w1" if weight > 1.0 - step else "w2" if weight > 1.0 - 2 * step else "w3"


# The key under the matchup table. Each sample has the look of a real cell.
MATCHUP_KEY = (
    '<p class="key" id="mu-key">'
    '<span>Margin: <span class="lead">+12</span> a lead</span>'
    '<span><span class="trail">-12</span> a deficit</span>'
    "<span>+2 close</span>"
    '<span><span class="lead big">+30</span> bold: a large margin</span>'
    '<span>Weight: <span class="w0">1.00</span> full, a lighter weight counts less</span></p>'
)


def matchup_section(matchup, weights, min_weight=0.5):
    """The score of each category in the current matchup, the margin and the matchup weight.

    One column for each category, and the rows You, Opp, Margin and Weight (#144). The Margin cells and the Weight
    cells get the classes of margin_class() and weight_class(). matchup: a matchup.Matchup, or None if the planner
    did not find the scores. weights: {category: weight}. min_weight: [adds.matchup] min_weight.
    Nothing if weights is None (the run read no free agents).
    """
    if weights is None:
        return ""
    title = "<h2>Matchup</h2>"
    note = (
        '<p class="legend">Weight: the matchup weight of the category. A close category keeps weight 1. '
        "A large lead or deficit lowers the weight. Match in the free-agent table uses these weights.</p>"
    )
    if matchup is None:
        return (
            f"<section>{title}\n<p>The planner did not find the category scores on the matchup page. "
            "All weights are 1.</p></section>"
        )
    names = {key: name for name, key in STAT_COLUMNS.items()}
    cats = list(weights)

    def row(label, cells):
        return f'<tr><th scope="row" class="name">{label}</th>{"".join(cells)}</tr>'

    def cell(text, cls):
        return f'<td class="{cls}">{text}</td>' if cls else f"<td>{text}</td>"

    margins = [matchup.margin(c) for c in cats]
    rows = [
        row("You", [f"<td>{matchup.mine.get(c, 0):g}</td>" for c in cats]),
        row("Opp", [f"<td>{matchup.theirs.get(c, 0):g}</td>" for c in cats]),
        row("Margin", [cell(f"{m:+g}", margin_class(m, weights[c], min_weight)) for c, m in zip(cats, margins)]),
        row("Weight", [cell(f"{weights[c]:.2f}", weight_class(weights[c], min_weight)) for c in cats]),
    ]
    head = "".join(f'<th scope="col">{_e(names.get(c, c))}</th>' for c in cats)
    # The page is public (ADR 2), so it does not show the name of the opponent.
    return (
        f'<section id="matchup">{title}\n<p>The category totals of your team and your opponent in this matchup.</p>\n'
        f'<table class="mu"><thead><tr><td class="name"></td>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>\n'
        f"{MATCHUP_KEY}\n{note}</section>"
    )


def role_text(role):
    """For example "Min 28.0 L5, 22.0 14d (+6.0) · Starts 3/4 (Regular) · Closes 1/2 (New)". None with no Role
    (adds/roles.py). The starter flag follows the starts and the closer flag follows the closes. No flag: no word."""
    if role is None:
        return None
    recent = "no games in 14d" if role.minutes_14d is None else f"{role.minutes_14d:.1f} 14d ({role.change:+.1f})"
    starter = f" ({role.starter})" if role.starter else ""
    closer = f" ({role.closer})" if role.closer else ""
    return (
        f"Min {role.minutes_last5:.1f} L5, {recent} · Starts {role.starts}/{role.games}{starter} · "
        f"Closes {role.closes}/{role.close_games}{closer}"
    )


def _fits(player, day, games):
    """True if his team plays on day (a Day) and one of the open slots takes one of his positions (Util takes all)."""
    return player.team in games.get(day.date, ()) and any(s in day.open for s in (*player.positions, "Util"))


def _open_label(d):
    """The next-week mark of a day, for example "Mon open"."""
    return f"{d:%a} open"


def free_agent_data(
    options, days, games, replacement, match_replacement=None, nights=None, roles=None, next_days=(), next_games=None
):
    """The data of the free-agent table: the days and one row for each option who plays, best value first.

    Each day has its date (for example "2027-01-07"), so that the script can match the days of a plan link (#165).

    A value is a market value: the value minus replacement. match: the matchup value minus match_replacement, the
    matchup value of a replacement free agent. plays: his team plays on the day. fits: he plays and
    one of the open slots of the day takes one of his positions (Util takes all positions). b2b: he plays on the
    second night of a back-to-back (nights, from rest.second_nights()).
    roles: {(name, team): Role} from adds/roles.py. role: the text of role_text(). rise: the minutes mark.
    band: the style of his team band (publish.band_style()).
    next_days: the Days of the first days of next week, from the core roster (slots.next_week_window()).
    next_games: {day: set of teams} of those days. next_open: the mark of each of these days that he fits.
    """
    nights = nights or {}
    roles = roles or {}
    next_games = next_games or {}

    def market(v, base=replacement):
        return None if v is None or base is None else round(v - base, 2)

    players = []
    for o in sorted((o for o in options if not o.player.out and o.value is not None), key=lambda o: -o.value):
        p = o.player
        plays = [p.team in games.get(d.date, ()) for d in days]
        fits = [_fits(p, d, games) for d in days]
        role = roles.get((p.name, p.team))
        players.append(
            {
                "name": p.name,
                "team": p.team,
                "pos": list(p.positions),
                "status": p.status,
                "value": market(o.value),
                "recent": market(o.recent_value),
                "match": market(o.match, match_replacement),
                "trend": o.trend.adds_today if o.trend else None,
                "plays": plays,
                "fits": fits,
                "b2b": [on and p.team in nights.get(d.date, ()) for on, d in zip(plays, days)],
                "role": role_text(role),
                "rise": bool(role and role.rise),
                "role_up": list(o.role_up),
                "band": site.band_style(p.team),
                "next_open": [_open_label(d.date) for d in next_days if _fits(p, d, next_games)],
            }
        )
    return {
        "days": [
            {
                "label": f"{d.date:%a}",
                "md": f"{d.date.month}/{d.date.day}",
                "date": d.date.isoformat(),
                "nba": d.nba_games,
                "open": len(d.open),
            }
            for d in days
        ],
        "players": players,
        "positions": list(POSITIONS),
        "flag": FLAG,
        "rows": FREE_AGENT_ROWS,
    }


def flag_legend(flags):
    """The legend of the starter flag and the closer flag. flags: [adds.flags] in config.toml. Nothing with None."""
    if not flags:
        return ""
    return (
        f" The word after Starts is the starter flag, from his last {flags['window_games']} games "
        f"({flags['min_games']} or more). The word after Closes is the closer flag, from the last "
        f"{flags['close_window']} close games of his team ({flags['min_close_games']} or more). A close game "
        f"that he did not play counts as not closed. New: he started each of his last {flags['new_games']} "
        f"games (closed each of the last {flags['new_closes']} close games), and fewer than half of the "
        f"earlier games in the window. Regular: {flags['regular_share']:.0%} or more. Inconsistent: "
        f"{flags['some_share']:.0%} or more. No word: less, or too few games."
    )


def role_legend(roles, minutes_rise, flags=None):
    """The legend of the role line under each player. Nothing with no roles (no rotation log)."""
    if not roles:
        return ""
    rise = (
        f' <span class="flag">MIN+</span> L5 is {minutes_rise:g} minutes or more above 14d.'
        if minutes_rise is not None
        else ""
    )
    rise += flag_legend(flags)
    return (
        '<p class="legend">Min: his mean minutes in his last 5 games (L5) and in the last 14 days (14d), with the '
        "change. Starts: his starts / his games in the last 14 days. Closes: his closes / the close games of his "
        "team in the last 14 days. A close: he is on the floor at the end of a close game. "
        f"The ESPN play-by-play gives these numbers.{rise} "
        "They do not change Val.</p>\n"
    )


def next_week_legend(next_days):
    """The legend of the next-week marks: one line for each day checked. Nothing with no days to check."""
    if not next_days:
        return ""
    lines = [
        f'<span class="flag next">{_open_label(d.date)}</span>: he has a game next {d.date:%A} '
        f"{d.date.month}/{d.date.day}, and your core players leave a slot open that he can fill "
        f"({len(d.open)} open slots)."
        if d.open
        else f"Next {d.date:%A} {d.date.month}/{d.date.day}: your core players fill all slots. No player gets a mark."
        for d in next_days
    ]
    return '<p class="legend">' + " ".join(lines) + " The mark changes no value and no plan.</p>\n"


SKIP_NOTE = (
    'Val uses the projection only in this run. The Run time section of the <a href="../adds/#run-time">Adds plan</a> '
    "page gives the reason."
)


def fa_key(roles, minutes_rise, next_days):
    """The one-line key of the dots and the flags, above the free-agent table (#118). MIN+ shows only with roles
    and minutes_rise. The next-week flag shows only if a day of next week has an open slot."""
    items = [
        '<span class="dot fit"></span> game, open slot',
        '<span class="dot game"></span> game, no open slot',
        f"{B2B} back-to-back",
        '<span class="flag">FA?</span> unusual value',
        '<span class="flag up">UP</span> role up',
    ]
    if roles and minutes_rise is not None:
        items.append('<span class="flag">MIN+</span> more minutes')
    early = next((d for d in next_days if d.open), None)
    if early:
        items.append(f'<span class="flag next">{_open_label(early.date)}</span> slot next week')
    spans = "".join(f"<span>{item}</span>" for item in items)
    return f'<p class="key" id="fa-key"><span class="vh">Key: </span>{spans}</p>\n'


def free_agents_section(run):
    """The free-agent table of a PlanningRun with its filters. A script fills the table from the data. Nothing
    with no options.

    The table holds only the players with status FA. The waiver players are in waivers_section().
    The role line of each player uses run.roles (adds/roles.py) and [adds] minutes_rise of run.cfg.
    [adds.flags] of run.cfg gives the legend of the starter flag and the closer flag.
    run.next_days and run.next_games: the first days of next week, for the next-week marks (see free_agent_data()).
    run.recent_skip: the line that says that the run skipped the recent view (lists.recent_skip_line(), #90). With a
    line, SKIP_NOTE shows above the table, and the full line shows in the Run time section (#118). None: no note.
    The key of the marks shows above the table. The long legends are in a <details> below the table (#118).
    The script shows a message with a "Clear days" button when no free agent matches the filters.
    """
    options = [o for o in run.options if not o.player.on_waivers]
    if not options or not run.days:
        return ""
    adds = run.cfg.get("adds", {})
    roles, minutes_rise, next_days = run.roles, adds.get("minutes_rise"), run.next_days
    data = free_agent_data(
        options,
        run.days,
        run.games,
        run.replacement,
        run.match_replacement,
        run.nights,
        roles,
        next_days,
        run.next_games,
    )
    data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    skip = f'<p class="skip" id="skip-note">{SKIP_NOTE}</p>\n' if run.recent_skip else ""
    return (
        '<section id="fa"><h2>Free agents</h2>\n'
        '<p class="from" id="fa-from" hidden><span id="fa-from-text"></span> '
        f'<a href="{PLAN_LINK}">Back to the team plan</a></p>\n'
        '<div class="filters" id="day-chips"></div>\n<div class="filters" id="pos-chips"></div>\n'
        '<div class="filters" id="team-chips"></div>\n'
        '<div class="tools"><label class="toggle"><input type="checkbox" id="fit-only" checked> Only games that fill '
        'an open slot</label>\n<button type="button" class="chip act" id="fa-reset">Reset filters</button></div>\n'
        f'{skip}{fa_key(roles, minutes_rise, next_days)}<p class="count" id="fa-count" aria-live="polite" tabindex="-1"></p>\n'
        '<div class="empty" id="fa-empty" hidden><p id="fa-empty-text"></p>'
        '<button type="button" class="chip act" id="fa-clear-days">Clear days</button></div>\n'
        '<table class="fa lab-t" id="fa-table"></table>\n'
        '<details class="notes" id="fa-notes"><summary>Columns and marks</summary>\n'
        '<p class="legend"><span class="dot fit"></span> game in an open slot that he can fill '
        f'<span class="dot game"></span> game, no open slot for him. {B2B} second game of a back-to-back. '
        "Val: blended value per game above a "
        f"replacement free agent (0 = the free agent at rank {REPLACEMENT_RANK} by value). Match: the same value "
        "with the matchup weights. A filter does not change Val or Match. Gms: his games on the selected days. "
        '<span class="flag">FA?</span> a value this high is unusual for a free agent. '
        '<span class="flag up">UP</span> role up: a starter at his position is absent.</p>\n'
        f"{role_legend(roles, minutes_rise, adds.get('flags'))}{next_week_legend(next_days)}</details>\n"
        f'<script type="application/json" id="fa-data">{data}</script>\n<script>{SCRIPT}</script></section>'
    )


def waivers_section(options, replacement):
    """The waiver players (W), best value first: the clear day, the first day that he can play and the market value.

    The table has the look of the Roster table (#143): the team band, then the player cell with the team and the
    positions.

    Nothing if no option is on waivers.
    """
    waivers = waiver_options(options)
    if not waivers:
        return ""

    def market(v):
        v = market_value(v, replacement)
        return "—" if v is None else f"{v:+.2f}"

    rows = "".join(
        f'<tr><td class="band" style="{site.band_style(o.player.team)}">{_e(o.player.team)}</td>'
        f'<th class="pl" scope="row"><b>{_e(o.player.name)}</b>{_status(o.player)}'
        f"<small>{_e(o.player.team)} · {_e('/'.join(o.player.positions))}</small></th>"
        f'<td class="s1">{_day(o.player.clear_day)}</td><td>{_day(o.player.clear_day + timedelta(days=1))}</td>'
        f'<td class="n s1">{market(o.value)}</td></tr>'
        for o in waivers
    )
    return (
        '<section id="waivers"><h2>Waiver players</h2>\n'
        '<table class="wv lab-t" id="wv-table"><caption class="vh">Waiver players, best value first</caption>'
        '<thead><tr><th scope="col" class="l">Team</th><th scope="col" class="l">Player</th>'
        '<th scope="col" class="s1">Clears</th><th scope="col">First day</th><th scope="col" class="s1">Val</th>'
        f"</tr></thead><tbody>{rows}</tbody></table>\n"
        '<p class="legend">First day: the first day that he can play for you, the day after he clears waivers. '
        f"Val: the same value as in the free-agent table. {CLAIM_NOTE}</p></section>"
    )


def role_up_section(options):
    """One line for each absent starter who marks a free agent: the free agents at his positions. Nothing if none."""
    marked = {}
    for o in options:
        if not o.player.out:
            for name in o.role_up:
                marked.setdefault(name, []).append(o.player)
    if not marked:
        return ""
    items = "".join(
        f"<li>{_e(name)} is absent. Role up: {_e(', '.join(f'{p.name} ({p.team})' for p in players))}.</li>"
        for name, players in marked.items()
    )
    return (
        f'<section id="role-up"><h2>Role up</h2>\n<ul>{items}</ul>\n'
        '<p class="legend">Absent: he started most of his recent games, then missed the last games of his team. '
        "His backups can get more minutes. Their recent line does not show the new role yet. The mark changes "
        "no value.</p></section>"
    )


def timings_section(timings, market=None, cache=None, recent_skip=None):
    """The Run time section: the lines about the run, then a table with the seconds of each step of the run, the
    calls and the states of each search step, and the Yahoo pages of each step with sub-steps.

    timings: the timing.StepTimes of the run. A sub-step row follows the row of its step and shows only the
    sub-step name, indented. The page write has no row, because the run writes the page before that step ends.
    timings.csv has its row.
    market: the line of the market read (lists.market_line(), #92). cache: the line of the pages from the same-day
    cache (cache.PageCache.line(), #91). recent_skip: the line of the skip of the recent view
    (lists.recent_skip_line(), #90). Each line is None when it does not apply. Nothing with no timings and no lines.
    """

    def count(n):
        return "" if n is None else f"{n:,}"

    def name(s):
        if s.parent is None:
            return f'<td class="name">{_e(s.step)}</td>'
        return f'<td class="name sub">{_e(s.step.removeprefix(s.parent + ": "))}</td>'

    body = "".join(
        f"<tr>{name(s)}<td>{s.seconds:.2f}</td><td>{count(s.calls)}</td>"
        f"<td>{count(s.states)}</td><td>{count(s.pages)}</td></tr>"
        for s in timings
    )
    lines = "".join(
        f'<p class="legend" id="{key}">{_e(line)}</p>\n'
        for key, line in (("skip-read", recent_skip), ("market-read", market), ("cache-read", cache))
        if line
    )
    if not body:
        return f'<details class="notes" id="run-time"><summary>Run time</summary>\n{lines}</details>' if lines else ""
    return (
        f'<details class="notes" id="run-time"><summary>Run time</summary>\n{lines}'
        '<table class="ranking"><thead><tr><th class="name">Step</th><th>Seconds</th><th>Calls</th>'
        f"<th>States</th><th>Pages</th></tr></thead><tbody>{body}</tbody></table>\n"
        '<p class="muted">Calls: the calls of the plan search, cache hits included. States: the unique states '
        "that the search computed. A step with no search has no counts. Pages: the Yahoo pages that the step "
        "opened. The indented rows are the sub-steps of the Yahoo reads. Their seconds do not include the work "
        "between them or the browser close. The page write is not in the table. "
        "output/adds/timings.csv has all the steps.</p></details>"
    )


def ranking_section(ranking, read):
    """The NBA teams by the open days that they cover. A * marks the teams whose free agents the planner read."""
    if not ranking:
        return ""
    rows = "".join(
        f'<tr><td class="name">{"*" if r.team in read else ""}{_e(r.team)}</td><td>{len(r.open_days)}</td>'
        f'<td>{r.open_slots}</td><td class="name">{_e(" ".join(f"{d:%a}" for d in r.open_days))}</td></tr>'
        for r in ranking[:RANKING_ROWS]
    )
    more = (
        f'<p class="muted">{len(ranking) - RANKING_ROWS} more teams play on an open day.</p>'
        if len(ranking) > RANKING_ROWS
        else ""
    )
    return (
        '<details class="notes"><summary>NBA teams by open days</summary>\n'
        '<table class="ranking"><thead><tr><th class="name">Team</th><th>Days</th><th>Slots</th>'
        f'<th class="name">Open days</th></tr></thead><tbody>{rows}</tbody></table>\n'
        f'<p class="muted">* = the planner read the free agents of this team.</p>{more}</details>'
    )


def method_note():
    """A short note on the method for a reader who does not play in the league."""
    return (
        '<details class="notes"><summary>How the plan works</summary>\n'
        "<p>This is one team in a Yahoo fantasy basketball league. Each day, the team starts up to 6 players. "
        "A player scores only on a day when his NBA team plays and he is in a starting slot.</p>\n"
        "<p>The team keeps its core players all season. The other roster spots are stream spots. "
        "The league gives 5 adds each week, so the team can change the players in the stream spots.</p>\n"
        "<p>The planner finds the days with open starting slots. For each stream spot, it finds the NBA teams whose "
        "games fill the most open slots with the fewest adds. You pick the player in the free-agent table.</p>\n"
        "<p>The value of a player is his value per game in the 6 categories that this league counts, above a "
        f"replacement free agent: 0 is the value of the free agent at rank {REPLACEMENT_RANK}.</p></details>"
    )


def render(run):
    """The plan page of a PlanningRun (plan.py) as HTML text. The page uses these fields of run:

    data (week, adds, roster, next_week, matchup), days, games, spots, plan, record, week_games (the team plan,
    grid.plan_section()), options, ranking, read, today, replacement, match_replacement, warnings, weights (None: no
    matchup section), nights (the B2B marks), roles, next_days, next_games, timings (the Run time table) and the run
    lines recent_skip, market and cache (timings_section()).
    [adds] minutes_rise and [adds.flags] of run.cfg give the legends of the role marks.
    [league] teams of run.cfg gives the team count in the site menu.
    The Free agents, Waiver players and Role up sections are on the Free agents page (render_free_agents(), #165).
    The add cells and the day headers of the team plan link to that page when it has a free-agent table.
    """
    today = run.today or date.today()
    run = replace(run, today=today)
    min_weight = run.cfg.get("adds", {}).get("matchup", {}).get("min_weight", 0.5)
    sections = [
        header(run.data, run.days, run.spots, today),
        warnings_section(run.warnings),
        matchup_section(run.data.matchup, run.weights, min_weight),
        grid.plan_section(run, interactive=bool(free_agents_section(run))),
        ranking_section(run.ranking, run.read),
        timings_section(run.timings, run.market, run.cache, run.recent_skip),
        method_note(),
    ]
    return _page(TITLE, "adds", run.cfg, sections, FORWARD, PLAN_CSS)


def fa_header(run):
    """The title of the Free agents page, the fantasy week, the planning window and the day of the run."""
    week, days = run.data.week, run.days
    window = f" Planning window: {_day(days[0].date)} to {_day(days[-1].date)}." if days else ""
    return (
        f"<h1>{FA_TITLE}</h1>\n<p>Week {week.number}: {_day(week.start)} to {_day(week.end)}.{window} "
        f'Made on {_day(run.today)}. The <a href="{PLAN_LINK}">team plan</a> is on the Adds plan page.</p>'
    )


NO_FREE_AGENTS = "The planning run read no free agents and no waiver players. The team plan gives the reason."


def render_free_agents(run):
    """The Free agents page of a PlanningRun (#165) as HTML text: the free-agent table, the waiver players and the
    role-up marks. It uses the fields of run that free_agents_section(), waivers_section() and role_up_section() use.
    With none of the three sections, a line says that the run read no free agents.
    """
    today = run.today or date.today()
    run = replace(run, today=today)
    sections = [
        free_agents_section(run),
        waivers_section(run.options, run.replacement),
        role_up_section(run.options),
    ]
    if not any(sections):
        sections = [f'<p id="fa-none">{_e(NO_FREE_AGENTS)}</p>']
    return _page(FA_TITLE, "free-agents", run.cfg, [fa_header(run), *sections])


def _page(title, current, cfg, sections, forward="", css=""):
    """A page of the planner: the template HTML with the title, the site shell, the sections and the CSS of the page."""
    template = HTML.replace("__TITLE__", title).replace("__GRID_CSS__", grid.CSS.strip()).replace("__PAGE_CSS__", css)
    shell = site.shell(template.replace("__FORWARD__", forward), current, cfg)
    return shell.replace("__BODY__", "\n".join(s for s in sections if s))


# An old link to the Free agents section of the plan page (adds/#fa, adds/#waivers) opens the Free agents page.
FORWARD = (
    "<script>if (/^#(fa|waivers)$/.test(location.hash)) "
    'location.replace("../free-agents/" + location.search + location.hash);</script>'
)


# The CSS of the plan page only (#190). The Free agents page does not get it.
# 1. The shared chart style (core/chart.py, #185): the --lab-c-* sizes that the week grid and the matchup table use.
# 2. The heading rule of the DESIGN.md "Charts" panel head: 1px, not 2px.
PLAN_CSS = """__CHART_CSS__
h2 { border-bottom-width: var(--lab-c-sw-rule); }"""


def page_path():
    """The page file: output/adds/adds_plan.html, from common.OUT at the time of the call."""
    return common.OUT / "adds" / "adds_plan.html"


def free_agents_path():
    """The Free agents page file: output/adds/free_agents.html, from common.OUT at the time of the call."""
    return common.OUT / "adds" / "free_agents.html"


def write(text, path=None):
    """Write the page text to path (default: page_path()), and the font file to fonts/ next to it. Return the path."""
    return site.write_page(path or page_path(), text)


def write_free_agents(text, path=None):
    """Write the Free agents page text to path (default: free_agents_path()) and the font. Return the path."""
    return site.write_page(path or free_agents_path(), text)


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
__FORWARD__
__HEAD__
<style>
__TABLE_CSS__
/* Short names for the shared tokens of core/tokens.py. The page has no colors of its own. */
:root { --bg: var(--lab-stock); --fg: var(--lab-ink); --muted: var(--lab-mute); --line: var(--lab-rule);
        --bad: var(--lab-red); --good: var(--lab-green); --q: var(--mark); }
* { box-sizing: border-box; }
body { font: 400 14px/1.4 var(--lab-face); }
.sheet { max-width: 776px; padding: 24px max(28px, env(safe-area-inset-right)) 32px max(28px, env(safe-area-inset-left)); }
@media (max-width: 599px) {
  .sheet { padding: 16px max(16px, env(safe-area-inset-right)) 24px max(16px, env(safe-area-inset-left)); }
}
h1 { margin: 0 0 10px; padding-bottom: 10px; border-bottom: 3px solid var(--mark); color: var(--mark);
     font-weight: 900; font-stretch: 66%; font-size: clamp(30px, 4vw, 40px); line-height: .9;
     text-transform: uppercase; text-wrap: balance; }
h2 { margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--mark); font-weight: 900;
     font-stretch: 75%; font-size: 19px; line-height: 1.1; text-transform: uppercase; }
h3 { font-size: 15px; font-weight: 800; margin: 0 0 4px; }
p { margin: 0 0 8px; color: var(--muted); }
a { color: var(--q); text-underline-offset: 3px; }
.muted { color: var(--muted); }
.stats { display: flex; flex-wrap: wrap; gap: 8px 0; margin: 12px 0; }
.stat { display: flex; flex-direction: column-reverse; padding: 0 16px; border-left: 1px solid var(--line); }
.stat:first-child { padding-left: 0; border-left: 0; }
.stat b { font-size: 24px; font-weight: 900; font-stretch: 75%; line-height: 1.05; font-variant-numeric: tabular-nums; }
.stat span { font-size: 12px; color: var(--muted); }
.warning { border: 2px solid var(--bad); padding: 6px 12px; margin: 8px 0; }
.warning ul { margin: 0; padding-left: 18px; color: var(--bad); font-weight: 700; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 5px 4px; text-align: right; border-bottom: 1px solid var(--line); }
thead th { font-size: 11px; font-weight: 800; vertical-align: bottom; border-bottom: 2px solid var(--mark); }
tbody tr:nth-child(even) > * { background: var(--zebra); }
th.name, td.name { text-align: left; overflow-wrap: anywhere; }
td.name.sub { padding-left: 20px; color: var(--muted); }
i { font-style: normal; font-weight: 900; }
sup.b2b { font-size: 9px; font-weight: 800; color: var(--bad); margin-left: 1px; }
__GRID_CSS__
.legend { font-size: 12px; margin-top: 6px; max-width: 75ch; }
.skip { font-size: 13px; color: var(--fg); border: 1.5px solid var(--lamp-off); padding: 4px 8px; width: fit-content; }
.key { display: flex; flex-wrap: wrap; gap: 2px 14px; font-size: 12px; margin: 0 0 6px; }
.key > span { white-space: nowrap; }
.tools { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; margin: 0 0 8px; }
.tools label.toggle { margin: 0; }
.empty { border: 1.5px solid var(--lamp-off); padding: 10px 12px; margin: 0 0 8px; }
.empty p { color: var(--fg); font-weight: 700; }
.empty[hidden], .fa[hidden], .empty button[hidden] { display: none; }
.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
.filters .label { width: 100%; font-size: 12px; font-weight: 700; color: var(--muted); }
button.chip { font: inherit; font-size: 13px; font-weight: 700; padding: 4px 9px; border: 1.5px solid var(--lamp-off);
              border-radius: 0; background: var(--bg); color: var(--fg); cursor: pointer; line-height: 1.2;
              min-height: 28px; }
button.chip small { display: block; color: var(--muted); font-size: 11px; font-weight: 400; }
button.chip:hover { border-color: var(--fg); }
/* A day with no open slot: a dashed chip. This rule comes before the pressed rule, so that a pressed chip
   has stock text on the blue fill. */
button.chip.none { color: var(--muted); border-style: dashed; }
button.chip[aria-pressed="true"] { background: var(--q); border-color: var(--q); color: var(--bg); }
button.chip[aria-pressed="true"] small { color: var(--bg); }
button.chip.act { min-height: 32px; }
label.toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; margin: 0 0 8px; min-height: 28px;
               cursor: pointer; }
label.toggle input { width: 18px; height: 18px; margin: 0; accent-color: var(--q); }
.count { font-size: 12px; margin: 0 0 4px; }
/* The free-agent table and the waiver table (issue 143): publish.TABLE_STYLE gives the look of the Roster table.
   These rules add the sort buttons, the day columns and the role line. */
.fa, .wv { font-size: 13px; }
.fa td.band, .wv td.band { width: 44px; }
/* A long name wraps inside its cell. The name is an inline block, so that its glyph box stays inside the line. */
.fa th.pl, .wv th.pl { overflow-wrap: anywhere; }
.fa .pl b, .wv .pl b { display: inline-block; }
.lab-t .pl .status, .lab-t .pl .flag { vertical-align: 3px; margin-left: 2px; }
.fa th.pl small + small { font-size: 11px; }
.fa th.sort { white-space: nowrap; padding: 0; }
.fa th.sort button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; width: 100%;
                     min-height: 28px; padding: 0 6px 6px; display: flex; align-items: flex-end;
                     justify-content: flex-end; }
.fa th.sort[aria-sort] { box-shadow: inset 0 -3px var(--q); }
.fa th.day, .fa td.day { text-align: center; width: 26px; padding: 0 0 6px; }
.fa td.day { padding: 0; }
.fa th.day.sel { box-shadow: inset 0 -3px var(--q); }
.fa td.sel { background: color-mix(in srgb, var(--q) 12%, var(--bg)); }
.fa th.day small { display: block; color: var(--muted); font-weight: 400; font-size: 11px; }
.wv td { white-space: nowrap; }
/* Below 600px, the free-agent table has 4 number columns and up to 7 day columns next to the name. A smaller
   band and name keep a long name such as VALANCIUNAS on one line. */
@media (max-width: 599px) {
  .fa th.day, .fa td.day { width: 18px; }
  .fa td.n, .wv td { padding: 0 4px; }
  .fa th.sort button { padding: 0 4px 6px; }
  .fa td.band { width: 36px; font-size: 15px; }
  .fa th.pl { padding-left: 6px; }
  .fa .pl b { font-size: 15px; }
}
/* At 320px, the value cells and the sort buttons get less padding, so that a wide fallback font also fits. */
@media (max-width: 359px) {
  .fa td.n { padding: 0 2px; font-size: 13px; }
  .fa th.sort button { padding: 0 2px 6px; }
  .fa td.band { font-size: 13px; }
}
.dot { display: inline-block; width: 10px; height: 10px; vertical-align: -1px; }
.dot.fit { background: var(--fg); }
.dot.game { border: 1.5px solid var(--muted); }
.flag { display: inline-block; padding: 0 3px; border: 1.5px solid var(--fg); color: var(--fg);
        font-size: 11px; font-weight: 800; line-height: 1.25; }
.flag.next { background: var(--fg); color: var(--bg); }
.neg { color: var(--muted); }
.wide { display: none; }
@media (min-width: 600px) { .fa .wide { display: table-cell; } }
.status { display: inline-block; padding: 0 4px; background: var(--bad); color: var(--lab-on-red);
          font-size: 11px; font-weight: 800; line-height: 1.4; }
.ranking { font-size: 13px; }
/* The matchup table (issue 144): one column for each category. The fixed layout keeps the 6 columns inside 320px. */
.mu { font-size: 13px; table-layout: fixed; }
.mu .name { width: 62px; }
.mu th.name { font-size: 12px; font-weight: 800; }
.mu thead th { text-align: right; }
/* The chart audit (issue 190): no zebra rows and a 1px lab-rule under the head. */
.mu thead th, .mu thead td { border-bottom: var(--lab-c-sw-rule) solid var(--line); }
.mu tbody tr > * { background: transparent; }
.lead { color: var(--good); }
.trail { color: var(--bad); }
.big { font-weight: 800; }
.w0 { color: var(--fg); font-weight: 800; }
.w1 { color: var(--fg); }
.w2 { color: color-mix(in srgb, var(--fg) 50%, var(--muted)); }
.w3 { color: var(--muted); }
details.notes { margin: 16px 0 8px; color: var(--muted); }
details.notes summary { cursor: pointer; color: var(--fg); font-weight: 700; width: fit-content; padding: 4px 0;
                         min-height: 28px; }
:focus-visible { outline: 2px solid var(--q); outline-offset: 2px; }
.vh { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
      clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
details.notes p, details.notes table { margin: 6px 0 0; }
__PAGE_CSS__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main"><div class="sheet">
__BODY__
</div></main>
__SCRIPT__
</body>
</html>
"""

SCRIPT = r"""
const DATA = JSON.parse(document.getElementById("fa-data").textContent);
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const fmt = v => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2);
const B2B = '<sup class="b2b" title="second game of a back-to-back">2</sup>';
const state = {days: new Set(), pos: new Set(), teams: new Set(), fit: true, sort: "value"};
// The team filter (issue 140): a chip for each team of the free agents that the run read.
const TEAMS = [...new Set(DATA.players.map(p => p.team))].sort();
const hits = p => state.fit ? p.fits : p.plays;
const games = p => hits(p).filter((h, i) => h && (!state.days.size || state.days.has(i))).length;
const SORTS = {value: p => p.value, games: p => games(p) * 100 + p.value, recent: p => p.recent ?? -99,
  match: p => p.match ?? -99};
const SORT_NAMES = {value: "Val", match: "Match", recent: "Recent", games: "Gms"};
// A day chip has an aria-label such as "Tue 10/27, 5 open slots, 4 NBA games". The visible text stays short.
const chip = (label, sub, said, dim) => `<button type="button" class="chip${dim ? " none" : ""}" aria-pressed="false"`
  + `${said ? ` aria-label="${esc(`${label}, ${said}`)}"` : ""}>${esc(label)}${sub ? `<small>${esc(sub)}</small>` : ""}`
  + `</button>`;
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const DOT_FIT = '<span class="dot fit" role="img" aria-label="game in an open slot"></span>';
const DOT_GAME = '<span class="dot game" role="img" aria-label="game"></span>';

function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); render(); }

// The script makes the chips one time. render() changes only aria-pressed, so a chip keeps the focus after a press.
function chips() {
  $("day-chips").innerHTML = `<span class="label">Days (plays on all selected days)</span>` + DATA.days.map(d =>
    chip(`${d.label} ${d.md}`, `${d.open} open · ${d.nba} NBA`,
      `${plural(d.open, "open slot")}, ${plural(d.nba, "NBA game")}`, !d.open)).join("");
  $("pos-chips").innerHTML = `<span class="label">Positions (any)</span>`
    + DATA.positions.map(p => chip(p, "", "", false)).join("");
  $("team-chips").innerHTML = `<span class="label">Teams (any)</span>`
    + TEAMS.map(t => chip(t, "", "", false)).join("");
  $("day-chips").querySelectorAll("button").forEach((b, i) => b.onclick = () => toggle(state.days, i));
  $("team-chips").querySelectorAll("button").forEach((b, i) => b.onclick = () => toggle(state.teams, TEAMS[i]));
  $("pos-chips").querySelectorAll("button").forEach((b, i) => b.onclick = () => toggle(state.pos, DATA.positions[i]));
}

function pressed() {
  $("day-chips").querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-pressed", state.days.has(i)));
  $("pos-chips").querySelectorAll("button").forEach((b, i) =>
    b.setAttribute("aria-pressed", state.pos.has(DATA.positions[i])));
  $("team-chips").querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-pressed", state.teams.has(TEAMS[i])));
}

function render() {
  pressed();
  const rows = DATA.players.filter(p => [...state.days].every(i => hits(p)[i])
    && (!state.pos.size || p.pos.some(x => state.pos.has(x)))
    && (!state.teams.size || state.teams.has(p.team)))
    .sort((a, b) => SORTS[state.sort](b) - SORTS[state.sort](a));
  $("fa-count").textContent = rows.length
    ? `Top ${Math.min(DATA.rows, rows.length)} of ${rows.length} free agents that match the filters`
    : "0 free agents match the filters";
  if (state.teams.size) $("fa-count").textContent += ` (teams: ${[...state.teams].sort().join(", ")})`;
  // With no match, the table hides and a message shows. With selected days, the message has a Clear days button.
  $("fa-empty").hidden = rows.length > 0;
  $("fa-table").hidden = !rows.length;
  $("fa-empty-text").textContent = state.days.size
    ? "No free agent plays on all selected days." : "No free agent matches the filters.";
  $("fa-clear-days").hidden = !state.days.size;
  // Each sort header holds a button. The th of the sorted column has aria-sort and shows an arrow.
  const th = (key, cls) => `<th class="sort ${cls || ""}"${state.sort === key ? ' aria-sort="descending"' : ""}>`
    + `<button type="button" data-sort="${key}">${SORT_NAMES[key]}`
    + `${state.sort === key ? '<span aria-hidden="true"> ▼</span>' : ""}</button></th>`;
  const sel = i => state.days.has(i) ? " sel" : "";
  const head = DATA.days.map((d, i) => `<th scope="col" class="day${i ? "" : " s1"}${sel(i)}">${d.label.slice(0, 2)}<br><small>${d.open}</small></th>`).join("");
  const active = document.activeElement;
  const focus = active && active.dataset ? active.dataset.sort : undefined;
  $("fa-table").innerHTML = `<caption class="vh">Free agents, sorted by ${SORT_NAMES[state.sort]}, highest first`
    + `</caption><thead><tr><th scope="col" class="l">Team</th><th scope="col" class="l">Player</th>`
    + `${th("value", "s1")}${th("match")}${th("recent", "wide")}${th("games")}${head}</tr></thead><tbody>`
    + rows.slice(0, DATA.rows).map(p =>
      `<tr><td class="band" style="${esc(p.band)}">${esc(p.team)}</td>`
      + `<th class="pl" scope="row"><b>${esc(p.name)}</b>`
      + `${p.status ? ` <span class="status">${esc(p.status)}</span>` : ""}`
      + `${p.value >= DATA.flag ? ' <span class="flag">FA?</span>' : ""}`
      + `${p.rise ? ' <span class="flag">MIN+</span>' : ""}`
      + `${p.role_up.length ? ' <span class="flag up">UP</span>' : ""}`
      + p.next_open.map(m => ` <span class="flag next">${esc(m)}</span>`).join("")
      + `<small>${esc(p.team)} · ${esc(p.pos.join("/"))}${p.trend ? ` · ${p.trend} adds today` : ""}`
      + `${p.role_up.length ? ` · role up: ${esc(p.role_up.join(", "))} absent` : ""}</small>`
      + `${p.role ? `<small>${esc(p.role)}</small>` : ""}</th>`
      + `<td class="n s1${p.value < 0 ? " neg" : ""}">${fmt(p.value)}</td>`
      + `<td class="n${p.match < 0 ? " neg" : ""}">${fmt(p.match)}</td><td class="n wide">${fmt(p.recent)}</td>`
      + `<td class="n">${games(p)}</td>`
      + DATA.days.map((d, i) => `<td class="day${i ? "" : " s1"}${sel(i)}">${p.fits[i] ? DOT_FIT
        : p.plays[i] ? DOT_GAME : ""}${p.b2b[i] ? B2B : ""}</td>`).join("") + `</tr>`).join("")
      + `</tbody>`;
  $("fa-table").querySelectorAll("th.sort button").forEach(b => {
    b.onclick = () => { state.sort = b.dataset.sort; render(); };
    // render() makes a new table. The sort button that had the focus gets it again.
    if (focus && b.dataset.sort === focus) b.focus();
  });
}

$("fit-only").onchange = e => { state.fit = e.target.checked; render(); };
// Clear days hides itself, so the focus goes to the first day chip.
$("fa-clear-days").onclick = () => {
  state.days.clear(); render();
  const first = $("day-chips").querySelector("button");
  if (first) first.focus();
};
// Reset filters restores the defaults: no days, no positions, no teams, only games that fill an open slot, sort by Val.
// It also removes the filters of a plan link from the URL, so that a reload shows the defaults.
$("fa-reset").onclick = () => {
  state.days.clear(); state.pos.clear(); state.teams.clear(); state.fit = true; state.sort = "value";
  $("fit-only").checked = true; $("fa-from").hidden = true;
  try { if (location.search) history.replaceState(null, "", location.pathname + location.hash); } catch (e) {}
  render();
};
// The team plan of the Adds plan page (issues 140 and 165) links here with the filters in the URL: days (the dates,
// for example 2027-01-07), pos (the slots, empty for Util: any position), teams, and from (the text of the line).
// A date that is not a day of the table does not set a filter.
const list = s => (s || "").split(",").filter(Boolean);
function fromPlan() {
  const q = new URLSearchParams(location.search);
  if (!q.has("from")) return false;
  const dates = list(q.get("days"));
  state.days = new Set(DATA.days.map((d, i) => dates.includes(d.date) ? i : -1).filter(i => i >= 0));
  state.pos = new Set(list(q.get("pos")));
  state.teams = new Set(list(q.get("teams")));
  $("fa-from-text").textContent = `Filters from the team plan: ${q.get("from")}.`;
  $("fa-from").hidden = false;
  return true;
}
chips();
const linked = fromPlan();
render();
if (linked) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("fa").scrollIntoView({behavior: still ? "auto" : "smooth", block: "start"});
  $("fa-count").focus({preventScroll: true});
}
"""
