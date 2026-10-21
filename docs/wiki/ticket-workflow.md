# Ticket workflow

## The usual way to close a ticket

Before #42, the project closed most tickets with the owner's `/ship-it` skill: one PR for each issue, a squash merge, then a comment on the issue. The comment has this shape:

1. The line "Shipped via /ship-it."
2. 2 to 5 bullets on the change.
3. The PR URL and the merge sha.
4. A "Deferred" line for work left undone.

Examples: #15, #23, #29, #33 and #39. Issue #39 also held dated "Decision" comments during the work.

## Parent issue precedent: #8

Parent #8 (team builder) had sub-issues #35, #36 and #37. Local merges such as "Merge feat/team-builder-a (#35)" brought in the work, and the sub-issues closed with no comment. Parent #8 got one summary comment that named merge `84c5813` and the sub-issues.

## Problem in the #42 build

On 2026-10-20, the #42 build merged each ticket locally on `feat/adds-planner` as a "Merge ticket N: ... (#N)" commit. The "(#N)" is the issue number, not a PR. The build opened no PR for each ticket. On 2026-10-21, no issue from #42 to #53 had a comment.

Effects found on 2026-10-21:

- The decisions of the build are in the guide and the PR #54 body only. No issue records them. See [Adds build decisions](adds-build-decisions.md).
- The scope change of #52 is not on the issue. See [Page redesign kept](decision-page-redesign-kept.md).
- The merge of PR #54 closes 12 issues with no closing comment.
- Ticket #51 has no "Merge ticket 7" commit.

## To avoid it

The audit of 2026-10-21 suggested these steps for #42:

1. Post one summary comment on parent #42, as on #8.
2. Post a short "Shipped" comment on each sub-issue.
3. Add a "Deferred" note on #47, #48 and #52, and the owner checks on #45 and #46.

For a later epic, post the decision comments on the issue when the decision happens, as on #39.

Related: [Adds planner build](adds-planner-build.md), [Environment gaps](environment-gaps.md).

## Update on 2026-10-21

- On 2026-10-21, CODING_STANDARDS.md came into the repo (PR #56). It states the ticket rules: one PR per ticket, dated Decision comments, and a closing comment.
- On 2026-10-21, the owner squash-merged PR #54. The commit SHAs in a ticket's closing comment are then not in main's history. A squash PR for each ticket avoids this, because its closing comment cites the squash commit.
- On 2026-10-21, the owner decided that a commit that changes only `docs/wiki/` can go straight to main. CODING_STANDARDS.md got this as Docs rule 5. This commit adds the rule.
