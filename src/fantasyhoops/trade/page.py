"""The trade page (#150): the suggested 1-for-1 trades, in the look that the owner picked on #149 (look 3).

The page has a header (the trade deadline, your playoff starts and the time of the run), the line of the offered
players with a reason line for each offered player with no suggestion (#170), a filter row of the players you give
and the suggestions table. Each playoff week cell shows the new count, the change and a small bar.
Below 940px of content, a row list replaces the table. The page gets the site shell from publish.shell() and the
table look from publish.TABLE_STYLE (the lab-t table) and publish.band_style().
Under the table, the trade builder (#152) computes a custom trade in the browser. The page inlines
draft/team_builder.js and trade/trade_builder.js, as draft/board.py does. A click on a suggestion loads it into the
builder. The partner starts are an estimate ("est."), because the rostered list does not show the IL slots.
Warning lines (no trade deadline, players with no match in the data files) sit under the header (#153).
After the trade deadline, render_deadline() gives a short page with only the header and the deadline line.
render() and render_deadline() take their data from the caller. write() writes output/trade/index.html with
publish.write_page().
"""

import html
import json
from pathlib import Path

from fantasyhoops import draft
from fantasyhoops.core import common
from fantasyhoops.core import publish as site
from fantasyhoops.core.lineup import UTIL

ENGINE = Path(draft.__file__).parent / "team_builder.js"
TRADE_ENGINE = Path(__file__).parent / "trade_builder.js"
MINUS = "−"
CURRENT = "trade"  # the page in the site menu and its folder on the site: the Trades tab of publish.TOOLS (#151)
EMPTY = "No trade raises your playoff starts."
S1 = ' class="s1"'


def page_path():
    """The trade page: output/trade/index.html, from common.OUT at the time of the call."""
    return common.OUT / "trade" / "index.html"


def write(text, path=None):
    """Write the page text and the font next to it. Return the path."""
    return site.write_page(path or page_path(), text)


def _e(text):
    return html.escape(str(text), quote=True)


def week_label(name):
    """The column label of a playoff week, for example "wk19" -> "Wk19"."""
    return name[:1].upper() + name[1:]


def signed(n):
    """A change of starts: "+2", "−1" or "±0"."""
    return ("+" if n > 0 else MINUS if n < 0 else "±") + str(abs(n))


def value_text(v):
    """A value per game with 2 decimals and a true minus sign. "–" for no value."""
    return "–" if v is None else (MINUS if v < 0 else "") + f"{abs(v):.2f}"


def change_text(v):
    """A value change with its sign: "+0.19", "−0.10" or "±0.00". A change that rounds to 0.00 gets "±"."""
    v = round(v, 2)
    return ("+" if v > 0 else MINUS if v < 0 else "±") + f"{abs(v):.2f}"


def percent(dv, give):
    """Your value change as a percent of |give|, for example "+10%". "" if give is 0."""
    if not give:
        return ""
    p = round(dv / abs(give) * 100)
    return ("+" if p > 0 else MINUS if p < 0 else "") + f"{abs(p)}%"


def _bar(d, total):
    """The change bar of a week cell: a tick at 0, blue to the right for a gain, red to the left for a loss."""
    if d > 0:
        return f'<i class="up" style="--d:{min(d, 6 if total else 4)}"></i>'
    if d < 0:
        return f'<i class="dn" style="--d:{min(-d, 2)}"></i>'
    return ""


def week_cell(before, after, total=False):
    """(class, inner HTML) of a playoff week cell: the new count, the change and the bar, and a text for a reader."""
    d = after - before
    kind = "up" if d > 0 else "dn" if d < 0 else "eq"
    said = "no change" if d == 0 else f"{'up' if d > 0 else 'down'} {abs(d)}"
    inner = (
        f'<span aria-hidden="true"><b>{after}</b><small>{signed(d)}</small>'
        f'<span class="cb">{_bar(d, total)}</span></span>'
        f'<span class="vh">{after} starts, {said} from {before}</span>'
    )
    return f"wk {kind}{' t' if total else ''}", inner


def partner_starts(s):
    """The partner starts of a suggestion under the partner name, an estimate: the starts of each week and the
    total, before (first line) and after (second line), for example "Est. 27·27·25 = 79" and "→ 26·28·26 = 80 +1".
    """
    before, after = sum(s.partner_before), sum(s.partner_after)
    d = after - before
    said = "no change" if d == 0 else f"{'up' if d > 0 else 'down'} {abs(d)}"
    weeks = f"{' · '.join(map(str, s.partner_before))} before, {' · '.join(map(str, s.partner_after))} after"
    kind = "up" if d > 0 else "dn" if d < 0 else "eq"
    b, a = "·".join(map(str, s.partner_before)), "·".join(map(str, s.partner_after))
    return (
        f'<small class="pe {kind}" aria-hidden="true"><span>Est. {b} = {before}</span>'
        f"<span>→ {a} = <b>{after}</b> {signed(d)}</span></small>"
        f'<span class="vh">Partner starts, an estimate: {after}, {said} from {before}. Weeks: {weeks}.</span>'
    )


def partner_line(s):
    """The partner starts of a suggestion in the row list, for example "27 · 29 · 25 = 81 → 26 · 28 · 26 = 80"."""
    b, a = s.partner_before, s.partner_after
    return (
        f'<span class="pst"><em>Them, est.</em>{" · ".join(map(str, b))} = {sum(b)} → '
        f"{' · '.join(map(str, a))} = {sum(a)} <b>{signed(sum(a) - sum(b))}</b></span>"
    )


def _load(k):
    """The rank of a suggestion as a button that loads the trade into the builder."""
    return f'<button type="button" class="ld" aria-label="Load trade {k} in the builder">{k}</button>'


def _flag(p):
    if p.on_il:
        return '<span class="status">IL</span>'
    return f'<span class="status">{_e(p.status)}</span>' if p.status else ""


def _values(p):
    pre = ' <span class="pre">pre</span>' if p.mark else ""
    return f"Val <i>{value_text(p.value)}</i>{pre} · Pre <i>{value_text(p.pg)}</i>"


def _band(team, tag="td"):
    wide = " b4" if len(team) > 3 else ""
    return f'<{tag} class="band{wide}" style="{site.band_style(team)}">{_e(team)}</{tag}>'


