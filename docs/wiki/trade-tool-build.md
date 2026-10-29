# Trade tool build

This page records the build of the trade tool, issues #148 and #150 to #153. The design and the owner decisions are in [Trade tool design of 2026-10-28](trade-tool-design-2026-10-28.md). The guide of the tool is [docs/trade/README.md](../trade/README.md).

## Merged builds

| Issue | What it added | PR | Merge |
|---|---|---|---|
| #148 | The Yahoo reads: the rostered list in both views and the trade deadline | #154 | `mccomark21/fantasy-hoops-lab@8a953c8` (2026-10-28) |
| #150 | The suggestions page, `python -m fantasyhoops.trade --no-publish` | #155 | `mccomark21/fantasy-hoops-lab@d74043d` (2026-10-29) |
| #151 | The Trades tab and the publish of `/trade/` that keeps the home page | #156 | `mccomark21/fantasy-hoops-lab@91ee221` (2026-10-29) |
| #152 | The trade builder for custom trades, and the partner "est." starts | #157 | `mccomark21/fantasy-hoops-lab@197ee0f` (2026-10-29) |

## Edge states (#153, 2026-10-29)

- On 2026-10-29, the builder of #153 started from `mccomark21/fantasy-hoops-lab@0dd9f12` on the branch `153-trade-deadline-warnings`.
- The run now reads the league settings before the team page and the rostered list. After the trade deadline, it reads no other Yahoo page and writes a short deadline page. The timing sub-steps changed from "team page" and "rostered list and settings" to "settings", "team page" and "rostered list".
- A missing trade deadline gives one warning in the terminal and on the page. The run continues.
- A player with no match in the rankings, the `[risk] file` or the projections file gets one warning line for each file, on the page and in the terminal.
- A `YahooBlocked` error, a `PageNotReady` error or a sign-in timeout stops the run with `YahooReadFailed`. The run does not write or publish a page.
- The choices that the issue did not settle are in the Decision comments of 2026-10-29 on #153.

## Live run of #153 (2026-10-29)

- On 2026-10-29, the builder ran `python -m fantasyhoops.trade --no-publish` in its worktree, with the `data/` and `.auth/` folders of the main checkout linked in. The run did not publish.
- The run found 5 suggestions. The deadline was in the future, so the deadline page did not show. A test covers it.
- The warning lines named 2 players with no rank and no projections match (Alex Sarr, Nic Claxton) and 11 players not in the `[risk] file`.
- The builder checked 5 of the 11 names: `name_key()` removes the suffix and the diacritics ("Kristaps Porziņģis" gives "kristaps porzingis"). The 210 rows of `data/projection_risk.csv` do not have these players. So the `[risk] file` line is long while that file is short. This is a follow-up note, not an issue (the no-new-issues rule of 2026-10-27).
