"""Tests of bluesky/post.py (#237): the post text, the 2 alt texts, the week, the missing days and the 2 PNGs.

The PNG tests use the Playwright Chromium. They skip when Chromium is not installed.
"""

import ast
import json
import struct
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from fantasyhoops.bluesky import post
from fantasyhoops.bluesky.post import (
    ALT_LIMIT,
    LIMIT,
    MAX_BYTES,
    MIN_TEXT,
    TAG,
    MissingDays,
    build,
    dates,
    export_pngs,
    ladder_alt,
    next_week_start,
    post_text,
    skyline_alt,
    week_number,
    write_post,
)
from fantasyhoops.core import common

# Weeks A-E of docs/wiki/schedule-map-2026-11-04.md and their fantasy week numbers (the v6 mock).
FIXTURE = Path(__file__).parents[1] / "core" / "fixtures" / "skyline_weeks.json"
WEEKS = {
    "A": (date(2026, 11, 2), 3),
    "B": (date(2027, 2, 15), 18),
    "C": (date(2027, 1, 11), 13),
    "D": (date(2026, 11, 9), 4),
    "E": (date(2027, 2, 8), 17),
}
CFG = {
    "quality_games": {"max_games_per_day": 6},
    "skyline": {
        "max_adds": 4,
        "scarce_teams": 5,
        "anchor_max_games": 4,
        "heavy_max_teams": 3,
        "week_1": date(2026, 10, 19),
        "unscheduled": [[date(2026, 12, 4), date(2026, 12, 11)]],
    },
}


@pytest.fixture(scope="module")
def sched():
    return pd.DataFrame(json.loads(FIXTURE.read_text()), columns=["date", "team", "opponent"])


@pytest.fixture(scope="module")
def posts(sched):
    """{week key: the post of build()} for weeks A-E."""
    return {k: build(sched, start, CFG) for k, (start, _) in WEEKS.items()}


# ---- The week


@pytest.mark.parametrize(
    "today, monday",
    [
        (date(2026, 11, 5), date(2026, 11, 9)),
        (date(2026, 11, 9), date(2026, 11, 9)),
        (date(2026, 11, 8), date(2026, 11, 9)),
    ],
)
def test_the_default_week_is_the_next_monday_or_today_on_a_monday(today, monday):
    assert next_week_start(today) == monday


def test_the_week_number_counts_weeks_from_week_1():
    assert {k: week_number(start, CFG) for k, (start, _) in WEEKS.items()} == {k: no for k, (_, no) in WEEKS.items()}


@pytest.mark.parametrize("start", [date(2026, 11, 4), date(2026, 10, 12)])
def test_a_week_that_is_not_a_monday_or_is_before_week_1_is_an_error(start):
    with pytest.raises(ValueError):
        week_number(start, CFG)


def test_the_config_has_the_settings_of_the_post():
    sk = common.load_config()["skyline"]
    assert sk["week_1"].weekday() == 0
    assert all(first <= last for first, last in sk["unscheduled"])


# ---- The post text


def test_the_post_text_has_the_tag_and_the_dates_and_fits_the_limit(posts):
    for key, p in posts.items():
        text = p["text"]
        assert TAG in text, key
        assert dates(p["week"]) in text, key
        assert f"Week {WEEKS[key][1]}" in text, key
        assert len(text) <= LIMIT, (key, len(text))
    assert "Nov 2–8, 2026" in posts["A"]["text"]


@pytest.mark.parametrize(
    "start, text",
    [
        (date(2026, 11, 30), "Nov 30 – Dec 6, 2026"),
        (date(2026, 12, 28), "Dec 28, 2026 – Jan 3, 2027"),
        (date(2027, 2, 15), "Feb 15–21, 2027"),
    ],
)
def test_the_dates_of_a_week_across_months_and_years(start, text):
    week = SimpleNamespace(days=tuple(pd.date_range(start, periods=7).date))
    assert dates(week) == text
    assert len(post_text(week, 52, CFG)) <= LIMIT


# ---- The alt texts


def test_the_skyline_alt_text_gives_the_games_of_each_night(posts):
    for key, p in posts.items():
        week, alt = p["week"], p["alts"][0]
        assert alt == skyline_alt(week, p["week_no"])
        for d, g in zip(week.days, week.games):
            assert (f"{d:%a} {g}," if g else f"{d:%a} no games") in alt.replace(".", ","), (key, d)
        light = [f"{d:%a}" for d, lt in zip(week.days, week.light) if lt]
        if light:
            assert f"Light nights (6 or fewer games): {', '.join(light)}." in alt, key
        assert len(alt) <= ALT_LIMIT, key
    # Week A: Tue Nov 3 has no games, Thu Nov 5 has 2 games and is the anchor night.
    assert "Tue no games" in posts["A"]["alts"][0]
    assert "Anchor night: Thu (2 games)." in posts["A"]["alts"][0]


def test_the_ladder_alt_text_gives_each_rung_and_each_leg(posts):
    for key, p in posts.items():
        week, alt = p["week"], p["alts"][1]
        assert alt == ladder_alt(week, p["week_no"])
        assert len(alt) <= ALT_LIMIT, key
        pos = 0
        for rung in week.rungs:
            head = f"{rung.adds} add{'s' if rung.adds > 1 else ''}: {rung.games} games"
            pos = alt.index(head, pos)  # the rungs come in order
            if rung.adds > 1:
                assert (", +0, this add gains nothing" if rung.zero_gain else f", +{rung.gain}, buys") in alt[pos:]
            for leg in rung.legs:
                if leg.games and leg.scarce:
                    assert ", ".join(leg.teams) in alt[pos:], (key, rung.adds)
                elif leg.games:
                    assert f"{leg.team_count} teams to choose from" in alt[pos:], (key, rung.adds)
    # Week A: the 1-add rung is 4 games of PHX or MIA, and the 4th add gains nothing.
    a = posts["A"]["alts"][1]
    assert "1 add: 4 games (1 on a light night). Mon–Sun, 4 games: PHX, MIA." in a
    assert "4 adds: 6 games (1 on a light night), +0, this add gains nothing." in a


