"""A benchmark of the plan searches (#100): schedule_plan() and aggressive_plan() on fixed synthetic inputs.

Run it with python -m fantasyhoops.adds.bench. It runs the CASES, prints one line when each case starts and ends,
prints a table of the results and appends the rows to output/adds/bench.csv.

The inputs come from code and a seed. No Yahoo page, no data/ file and no output/ file is an input. The same
seed gives the same inputs, the same calls and the same states. tests/adds/test_bench.py runs the same inputs.

The inputs (search_inputs()):
- games: the NBA games of the week of 2026-10-26 to 2026-11-01, copied from data/schedule.csv. A window of D days
  is the last D days of that week. NEXT_WEEK: the games of each team from 2026-11-02 to 2026-11-08.
- days: open_slots_by_day() on ROSTER, 7 fixed players. ROSTER leaves 5 of the 7 days of the week open.
- spots: [adds] stream_spots empty StreamSpots. No spot has a holder.
- free_agents: TEAM_FREE_AGENTS for each team of teams_to_read(), plus MARKET_FREE_AGENTS on random teams. Each
  free agent gets random positions from POSITIONS and a random value. No free agent is Out, on waivers or on the
  rest list.
- slots and next_week_weight: from config.toml, as in a planning run.

A case that passes the cap (timing.Capped) ends as "capped". That is a result: the search with these inputs does
not end under the cap.
"""

import argparse
import csv
import random
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fantasyhoops.adds import timing
from fantasyhoops.adds.planner import Option, StreamSpot, aggressive_plan, rank_teams, schedule_plan, teams_to_read
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.core import common
from fantasyhoops.core.common import ROOT, load_config
from fantasyhoops.core.console import use_utf8_output

COLUMNS = [
    "run_at",
    "commit",
    "seed",
    "search",
    "days",
    "open_days",
    "adds",
    "spots",
    "free_agents",
    "calls",
    "states",
    "seconds",
    "capped",
]


def bench_path():
    """The results file: output/adds/bench.csv, from common.OUT at the time of the call."""
    return common.OUT / "adds" / "bench.csv"


