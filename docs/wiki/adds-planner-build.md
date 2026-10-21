# Adds planner build

The weekly adds planner is the tool that plans the 5 weekly adds of the league. Its design and usage are in [docs/adds/README.md](../adds/README.md). This page records how the build went.

## Timeline

1. On 2026-10-20, the owner opened epic #42 "Weekly adds planner" with sub-issues #43 to #53.
2. On 2026-10-20, commit `5385487` added the design, the glossary and the first ADRs ([ADR 1](../adr/0001-playwright-for-league-data.md), [ADR 2](../adr/0002-publish-adds-plan-publicly.md)).
3. On 2026-10-20, the ticket work went onto branch `feat/adds-planner`. Most tickets came in as local merge commits, for example `966993f` (#44), `aee2a0c` (#45) and `2c6afc8` (#50). See [Ticket workflow](ticket-workflow.md).
4. On 2026-10-20, commit `6eee3c3` marked the planner as built in the guide.
5. On 2026-10-20, PR #54 "feat: weekly adds planner" opened from `feat/adds-planner` to `main`.
6. On 2026-10-20, the owner approved a publish. Commit `2c37422` on `gh-pages` published `/`, `/adds/` and `/draft/`.
7. On 2026-10-20, commit `39c7df7` added a nav bar, and commit `a73ee76` redesigned the plan page. See [Page redesign kept](decision-page-redesign-kept.md).

## Ticket status on 2026-10-21

The source is the audit of #42 on 2026-10-21. As of `mccomark21/fantasy-hoops-lab@a73ee76`, `python -m pytest -q` gave 323 passed and 0 failed.

| Ticket | Status on 2026-10-21 | Note |
|---|---|---|
| #43 P1 lineup in core | Done | Commit `bcc5c04`. |
| #44 P2 per-game value | Done | Merge `966993f`. |
| #45 1 read team, open slots | Done, owner check left | See [Owner follow-ups](decision-owner-follow-ups.md). |
| #46 2 schedule plan | Done, owner check left | See [Owner follow-ups](decision-owner-follow-ups.md). |
| #47 3 blended value | Done | The page after `a73ee76` shows market value. The terminal shows the three values. |
| #48 4 trend | Done, with a caveat | Nobody tested the "this week" sum for a `date=` older than yesterday. |
| #49 5 core list, drops | Done, owner step left | See [Owner follow-ups](decision-owner-follow-ups.md). |
| #50 6 aggressive plan | Done | The audit found a wording conflict in the guide on the score. See [Adds build decisions](adds-build-decisions.md). |
| #51 7 contingency | Done | Commit `f92ac44`. |
| #52 8 plan page | Partial, scope changed | See [Page redesign kept](decision-page-redesign-kept.md). |
| #53 9 site publish | Done | Commit `d501c64`. |
| #42 parent | Open | Closes when PR #54 merges. |

On 2026-10-21, all 12 issues were open with 0 comments.

## PR #54 on 2026-10-21

- PR #54 was open, not a draft, with 0 CI checks and 0 comments. See [Environment gaps](environment-gaps.md).
- Branch `feat/adds-planner` was 26 commits ahead of `main` and 0 behind.
- The PR body ends with "Closes #42" through "closes #53". A merge closes all 12 issues, but adds no comment to them.
- The audit found three stale points in the PR body: the test count (317, not 323), the claim that nothing was published, and the #52 row.
- The owner merges PR #54. See [Owner merges PR #54](decision-owner-merges-pr-54.md).
