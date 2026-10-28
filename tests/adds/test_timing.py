import csv
from datetime import date, timedelta

import pytest

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import StreamSpot
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.adds.team_plan import team_plan

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def clock(step):
    """A fake clock that moves step seconds at each read."""
    now = [0.0]

    def read():
        now[0] += step
        return now[0]

    return read


def search():
    games = {d: {"PHI"} if i % 2 else {"BOS"} for i, d in enumerate(WEEK)}
    days = open_slots_by_day([], games, SLOTS)
    return team_plan(days, games, [StreamSpot(), StreamSpot()], 3, SLOTS)


def test_a_step_prints_nothing_and_keeps_its_time(capsys):
    # #130: the terminal shows no step line. The page and timings.csv show the times.
    timings = timing.Timings(clock=clock(1.5), work=timing.Work())
    with timings.step("schedule read"):
        print("inside")
    assert capsys.readouterr().out.splitlines() == ["inside"]
    assert timings.steps == [timing.StepTime("schedule read", 1.5)]


def test_a_search_step_has_the_calls_and_the_states_of_its_searches(monkeypatch):
    work = timing.Work()
    monkeypatch.setattr(timing, "WORK", work)
    timings = timing.Timings()
    with timings.step("team plan", search=True):
        search()
        first = (work.calls, work.states)
        search()
    with timings.step("role read"):
        pass
    spots, roles = timings.steps
    assert 0 < first[1] <= first[0]
    assert (spots.calls, spots.states) == (2 * first[0], 2 * first[1])  # two searches add into one row
    assert (roles.calls, roles.states) == (None, None)


def test_the_counts_change_no_plan(monkeypatch):
    before = search()
    monkeypatch.setattr(timing, "WORK", timing.Work())
    assert search() == before


def test_a_long_search_prints_no_progress_line(monkeypatch, capsys):
    work = timing.Work()
    monkeypatch.setattr(timing, "WORK", work)
    timings = timing.Timings(clock=clock(4.0))  # before #130, a progress line after each 10 s
    with timings.step("team plan", search=True):
        search()
    assert work.calls > 3 and capsys.readouterr().out == ""


def test_a_run_with_no_timers_has_no_steps(capsys):
    timings = timing.Timings(on=False)
    with timings.step("schedule read"):
        pass
    assert timings.steps == [] and capsys.readouterr().out == ""


def test_each_step_appends_its_row_when_it_ends(tmp_path):
    days = open_slots_by_day([], {d: {"PHI"} for d in WEEK[:3]}, SLOTS)
    path = tmp_path / "timings.csv"
    work = timing.Work()
    timings = timing.Timings(clock=clock(0.123), work=work, path=path)
    with timings.step("schedule read"):
        pass
    assert not path.exists()  # the row waits for the window columns
    timings.window(days, 4)
    assert len(read_rows(path)[1]) == 1
    with timings.step("team plan", search=True):
        work.calls += 40
        work.states += 12
    columns, rows = read_rows(path)
    assert columns == timing.COLUMNS
    assert rows[0] == {
        "run_at": timings.run_at.isoformat(),
        "days": "3",
        "open_days": "3",
        "adds_left": "4",
        "step": "schedule read",
        "seconds": "0.12",
        "calls": "",
        "states": "",
        "pages": "",
    }
    assert (rows[1]["step"], rows[1]["calls"], rows[1]["states"]) == ("team plan", "40", "12")
    assert len(rows[0]["run_at"]) == len("2026-10-25T21:04:33")


def test_a_stopped_step_keeps_the_rows_of_the_earlier_steps(tmp_path):
    path = tmp_path / "timings.csv"
    timings = timing.Timings(path=path)
    with timings.step("schedule read"):
        pass
    timings.window([], 5)
    with timings.step("Yahoo reads"):
        pass
    with pytest.raises(KeyboardInterrupt):
        with timings.step("team plan", search=True):
            raise KeyboardInterrupt  # the owner stops the run with Ctrl+C
    assert [r["step"] for r in read_rows(path)[1]] == ["schedule read", "Yahoo reads"]


