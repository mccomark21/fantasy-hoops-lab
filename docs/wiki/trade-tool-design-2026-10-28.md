# Trade tool design of 2026-10-28

On 2026-10-28, the owner asked for a trade tool as a new tab of the site menu. It suggests 1-for-1 trades that raise the playoff games and the playoff starts and keep the season value. It also has a trade builder (for example 2-for-1) that shows the effect of a trade. The chief of staff ran a grilling session. The owner answered 12 questions. Then the owner said: "have an agent answer the remaining questions".

## Facts found (2026-10-28, `mccomark21/fantasy-hoops-lab@49e06a1`)

- The planner read no roster of another team.
- `core/home.py` `lineup_fit()` counts the playoff starts. It applies the back-to-back rest rule and keeps IL players in the lineup pool.
- The draft board scores a core in the browser with the JavaScript lineup matcher of `team_builder.js` (kept in JavaScript by #133).

## Owner decisions (2026-10-28)

1. Trade targets come from Yahoo's list of rostered players (`/players?status=T`), with the fantasy team of each player.
2. The tool is its own command, `python -m fantasyhoops.trade`, and publishes `/trade/`. It is not part of the planning run.
3. The page computes a custom trade in the browser with the board's JavaScript lineup matcher, shared by the board and the trade page. A parity test compares the Python rules and the JavaScript rules. Python scores the suggested trades.
4. Season value is per-game value. The player you get has at least 95% of the value you give (config value).
5. The rank is the gain in total playoff starts over weeks 19 to 21, then the gain of the weakest playoff week, then the season value. A trade with no gain in playoff starts is not suggested.
6. The tool can offer any rostered player of the owner, except a config list `untouchable` (default: Flagg).
7. A value band of 95% to 110% (config values). Each suggestion shows the value change of the other team.
8. In the builder: when you get more players than you give, you pick a drop. When you give more, the open spot stays empty with a line about it.
9. One partner team per trade. The result shows the side of the partner too.
10. The playoff starts use the home page rules exactly.
11. The page shows the suggestions first, then the builder. A click on a suggestion loads it into the builder. A prototype round comes before the build.
12. At most 3 suggestions for each player you give, and 20 rows in all, with a filter row of your players.
13. The value is the blended value of the adds planner for all players on both sides, from both Yahoo views of the rostered list. The page shows the preseason `pg_value` beside it. (The chief of staff took this recommendation when the owner handed the rest to an agent.)

## Next

An agent decides the remaining questions and proposes the issue split. The owner confirms before any issue or build.

## Agent decisions and the last owner answers (2026-10-28)

- An agent decided 53 further points and proposed 6 issues. Its file was a scratchpad file outside the repo. The issues hold its content.
- On 2026-10-28, the owner decided: the tool reads the trade deadline ("Trade End Date") from the Yahoo league settings. It is not a hand-set config value.
- On 2026-10-28, the owner decided: the playoff starts of a trade count the top 8 players by blended value (the agent proposed 7). Flagg (untouchable) and IL players are always in. This is the trade tool's kept set. It does not change the adds planner's `stream_spots`.
- The agent found that a publish with no home page puts a plain tool list at `/` (`core/publish.py` `publish()`, `home=None`). The trade publish must keep the home page.

## Live sample of #148 (2026-10-28)

- On 2026-10-28, PR #154 merged as `mccomark21/fantasy-hoops-lab@8a953c8`. The live read gave 145 rostered players of 13 teams (7 pages per view), each row with a team link, and the trade deadline 2027-03-04. IL players are on the rostered list.
- A sample scored 1,595 one-for-one trades: 36 in the value band, 13 with a gain. The baseline was 28/27/26 playoff starts (81) in weeks 19 to 21.
- The sample showed a flaw: with "the top 8 after the trade", a trade of the IL player Coby White showed a gain of 5 starts from the 9th player moving up. On 2026-10-28, the owner decided that the player you get takes the spot of the player you give (Decision comment on #150). This supersedes the top-8-after-the-trade rule.
- The owner said the sample "looks alright but it looks nothing like the rest of the site". The plain look was on purpose. The prototype round (#149) uses the site style.
- The blended values rested on 4 to 5 games, so few trades were in the band this early.

## Prototype round (2026-10-28)

- On 2026-10-28, an agent made 3 looks of the fixed layout with the real suggestions of the second sample (the swap rule), and one compare page with toggles. The owner picked look 3: the new count, the change and a small bar in each playoff week cell. #149 closed.
- On 2026-10-28, the owner accepted the recommendation that the partner's playoff starts use the owner's rule (their top 8 with the swap) and show as "est.", because the rostered list does not show IL slots.

## State at the shutdown (2026-10-28, night)

- The owner went to bed. The chief of staff stopped the builder of #150 a few minutes after it started. It left no worktree, branch or PR.
- `main` was at `mccomark21/fantasy-hoops-lab@34aebe2`. No PR was open. Open issues: #150, #151, #152, #153.
- The approved look 3, the compare page, the sample script and the scored sample (`trade-sample-v2.json`) were copied from the session scratchpad to `output/trade/prototype/` in the main checkout. Git ignores that folder, and it holds real league names. A builder reads the files there.
- Next steps: build #150 (suggestions page) with `output/trade/prototype/trade-look-3.html` as the visual reference. Then #151 (Trades tab and publish that keeps the home page) and #152 (builder) can run in parallel. Then #153.
- Builders must run tests with `PYTHONPATH=src` in a worktree, and commit and push early (two builders stalled on 2026-10-28).

## Resume (2026-10-29)

- On 2026-10-29, the owner said to resume the trade tab. The chief of staff started a builder of #150 in a worktree at `mccomark21/fantasy-hoops-lab@ccab25c`. The brief told it that the swap rule of the Decision comment supersedes item 3.3 of the issue body.
- On 2026-10-29, the builder opened PR #155 (closes #150) at head `c01b3f7`. It reported 692 tests passed and green CI. The first CI run failed on a 320 px overflow with the Linux fonts, and `c01b3f7` fixed it. Live run: 7.4 s of Yahoo reads with no cache, 3.7 s wall time with a full cache. The run found 4 suggestions.
- The builder asked if the table shows the partner's starts as "est." The issue has no partner column. This question is for the owner.
