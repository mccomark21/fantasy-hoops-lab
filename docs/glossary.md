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
