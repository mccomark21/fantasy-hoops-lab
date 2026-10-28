"""The team plan section of the plan page (#140): one week grid, Mon to Sun, with the rows Games, Add 1 and Add 2.

The design is in docs/adds/README.md, "The team plan". The owner approved the C3 heat sample on 2026-10-28.
plan_section() makes the HTML from a PlanningRun (adds/plan.py) and its week_file.WeekRecord:
- The day headers show the days of the fantasy week. The games of each day shade its column: more games, a deeper
  mark tint (0% to 40%). A key under the grid shows the scale.
- Each add sits in the column of its add day: "+<slots> <teams>". With [adds] team_count_at teams or more, the cell
  gives the count. A band continues in the same row through each later day that the new player holds the spot. A
  filled square on the band marks a day that he starts.
- A past day is muted. Its add cells show the last saved recommendation, in a dashed cell. It has no button.
- An add cell and a day header of a day that is not past are buttons. The script of the page (page.SCRIPT) sets the
  filters of the free-agent table from their data attributes: data-days (the indexes of the days of the table),
  data-pos (the slots, empty for Util) and data-teams.
add_text() gives the line of one add for the terminal summary. The module writes no files.
"""

import html

from fantasyhoops.adds.team_plan import UTIL

TEAM_COUNT_AT = 6  # [adds] team_count_at if config.toml does not set it: from this number of teams, a cell gives a count
ADD_ROWS = 2  # the add rows of the grid, at least
HEAT = 40  # the tint of the day with the most games, in percent of mark


def _e(text):
    return html.escape(str(text))


def _words(words, last="and"):
    """For example "Mon, Tue and Wed"."""
    words = list(words)
    return f" {last} ".join(filter(None, [", ".join(words[:-1]), words[-1]])) if words else ""


def _days(days):
    """For example "Thu & Sat"."""
    names = [f"{d:%a}" for d in days]
    return " & ".join(filter(None, [", ".join(names[:-1]), names[-1]])) if names else ""


def team_count_at(cfg):
    """[adds] team_count_at of cfg, or TEAM_COUNT_AT."""
    return cfg.get("adds", {}).get("team_count_at", TEAM_COUNT_AT)


def slot_text(slots):
    """For example "SG/PF", or "Util" for any position."""
    return "/".join(slots)


def teams_text(teams, count_at):
    """For example "ATL CLE", or "8 teams" with count_at teams or more."""
    return f"{len(teams)} teams" if len(teams) >= count_at else " ".join(teams)


def add_text(add, count_at):
    """The terminal line of one SavedAdd, for example "Add 1, Thu 10/29: +SG/PF ATL CLE. Starts Thu & Sat.\""""
    return (
        f"Add {add.row}, {add.day:%a} {add.day.month}/{add.day.day}: +{slot_text(add.slots)} "
        f"{teams_text(add.teams, count_at)}. Starts {_days(add.starts)}."
    )


def _said_slots(slots):
    return "any position" if slots == (UTIL,) else _words(slots, "or")


def _said_teams(teams, count_at):
    return f"{len(teams)} teams: {', '.join(teams)}" if len(teams) >= count_at else _words(teams, "or")


def _who(teams, count_at):
    if len(teams) >= count_at:
        return f'<span class="n">{len(teams)} teams</span>'
    return "".join(f"<span>{_e(t)}</span>" for t in teams)


def _slots_html(slots):
    return "/<wbr>".join(_e(s) for s in slots)


def _add_cell(add, heat, index, count_at, interactive):
    """The cell of a current add: a button that sets the filters of the free-agent table."""
    said = (
        f"Add {add.row}, {add.day:%a}: add {_said_slots(add.slots)} from {_said_teams(add.teams, count_at)}. "
        f"Starts {_days(add.starts)}."
    )
    inner = f"<b>+{_slots_html(add.slots)}</b><span class=\"who\">{_who(add.teams, count_at)}</span>"
    if not interactive:
        return f'<td class="add" style="--h: {heat}%"><span class="addc" role="img" aria-label="{_e(said)}">{inner}</span></td>'
    days = ",".join(str(index[d]) for d in add.starts if d in index)
    pos = "" if add.slots == (UTIL,) else ",".join(add.slots)
    source = f"Add {add.row}, {add.day:%a}: +{slot_text(add.slots)} {teams_text(add.teams, count_at)}"
    return (
        f'<td class="add" style="--h: {heat}%"><button type="button" class="addc" data-days="{days}" '
        f'data-pos="{_e(pos)}" data-teams="{_e(",".join(add.teams))}" data-from="{_e(source)}" '
        f'aria-label="{_e(said + " Show these free agents.")}" title="{_e(f"Starts {_days(add.starts)}.")}">'
        f"{inner}</button></td>"
    )


