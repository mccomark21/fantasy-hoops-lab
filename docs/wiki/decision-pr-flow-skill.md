# The pr-flow skill

On 2026-10-21, the owner asked for a skill that agents use to manage worktrees, branches and merges. The skill is user-level, at `~/.claude/skills/pr-flow/` (SKILL.md and REFERENCE.md), so other projects can use it. It is not in this repo.

The skill came from the problems of [Run of issues #59 to #65](run-issues-59-to-65.md) and [Run of issues #73 to #76](run-issues-73-to-76.md):

- `gh pr merge --delete-branch` failed while a worktree held the branch (PR #66). The merger merges with no `--delete-branch`, then removes the worktree and deletes both branches.
- Review agents left local branches `pr66` to `pr82` from `gh pr checkout`. A reviewer uses `gh pr diff` and a detached worktree.
- Auto mode blocked agent merges as "Merge Without Review". When a merge is blocked, the merger gives the owner the exact command and does not work around the block.
- Hidden conflicts between PRs that changed the same file (for example #68 and #69 in `adds/plan.py`). One merger merges one PR at a time, and each PR rebases right before its merge.

A change from the runs of 2026-10-21: in the skill, a reviewer posts its review on the PR, and the merger checks for that "No blockers" review. In the runs, reviewers replied only to the chief of staff.

The skill reads the CI check name, the ticket rules and the closing-comment shape from `CODING_STANDARDS.md` of each repo.

For agents to merge, the owner must add an auto-mode allow rule to `~/.claude/settings.json`. As of 2026-10-21, the owner had not added it.

Related: [Ticket workflow](ticket-workflow.md), [Environment gaps](environment-gaps.md).
