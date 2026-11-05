"""Tests of core/skyline_svg.py: the 5 layouts of the Schedule Skyline for weeks A-E (issue 235, PR 241).

The browser tests at the end use the Playwright Chromium. They skip when Chromium is not installed.
"""

import json
import re
import struct
import zlib
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.core import skyline_svg, tokens
from fantasyhoops.core.common import ROOT
from fantasyhoops.core.skyline import week_facts
from fantasyhoops.core.skyline_svg import (
    FRAMES,
    LAYOUTS,
    MARK_ROLES,
    TALL,
    axis,
    display_scale,
    phone_panels,
    post_images,
    render,
    text_boxes,
    text_overlaps,
)

# Weeks A-E of docs/wiki/schedule-map-2026-11-04.md, with the week numbers of the v6 mock.
FIXTURE = Path(__file__).parent / "fixtures" / "skyline_weeks.json"
WEEKS = {
    "A": (date(2026, 11, 2), 3),
    "B": (date(2027, 2, 15), 18),
    "C": (date(2027, 1, 11), 13),
    "D": (date(2026, 11, 9), 4),
    "E": (date(2027, 2, 8), 17),
}
CFG = {
    "quality_games": {"max_games_per_day": 6},
    "skyline": {"max_adds": 4, "scarce_teams": 5, "anchor_max_games": 4, "heavy_max_teams": 3},
}
DAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
SKYLINES = ("page", "phone-skyline", "skyline")  # the layouts with a skyline
LADDERS = ("page", "phone-ladder", "ladder")  # the layouts with a ladder
# The phrase of DESIGN.md "The Named Exception Rule" for each mark role of the renderer. "title" is a heading.
EXCEPTIONS = {
    "anchor": "the anchor stripe or the anchor night column",
    "gain-tag": 'the "+1" gain tags',
    "night-line": "and the light-night line",
    "game-dot": "The game dots of a leg",
    "light-block": "the skyline blocks of a light night",
    "light-count": "the game count of a light night",
    "light-head": "the day head of a light night",
    "gain-text": "the rung gain text",
    "line-key": "the label of the light-night line",
}


@pytest.fixture(scope="module")
def weeks():
    sched = pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])
    return {k: (week_facts(sched, start, CFG), no) for k, (start, no) in WEEKS.items()}


@pytest.fixture(scope="module")
def svgs(weeks):
    """{(week key, layout): SVG text} for weeks A-E and the 5 layouts."""
    return {(k, lay): render(w, no, lay) for k, (w, no) in weeks.items() for lay in LAYOUTS}


def texts(svg):
    return [t for t, _, _ in text_boxes(svg)]


def days_of(svg, cls, layout, week):
    """The days of the rects of class cls in svg: by x in the page layout, by y in a tall layout."""
    ax = axis(layout, week)
    coord = "x" if layout == "page" else "y"
    found = re.findall(rf'<rect class="{cls}" x="([\d.]+)" y="([\d.]+)"', svg)
    values = [float(x if coord == "x" else y) for x, y in found]
    return {max(i for i in range(7) if ax.lo(i) <= v + 1) for v in values}


