"""The shared chart style of the site (#185): CSS classes, SVG helpers, label placement and two checks.

The rules are in the DESIGN.md "Charts" section. The approved look is "After + tooltips" in
docs/design/players-sample.html.

1. CHART_STYLE: the CSS of the chart marks and the chart text. publish.shell() puts it in place of __CHART_CSS__
   in a page template. The sizes come from core/tokens.py as CSS custom properties (--lab-c-*).
2. The SVG helpers (hero_line() to label()) give the SVG text of each mark of the DESIGN.md "Marks" table.
3. The label placement (end_labels(), point_label(), band_label(), now_proj()) follows "Label placement".
4. style_problems() finds an inline stroke width, a raw color or a chart outside the shared classes in a page.
5. label_overlaps() finds the chart labels of a page that overlap.

The module writes no files.
"""

import html
import math
import re
from html.parser import HTMLParser
from typing import NamedTuple

from fantasyhoops.core import tokens

CHAR_W = 5.6  # the estimated width of one character of chart text, in px
TXT_H = 11  # the estimated height of a line of chart text, in px
END_GAP = 13  # the smallest gap between two end labels
END_DX = 8  # the end labels sit this far right of the plot
END_INSET = 4  # the end labels stay this far inside the top and the bottom of the plot
PLOT_INSET = 2  # a placed label stays this far inside the plot
SIDE_DX = 7  # a dud, spike or range exit label: the distance to the right or the left of the mark
SIDE_DY = 8  # a dud, spike or range exit label: the distance above or below the mark
BAND_INSET = 4  # the band label: the distance from the edges of the band
NOW_PROJ_APART = 34  # above this distance, "now" and "proj" both sit above the track
NOW_PROJ_DY = 10  # "now" and "proj" sit this far above the track
PROJ_BELOW_DY = 18  # the baseline of "proj" below the track, when the two dots are close
NOW_PROJ_DX = 2  # the shift of "now" and "proj" away from the other dot, when the two dots are close


def _n(value):
    """A number for SVG or CSS text: at most 2 decimals, with no trailing zeros."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _vars():
    """The CSS custom properties of the chart sizes, from core/tokens.py."""
    sets = [
        ("sw", tokens.CHART_STROKES, "px"),
        ("op", tokens.CHART_OPACITIES, ""),
        ("fs", tokens.CHART_TEXT, "px"),
        ("fw", tokens.CHART_WEIGHTS, ""),
    ]
    return " ".join(
        f"--lab-c-{kind}-{name}: {_n(v)}{unit};" for kind, values, unit in sets for name, v in values.items()
    )


# Each class takes its sizes from var(--lab-c-*) and its colors from the color tokens. No class has a literal size.
CLASS_RULES = """svg.lab-chart { display: block; width: 100%; height: auto; font-variant-numeric: tabular-nums; }
.lab-c-hero { fill: none; stroke: var(--mark); stroke-width: var(--lab-c-sw-hero); stroke-linejoin: round;
  stroke-linecap: round; }
.lab-c-hero-dot { fill: var(--mark); stroke: var(--lab-stock); stroke-width: var(--lab-c-sw-ring); }
.lab-c-second { fill: none; stroke: var(--lamp-off); stroke-width: var(--lab-c-sw-second); stroke-linejoin: round;
  opacity: var(--lab-c-op-second); }
