"""Schedule Skyline: the SVG of one week, drawn from the facts of core/skyline.py (issue 235).

render() gives one of three layouts. "page" is the skyline over the ladder, for the adds page. "skyline" and
"ladder" are the two 1080x1350 images of the Bluesky post. The two post layouts keep all text at 30 px or more
(DESIGN.md "The Phone Legibility Rule"). The colors come from core/tokens.py. This module writes no files.
DESIGN.md "Poster mode" gives the rules. The approved mock is concept "7C v6".
"""

import html
import re
from dataclasses import dataclass, replace

from fantasyhoops.core import tokens
from fantasyhoops.core.skyline import DAYS

LAYOUTS = ("page", "skyline", "ladder")
SIZE = (1080, 1350)  # the width and the height of each layout, in px
TITLE, BRAND = "SCHEDULE ", "SKYLINE"  # "Schedule" in lab-ink, "Skyline" in mark

# The 4 type styles of the Skyline: (font weight, font stretch in %, the width of each character of CHARS in
# 1/1000 em). The widths are Archivo in Chromium, measured on 2026-11-05 with tabular digits.
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+=-()·–,. "
_WIDTHS = {
    "display": (
        900,
        62,
        "530 498 513 509 462 402 543 513 263 453 510 432 705 518 554 485 554 509 469 475 503 490 729 500 481 475 "
        "443 440 421 440 428 287 415 437 228 232 462 228 649 437 433 440 440 296 400 293 437 414 638 448 408 383 "
        "440 440 440 440 440 440 440 440 440 440 528 528 240 389 389 210 310 222 222 110",
    ),
    "label": (
        800,
        75,
        "584 572 589 589 537 479 629 601 273 496 593 484 758 604 634 550 634 584 537 532 594 560 797 572 566 538 "
        "491 495 475 495 484 294 478 490 238 238 490 238 733 491 493 495 495 319 446 305 491 447 684 482 444 425 "
        "497 497 497 497 497 497 497 497 497 497 557 557 272 368 368 252 375 248 248 142",
    ),
    "body": (
        500,
        80,
        "565 574 601 606 549 491 647 605 240 470 572 459 730 607 648 552 648 594 543 515 599 545 791 568 567 534 "
        "469 481 448 481 468 257 465 475 210 207 444 209 718 475 483 481 481 288 426 258 475 414 623 439 414 418 "
        "488 488 488 488 488 488 488 488 488 488 549 549 284 339 339 268 400 239 239 164",
    ),
    "text": (
        400,
        100,
        "682 698 728 734 677 612 796 736 267 559 662 536 847 736 788 665 788 727 673 606 731 648 924 680 655 635 "
        "545 567 519 567 548 280 556 563 225 223 514 225 860 563 570 567 567 332 510 297 562 504 723 513 504 498 "
        "568 568 568 568 568 568 568 568 568 568 625 625 333 355 355 333 500 277 277 209",
    ),
}
STYLES = {
    name: (weight, stretch, dict(zip(CHARS, (int(v) / 1000 for v in widths.split()))))
    for name, (weight, stretch, widths) in _WIDTHS.items()
}


@dataclass(frozen=True)
class DayAxis:
    """The day axis of a layout: the position and the size of each day column.

    All day positions of the renderer come from this class. Today the axis runs from left to right.
    """

    start: float
    length: float
    days: int = DAYS

    @property
    def step(self):
        return self.length / self.days

    def lo(self, i):
        return self.start + i * self.step

    def mid(self, i):
        return self.lo(i) + self.step / 2

    @property
    def end(self):
        return self.start + self.length

    def span(self, first, last, inset=0.0):
        """(position, size) of the days first to last (last exclusive), inset at each end."""
        return self.lo(first) + inset, (last - first) * self.step - 2 * inset