def legs(svg):
    """{(rung, first, last): (the text of the leg, the chip teams, the leg SVG)} of svg."""
    out = {}
    for part in svg.split('<g class="rung')[1:]:
        rung = int(re.search(r'data-adds="(\d+)"', part).group(1))
        for leg in part.split('<g class="leg" ')[1:]:
            first, last = map(int, re.match(r'data-first="(\d)" data-last="(\d)"', leg).groups())
            leg = leg.split("</g></g>")[0]
            words = " ".join(re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<text\b[^>]*>(.*?)</text>", leg))
            out[rung, first, last] = (words, re.findall(r'data-team="(\w+)"', leg), leg)
    return out


def outside(leg):
    """The texts and chips of one leg (from legs()) that do not fit inside its white block."""
    x, y, w, h = map(
        float, re.search(r'class="leg-box" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', leg).groups()
    )
    boxes = [(t, b) for t, _, b in text_boxes(leg)]
    boxes += [
        (f"chip at {cx}", tuple(map(float, (cx, cy, cw, ch))))
        for cx, cy, cw, ch in re.findall(
            r'class="chip-box" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', leg
        )
    ]
    return [t for t, (bx, by, bw, bh) in boxes if bx < x or by < y or bx + bw > x + w + 0.5 or by + bh > y + h + 0.5]


def unlisted_marks(svg, theme="light"):
    """The elements of svg that use the mark color with no data-mark role of MARK_ROLES, as a list of tags.

    The check reads the elements of each type (rect, polygon, path, g and the others). theme: the theme of svg.
    """
    mark = (tokens.DARK if theme == "dark" else tokens.LIGHT)["mark"]
    css = re.search(r"<style>(.*?)</style>", svg, re.S).group(1)
    classes = set()
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if mark in body:
            classes |= {sel.split()[-1].lstrip(".") for sel in selectors.split(",") if "." in sel}
    bad = []
    frame = {"svg", "style", "title", "defs", "pattern"}  # the frame of the SVG, not marks
    for tag, name in re.findall(r"(<([a-zA-Z]+)\b[^>]*>)", svg):
        if name in frame:
            continue
        cls = set((re.search(r'class="([^"]*)"', tag) or re.search("()", "")).group(1).split())
        role = re.search(r'data-mark="([^"]*)"', tag)
        if (cls & classes or mark in tag) and (not role or role.group(1) not in MARK_ROLES):
            bad.append(tag)
    return bad


def test_the_renderer_writes_no_color_value_outside_tokens():
    source = Path(skyline_svg.__file__).read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", source)


def test_each_light_color_of_the_skyline_has_a_dark_value():
    names = ("sky-hatch", "sky-hatch-line", "sky-stripe", "sky-dim", "sky-grid")
    light, dark = tokens.SKYLINE_LIGHT, tokens.SKYLINE_DARK
    assert set(light) == set(dark) == set(names) and all(light[n] != dark[n] for n in names)


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_the_title_line_the_7_days_and_the_frame(weeks, svgs, key, layout):
    week, no = weeks[key]
    svg = svgs[key, layout]
    assert '>SCHEDULE <tspan class="mark" data-mark="title">SKYLINE</tspan></text>' in svg
    assert f"Week {no} · {week.start.year}" in texts(svg)
    assert [t for t in texts(svg) if t in DAY_NAMES] == list(DAY_NAMES)
    height, width, display_height = FRAMES[layout]
    assert f'viewBox="0 0 1080 {height}" width="{width}" height="{display_height}"' in svg


def test_the_frames_of_the_phone_panels_and_the_post_images():
    assert FRAMES["phone-skyline"][1:] == FRAMES["phone-ladder"][1:] == (390, 780)
    assert FRAMES["skyline"] == FRAMES["ladder"] == (1350, 1080, 1350)


@pytest.mark.parametrize("key", WEEKS)
def test_one_light_night_line_in_each_skyline_and_none_in_a_ladder(svgs, key):
    for layout in SKYLINES:
        assert svgs[key, layout].count('<g class="sk-line">') == 1, layout
    for layout in ("phone-ladder", "ladder"):
        assert '<g class="sk-line">' not in svgs[key, layout]
    for layout in ("phone-skyline", "skyline"):
        assert "6 or fewer games = light night" in texts(svgs[key, layout])


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LADDERS)
def test_the_anchor_stripe_is_on_the_anchor_day_only(weeks, svgs, key, layout):
    week, _ = weeks[key]
    anchors = {week.days.index(d) for d in week.anchors}
    assert days_of(svgs[key, layout], "stripe", layout, week) == anchors
    assert days_of(svgs[key, layout], "anchor", layout, week) == anchors  # the inverted day head (and the bar)


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", SKYLINES)
def test_a_no_game_day_has_the_hatch_and_the_text_no_nba_games(weeks, svgs, key, layout):
    week, _ = weeks[key]
    svg = svgs[key, layout]
    empty = {i for i, none in enumerate(week.no_games) if none}
    assert days_of(svg, "hatch", layout, week) == empty
    words = " ".join(texts(svg))  # a narrow column wraps the text: "NO NBA" over "GAMES"
    assert ("NO NBA" in words and "GAMES" in words) == bool(empty)


@pytest.mark.parametrize("layout", SKYLINES)
def test_the_hatch_is_on_the_no_game_days_of_weeks_a_and_b(weeks, svgs, layout):
    assert days_of(svgs["A", layout], "hatch", layout, weeks["A"][0]) == {1}
    assert days_of(svgs["B", layout], "hatch", layout, weeks["B"][0]) == {4, 5, 6}
    assert "Fri–Sun" in texts(svgs["B", layout])


