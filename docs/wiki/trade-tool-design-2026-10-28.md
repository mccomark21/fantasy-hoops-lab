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
