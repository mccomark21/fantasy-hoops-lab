# Architecture refactors of 2026-10-28

On 2026-10-28, the owner asked the chief of staff to run `/improve-codebase-architecture` and build its candidates with the ticket pipeline. The scan ran at `mccomark21/fantasy-hoops-lab@5e89567`. The HTML report was a temporary file outside the repo. The issues below hold its content.

## Scope

- At first, the owner asked for the top 3 candidates. Later on the same day, the owner asked for all 7.
- The owner rule "no new issues until done" ([Run of 2026-10-28](run-2026-10-28.md)) did not stop this run, because the owner asked for the issues. #112 stayed open.

## Issues and owner decisions (2026-10-28)

| Issue | Refactor | Blocked by | Owner decision |
|---|---|---|---|
| #127 | One output-folder seam | none | An autouse fixture in `tests/conftest.py` points `common.OUT` at `tmp_path`. |
| #128 | One `PlanningRun` result feeds the page and the terminal | #127 | The name is `PlanningRun`. The `main()` tests move to `tests/adds/test_plan.py`. |
| #129 | One module for the free-agent list reads (`adds/lists.py`) | #128 | The function takes `timings.part`, so the #89 timing rows stay. |
| #130 | Terminal report cut to a summary | #128 | Best plan, page path or URL, warnings. The four terminal-only sections (schedule plan, aggressive plan, drop trade-offs, comparison) are dropped, not moved to the page. |
| #131 | One value for the search inputs | #129 | The owner was not sure if the missing `next_week` in `drop_trade_offs`, `spot_plans` (and `contingency_plans`) is intended. The builder researches it and keeps the behaviour. |
| #132 | One site-page module | #127, #128 | No change to the HTML of any page. |
| #133 | One playoff lineup fit | none | The Python rules are the source. The draft board uses them. |

## Corrections to the scan

The issue filer checked the report against the code at `5e89567`. The report had these errors: `render()` takes 25 parameters (not 27). "Planning run" is defined in `docs/adds/README.md`, not the glossary. `run_command()` has 3 path patches (not 4). `core/home.py` uses the Python `best_lineup()`, and only the JS in `draft/board.py` is a copy.

## Waves

- Wave 1 (2026-10-28): #127 and #133 in parallel.