def test_each_team_chip_text_has_aa_contrast_for_all_30_teams():
    assert len(tokens.TEAM_COLORS) == 30
    for team, color in tokens.TEAM_COLORS.items():
        assert tokens.contrast(color, tokens.team_ink(color)) >= 4.5, team


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LADDERS)
def test_each_chip_of_the_svg_uses_the_team_color_and_its_aa_ink(svgs, key, layout):
    chips = re.findall(
        r'data-team="(\w+)"><rect class="chip-box" [^>]*style="fill:(#\w+)"/><text [^>]*style="[^"]*fill:(#\w+)"',
        svgs[key, layout],
    )
    assert chips
    for team, ground, ink in chips:
        assert ground == tokens.TEAM_COLORS[team] and tokens.contrast(ground, ink) >= 4.5


@pytest.mark.parametrize("layout", LADDERS)
def test_a_scarce_leg_names_all_its_teams_and_other_legs_give_the_team_count(weeks, svgs, layout):
    for key, (week, _) in weeks.items():
        drawn = legs(svgs[key, layout])
        for rung in week.rungs:
            for leg in rung.legs:
                words, chips, _ = drawn[rung.adds, leg.first, leg.last]
                if leg.scarce:
                    assert chips == list(leg.teams) and "to choose from" not in words
                elif leg.games:
                    assert not chips and f"{leg.team_count} teams to choose from" in words
    assert legs(svgs["A", layout])[1, 0, 7][1] == ["PHX", "MIA"]
    assert legs(svgs["A", layout])[4, 3, 4][1] == ["GS", "MIA", "ORL", "PHX"]  # post A, rung 4, Thu: all 4 chips
    assert "16 teams to choose from" in legs(svgs["A", layout])[2, 4, 7][0]


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LADDERS)
def test_each_text_and_chip_of_a_leg_fits_inside_the_leg(svgs, key, layout):
    bad = {where: out for where, (_, _, leg) in legs(svgs[key, layout]).items() if (out := outside(leg))}
    assert bad == {}


def test_a_decisive_back_to_back_has_a_callout_and_each_back_to_back_has_a_line(svgs):
    assert "BACK-TO-BACK" in legs(svgs["A", "page"])[2, 0, 4][0]
    assert "BACK-TO-BACK" not in legs(svgs["A", "page"])[1, 0, 7][0]
    for layout in ("phone-ladder", "ladder"):
        assert "B2B" in legs(svgs["A", layout])[2, 0, 4][0]
        assert "B2B" not in legs(svgs["A", layout])[1, 0, 7][0]
    for layout in LADDERS:
        assert svgs["A", layout].count('class="b2b"') >= 4


@pytest.mark.parametrize("layout", LADDERS)
def test_the_gain_tags_the_zero_gain_rung_and_the_replan_tag(svgs, layout):
    a, d = texts(svgs["A", layout]), texts(svgs["D", layout])
    assert a.count("+1") == 2  # rung 2 buys Fri, rung 3 buys Sat
    assert "+0 · a 4th add gains nothing" in " ".join(a)
    assert svgs["A", layout].count('class="rung quiet"') == 1
    assert "RE-PLAN" in d and "RE-PLAN" not in a


def test_the_post_images_and_the_phone_panels(weeks, svgs):
    week, no = weeks["A"]
    assert post_images(week) == (render(week, None, "skyline"), render(week, None, "ladder"))
    assert phone_panels(week, no) == (svgs["A", "phone-skyline"], svgs["A", "phone-ladder"])
    for layout in ("phone-skyline", "skyline"):
        assert 'class="leg"' not in svgs["A", layout] and 'class="blk' in svgs["A", layout]
    for layout in ("phone-ladder", "ladder"):
        assert 'class="leg"' in svgs["A", layout] and 'class="blk' not in svgs["A", layout]
    assert 'class="leg"' in svgs["A", "page"] and 'class="blk' in svgs["A", "page"]


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", TALL)
def test_all_text_of_a_tall_layout_is_11_px_or_more_at_390_px(svgs, key, layout):
    # DESIGN.md "The Phone Legibility Rule": 11 px or more at a display width of 390 px.
    # A post image is 1080 px wide, but a phone shows it 390 px wide. A phone panel is 390 px wide.
    sizes = [size for _, size, _ in text_boxes(svgs[key, layout])]
    assert sizes and min(sizes) * min(display_scale(layout), 390 / 1080) >= 11


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", TALL)
def test_the_days_of_a_tall_layout_fill_the_frame(weeks, key, layout):
    week, _ = weeks[key]
    ax = axis(layout, week)
    assert ax.end == FRAMES[layout][0] - skyline_svg.profile(layout).margin
    sizes = [ax.span(i, i + 1)[1] for i in range(7)]
    full = max(sizes)
    assert all(
        s == pytest.approx(skyline_svg.NO_GAME_WEIGHT * full if none else full) for s, none in zip(sizes, week.no_games)
    )


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_the_svg_has_no_headline_footer_week_type_stamp_or_credit_line(svgs, key, layout):
    svg = svgs[key, layout]
    words = " ".join(texts(svg)).lower()
    for banned in ("anchor", "dead-day", "heavy", "stream", "week type", "espn", "chart:", "fantasy hoops", "rule"):
        assert banned not in words, banned
    assert "<footer" not in svg and 'class="foot' not in svg and 'class="kick' not in svg
    sizes = sorted(((size, t) for t, size, _ in text_boxes(svg)), reverse=True)
    assert sizes[0][1] == "SCHEDULE SKYLINE" and sizes[1][0] < sizes[0][0]  # one title and no headline


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_no_text_overlaps_another(svgs, key, layout):
    assert text_overlaps(svgs[key, layout]) == []


