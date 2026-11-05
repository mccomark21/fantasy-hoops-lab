import json
import re
import struct
import zlib
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fantasyhoops.core import skyline_svg, tokens
from fantasyhoops.core.skyline import week_facts
from fantasyhoops.core.skyline_svg import LAYOUTS, axis, post_images, render, text_boxes, text_overlaps

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


@pytest.fixture(scope="module")
def weeks():
    sched = pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])
    return {k: (week_facts(sched, start, CFG), no) for k, (start, no) in WEEKS.items()}


@pytest.fixture(scope="module")
def svgs(weeks):
    """{(week key, layout): SVG text} for weeks A-E and the 3 layouts."""
    return {(k, lay): render(w, no, lay) for k, (w, no) in weeks.items() for lay in LAYOUTS}


def texts(svg):
    return [t for t, _, _ in text_boxes(svg)]


def columns(svg, cls, layout):
    """The day columns of the rects of class cls in svg."""
    ax = axis(layout)
    xs = re.findall(rf'<rect class="{cls}" x="([\d.]+)"', svg)
    return {int((float(x) - ax.start + 1) // ax.step) for x in xs}


def legs(svg):
    """{(rung, first, last): (the text of the leg, the chip teams)} of svg."""
    out = {}
    for part in svg.split('<g class="rung')[1:]:
        rung = int(re.search(r'data-adds="(\d+)"', part).group(1))
        for leg in part.split('<g class="leg" ')[1:]:
            first, last = map(int, re.match(r'data-first="(\d)" data-last="(\d)"', leg).groups())
            leg = leg.split("</g></g>")[0]
            words = " ".join(re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<text\b[^>]*>(.*?)</text>", leg))
            out[rung, first, last] = (words, re.findall(r'data-team="(\w+)"', leg))
    return out


def test_the_renderer_writes_no_color_value_outside_tokens():
    source = Path(skyline_svg.__file__).read_text(encoding="utf-8")
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", source)


def test_each_light_color_of_the_skyline_has_a_dark_value():
    names = ("sky-hatch", "sky-hatch-line", "sky-stripe", "sky-dim", "sky-grid")
    light, dark = tokens.SKYLINE_LIGHT, tokens.SKYLINE_DARK
    assert set(light) == set(dark) == set(names) and all(light[n] != dark[n] for n in names)


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", LAYOUTS)
def test_the_title_line_and_7_day_columns(weeks, svgs, key, layout):
    week, no = weeks[key]
    svg = svgs[key, layout]
    assert '>SCHEDULE <tspan class="mark">SKYLINE</tspan></text>' in svg
    assert f"Week {no} · {week.start.year}" in texts(svg)
    assert [t for t in texts(svg) if t in DAY_NAMES] == list(DAY_NAMES)
    assert f'width="{skyline_svg.SIZE[0]}" height="{skyline_svg.SIZE[1]}"' in svg


@pytest.mark.parametrize("key", WEEKS)
def test_one_light_night_line_in_the_skyline_and_none_in_the_ladder(svgs, key):
    assert svgs[key, "page"].count('<g class="sk-line">') == 1
    assert svgs[key, "skyline"].count('<g class="sk-line">') == 1
    assert '<g class="sk-line">' not in svgs[key, "ladder"]
    assert "6 or fewer games = light night" in texts(svgs[key, "skyline"])


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", ("page", "ladder"))
def test_the_anchor_stripe_is_on_the_anchor_column_only(weeks, svgs, key, layout):
    week, _ = weeks[key]
    anchors = {week.days.index(d) for d in week.anchors}
    assert columns(svgs[key, layout], "stripe", layout) == anchors
    assert columns(svgs[key, layout], "anchor", layout) == anchors  # the inverted day head (and skyline bar)


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", ("page", "skyline"))
def test_a_no_game_day_has_the_hatch_and_the_text_no_nba_games(weeks, svgs, key, layout):
    week, _ = weeks[key]
    svg = svgs[key, layout]
    empty = {i for i, none in enumerate(week.no_games) if none}
    assert columns(svg, "hatch", layout) == empty
    words = " ".join(texts(svg))  # a narrow column wraps the text: "NO NBA" over "GAMES"
    assert ("NO NBA" in words and "GAMES" in words) == bool(empty)


def test_the_hatch_is_on_the_no_game_days_of_weeks_a_and_b(svgs):
    assert columns(svgs["A", "skyline"], "hatch", "skyline") == {1}
    assert columns(svgs["B", "skyline"], "hatch", "skyline") == {4, 5, 6}
    assert "Fri–Sun" in texts(svgs["B", "skyline"])


def test_each_team_chip_text_has_aa_contrast_for_all_30_teams():
    assert len(tokens.TEAM_COLORS) == 30
    for team, color in tokens.TEAM_COLORS.items():
        assert tokens.contrast(color, tokens.team_ink(color)) >= 4.5, team


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", ("page", "ladder"))
def test_each_chip_of_the_svg_uses_the_team_color_and_its_aa_ink(svgs, key, layout):
    chips = re.findall(
        r'data-team="(\w+)"><rect class="chip-box" [^>]*style="fill:(#\w+)"/><text [^>]*style="[^"]*fill:(#\w+)"',
        svgs[key, layout],
    )
    assert chips
    for team, ground, ink in chips:
        assert ground == tokens.TEAM_COLORS[team] and tokens.contrast(ground, ink) >= 4.5


@pytest.mark.parametrize("layout", ("page", "ladder"))
def test_a_scarce_leg_names_its_teams_and_other_legs_give_the_team_count(weeks, svgs, layout):
    for key, (week, _) in weeks.items():
        drawn = legs(svgs[key, layout])
        for rung in week.rungs:
            for leg in rung.legs:
                words, chips = drawn[rung.adds, leg.first, leg.last]
                if leg.scarce:
                    assert chips == list(leg.teams) and "to choose from" not in words
                elif leg.games:
                    assert not chips and f"{leg.team_count} teams to choose from" in words
    words, chips = legs(svgs["A", layout])[1, 0, 7]
    assert chips == ["PHX", "MIA"]
    assert "16 teams to choose from" in legs(svgs["A", layout])[2, 4, 7][0]


def test_a_decisive_back_to_back_has_a_callout_and_each_back_to_back_has_a_line(svgs):
    words, _ = legs(svgs["A", "page"])[2, 0, 4]
    assert "BACK-TO-BACK" in words
    assert "BACK-TO-BACK" not in legs(svgs["A", "page"])[1, 0, 7][0]
    assert svgs["A", "page"].count('class="b2b"') >= 4


def test_the_gain_tags_the_zero_gain_rung_and_the_replan_tag(svgs):
    a, d = texts(svgs["A", "page"]), texts(svgs["D", "page"])
    assert a.count("+1") == 2  # rung 2 buys Fri, rung 3 buys Sat
    assert "+0 · a 4th add" in a or "+0 · a 4th add gains nothing" in " ".join(a)
    assert svgs["A", "page"].count('class="rung quiet"') == 1
    assert "RE-PLAN" in d and "RE-PLAN" not in a
    assert "+0 · a 4th add gains nothing" in texts(svgs["A", "ladder"])


def test_the_post_has_a_skyline_image_and_a_ladder_image_and_the_page_has_both_parts(weeks, svgs):
    week, no = weeks["A"]
    sky, lad = post_images(week, no)
    assert (sky, lad) == (svgs["A", "skyline"], svgs["A", "ladder"])
    for svg in (sky, lad, svgs["A", "page"]):
        assert 'viewBox="0 0 1080 1350" width="1080" height="1350"' in svg
    assert 'class="leg"' not in sky and 'class="blk' in sky
    assert 'class="leg"' in lad and 'class="blk' not in lad
    assert 'class="leg"' in svgs["A", "page"] and 'class="blk' in svgs["A", "page"]


@pytest.mark.parametrize("key", WEEKS)
@pytest.mark.parametrize("layout", ("skyline", "ladder"))
def test_all_text_of_a_post_image_is_30_px_or_more(svgs, key, layout):
    # DESIGN.md "The Phone Legibility Rule": 11 px at a display width of 390 px is about 30 px on 1080 px.
    sizes = [size for _, size, _ in text_boxes(svgs[key, layout])]
    assert sizes and min(sizes) >= 30


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


def test_the_renderer_takes_a_ladder_and_gives_each_leg_a_link(weeks):
    week, no = weeks["A"]
    svg = render(week, no, "page", rungs=week.rungs[:2], leg_href=lambda r, leg: f"#fa-{r.adds}-{leg.first}")
    assert svg.count("data-adds=") == 2
    assert re.findall(r'<a href="([^"]+)">', svg) == ["#fa-1-0", "#fa-2-0", "#fa-2-4"]
    assert "<a " not in render(week, no, "page")


def test_the_dark_theme_uses_the_dark_token_values(weeks):
    week, no = weeks["A"]
    svg = render(week, no, "page", theme="dark")
    assert tokens.SKYLINE_DARK["sky-stripe"] in svg and tokens.DARK["lab-stock"] in svg
    assert tokens.SKYLINE_LIGHT["sky-stripe"] not in svg


def test_an_unknown_layout_is_an_error(weeks):
    with pytest.raises(ValueError, match="layout"):
        render(weeks["A"][0], 3, "poster")


def test_the_day_axis_has_7_equal_columns_inside_the_frame():
    for layout in LAYOUTS:
        ax = axis(layout)
        assert ax.lo(0) >= skyline_svg.profile(layout).margin and ax.end <= skyline_svg.SIZE[0] - 48
        assert ax.span(2, 4) == (ax.lo(2), 2 * ax.step)


# ---- Browser checks: the line of check_line.py (the v6 mock folder) and the real text boxes, in Chromium.

PAGE_SCALE = 0.45  # the adds page shows the poster at about 0.45x (docs/wiki/schedule-map-2026-11-04.md)


@pytest.fixture(scope="module")
def chromium():
    """A Chromium page from Playwright. The tests skip if Chromium is not installed (as in CI)."""
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


def show(page, svg, tmp_path, scale=1.0):
    """Open svg in page at scale, with the Archivo font of core/tokens.py."""
    tokens.copy_font(tmp_path)
    w, h = (v * scale for v in skyline_svg.SIZE)
    doc = tmp_path / "skyline.html"
    doc.write_text(
        f"<!DOCTYPE html><html><head><style>{tokens.TOKENS}\nbody{{margin:0}}"
        f"svg{{display:block;width:{w}px;height:{h}px}}</style></head><body>{svg}</body></html>",
        encoding="utf-8",
    )
    page.goto(doc.as_uri())
    page.evaluate("document.fonts.ready")


LINE_CHECK = """([cols, y]) => cols.map(([x0, x1]) => {
  const line = document.querySelector('.sk-line'); let ok = 0;
  for (let k = 1; k <= 9; k++) { const top = document.elementFromPoint(x0 + (x1 - x0) * k / 10, y);
    if (top && line.contains(top)) ok++; }
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


@pytest.mark.parametrize("scale", (1.0, PAGE_SCALE))
@pytest.mark.parametrize("layout", ("page", "skyline"))
def test_the_light_night_line_is_on_top_and_shows_in_each_column(chromium, weeks, tmp_path, layout, scale):
    """From check_line.py: in each of the 7 columns of weeks A-E, the line is the topmost element at 9 points.

    A screenshot also shows mark-blue dashes in each column, also when the page scales the poster to 0.45x.
    """
    ax = axis(layout)
    for key, (week, no) in weeks.items():
        show(chromium, render(week, no, layout), tmp_path, scale)
        box = chromium.evaluate(
            "(() => { const r = document.querySelector('.sk-line .night-line').getBoundingClientRect();"
            " return [r.left, r.right, r.top + r.height / 2]; })()"
        )
        y = box[2]
        cols = [((ax.lo(i) + 4) * scale, (ax.lo(i + 1) - 4) * scale) for i in range(7)]
        assert box[0] <= cols[0][0] and box[1] >= cols[-1][1], key
        assert chromium.evaluate(LINE_CHECK, [cols, y]) == [9] * 7, key
        rows = png_rows(chromium.screenshot(clip={"x": 0, "y": int(y) - 3, "width": 1080 * scale, "height": 7}))
        for x0, x1 in cols:
            blue = max(sum(1 for px in row[int(x0) : int(x1)] if px[2] - px[0] > 45 and sum(px) < 600) for row in rows)
            assert blue >= max(3, (x1 - x0) // 15), (key, x0)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_no_text_overlaps_another_in_chromium(chromium, weeks, tmp_path, layout):
    """The real text boxes of weeks A-E do not overlap, and each estimated width holds the real width."""
    for key, (week, no) in weeks.items():
        svg = render(week, no, layout)
        show(chromium, svg, tmp_path)
        real = chromium.evaluate(
            "[...document.querySelectorAll('svg text')].map(t => { const b = t.getBBox();"
            " const s = parseFloat(t.style.fontSize); return [t.textContent, b.x, b.y + s * 0.15, b.width, b.height - s * 0.3]; })"
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