@dataclass(frozen=True)
class _Profile:
    """The sizes of one layout, in px. A text size is the font size."""

    margin: float  # the margin of the frame
    gutter: float  # the column left of the days for the rung totals. 0: each rung has a header row
    title: float
    week: float
    count: float  # the game count over a skyline column
    count_big: float  # the game count of a light night or an anchor night
    head: float  # the day name
    head_date: float  # the date under the day name
    label: float  # the leg label ("4 GM · 1 LIGHT")
    chip: float
    chip_lead: float  # the chips of rung 1 in a heavy-team week
    body: float  # "N teams to choose from"
    tag: float  # "+1", "BACK-TO-BACK", "RE-PLAN"
    none: float  # "NO NBA GAMES"
    rung: float  # the rung text ("1 ADD", "games · 1 light", the gain)
    total: float  # the game total of a rung, in the gutter
    dot: float  # the radius of a game dot on a light night
    tick: float  # the radius of a tick
    b2b: float  # the width of a back-to-back line
    line: float  # the width of the light-night line
    halo: float  # the width of the paper halo on each side of the light-night line
    inset: float  # the gap between a skyline column and the day rule


PAGE = _Profile(64, 96, 90, 30, 22, 40, 24, 12, 11, 17, 30, 14, 12, 22, 13, 58, 8.5, 2, 2, 1.5, 2.5, 4)
# The post: 30 px on a 1080 px image is 11 px at a display width of 390 px.
POST = _Profile(48, 0, 84, 36, 40, 60, 44, 30, 30, 30, 48, 30, 30, 30, 30, 0, 15, 6, 5, 4, 4, 4)


def profile(layout):
    """The _Profile of layout."""
    return PAGE if layout == "page" else replace(POST, title=52, week=30) if layout == "ladder" else POST


def axis(layout):
    """The DayAxis of layout: the page layout has a gutter for the rung totals, a post layout has none."""
    p = profile(layout)
    return DayAxis(p.margin + p.gutter, SIZE[0] - 2 * p.margin - p.gutter)


def text_width(text, size, style="text"):
    """The width of text in px, at the font size size and the type style style of STYLES, plus 5%."""
    widths = STYLES[style][2]
    return sum(widths.get(c, widths["M"]) for c in text) * size * 1.05


def _wrap(text, width, size, style, sep=" "):
    """The lines of text, broken at sep, so that each line fits width if it can."""
    lines = []
    for word in text.split(sep):
        if lines and text_width(lines[-1] + sep + word, size, style) <= width:
            lines[-1] += sep + word
        else:
            lines.append(word)
    return lines


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class _Svg:
    """The elements of one SVG, in paint order."""

    def __init__(self):
        self.parts = []

    def add(self, part):
        self.parts.append(part)

    def rect(self, x, y, w, h, cls, style=""):
        st = f' style="{style}"' if style else ""
        self.add(f'<rect class="{cls}" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}"{st}/>')

    def line(self, x1, y1, x2, y2, cls, style=""):
        st = f' style="{style}"' if style else ""
        self.add(f'<line class="{cls}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"{st}/>')

    def circle(self, cx, cy, r, cls, style=""):
        st = f' style="{style}"' if style else ""
        self.add(f'<circle class="{cls}" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}"{st}/>')

    def text(self, x, y, s, size, cls, style="text", anchor="start", css="", inner=None):
        weight, stretch, _ = STYLES[style]
        st = f"font-size:{_f(size)}px;font-weight:{weight};font-stretch:{stretch}%;{css}"
        body = inner if inner is not None else html.escape(s)
        self.add(
            f'<text class="{cls}" data-style="{style}" x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" '
            f'style="{st}">{body}</text>'
        )

    def lines(self, x, top, lines, size, cls, style, lead=1.1):
        """Text lines from top (the top of the first line). Return the y under the last line."""
        for n, t in enumerate(lines):
            self.text(x, top + size * 0.86 + n * size * lead, t, size, cls, style)
        return top + len(lines) * size * lead


