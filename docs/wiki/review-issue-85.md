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

Related: [Run of issues #73 to #76](run-issues-73-to-76.md) (#74 was the first performance issue of the adds planner), [Environment gaps](environment-gaps.md).