def _past_cell(add, count_at):
    """The cell of a past add: a dashed muted box with no button."""
    said = f"Recommended for {add.day:%a}: add {_said_slots(add.slots)} from {_said_teams(add.teams, count_at)}. Past."
    return (
        f'<td class="add past"><span class="addc was" role="img" aria-label="{_e(said)}">'
        f'<b>+{_slots_html(add.slots)}</b><span class="who">{_who(add.teams, count_at)}</span></span></td>'
    )


def _band_cell(add, day, past, heat):
    """A day after the add day that the new player of add holds the spot: a band, and a square if he starts."""
    start = day in add.starts
    mark = '<span class="mk" aria-hidden="true"></span>' if start else ""
    said = f"{day:%a}: holds the spot, {'starts' if start else 'no start'}"
    style = "" if past else f' style="--h: {heat}%"'
    return (
        f'<td class="band{" past" if past else ""}"{style}><span class="bar{" on" if start else ""}" role="img" '
        f'aria-label="{_e(said)}">{mark}</span></td>'
    )


def _head(day, past, heat, index, interactive):
    inner = (
        f'<b><span class="long">{day:%a}</span><span class="short">{f"{day:%a}"[0]}</span></b>'
        f'<small><span class="long">{day.month}/{day.day}</span><span class="short">{day.day}</span></small>'
    )
    label = f"{day:%a} {day.month}/{day.day}"
    if past:
        return f'<th scope="col" class="past" aria-label="{label}, past">{inner}</th>'
    if not interactive or day not in index:
        return f'<th scope="col" class="plain" style="--h: {heat}%" aria-label="{label}">{inner}</th>'
    return (
        f'<th scope="col" style="--h: {heat}%"><button type="button" class="dayc" data-days="{index[day]}" '
        f'data-pos="" data-teams="" data-from="{_e(label)}" aria-label="Show free agents who play {label}">'
        f"{inner}</button></th>"
    )


def _messages(run):
    """The reason for a plan with no add, or nothing."""
    adds = run.data.adds
    if not run.spots:
        return "No stream spots. All roster spots hold a player, and [adds] stream_spots is 0. There are no adds to plan."
    if not adds.left:
        return f"No adds left this week ({adds.used} of {adds.limit} used). There are no adds to plan."
    if not run.days:
        return "The fantasy week is over. There are no days to plan."
    if run.plan is None or not run.plan.adds:
        return "No NBA team gives a started game in an open slot."
    return ""


