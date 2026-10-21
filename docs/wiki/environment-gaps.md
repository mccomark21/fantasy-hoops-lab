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
