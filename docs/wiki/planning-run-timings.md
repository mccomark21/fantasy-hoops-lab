# Planning run timings

On 2026-10-26, the chief of staff ran `python -m fantasyhoops.adds.plan --no-publish` two times at `mccomark21/fantasy-hoops-lab@9f11902`. These were the first live runs with the step timers of PR #86. The date was Monday, the first day of the fantasy week.

Source: the rows of `output/adds/timings.csv` with `run_at` 2026-10-26T20:53:52 (first run) and 2026-10-26T20:55:09 (second run). Git ignores that file, so this page copies the numbers into the tables below.

Window of both runs: 7 days, 5 open days, 3 adds left.

## Second run (complete)

The second run ended with exit 0.

| Step | Time (s) | `best()` calls | Unique states |
|---|---|---|---|
| Yahoo reads | 31.34 | | |
| Schedule search | 6.82 | 613,874 | 135,495 |
| Aggressive search | 8.03 | 613,874 | 135,495 |
| Drop trade-offs | 0.47 | 73,765 | 5,193 |
| Value options | 0.30 | | |
| Spot plans | 0.08 | 7,943 | 843 |
| All other steps | under 0.1 each | | |
| Total | about 47 | | |

## First run (crashed)

| Step | Time (s) |
|---|---|
| Yahoo reads | 38.68 |
| Schedule search | 7.03 |
| Aggressive search | 8.51 |

After the spot plans step, the run crashed in the terminal print with `UnicodeEncodeError`. The cp1252 codec cannot encode `'č'`, a character in a player name. The crash occurred because stdout went to a file. For the second run, the chief of staff set `PYTHONIOENCODING=utf-8`. See [Environment gaps](environment-gaps.md).

## Observations

1. This window had 3 adds and 5 open days. The run of 2026-10-25 that did not end had 7 days and 5 adds. Thus these runs did not reproduce the slow case.
2. The schedule search and the aggressive search visit the same count of calls and the same count of states. Thus they likely repeat the same search work. This is an inference from the equal counts. Nobody checked it in the code.

Related: [Review of issue #85](review-issue-85.md), [Yahoo reads study](yahoo-reads-study.md).
