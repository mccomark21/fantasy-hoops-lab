"""The trade page (#150): the suggested 1-for-1 trades, in the look that the owner picked on #149 (look 3).

The page has a header (the trade deadline, your playoff starts and the time of the run), a filter row of the
players you give and the suggestions table. Each playoff week cell shows the new count, the change and a small bar.
Below 940px of content, a row list replaces the table. The page gets the site shell from publish.shell() and the
table look from publish.TABLE_STYLE (the lab-t table) and publish.band_style().
render() takes its data from the caller. write() writes output/trade/index.html with publish.write_page().
"""

import html

from fantasyhoops.core import common
from fantasyhoops.core import publish as site

MINUS = "−"
CURRENT = "trade"  # the page in the site menu. #151 adds the Trades tab to publish.TOOLS.
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
    """A value change with its sign: "+0.19", "−0.10" or "±0.00"."""
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


def _flag(p):
    if p.on_il:
        return '<span class="status">IL</span>'
    return f'<span class="status">{_e(p.status)}</span>' if p.status else ""


def _values(p):
    pre = ' <span class="pre">pre</span>' if p.mark else ""
    return f"Val <i>{value_text(p.value)}</i>{pre} · Pre <i>{value_text(p.pg)}</i>"


def _band(team, tag="td"):
    return f'<{tag} class="band" style="{site.band_style(team)}">{_e(team)}</{tag}>'


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
        '<th scope="col" class="l" colspan="2">You get</th><th scope="col" class="l">Partner</th>'
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
            f'<tr data-give="{_e(s.give.name)}"><td class="rk">{k}</td>{_band(s.give.team)}{_player_cell(s.give)}'
            f'{_band(s.get.team)}{_player_cell(s.get)}<td class="pt">{_e(s.get.team_name)}</td>{"".join(cells)}'
            f'<td class="{cls}">{inner}</td>{_value_cells(s)}</tr>'
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
            f'<li class="ms" data-give="{_e(g.name)}"><span class="rk">{k}</span>{_band(g.team, "span")}'
            f'<span class="nm"><b>{_e(g.name)}</b>{_flag(g)}<small>You give · {_e("/".join(g.positions))} · '
            f"{_values(g)}</small></span>{_band(r.team, 'span')}"
            f'<span class="nm"><b>{_e(r.name)}</b>{_flag(r)}<small>You get from {_e(r.team_name)} · '
            f'{_e("/".join(r.positions))} · {_values(r)}</small></span><span class="nums">{"".join(nums)}</span></li>'
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


def deadline_text(deadline, today):
    """The header cell of the trade deadline, for example "<strong>Thu Mar 4</strong> · 127 days"."""
    if deadline is None:
        return "<strong>Not found</strong>"
    days = (deadline - today).days
    return f"<strong>{deadline:%a %b} {deadline.day}</strong> · {days} day{'' if days == 1 else 's'}"


def render(result, weeks, cfg, made, today, deadline=None, rostered_line=""):
    """The HTML of the trade page.

    result: the suggest.Suggestions. weeks: the names of the playoff weeks. cfg: the config ([trade] kept and
    per_player, [league] teams for the menu). made: the datetime of the run. today: the date of the run.
    deadline: the trade deadline, or None. rostered_line: the read time of the rostered pages (run.rostered_line()).
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
    if result.rows:
        body = (
            filter_row(result)
            + f'<p class="count" id="sg-count" aria-live="polite">{len(result.rows)} of {len(result.rows)} trades</p>'
            + desk_table(result, weeks)
            + mob_list(result, weeks)
            + KEY
        )
    else:
        body = f'<div class="empty"><p>{EMPTY}</p></div>'
    return (
        site.shell(PAGE, CURRENT, cfg)
        .replace("__DEADLINE__", deadline_text(deadline, today))
        .replace("__STARTS__", f"<strong>{starts}</strong> = {sum(base)}, {_e(span)}")
        .replace("__MADE__", f"<strong>{made:%a} {made.month}/{made.day}</strong> {made:%H:%M}")
        .replace("__BODY__", body)
        .replace("__FOOT__", foot)
        .replace("__ROSTERED__", _e(rostered_line))
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

/* The suggestions table: the lab-t table of the Roster. Desktop at 940px of content and more, a row list below. */
.sg { table-layout: fixed; font-size: 13px; }
.sg col.c-rk { width: 36px; } .sg col.c-band { width: 40px; } .sg col.c-pt { width: 104px; }
.sg col.c-w { width: var(--wk-w, 64px); } .sg col.c-t { width: var(--t-w, 74px); } .sg col.c-v { width: 76px; }
.sg col.c-v2 { width: 64px; }
.sg thead tr.grp th { border-bottom: 0; padding-bottom: 4px; font-size: 12px; }
.sg thead tr.grp th.fine { background: var(--lab-blue); color: var(--lab-on-blue); text-align: center; padding: 5px 0; }
.sg th.pl { overflow-wrap: anywhere; }
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
  grid-template-columns: repeat(4, minmax(0, 1fr)) minmax(0, 1.1fr) minmax(0, .9fr);
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
.cb i.up { left: 18px; width: calc(var(--d) * 8px - 1px); background: var(--mark); }
.cb i.dn { right: 35px; width: calc(var(--d) * 8px - 1px);
  background: repeating-linear-gradient(90deg, var(--lab-red) 0 6px, transparent 6px 8px); }
.wk.t .cb { width: 60px; }
.wk.t .cb i.up { max-width: 42px; }
.sg thead tr.now > * { background: var(--lab-blue) !important; color: var(--lab-on-blue); border-bottom: 0; }
.sg thead tr.now th, .sg thead tr.now td { font-size: 15px; font-weight: 900; padding: 6px; vertical-align: middle; }
.sg thead tr.now th.l { font-size: 12px; font-weight: 800; text-align: left; padding-left: 10px; }
.ms .nums .cb { width: 100%; max-width: 50px; }
.key { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--lab-mute); margin: 8px 0 0;
  align-items: center; }
.key .cb { display: inline-block; margin: 0 4px 0 0; vertical-align: middle; }"""

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
<section id="sugg" aria-labelledby="sugg-h">
<h2 id="sugg-h">Suggested trades</h2>
__BODY__
<p class="foot" id="sg-foot">__FOOT__</p>
<p class="foot" id="sg-read">__ROSTERED__</p>
</section>
</main>
__SCRIPT__
"""
    + SCRIPT
    + """
</body>
</html>
"""
)
