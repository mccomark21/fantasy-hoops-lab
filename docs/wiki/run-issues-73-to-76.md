# Run of issues #73 to #76

On 2026-10-21, the owner asked the chief of staff to build issues #73 to #76. The process of [Run of issues #59 to #65](run-issues-59-to-65.md) applies: one worktree agent and one PR for each ticket, a review by a separate agent, and the owner runs `gh pr merge <N> --squash`.

## Owner decisions on 2026-10-21

1. **The page, not the terminal.** The owner said: "The printed reports are not helpful to me. I need features incorporated into the adds_plan.html." A feature of the adds planner counts as done only when `adds_plan.html` shows it. #60 (PR #72, `mccomark21/fantasy-hoops-lab@346b0a5`) showed next-week games only in the terminal, so the owner saw nothing.
2. **#76 (open day early next week).** The planner checks next Monday and Tuesday, finds the open starting slots from the core players' games, and marks each free agent who plays on such a day.
3. **#75 (starter and closer flags).** The flags are Regular, Inconsistent and New. The owner chose "Show a sample first": an agent posts a sample table of real players on #75, and the owner approves the rule before the page work.
4. **#73 and #74.** The diagnosis of 2026-10-21 found them after the first owner run. See the "Result" section of [Run of issues #59 to #65](run-issues-59-to-65.md).

## Order

- #73, #74 and #76 build in parallel. #75 waits for the owner to approve the sample.

Related: [Environment gaps](environment-gaps.md).

## Result on 2026-10-21

- All issues of this run closed on 2026-10-21: #73 (PR #80, `mccomark21/fantasy-hoops-lab@5c14544`), #75 (PR #81, `@1557a76`), #74 (PR #82, `@08dbbf2`), #83 (PR #84, `@b6a2cea`) and #76 (PR #77, `@79fc505`). #78 (PR #79, `@0922496`) added the "Adds planner" rule 1 to CODING_STANDARDS.md.
- The chief of staff filed #83 during the run. Two PRs failed CI once on a timing test of the draft tools (187 ms against a limit of 100 ms), and a rerun passed. PR #84 made the timing tests relative to a reference workload in the same Node process.
- The reviews found 2 blockers in PR #82: the Transaction Trends page got no wait, and a matchup page with no score table stopped the run. The builder fixed both before the merge.
- On 2026-10-21, the owner's run at `@08dbbf2` took 32 s, against 553 s before #74. The matchup weights came from the live scores (REB 0.99, BLK 0.95, others 1.00).
- On 2026-10-21, the rotation log held 3 games, so the page showed no starter or closer flags yet. The flags need about 5 logged games for each player.
- Review agents left local branches `pr66` to `pr82` from `gh pr checkout`. The chief of staff deleted them on 2026-10-21. A later review prompt can ask the reviewer to use `gh pr diff` or a detached checkout.
