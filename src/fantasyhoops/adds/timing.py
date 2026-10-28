"""The run time of each step of a planning run (#85). The design is in docs/adds/README.md, "Run time".

Timings.step() times one step of plan.main(). It prints nothing (#130): the Run time table of the plan page and
output/adds/timings.csv show the times.
WORK counts the work of the plan searches (planner._Search): the calls of best(), cache hits included, and the
unique states that best() computes. A search step writes the counts of all its searches in one row. The other steps write empty counts.
Timings.part() times one sub-step of the open step (#89), for example the market pages of the Yahoo reads. A sub-step
can have more than one timed block. Its row adds the seconds and the pages of all its blocks. The pages are the
Yahoo pages that League.get() opens (session.py). The step row gets the sum of the pages of its sub-steps and comes
first. Then each sub-step gets a row, named "<step>: <sub-step>". A step with no sub-step has empty pages.
Each step appends its row to output/adds/timings.csv when it ends, so a run that you stop (Ctrl+C) keeps the rows
of its finished steps. The first steps end before the run knows the planning window. Their rows wait until
Timings.window() gives it, or until a step stops the run. Then they get empty window columns.
A timings file with an older header gets the new header at the next write. Its old rows get empty new columns.
A Work with a cap (limit, seconds) raises Capped in tick() when the search passes the cap. The benchmark (#100,
adds/bench.py) uses it. WORK has no cap, so a planning run never stops for it.
"""

import csv
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from fantasyhoops.core import common

COLUMNS = ["run_at", "days", "open_days", "adds_left", "step", "seconds", "calls", "states", "pages"]


def timings_path():
    """The timings file: output/adds/timings.csv, from common.OUT at the time of the call."""
    return common.OUT / "adds" / "timings.csv"


class Capped(Exception):
    """A search passed the cap of its Work. The search does not end under the cap."""


class Work:
    """The counts of the plan searches. tick() counts one call of best(). state() counts one computed state.

    clock: a function that gives seconds, for the tests.
    limit: the most calls. seconds: the most seconds from the start of this Work, by clock. When the calls or the
    time pass the cap, tick() raises Capped. None: no cap. Each cap check costs time, so leave seconds None in CI.
    """

    def __init__(self, clock=time.monotonic, limit=None, seconds=None):
        self.clock, self.calls, self.states = clock, 0, 0
        self.limit, self.stop = limit, None if seconds is None else clock() + seconds

    def tick(self):
        self.calls += 1
        if self.limit is not None and self.calls > self.limit:
            raise Capped(f"The search passed {self.limit:,} calls.")
        if self.stop is not None and self.clock() >= self.stop:
            raise Capped(f"The search passed its time limit at {self.calls:,} calls.")

    def state(self):
        self.states += 1


WORK = Work()


@dataclass(frozen=True)
class StepTime:
    """The time of one step. calls and states: the search work of the step, or None for a step with no search.

    pages: the Yahoo pages of the step, or None for a step with no sub-step. parent: for a sub-step, the name of
    its step. Then step is "<parent>: <sub-step>".
    """

    step: str
    seconds: float
    calls: int = None
    states: int = None
    pages: int = None
    parent: str = None


class Timings:
    """The step times of one planning run. on False: step() does nothing, and the run writes no row.

    path: the timings file (default: timings_path() at the time of the first write).
    """

    def __init__(self, on=True, clock=time.perf_counter, work=None, path=None):
        self.on, self.clock, self.work, self.path = on, clock, work or WORK, path
        self.run_at = datetime.now().replace(microsecond=0)
        self.steps, self.head, self.waiting = [], None, []
        self.parts = None  # {sub-step name: [seconds, pages]} of the open step, in the order of the first block

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
        calls, states = self.work.calls, self.work.states
        self.parts = {}
        start = self.clock()
        try:
            yield
        except BaseException:
            self._flush(stopped=True)
            raise
        finally:
            parts, self.parts = self.parts, None
        seconds = self.clock() - start
        pages = sum(p for _, p in parts.values()) if parts else None
        if search:
            done = StepTime(name, seconds, self.work.calls - calls, self.work.states - states, pages)
        else:
            done = StepTime(name, seconds, pages=pages)
        done = [done] + [StepTime(f"{name}: {part}", s, pages=p, parent=name) for part, (s, p) in parts.items()]
        self.steps += done
        self.waiting += done
        self._flush()

    @contextmanager
    def part(self, name, league=None):
        """Time the code in the with block as the sub-step name of the open step. league: the session.League whose
        pages the sub-step counts. None: the sub-step opens no Yahoo page, so it has 0 pages.

        Two blocks with the same name add into one sub-step. A block outside a step raises RuntimeError.
        """
        if not self.on:
            yield
            return
        if self.parts is None:
            raise RuntimeError(f"The sub-step {name!r} is not in a step. Put it in a with block of Timings.step().")
        pages, start = league.pages if league else 0, self.clock()
        yield
        seconds, pages = self.clock() - start, (league.pages if league else 0) - pages
        total = self.parts.setdefault(name, [0.0, 0])
        total[0] += seconds
        total[1] += pages

    def _flush(self, stopped=False):
        """Append the rows that wait. Without the window columns, only if stopped, with empty window columns."""
        if not self.waiting or (self.head is None and not stopped):
            return
        head = self.head or {"days": "", "open_days": "", "adds_left": ""}
        rows = [
            {
                "run_at": self.run_at.isoformat(),
                **head,
                "step": s.step,
                "seconds": f"{s.seconds:.2f}",
                "calls": "" if s.calls is None else s.calls,
                "states": "" if s.states is None else s.states,
                "pages": "" if s.pages is None else s.pages,
            }
            for s in self.waiting
        ]
        self.waiting = []
        append(self.path or timings_path(), rows)


def append(path, rows):
    """Append rows (dicts with the COLUMNS) to the CSV file path. The first write also writes the header.

    If the file has a header other than COLUMNS (a file of an older version), append() first writes the file again
    with the COLUMNS header. The old rows keep their values and get empty values in the new columns.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    if not new:
        _upgrade(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def _upgrade(path):
    """Write the file path again with the COLUMNS header, if its header is different. See append()."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == COLUMNS:
            return
        old = list(reader)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(old)
