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
- On 2026-10-29, the reviewer found no blockers in PR #155 at `c01b3f7` (review comment on the PR). Nits: the phone row list assumes 3 playoff weeks, the name-key fallback can match the wrong player, the partner starts leave out IL players, and the "pre" mark sits next to the "Pre" label.
- On 2026-10-29, the owner approved a rule: when a Decision comment changes what an issue body asks for, the body is edited too, with a "superseded" note. The rule went into the user-level `ticket-pipeline` skill (Role 1, Record). The chief of staff applied it to #150 item 3.3 and #152 item 2 (the swap rule).
- On 2026-10-29, the owner decided that the partner's "est." playoff starts go into #152 (Decision comment on #152, body updated). The owner merged PR #155 as is: it merged as `mccomark21/fantasy-hoops-lab@d74043d` and closed #150. The reviewer's nits are not filed as issues (the no-new-issues rule); they stay in this page.
- Next: #151 (Trades tab and publish) and #152 (builder) in parallel, then #153.
- On 2026-10-29, PR #156 merged as `mccomark21/fantasy-hoops-lab@91ee221` and closed #151 (reviewer: no blockers). The owner allowed the first live publish after the merge. The chief of staff ran `python -m fantasyhoops.trade` from `main`: 4 suggestions, gh-pages commit `8f37ba9`. The gh-pages root kept the Roster home page, and `/trade/` returned 200 after the Pages build.
- The home page on gh-pages has no Trades link yet, because a planning run before #156 published it. The next planning run from `main` adds the link.
- On 2026-10-29, the owner asked for a planning run to add the Trades link. The run published gh-pages commit `171988b`. The live home page then showed the Trades link, and `/trade/` stayed. This supersedes the claim above that the home page has no Trades link.
- On 2026-10-29, PR #157 (closes #152) opened at `2435d70`. The owner gave three standing approvals: merge #157 when its review is clean, then start the #153 builder, then publish the trade page after #153 merges.
- On 2026-10-29, the #157 review found one blocker: the desktop table showed only the partner's total "est." starts, not Wk19 to Wk21. The chief of staff sent it back to the builder. The owner also approved: merge #153 when its review is clean.
- On 2026-10-29, the builder fixed the #157 blocker at `843e738` (desktop shows the partner's Wk19 to Wk21 and total, marked "Est."). The re-review was clean (736 passed, CI green). PR #157 merged as `mccomark21/fantasy-hoops-lab@197ee0f` and closed #152. The chief of staff started the #153 builder.
- On 2026-10-29, the owner asked the chief of staff to file the reviewer nits as issues after #153 merges. The nits are in the review comments of PRs #155, #156, #157 and the coming #153 PR.
- On 2026-10-29, the owner accepted the two open #153 choices (Decision comment on #153). The #158 review was clean (755 passed). PR #158 merged as `mccomark21/fantasy-hoops-lab@22d6413` and closed #153. All of #150 to #153 are closed.
- On 2026-10-29, the chief of staff published the trade page from `main` (gh-pages commit `3741b28`): 4 suggestions and 3 missing-data warnings. After the Pages build, `/trade/` returned 200 and `/` showed the Roster page with the Trades link. An agent started to file the reviewer nits as issues.
- On 2026-10-29, an agent filed the reviewer nits as #159 to #164 (enhancement, ready-for-agent). It dropped 2 nits: the partner starts without IL players (the owner chose the "est." label, shipped in #157) and the old tool list at `/` (the planning run of 2026-10-29 replaced it).

## Offer list (2026-10-29)

- On 2026-10-29, the owner asked to focus the suggestions on Gobert, Buzelis and Coby White ("the least playoff games and low quality games for playoffs").
- A sample (session scratchpad, not in the repo) found: Gobert and Buzelis are outside the top-8 kept set, so no trade of them changes the playoff starts, with any band or limit. Playoff games Wk19/20/21: Gobert 4/2/4, Buzelis 4/4/3, White 4/3/4, team average 3.7/3.4/3.8. White's best trade stayed P.J. Washington (83 to 88).
- The chief of staff proposed a `kept_always` list to put players into the kept set. The owner instead decided on a config list of the players the owner is willing to trade, changed through the season. The kept-set rule does not change. A builder files the issue and builds it; the page says why an offered player gets no suggestion.
- On 2026-10-29, the owner approved: merge the offer-list PR when its review is clean, then publish the trade page.
- On 2026-10-29, the builder filed #170 and opened PR #171. The review was clean (787 passed; nits: the offer list is read from two sources, `listed()` rebuilds its key set on each call, the counters use `give.name` not `name_key()`). PR #171 merged as `mccomark21/fantasy-hoops-lab@d973e12`. The trade publish gave 3 suggestions, all for Coby White, and a no-suggestion line each for Buzelis and Gobert.