def _css(sid, theme):
    """The style of one SVG. sid scopes the rules to that SVG. Each color is a token of core/tokens.py."""
    dark = theme == "dark"
    c = {
        **tokens.LIGHT,
        **tokens.SKYLINE_LIGHT,
        **(tokens.DARK if dark else {}),
        **(tokens.SKYLINE_DARK if dark else {}),
    }
    o = tokens.SKYLINE_OPACITIES
    rules = {
        "": "font-family: Archivo, 'Arial Narrow', system-ui, sans-serif; font-variant-numeric: tabular-nums",
        ".paper": f"fill: {c['lab-stock']}",
        ".ink": f"fill: {c['lab-ink']}",
        ".mute": f"fill: {c['lab-mute']}",
        ".mark": f"fill: {c['mark']}",
        ".stock": f"fill: {c['lab-stock']}",
        ".blk": f"fill: {c['qcol']}",
        ".blk-dim": f"fill: {c['sky-dim']}",
        ".blk-lt, .anchor": f"fill: {c['mark']}",
        ".hatch-ground": f"fill: {c['sky-hatch']}",
        ".hatch-line": f"fill: {c['sky-hatch-line']}",
        ".none-box": f"fill: {c['sky-grid']}; stroke: {c['sky-hatch-line']}; stroke-width: 1.5",
        ".stripe": f"fill: {c['sky-stripe']}; pointer-events: none",
        ".grid": f"fill: {c['sky-grid']}",
        ".day-rule, .rung-rule": f"stroke: {c['vrule']}; stroke-width: 1",
        ".rung-rule.first": f"stroke: {c['lab-ink']}",
        ".base-rule": f"stroke: {c['lab-ink']}; stroke-width: 2",
        ".title-rule": f"stroke: {c['lab-ink']}; stroke-width: 3",
        ".leg-box": f"fill: {c['lab-stock']}; stroke: {c['lamp-off']}; stroke-width: 1",
        ".quiet .leg-box": f"stroke: {c['vrule']}",
        ".quiet .leg-ink": f"opacity: {o['quiet']}",
        ".quiet .chip": f"opacity: {o['quiet-chip']}",
        ".dot": f"fill: {c['lab-stock']}; stroke: {c['mark']}",
        ".dot-s": f"fill: {c['mark']}",
        ".tick": f"fill: {c['lamp-off']}; opacity: {o['tick']}",
        ".b2b": f"stroke: {c['lab-ink']}",
        ".tag-box": f"fill: {c['lab-ink']}",
        ".halo": f"stroke: {c['lab-stock']}",
        ".night-line": f"stroke: {c['mark']}",
    }
    return "\n".join(f"#{sid}{' ' + k if k else ''} {{ {v}; }}" for k, v in rules.items())


def _hatch(sid):
    return (
        f'<pattern id="{sid}-hatch" patternUnits="userSpaceOnUse" width="6.5" height="6.5" '
        'patternTransform="rotate(45)"><rect class="hatch-ground" width="6.5" height="6.5"/>'
        '<rect class="hatch-line" width="1.5" height="6.5"/></pattern>'
    )


class _Week:
    """The drawing facts of one week that more than one part of a layout reads."""

    def __init__(self, week, rungs, sid):
        self.w = week
        self.rungs = tuple(rungs if rungs is not None else week.rungs)
        self.anchor = tuple(d in week.anchors for d in week.days)
        span = week.dead_span or (0, 0)
        # The stripe: the anchor nights, and the days of the dead span that have games (v6).
        self.stripe = tuple(self.anchor[i] or (span[0] <= i < span[1] and not week.no_games[i]) for i in range(DAYS))
        self.spot = bool(week.anchors)  # a week with an anchor night dims the other skyline blocks
        self.lead = week.week_type == "heavy-team"
        self.hatch = f"fill:url(#{sid}-hatch)"


def _title(s, p, y, week_no, year):
    s.text(p.margin, y, TITLE + BRAND, p.title, "ink", "display", inner=f'{TITLE}<tspan class="mark">{BRAND}</tspan>')
    x = p.margin + text_width(TITLE + BRAND, p.title, "display") + p.week * 0.4
    s.text(x, y, f"Week {week_no} · {year}", p.week, "ink", "label")


def _runs(flags):
    """(first, last exclusive) of each run of True in flags."""
    out, i = [], 0
    while i < len(flags):
        j = i
        while j < len(flags) and flags[j]:
            j += 1
        if j > i:
            out.append((i, j))
        i = j + 1
    return out


def _night_line(s, p, x0, x1, y, cls="sk-line"):
    """The light-night line: a dashed mark line on a paper halo. Its width stays the same when a page scales it."""
    keep = "vector-effect:non-scaling-stroke"
    s.add(f'<g class="{cls}">')
    s.line(x0, y, x1, y, "halo", f"stroke-width:{_f(p.line + 2 * p.halo)};{keep}")
    s.line(x0, y, x1, y, "night-line", f"stroke-width:{_f(p.line)};stroke-dasharray:5 4;{keep}")
    s.add("</g>")