def _player_cell(p):
    return (
        f'<th class="pl" scope="row"><b>{_e(p.name)}</b>{_flag(p)}<small>{_e(p.team)} · {_e("/".join(p.positions))}'
        f"</small><small>{_values(p)}</small></th>"
    )


def _value_cells(s):
    minus = " minus" if s.dv < 0 else ""
    return (
        f'<td class="v s1{minus}">{change_text(s.dv)}<small>{percent(s.dv, s.give.value)}</small></td>'
        f'<td class="v">{change_text(s.partner_dv)}</td>'
    )


def desk_table(result, weeks):
    """The suggestions table for 940px of content and more."""
    base, total = result.base, sum(result.base)
    head_weeks = "".join(f'<th scope="col"{S1 if i == 0 else ""}>{_e(week_label(w))}</th>' for i, w in enumerate(weeks))
    now = "".join(f"<td>{b}</td>" for b in base)
    head = (
        '<colgroup><col class="c-rk"><col class="c-band"><col><col class="c-band"><col><col class="c-pt">'
        f'<col class="c-w" span="{len(weeks)}"><col class="c-t"><col class="c-v"><col class="c-v2"></colgroup>'
        f'<thead><tr class="grp"><td colspan="6"></td><th colspan="{len(weeks) + 1}" scope="colgroup" '
        'class="fine s1">Playoff starts</th><th colspan="2" scope="colgroup" class="s1">Value change</th></tr>'
        '<tr><th scope="col">#</th><th scope="col" class="l" colspan="2">You give</th>'
        '<th scope="col" class="l" colspan="2">You get</th><th scope="col" class="l">Partner, est. starts</th>'
        f'{head_weeks}<th scope="col">Total</th><th scope="col" class="s1">You</th><th scope="col">Them</th></tr>'
        f'<tr class="now"><th colspan="6" class="l" scope="row">Your starts now</th>{now}<td>{total}</td>'
        '<td colspan="2"></td></tr></thead>'
    )
    rows = []
    for k, s in enumerate(result.rows, 1):
        cells = []
        for i, (b, a) in enumerate(zip(base, s.after)):
            cls, inner = week_cell(b, a)
            cells.append(f'<td class="{cls}{" s1" if i == 0 else ""}">{inner}</td>')
        cls, inner = week_cell(total, sum(s.after), total=True)
        rows.append(
            f'<tr data-give="{_e(s.give.name)}" data-k="{k - 1}"><td class="rk">{_load(k)}</td>{_band(s.give.team)}'
            f'{_player_cell(s.give)}{_band(s.get.team)}{_player_cell(s.get)}<td class="pt">{_e(s.get.team_name)}'
            f'{partner_starts(s)}</td>{"".join(cells)}<td class="{cls}">{inner}</td>{_value_cells(s)}</tr>'
        )
    return (
        '<table class="sg desk lab-t" id="sg-desk"><caption class="vh">Suggested 1-for-1 trades, the best gain in '
        f"playoff starts first.</caption>{head}<tbody>{''.join(rows)}</tbody></table>"
    )


def _num(label, cls, inner):
    return f'<span class="{cls}"><em>{_e(label)}</em>{inner}</span>'


def mob_list(result, weeks):
    """The row list of the suggestions for less than 940px of content."""
    base, total = result.base, sum(result.base)
    now = "".join(f"<span>{b}</span>" for b in base)
    items = []
    for k, s in enumerate(result.rows, 1):
        nums = [_num(week_label(w), *week_cell(b, a)) for w, b, a in zip(weeks, base, s.after)]
        nums.append(_num("Total", *week_cell(total, sum(s.after), total=True)))
        minus = " minus" if s.dv < 0 else ""
        nums.append(
            f'<span class="v{minus}"><em>You</em>{change_text(s.dv)}<small>{percent(s.dv, s.give.value)}</small></span>'
        )
        nums.append(f'<span class="v"><em>Them</em>{change_text(s.partner_dv)}</span>')
        g, r = s.give, s.get
        items.append(
            f'<li class="ms" data-give="{_e(g.name)}" data-k="{k - 1}"><span class="rk">{_load(k)}</span>'
            f"{_band(g.team, 'span')}"
            f'<span class="nm"><b>{_e(g.name)}</b>{_flag(g)}<small>You give · {_e("/".join(g.positions))} · '
            f"{_values(g)}</small></span>{_band(r.team, 'span')}"
            f'<span class="nm"><b>{_e(r.name)}</b>{_flag(r)}<small>You get from {_e(r.team_name)} · '
            f'{_e("/".join(r.positions))} · {_values(r)}</small></span><span class="nums">{"".join(nums)}</span>'
            f"{partner_line(s)}</li>"
        )
    return (
        f'<div class="mob" id="sg-mob"><div class="mnow">{now}<span>{total}</span><span>Your starts now</span></div>'
        f'<ol class="ml">{"".join(items)}</ol></div>'
    )


def filter_row(result):
    """The filter chips: one chip for each player you give in the suggestions, in the order of the first row."""
    count = {}
    for s in result.rows:
        count[s.give.name] = count.get(s.give.name, 0) + 1
    chips = "".join(
        f'<button type="button" class="chip" aria-pressed="false" data-n="{_e(n)}">{_e(n)}'
        f"<small>{c} trade{'' if c == 1 else 's'}</small></button>"
        for n, c in count.items()
    )
    return f'<div class="filters" id="give-chips"><span class="label">You give (any)</span>{chips}</div>'


def offer_lines(result, offer):
    """The lines of the offered players (#170): the "Offered: ..." line, then one line for each player on the
    [trade] offer list with no suggestion and its reason. offer: the names of [trade] offer.
    """
    if not offer:
        head = "Offered: each player who is not untouchable (config [trade] offer is empty)."
    elif result.offered:
        head = f"Offered: {', '.join(result.offered)} (config [trade] offer)."
    else:
        head = "Offered: none of your players (config [trade] offer)."
    return [head] + [f"No suggestion for {name}: {reason}" for name, reason in result.missed]


def offer_block(result, offer):
    """The offered players and the players with no suggestion, above the table (#170)."""
    head, *missed = offer_lines(result, offer)
    items = "".join(f"<li>{_e(m)}</li>" for m in missed)
    rest = f'<ul class="miss" id="offer-miss">{items}</ul>' if missed else ""
    return f'<div class="offer" id="offer"><p>{_e(head)}</p>{rest}</div>'