def plan_section(run, interactive=True):
    """The team plan of a PlanningRun as HTML: the lede, the week grid, the keys and the legend.

    run.data.week gives the days of the grid, run.today the past days, run.week_games the NBA games of each day,
    run.days the days of the free-agent table, run.record the saved adds (the past adds and the adds of this run) and
    [adds] team_count_at of run.cfg the count rule. interactive: the page has a free-agent table, so the add cells and
    the day headers are buttons.
    """
    week, today = list(run.data.week.days), run.today
    count_at = team_count_at(run.cfg)
    games = run.week_games or {}
    most = max([games.get(d, 0) for d in week] + [1])
    heat = {d: round(games.get(d, 0) / most * HEAT) for d in week}
    index = {d.date: i for i, d in enumerate(run.days)}
    record = run.record
    adds = list(record.adds) if record else []
    head = ['<th scope="col"><span class="vh">Row</span></th>']
    head += [_head(d, d < today, heat[d], index, interactive) for d in week]
    games_row = ['<th scope="row">Games</th>'] + [
        f'<td class="past">{games.get(d, 0)}</td>' if d < today else f'<td style="--h: {heat[d]}%">{games.get(d, 0)}</td>'
        for d in week
    ]
    body = [f'<tr class="games">{"".join(games_row)}</tr>']
    rows = max([ADD_ROWS] + [a.row for a in adds])
    for r in range(1, rows + 1):
        chain = sorted((a for a in adds if a.row == r), key=lambda a: a.day)
        owner = {}
        for k, a in enumerate(chain):
            end = chain[k + 1].day if k + 1 < len(chain) else None
            for d in week:
                if d >= a.day and (end is None or d < end):
                    owner[d] = a
        current = sum(a.day >= today for a in chain)
        small = f"<small>{current} add{'' if current == 1 else 's'}</small>" if current else ""
        cells = [f'<th scope="row">Add {r}{small}</th>']
        for d in week:
            a, past = owner.get(d), d < today
            if a and a.day == d:
                cells.append(_past_cell(a, count_at) if past else _add_cell(a, heat[d], index, count_at, interactive))
            elif a:
                cells.append(_band_cell(a, d, past, heat[d]))
            else:
                cells.append('<td class="past"></td>' if past else f'<td style="--h: {heat[d]}%"></td>')
        body.append(f'<tr class="add">{"".join(cells)}</tr>')
    current = [a for a in adds if a.day >= today]
    lines = []
    left = run.data.adds.left
    if current:
        tap = " Tap an add to see the free agents who fit it." if interactive else ""
        lines.append(f'<p class="tp-lede">The plan uses <b>{len(current)} of the {left} adds</b> that are left.{tap}</p>')
    message = _messages(run)
    if message:
        lines.append(f'<p class="tp-lede">{_e(message)}</p>')
    notes = []
    runs = set(record.runs) if record else set()
    missing = [d for d in week if d < today and d not in runs]
    if missing:
        notes.append(f"No saved plan for {_words(f'{d:%a}' for d in missing)}.")
    if any(a.day == today for a in current):
        notes.append("An add for today helps only if his game has not started.")
    for a in adds:
        if a.mixed:
            notes.append(
                f"The teams of add {a.row} on {a.day:%a} play on different days. Its squares mark the days that all "
                "of them play."
            )
    note = "".join(f'<p class="muted tp-note">{_e(n)}</p>' for n in notes)
    key = (
        '<p class="heatkey">Fewer <i style="--h: 8%"></i><i style="--h: 22%"></i><i style="--h: 40%"></i> '
        "more NBA games</p>"
        '<p class="heatkey spankey"><span class="kbar"><span class="kmk"></span></span> holds the spot and starts'
        '<span class="kbar"></span> holds the spot, no start</p>'
    )
    legend = (
        '<details class="notes" id="plan-notes"><summary>How to read the plan</summary>\n'
        '<p class="legend">Games: the NBA games of the day. A deeper shade: more games. An add sits on its add day: '
        "the slots that the new player can fill, then the NBA teams that fit equally. With "
        f"{count_at} teams or more, the cell gives the count. Util: any position. A later add in a row drops the "
        "player of the earlier add. A band after an add shows the days that the new player holds the spot, up to the "
        "next add in the row or Sunday. A square on the band marks a day that he starts: his team plays, and an open "
        "slot takes him. Each add also starts on its add day. A click on an add or a day sets the filters of the "
        "free-agent table. A past day is muted. A dashed cell shows the add that the last run on or before that day "
        "recommended for it.</p></details>"
    )
    return "\n".join(
        [
            '<section id="plan"><h2>Team plan</h2>',
            *lines,
            '<table class="week"><colgroup><col class="lab">' + "<col>" * len(week) + "</colgroup>"
            f'<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body)}</tbody></table>',
            key + note,
            legend,
            "</section>",
        ]
    )


