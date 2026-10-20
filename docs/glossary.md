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
| Status | The Yahoo injury status of a player: blank (healthy), GTD, O, INJ and others. |

## Value

| Term | Meaning |
|---|---|
| Per-game value | The value of a player per game on the 6 ranked categories, from the season projections (`core/valuation.py`). |
| Recent value | The per-game value of a player's stats in the last 14 days, from Yahoo. |
