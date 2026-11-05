"""The weekly Bluesky post of the Schedule Skyline (#237): 2 PNGs, the post text and 1 alt text for each PNG.

The post is team-agnostic: one roster spot that is open each day, 1 to [skyline] max_adds adds, from the NBA
schedule only (data/schedule.csv). The module reads no Yahoo data and no roster file. It posts nothing.
core/skyline.py gives the facts of the week and core/skyline_svg.py draws the 2 images. Playwright Chromium
saves each SVG as a 1080x1350 PNG, with the Archivo font of core/fonts/.

The module writes these files in output/bluesky/<first day of the week>/:
  skyline.png - image 1, the skyline
  ladder.png  - image 2, the add ladder
  post.json   - the week, the post text, and the file and the alt text of each image, in the post order
"""

import argparse
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from fantasyhoops.core import common, tokens
from fantasyhoops.core.schedule import read_schedule
from fantasyhoops.core.skyline import week_facts
from fantasyhoops.core.skyline_svg import FRAMES, post_images

TAG = "#FantasyBasketball"
LIMIT = 300  # the Bluesky limit of the post text, in characters
ALT_LIMIT = 2000  # the Bluesky limit of an alt text, in characters
WIDTH, HEIGHT = FRAMES["skyline"][1:]  # 1080x1350, the frame of each post image
PHONE = 390  # the display width of the phone rule: all text 11 px or more at 390 px (DESIGN.md)
MIN_TEXT = 11
MAX_BYTES = 1_000_000  # each PNG is under 1 MB
IMAGES = ("skyline", "ladder")  # the post order: image 1, image 2

# The smallest text of the page in screen px: the font size of each <text> times the scale of its SVG.
SMALLEST_TEXT = """() => Math.min(...[...document.querySelectorAll('svg text')].map(t =>
  parseFloat(getComputedStyle(t).fontSize) * t.getScreenCTM().a))"""
# True when the browser loaded the Archivo font of the page.
ARCHIVO_LOADED = "() => [...document.fonts].some(f => f.family.includes('Archivo') && f.status === 'loaded')"


class MissingDays(ValueError):
    """The week has days that the schedule does not have yet. The command makes no post for this week."""


def next_week_start(today):
    """The Monday of the next fantasy week: today if today is a Monday, else the next Monday."""
    return today + timedelta((7 - today.weekday()) % 7)


def week_number(start, cfg):
    """The fantasy week number of the week that starts on start: weeks of 7 days from [skyline] week_1."""
    if start.weekday() != 0:
        raise ValueError(f"A fantasy week starts on a Monday. {start:%a %Y-%m-%d} is not a Monday.")
    first = cfg["skyline"]["week_1"]
    if start < first:
        raise ValueError(f"Week 1 starts on {first}. {start} is before week 1.")
    return (start - first).days // 7 + 1


def missing_days(week, cfg):
    """The days of week in the [skyline] unscheduled ranges that have 0 games in the schedule."""
    ranges = cfg["skyline"].get("unscheduled", [])
    return tuple(
        d for d, g in zip(week.days, week.games) if g == 0 and any(first <= d <= last for first, last in ranges)
    )


def _day(d):
    return f"{d:%b} {d.day}"


def dates(week):
    """The dates of the week, for example "Nov 9–15, 2026" or "Dec 28, 2026 – Jan 3, 2027"."""
    a, b = week.days[0], week.days[-1]
    if a.year != b.year:
        return f"{_day(a)}, {a.year} – {_day(b)}, {b.year}"
    if a.month != b.month:
        return f"{_day(a)} – {_day(b)}, {b.year}"
    return f"{_day(a)}–{b.day}, {b.year}"


def post_text(week, week_no, cfg):
    """The text of the post: the title line with the dates, one line about the Skyline and the tag."""
    adds = cfg["skyline"]["max_adds"]
    return (
        f"Schedule Skyline · Week {week_no} · {dates(week)}\n\n"
        f"The NBA games of each night, and the most games that one open roster spot gets with 1 to {adds} adds.\n\n"
        f"{TAG}"
    )


def _span(week, first, last):
    """The day names of the days first to last (last exclusive), for example "Mon–Wed" or "Thu"."""
    a, b = week.days[first], week.days[last - 1]
    return f"{a:%a}" if first == last - 1 else f"{a:%a}–{b:%a}"


def _names(days):
    return ", ".join(f"{d:%a}" for d in days)


def skyline_alt(week, week_no):
    """The alt text of image 1: the games of each night, the light nights, the no-game days and the anchor nights."""
    nights = ", ".join(f"{d:%a} {g}" if g else f"{d:%a} no games" for d, g in zip(week.days, week.games))
    parts = [
        f"Schedule Skyline, week {week_no}, {dates(week)}.",
        f"A chart of the NBA games of each night: {nights}.",
    ]
    light = [d for d, lt in zip(week.days, week.light) if lt]
    if light:
        parts.append(f"Light nights ({week.light_max} or fewer games): {_names(light)}.")
    if week.anchors:
        count = dict(zip(week.days, week.games))
        anchors = ", ".join(f"{d:%a} ({count[d]} games)" for d in week.anchors)
        parts.append(f"Anchor night{'s' if len(week.anchors) > 1 else ''}: {anchors}.")
    return " ".join(parts)


