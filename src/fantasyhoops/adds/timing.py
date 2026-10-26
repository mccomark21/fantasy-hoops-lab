"""The run time of each step of a planning run (#85). The design is in docs/adds/README.md, "Run time".

Timings.step() times one step of plan.main(). It prints the step when it starts and its time when it ends.
WORK counts the work of the plan searches (planner._Search): the calls of best(), cache hits included, and the
unique states that best() computes. During a search, WORK prints the calls and the states every PROGRESS_SECONDS.
A search step writes the counts of all its searches in one row. The other steps write empty counts.
write() appends one row for each step to output/adds/timings.csv.
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
    """The step times of one planning run. on False: step() does nothing, and the run has no times."""

    def __init__(self, on=True, clock=time.perf_counter, work=None):
        self.on, self.clock, self.work = on, clock, work or WORK
        self.run_at = datetime.now().replace(microsecond=0)
        self.steps = []

    @contextmanager
    def step(self, name, search=False):
        """Time the code in the with block as the step name. search: the step runs plan searches."""
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


def rows(timings, days, adds_left):
    """The rows of timings.csv for one run. days: the Days of the planning window. adds_left: the adds left."""
    head = {"run_at": timings.run_at.isoformat(), "days": len(days), "open_days": sum(bool(d.open) for d in days),
            "adds_left": adds_left}
    return [{**head, "step": s.step, "seconds": f"{s.seconds:.2f}",
             "calls": "" if s.calls is None else s.calls, "states": "" if s.states is None else s.states}
            for s in timings.steps]


def write(timings, days, adds_left, path=None):
    """Append the rows of one run to path (default: TIMINGS). Nothing if the run has no step times."""
    path = path or TIMINGS
    new_rows = rows(timings, days, adds_left)
    if not new_rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerows(new_rows)
