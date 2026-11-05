"""Schedule Skyline: the SVG of one week, drawn from the facts of core/skyline.py (issue 235).

render() gives one of 5 layouts. "page" is the desktop layout: the skyline over the ladder, with the days from left
to right. The other 4 layouts are tall: the days go from top to bottom, Monday at the top. "phone-skyline" and
"phone-ladder" are the 2 panels of the phone page, each shown at 390x780. "skyline" and "ladder" are the 2 images of
the Bluesky post, each 1080x1350. The tall layouts keep all text at 11 px or more at a display width of 390 px
(DESIGN.md "The Phone Legibility Rule"). DayAxis holds the position and the size of each day, in all 5 layouts.
The colors come from core/tokens.py. This module writes no files. DESIGN.md "Poster mode" gives the rules.
"""

import html
import re
from dataclasses import dataclass

from fantasyhoops.core import tokens
from fantasyhoops.core.skyline import DAYS

WIDE, TALL = ("page",), ("phone-skyline", "phone-ladder", "skyline", "ladder")
LAYOUTS = WIDE + TALL
UNITS = 1080  # the width of each layout, in SVG units
# (the height in units, the display width, the display height) of each layout
FRAMES = {
    "page": (1350, 1080, 1350),
    "phone-skyline": (2160, 390, 780),
    "phone-ladder": (2160, 390, 780),
    "skyline": (1350, 1080, 1350),
    "ladder": (1350, 1080, 1350),
}
TITLE, BRAND = "SCHEDULE ", "SKYLINE"  # "Schedule" in lab-ink, "Skyline" in mark

# The roles of the marks that the renderer draws in `mark` (data-mark). The test ties each role to an item of the
# DESIGN.md "Named Exception Rule", or to the site use of `mark` for headings ("title").
MARK_ROLES = (
    "title",
    "anchor",
    "gain-tag",
    "night-line",
    "game-dot",
    "light-block",
    "light-count",
    "light-head",
    "gain-text",
    "line-key",
)