# ---- Missing days


def test_a_week_with_unscheduled_days_gives_a_clear_message_and_no_post(sched):
    # Wed Nov 4 of week A loses its games, and the config lists it as unscheduled.
    cut = sched[sched.date != "2026-11-04"]
    cfg = {**CFG, "skyline": {**CFG["skyline"], "unscheduled": [[date(2026, 11, 4), date(2026, 11, 4)]]}}
    with pytest.raises(MissingDays, match=r"No post for week 3 \(Nov 2–8, 2026\).*Wed Nov 4\."):
        build(cut, date(2026, 11, 2), cfg)


def test_a_no_game_day_outside_the_unscheduled_days_stays_in_the_post(sched):
    # Tue Nov 3 of week A has no games, and it is not in the unscheduled days: the image shows the hatch.
    p = build(sched, date(2026, 11, 2), CFG)
    assert p["week"].no_games[1]
    assert "NO NBA GAMES" in p["svgs"][0]


def test_only_the_unscheduled_days_with_0_games_stop_the_post(sched):
    # All of week A is in the range. Only Tue Nov 3 has 0 games, so the message names only that day.
    cfg = {**CFG, "skyline": {**CFG["skyline"], "unscheduled": [[date(2026, 11, 2), date(2026, 11, 8)]]}}
    with pytest.raises(MissingDays, match=r"no games on Tue Nov 3\. These days"):
        build(sched, date(2026, 11, 2), cfg)


def test_the_command_stops_with_the_message_and_writes_no_files(sched, monkeypatch, tmp_path):
    cut = sched[sched.date != "2026-11-04"]
    cfg = {**CFG, "skyline": {**CFG["skyline"], "unscheduled": [[date(2026, 11, 4), date(2026, 11, 4)]]}}
    monkeypatch.setattr(post, "read_schedule", lambda: cut)
    monkeypatch.setattr(common, "load_config", lambda: cfg)
    with pytest.raises(SystemExit, match="No post for week 3"):
        post.main(["--week", "2026-11-02"])
    assert not (tmp_path / "bluesky").exists()


# ---- No Yahoo data and no roster


def test_the_command_reads_no_yahoo_data_and_no_roster_file():
    for name in ("post.py", "__main__.py"):
        source = (Path(post.__file__).parent / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        # The command imports only core/ and its own subpackage: no Yahoo reader and no adds, league or trade code.
        ours = [m.split(".")[:2] for m in modules if m.startswith("fantasyhoops")]
        assert all(m[1] in ("core", "bluesky") for m in ours), modules
        assert not {"fantasyhoops.core.roster", "fantasyhoops.core.lineup"} & set(modules)
        for word in ("yahoo", "roster.csv", "rosters.csv", "projections"):
            assert word not in source.lower().replace("no yahoo data and no roster file", ""), (name, word)


# ---- The PNGs (Chromium)


@pytest.fixture(scope="module")
def chromium_ok():
    """Skip when the Playwright Chromium is not installed."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        try:
            pw.chromium.launch().close()
        except Error as e:
            pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")


def png_size(path):
    """(width, height) from the IHDR chunk of a PNG."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.fixture(scope="module")
def exported(chromium_ok, posts, tmp_path_factory):
    """{week key: (the paths of write_post(), the smallest text of each PNG at 390 px)} for weeks A-E."""
    out = {}
    for key, p in posts.items():
        folder = tmp_path_factory.mktemp(f"post-{key}")
        out[key] = write_post(p, folder)
    return out


def test_each_png_is_1080x1350_and_under_1_mb(exported):
    for key, (files, _) in exported.items():
        for png in files[:2]:
            assert png_size(png) == (1080, 1350), (key, png.name)
            assert png.stat().st_size < MAX_BYTES, (key, png.name)


def test_the_smallest_text_of_each_png_is_11_px_or_more_at_390_px(exported):
    for key, (_, smallest) in exported.items():
        assert len(smallest) == 2
        assert all(px >= MIN_TEXT for px in smallest), (key, smallest)


def test_the_text_check_stops_an_image_with_small_text(chromium_ok, tmp_path):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1350"><text x="9" y="40" style="font-family:Archivo;font-size:20px">x</text></svg>'
    with pytest.raises(RuntimeError, match="smallest text"):
        export_pngs([svg], [tmp_path / "small.png"])
    assert not (tmp_path / "small.png").exists()


def test_post_json_lists_the_text_and_the_2_images_in_the_post_order(exported, posts):
    files, _ = exported["A"]
    data = json.loads(files[2].read_text(encoding="utf-8"))
    assert data["week_no"] == 3 and data["first_day"] == "2026-11-02" and data["last_day"] == "2026-11-08"
    assert data["text"] == posts["A"]["text"]
    assert [i["file"] for i in data["images"]] == ["skyline.png", "ladder.png"]
    assert [i["alt"] for i in data["images"]] == list(posts["A"]["alts"])


def test_the_command_writes_the_files_of_the_week_in_output_bluesky(chromium_ok, sched, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(post, "read_schedule", lambda: sched)
    monkeypatch.setattr(common, "load_config", lambda: CFG)
    post.main(["--week", "2026-11-09"])
    folder = tmp_path / "bluesky" / "2026-11-09"
    assert sorted(p.name for p in folder.iterdir()) == ["ladder.png", "post.json", "skyline.png"]
    assert "Week 4: Nov 9–15, 2026" in capsys.readouterr().out