CSS = """
/* The team plan (#140): the C3 heat week grid. The games of the day shade the whole column (--h). */
.tp-lede { color: var(--fg); font-size: 14px; margin: 0 0 10px; }
.tp-lede b { font-weight: 800; }
.tp-note { font-size: 12px; margin: 4px 0 0; }
.week { table-layout: fixed; font-size: 13px; }
.week th, .week td { text-align: center; padding: 0; border-bottom: 1px solid var(--line); vertical-align: top; }
.week col.lab { width: 64px; }
.week thead th { padding: 0 0 2px; border-bottom: 0; font-size: 13px; }
.week thead th:first-child { text-align: left; vertical-align: bottom; }
.week thead b { display: block; font-size: 15px; font-weight: 900; font-stretch: 75%; text-transform: uppercase;
                line-height: 1; }
.week thead small { display: block; margin-top: 3px; font-size: 11px; color: var(--fg); font-weight: 400; }
.week thead .short { display: none; }
.week thead th.past, .week thead th.plain { padding: 4px 0 6px; }
.week thead button { font: inherit; color: var(--fg); background: none; border: 0; cursor: pointer; width: 100%;
                     min-height: 40px; padding: 4px 0; }
.week thead button:hover b { text-decoration: underline; text-underline-offset: 3px; }
.week thead button:focus-visible { outline: 2px solid var(--fg); outline-offset: -2px; }
.week thead button[aria-current="true"], .week thead button[aria-current="true"]:hover { color: var(--bg);
  background: var(--q); }
.week thead button[aria-current="true"] small { color: var(--bg); }
.week thead button[aria-current="true"]:focus-visible { outline-color: var(--fg); outline-offset: 1px; }
.week tbody th { text-align: left; padding: 8px 4px 8px 0; font-size: 12px; font-weight: 800; }
.week td { padding: 8px 2px; }
.week tbody tr > * { background: transparent; }
.week td, .week thead th + th { background: color-mix(in srgb, var(--q) var(--h, 0%), var(--bg)); }
.week tbody tr > td { background: color-mix(in srgb, var(--q) var(--h, 0%), var(--bg)); }
.week tbody tr > td.past, .week thead th.past { background: color-mix(in srgb, var(--muted) 10%, var(--bg));
  color: var(--muted); }
.week thead th.past small { color: var(--muted); }
.week td + td, .week th + th { border-left: 2px solid var(--bg); }
.week tr.games td { font-size: 15px; font-weight: 800; font-variant-numeric: tabular-nums; }
.week tr.games td.past { font-weight: 500; }
.week tr.games td, .week tr.games th { border-bottom: 2px solid var(--fg); }
.week tr.add td { padding: 3px 2px; height: auto; }
.week tr.add th small { display: block; color: var(--muted); font-weight: 600; font-size: 11px; }
.addc { display: flex; flex-direction: column; align-items: center; gap: 2px; width: 100%; height: auto;
        min-height: 58px; min-width: 0; max-width: 100%; padding: 6px 2px; font: inherit; color: var(--fg);
        background: var(--bg); border: 1.5px solid var(--fg); border-top-width: 3px; }
button.addc { cursor: pointer; }
.addc b { font-size: 15px; font-weight: 900; font-stretch: 75%; line-height: 1; overflow-wrap: anywhere; }
.addc .who { display: flex; flex-direction: column; max-width: 100%; font-size: 12px; font-weight: 700;
             line-height: 1.2; }
.addc .who span { overflow-wrap: anywhere; }
button.addc .who { color: var(--q); text-decoration: underline; text-underline-offset: 2px; }
/* The states of an add cell. Each state sets the text color and the background together, so each pair has 4.5:1
   or more in both themes. Hover: the zebra ground. Selected (the cell that set the filters): stock on a solid mark
   block, also on hover. Focus: a 2px ink outline. */
button.addc:hover { color: var(--fg); background: var(--zebra); }
button.addc:hover .who { color: var(--q); text-decoration-thickness: 2px; }
button.addc[aria-current="true"], button.addc[aria-current="true"]:hover { color: var(--bg); background: var(--q);
  border-color: var(--q); }
button.addc[aria-current="true"] .who { color: var(--bg); }
button.addc:focus-visible { outline: 2px solid var(--fg); outline-offset: 2px; }
.addc.was { color: var(--muted); background: var(--bg); border: 1.5px dashed var(--lamp-off); border-top-width: 3px; }
.addc.was b { font-weight: 800; }
.addc.was .who { font-weight: 600; }
/* The span of an add: a band through each later day that the new player holds the spot. A filled square on the band
   marks a start. */
.week td.band { position: relative; padding: 0; vertical-align: middle; }
.week td.band .bar { position: relative; display: block; height: 58px; }
.week td.band .bar::before { content: ""; position: absolute; left: -2px; right: 0; top: 50%; height: 6px;
  margin-top: -3px; background: var(--fg); }
.week td.band .mk { position: absolute; left: 50%; top: 50%; width: 18px; height: 18px; margin: -9px 0 0 -9px;
  background: var(--fg); outline: 2px solid var(--bg); }
.week td.band.past .bar::before { background: var(--muted); }
.week td.band.past .mk { background: var(--muted); width: 14px; height: 14px; margin: -7px 0 0 -7px; }
.heatkey { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); margin: 6px 0 0; }
.heatkey i { display: inline-block; width: 18px; height: 12px;
             background: color-mix(in srgb, var(--q) var(--h, 0%), var(--bg)); }
.spankey { gap: 6px 10px; flex-wrap: wrap; }
.spankey .kbar { position: relative; display: inline-block; width: 30px; height: 14px; }
.spankey .kbar::before { content: ""; position: absolute; left: 0; right: 0; top: 4px; height: 6px;
  background: var(--fg); }
.spankey .kmk { position: absolute; left: 9px; top: -1px; width: 14px; height: 14px; background: var(--fg);
                outline: 2px solid var(--bg); }
.from { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; font-size: 13px; color: var(--fg);
        border: 1.5px solid var(--q); padding: 5px 10px; margin: 0 0 8px; }
.from[hidden] { display: none; }
.from a { font-weight: 700; }
#fa, #plan { scroll-margin-top: 8px; }
@media (max-width: 899px) { #fa, #plan { scroll-margin-top: 56px; } }
#team-chips button.chip { font-size: 12px; padding: 3px 6px; min-height: 28px; }
@media (max-width: 599px) {
  .week col.lab { width: 44px; }
  .week { font-size: 12px; }
  .week thead .long { display: none; }
  .week thead .short { display: inline; }
  .week thead b { font-size: 14px; }
  .week tbody th { font-size: 11px; }
  .week tr.add th small { display: none; }
  .week tr.games td { font-size: 14px; }
  .addc { padding: 5px 1px; }
  .addc b { font-size: 13px; }
  .addc .who { font-size: 11px; }
  .week td.band .mk { width: 14px; height: 14px; margin: -7px 0 0 -7px; }
}
"""
