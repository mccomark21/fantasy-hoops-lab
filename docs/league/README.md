# League page

## Goal

The League page at `/league/` compares the 14 teams of the league in playoff weeks 19 to 21. Each team gets one row: its record, its playoff core, the value that the core starts, and the open slots that its stream spots can fill. The owner asked for the page on 2026-11-01 (#218): "I'm hoping my competitive advantage can be the open heavy/light." The owner decisions of 2026-11-02 are on #218.

## Publish

The planning run (`python -m fantasyhoops.adds.plan`) writes `output/league/index.html` after the Playoffs page, and publishes it to `/league/` in the same publish. The page takes its players from the player file of that run (`players.json`), as the Playoffs page does. When the run makes no Players page, it makes no League page, and the site keeps the old page. The trade run keeps `/league/` on the site.

The planning run reads the records from the standings table of the Yahoo league home page (`readers.read_standings()`). This read is one more page load. It is in the "standings" sub-step of the Yahoo reads step. When the read fails, the run prints a warning, and the page shows "—" for each record. A Yahoo block still stops the run (#107). The page matches a standings name to the owner name of the player file. The match ignores the case and the outer spaces.

## The page

- **Header:** two lines for your team. "Core starts: rank X of 14 (league median Y)" uses the Starts column. "Filled heavy: rank X of 14 (league median Y)" uses the filled open slots on heavy nights. Rank 1 is the most. Equal values share the higher rank. `rankMedian()` of `core/starts.js` gives each rank and median (owner decision of 2026-11-02).
- **Summary:** your rank by Total, your core size and its source, the open slots that your streams fill, and v with the free agents of v.
- **Table:** one row for each team. Your row has the "You" tag. A click on a column header sorts by that column. A second click reverses the sort. Record sorts by the win share, (W + T ÷ 2) ÷ games. A click on a team opens its core: each core player with his Val and his starts, then the players outside the core.
- **Column descriptions (#227):** each header except Team and Record shows a short description on mouse hover and on keyboard focus, with the numbers of the run (the slots, the light-night bonus and v). `notes()` of `league.js` gives the text. Phones have no hover, so a closed "Column meanings" list below the table has the same text. The footer has only the data line.

| Column | Meaning |
| --- | --- |
| # | The rank by Total. |
| Team, Record | The team name and its record (W-L-T) from the Yahoo standings. |
| Core | The number of core players. |
| Val / core | Value started ÷ core players. |
| Stream value | Stream games × v. |
| Total | Value started + stream value. |
| Starts | The started core games / the core games (starts + starts lost). |
| Open heavy | The filled open slots on heavy nights / the open slots on heavy nights. |
| Open light | The filled open slots on light nights / the open slots on light nights. |
| Stream games | Filled heavy + filled light × (1 + `[quality_games] bonus`). |
| Fill rate | Stream games ÷ (open heavy + open light × (1 + bonus)), as a percent. |
| Unused | (Open heavy − filled heavy) + (open light − filled light): the open slots that the streams do not fill. |

## The numbers

`core/starts.js` gives each lineup number. The page script (`league/league.js`) has no lineup math. It multiplies the stream games by v and adds the totals.

- **Core:** the core of each other team is its best `[playoffs] core` players (8) by value started alone (`bestCore()`). Your row uses the core that you saved on the Playoffs page, with its R switches. The page reads it from localStorage key `fhl-playoffs` in this browser. With no saved core, your row uses your best 8.
- **Value started, starts and open slots:** `valueStarted()`, as on the Playoffs page. An open slot is an empty starting slot on a day with NBA games. A light night has 6 or fewer NBA games.
- **Stream spots:** `[league] roster_spots` (10) minus the core players.
- **Fill:** `streamFill()` counts the open slots that the stream spots can fill with `[league] adds` (5) adds each week:
  1. At the start of each week, each stream spot holds a player of the team that gives the most starts. This player is kept from the week before, so he uses no add.
  2. Each day, the players in the stream spots start first, in spot order.
  3. For each open slot that is left, an add puts a player of a team that plays that day in a spot whose player does not start that day. The add with the most starts that day and on the days that are left wins.
  4. Heavy nights come first. On a light night, the page uses an add only if the adds left are more than the heavy nights with open slots that are left in the week.
- **Positions:** a stream player starts only if the slots and Util can hold him with the core players of the day. This is the position-slot logic of `count()` in `adds/team_plan.py` (`best_lineup()` of `core/lineup.py`). On his first start, a stream player takes the positions that fit that day (`slots_of()` and `_positions()` of `adds/team_plan.py`). With an open Util slot, each position fits. So a player who fills an open C slot on Monday cannot fill an open PG slot on Wednesday.
- **v:** the value of one streamed game: the mean Val of the best `[league_page] v_free_agents` (10) free agents of the run. On the 11/1 data, v = 1.40.

## Limits

- The fill is a greedy rule, day by day. It is not the search of the Adds planner (`team_plan()`), so the Adds planner can find a plan with more starts.
- The fill does not know which free agents each NBA team has. It assumes that a team that plays has a free agent at each open position.
- The saved core is in one browser only. On another device, your row uses your best 8.