# The 5 type styles of the Skyline: (font weight, font stretch in %, the width of each character of CHARS in
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
    "cond": (
        500,
        62,
        "448 458 490 493 436 384 513 490 210 379 477 376 625 492 524 449 524 479 428 428 482 443 658 464 478 443 "
        "396 393 373 393 391 224 368 386 184 181 369 183 590 387 393 393 393 237 337 215 387 323 518 359 322 342 "
        "412 412 412 412 412 412 412 412 412 412 476 476 240 324 324 210 310 195 195 127",
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
    """The day axis of a layout: the position and the size of each day, from start along the axis.

    All day positions of the renderer come from this class. In the page layout the axis is x (Monday at the left).
    In a tall layout the axis is y (Monday at the top). weights: the relative size of each day.
    """

    start: float
    length: float
    weights: tuple = (1,) * DAYS

    def lo(self, i):
        return self.start + self.length * sum(self.weights[:i]) / sum(self.weights)

    def mid(self, i):
        return (self.lo(i) + self.lo(i + 1)) / 2

    @property
    def end(self):
        return self.start + self.length

    def span(self, first, last, inset=0.0):
        """(position, size) of the days first to last (last exclusive), inset at each end."""
        return self.lo(first) + inset, self.lo(last) - self.lo(first) - 2 * inset


@dataclass(frozen=True)
class _Profile:
    """The sizes of one layout, in SVG units. A text size is the font size."""

    margin: float  # the margin of the frame
    gutter: float  # page: the column left of the days for the rung totals. tall: the column of the day labels
    title: float
    week: float
    count: float  # the game count of a skyline bar
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
    total: float  # the game total of a rung
    dot: float  # the radius of a game dot on a light night
    tick: float  # the radius of a tick
    b2b: float  # the width of a back-to-back line
    line: float  # the width of the light-night line
    halo: float  # the width of the paper halo on each side of the light-night line
    inset: float  # the gap between a skyline bar and the day rule


PAGE = _Profile(64, 96, 90, 30, 22, 40, 24, 12, 11, 17, 30, 14, 12, 22, 13, 58, 8.5, 2, 2, 1.5, 2.5, 4)
# A tall layout: 32 units on a 1080 unit width are 11.6 px at a display width of 390 px.
TALL_PROFILE = _Profile(36, 132, 64, 32, 44, 60, 48, 32, 32, 32, 44, 32, 32, 32, 32, 60, 14, 6, 6, 4, 4, 8)
NO_GAME_WEIGHT = 0.6  # the size of a no-game day on a tall axis, relative to a day with games


def profile(layout):
    """The _Profile of layout."""
    return PAGE if layout == "page" else TALL_PROFILE


def text_width(text, size, style="text"):
    """The width of text in SVG units, at the font size size and the type style style of STYLES, plus 10% (small text on a phone screen renders wider)."""
    widths = STYLES[style][2]
    return sum(widths.get(c, widths["M"]) for c in text) * size * 1.1


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
    """The elements of one SVG, in paint order. mark: the MARK_ROLES role of an element drawn in `mark`."""

    def __init__(self):
        self.parts = []

    def add(self, part):
        self.parts.append(part)

    @staticmethod
    def _extra(style, mark):
        return (f' style="{style}"' if style else "") + (f' data-mark="{mark}"' if mark else "")

    def rect(self, x, y, w, h, cls, style="", mark=None):
        self.add(
            f'<rect class="{cls}" x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}"{self._extra(style, mark)}/>'
        )

    def line(self, x1, y1, x2, y2, cls, style="", mark=None):
        self.add(
            f'<line class="{cls}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"{self._extra(style, mark)}/>'
        )

    def circle(self, cx, cy, r, cls, style="", mark=None):
        self.add(f'<circle class="{cls}" cx="{_f(cx)}" cy="{_f(cy)}" r="{_f(r)}"{self._extra(style, mark)}/>')

    def text(self, x, y, s, size, cls, style="text", anchor="start", css="", inner=None, mark=None):
        weight, stretch, _ = STYLES[style]
        st = f"font-size:{_f(size)}px;font-weight:{weight};font-stretch:{stretch}%;{css}"
        body = inner if inner is not None else html.escape(s)
        mk = f' data-mark="{mark}"' if mark else ""
        self.add(
            f'<text class="{cls}" data-style="{style}" x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" '
            f'style="{st}"{mk}>{body}</text>'
        )

    def lines(self, x, top, lines, size, cls, style, lead=1.1, mark=None):
        """Text lines from top (the top of the first line). Return the y under the last line."""
        for n, t in enumerate(lines):
            self.text(x, top + size * 0.86 + n * size * lead, t, size, cls, style, mark=mark)
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
        ".blk-lt, .anchor, .plus-box": f"fill: {c['mark']}",
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
    scoped = {", ".join(f"#{sid} {sel}" for sel in k.split(", ")) if k else f"#{sid}": v for k, v in rules.items()}
    return "\n".join(f"{k} {{ {v}; }}" for k, v in scoped.items())


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

    def light_night(self, i):
        """True if day i is drawn as a light night: a light night in a week with no anchor night."""
        return self.w.light[i] and not self.spot


def _title(s, p, y, size, week_no, year):
    brand = f'<tspan class="mark" data-mark="title">{BRAND}</tspan>'
    s.text(p.margin, y, TITLE + BRAND, size, "ink", "display", inner=f"{TITLE}{brand}")
    x = p.margin + text_width(TITLE + BRAND, size, "display") + p.week * 0.4
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


def _night_line(s, p, x0, y0, x1, y1, cls="sk-line"):
    """The light-night line: a dashed mark line on a paper halo. Its width stays the same when a page scales it."""
    keep = "vector-effect:non-scaling-stroke"
    s.add(f'<g class="{cls}">')
    s.line(x0, y0, x1, y1, "halo", f"stroke-width:{_f(p.line + 2 * p.halo)};{keep}")
    s.line(x0, y0, x1, y1, "night-line", f"stroke-width:{_f(p.line)};stroke-dasharray:5 4;{keep}", "night-line")
    s.add("</g>")


def _gain(rung, n):
    if n == 1:
        return "the best single team"
    if rung.zero_gain:
        return f"+0 · a {_ordinal(n)} add gains nothing"
    return f"+{rung.gain} · buys " + ", ".join(f"{d:%a}" for d in rung.plus_one)


def _gain_ink(rung):
    """(class, mark role) of the gain text: ink on a zero-gain rung, else mark."""
    return ("ink", None) if rung.zero_gain else ("mark", "gain-text")


def _tag(s, x, y, text, size):
    """An ink tag with lab-stock text, from (x, y top). Return its width."""
    w = text_width(text, size, "label") + size * 0.6
    s.rect(x, y, w, size * 1.2, "tag-box")
    s.text(x + size * 0.3, y + size * 0.94, text, size, "stock", "label")
    return w


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


def _dot(s, k, p, i, x, y, plus):
    """The game dot of day i at (x, y). On a bought game, a tall layout draws the "+1" tag in place of the dot."""
    if plus and k.w.days[i] in plus:
        w = text_width("+1", p.tag, "label") + p.tag * 0.4
        s.rect(x - w / 2, y - p.tag * 0.62, w, p.tag * 1.24, "plus-box", mark="gain-tag")
        s.text(x, y + p.tag * 0.34, "+1", p.tag, "stock plus", "label", "middle")
    elif k.w.light[i]:
        s.circle(x, y, p.dot, "dot-s game", mark="game-dot")
    else:
        ring = p.dot / 3.5
        s.circle(x, y, p.dot - ring / 2, "dot game", f"stroke-width:{_f(ring)}", mark="game-dot")


def _leg_open(s, leg, href):
    if href:
        s.add(f'<a href="{html.escape(href)}">')
    s.add(f'<g class="leg" data-first="{leg.first}" data-last="{leg.last}">')


def _leg_close(s, href):
    s.add("</g></g>")
    if href:
        s.add("</a>")


# ---------------------------------------------------------------- the page layout: the days from left to right


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
            s.rect(x, bottom - h, cw, h, "anchor", mark="anchor")
            if h >= p.count_big + 12:
                s.text(
                    ax.mid(i), bottom - h + p.count_big * 0.86 + 6, str(g), p.count_big, "stock", "display", "middle"
                )
            else:
                s.text(x, bottom - h - 6, str(g), p.count_big, "mark", "display", mark="light-count")
        else:
            lt = k.light_night(i)
            for n in range(g):
                cls = "blk-dim" if k.spot else "blk-lt" if lt else "blk"
                s.rect(x, bottom - n * pitch - bh, cw, bh, cls, mark="light-block" if lt else None)
            size, ink = (p.count_big, "mark") if lt else (p.count, "mute" if k.spot else "ink")
            y = bottom - h + (pitch - bh) - 6
            if y - size * 0.8 - p.halo < line_y < y + p.halo:  # the count stays clear of the light-night line
                y = line_y - p.line - p.halo - 4
            s.text(x, y, str(g), size, ink, "display", mark="light-count" if lt else None)
    for a, b in _runs(w.no_games):
        x, cw = ax.span(a, b, p.inset)
        _none_box(s, k, p, a, b, x + cw / 2, bottom - 8, cw - 16, "bottom")
    _night_line(s, p, p.margin, line_y, ax.end, line_y)
    return line_y


def _none_box(s, k, p, a, b, cx, edge, width, where):
    """The "NO NBA GAMES" box of the no-game days a to b. where: "bottom" (edge is the bottom) or "middle"."""
    lines = _wrap("NO NBA GAMES", width, p.none, "display")
    if b - a > 1:
        lines.append(f"{k.w.days[a]:%a}–{k.w.days[b - 1]:%a}")
    bw = max(text_width(t, p.none, "display") for t in lines) + 16
    bh = p.none * 1.15 * len(lines) + 12
    by = edge - bh if where == "bottom" else edge - bh / 2
    s.rect(cx - bw / 2, by, bw, bh, "none-box")
    for n, t in enumerate(lines):
        s.text(cx, by + 6 + p.none * 0.86 + n * p.none * 1.15, t, p.none, "ink", "display", "middle")


def _heads(s, k, p, ax, top, height):
    """The day heads of the page layout: the day name, the date and the game count."""
    w = k.w
    for i, d in enumerate(w.days):
        x, cw = ax.span(i, i + 1, p.inset)
        ink, sub, mark = "ink", "mute", None
        if k.anchor[i]:
            s.rect(x, top + 4, cw, height - 8, "anchor", mark="anchor")
            ink = sub = "stock"
        elif w.no_games[i]:
            s.rect(x, top + 4, cw, height - 8, "hatch", k.hatch)
            sub = "ink"
        elif k.light_night(i):
            ink, sub, mark = "mark", "mark", "light-head"
        tx, y = x + 6, top + 8 + p.head * 0.86
        name = f"{d:%a}".upper()
        if w.no_games[i]:
            s.rect(tx - 3, y - p.head * 0.82, text_width(name, p.head, "display") + 6, p.head * 0.94, "grid")
        s.text(tx, y, name, p.head, ink, "display", mark=mark)
        date = f"{d:%b} {d.day} · " + (f"{w.games[i]} games" if w.games[i] else "No games")
        style = "text" if sub == "mute" else "label"
        dy = y + p.head_date * 1.35
        if w.no_games[i]:
            dw = text_width(date, p.head_date, style) + 6
            s.rect(tx - 3, dy - p.head_date * 0.9, dw, p.head_date * 1.15, "grid")
        s.text(tx, dy, date, p.head_date, sub, style, mark=mark)


def _leg(s, k, p, ax, rung, leg, y0, y1, lead, href):
    """One leg of the page layout: a white block with its label, its teams and one dot for each game."""
    w = k.w
    x, lw = ax.span(leg.first, leg.last, 3)
    inner, tx = lw - 16, x + 8
    _leg_open(s, leg, href)
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
        bottom, after = _chips(s, leg.named, tx, top, inner, size, "label", 0.3)
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
        if leg.games and w.days[i] in leg.pattern:
            _dot(s, k, p, i, ax.mid(i), cy, None)
            if w.days[i] in rung.plus_one:
                s.text(ax.mid(i), cy - p.dot - 6, "+1", p.tag, "mark plus", "label", "middle", mark="gain-tag")
        else:
            s.circle(ax.mid(i), cy, p.tick, "tick")
    _leg_close(s, href)


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
    cls, mark = _gain_ink(rung)
    y = s.lines(x, y + p.rung * 0.3, gain, p.rung, cls, "label", 1.15, mark)
    if rung.games < rung.best_games:
        y = s.lines(x, y, [f"(best possible: {rung.best_games})"], p.rung, "mute", "text", 1.15)
    if rung.replan:
        _tag(s, x, y + 4, "RE-PLAN", p.tag)


def _ladder(s, k, p, ax, top, bottom, href):
    """The ladder of the page layout: the grid, one rung for each number of adds, then the anchor stripe."""
    w = k.w
    rh = (bottom - top) / len(k.rungs)
    for i in range(DAYS):
        x, cw = ax.span(i, i + 1)
        s.rect(x, top, cw, bottom - top, "hatch" if w.no_games[i] else "grid", k.hatch if w.no_games[i] else "")
    for i in range(DAYS + 1):
        s.line(ax.lo(i), top, ax.lo(i), bottom, "day-rule")
    for n, rung in enumerate(k.rungs, start=1):
        rt = top + (n - 1) * rh
        s.line(p.margin, rt, ax.end, rt, "rung-rule first" if n == 1 else "rung-rule")
        _rung_info(s, p, rung, n, p.margin, rt)
        s.add(f'<g class="rung{" quiet" if rung.zero_gain else ""}" data-adds="{n}">')
        for leg in rung.legs:
            url = href(rung, leg) if href else None
            _leg(s, k, p, ax, rung, leg, rt + 7, rt + rh - 7, k.lead and n == 1, url)
        s.add("</g>")
    for i in range(DAYS):
        if k.stripe[i]:
            x, cw = ax.span(i, i + 1, p.inset)
            s.rect(x, top, cw, bottom - top, "stripe", mark="anchor")


def _page(s, k, p, ax, week_no, href):
    w = k.w
    _title(s, p, 60 + p.title * 0.84, p.title, week_no, w.start.year)
    s.line(p.margin, 182, ax.end, 182, "base-rule")
    line_y = _skyline(s, k, p, ax, 190, 490)
    label = (f"{w.light_max} or fewer", "games = light", "night")
    s.lines(p.margin, line_y - 8 - 3 * 12 * 1.2, label, 12, "mark", "label", 1.2, "line-key")
    s.line(p.margin, 490, ax.end, 490, "base-rule")
    _heads(s, k, p, ax, 490, 62)
    _ladder(s, k, p, ax, 560, FRAMES["page"][0] - 56, href)


# ---------------------------------------------------------------- the tall layouts: the days from top to bottom


def _rung_head(s, p, rung, n, x, top, width, draw=True):
    """The head of one rung column: the add count, the game total, the light-night games and the gain.

    Return the height of the head. draw=False only measures it.
    """
    t = _Svg() if not draw else s
    quiet = rung.zero_gain
    y = top + p.rung * 0.86
    t.text(x, y, f"{n} ADD" + ("S" if n > 1 else ""), p.rung, "mute", "label")
    y += p.total * 0.95
    dim = f"opacity:{tokens.SKYLINE_OPACITIES['quiet']}" if quiet else ""
    total = str(rung.games)
    t.text(x, y, total, p.total, "mute" if quiet else "ink", "display", css=dim)
    games = "games" + (f" · {rung.light} light" if rung.light else "")
    tx = x + text_width(total, p.total, "display") + 6
    if tx + text_width(games, p.rung, "cond") <= x + width:
        t.text(tx, y, games, p.rung, "mute", "cond")
        bottom = y + p.rung * 0.3
    else:  # the light-night games go on a line of their own
        t.text(tx, y, "games", p.rung, "mute", "cond")
        bottom = t.lines(x, y + p.rung * 0.3, [f"{rung.light} light"], p.rung, "mute", "cond", 1.12)
    cls, mark = _gain_ink(rung)
    bottom = t.lines(x, bottom + 2, _wrap(_gain(rung, n), width, p.rung, "label"), p.rung, cls, "label", 1.12, mark)
    if rung.games < rung.best_games:
        bottom = t.lines(x, bottom, [f"(best: {rung.best_games})"], p.rung, "mute", "text", 1.12)
    if rung.replan:
        _tag(t, x, bottom + 6, "RE-PLAN", p.tag)
        bottom += 6 + p.tag * 1.2
    return bottom - top


def _heads_tall(s, k, p, ax):
    """The day labels of a tall layout: the day name over the date, in the label column at the left."""
    w = k.w
    for i, d in enumerate(w.days):
        y, h = ax.span(i, i + 1, 4)
        ink, sub, mark = "ink", "mute", None
        if k.anchor[i]:
            s.rect(p.margin, y, p.gutter - 8, h, "anchor", mark="anchor")
            ink = sub = "stock"
        elif k.light_night(i):
            ink, sub, mark = "mark", "mark", "light-head"
        yc = ax.mid(i)
        s.text(p.margin + 8, yc - 2, f"{d:%a}".upper(), p.head, ink, "display", mark=mark)
        style = "text" if sub == "mute" else "label"
        s.text(p.margin + 8, yc - 2 + p.head_date * 1.15, f"{d:%b} {d.day}", p.head_date, sub, style, mark=mark)


def _rows(s, ax, x0, x1, first_ink=False):
    for i in range(DAYS + 1):
        s.line(x0, ax.lo(i), x1, ax.lo(i), "rung-rule first" if first_ink and i == 0 else "day-rule")


def _skyline_tall(s, k, p, ax):
    """The tall skyline: one row for each day, a bar of one block for each game, and the light-night line."""
    w = k.w
    x0, x1 = p.margin + p.gutter, UNITS - p.margin
    bx0 = x0 + 6
    room = text_width("15", p.count_big, "display") + 14
    pitch = (x1 - room - bx0) / w.scale_max
    bw = pitch * 0.76
    line_x = bx0 + w.light_max * pitch - (pitch - bw) / 2
    clear = p.line / 2 + p.halo + 4  # a count keeps this distance from the light-night line
    for i in range(DAYS):
        y, h = ax.span(i, i + 1, p.inset)
        bh = min(h * 0.62, 110)
        yc, g = ax.mid(i), w.games[i]
        if w.no_games[i]:
            s.rect(x0, y, x1 - x0, h, "hatch", k.hatch)
            continue
        length = g * pitch - (pitch - bw)
        size, ink, mark = p.count, "mute" if k.spot else "ink", None
        if k.anchor[i]:
            s.rect(bx0, yc - bh / 2, length, bh, "anchor", mark="anchor")
            size, ink, mark = p.count_big, "mark", "light-count"
            if length >= text_width(str(g), size, "display") + 24:
                s.text(bx0 + length - 12, yc + size * 0.34, str(g), size, "stock", "display", "end")
                continue
        else:
            lt = k.light_night(i)
            for n in range(g):
                cls = "blk-dim" if k.spot else "blk-lt" if lt else "blk"
                s.rect(bx0 + n * pitch, yc - bh / 2, bw, bh, cls, mark="light-block" if lt else None)
            if lt:
                size, ink, mark = p.count_big, "mark", "light-count"
        tx = bx0 + length + 12
        tw = text_width(str(g), size, "display")
        if tx < line_x + clear and tx + tw > line_x - clear:  # the count stays clear of the light-night line
            tx = line_x + clear
        s.text(tx, yc + size * 0.34, str(g), size, ink, "display", mark=mark)
    # The "NO NBA GAMES" box goes in the wider part of the row, at one side of the light-night line.
    left, right = (x0 + 8, line_x - clear - 8), (line_x + clear + 8, x1 - 8)
    lo, hi = max((left, right), key=lambda r: r[1] - r[0])
    for a, b in _runs(w.no_games):
        _none_box(s, k, p, a, b, (lo + hi) / 2, (ax.lo(a) + ax.lo(b)) / 2, hi - lo - 16, "middle")
    _night_line(s, p, line_x, ax.start - 8, line_x, ax.end)


def _leg_tall(s, k, p, ax, rung, leg, x, width, lead, href):
    """One leg of a tall layout: a white block down the rows of its days.

    The dots go in a column at the left. The label and the teams go at the right of the dots.
    """
    w = k.w
    y, h = ax.span(leg.first, leg.last, 5)
    dot_x = x + 8 + p.tag * 0.75
    fx = dot_x + p.tag * 0.75 + 8
    inner = x + width - 8 - fx
    _leg_open(s, leg, href)
    s.rect(x, y, width, h, "leg-box")
    s.add('<g class="leg-ink">')
    top = s.lines(fx, y + 8, [f"{leg.games} GM"], p.label, "ink", "label", 1.12) + 6
    if not leg.games:
        s.lines(fx, top, _wrap("no team plays", inner, p.body, "cond"), p.body, "mute", "cond")
    elif not leg.scarce:
        text = f"{leg.team_count} teams to choose from"
        s.lines(fx, top, _wrap(text, inner, p.body, "cond"), p.body, "mute", "cond")
    s.add("</g>")
    if leg.games and leg.scarce:
        size = p.chip_lead if lead else p.chip
        bottom, after = _chips(s, leg.named, fx, top, inner, size, "display", 0.16)
        if leg.decisive_b2b:
            # A written callout: the leg depends on a back-to-back that 5 or fewer teams have.
            s.add('<g class="leg-ink">')
            if after + text_width("B2B", p.tag, "label") <= fx + inner:
                s.text(after + 2, bottom - (size * 1.22 - p.tag * 0.72) / 2, "B2B", p.tag, "ink", "label")
            else:
                s.text(fx, bottom + p.tag * 1.1, "B2B", p.tag, "ink", "label")
            s.add("</g>")
    s.add('<g class="leg-ink">')
    for a, b in zip(leg.pattern, leg.pattern[1:]):
        if (b - a).days == 1:
            s.line(dot_x, ax.mid(w.days.index(a)), dot_x, ax.mid(w.days.index(b)), "b2b", f"stroke-width:{_f(p.b2b)}")
    for i in range(leg.first, leg.last):
        if w.no_games[i]:
            continue
        if leg.games and w.days[i] in leg.pattern:
            _dot(s, k, p, i, dot_x, ax.mid(i), rung.plus_one)
        else:
            s.circle(dot_x, ax.mid(i), p.tick, "tick")
    _leg_close(s, href)


def _ladder_tall(s, k, p, ax, head_top, head_h, href):
    """The tall ladder: one column for each rung, with its head on top. The days are the rows."""
    w = k.w
    x0, x1 = p.margin + p.gutter, UNITS - p.margin
    cw = (x1 - x0) / len(k.rungs)
    for i in range(DAYS):
        y, h = ax.span(i, i + 1)
        s.rect(x0, y, x1 - x0, h, "hatch" if w.no_games[i] else "grid", k.hatch if w.no_games[i] else "")
    _rows(s, ax, p.margin, x1, first_ink=True)
    for c in range(len(k.rungs) + 1):
        s.line(x0 + c * cw, ax.start, x0 + c * cw, ax.end, "day-rule")
    for n, rung in enumerate(k.rungs, start=1):
        cx = x0 + (n - 1) * cw
        _rung_head(s, p, rung, n, cx + 8, head_top, cw - 14)
        s.add(f'<g class="rung{" quiet" if rung.zero_gain else ""}" data-adds="{n}">')
        for leg in rung.legs:
            url = href(rung, leg) if href else None
            _leg_tall(s, k, p, ax, rung, leg, cx + 5, cw - 10, k.lead and n == 1, url)
        s.add("</g>")
    for i in range(DAYS):
        if k.stripe[i]:
            y, h = ax.span(i, i + 1, 3)
            s.rect(x0, y, x1 - x0, h, "stripe", mark="anchor")


def _tall_top(layout, week, rungs):
    """(the y of the title, the y of the top of the rung heads, the height of the heads, the y of the day axis)."""
    p = TALL_PROFILE
    title_y = p.margin + p.title * 0.84
    rule_y = title_y + 22
    if layout.endswith("skyline"):
        return title_y, rule_y, 0, rule_y + 90  # the key of the light-night line goes between the rule and the axis
    cw = (UNITS - 2 * p.margin - p.gutter) / len(rungs)
    head_h = max(_rung_head(None, p, r, n, 0, 0, cw - 14, draw=False) for n, r in enumerate(rungs, start=1))
    return title_y, rule_y + 16, head_h, rule_y + 16 + head_h + 14


def axis(layout, week=None, rungs=None):
    """The DayAxis of layout. A tall layout needs week (and rungs, week.rungs when None), for its no-game days."""
    p = profile(layout)
    if layout in WIDE:
        return DayAxis(p.margin + p.gutter, UNITS - 2 * p.margin - p.gutter)
    rungs = tuple(rungs if rungs is not None else week.rungs)
    start = _tall_top(layout, week, rungs)[3]
    weights = tuple(NO_GAME_WEIGHT if none else 1 for none in week.no_games)
    return DayAxis(start, FRAMES[layout][0] - p.margin - start, weights)


def _tall(s, k, p, ax, layout, week_no, href):
    w = k.w
    title_y, top, head_h, _ = _tall_top(layout, w, k.rungs)
    ladder = layout.endswith("ladder")
    _title(s, p, title_y, p.title, week_no, w.start.year)
    s.line(p.margin, title_y + 22, UNITS - p.margin, title_y + 22, "title-rule")
    if ladder:
        _ladder_tall(s, k, p, ax, top, head_h, href)
    else:
        ky = title_y + 22 + 54  # the key of the light-night line
        _night_line(s, p, p.margin, ky - p.body * 0.34, p.margin + 64, ky - p.body * 0.34, "sk-key")
        s.text(
            p.margin + 80, ky, f"{w.light_max} or fewer games = light night", p.body, "mark", "label", mark="line-key"
        )
        _rows(s, ax, p.margin, UNITS - p.margin)
        _skyline_tall(s, k, p, ax)
    _heads_tall(s, k, p, ax)


def render(week, week_no, layout="page", rungs=None, leg_href=None, theme="light"):
    """The SVG text of the Schedule Skyline of week (a core.skyline.Week).

    layout: one of LAYOUTS. "page": the desktop layout. "phone-skyline", "phone-ladder": the 2 phone panels.
    "skyline", "ladder": the 2 images of the post.
    rungs: the ladder to draw, week.rungs when None. The adds page can give the rungs of a roster.
    leg_href: a function (rung, leg) -> URL or None. Each leg with a URL becomes a link.
    theme: "light" or "dark", the token values of core/tokens.py.
    """
    if layout not in LAYOUTS:
        raise ValueError(f"The layout must be one of {LAYOUTS}, not {layout!r}.")
    sid = f"sk-{layout}-{week.start:%Y%m%d}"
    k = _Week(week, rungs, sid)
    p, ax = profile(layout), axis(layout, week, k.rungs)
    s = _Svg()
    if layout in WIDE:
        _page(s, k, p, ax, week_no, leg_href)
    else:
        _tall(s, k, p, ax, layout, week_no, leg_href)
    height, dw, dh = FRAMES[layout]
    label = f"Schedule Skyline, week {week_no}, {week.days[0]:%b} {week.days[0].day} to {week.days[-1]:%b} {week.days[-1].day}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" id="{sid}" class="skyline skyline-{layout}" '
        f'viewBox="0 0 {UNITS} {height}" width="{dw}" height="{dh}" role="img" aria-label="{label}">'
        f"<title>{label}</title><style>{_css(sid, theme)}</style><defs>{_hatch(sid)}</defs>"
        f'<rect class="paper" width="{UNITS}" height="{height}"/>' + "".join(s.parts) + "</svg>"
    )


def post_images(week, week_no, theme="light"):
    """The 2 images of the Bluesky post: (the skyline SVG, the ladder SVG), each 1080x1350."""
    return render(week, week_no, "skyline", theme=theme), render(week, week_no, "ladder", theme=theme)


def phone_panels(week, week_no, rungs=None, leg_href=None, theme="light"):
    """The 2 panels of the phone page: (the skyline SVG, the ladder SVG), each shown at 390x780."""
    return (
        render(week, week_no, "phone-skyline", theme=theme),
        render(week, week_no, "phone-ladder", rungs, leg_href, theme),
    )


TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def text_boxes(svg):
    """[(text, font size, (x, top, width, height))] of each <text> of svg, in SVG units, from text_width()."""
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


def display_scale(layout):
    """The display width of layout / its width in SVG units: the px of one SVG unit on the screen."""
    return FRAMES[layout][1] / UNITS
