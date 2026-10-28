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
- On 2026-10-28, PR #134 (#127) merged as `mccomark21/fantasy-hoops-lab@051b33d`. An autouse fixture gives each test its own output folder, and the session fails if a test changes the real `output/`.
- On 2026-10-28, PR #135 (#133) merged as `mccomark21/fantasy-hoops-lab@a92ac48`. `core/lineup.py` holds the lineup-fit rules for the home page and the draft board. It also moved `draft/board.py` to `out_dir()` and removed `draft.OUT`, which #134 had left.
- Wave 2 (2026-10-28): #128 started after the merge of #134.

## Environment notes (2026-10-28)

- Two builders reported that in an agent worktree, the installed package points at the main checkout, so `pytest` tests the main checkout's code unless `PYTHONPATH=src` is set. A possible fix is `pythonpath = ["src"]` in the pytest section of `pyproject.toml`. No issue filed (owner rule: no new issues until done).
- Review nits of #135, not built: `ideal_games()` counts only game days (the same result today, because each playoff day comes from a game date); `data.ideal[w][core.length]` is undefined for a core larger than the spots (`addPlayer` stops at spots).

## Wave 2 and the plan for waves 3 to 5 (2026-10-28)

- On 2026-10-28, PR #136 (#128) merged as `mccomark21/fantasy-hoops-lab@488017a`. `main()` builds one `PlanningRun`, and the page and the terminal report read from it. The reviewer ran the old code at `0e00103`, and its page and terminal output matched the new fixtures byte for byte. The chief of staff accepted one change in timed runs: the "contingency plans" and "role read" step lines print before the report. #130 removes them.
- Wave 3: #129 (`adds/lists.py`) and #132 (site shell) in parallel, because they change different files.
- Wave 4: #130 after #129, because both change `adds/plan.py`. Review nit on #136: #130 can remove the `PlanningRun` fields that only the report uses.
- Wave 5: #131 after #130. #130 can remove the terminal-only outputs, such as the drop trade-offs, and #131 bundles the inputs of the searches that remain.

## Wave 3 results (2026-10-28)

- On 2026-10-28, PR #138 (#129) merged as `mccomark21/fantasy-hoops-lab@9276275`. `adds/lists.py` holds the list reads, and `read_lists()` times its own four sub-steps. Review nits, not built: `ListPages` has a copy in `tests/adds/test_lists.py` and in `tests/adds/test_plan.py`; `test_the_page_shows_why_the_market_read_stopped` tests only `lists.market_line()`.
- On 2026-10-28, PR #137 (#132) merged as `mccomark21/fantasy-hoops-lab@8efb0f7`. The first review (at `591edb8`) found a blocker: the builder made `cfg` optional in `publish()` so that `adds/plan.py` did not change, and the None path read `config.toml`. That brought back the hidden read that #132 set out to remove. The fix made `cfg` required. A dated Decision comment on #132 supersedes the "optional" claim.
- Lesson of 2026-10-28: a "Do not change file X" line in a builder brief can push the builder to an optional parameter that hides the old behaviour. A brief should allow a minimal call-site change in a shared file, as the fix brief for #137 did.
- Lesson of 2026-10-28: a SendMessage to a builder that is still working queues. The builder of #137 finished its first task and reported before it read the queued rebase message. Check the head (ancestor of `origin/main`, the expected diff) before you start a reviewer.
