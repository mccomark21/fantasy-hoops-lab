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
