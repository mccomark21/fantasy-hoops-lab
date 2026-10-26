# Review of issue #85

On 2026-10-26, the chief of staff reviewed issue #85 against `mccomark21/fantasy-hoops-lab@3fcc4db`. Issue #85 asks the planner to time each step of a planning run. The owner approved a rewrite of the issue body. For the full text, read issue #85. This page does not copy it.

## Defaults the owner accepted on 2026-10-26

1. The timing counts both the `best()` calls and the unique states.
2. A step that runs more than one search writes one summed row.
3. A skipped step writes no row.
4. The table has two window columns: days and open days.

## Additions in the rewrite

- `drop_trade_offs` is a step. The original issue did not name it. It runs `schedule_plan` again for each holder.
- During a search, the planner prints its progress every 10 s. The chief of staff chose the 10 s value.
- A test checks that the plans are the same with the timers and without them.

## Correction

The original issue suggested that the contingency plans search. At `@3fcc4db`, they do not search. See `src/fantasyhoops/adds/contingency.py` lines 63 to 113.

## Build and merge on 2026-10-26

1. The builder opened PR #86. For the decisions of the build, read the [Decision comment on #85](https://github.com/mccomark21/fantasy-hoops-lab/issues/85#issuecomment-6429035216). This page does not copy it.
2. The first review at `787b43a` found no blockers and two nits. See [the review comment on PR #86](https://github.com/mccomark21/fantasy-hoops-lab/pull/86#issuecomment-6429082701). The orchestrator chose to fix both nits before the merge.
3. The second review at `090cf68` found no blockers. See [the second review comment on PR #86](https://github.com/mccomark21/fantasy-hoops-lab/pull/86#issuecomment-6429159458).
4. PR #86 was squash-merged as `mccomark21/fantasy-hoops-lab@131fdc0`. For the close-out, read [the closing comment on #85](https://github.com/mccomark21/fantasy-hoops-lab/issues/85#issuecomment-6429170400).

One nit of the first review mattered. At `787b43a`, the planner wrote `timings.csv` only at the end of `main()`. Thus a run that stopped on Ctrl+C left no rows. The run of 2026-10-25 that led to #85 stopped in this way. The fix writes each row when its step ends.

The second review left two optional nits open:

- `Timings.window()` has no guard for the case where timing is off.
- If the run stops outside a step before `window()`, the waiting rows are lost.

Not checked: nobody ran the planner live, because the worktree had no `data/` folder and no Yahoo session. The first full-week run must check the step times and the 10 s progress lines.

Related: [Run of issues #73 to #76](run-issues-73-to-76.md) (#74 was the first performance issue of the adds planner), [Environment gaps](environment-gaps.md).