def test_a_step_that_stops_the_run_before_the_window_writes_the_waiting_rows(tmp_path):
    path = tmp_path / "timings.csv"
    timings = timing.Timings(path=path)
    with timings.step("schedule read"):
        pass
    with pytest.raises(RuntimeError):
        with timings.step("Yahoo reads"):
            raise RuntimeError("no Yahoo session")
    rows = read_rows(path)[1]
    assert [(r["step"], r["days"], r["open_days"], r["adds_left"]) for r in rows] == [("schedule read", "", "", "")]


class Pages:
    """A fake session.League: get() counts one page."""

    def __init__(self):
        self.pages = 0

    def get(self, n=1):
        self.pages += n


def test_each_sub_step_gets_a_row_after_its_step_with_its_seconds_and_its_pages(tmp_path, capsys):
    path, league = tmp_path / "timings.csv", Pages()
    timings = timing.Timings(clock=clock(1.0), path=path)
    timings.window([], 5)
    with timings.step("Yahoo reads"):
        with timings.part("browser start"):
            pass
        with timings.part("market pages", league):
            league.get(6)
        with timings.part("waiver list", league):
            league.get(1)
        with timings.part("market pages", league):  # a second block adds into the same sub-step
            league.get(6)
    with timings.step("role read"):
        pass
    # Each clock read moves 1 s, so each block is 1 s, and the step is 9 s: from read 1 to read 10.
    assert timings.steps == [
        timing.StepTime("Yahoo reads", 9.0, pages=13),
        timing.StepTime("Yahoo reads: browser start", 1.0, pages=0, parent="Yahoo reads"),
        timing.StepTime("Yahoo reads: market pages", 2.0, pages=12, parent="Yahoo reads"),
        timing.StepTime("Yahoo reads: waiver list", 1.0, pages=1, parent="Yahoo reads"),
        timing.StepTime("role read", 1.0),
    ]
    rows = read_rows(path)[1]
    assert [(r["step"], r["seconds"], r["pages"]) for r in rows] == [
        ("Yahoo reads", "9.00", "13"),
        ("Yahoo reads: browser start", "1.00", "0"),
        ("Yahoo reads: market pages", "2.00", "12"),
        ("Yahoo reads: waiver list", "1.00", "1"),
        ("role read", "1.00", ""),
    ]
    assert capsys.readouterr().out == ""


def test_a_sub_step_outside_a_step_raises_an_error():
    with pytest.raises(RuntimeError, match="browser start"):
        with timing.Timings().part("browser start"):
            pass


def test_a_run_with_no_timers_times_no_sub_step():
    timings = timing.Timings(on=False)
    with timings.part("market pages", Pages()):
        pass
    assert timings.steps == []


def test_a_stopped_step_writes_no_row_for_its_sub_steps(tmp_path):
    path = tmp_path / "timings.csv"
    timings = timing.Timings(path=path)
    timings.window([], 5)
    with pytest.raises(KeyboardInterrupt):
        with timings.step("Yahoo reads"):
            with timings.part("browser start"):
                pass
            raise KeyboardInterrupt
    assert not path.exists()


def test_a_file_with_the_old_header_gets_the_new_header_and_keeps_its_rows(tmp_path):
    path = tmp_path / "timings.csv"
    path.write_text(
        "run_at,days,open_days,adds_left,step,seconds,calls,states\n2026-10-26T09:00:00,2,2,1,Yahoo reads,31.34,,\n",
        encoding="utf-8",
    )
    timings = timing.Timings(path=path)
    timings.window([], 5)
    with timings.step("role read"):
        pass
    columns, rows = read_rows(path)
    assert columns == timing.COLUMNS
    assert rows[0] == {
        "run_at": "2026-10-26T09:00:00",
        "days": "2",
        "open_days": "2",
        "adds_left": "1",
        "step": "Yahoo reads",
        "seconds": "31.34",
        "calls": "",
        "states": "",
        "pages": "",
    }
    assert rows[1]["step"] == "role read"


def test_a_run_with_no_timers_writes_no_file(tmp_path):
    timings = timing.Timings(on=False, path=tmp_path / "timings.csv")
    with timings.step("schedule read"):
        pass
    timings.window([], 5)
    assert not (tmp_path / "timings.csv").exists()