def test_the_overlap_check_finds_an_overlap():
    svg = '<svg><text data-style="text" x="0" y="20" style="font-size:20px">overlap</text>'
    assert text_overlaps(svg + svg[5:] + "</svg>") == [("overlap", "overlap")]


@pytest.mark.parametrize("theme", ("light", "dark"))
@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_each_mark_mark_is_in_the_exception_list_of_design_md(weeks, svgs, key, layout, theme):
    week, no = weeks[key]
    svg = svgs[key, layout] if theme == "light" else render(week, no, layout, theme="dark")
    assert unlisted_marks(svg, theme) == []


def test_each_mark_role_is_an_item_of_the_named_exception_rule():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    rule = design.split("**The Named Exception Rule.**")[1].split("**The Phone Legibility Rule.**")[0]
    assert set(EXCEPTIONS) == set(MARK_ROLES) - {"title"}
    for role, phrase in EXCEPTIONS.items():
        assert phrase in rule, role


def test_the_mark_check_finds_a_mark_mark_with_no_listed_role():
    svg = render(*_week_a(), "page")
    assert unlisted_marks(svg.replace(' data-mark="gain-text"', "", 1))
    assert unlisted_marks(svg.replace(' data-mark="game-dot"', ' data-mark="other"', 1))
    assert unlisted_marks(svg.replace("</svg>", f'<rect class="paper" style="fill:{tokens.LIGHT["mark"]}"/></svg>'))
    for shape in ("polygon", "path", "ellipse", "polyline", "g"):
        assert unlisted_marks(svg.replace("</svg>", f'<{shape} class="mark"/></svg>')), shape
    dark = render(*_week_a(), "page", theme="dark")
    assert unlisted_marks(dark, "dark") == []
    assert unlisted_marks(dark.replace("</svg>", f'<polygon style="fill:{tokens.DARK["mark"]}"/></svg>'), "dark")


def _week_a():
    sched = pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])
    return week_facts(sched, WEEKS["A"][0], CFG), WEEKS["A"][1]


@pytest.mark.parametrize("layout", ("page", "phone-ladder"))
def test_the_renderer_takes_a_ladder_and_gives_each_leg_a_link(weeks, layout):
    week, no = weeks["A"]
    svg = render(week, no, layout, rungs=week.rungs[:2], leg_href=lambda r, leg: f"#fa-{r.adds}-{leg.first}")
    assert svg.count("data-adds=") == 2
    assert re.findall(r'<a href="([^"]+)">', svg) == ["#fa-1-0", "#fa-2-0", "#fa-2-4"]
    assert "<a " not in render(week, no, layout)


def test_the_dark_theme_uses_the_dark_token_values(weeks):
    week, no = weeks["A"]
    svg = render(week, no, "page", theme="dark")
    assert tokens.SKYLINE_DARK["sky-stripe"] in svg and tokens.DARK["lab-stock"] in svg
    assert tokens.SKYLINE_LIGHT["sky-stripe"] not in svg


def test_an_unknown_layout_is_an_error(weeks):
    with pytest.raises(ValueError, match="layout"):
        render(weeks["A"][0], 3, "poster")


def test_the_page_day_axis_has_7_equal_columns_inside_the_frame():
    ax = axis("page")
    assert ax.lo(0) >= skyline_svg.PAGE.margin and ax.end <= 1080 - skyline_svg.PAGE.margin
    assert ax.span(2, 4) == pytest.approx((ax.lo(2), 2 * (ax.lo(1) - ax.lo(0))))