def _skyline(s, k, p, ax, top, bottom):
    """The skyline from top to bottom: one column for each day, then the light-night line on top. Return its y."""
    w = k.w
    pitch = (bottom - top - p.count_big - 10) / w.scale_max
    bh = pitch * 0.76
    line_y = bottom - w.light_max * pitch
    for i in range(DAYS):
        x, cw = ax.span(i, i + 1, p.inset)
        g, h = w.games[i], w.games[i] * pitch
        if w.no_games[i]:
            s.rect(x, top, cw, bottom - top, "hatch", k.hatch)
        elif k.anchor[i]:
            s.rect(x, bottom - h, cw, h, "anchor")
            if h >= p.count_big + 12:
                s.text(
                    ax.mid(i), bottom - h + p.count_big * 0.86 + 6, str(g), p.count_big, "stock", "display", "middle"
                )
            else:
                s.text(x, bottom - h - 6, str(g), p.count_big, "mark", "display")
        else:
            lt = w.light[i] and not k.spot
            for n in range(g):
                s.rect(x, bottom - n * pitch - bh, cw, bh, "blk-dim" if k.spot else "blk-lt" if lt else "blk")
            size, ink = (p.count_big, "mark") if lt else (p.count, "mute" if k.spot else "ink")
            y = bottom - h + (pitch - bh) - 6
            if y - size * 0.8 - p.halo < line_y < y + p.halo:  # the count stays clear of the light-night line
                y = line_y - p.line - p.halo - 4
            s.text(x, y, str(g), size, ink, "display")
    for a, b in _runs(w.no_games):
        x, cw = ax.span(a, b, p.inset)
        lines = _wrap("NO NBA GAMES", cw - 16, p.none, "display")
        if b - a > 1:
            lines.append(f"{w.days[a]:%a}–{w.days[b - 1]:%a}")
        bw = max(text_width(t, p.none, "display") for t in lines) + 16
        bh2 = p.none * 1.15 * len(lines) + 12
        cx, by = x + cw / 2, bottom - bh2 - 8
        s.rect(cx - bw / 2, by, bw, bh2, "none-box")
        for n, t in enumerate(lines):
            s.text(cx, by + 6 + p.none * 0.86 + n * p.none * 1.15, t, p.none, "ink", "display", "middle")
    _night_line(s, p, p.margin, ax.end, line_y)
    return line_y


def _heads(s, k, p, ax, top, height, dates):
    """The day heads: the day name and, if dates, the date (and in the page layout, the game count)."""
    w = k.w
    for i, d in enumerate(w.days):
        x, cw = ax.span(i, i + 1, p.inset)
        ink, sub = "ink", "mute"
        if k.anchor[i]:
            s.rect(x, top + 4, cw, height - 8, "anchor")
            ink = sub = "stock"
        elif w.no_games[i]:
            s.rect(x, top + 4, cw, height - 8, "hatch", k.hatch)
            sub = "ink"
        elif w.light[i] and not k.spot:
            ink = sub = "mark"
        tx, y = x + 6, top + 8 + p.head * 0.86
        name = f"{d:%a}".upper()
        if w.no_games[i]:
            s.rect(tx - 3, y - p.head * 0.82, text_width(name, p.head, "display") + 6, p.head * 0.94, "grid")
        s.text(tx, y, name, p.head, ink, "display")
        if not dates:
            continue
        date = f"{d:%b} {d.day}"
        if p.gutter:
            date += " · " + (f"{w.games[i]} games" if w.games[i] else "No games")
        style = "text" if sub == "mute" else "label"
        dy = y + p.head_date * 1.35
        if w.no_games[i]:
            dw = text_width(date, p.head_date, style) + 6
            s.rect(tx - 3, dy - p.head_date * 0.9, dw, p.head_date * 1.15, "grid")
        s.text(tx, dy, date, p.head_date, sub, style)