.lab-c-game { fill: var(--lamp-off); opacity: var(--lab-c-op-game); }
.lab-c-dud { fill: var(--lab-red); }
.lab-c-spike { fill: var(--lab-ink); }
.lab-c-band { fill: var(--zebra); }
.lab-c-ref, .lab-c-track { stroke: var(--lab-rule); stroke-width: var(--lab-c-sw-rule); }
.lab-c-conn { stroke: var(--lamp-off); stroke-width: var(--lab-c-sw-second); opacity: var(--lab-c-op-conn); }
.lab-c-proj { fill: var(--lab-stock); stroke: var(--lamp-off); stroke-width: var(--lab-c-sw-second); }
.lab-c-cross { stroke: var(--lamp-off); stroke-width: var(--lab-c-sw-rule); }
.lab-c-hit { fill: transparent; }
.lab-c-hit:focus-visible { outline: none; stroke: var(--lamp-off); stroke-width: var(--lab-c-sw-rule); }
.lab-c-tick { fill: var(--lab-mute); font-size: var(--lab-c-fs-small); font-weight: var(--lab-c-fw-small); }
.lab-c-label { fill: var(--lab-ink); font-size: var(--lab-c-fs-label); font-weight: var(--lab-c-fw-label); }
.lab-c-exit { fill: var(--lab-red); font-size: var(--lab-c-fs-label); font-weight: var(--lab-c-fw-exit); }
.lab-c-state { color: var(--lab-mute); font-size: var(--lab-c-fs-label); font-weight: var(--lab-c-fw-small); }
.lab-c-state b { color: var(--lab-ink); font-weight: var(--lab-c-fw-exit); }
.lab-c-empty { border: var(--lab-c-sw-empty) dashed var(--lamp-off); color: var(--lab-mute); text-align: center; }"""

CHART_STYLE = f"""/* The shared chart style (issue 185): the DESIGN.md "Charts" rules. The sizes come from core/tokens.py. */
:root {{ {_vars()} }}
{CLASS_RULES}"""

# The classes of the chart marks and the chart text. A mark or a text in a chart must have one of them.
CHART_CLASSES = frozenset(re.findall(r"\.(lab-c-[a-z-]+)", CLASS_RULES))


def _tag(name, cls, **attrs):
    parts = [f'class="{cls}"'] + [
        f'{k.replace("_", "-")}="{_n(v) if isinstance(v, float | int) else v}"' for k, v in attrs.items()
    ]
    return f"<{name} {' '.join(parts)}/>"


def _path(points):
    return "M" + "L".join(f"{_n(x)},{_n(y)}" for x, y in points)


def chart_svg(width, height, body, label):
    """The <svg> of a chart: the shared class, a viewBox of width x height and an aria-label. body: the marks."""
    return (
        f'<svg class="lab-chart" viewBox="0 0 {_n(width)} {_n(height)}" role="img" '
        f'aria-label="{html.escape(label)}">{body}</svg>'
    )


def hero_line(points):
    """The hero line through points [(x, y)]. One point or none gives "": the chart draws the hero dot only."""
    return _tag("path", "lab-c-hero", d=_path(points)) if len(points) > 1 else ""


def hero_dot(x, y, category=False):
    """The hero dot: the last hero point of a trend chart, or the "now" dot of a category (category=True)."""
    return _tag("circle", "lab-c-hero-dot", cx=x, cy=y, r=tokens.CHART_MARKERS["now" if category else "hero"])


def secondary_line(points):
    """A secondary line through points [(x, y)], for example the competitive minutes. One point or none gives ""."""
    return _tag("path", "lab-c-second", d=_path(points)) if len(points) > 1 else ""


def game_dot(x, y):
    """The dot of one game."""
    return _tag("circle", "lab-c-game", cx=x, cy=y, r=tokens.CHART_MARKERS["game"])


def _triangle(x, y, down):
    """A triangle of CHART_MARKERS tri-w by tri-h around (x, y), as in the approved sample.

    The tip is half the width from y. The base is the rest of the height from y, on the other side.
    """
    half = tokens.CHART_MARKERS["tri-w"] / 2
    base = tokens.CHART_MARKERS["tri-h"] - half
    sign = 1 if down else -1
    return _path([(x - half, y - sign * base), (x + half, y - sign * base), (x, y + sign * half)]) + "Z"


def dud(x, y):
    """A dud: a down triangle in lab-red."""
    return _tag("path", "lab-c-dud", d=_triangle(x, y, down=True))


def spike(x, y):
    """A spike: an up triangle in lab-ink."""
    return _tag("path", "lab-c-spike", d=_triangle(x, y, down=False))


def band(x, y, width, height):
    """The normal-range band: a filled rect across the plot."""
    return _tag("rect", "lab-c-band", x=x, y=y, width=width, height=height)


def ref_line(x1, y1, x2, y2):
    """A reference line (replacement, top-30 level, 50th pct)."""
    return _tag("line", "lab-c-ref", x1=x1, y1=y1, x2=x2, y2=y2)


def track(x1, x2, y):
    """The 0 to 100 track of one category row."""
    return _tag("line", "lab-c-track", x1=x1, y1=y, x2=x2, y2=y)


def connector(x1, x2, y):
    """The connector of a category row, from the projection dot to the "now" dot."""
    return _tag("line", "lab-c-conn", x1=x1, y1=y, x2=x2, y2=y)


def proj_dot(x, y):
    """The hollow projection dot of a category row."""
    return _tag("circle", "lab-c-proj", cx=x, cy=y, r=tokens.CHART_MARKERS["proj"])


def crosshair(x, top, bottom):
    """The vertical crosshair through a game column, for the full plot height."""
    return _tag("line", "lab-c-cross", x1=x, y1=top, x2=x, y2=bottom)


def label(x, y, text, kind="tick", anchor="start"):
    """A chart text at baseline y. kind: "tick" (10.5px, lab-mute), "label" (11px, lab-ink) or "exit" (lab-red)."""
    extra = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return f'<text class="lab-c-{kind}" x="{_n(x)}" y="{_n(y)}"{extra}>{html.escape(text)}</text>'


class Box(NamedTuple):
    """A box around a mark, a line or a label: the top-left corner, the width and the height, in px."""

    x: float
    y: float
    w: float
    h: float


def hits(box, boxes):
    """True if box overlaps one of boxes. Boxes that only touch do not overlap."""
    return any(box.x < b.x + b.w and box.x + box.w > b.x and box.y < b.y + b.h and box.y + box.h > b.y for b in boxes)


def text_width(text):
    """The estimated width of a chart text, in px."""
    return len(text) * CHAR_W


def line_boxes(points, pad):
    """Small boxes along a line through points [(x, y)], each 2 x pad wide, about 4px apart."""
    out = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        k = max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / 4))
        for j in range(k + 1):
            out.append(Box(x1 + (x2 - x1) * j / k - pad, y1 + (y2 - y1) * j / k - pad, 2 * pad, 2 * pad))
    return out


def end_labels(ys, top, bottom):
    """The label heights for the end labels at heights ys, in the order of ys.

    Two labels less than END_GAP apart move apart by the same amount. The labels stay END_INSET inside the plot,
    from top to bottom. Draw each label END_DX right of the plot, at the returned height + 4 (the baseline).
    """
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed = [ys[i] for i in order]
    lo, hi = top + END_INSET, bottom - END_INSET
    for _ in range(20):
        moved = False
        for i in range(1, len(placed)):
            gap = placed[i] - placed[i - 1]
            if gap < END_GAP:
                half = (END_GAP - gap) / 2
                placed[i - 1] -= half
                placed[i] += half
                moved = True
        placed = [max(lo, min(hi, y)) for y in placed]
        if not moved:
            break
    # Near the top or the bottom, the clamp stops the even move. These sweeps close the gaps that stay.
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + END_GAP)
    if placed:
        placed[-1] = min(placed[-1], hi)
        for i in range(len(placed) - 2, -1, -1):
            placed[i] = min(placed[i], placed[i + 1] - END_GAP)
    out = [0.0] * len(ys)
    for i, y in zip(order, placed):
        out[i] = y
    return out


def point_label(text, cx, cy, boxes, plot):
    """The place of a dud, spike or range exit label at the mark (cx, cy), or None if no side is clear.

    The sides, in order: SIDE_DX right, SIDE_DX left, SIDE_DY above, SIDE_DY below. plot: the Box of the plot.
    The label stays PLOT_INSET inside the plot and overlaps none of boxes. The label box goes into boxes.
    Return (x, baseline y) for label().
    """
    w = text_width(text)
    sides = [(cx + SIDE_DX, cy - TXT_H / 2), (cx - SIDE_DX - w, cy - TXT_H / 2)]
    sides += [(cx - w / 2, cy - SIDE_DY - TXT_H), (cx - w / 2, cy + SIDE_DY)]
    left, top = plot.x + PLOT_INSET, plot.y + PLOT_INSET
    right, bottom = plot.x + plot.w - PLOT_INSET, plot.y + plot.h - PLOT_INSET
    for x, y in sides:
        box = Box(x, y, w, TXT_H)
        if x < left or x + w > right or y < top or y + TXT_H > bottom or hits(box, boxes):
            continue
        boxes.append(box)
        return x, y + TXT_H - 2
    return None


def band_label(text, band_box, boxes):
    """The place of the band label in a corner of band_box that overlaps none of boxes, or None.

    The corners, in order: bottom-left, top-left, bottom-right, top-right, BAND_INSET from the edges.
    The label box goes into boxes. Return (x, baseline y) for label().
    """
    w = text_width(text)
    left, right = band_box.x + BAND_INSET, band_box.x + band_box.w - BAND_INSET - w
    top, bottom = band_box.y + BAND_INSET, band_box.y + band_box.h - BAND_INSET - TXT_H
    for x, y in ((left, bottom), (left, top), (right, bottom), (right, top)):
        box = Box(x, y, w, TXT_H)
        if not hits(box, boxes):
            boxes.append(box)
            return x, y + TXT_H - 2
    return None


def now_proj(x_now, x_proj, cy):
    """The places of the "now" and "proj" labels of the first category row, at track height cy.

    Return two (x, baseline y, anchor) for label(): the "now" label, then the "proj" label.
    """
    if abs(x_now - x_proj) > NOW_PROJ_APART:
        return (x_now, cy - NOW_PROJ_DY, "middle"), (x_proj, cy - NOW_PROJ_DY, "middle")
    if x_now <= x_proj:
        return (x_now + NOW_PROJ_DX, cy - NOW_PROJ_DY, "end"), (x_proj - NOW_PROJ_DX, cy + PROJ_BELOW_DY, "start")
    return (x_now - NOW_PROJ_DX, cy - NOW_PROJ_DY, "start"), (x_proj + NOW_PROJ_DX, cy + PROJ_BELOW_DY, "end")


MARK_TAGS = {"path", "circle", "line", "rect", "polygon", "polyline", "ellipse", "text"}
COLOR_ATTRS = {"fill", "stroke", "color", "stop-color", "flood-color", "style"}
RAW_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(")


class _StyleCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # one entry for each open <svg>: True if the check applies inside it
        self.problems = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "svg":
            checked = (not self.stack or self.stack[-1]) and a.get("aria-hidden") != "true"
            if checked and not self.stack and "lab-chart" not in (a.get("class") or "").split():
                self.problems.append(f'An <svg> has no class "lab-chart": {a.get("aria-label", "no aria-label")}.')
            self.stack.append(checked)
        if not self.stack or not self.stack[-1]:
            return
        where = f"<{tag} {' '.join(f'{k}={v!r}' for k, v in attrs)}>"
        if "stroke-width" in a or "stroke-width" in (a.get("style") or ""):
            self.problems.append(f"An inline stroke width: {where}.")
        if any(RAW_COLOR.search(v or "") for k, v in a.items() if k in COLOR_ATTRS):
            self.problems.append(f"A raw color: {where}.")
        if tag in MARK_TAGS and not CHART_CLASSES & set((a.get("class") or "").split()):
            self.problems.append(f"A mark with no shared chart class: {where}.")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "svg":
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == "svg" and self.stack:
            self.stack.pop()


def style_problems(page):
    """The chart style problems of the HTML text page, as a list of messages. An empty list means no problem.

    Each <svg> must have the class "lab-chart". An <svg> with aria-hidden="true" (an icon) is not a chart.
    In a chart, a problem is an inline stroke width, a raw color (hex, rgb() or hsl()) or a mark with no class of
    CHART_CLASSES.
    """
    check = _StyleCheck()
    check.feed(page)
    check.close()
    return check.problems


TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _text_box(attrs, text):
    a = dict(ATTR.findall(attrs))
    w = text_width(text)
    x = float(a.get("x", 0)) - {"middle": w / 2, "end": w}.get(a.get("text-anchor"), 0)
    return Box(x, float(a.get("y", 0)) - (TXT_H - 2), w, TXT_H)


def label_overlaps(page):
    """The pairs of chart texts that overlap in the HTML or SVG text page, as [(text, text)].

    The check estimates each text box from x, y, text-anchor, CHAR_W and TXT_H, as the label placement does.
    It compares the texts of one <svg> only. An empty list means no overlap.
    """
    pairs = []
    for svg in re.findall(r"<svg\b.*?</svg>", page, re.S):
        texts = [(re.sub(r"<[^>]+>", "", t), attrs) for attrs, t in TEXT.findall(svg)]
        texts = [(html.unescape(t), _text_box(attrs, html.unescape(t))) for t, attrs in texts]
        for i, (a, box_a) in enumerate(texts):
            pairs += [(a, b) for b, box_b in texts[i + 1 :] if hits(box_a, [box_b])]
    return pairs