def _leg_text(week, leg):
    where = _span(week, leg.first, leg.last)
    if not leg.games:
        return f"{where}: no team plays."
    games = f"{leg.games} game{'s' if leg.games > 1 else ''}"
    teams = ", ".join(leg.named) if leg.scarce else f"{leg.team_count} teams to choose from"
    b2b = ", needs a back-to-back" if leg.decisive_b2b else ""
    return f"{where}, {games}: {teams}{b2b}."


def _rung_text(rung):
    head = f"{rung.adds} add{'s' if rung.adds > 1 else ''}: {rung.games} games"
    if rung.light:
        head += f" ({rung.light} on {'a light night' if rung.light == 1 else 'light nights'})"
    if rung.adds > 1:
        if rung.zero_gain:
            head += ", +0, this add gains nothing"
        else:
            head += f", +{rung.gain}, buys {_names(rung.plus_one)}"
    if rung.replan:
        head += ", re-planned"
    return head + "."


def ladder_alt(week, week_no):
    """The alt text of image 2: each rung of the ladder with its games, its gain and its legs."""
    parts = [f"The add ladder of week {week_no}: the most games for one roster spot that is open each day."]
    for rung in week.rungs:
        parts.append(" ".join([_rung_text(rung), *(_leg_text(week, leg) for leg in rung.legs)]))
    return " ".join(parts)


def build(sched, start, cfg):
    """{"week", "week_no", "text", "alts", "svgs"} of the post of the week that starts on start.

    Raise MissingDays if the week has unscheduled days with 0 games.
    """
    week_no = week_number(start, cfg)
    week = week_facts(sched, start, cfg)
    missing = missing_days(week, cfg)
    if missing:
        raise MissingDays(
            f"No post for week {week_no} ({dates(week)}). The schedule has no games on "
            + ", ".join(f"{d:%a} {_day(d)}" for d in missing)
            + ". These days are in [skyline] unscheduled of config.toml. "
            "Run python -m fantasyhoops.fetch.espn again after the NBA sets the games of these days."
        )
    return {
        "week": week,
        "week_no": week_no,
        "text": post_text(week, week_no, cfg),
        "alts": (skyline_alt(week, week_no), ladder_alt(week, week_no)),
        "svgs": post_images(week, week_no),
    }


def export_pngs(svgs, paths):
    """Save each SVG as a WIDTH x HEIGHT PNG at its path with Playwright Chromium. Return the smallest text of each
    image in px at the PHONE display width. Raise RuntimeError if Archivo does not load or a text is too small."""
    from playwright.sync_api import sync_playwright

    smallest = []
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        tokens.copy_font(tmp)
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
            for i, (svg, path) in enumerate(zip(svgs, paths)):
                doc = Path(tmp) / f"image{i + 1}.html"
                doc.write_text(
                    f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{tokens.TOKENS}\n"
                    f"body{{margin:0}} svg{{display:block;width:{WIDTH}px;height:{HEIGHT}px}}</style></head>"
                    f"<body>{svg}</body></html>",
                    encoding="utf-8",
                )
                page.goto(doc.as_uri())
                page.evaluate("document.fonts.ready")
                if not page.evaluate(ARCHIVO_LOADED):
                    raise RuntimeError(f"Chromium did not load the Archivo font for {path.name}.")
                px = page.evaluate(SMALLEST_TEXT) * PHONE / WIDTH
                if px < MIN_TEXT:
                    raise RuntimeError(
                        f"The smallest text of {path.name} is {px:.1f} px at {PHONE} px, not {MIN_TEXT}."
                    )
                page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT})
                smallest.append(px)
        finally:
            browser.close()
    return smallest


def write_post(post, folder):
    """Write the 2 PNGs and post.json of post in folder.

    Return ([skyline.png, ladder.png, post.json], the smallest text of each PNG in px at the PHONE display width).
    """
    folder.mkdir(parents=True, exist_ok=True)
    pngs = [folder / f"{name}.png" for name in IMAGES]
    smallest = export_pngs(post["svgs"], pngs)
    for p in pngs:
        if p.stat().st_size >= MAX_BYTES:
            raise RuntimeError(f"{p.name} is {p.stat().st_size} bytes. A post image must be under {MAX_BYTES} bytes.")
    week = post["week"]
    data = {
        "week_no": post["week_no"],
        "first_day": week.days[0].isoformat(),
        "last_day": week.days[-1].isoformat(),
        "text": post["text"],
        "images": [{"file": p.name, "alt": alt} for p, alt in zip(pngs, post["alts"])],
    }
    path = folder / "post.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return [*pngs, path], smallest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the PNGs and the text of the weekly Schedule Skyline post.")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        help="the Monday of the week, YYYY-MM-DD. Default: the Monday of the next fantasy week.",
    )
    args = parser.parse_args(argv)
    cfg = common.load_config()
    start = args.week or next_week_start(date.today())
    try:
        post = build(read_schedule(), start, cfg)
    except FileNotFoundError as e:
        sys.exit(f"{e}. Run python -m fantasyhoops.fetch.espn first.")
    except ValueError as e:  # MissingDays is a ValueError
        sys.exit(str(e))
    files, smallest = write_post(post, common.OUT / "bluesky" / start.isoformat())
    print(f"Week {post['week_no']}: {dates(post['week'])}")
    for f in files:
        print(f"  {f} ({f.stat().st_size / 1024:.0f} KB)")
    print(f"Smallest text at {PHONE} px: " + ", ".join(f"{px:.1f} px" for px in smallest))
    print(f"\n{post['text']}\n")
    for f, alt in zip(files, post["alts"]):
        print(f"Alt text of {f.name}: {alt}\n")
