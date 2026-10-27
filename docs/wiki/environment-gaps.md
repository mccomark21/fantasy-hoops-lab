# Environment gaps

Dated observations of what the repo did not have. Each item names the date of the observation.

| Date | Observation | Source |
|---|---|---|
| 2026-10-21 | The repo had no `CODING_STANDARDS.md` and no `CONTRIBUTING` file. | Audit of #42 |
| 2026-10-21 | PR #54 had 0 CI checks. The tests ran only on the local machine (323 passed). | Audit of #42, PR #54 |
| 2026-10-21 | `.claude/` held only an empty `worktrees/` folder. | Audit of #42 |
| 2026-10-21 | The repo had no agent docs (no `docs/agents/`). The `/ship-it` convention lived only in the owner's global skills, outside the repo. | Audit of #42 |

## Effects

- With no CI checks, a reviewer of PR #54 had no automatic test result. See [Owner merges PR #54](decision-owner-merges-pr-54.md).
- With no agent docs in the repo, the #42 build agents may not have known the `/ship-it` close-out. They did not follow it. See [Ticket workflow](ticket-workflow.md).

## Update on 2026-10-21

- The owner approved a CI workflow and a CODING_STANDARDS.md (issue #55, PR #56, branch `chore/ci-and-standards`). On 2026-10-21, the `pytest` check on PR #56 passed (run 39612852735). The owner merges PR #56.
- In CI, 6 tests in `tests/draft/test_team_builder.py` skip, because git does not track `data/schedule.csv` or the projections file. See the Decision comment on #55.
- The owner did not choose the weekly wiki lint schedule on 2026-10-21.
- When PR #56 merges, the "no CI checks" and "no CODING_STANDARDS.md" gaps above are superseded.
- On 2026-10-21, the owner merged PR #56 (`mccomark21/fantasy-hoops-lab@0f485ab`). This supersedes the "no CI checks" and "no CODING_STANDARDS.md" gaps above. On 2026-10-21, the first push runs on main waited about 1 minute in the queue and then passed.
- On 2026-10-21, agent worktrees under `.claude/worktrees/` had no `data/` folder and no Yahoo session, so no build agent of #59 to #65 could run the planner live. A suggested fix is `"worktree": {"symlinkDirectories": ["data"]}` in `.claude/settings.local.json`. Auto mode does not let an agent change settings, so the owner must add it. See [Run of issues #59 to #65](run-issues-59-to-65.md).

## Update on 2026-10-26

- At `mccomark21/fantasy-hoops-lab@3fcc4db`, `run_command` in `tests/adds/test_page.py` (lines 416 to 454) runs `main()` end to end in 9 tests. It patches only `page.PAGE`. Thus a feature that writes a new file under `output/` writes the real file during the tests, unless each issue tells the builder to patch that file. A possible fix is one fixture that points `core.common.OUT` at `tmp_path`. See [Review of issue #85](review-issue-85.md).
- On 2026-10-26, PR #86 (`mccomark21/fantasy-hoops-lab@131fdc0`) handled the test-path gap above for `timings.csv` only: `run_command` patches `timing.TIMINGS`. The general fixture for `core.common.OUT` is still open. See [Review of issue #85](review-issue-85.md).
- Idea: after #85 merges, add a CI benchmark test. The test uses a fixed input for a full week and sets a ceiling on the count of search states. #74 and #85 are the two performance issues of the adds planner to date.
- On 2026-10-26, at `mccomark21/fantasy-hoops-lab@9f11902`, the terminal print of the planner failed with `UnicodeEncodeError` when stdout was not UTF-8 (output redirected to a file on Windows). This affects any scheduled or logged run. With `PYTHONIOENCODING=utf-8`, the run ended with exit 0. See [Planning run timings](planning-run-timings.md).