def deadline_text(deadline, today):
    """The header cell of the trade deadline, for example "<strong>Thu Mar 4</strong> · 127 days"."""
    if deadline is None:
        return "<strong>Not found</strong>"
    days = (deadline - today).days
    return f"<strong>{deadline:%a %b} {deadline.day}</strong> · {days} day{'' if days == 1 else 's'}"


def _player_data(p, pid, settings):
    return {
        "id": pid,
        "name": p.name,
        "team": p.team,
        "pos": list(p.positions),
        "slot": p.slot,
        "status": p.status,
        "val": p.value,
        "mark": p.mark,
        "pg": p.pg,
        "rank": p.rank,
        "rests_b2b": int(p.rests_b2b),
        "il": p.on_il,
        "untouchable": settings.is_untouchable(p),
        "style": site.band_style(p.team),
    }


def builder_data(result, mine, others, days, slots, weeks, settings):
    """The page data of the trade builder: your players, the partner teams, the suggestions and the engine data.

    result: the suggest.Suggestions. mine, others: the TradePlayers of your team and of the other teams.
    days: the playoff days (home.playoff_days()). slots: [league] slots. weeks: the names of the playoff weeks.
    settings: the suggest.TradeSettings. Each suggestion is {team, give, get}, with the player ids.
    """
    me = [_player_data(p, f"m{i}", settings) for i, p in enumerate(mine)]
    teams, ids = {}, {}
    for i, p in enumerate(others):
        team = teams.setdefault(p.team_id, {"id": p.team_id, "name": p.team_name, "roster": []})
        team["roster"].append(_player_data(p, f"t{i}", settings))
        ids[p] = f"t{i}"
    sugg = [{"team": s.get.team_id, "give": [me[mine.index(s.give)]["id"]], "get": [ids[s.get]]} for s in result.rows]
    engine = {
        "slots": list(slots),
        "util": UTIL,
        "weeks": list(weeks),
        "days": [
            {
                "date": d.date.isoformat(),
                "week": d.week,
                "quality": d.quality,
                "teams": sorted(d.teams),
                "b2b": sorted(d.b2b),
            }
            for d in days
        ],
        "kept": settings.kept,
        "band": list(settings.band),
    }
    order = sorted(teams.values(), key=lambda t: t["name"].casefold())
    return {"me": me, "teams": order, "sugg": sugg, "engine": engine}


def builder_section(data):
    """The trade builder under the suggestions: the partner pick, both player tables, the drops and the result.

    The script of the page fills the tables and the result from data (builder_data()).
    """
    options = "".join(f'<option value="{t["id"]}">{_e(t["name"])}</option>' for t in data["teams"])
    return f"""<section id="builder" aria-labelledby="builder-h">
<h2 id="builder-h">Trade builder</h2>
<p class="lede">Pick a partner team, then the players to give and to get. A click on a suggestion loads it here.</p>
<div class="pick"><label>Partner team<select id="partner">{options}</select></label>
<button type="button" class="chip" id="clear">Clear the players</button></div>
<p class="vh" id="live" aria-live="polite"></p>
<div class="sides">
<div><h3>You give</h3><table class="pk lab-t" id="pk-give"></table>
<p class="line" id="open-me" hidden></p></div>
<div><h3 id="get-h">You get</h3><table class="pk lab-t" id="pk-get"></table></div>
</div>
<div class="drop" id="drop" hidden><div class="filters" id="drop-chips"></div></div>
<div class="res" id="res"></div>
</section>"""


def builder_script(data):
    """The scripts of the builder: the page data, team_builder.js, trade_builder.js and the page script."""
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        f'<script type="application/json" id="trade-data">{text}</script>\n'
        f"<script>\n{ENGINE.read_text(encoding='utf-8')}\n{TRADE_ENGINE.read_text(encoding='utf-8')}\n</script>\n"
        + BUILDER_SCRIPT
    )


def made_text(made):
    """The header cell of the time of the run, for example "<strong>Thu 10/29</strong> 09:30"."""
    return f"<strong>{made:%a} {made.month}/{made.day}</strong> {made:%H:%M}"


def deadline_line(deadline):
    """The line of the page after the trade deadline (#153)."""
    return f"The trade deadline was {deadline:%A, %B} {deadline.day}, {deadline.year}. Yahoo accepts no more trades this season."


def warning_block(warnings):
    """The warning lines under the header, or "" with no warning. Each line starts with "Warning: "."""
    if not warnings:
        return ""
    lines = "".join(f"<li>{_e(w)}</li>" for w in warnings)
    return f'<ul class="warn" id="warnings" aria-label="Warnings">{lines}</ul>'


def render_deadline(cfg, made, deadline):
    """The HTML of the trade page after the trade deadline: the header and the deadline line (#153).

    cfg: the config ([league] teams for the menu). made: the datetime of the run. deadline: the past trade deadline.
    """
    head = f"<strong>{deadline:%a %b} {deadline.day}</strong> · passed"
    body = f'<div class="empty" id="deadline"><p>{_e(deadline_line(deadline))}</p></div>'
    return (
        site.shell(DEADLINE_PAGE, CURRENT, cfg)
        .replace("__DEADLINE__", head)
        .replace("__MADE__", made_text(made))
        .replace("__BODY__", body)
    )


