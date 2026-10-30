import re
from pathlib import Path

import pytest

from fantasyhoops.core import chart, tokens
from fantasyhoops.core.publish import shell

FIXTURES = Path(__file__).parent / "fixtures"
CFG = {"league": {"teams": 14}}


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def attrs(svg):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', svg))


def mix(color, ground, alpha):
    """The color "#rrggbb" at opacity alpha on the ground "#rrggbb"."""
    a, b = ([int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in (color, ground))
    return "#" + "".join(f"{round(alpha * x + (1 - alpha) * y):02x}" for x, y in zip(a, b))


# The tokens


def test_the_tokens_have_the_sizes_of_the_design_md_token_gaps():
    assert tokens.CHART_STROKES == {"hero": 2, "ring": 2, "second": 1.25, "rule": 1, "empty": 1.5}
    assert tokens.CHART_MARKERS == {"game": 3.5, "hero": 4, "now": 5, "proj": 4, "tri-w": 9, "tri-h": 7.5}
    assert tokens.CHART_OPACITIES["second"] == 0.8 and tokens.CHART_OPACITIES["conn"] == 0.7
    assert tokens.CHART_TEXT == {"small": 10.5, "label": 11}


@pytest.mark.parametrize("theme", [tokens.LIGHT, tokens.DARK])
@pytest.mark.parametrize("ground", ["lab-stock", "zebra"])
def test_a_game_dot_has_3_to_1_on_its_ground(theme, ground):
    """A game dot sits on the page (lab-stock) or on the normal-range band (zebra)."""
    dot = mix(theme["lamp-off"], theme[ground], tokens.CHART_OPACITIES["game"])
    assert tokens.contrast(dot, theme[ground]) >= 3


# The CSS


def test_the_chart_css_takes_each_size_from_the_tokens():
    root, rules = chart.CHART_STYLE.split(":root {", 1)[1].split("}", 1)
    for name, value in tokens.CHART_STROKES.items():
        assert f"--lab-c-sw-{name}: {chart._n(value)}px;" in root
    for name, value in tokens.CHART_OPACITIES.items():
        assert f"--lab-c-op-{name}: {chart._n(value)};" in root
    assert "--lab-c-fs-small: 10.5px;" in root and "--lab-c-fw-exit: 800;" in root
    # No class repeats a literal value: each number is in a var(). width: 100% scales the chart to its panel.
    assert not re.findall(r"\d", re.sub(r"var\(--[\w-]+\)", "", rules).replace("100%", ""))
    assert not chart.RAW_COLOR.search(chart.CHART_STYLE)


def test_each_var_of_the_classes_has_a_value():
    defined = set(re.findall(r"(--lab-c-[\w-]+):", chart.CHART_STYLE))
    used = set(re.findall(r"var\((--lab-c-[\w-]+)\)", chart.CHART_STYLE))
    assert used <= defined and used


def test_the_shell_puts_the_chart_css_in_place_of_the_placeholder():
    assert shell("<style>__CHART_CSS__</style>", "adds", CFG) == f"<style>{chart.CHART_STYLE}</style>"


def test_no_page_template_has_the_chart_placeholder_yet():
    """#185 changes no page. Each page adds __CHART_CSS__ in its own adoption issue."""
    src = Path(chart.__file__).parents[1]
    users = [p for p in src.rglob("*.py") if "__CHART_CSS__" in p.read_text(encoding="utf-8")]
    assert sorted(p.name for p in users) == ["chart.py", "publish.py"]


# The SVG helpers


def test_the_hero_line_and_the_hero_dots():
    line = chart.hero_line([(10, 20), (30.5, 40)])
    assert line == '<path class="lab-c-hero" d="M10,20L30.5,40"/>'
    assert chart.hero_line([(10, 20)]) == ""  # one hero point: the hero dot only
    assert attrs(chart.hero_dot(1, 2)) == {"class": "lab-c-hero-dot", "cx": "1", "cy": "2", "r": "4"}
    assert attrs(chart.hero_dot(1, 2, category=True))["r"] == "5"


def test_the_secondary_line_the_game_dot_and_the_projection_dot():
    assert chart.secondary_line([(0, 0), (4, 4)]) == '<path class="lab-c-second" d="M0,0L4,4"/>'
    assert chart.secondary_line([]) == ""
    assert attrs(chart.game_dot(5, 6)) == {"class": "lab-c-game", "cx": "5", "cy": "6", "r": "3.5"}
    assert attrs(chart.proj_dot(5, 6)) == {"class": "lab-c-proj", "cx": "5", "cy": "6", "r": "4"}


def test_the_dud_points_down_and_the_spike_points_up_at_9_by_7_5():
    for helper, cls, tip_y in ((chart.dud, "lab-c-dud", 104.5), (chart.spike, "lab-c-spike", 95.5)):
        a = attrs(helper(100, 100))
        assert a["class"] == cls
        pts = [tuple(map(float, p.split(","))) for p in a["d"].strip("MZ").split("L")]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        assert max(xs) - min(xs) == 9 and max(ys) - min(ys) == 7.5
        assert pts[2] == (100, tip_y)


def test_the_band_the_lines_and_the_crosshair():
    assert attrs(chart.band(1, 2, 3, 4)) == {"class": "lab-c-band", "x": "1", "y": "2", "width": "3", "height": "4"}
    assert attrs(chart.ref_line(0, 5, 100, 5)) == {"class": "lab-c-ref", "x1": "0", "y1": "5", "x2": "100", "y2": "5"}
    assert attrs(chart.track(0, 100, 7)) == {"class": "lab-c-track", "x1": "0", "y1": "7", "x2": "100", "y2": "7"}
    assert attrs(chart.connector(20, 60, 7)) == {"class": "lab-c-conn", "x1": "20", "y1": "7", "x2": "60", "y2": "7"}
    assert attrs(chart.crosshair(9, 12, 80)) == {"class": "lab-c-cross", "x1": "9", "y1": "12", "x2": "9", "y2": "80"}


def test_the_label_and_the_chart_svg():
    assert chart.label(3, 4, "a<b") == '<text class="lab-c-tick" x="3" y="4">a&lt;b</text>'
    assert 'class="lab-c-exit"' in chart.label(3, 4, "▲ out", "exit", "middle")
    assert 'text-anchor="middle"' in chart.label(3, 4, "x", anchor="middle")
    svg = chart.chart_svg(580, 268, chart.game_dot(1, 2), "Minutes")
    assert svg.startswith('<svg class="lab-chart" viewBox="0 0 580 268" role="img" aria-label="Minutes">')


def test_a_chart_of_the_helpers_passes_the_style_check():
    body = "".join(
        [
            chart.band(30, 40, 446, 30),
            chart.ref_line(30, 90, 476, 90),
            chart.secondary_line([(60, 50), (120, 55)]),
            chart.game_dot(60, 60),
            chart.dud(120, 80),
            chart.spike(180, 30),
            chart.hero_line([(60, 60), (120, 58)]),
            chart.hero_dot(120, 58),
            chart.track(30, 476, 100),
            chart.connector(60, 90, 100),
            chart.proj_dot(60, 100),
            chart.hero_dot(90, 100, category=True),
            chart.crosshair(60, 12, 108),
            chart.label(24, 64, "30", anchor="end"),
        ]
    )
    assert chart.style_problems(chart.chart_svg(580, 120, body, "All marks")) == []


# The label placement


def test_end_labels_move_apart_to_13px_by_the_same_amount():
    assert chart.end_labels([60, 66], 0, 200) == [56.5, 69.5]
    assert chart.end_labels([66, 60], 0, 200) == [69.5, 56.5]  # in the order of the input
    assert chart.end_labels([40, 100], 0, 200) == [40, 100]  # far apart: no move


def test_end_labels_stay_4px_inside_the_plot():
    ys = chart.end_labels([0, 2], 0, 200)
    assert ys == [4, 17]
    assert chart.end_labels([198, 199], 0, 200) == [183, 196]


def test_line_boxes_cover_a_line_about_each_4px():
    boxes = chart.line_boxes([(0, 0), (8, 0)], 2)
    assert boxes == [chart.Box(-2, -2, 4, 4), chart.Box(2, -2, 4, 4), chart.Box(6, -2, 4, 4)]
    assert chart.hits(chart.Box(3, 1, 1, 1), boxes) and not chart.hits(chart.Box(3, 2, 1, 1), boxes)


def test_a_point_label_tries_right_left_above_below():
    plot = chart.Box(0, 0, 400, 200)
    boxes = []
    assert chart.point_label("dud", 100, 100, boxes, plot) == (107, 103.5)
    assert boxes == [chart.Box(107, 94.5, 3 * chart.CHAR_W, chart.TXT_H)]
    blocked = [chart.Box(105, 90, 20, 20)]
    x, _ = chart.point_label("dud", 100, 100, blocked, plot)
    assert x == 100 - 7 - 3 * chart.CHAR_W  # left
    blocked = [chart.Box(70, 92, 60, 18)]  # the right and the left side overlap it
    assert chart.point_label("dud", 100, 100, blocked, plot)[1] == 100 - 8 - 2  # above


def test_a_point_label_gives_none_when_no_side_is_clear():
    boxes = [chart.Box(0, 0, 400, 200)]
    assert chart.point_label("spike", 100, 100, boxes, chart.Box(0, 0, 400, 200)) is None
    assert len(boxes) == 1


def test_a_point_label_stays_2px_inside_the_plot():
    plot = chart.Box(30, 12, 446, 234)
    x, _ = chart.point_label("spike", 474, 100, [], plot)  # no room at the right
    assert x + len("spike") * chart.CHAR_W <= 474


def test_the_band_label_takes_the_first_clear_corner():
    band = chart.Box(30, 40, 446, 60)
    text = "normal range 20.1–28.4"
    assert chart.band_label(text, band, []) == (34, 40 + 60 - 4 - 2)  # bottom-left
    boxes = [chart.Box(30, 80, 100, 20)]
    assert chart.band_label(text, band, boxes) == (34, 44 + 9)  # top-left
    assert chart.band_label(text, band, [band]) is None


def test_now_and_proj_labels():
    assert chart.now_proj(100, 200, 50) == ((100, 40, "middle"), (200, 40, "middle"))
    assert chart.now_proj(100, 120, 50) == ((102, 40, "end"), (118, 68, "start"))
    assert chart.now_proj(120, 100, 50) == ((118, 40, "start"), (102, 68, "end"))


# The style test


def test_the_style_check_passes_a_chart_with_the_shared_classes():
    assert chart.style_problems(fixture("chart_ok.html")) == []


@pytest.mark.parametrize(
    "old, new, problem",
    [
        ('d="M60,60L120,58L180,56"/>', 'd="M60,60L120,58L180,56" stroke-width="3"/>', "An inline stroke width"),
        ('r="3.5"/>', 'r="3.5" style="stroke-width: 2px"/>', "An inline stroke width"),
        ('r="3.5"/>', 'r="3.5" fill="#6f7889"/>', "A raw color"),
        ('<svg class="lab-chart" viewBox', "<svg viewBox", 'An <svg> has no class "lab-chart"'),
        ('<circle class="lab-c-game"', '<circle class="dot"', "A mark with no shared chart class"),
    ],
)
def test_the_style_check_fails_on_each_bad_fixture(old, new, problem):
    page = fixture("chart_ok.html")
    assert old in page
    problems = chart.style_problems(page.replace(old, new, 1))
    assert len(problems) == 1 and problems[0].startswith(problem)


# The label-overlap check


def test_the_overlap_check_fails_on_2_overlapping_labels_and_passes_the_fixed_fixture():
    assert chart.label_overlaps(fixture("labels_overlap.html")) == [("3-game 31.4", "competitive 30.2")]
    assert chart.label_overlaps(fixture("labels_fixed.html")) == []


def test_the_overlap_check_reads_the_text_anchor():
    svg = "<svg>{}{}</svg>"
    end = '<text x="100" y="50" text-anchor="end">abcd</text>'
    assert chart.label_overlaps(svg.format(end, '<text x="101" y="50">abcd</text>')) == []
    assert chart.label_overlaps(svg.format(end, '<text x="90" y="50">abcd</text>')) == [("abcd", "abcd")]
