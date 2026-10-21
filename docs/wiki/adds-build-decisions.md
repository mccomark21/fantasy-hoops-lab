# Adds build decisions

On 2026-10-20, the owner made these decisions while the agents built tickets #42 to #53. The guide holds each rule. This page records only the decision, its date and where the rule lives.

| Decision | Date | Ticket | Rule |
|---|---|---|---|
| The aggressive plan scores the value of its started games, so it can give up started games for better players. | 2026-10-20 | #50 | [Aggressive plan](../adds/README.md#aggressive-plan) |
| NA (Not Active) and suspended players do not play in the main plan, the same as Out players. | 2026-10-20 | #51 | [Status rules](../adds/README.md#status-rules) |
| On the last day of a fantasy week, the planner plans the next week with all adds left. | 2026-10-20 | #46 | [Usage](../adds/README.md#usage) |
| The planner suggests plans for 3 stream spots by default. A drop is a suggestion, not an order. | 2026-10-20 | #49 | [Core and drops](../adds/README.md#core-and-drops), [Configuration](../adds/README.md#configuration) |

## Where the decisions were recorded

On 2026-10-21, the audit of #42 found these decisions only in `docs/adds/README.md` and in the PR #54 body. No issue held a decision comment. See [Ticket workflow](ticket-workflow.md).

## Aggressive score wording

On 2026-10-21, the audit found a conflict in `docs/adds/README.md` as of `mccomark21/fantasy-hoops-lab@a73ee76`. Line 71 says "the sum of the blended value". Lines 25, 73, 224 and 227 and the PR #54 body say "the sum of the value above an empty slot". The audit called line 71 stale. The [Aggressive plan](../adds/README.md#aggressive-plan) section gives the reason for the value above an empty slot.

## Earlier decisions

On 2026-10-20, two ADRs recorded the decisions on data and publishing:

- [ADR 1: Read league data with Playwright and a manual sign-in](../adr/0001-playwright-for-league-data.md)
- [ADR 2: Publish the adds plan on public GitHub Pages](../adr/0002-publish-adds-plan-publicly.md)

Related: [Adds planner build](adds-planner-build.md), [Page redesign kept](decision-page-redesign-kept.md).