def render(result, weeks, cfg, made, today, deadline=None, rostered_line="", builder=None, warnings=()):
    """The HTML of the trade page.

    result: the suggest.Suggestions. weeks: the names of the playoff weeks. cfg: the config ([trade] kept and
    per_player, [league] teams for the menu). made: the datetime of the run. today: the date of the run.
    deadline: the trade deadline, or None. rostered_line: the read time of the rostered pages (run.rostered_line()).
    builder: the page data of the trade builder (builder_data()), or None for a page with no builder.
    warnings: the warning lines of the run (run.warnings()). They show under the header.
    """
    base = result.base
    starts = " · ".join(str(b) for b in base)
    span = f"{week_label(weeks[0])}–{weeks[-1][2:]}" if len(weeks) > 1 else week_label(weeks[0])
    kept, per = cfg["trade"]["kept"], cfg["trade"]["per_player"]
    foot = (
        f"<b>Starts count your {kept} kept players.</b> The player you get takes the spot of the player you give. "
        f"Val: blended value per game. Pre: preseason value per game. At most {per} trades for each player you give. "
        f"{result.pairs:,} pairs, {result.in_band:,} in the value band, {result.gains:,} with a gain."
    )
    offer = offer_block(result, cfg["trade"].get("offer", []))
    if result.rows:
        body = (
            offer
            + filter_row(result)
            + f'<p class="count" id="sg-count" aria-live="polite">{len(result.rows)} of {len(result.rows)} trades</p>'
            + desk_table(result, weeks)
            + mob_list(result, weeks)
            + KEY
        )
    else:
        body = offer + f'<div class="empty"><p>{EMPTY}</p></div>'
    return (
        site.shell(PAGE, CURRENT, cfg)
        .replace("__DEADLINE__", deadline_text(deadline, today))
        .replace("__STARTS__", f"<strong>{starts}</strong> = {sum(base)}, {_e(span)}")
        .replace("__MADE__", made_text(made))
        .replace("__WARNINGS__", warning_block(warnings))
        .replace("__BODY__", body)
        .replace("__FOOT__", foot)
        .replace("__ROSTERED__", _e(rostered_line))
        .replace("__BUILDER__", builder_section(builder) if builder else "")
        .replace("__BUILDER_JS__", builder_script(builder) if builder else "")
    )


KEY = (
    '<p class="key" aria-hidden="true"><span><span class="cb"><i class="up" style="--d:2"></i></span>2 more starts'
    '</span><span><span class="cb"><i class="dn" style="--d:1"></i></span>1 start lost</span></p>'
)

