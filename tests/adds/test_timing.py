import csv
from datetime import date, timedelta

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import Option, StreamSpot, schedule_plan
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


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


def test_write_appends_one_row_for_each_step(tmp_path):
    days = open_slots_by_day([], {d: {"PHI"} for d in WEEK[:3]}, SLOTS)
    path = tmp_path / "timings.csv"
    for _ in range(2):
        timings = timing.Timings(on=True)
        timings.steps = [timing.StepTime("schedule read", 0.123), timing.StepTime("schedule search", 2.0, 40, 12)]
        timing.write(timings, days, 4, path)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert reader.fieldnames == timing.COLUMNS
    assert len(rows) == 4
    assert rows[0] == {"run_at": timings.run_at.isoformat(), "days": "3", "open_days": "3", "adds_left": "4",
                       "step": "schedule read", "seconds": "0.12", "calls": "", "states": ""}
    assert (rows[1]["calls"], rows[1]["states"]) == ("40", "12")
    assert len(rows[0]["run_at"]) == len("2026-10-25T21:04:33")


def test_write_writes_nothing_for_a_run_with_no_steps(tmp_path):
    timing.write(timing.Timings(on=False), [], 0, tmp_path / "timings.csv")
    assert not (tmp_path / "timings.csv").exists()
