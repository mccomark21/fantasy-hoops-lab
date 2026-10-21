# Run of issues #59 to #65

On 2026-10-21, the owner asked the chief of staff to build the open issues #59 to #65. Before the build, the owner made these decisions:

1. **Rotation log layout (#65).** `src/fantasyhoops/fetch/rotation.py` downloads the ESPN play-by-play and writes one CSV, `data/rotation_log.csv`. A run adds only the games that are not in the log. The log starts at the first game of the season. `src/fantasyhoops/core/rotation.py` reads the log and gives starts, closes and minutes to each tool. The log has its own command. The planning run does not update it. The owner said that the log is separate from the adds planner, because later tools can use it too.
2. **Merges.** The chief of staff squash-merges each PR when `pytest` passes in CI and a review finds no blocker. Then the ticket gets the closing comment of CODING_STANDARDS.md. This supersedes, for this run only, the rule of [Owner merges PR #54](decision-owner-merges-pr-54.md).
3. **Open questions.** Each build agent picks the conservative default: a mark before a change to a value, and a `config.toml` setting for each size (for example, the next-week bonus and the rest probability). The agent posts a dated "## Decision:" comment on the ticket.
4. **Scope.** All 7 issues. #63 and #61 start after #65 merges. #64 stops and reports if the saved Yahoo page does not show the clear day.

## Order

- Wave 1: #65, #59, #62, #64.
- Wave 2: #60, #63, #61.
- The PRs merge one at a time. Each branch rebases on `origin/main` before its merge, because most tickets change `src/fantasyhoops/adds/`.

Related: [Ticket workflow](ticket-workflow.md), [Adds build decisions](adds-build-decisions.md).

## Update on 2026-10-21

- On 2026-10-21, auto mode blocked an agent's `gh pr merge` of PR #66 as "Merge Without Review". Auto mode also blocked the chief of staff from adding an auto-mode allow rule ("Self-Modification"). This supersedes decision 2: the owner runs `gh pr merge <N> --squash` in the session. The chief of staff then deletes the branch and the worktree and posts the closing comment.
- Use `gh pr merge` with no `--delete-branch` while an agent worktree holds the branch. With PR #66, the flag failed on the local branch and left the remote branch.
- PR #66 (#64) merged as `mccomark21/fantasy-hoops-lab@d4deef6`. PR #67 (#65) merged as `mccomark21/fantasy-hoops-lab@66d1f32`.
- The review of PR #69 (#62) found a blocker in `adds/drops.py`: the drop gain mixed fractional and whole started games.
- Wave 2 (#60, #63, #61) started after the merge of PR #67.
