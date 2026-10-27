import csv
from datetime import date, timedelta

import pytest

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import Option, StreamSpot, schedule_plan
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


@pytest.fixture(autouse=True)
def no_real_file(monkeypatch, tmp_path):
    """No test writes the real output/adds/timings.csv."""
    monkeypatch.setattr(timing, "TIMINGS", tmp_path / "real_timings.csv")


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
    fas = [Option(Player("Phi", "PHI", ("SF",)), 1.0), Option(Player("Bos", "BOS", ("C",)), 0.5)]
    return schedule_plan(days, games, [StreamSpot(), StreamSpot()], fas, 3, SLOTS)


def test_a_step_prints_its_start_and_its_time(capsys):
    timings = timing.Timings(clock=clock(1.5), work=timing.Work())
    with timings.step("schedule read"):
        print("inside")
    assert capsys.readouterr().out.splitlines() == ["Step: schedule read ...", "inside",
                                                    "Step: schedule read: 1.50 s"]
    assert timings.steps == [timing.StepTime("schedule read", 1.5)]


def test_a_search_step_has_the_calls_and_the_states_of_its_searches(monkeypatch):
    work = timing.Work()
    monkeypatch.setattr(timing, "WORK", work)
    timings = timing.Timings()
    with timings.step("spot plans", search=True):
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
    monkeypatch.setattr(timing, "WORK", timing.Work(clock=clock(100.0)))
    timing.WORK.begin("schedule search")
    assert search() == before


def test_a_search_prints_its_calls_and_its_states_every_10_seconds(monkeypatch, capsys):
    work = timing.Work(clock=clock(4.0))  # 4 s for each call, so a progress line after each 10 s
    monkeypatch.setattr(timing, "WORK", work)
    timings = timing.Timings(clock=clock(1.0))
    with timings.step("schedule search", search=True):
        search()
    lines = [line for line in capsys.readouterr().out.splitlines() if "so far" in line]
    # begin() reads 4 s, so the first line is due at 14 s. Call n reads 4 + 4n s, so call 3 (16 s) prints it.
    assert lines[0].startswith("  schedule search: 3 calls, ")
    assert len(lines) == len(range(14, 4 + 4 * work.calls + 1, 10))  # one line for each 10 s of the search


def test_no_progress_line_outside_a_search_step(monkeypatch, capsys):
    monkeypatch.setattr(timing, "WORK", timing.Work(clock=clock(100.0)))
    search()
    assert "so far" not in capsys.readouterr().out


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
    with timings.step("schedule search", search=True):
        work.calls += 40
        work.states += 12
    columns, rows = read_rows(path)
    assert columns == timing.COLUMNS
    assert rows[0] == {"run_at": timings.run_at.isoformat(), "days": "3", "open_days": "3", "adds_left": "4",
                       "step": "schedule read", "seconds": "0.12", "calls": "", "states": "", "pages": ""}
    assert (rows[1]["step"], rows[1]["calls"], rows[1]["states"]) == ("schedule search", "40", "12")
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
        with timings.step("schedule search", search=True):
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
        timing.StepTime("role read", 1.0)]
    rows = read_rows(path)[1]
    assert [(r["step"], r["seconds"], r["pages"]) for r in rows] == [
        ("Yahoo reads", "9.00", "13"), ("Yahoo reads: browser start", "1.00", "0"),
        ("Yahoo reads: market pages", "2.00", "12"), ("Yahoo reads: waiver list", "1.00", "1"),
        ("role read", "1.00", "")]
    out = capsys.readouterr().out.splitlines()
    assert "Step: Yahoo reads: 9.00 s, 13 pages" in out
    assert "  Yahoo reads: market pages: 2.00 s, 12 pages" in out


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
    path.write_text("run_at,days,open_days,adds_left,step,seconds,calls,states\n"
                    "2026-10-26T09:00:00,2,2,1,Yahoo reads,31.34,,\n", encoding="utf-8")
    timings = timing.Timings(path=path)
    timings.window([], 5)
    with timings.step("role read"):
        pass
    columns, rows = read_rows(path)
    assert columns == timing.COLUMNS
    assert rows[0] == {"run_at": "2026-10-26T09:00:00", "days": "2", "open_days": "2", "adds_left": "1",
                       "step": "Yahoo reads", "seconds": "31.34", "calls": "", "states": "", "pages": ""}
    assert rows[1]["step"] == "role read"


def test_a_run_with_no_timers_writes_no_file(tmp_path):
    timings = timing.Timings(on=False, path=tmp_path / "timings.csv")
    with timings.step("schedule read"):
        pass
    timings.window([], 5)
    assert not (tmp_path / "timings.csv").exists()