def _chips(s, teams, x, y, width, size, style, pad):
    """Team chips from (x, y top), in rows inside width. Return the y under the last row and the x after it."""
    pad, gap, ch = size * pad, size * 0.2, size * 1.22
    cx, cy = x, y
    for t in teams:
        cw = text_width(t, size, style) + 2 * pad
        if cx > x and cx + cw > x + width:
            cx, cy = x, cy + ch + gap
        color = tokens.TEAM_COLORS[t]
        s.add(f'<g class="chip" data-team="{t}">')
        s.rect(cx, cy, cw, ch, "chip-box", f"fill:{color}")
        s.text(cx + pad, cy + ch / 2 + size * 0.34, t, size, "chip-ink", style, css=f"fill:{tokens.team_ink(color)}")
        s.add("</g>")
        cx += cw + gap
    return cy + ch, cx


def _leg(s, k, p, ax, rung, leg, y0, y1, lead, href):
    """One leg: a white block with its label, its teams and one dot for each game."""
    w = k.w
    x, lw = ax.span(leg.first, leg.last, 3)
    inner, tx = lw - 16, x + 8
    if href:
        s.add(f'<a href="{html.escape(href)}">')
    s.add(f'<g class="leg" data-first="{leg.first}" data-last="{leg.last}">')
    s.rect(x, y0, lw, y1 - y0, "leg-box")
    s.add('<g class="leg-ink">')
    label = f"{leg.games} GM" + (f" · {leg.light} LIGHT" if leg.light else "")
    top = s.lines(tx, y0 + 7, _wrap(label, inner, p.label, "label", sep=" · "), p.label, "ink", "label", 1.12) + 6
    if not leg.games:
        s.lines(tx, top, _wrap("no team plays", inner, p.body, "body"), p.body, "mute", "body")
    elif not leg.scarce:
        text = f"{leg.team_count} teams to choose from"
        s.lines(tx, top, _wrap(text, inner, p.body, "body"), p.body, "mute", "body")
    s.add("</g>")
    if leg.games and leg.scarce:
        size = p.chip_lead if lead else p.chip
        # The page keeps the chip type of v6. A post chip is narrower, so that 2 chips fit in a day column.
        style, pad = ("label", 0.3) if p.gutter else ("display", 0.16)
        bottom, after = _chips(s, leg.named, tx, top, inner, size, style, pad)
        if leg.decisive_b2b:
            # A written callout: the leg depends on a back-to-back that 5 or fewer teams have.
            s.add('<g class="leg-ink">')
            if after + text_width("BACK-TO-BACK", p.tag, "label") <= tx + inner:
                s.text(after + 4, bottom - (size * 1.22 - p.tag * 0.72) / 2, "BACK-TO-BACK", p.tag, "ink", "label")
            else:
                s.text(tx, bottom + p.tag * 1.1, "BACK-TO-BACK", p.tag, "ink", "label")
            s.add("</g>")
    # The game dots at the bottom of the leg. A line joins the dots of a back-to-back.
    cy = y1 - p.dot - 10
    s.add('<g class="leg-ink">')
    for a, b in zip(leg.pattern, leg.pattern[1:]):
        if (b - a).days == 1:
            s.line(ax.mid(w.days.index(a)), cy, ax.mid(w.days.index(b)), cy, "b2b", f"stroke-width:{_f(p.b2b)}")
    for i in range(leg.first, leg.last):
        if w.no_games[i]:
            continue
        d = w.days[i]
        if leg.games and d in leg.pattern:
            if w.light[i]:
                s.circle(ax.mid(i), cy, p.dot, "dot-s game")
            else:
                ring = p.dot / 3.5
                s.circle(ax.mid(i), cy, p.dot - ring / 2, "dot game", f"stroke-width:{_f(ring)}")
            if d in rung.plus_one:
                s.text(ax.mid(i), cy - p.dot - 6, "+1", p.tag, "mark plus", "label", "middle")
        else:
            s.circle(ax.mid(i), cy, p.tick, "tick")
    s.add("</g></g>")
    if href:
        s.add("</a>")


def _gain(rung, n):
    if n == 1:
        return "the best single team"
    if rung.zero_gain:
        return f"+0 · a {_ordinal(n)} add gains nothing"
    return f"+{rung.gain} · buys " + ", ".join(f"{d:%a}" for d in rung.plus_one)