SEED = 1
WEEK = [date(2026, 10, 26) + timedelta(days=i) for i in range(7)]
# The teams that play on each day of WEEK, from data/schedule.csv: 18, 8, 24, 6, 20, 14 and 8 teams.
GAMES = {
    d: frozenset(teams)
    for d, teams in zip(
        WEEK,
        [
            [
                "ATL",
                "BOS",
                "CHA",
                "CHI",
                "CLE",
                "DAL",
                "DEN",
                "GS",
                "HOU",
                "IND",
                "MEM",
                "MIA",
                "MIL",
                "MIN",
                "OKC",
                "PHX",
                "UTAH",
                "WSH",
            ],
            ["BKN", "BOS", "DET", "LAL", "NY", "POR", "SA", "SAC"],
            [
                "ATL",
                "CHA",
                "CHI",
                "CLE",
                "DAL",
                "DEN",
                "DET",
                "GS",
                "HOU",
                "IND",
                "LAC",
                "LAL",
                "MIA",
                "MIL",
                "MIN",
                "NO",
                "NY",
                "OKC",
                "ORL",
                "PHI",
                "SA",
                "TOR",
                "UTAH",
                "WSH",
            ],
            ["ATL", "CLE", "MEM", "NO", "POR", "SAC"],
            [
                "BKN",
                "BOS",
                "CHA",
                "CHI",
                "DAL",
                "DEN",
                "DET",
                "GS",
                "HOU",
                "IND",
                "LAC",
                "LAL",
                "MIA",
                "MIN",
                "NY",
                "ORL",
                "PHI",
                "PHX",
                "TOR",
                "WSH",
            ],
            ["ATL", "CHA", "CLE", "HOU", "MEM", "MIL", "MIN", "NO", "OKC", "PHI", "POR", "SA", "SAC", "UTAH"],
            ["BKN", "BOS", "GS", "IND", "LAC", "LAL", "ORL", "TOR"],
        ],
    )
}
TEAMS = sorted(set().union(*GAMES.values()))
# The games of each team from 2026-11-02 to 2026-11-08, from data/schedule.csv (slots.next_week_games()).
NEXT_WEEK = {
    "ATL": 4,
    "BKN": 4,
    "BOS": 4,
    "CHA": 3,
    "CHI": 3,
    "CLE": 4,
    "DAL": 4,
    "DEN": 3,
    "DET": 3,
    "GS": 3,
    "HOU": 3,
    "IND": 3,
    "LAC": 3,
    "LAL": 4,
    "MEM": 3,
    "MIA": 4,
    "MIL": 4,
    "MIN": 4,
    "NO": 4,
    "NY": 3,
    "OKC": 4,
    "ORL": 3,
    "PHI": 4,
    "PHX": 4,
    "POR": 4,
    "SA": 4,
    "SAC": 4,
    "TOR": 3,
    "UTAH": 4,
    "WSH": 4,
}
# The roster without the stream spots. ROSTER fills all 6 starting slots on Wed and Fri and leaves the other 5
# days of WEEK open.
ROSTER = [
    Player("R1", "LAL", ("PG",)),
    Player("R2", "NY", ("SG",)),
    Player("R3", "PHI", ("SF",)),
    Player("R4", "DET", ("PF",)),
    Player("R5", "TOR", ("C",)),
    Player("R6", "ORL", ("SF", "PF")),
    Player("R7", "LAC", ("PG", "SG")),
]
# The position sets of the free agents, each one equally likely. The size of the search depends on the base keys
# of each open day, so this list is the calibration (#100): with 7 days, 5 open days and 3 adds, the calls fall in
# the range of the live runs of 2026-10-26 (275,995 to 613,874). With ("SG",) and ("SF",) too, the calls were
# 864,733, above that range.
POSITIONS = [("PG",), ("PG", "SG"), ("SG", "SF"), ("SF", "PF"), ("PF",), ("PF", "C"), ("C",)]
TEAM_FREE_AGENTS = 19  # the free agents of each read team: 151 over 8 teams (docs/wiki/yahoo-reads-study.md)
MARKET_FREE_AGENTS = 75  # 3 market pages of 25 players (lists.MARKET_PAGES)
EMPTY_VALUE = -4.0  # the value of an empty slot for the aggressive score. Each free agent has a higher value.


@dataclass(frozen=True)
class Inputs:
    """The arguments of schedule_plan() for one case, without adds_left."""

    days: list
    games: dict
    spots: list
    free_agents: list
    slots: list
    next_week: dict
    next_weight: float


@dataclass(frozen=True)
class Case:
    """One benchmark case. search: "schedule" or "aggressive". days: the days of the window (D). adds: adds left (A)."""

    search: str
    days: int
    adds: int


CASES = [Case(s, d, a) for s in ("schedule", "aggressive") for d in (5, 7) for a in (3, 4, 5)]


@dataclass(frozen=True)
class Result:
    """The result of one case. capped: the search passed the cap. plan: None for a capped case."""

    case: Case
    open_days: int
    spots: int
    free_agents: int
    calls: int
    states: int
    seconds: float
    capped: bool
    plan: object = None


def search_inputs(days=7, seed=SEED, cfg=None):
    """The Inputs for a window of the last days days of WEEK. See the module docstring."""
    cfg = cfg or load_config()
    slots = cfg["league"]["slots"]
    window = WEEK[-days:]
    games = {d: set(GAMES[d]) for d in window}
    day_list = open_slots_by_day(ROSTER, games, slots)
    rng = random.Random(seed)
    teams = teams_to_read(rank_teams(day_list, games))
    homes = [t for t in teams for _ in range(TEAM_FREE_AGENTS)]
    homes += [rng.choice(TEAMS) for _ in range(MARKET_FREE_AGENTS)]
    free_agents = [
        Option(Player(f"FA{n}", team, rng.choice(POSITIONS)), round(rng.gauss(-1.0, 1.0), 2))
        for n, team in enumerate(homes)
    ]
    return Inputs(
        day_list,
        games,
        [StreamSpot()] * cfg["adds"]["stream_spots"],
        free_agents,
        slots,
        NEXT_WEEK,
        cfg["adds"].get("next_week_weight", 0.0),
    )