STYLE = """* { box-sizing: border-box; }
body { font: 400 14px/1.4 var(--lab-face); }
.trade { container-type: inline-size; color: var(--lab-ink); font: 400 13px/1.25 var(--lab-face);
  font-variant-numeric: tabular-nums; padding-block: 16px 40px; padding-left: max(28px, env(safe-area-inset-left));
  padding-right: max(28px, env(safe-area-inset-right)); max-width: 1240px; }
@media (max-width: 899px) { .trade { padding-left: max(16px, env(safe-area-inset-left));
  padding-right: max(16px, env(safe-area-inset-right)); } }
.vh { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }

/* Header: the Roster header, with the deadline, the starts now and the time of the run. */
.head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 28px; padding-bottom: 12px;
  border-bottom: 3px solid var(--mark); }
.head h1 { margin: 0; color: var(--mark); font-weight: 900; font-stretch: 66%; font-size: clamp(32px, 4vw, 44px);
  line-height: .9; text-transform: uppercase; }
.meta { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 0; margin: 0; font-size: 13px; }
.meta div { padding: 0 16px; border-left: 1px solid var(--lab-rule); }
.meta dt { color: var(--lab-mute); font-size: 12px; margin-bottom: 3px; }
.meta dd { margin: 0; }
.meta strong { font-weight: 800; font-size: 15px; }
.meta .dl strong { font-weight: 900; font-stretch: 75%; font-size: 24px; line-height: 1; }
@media (max-width: 599px) { .meta div:first-child { padding-left: 0; border-left: 0; }
  .meta { display: grid; grid-template-columns: auto 1fr; row-gap: 8px; }
  .meta .dl { grid-row: span 2; align-self: center; padding-right: 16px; } }

h2 { margin: 28px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--mark); color: var(--lab-ink);
  font-weight: 900; font-stretch: 75%; font-size: 19px; line-height: 1.1; text-transform: uppercase; }
.foot { margin: 8px 0 0; font-size: 12px; color: var(--lab-mute); max-width: 72ch; }
.foot b { color: var(--lab-ink); font-weight: 800; }

/* Chips: the filter chips of the Free agents table. */
.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }
.filters .label { width: 100%; font-size: 12px; font-weight: 700; color: var(--lab-mute); }
button.chip { font: inherit; font-size: 13px; font-weight: 700; padding: 4px 9px; border: 1.5px solid var(--lamp-off);
  border-radius: 0; background: var(--lab-stock); color: var(--lab-ink); cursor: pointer; line-height: 1.2;
  min-height: 32px; text-align: left; }
button.chip small { display: block; color: var(--lab-mute); font-size: 11px; font-weight: 400; }
button.chip:hover { border-color: var(--lab-ink); }
button.chip[aria-pressed="true"] { background: var(--mark); border-color: var(--mark); color: var(--lab-stock); }
button.chip[aria-pressed="true"] small { color: var(--lab-stock); }
.count { font-size: 12px; margin: 0 0 4px; color: var(--lab-mute); }
/* The offered players and the players with no suggestion (#170), above the filter row. */
.offer { margin: 0 0 10px; font-size: 13px; max-width: 100ch; overflow-wrap: anywhere; }
.offer p { margin: 0; font-weight: 700; }
.offer .miss { list-style: none; margin: 4px 0 0; padding: 0; color: var(--lab-mute); }
.offer .miss li + li { margin-top: 2px; }

/* The suggestions table: the lab-t table of the Roster. Desktop at 940px of content and more, a row list below. */
.sg { table-layout: fixed; font-size: 13px; }
.sg col.c-rk { width: 36px; } .sg col.c-band { width: 40px; } .sg col.c-pt { width: 124px; }
.sg col.c-w { width: var(--wk-w, 64px); } .sg col.c-t { width: var(--t-w, 74px); } .sg col.c-v { width: 76px; }
.sg col.c-v2 { width: 64px; }
.sg thead tr.grp th { border-bottom: 0; padding-bottom: 4px; font-size: 12px; }
.sg thead tr.grp th.fine { background: var(--lab-blue); color: var(--lab-on-blue); text-align: center; padding: 5px 0; }
.sg th.pl { overflow-wrap: anywhere; padding-block: 6px; }
.sg td.band { font-size: 15px; }
.lab-t td.band.b4, .ms .band.b4 { font-size: 12px; }  /* a team code of 4 letters, for example UTAH */
.sg .pl b { display: inline; }
.lab-t .pl small + small { font-size: 11px; margin-top: 1px; }
.lab-t .pl small i, .ms .nm small i { font-style: normal; font-weight: 700; color: var(--lab-ink); }
.pre { font-weight: 700; color: var(--lab-ink); }
.sg td.pt { text-align: left; font-size: 12px; line-height: 1.2; overflow-wrap: anywhere; }
.s1 { border-left: 1px solid var(--vrule); }
td.v { font-size: 14px; white-space: nowrap; }
td.v small { display: block; font-size: 11px; color: var(--lab-mute); }
.minus { color: var(--lab-red); }
.status { display: inline-block; padding: 0 4px; background: var(--lab-red); color: var(--lab-on-red);
  font-size: 11px; font-weight: 800; line-height: 1.4; vertical-align: 3px; margin-left: 4px; font-stretch: 100%; }
.desk { display: none; } .mob { display: block; }
@container (min-width: 940px) { .desk { display: table; } .mob { display: none; } }
[hidden] { display: none !important; }

/* The row list (below 940px of content): one item for each trade. */
.mob { margin: 4px -16px 0; border-top: 2px solid var(--mark); }
@container (min-width: 600px) { .mob { margin: 4px 0 0; } }
.ml { list-style: none; margin: 0; padding: 0; }
.ms { display: grid; grid-template-columns: 34px 40px minmax(0, 1fr); border-bottom: 1px solid var(--lab-rule);
  background: var(--lab-stock); color: var(--lab-ink); }
.ml .ms:nth-of-type(even) { background: var(--zebra); }
.ms .rk { grid-row: span 2; align-self: center; text-align: right; padding-right: 6px; color: var(--lab-red);
  font-weight: 900; font-stretch: 75%; font-size: 19px; }
.ms .band { display: flex; align-items: center; justify-content: center; background: var(--team); color: var(--team-ink);
  font-weight: 900; font-stretch: 70%; font-size: 15px; min-height: 46px; border-bottom: 1px solid var(--lab-stock); }
.ms .nm { padding: 6px 4px 6px 10px; line-height: 1; min-width: 0; align-self: center; }
.ms .nm b { font-weight: 900; font-stretch: 66%; font-size: 18px; text-transform: uppercase; overflow-wrap: anywhere; }
.ms .nm small { display: block; font-size: 12px; line-height: 1.25; color: var(--lab-mute); margin-top: 3px; }
.ms .nums { grid-column: 1 / -1; display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) minmax(min-content, 1.1fr) minmax(min-content, .9fr);
  padding: 6px 6px 8px 8px; border-top: 1px solid var(--lab-rule); }
.ms .nums > span { padding: 0 4px; text-align: right; min-width: 0; }
.ms .nums > span + span { border-left: 1px solid var(--vrule); }
.ms .nums em { display: block; font-style: normal; font-size: 11px; font-weight: 800; color: var(--mark); margin-bottom: 2px; }
.ms .nums .v { font-size: 14px; }
.ms .nums .v small { display: block; font-size: 11px; color: var(--lab-mute); }
.mnow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) minmax(0, 2fr); align-items: center;
  background: var(--lab-blue); color: var(--lab-on-blue); padding: 6px 6px 6px 8px; font-weight: 900; font-size: 15px; }
.mnow span { text-align: right; padding: 0 4px; }
.mnow span:last-child { text-align: left; font-size: 12px; font-weight: 700; padding-left: 12px; }
.empty { border: 1.5px solid var(--lamp-off); padding: 10px 12px; margin: 8px 0; color: var(--lab-ink); }
.empty p { margin: 0; font-weight: 700; }
/* The warning lines of the run (#153), under the header. */
.warn { list-style: none; margin: 12px 0 0; padding: 8px 12px; border-left: 4px solid var(--lab-red);
  background: var(--lab-stock); color: var(--lab-ink); font-size: 13px; max-width: 100ch; overflow-wrap: anywhere; }
.warn li + li { margin-top: 4px; }

/* Look 3 (#149): the starts now in one blue row. Each week cell has the new count, the change and a small bar.
   The bar: a tick at 0, 8px for each start, blue to the right for a gain, red with a gap to the left for a loss. */
.wk { white-space: nowrap; }
.wk b { font-size: 15px; font-weight: 800; }
.wk.eq b { font-weight: 400; }
.wk small { font-size: 12px; font-weight: 800; color: var(--mark); margin-left: 3px; }
.wk.dn small { color: var(--lab-red); }
.wk.eq small { color: var(--lab-mute); font-weight: 600; }
.cb { position: relative; display: block; width: 50px; height: 8px; margin: 4px 0 0 auto; }
.cb::before { content: ""; position: absolute; left: 16px; top: -2px; bottom: -2px; width: 2px; background: var(--lab-ink); }
.cb i { position: absolute; top: 1px; height: 6px; }
.cb i.up { left: 18px; width: calc(var(--d) * 8px - 1px); max-width: calc(100% - 18px); background: var(--mark); }
.cb i.dn { right: calc(100% - 15px); width: calc(var(--d) * 8px - 1px); max-width: 15px;
  background: repeating-linear-gradient(90deg, var(--lab-red) 0 6px, transparent 6px 8px); }
.wk.t .cb { width: 60px; }
.sg thead tr.now > * { background: var(--lab-blue) !important; color: var(--lab-on-blue); border-bottom: 0; }
.sg thead tr.now th, .sg thead tr.now td { font-size: 15px; font-weight: 900; padding: 6px; vertical-align: middle; }
.sg thead tr.now th.l { font-size: 12px; font-weight: 800; text-align: left; padding-left: 10px; }
.ms .nums .cb { width: 100%; max-width: 50px; }
.key { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--lab-mute); margin: 8px 0 0;
  align-items: center; }
.key .cb { display: inline-block; margin: 0 4px 0 0; vertical-align: middle; }

/* The partner starts of a suggestion (an estimate) and the button that loads a suggestion into the builder. */
.sg td.pt small.pe { display: block; margin-top: 4px; font-size: 11px; color: var(--lab-ink); }
.sg td.pt small.pe b { font-weight: 800; }
.sg td.pt small.pe span { display: block; white-space: nowrap; }
.ms .pst { grid-column: 1 / -1; padding: 0 8px 8px; font-size: 12px; color: var(--lab-ink); overflow-wrap: anywhere; }
.ms .pst em { font-style: normal; font-weight: 800; color: var(--mark); margin-right: 6px; }
.ms .pst b { font-weight: 800; }
button.ld { font: inherit; color: inherit; background: none; border: 0; padding: 0; min-width: 28px; min-height: 32px;
  cursor: pointer; text-align: right; }
.ms .rk button.ld { font-size: 19px; }
#sg-desk tbody tr, #sg-mob li.ms { cursor: pointer; }
#sg-desk tbody tr:hover > *:not(.band), #sg-mob li.ms:hover { background: var(--qcol); }
#sg-desk tbody tr[aria-current="true"] > *:not(.band), #sg-mob li.ms[aria-current="true"] { background: var(--qcol); }
#sg-desk tbody tr[aria-current="true"] > * { box-shadow: inset 0 2px var(--mark), inset 0 -2px var(--mark); }
#sg-mob li.ms[aria-current="true"] { box-shadow: inset 4px 0 var(--mark); }

/* The trade builder (#152): the partner pick, a table of the players of each side, the drops and the result. */
.lede { margin: 0 0 10px; font-size: 13px; color: var(--lab-mute); max-width: 72ch; }
h3 { margin: 0 0 6px; font-size: 13px; font-weight: 800; color: var(--lab-ink); overflow-wrap: anywhere; }
.pick { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 16px; margin: 0 0 12px; }
.pick label { display: grid; gap: 4px; font-size: 12px; font-weight: 700; color: var(--lab-mute); max-width: 100%; }
.pick select { font: inherit; font-size: 15px; font-weight: 800; color: var(--lab-ink); background: var(--lab-stock);
  border: 1.5px solid var(--lab-ink); border-radius: 0; min-height: 40px; padding: 0 8px; max-width: 100%; }
.pick select:hover { border-color: var(--mark); }
.sides { display: grid; gap: 20px; grid-template-columns: minmax(0, 1fr); }
@container (min-width: 760px) { .sides { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px; } }
.pk { table-layout: fixed; font-size: 13px; }
.pk col.c-ck { width: 38px; } .pk col.c-band { width: 40px; } .pk col.c-n { width: 54px; }
:where(.pk) tbody td, :where(.pk) tbody th { height: 44px; }
.pk th.pl { overflow-wrap: anywhere; } .pk .pl b { display: inline; font-size: 17px; }
.pk td.ck { padding: 0; text-align: center; }
.pk input { width: 20px; height: 20px; margin: 0; accent-color: var(--mark); cursor: pointer; vertical-align: middle; }
.pk tbody tr { cursor: pointer; }
.pk tbody tr.off { cursor: default; }
.pk tbody tr:not(.off):hover > *:not(.band) { background: var(--qcol); }
.pk tbody tr.on > *:not(.band) { background: var(--qcol); }
.pk tbody tr.on > * { box-shadow: inset 0 2px var(--mark), inset 0 -2px var(--mark); }
.pk td.n { font-size: 13px; }
.pk td.band { font-size: 15px; }
@container (max-width: 599px) { .pk col.c-band { width: 0; } .pk td.band { font-size: 0 !important; }
  .pk col.c-n { width: 50px; } }
.line { font-size: 13px; color: var(--lab-ink); border: 1.5px solid var(--lamp-off); padding: 6px 10px; margin: 10px 0 0;
  width: fit-content; max-width: 100%; }
.line b { font-weight: 800; }
.drop { margin: 14px 0 0; padding: 10px 0 0; border-top: 1px solid var(--lab-rule); }
.res { margin-top: 18px; }
.rt { table-layout: fixed; font-size: 13px; max-width: 860px; }
.rt col.c-w { width: 64px; } .rt col.c-t { width: 74px; } .rt col.c-v { width: 104px; }
.rt th.sd { text-align: left; padding: 5px 6px 5px 10px; line-height: 1.15; overflow-wrap: anywhere; }
.rt th.sd b { font-weight: 900; font-stretch: 66%; font-size: 18px; text-transform: uppercase; display: block; }
.rt th.sd small { display: block; font-size: 12px; color: var(--lab-mute); font-weight: 400; margin-top: 2px; }
.rt tr.now th.sd small { color: var(--lab-on-blue); }
.rt th.sd small.rv { display: none; }
.rt td.v small { white-space: normal; }
.rt tbody tr.now > * { background: var(--lab-blue) !important; color: var(--lab-on-blue); font-weight: 900; }
@container (max-width: 599px) { .rt col.c-v { width: 0; } .rt td.v, .rt thead th.cv { font-size: 0; padding: 0;
  border-left: 0; } .rt td.v small { font-size: 0; } .rt th.sd small.rv { display: block; }
  .rt col.c-w { width: 44px; } .rt col.c-t { width: 54px; } .rt th.sd b { font-size: 16px; }
  .rt .wk .cb { display: none; } .rt td.wk, .rt thead th { padding: 0 4px; }
  .rt .wk small { display: block; margin-left: 0; } }
.res .line { margin-top: 8px; }
.mv { display: flex; flex-wrap: wrap; gap: 4px 22px; margin: 10px 0 0; font-size: 12px; color: var(--lab-mute); }
.mv b { color: var(--lab-ink); font-weight: 800; }"""

