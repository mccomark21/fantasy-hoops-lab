# Glossary

The terms that more than one tool uses. Each term has one meaning in the code, the docs and the conversation. The terms that only one tool uses are in the guide of that tool, for example [the weekly adds planner](adds/README.md#terms).

## Roster

| Term | Meaning |
|---|---|
| Core | The players that you keep all season, about 7. You list them in `config.toml`. The tools never drop a core player. |
| Stream spot | A roster spot that does not hold a core player. Stream spots = 10 − the core players on the active roster, usually 3. A player on IL does not take a roster spot, so his spot is a stream spot. |
| Starting slot | One of the 6 daily lineup slots: PG, SG, SF, PF, C and Util. |
| IL | Injured list: 3 spots that are not roster spots. |

## League

| Term | Meaning |
|---|---|
| Fantasy week | Usually Monday to Sunday. Yahoo gives the dates of each week. The first week of the season can be longer. |
| Add | One free-agent pickup. The league gives 5 adds each fantasy week. The count resets at the start of each week. |
| Add delay | The days between an add and the first day that the player can start. This league: 0 (same day). |
| Free agent | A player with Yahoo status FA. You can add him right away. A player on waivers (W) is not a free agent. |
| Status | The Yahoo injury status of a player, from the official NBA designations: blank (healthy), O (out), Q (questionable), D (doubtful), P (probable) and others. Only players who are Out or Out for Season can go on IL. |

## Value

| Term | Meaning |
|---|---|
| Per-game value | The value of a player per game on the 6 ranked categories, with the category weights in `config.toml` (`core/valuation.py`). The stat line can change: the draft tools use the season projections file. |
| Projected value | The per-game value of Yahoo's projection for the next 7 days (from Rotowire). |
| Recent value | The per-game value of a player's averages in the last 14 days, from Yahoo. |
| Blended value | The per-game value of a blend of the projected line and the recent line. The weight of the recent line = games in the last 14 days ÷ 14. |

## Rotation

The rotation log (`data/rotation_log.csv`) gives these terms. `core/rotation.py` reads it.

| Term | Meaning |
|---|---|
| Stint | The time from a check-in of a player to his next check-out, in one period. A stint of 0 seconds is not in the log. |
| Start | The player is in the starting lineup of the game, from the ESPN box score. |
| Close game | At some moment in the last 5:00 of the fourth quarter or of an overtime period, the margin is 5 points or fewer. A game with an overtime period is always a close game. The settings are `close_minutes` and `close_margin` in `[rotation]`. |
| Close | The player is on the floor at the end of a close game. The closes of a player are counted against the close games of his team. |

## Schedule

| Term | Meaning |
|---|---|
| Back-to-back | Two games of one NBA team on two days in a row. |
| Second night | The second game of a back-to-back. |
| Rest list | The players with `rests_b2b` = 1 in the `[risk] file` of `config.toml`. They can rest on a second night. In the draft tools, the list changes only the playoff game counts, never the season games or the value. In the adds planner, a game of a player on the list on a second night counts `1 - [adds] rest_chance` started games. |