# ---- Browser checks: the line of check_line.py (the v6 mock folder) and the real text boxes, in Chromium.

PAGE_SCALE = 0.45  # the adds page shows the desktop poster at about 0.45x (docs/wiki/schedule-map-2026-11-04.md)


@pytest.fixture(scope="module")
def chromium():
    """A Chromium page from Playwright. The tests skip if Chromium is not installed."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Error as e:
            pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")
        try:
            yield browser.new_page(viewport={"width": 1080, "height": 1350})
        finally:
            browser.close()


def show(page, svg, tmp_path, width):
    """Open svg in page at the display width width, with the Archivo font of core/tokens.py."""
    tokens.copy_font(tmp_path)
    doc = tmp_path / "skyline.html"
    doc.write_text(
        f"<!DOCTYPE html><html><head><style>{tokens.TOKENS}\nbody{{margin:0}}"
        f"svg{{display:block;width:{width}px;height:auto}}</style></head><body>{svg}</body></html>",
        encoding="utf-8",
    )
    page.goto(doc.as_uri())
    page.evaluate("document.fonts.ready")


LINE_CHECK = """(points) => points.map(row => {
  const line = document.querySelector('.sk-line'); let ok = 0;
  for (const [x, y] of row) { const top = document.elementFromPoint(x, y); if (top && line.contains(top)) ok++; }
  return ok; })"""


def png_rows(data):
    """The rows of an 8-bit RGB or RGBA PNG as lists of (r, g, b), with no third-party library."""
    pos, idat = 8, b""
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos : pos + 8])
        chunk = data[pos + 8 : pos + 8 + n]
        if kind == b"IHDR":
            w, h, _, color = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + n
    bpp = 4 if color == 6 else 3
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append([tuple(line[x * bpp : x * bpp + 3]) for x in range(w)])
        prev = line
    return rows


def blue(px):
    """A pixel of the line: mark-blue hue (blue well above red) and darker than paper."""
    return px[2] - px[0] > 45 and sum(px) < 600


@pytest.mark.parametrize(
    "layout, width",
    [("page", 1080), ("page", 1080 * PAGE_SCALE), ("phone-skyline", 390), ("skyline", 1080), ("skyline", 390)],
)
def test_the_light_night_line_is_on_top_and_shows_in_each_day(chromium, weeks, tmp_path, layout, width):
    """From check_line.py: on each of the 7 days of weeks A-E, the line is the topmost element at 9 points.

    A screenshot also shows mark-blue dashes on each day, also when the page scales the image down.
    """
    scale = width / 1080
    for key, (week, no) in weeks.items():
        ax = axis(layout, week)
        show(chromium, render(week, no, layout), tmp_path, width)
        x0, x1, y0, y1 = chromium.evaluate(
            "(() => { const r = document.querySelector('.sk-line .night-line').getBoundingClientRect();"
            " return [r.left, r.right, r.top, r.bottom]; })()"
        )
        spans = [((ax.lo(i) + 4) * scale, (ax.lo(i + 1) - 4) * scale) for i in range(7)]
        if layout == "page":
            y = (y0 + y1) / 2
            assert x0 <= spans[0][0] and x1 >= spans[-1][1], key
            points = [[(a + (b - a) * k / 10, y) for k in range(1, 10)] for a, b in spans]
            clip = {"x": 0, "y": int(y) - 3, "width": width, "height": 7}
        else:
            x = (x0 + x1) / 2
            assert y0 <= spans[0][0] and y1 >= spans[-1][1], key
            points = [[(x, a + (b - a) * k / 10) for k in range(1, 10)] for a, b in spans]
            clip = {"x": int(x) - 3, "y": 0, "width": 7, "height": FRAMES[layout][0] * scale}
        assert chromium.evaluate(LINE_CHECK, points) == [9] * 7, key
        rows = png_rows(chromium.screenshot(clip=clip))
        for a, b in spans:
            if layout == "page":
                hits = max(sum(1 for px in row[int(a) : int(b)] if blue(px)) for row in rows)
            else:
                hits = max(sum(1 for row in rows[int(a) : int(b)] if blue(row[c])) for c in range(len(rows[0])))
            assert hits >= max(3, (b - a) // 15), (key, a)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_no_text_overlaps_another_in_chromium(chromium, weeks, tmp_path, layout):
    """The real text boxes of weeks A-E do not overlap, and each estimated width holds the real width."""
    for key, (week, no) in weeks.items():
        svg = render(week, no, layout)
        show(chromium, svg, tmp_path, FRAMES[layout][1])
        real = chromium.evaluate(
            "[...document.querySelectorAll('svg text')].map(t => { const b = t.getBBox();"
            " const s = parseFloat(t.style.fontSize);"
            " return [t.textContent, b.x, b.y + s * 0.15, b.width, b.height - s * 0.3]; })"
        )
        for (text, _, (_, _, est, _)), (_, _, _, width, _) in zip(text_boxes(svg), real):
            assert width <= est + 0.5, (key, text, width, est)
        hits = [
            (a[0], b[0])
            for i, a in enumerate(real)
            for b in real[i + 1 :]
            if a[1] < b[1] + b[3] - 0.5
            and b[1] < a[1] + a[3] - 0.5
            and a[2] < b[2] + b[4] - 0.5
            and b[2] < a[2] + a[4] - 0.5
        ]
        assert hits == [], key


def ladder_zone(layout, week):
    """(x0, y0, x1, y1) of the ladder grid of layout, in SVG units."""
    if layout == "page":
        ax = axis("page")
        return ax.start, 560, ax.end, FRAMES["page"][0] - 56
    p, ax = skyline_svg.TALL_PROFILE, axis(layout, week)
    return p.margin + p.gutter, ax.start, 1080 - p.margin, ax.end


@pytest.mark.parametrize("key", ("A", "B"))
@pytest.mark.parametrize("layout", LADDERS)
def test_the_no_game_hatch_is_drawn_after_the_legs(svgs, key, layout):
    svg = svgs[key, layout]
    last_leg = svg.rindex('<g class="leg"')
    ladder_hatch = [
        m.start() for m in re.finditer(r'<rect class="hatch"', svg) if m.start() > svg.index('<g class="rung')
    ]
    assert ladder_hatch and min(ladder_hatch) > last_leg


HATCH_CHECK = """(points) => points.map(([x, y]) => { const top = document.elementFromPoint(x, y);
  return top ? top.getAttribute('class') : null; })"""


@pytest.mark.parametrize("layout", LADDERS)
def test_the_no_game_hatch_is_on_top_of_the_legs_in_chromium(chromium, weeks, tmp_path, layout):
    """On each no-game day of weeks A-E, the hatch is the topmost element at points across the whole ladder.

    The points cross the legs that span the no-game day. No leg, chip, dot or text may paint over the hatch.
    """
    width = FRAMES[layout][1]
    scale = width / 1080
    for key, (week, no) in weeks.items():
        empty = [i for i, none in enumerate(week.no_games) if none]
        if not empty:
            continue
        show(chromium, render(week, no, layout), tmp_path, width)
        x0, y0, x1, y1 = ladder_zone(layout, week)
        ax = axis(layout, week)
        points = []
        for i in empty:
            lo, hi = ax.lo(i) + 3, ax.lo(i + 1) - 3
            for k in range(1, 20):
                for j in range(1, 4):
                    if layout == "page":
                        points.append((lo + (hi - lo) * j / 4, y0 + (y1 - y0) * k / 20))
                    else:
                        points.append((x0 + (x1 - x0) * k / 20, lo + (hi - lo) * j / 4))
        tops = chromium.evaluate(HATCH_CHECK, [[x * scale, y * scale] for x, y in points])
        assert [t for t in tops if t != "hatch"] == [], key


@pytest.mark.parametrize(
    "start, text",
    [
        (date(2026, 11, 9), "Nov 9–15, 2026"),
        (date(2026, 11, 30), "Nov 30 – Dec 6, 2026"),
        (date(2026, 12, 28), "Dec 28, 2026 – Jan 3, 2027"),
    ],
)
def test_the_post_images_give_the_dates_in_the_title_line_inside_the_frame(start, text):
    """The post title line gives the dates, not a week number (owner, 2026-11-05). The longest dates fit the frame."""
    sched = pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])
    week = week_facts(sched, start, CFG)
    for svg in post_images(week):
        boxes = {t: (size, box) for t, size, box in text_boxes(svg)}
        _, (x, _, w, _) = boxes[text]
        assert x + w <= 1080 - skyline_svg.profile("skyline").margin, (text, x + w)
        assert not any(t.startswith("Week ") for t in boxes)
        assert text_overlaps(svg) == []