# The filter row: a press toggles a chip. With no chip pressed, the table shows all rows.
SCRIPT = """<script>
(() => {
  const chips = [...document.querySelectorAll("#give-chips button")];
  if (!chips.length) return;
  const rows = [...document.querySelectorAll("#sg-desk tbody tr, #sg-mob li.ms")];
  const count = document.getElementById("sg-count"), all = document.querySelectorAll("#sg-desk tbody tr").length;
  const on = new Set();
  const show = () => {
    chips.forEach(b => b.setAttribute("aria-pressed", on.has(b.dataset.n)));
    rows.forEach(r => { r.hidden = on.size > 0 && !on.has(r.dataset.give); });
    const n = [...document.querySelectorAll("#sg-desk tbody tr")].filter(r => !r.hidden).length;
    count.textContent = `${n} of ${all} trades`;
  };
  chips.forEach(b => b.addEventListener("click", () => {
    on.has(b.dataset.n) ? on.delete(b.dataset.n) : on.add(b.dataset.n);
    show();
  }));
})();
</script>"""

# The trade builder (#152). TradeBuilder (trade_builder.js) computes the trade, and this script draws it.
# A click on a suggestion row loads its trade. The week cells have the markup of week_cell().
BUILDER_SCRIPT = """<script>
(() => {
  const D = JSON.parse(document.getElementById("trade-data").textContent);
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const M = "−", sum = a => a.reduce((x, y) => x + y, 0), plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const signed = n => (n > 0 ? "+" : n < 0 ? M : "±") + Math.abs(n);
  const val = v => (v == null ? "–" : (v < 0 ? M : "") + Math.abs(v).toFixed(2));
  const change = v => { const r = Math.round(v * 100) / 100; return (r > 0 ? "+" : r < 0 ? M : "±") + Math.abs(r).toFixed(2); };
  const label = w => w.charAt(0).toUpperCase() + w.slice(1);
  const byId = new Map(D.me.map(p => [p.id, p]));
  D.teams.forEach(t => t.roster.forEach(p => byId.set(p.id, p)));
  const st = {team: D.teams.length ? D.teams[0].id : null, give: new Set(), get: new Set(), drops: [], row: null};
  const team = () => D.teams.find(t => t.id === st.team);
  const flag = p => (p.il ? '<span class="status">IL</span>' : p.status ? `<span class="status">${esc(p.status)}</span>` : "");
  const band = p => `<td class="band${p.team.length > 3 ? " b4" : ""}" style="${p.style}">${esc(p.team)}</td>`;

  function bar(d, total) {
    if (d > 0) return `<i class="up" style="--d:${Math.min(d, total ? 6 : 4)}"></i>`;
    if (d < 0) return `<i class="dn" style="--d:${Math.min(-d, 2)}"></i>`;
    return "";
  }
  function cell(before, after, total, extra) {
    const d = after - before, kind = d > 0 ? "up" : d < 0 ? "dn" : "eq";
    const said = d === 0 ? "no change" : `${d > 0 ? "up" : "down"} ${Math.abs(d)}`;
    return `<td class="wk ${kind}${total ? " t" : ""}${extra ? " " + extra : ""}"><span aria-hidden="true"><b>${after}</b>`
      + `<small>${signed(d)}</small><span class="cb">${bar(d, total)}</span></span>`
      + `<span class="vh">${after} starts, ${said} from ${before}</span></td>`;
  }

  function pickTable(id, players, set, mine) {
    const kept = new Set(TradeBuilder.keptSet(players, D.engine.kept).map(p => p.id));
    const rows = players.map(p => {
      const off = mine && p.untouchable, on = set.has(p.id);
      const line = [p.team, p.pos.join("/")].concat(kept.has(p.id) ? ["kept"] : [], off ? ["untouchable"] : []);
      return `<tr class="${off ? "off" : ""}${on ? " on" : ""}" data-id="${p.id}">`
        + `<td class="ck"><input type="checkbox" aria-label="${mine ? "Give" : "Get"} ${esc(p.name)}"${on ? " checked" : ""}`
        + `${off ? " disabled" : ""}></td>${band(p)}<th class="pl" scope="row"><b>${esc(p.name)}</b>${flag(p)}`
        + `<small>${esc(line.join(" · "))}</small></th>`
        + `<td class="n s1">${val(p.val)}${p.mark ? " pre" : ""}</td><td class="n">${val(p.pg)}</td></tr>`;
    }).join("");
    $(id).innerHTML = '<colgroup><col class="c-ck"><col class="c-band"><col><col class="c-n" span="2"></colgroup>'
      + `<thead><tr><th scope="col"><span class="vh">${mine ? "Give" : "Get"}</span></th>`
      + '<th scope="col" class="l" colspan="2">Player</th><th scope="col" class="s1">Val</th><th scope="col">Pre</th></tr></thead>'
      + `<tbody>${rows}</tbody>`;
    $(id).querySelectorAll("tbody tr").forEach(tr => {
      const box = tr.querySelector("input");
      const flip = () => {
        const n = tr.dataset.id;
        set.has(n) ? set.delete(n) : set.add(n);
        st.row = null;
        draw();
        $(id).querySelector(`tr[data-id="${n}"] input`).focus();
      };
      box.addEventListener("change", flip);
      tr.addEventListener("click", ev => { if (ev.target !== box && !box.disabled) flip(); });
    });
  }

  function pickDrops(more) {
    const options = D.me.filter(p => !st.give.has(p.id) && !p.untouchable);
    const ok = new Set(options.map(p => p.id));
    st.drops = st.drops.filter(id => ok.has(id)).slice(-more);
    const low = options.slice().sort((a, b) => (a.val != null) - (b.val != null) || (a.val || 0) - (b.val || 0));
    for (const p of low) if (st.drops.length < more && !st.drops.includes(p.id)) st.drops.push(p.id);
    $("drop-chips").innerHTML = `<span class="label">You get ${plural(more, "more player")} than you give. `
      + `Pick ${more === 1 ? "your drop" : `${more} drops`}.</span>` + options.map(p =>
        `<button type="button" class="chip" aria-pressed="${st.drops.includes(p.id)}" data-id="${p.id}">${esc(p.name)}`
        + `<small>Val ${val(p.val)}</small></button>`).join("");
    $("drop-chips").querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
      if (!st.drops.includes(b.dataset.id)) { st.drops.push(b.dataset.id); st.drops = st.drops.slice(-more); }
      st.row = null;
      draw();
      $("drop-chips").querySelector(`[data-id="${b.dataset.id}"]`).focus();
    }));
  }

  function sideRows(name, side, est, verdict) {
    const bt = sum(side.before), at = sum(side.after);
    const tag = est ? ", est." : "", minus = side.dv < 0 ? " minus" : "";
    const note = verdict ? `<small>${verdict === "in" ? "In the band" : verdict === "below" ? "Below the band" : "Above the band"}</small>` : "";
    const now = side.before.map((b, i) => `<td class="${i ? "" : "s1"}">${b}</td>`).join("");
    return `<tr class="now"><th class="sd" scope="row"><b>${esc(name)}</b><small>Now${tag}</small></th>${now}<td>${bt}</td>`
      + '<td class="v s1"></td></tr>'
      + `<tr><th class="sd" scope="row"><b>${esc(name)}</b><small>After the trade${tag}</small>`
      + `<small class="rv">Value ${change(side.dv)}</small></th>`
      + side.before.map((b, i) => cell(b, side.after[i], false, i ? "" : "s1")).join("") + cell(bt, at, true)
      + `<td class="v s1${minus}">${change(side.dv)}${note}</td></tr>`;
  }

  function result(give, get, drops) {
    const t = team();
    const r = TradeBuilder.trade(D.me, t.roster, give, get, drops, D.engine);
    const weeks = D.engine.weeks;
    const head = '<colgroup><col><col class="c-w" span="' + weeks.length + '"><col class="c-t"><col class="c-v"></colgroup>'
      + '<thead><tr><th scope="col" class="l">Team</th>'
      + weeks.map((w, i) => `<th scope="col"${i ? "" : ' class="s1"'}>${label(w)}</th>`).join("")
      + '<th scope="col">Total</th><th scope="col" class="s1 cv">Value</th></tr></thead>';
    const lines = [];
    if (r.partner.open) lines.push(`<p class="line" id="open-them"><b>${esc(t.name)}: ${plural(r.partner.open, "open roster spot")}:</b> a free agent can fill ${r.partner.open === 1 ? "it" : "them"}.</p>`);
    r.partner.drops.forEach(p => lines.push(`<p class="line" id="drop-them"><b>${esc(t.name)} drops ${esc(p.name)}</b> (Val ${val(p.val)}): his lowest value player who is not on IL.</p>`));
    const moved = give.map(p => `<span>You give <b>${esc(p.name)}</b> Val ${val(p.val)} · Pre ${val(p.pg)}</span>`)
      .concat(get.map(p => `<span>You get <b>${esc(p.name)}</b> Val ${val(p.val)} · Pre ${val(p.pg)}</span>`))
      .concat(drops.map(p => `<span>You drop <b>${esc(p.name)}</b> Val ${val(p.val)} · Pre ${val(p.pg)}</span>`));
    $("res").innerHTML = '<h3>Result</h3><table class="rt lab-t" id="rt"><caption class="vh">Playoff starts before and after '
      + 'the trade, and the value change, for both teams.</caption>' + head + "<tbody>"
      + sideRows("Your team", r.mine, false, r.band) + sideRows(t.name, r.partner, true, "") + "</tbody></table>"
      + lines.join("")
      + '<p class="mv" id="est-note">Est.: their starts are an estimate, because the rostered list does not show their IL slots.</p>'
      + `<p class="mv">${moved.join("")}</p>`;
  }

  function draw() {
    const t = team();
    $("partner").value = String(st.team);
    $("get-h").textContent = `You get from ${t.name}`;
    const own = new Set(t.roster.map(p => p.id));
    [...st.get].forEach(id => { if (!own.has(id)) st.get.delete(id); });
    pickTable("pk-give", D.me, st.give, true);
    pickTable("pk-get", t.roster, st.get, false);
    const more = st.get.size - st.give.size, open = st.give.size - st.get.size;
    $("drop").hidden = !(more > 0);
    if (more > 0) pickDrops(more); else st.drops = [];
    $("open-me").hidden = !(open > 0 && st.get.size > 0);
    $("open-me").innerHTML = `<b>${plural(open, "open roster spot")}:</b> a free agent can fill ${open === 1 ? "it" : "them"}.`;
    document.querySelectorAll("#sg-desk tbody tr, #sg-mob li.ms").forEach(r => {
      if (st.row !== null && Number(r.dataset.k) === st.row) r.setAttribute("aria-current", "true");
      else r.removeAttribute("aria-current");
    });
    if (!st.give.size || !st.get.size) {
      $("res").innerHTML = '<div class="empty"><p>Pick at least 1 player to give and 1 player to get.</p></div>';
      return;
    }
    result(D.me.filter(p => st.give.has(p.id)), t.roster.filter(p => st.get.has(p.id)), st.drops.map(id => byId.get(id)));
  }

  function load(k) {
    const s = D.sugg[k];
    st.team = s.team; st.give = new Set(s.give); st.get = new Set(s.get); st.drops = []; st.row = k;
    draw();
    $("live").textContent = `Trade ${k + 1} is in the builder.`;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    $("builder").scrollIntoView({behavior: reduce ? "auto" : "smooth", block: "start"});
  }

  if (!st.team) return;
  document.querySelectorAll("#sg-desk tbody tr, #sg-mob li.ms").forEach(r =>
    r.addEventListener("click", () => load(Number(r.dataset.k))));
  $("partner").addEventListener("change", e => {
    st.team = Number(e.target.value); st.get.clear(); st.row = null; draw();
  });
  $("clear").addEventListener("click", () => { st.give.clear(); st.get.clear(); st.row = null; draw(); });
  draw();
})();
</script>"""