def _tag(s, x, y, text, size):
    """An ink tag with lab-stock text, from (x, y top). Return its width."""
    w = text_width(text, size, "label") + size * 0.6
    s.rect(x, y, w, size * 1.2, "tag-box")
    s.text(x + size * 0.3, y + size * 0.94, text, size, "stock", "label")
    return w


def _rung_info(s, p, rung, n, x, top):
    """The rung totals in the gutter of the page layout."""
    quiet = rung.zero_gain
    s.text(x, top + 12 + p.rung * 0.86, f"{n} ADD" + ("S" if n > 1 else ""), p.rung, "mute", "label")
    y = top + 18 + p.rung + p.total * 0.8
    dim = f"opacity:{tokens.SKYLINE_OPACITIES['quiet']}" if quiet else ""
    s.text(x, y, str(rung.games), p.total, "mute" if quiet else "ink", "display", css=dim)
    y += p.rung * 1.9
    s.text(x, y, "games" + (f" · {rung.light} light" if rung.light else ""), p.rung, "mute")
    gain = _wrap(_gain(rung, n), p.gutter - 8, p.rung, "label")
    y = s.lines(x, y + p.rung * 0.3, gain, p.rung, "ink" if quiet else "mark", "label", 1.15)
    if rung.games < rung.best_games:
        y = s.lines(x, y, [f"(best possible: {rung.best_games})"], p.rung, "mute", "text", 1.15)
    if rung.replan:
        _tag(s, x, y + 4, "RE-PLAN", p.tag)


def _rung_header(s, p, rung, n, x0, x1, y):
    """The rung totals in a header row of a post layout. y: the baseline."""
    adds = f"{n} ADD" + ("S" if n > 1 else "")
    s.text(x0, y, adds, p.rung, "mute", "label")
    x = x0 + text_width(adds, p.rung, "label") + p.rung * 0.5
    total = f"{rung.games} games" + (f" · {rung.light} light" if rung.light else "")
    s.text(x, y, total, p.rung, "ink", "label")
    x += text_width(total, p.rung, "label") + p.rung * 0.5
    if rung.replan:
        _tag(s, x, y - p.tag * 0.94, "RE-PLAN", p.tag)
    s.text(x1, y, _gain(rung, n), p.rung, "ink" if rung.zero_gain else "mark", "label", "end")


def _ladder(s, k, p, ax, top, bottom, href):
    """The ladder from top to bottom: the grid, one rung for each number of adds, then the anchor stripe."""
    w = k.w
    rh = (bottom - top) / len(k.rungs)
    head = 0 if p.gutter else p.rung * 1.5
    # The grid: one zone in the page layout, one zone under the header row of each rung in a post layout.
    zones = [(top, bottom)] if p.gutter else [(top + (n * rh) + head, top + (n + 1) * rh) for n in range(len(k.rungs))]
    for z0, z1 in zones:
        for i in range(DAYS):
            x, cw = ax.span(i, i + 1)
            s.rect(x, z0, cw, z1 - z0, "hatch" if w.no_games[i] else "grid", k.hatch if w.no_games[i] else "")
        for i in range(DAYS + 1):
            s.line(ax.lo(i), z0, ax.lo(i), z1, "day-rule")
    for n, rung in enumerate(k.rungs, start=1):
        rt = top + (n - 1) * rh
        s.line(p.margin, rt, ax.end, rt, "rung-rule first" if n == 1 else "rung-rule")
        if p.gutter:
            _rung_info(s, p, rung, n, p.margin, rt)
        else:
            _rung_header(s, p, rung, n, p.margin, ax.end, rt + head / 2 + p.rung * 0.36)
        s.add(f'<g class="rung{" quiet" if rung.zero_gain else ""}" data-adds="{n}">')
        for leg in rung.legs:
            url = href(rung, leg) if href else None
            _leg(s, k, p, ax, rung, leg, rt + head + 7, rt + rh - 7, k.lead and n == 1, url)
        s.add("</g>")
    for z0, z1 in zones:
        for i in range(DAYS):
            if k.stripe[i]:
                x, cw = ax.span(i, i + 1, p.inset)
                s.rect(x, z0, cw, z1 - z0, "stripe")


