"""The run time of each step of a planning run (#85). The design is in docs/adds/README.md, "Run time".

Timings.step() times one step of plan.main(). It prints the step when it starts and its time when it ends.
WORK counts the work of the plan searches (planner._Search): the calls of best(), cache hits included, and the
unique states that best() computes. During a search, WORK prints the calls and the states every PROGRESS_SECONDS.
A search step writes the counts of all its searches in one row. The other steps write empty counts.
Each step appends its row to output/adds/timings.csv when it ends, so a run that you stop (Ctrl+C) keeps the rows
of its finished steps. The first steps end before the run knows the planning window. Their rows wait until
Timings.window() gives it, or until a step stops the run. Then they get empty window columns.
"""
import csv
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from fantasyhoops.core.common import OUT

TIMINGS = OUT / "adds" / "timings.csv"
COLUMNS = ["run_at", "days", "open_days", "adds_left", "step", "seconds", "calls", "states"]
PROGRESS_SECONDS = 10  # the time between two progress lines of a search


class Work:
    """The counts of the plan searches. tick() counts one call of best(). state() counts one computed state.

    When a step is open (begin()), tick() prints the calls and the states every PROGRESS_SECONDS.
    clock: a function that gives seconds, for the tests.
    """

    def __init__(self, clock=time.monotonic):
        self.clock, self.calls, self.states, self.step, self.next_print = clock, 0, 0, None, None

    def begin(self, step):
        self.step, self.next_print = step, self.clock() + PROGRESS_SECONDS

    def end(self):
        self.step = self.next_print = None

    def tick(self):
        self.calls += 1
        if self.next_print is not None and self.clock() >= self.next_print:
            self.next_print += PROGRESS_SECONDS
            print(f"  {self.step}: {self.calls:,} calls, {self.states:,} states so far", flush=True)

    def state(self):
        self.states += 1


WORK = Work()


@dataclass(frozen=True)
class StepTime:
    """The time of one step. calls and states: the search work of the step, or None for a step with no search."""
    step: str
    seconds: float
    calls: int = None
    states: int = None


class Timings:
    """The step times of one planning run. on False: step() does nothing, and the run writes no row.

    path: the timings file (default: TIMINGS at the time of the first write).
    """

    def __init__(self, on=True, clock=time.perf_counter, work=None, path=None):
        self.on, self.clock, self.work, self.path = on, clock, work or WORK, path
        self.run_at = datetime.now().replace(microsecond=0)
        self.steps, self.head, self.waiting = [], None, []

    def window(self, days, adds_left):
        """Set the window columns: days, the Days of the planning window, and adds_left, the adds left. Then write
        the rows that wait for them."""
        self.head = {"days": len(days), "open_days": sum(bool(d.open) for d in days), "adds_left": adds_left}
        self._flush()

    @contextmanager
    def step(self, name, search=False):
        """Time the code in the with block as the step name. search: the step runs plan searches.

        A step that stops with an error (Ctrl+C too) writes no row. The rows that wait are written first."""
        if not self.on:
            yield
            return
        print(f"Step: {name} ...", flush=True)
        calls, states = self.work.calls, self.work.states
        if search:
            self.work.begin(name)
        start = self.clock()
        try:
            yield
        except BaseException:
            self._flush(stopped=True)
            raise
        finally:
            self.work.end()
        seconds = self.clock() - start
        if search:
            done = StepTime(name, seconds, self.work.calls - calls, self.work.states - states)
            print(f"Step: {name}: {seconds:.2f} s, {done.calls:,} calls, {done.states:,} states", flush=True)
        else:
            done = StepTime(name, seconds)
            print(f"Step: {name}: {seconds:.2f} s", flush=True)
        self.steps.append(done)
        self.waiting.append(done)
        self._flush()

    def _flush(self, stopped=False):
        """Append the rows that wait. Without the window columns, only if stopped, with empty window columns."""
        if not self.waiting or (self.head is None and not stopped):
            return
        head = self.head or {"days": "", "open_days": "", "adds_left": ""}
        rows = [{"run_at": self.run_at.isoformat(), **head, "step": s.step, "seconds": f"{s.seconds:.2f}",
                 "calls": "" if s.calls is None else s.calls, "states": "" if s.states is None else s.states}
                for s in self.waiting]
        self.waiting = []
        append(self.path or TIMINGS, rows)


def append(path, rows):
    """Append rows (dicts with the COLUMNS) to the CSV file path. The first write also writes the header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerows(rows)