PAGE = (
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trades</title>
__HEAD__
<style>
__TABLE_CSS__
"""
    + STYLE
    + """
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main trade">
<header class="head">
<h1>Trades</h1>
<dl class="meta">
<div class="dl"><dt>Trade deadline</dt><dd>__DEADLINE__</dd></div>
<div><dt>Your playoff starts</dt><dd>__STARTS__</dd></div>
<div><dt>Made</dt><dd>__MADE__</dd></div>
</dl>
</header>
__WARNINGS__
<section id="sugg" aria-labelledby="sugg-h">
<h2 id="sugg-h">Suggested trades</h2>
__BODY__
<p class="foot" id="sg-foot">__FOOT__</p>
<p class="foot" id="sg-read">__ROSTERED__</p>
</section>
__BUILDER__
</main>
__SCRIPT__
"""
    + SCRIPT
    + """
__BUILDER_JS__
</body>
</html>
"""
)

# The page after the trade deadline (#153): the header and one line. No table, no builder and no script of its own.
DEADLINE_PAGE = (
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trades</title>
__HEAD__
<style>
__TABLE_CSS__
"""
    + STYLE
    + """
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main trade">
<header class="head">
<h1>Trades</h1>
<dl class="meta">
<div class="dl"><dt>Trade deadline</dt><dd>__DEADLINE__</dd></div>
<div><dt>Made</dt><dd>__MADE__</dd></div>
</dl>
</header>
__BODY__
</main>
__SCRIPT__
</body>
</html>
"""
)