def render(week, week_no, layout="page", rungs=None, leg_href=None, theme="light"):
    """The SVG text of the Schedule Skyline of week (a core.skyline.Week).

    layout: "page" (the skyline over the ladder), "skyline" or "ladder" (the 2 images of the post).
    rungs: the ladder to draw, week.rungs when None. The adds page can give the rungs of a roster.
    leg_href: a function (rung, leg) -> URL or None. Each leg with a URL becomes a link.
    theme: "light" or "dark", the token values of core/tokens.py.
    """
    if layout not in LAYOUTS:
        raise ValueError(f"The layout must be one of {LAYOUTS}, not {layout!r}.")
    sid = f"sk-{layout}-{week.start:%Y%m%d}"
    k = _Week(week, rungs, sid)
    p, ax = profile(layout), axis(layout)
    width, height = SIZE
    s = _Svg()
    if layout == "page":
        _title(s, p, 60 + p.title * 0.84, week_no, week.start.year)
        s.line(p.margin, 182, ax.end, 182, "base-rule")
        line_y = _skyline(s, k, p, ax, 190, 490)
        label = (f"{week.light_max} or fewer", "games = light", "night")
        s.lines(p.margin, line_y - 8 - 3 * 12 * 1.2, label, 12, "mark", "label", 1.2)
        s.line(p.margin, 490, ax.end, 490, "base-rule")
        _heads(s, k, p, ax, 490, 62, dates=True)
        _ladder(s, k, p, ax, 560, height - 56, leg_href)
    elif layout == "skyline":
        _title(s, p, p.margin + p.title * 0.84, week_no, week.start.year)
        ky = p.margin + p.title + 52  # the key of the light-night line
        _night_line(s, p, p.margin, p.margin + 64, ky - p.body * 0.34, "sk-key")
        s.text(p.margin + 80, ky, f"{week.light_max} or fewer games = light night", p.body, "mark", "label")
        s.line(p.margin, ky + 26, ax.end, ky + 26, "title-rule")
        bottom = height - p.margin - 110
        _skyline(s, k, p, ax, ky + 40, bottom)
        s.line(p.margin, bottom, ax.end, bottom, "base-rule")
        _heads(s, k, p, ax, bottom, 110, dates=True)
    else:
        _title(s, p, p.margin + p.title * 0.84, week_no, week.start.year)
        top = p.margin + p.title + 14
        _heads(s, k, p, ax, top, 60, dates=False)
        _ladder(s, k, p, ax, top + 64, height - p.margin, leg_href)
    label = f"Schedule Skyline, week {week_no}, {week.days[0]:%b} {week.days[0].day} to {week.days[-1]:%b} {week.days[-1].day}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" id="{sid}" class="skyline skyline-{layout}" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{label}">'
        f"<title>{label}</title><style>{_css(sid, theme)}</style><defs>{_hatch(sid)}</defs>"
        f'<rect class="paper" width="{width}" height="{height}"/>' + "".join(s.parts) + "</svg>"
    )


def post_images(week, week_no, theme="light"):
    """The 2 images of the Bluesky post: (the skyline SVG, the ladder SVG), each 1080x1350."""
    return render(week, week_no, "skyline", theme=theme), render(week, week_no, "ladder", theme=theme)


TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def text_boxes(svg):
    """[(text, font size, (x, top, width, height))] of each <text> of svg, from the estimate of text_width()."""
    out = []
    for attrs, inner in TEXT.findall(svg):
        a = dict(ATTR.findall(attrs))
        size = float(re.search(r"font-size:([\d.]+)px", a["style"]).group(1))
        t = html.unescape(re.sub(r"<[^>]+>", "", inner))
        w = text_width(t, size, a["data-style"])
        x = float(a["x"]) - {"middle": w / 2, "end": w}.get(a.get("text-anchor"), 0)
        out.append((t, size, (x, float(a["y"]) - size * 0.76, w, size * 0.96)))
    return out


def text_overlaps(svg):
    """The pairs of texts of svg whose estimated boxes overlap, as [(text, text)]. An empty list means no overlap."""
    boxes = text_boxes(svg)
    pairs = []
    for i, (a, _, (x, y, w, h)) in enumerate(boxes):
        for b, _, (x2, y2, w2, h2) in boxes[i + 1 :]:
            if x < x2 + w2 and x2 < x + w and y < y2 + h2 and y2 < y + h:
                pairs.append((a, b))
    return pairs
