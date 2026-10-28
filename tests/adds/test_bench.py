from functools import cache

import pytest

from fantasyhoops.adds import bench, timing
from fantasyhoops.adds.bench import Case

# The ceilings of the cases that end in a few seconds: (calls, states), about 2 times the counts of the search with
# the prune (#110, 2026-10-27). The counts are deterministic, so a ceiling never fails by chance. Both searches had
# the same counts.
CEILINGS = {
    (5, 3): (20_000, 8_100),  # 9,545 calls, 4,030 states (22,660 and 9,688 with no prune)
    (5, 4): (125_000, 22_000),  # 61,768 calls, 10,952 states (188,902 and 25,718 with no prune)
    (7, 3): (350_000, 135_000),  # 175,303 calls, 67,259 states (495,295 and 194,726 with no prune)
}
# The base case calibrates the inputs (#100). CI runs each case once with the prune and once with no prune, so the
# tests of this file take about 30 s.
BASE = Case("schedule", 7, 3)
CI_CASES = [Case(s, d, a) for s in ("schedule", "aggressive") for d, a in CEILINGS]


@cache
def run(case, prune=None):
    """The Result of a case with the default seed and no cap. Each case and prune runs once in this file."""
    return bench.run_case(case, prune=prune)


@pytest.fixture(autouse=True)
def no_real_file(monkeypatch, tmp_path):
    """The tests never write the real output/adds/bench.csv."""
    monkeypatch.setattr(bench, "BENCH", tmp_path / "bench.csv")


@pytest.mark.parametrize("case", CI_CASES, ids=lambda c: f"{c.search}-D{c.days}-A{c.adds}")
def test_the_calls_and_the_states_stay_below_the_ceiling(case):
    r = run(case)
    calls, states = CEILINGS[case.days, case.adds]
    assert not r.capped
    assert r.calls <= calls
    assert r.states <= states


@pytest.mark.parametrize("case", CI_CASES, ids=lambda c: f"{c.search}-D{c.days}-A{c.adds}")
def test_the_prune_gives_the_plan_of_the_search_with_no_prune(case):
    # #110: == on the Plan, so the windows and the window options match too.
    pruned, old = run(case), run(case, prune=False)
    assert pruned.plan is not None
    assert pruned.plan == old.plan
    assert pruned.calls < old.calls


def test_the_base_case_has_the_calls_of_the_live_runs():
    # The live runs of 2026-10-26 with 7 days, 5 open days and 3 adds had 275,995 to 613,874 calls (#89, #90, #92).
    # Those runs had no prune, so the check uses the search with no prune.
    r = run(BASE, prune=False)
    assert (r.open_days, r.spots) == (5, 3)
    assert 276_000 <= r.calls <= 614_000


def test_the_inputs_are_the_week_of_the_issue():
    inputs = bench.search_inputs(7)
    assert [d.date for d in inputs.days] == bench.WEEK
    assert sum(bool(d.open) for d in inputs.days) == 5
    assert len(inputs.free_agents) == 8 * bench.TEAM_FREE_AGENTS + bench.MARKET_FREE_AGENTS
    assert [d.date for d in bench.search_inputs(5).days] == bench.WEEK[2:]


def test_the_same_seed_gives_the_same_inputs_and_counts():
    assert bench.search_inputs(7, seed=3) == bench.search_inputs(7, seed=3)
    assert bench.search_inputs(7, seed=3) != bench.search_inputs(7, seed=4)
    first, second = (bench.run_case(Case("schedule", 5, 3), seed=3) for _ in range(2))
    assert (first.calls, first.states, first.plan) == (second.calls, second.states, second.plan)


def test_a_low_cap_stops_a_search_and_the_result_says_capped(capsys):
    r = bench.run_case(Case("schedule", 7, 5), limit=50_000)
    assert r.capped and r.plan is None
    assert r.calls == 50_001  # the call that passes the cap raises
    assert "capped" in bench.table([r]).splitlines()[1].split()
    assert timing.WORK.limit is None  # run_case() puts back the WORK of the planning run


@pytest.mark.parametrize("search", ["schedule", "aggressive"])
def test_a_cap_that_the_search_does_not_reach_changes_no_plan(search):
    free = bench.run_case(Case(search, 5, 3))
    capped = bench.run_case(Case(search, 5, 3), limit=free.calls, seconds=3600)
    assert not capped.capped
    assert capped.plan == free.plan
    assert (capped.calls, capped.states) == (free.calls, free.states)


def test_main_prints_the_table_and_appends_the_rows(monkeypatch, capsys):
    monkeypatch.setattr(bench, "CASES", [Case("schedule", 5, 3), Case("aggressive", 7, 5)])
    bench.main(["--max-calls", "30000"])
    bench.main(["--max-calls", "30000"])
    out = capsys.readouterr().out
    assert "Start: schedule D=5 A=3 ..." in out
    assert "End: aggressive D=7 A=5: capped" in out
    lines = bench.BENCH.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(bench.COLUMNS)
    assert len(lines) == 5  # one header, then 2 rows for each run
    assert [line.split(",")[-1] for line in lines[1:]] == ["False", "True"] * 2