def run_case(case, seed=SEED, limit=None, seconds=None, cfg=None, prune=None):
    """Run one case with a new timing.Work and give its Result. limit, seconds: the cap of the Work.

    prune: the prune argument of schedule_plan() and aggressive_plan(). None is the prune of a planning run. False
    gives the search with no prune (#110).
    """
    inputs = search_inputs(case.days, seed, cfg)
    work, saved = timing.Work(limit=limit, seconds=seconds), timing.WORK
    timing.WORK = work
    start, plan, capped = time.perf_counter(), None, False
    try:
        args = (inputs.days, inputs.games, inputs.spots, inputs.free_agents, case.adds, inputs.slots)
        if case.search == "schedule":
            plan = schedule_plan(*args, next_week=inputs.next_week, next_weight=inputs.next_weight, prune=prune)
        else:
            plan = aggressive_plan(
                *args, EMPTY_VALUE, next_week=inputs.next_week, next_weight=inputs.next_weight, prune=prune
            )
    except timing.Capped:
        capped = True
    finally:
        timing.WORK = saved
    return Result(
        case,
        sum(bool(d.open) for d in inputs.days),
        len(inputs.spots),
        len(inputs.free_agents),
        work.calls,
        work.states,
        time.perf_counter() - start,
        capped,
        plan,
    )


def rows(results, seed, run_at, commit):
    """The bench.csv rows (dicts with the COLUMNS) of results."""
    return [
        {
            "run_at": run_at,
            "commit": commit,
            "seed": seed,
            "search": r.case.search,
            "days": r.case.days,
            "open_days": r.open_days,
            "adds": r.case.adds,
            "spots": r.spots,
            "free_agents": r.free_agents,
            "calls": r.calls,
            "states": r.states,
            "seconds": f"{r.seconds:.2f}",
            "capped": r.capped,
        }
        for r in results
    ]


def table(results):
    """The text table of results, one line for each case."""
    head = ["search", "D", "open days", "A", "S", "free agents", "calls", "states", "seconds", "capped"]
    body = [
        [
            r.case.search,
            r.case.days,
            r.open_days,
            r.case.adds,
            r.spots,
            r.free_agents,
            f"{r.calls:,}",
            f"{r.states:,}",
            f"{r.seconds:.2f}",
            "capped" if r.capped else "no",
        ]
        for r in results
    ]
    widths = [max(len(str(x)) for x in col) for col in zip(head, *body)]
    return "\n".join("  ".join(str(x).rjust(w) for x, w in zip(line, widths)) for line in [head, *body])


def append(path, new_rows):
    """Append new_rows to the CSV file path. The first write also writes the header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerows(new_rows)


def commit():
    """The short commit of the checkout, or "" if git does not give it."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark the plan searches on fixed synthetic inputs (#100).")
    parser.add_argument("--seed", type=int, default=SEED, help="the seed of the free agents")
    parser.add_argument(
        "--max-calls",
        type=int,
        default=55_000_000,
        help="the cap on the calls of one case (55 million is about 10 minutes at 90k calls/s)",
    )
    parser.add_argument("--max-seconds", type=float, default=600.0, help="the cap on the seconds of one case")
    args = parser.parse_args(argv)
    cfg, run_at, results = load_config(), datetime.now().replace(microsecond=0).isoformat(), []
    for case in CASES:
        print(f"Start: {case.search} D={case.days} A={case.adds} ...", flush=True)
        r = run_case(case, args.seed, args.max_calls, args.max_seconds, cfg)
        end = "capped" if r.capped else "done"
        print(
            f"End: {case.search} D={case.days} A={case.adds}: {end}, {r.seconds:.2f} s, {r.calls:,} calls, "
            f"{r.states:,} states",
            flush=True,
        )
        results.append(r)
    print()
    print(table(results))
    path = bench_path()
    append(path, rows(results, args.seed, run_at, commit()))
    print(f"\nWrote {len(results)} rows to {path}")


if __name__ == "__main__":
    use_utf8_output()
    main()
