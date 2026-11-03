# Playoffs page

## Goal

The Playoffs page at `/playoffs/` models the playoff core of your team: the players who start in weeks 19 to 21. You pick the core from your team, the free agents and the players of other teams. The other roster spots are stream spots. The design is in [docs/wiki/playoffs-page-design-2026-11-01.md](../wiki/playoffs-page-design-2026-11-01.md) (decisions 1 to 18, #214 and #215).

## Publish

The planning run (`python -m fantasyhoops.adds.plan`) writes `output/playoffs/index.html` after the Players page, and publishes it to `/playoffs/` in the same publish. The page takes its pool from the player file of that run (`players.json`). When the run makes no Players page, it makes no Playoffs page, and the site keeps the old page. The trade run keeps `/playoffs/` on the site.

## History file

Each planning run adds one row to `output/adds/playoff_history.json`, next to the week files of the planning run (#230). The row holds the date of the player file, the ids of the best N players of your roster, and the weekly Total and its rank of 14 for each playoff week. The best N follows your adds, drops and trades. It is not the core that you saved in the browser, because a run cannot read the browser. A second run on the same date replaces the row of that date. `historyRow()` of `core/starts.js` gives the numbers. The run runs it in Node. With no Node on PATH, the run prints a warning and adds no row. The trade run and the refresh command do not write or remove the file.

## The page

- **Open:** the page opens on your saved core. With no save, it opens on the best core: your N players with the highest value started. N is `[playoffs] core` of `config.toml` (8).
- **Core size:** the number box sets N and picks the best core again.
- **Search:** finds any player of the pool, with his owner (Mine, a team name or FA). A click adds the player to the core.
- **R switch:** marks a player as a rester or not. A rester sits on the second night of each back-to-back. The switch does not change the rest list (the `[risk]` file).
- **Save:** keeps the core, N, the added players and the R switches in this browser (localStorage). The page shows the save date.
- **Reset to best N:** clears the added players, the R switches and the save, and sets the best core.
- **Headline:** value started, the core size, the starts lost, the open slots (heavy and light days) and the starts. A table gives the totals of each week.
- **Floor:** for the core on the page, the Total, value started, stream value, Volume and Value per start of each playoff week, with the rank of each among the 14 teams. The header gives the weakest week (the worst Total rank), the spread and the mean week. "Why" lists the reasons of the weakest week: the core players with few starts, the starts lost on crowded nights (`lost_by`) and the open slots that the streams cannot fill. The numbers change when the core changes.
- **Trend:** a line of the floor and the Total, one point for each earlier planning run, then the core on the page now. The floor of a point is its lowest weekly Total. The NBA schedule does not change, so the line shows the result of your moves. Until the line has 2 points, the block says "No trend yet".
- **Core grid:** a row for each core player with the marks of the Roster grid, then the Starts, Open slots and NBA games rows. On a phone, each player is a row that opens with a tap.
- **Players table:** the core, then the players outside the core, with Val, the light-night count, Adds and the R switch. A name opens the player modal. The core player with the lowest Adds has the "Weakest" flag (the weakest link).
- **Best swaps:** the top 10 swaps of a free agent or a player of another team into the core, by schedule gain. The owner filter shows Free agents, Other teams or All. Each row shows the player, the owner, the core player to swap out, the schedule gain, the value gain and the starts gain (light nights). A click on the row loads the swap into the core. A click on the name opens the player modal. "Rank by" sets the ranking: Schedule gain (the default) or Worst-week gain.

## The numbers

`valueStarted()` of `core/starts.js` gives each number. The page script (`playoffs/playoffs.js`) has no lineup math.

- **Val:** the Season value above the replacement free agent (`core/season_value.py`, #222), from `val` of the player file. It is the Val of the Players, Free agents and Trades pages (#223). A player with no Val gets `proj_val` with the "proj" tag. Since #222, `proj_val` is the same Season value for a player in no Yahoo list of the run. A player with neither shows "–" and counts as 0.
- **Lineup:** each day, the core players start in Val order, highest first, in the position slots and Util.
- **Value started:** the sum of the Val of each started game in weeks 19 to 21. A game on a light night (6 or fewer NBA games) counts `[quality_games] bonus` more (10%).
- **Starts lost:** the core games that sit because the lineup is full. A rest night is not a start lost.
- **Open slots:** the empty starting slots that a stream player can fill. A day with no NBA games has none.
- **Starts / games:** the starts of the core against its games (the core games less the rest nights, so starts + starts lost). "N lost to slot clashes" is games − starts.
- **Ideal:** the ideal of the Roster page, `ideal_games()` of `core/lineup.py` (`idealGames()` of `core/starts.js`): min(core size × the most games of any NBA team that week, 6 × the game days). "N below ideal" is ideal − games. The headline, the week table, the Starts row of the grid and the phone totals show both (owner decision of 2026-11-01).

- **Adds:** the value started of the core with the player minus the value started of the core without him (`adds()` of `core/starts.js`). For a player outside the core, the page shows his Adds "if added". A core player with a Val below 0 still starts when his team plays. So his Adds is below 0, and he is the weakest link.
- **Value gain:** the change of value started when the pool player takes the place of the core player.
- **Schedule gain:** the value gain minus (Val in − Val out) × the starts of the player out. It is the part of the gain that comes from the schedule and the lineup, not from the Val alone. The list ranks by it (`bestSwaps()` of `core/starts.js`).
- **Weekly Total:** value started + the stream games of the week × v, as on the League page (`weekTotals()` of `core/starts.js`, #229). The stream spots are `[league] roster_spots` minus the core size. v is the mean Val of the best `[league_page] v_free_agents` free agents. The other teams have the best N players by value started, as on the League page, so the two pages give the same weekly Totals and ranks.
- **Weakest week:** the week with the worst rank of the Total among the 14 teams (`coreFloor()` of `core/starts.js`). With equal ranks, the week with the lower Total, then the first week. **Spread:** the best weekly Total − the worst weekly Total.
- **Floor (trend):** the lowest weekly Total of a run (owner decision 2 of 2026-11-02 on #230, `trendPoints()` of `core/starts.js`).
- **Worst-week gain:** the change of the Total of your lowest week now when the pool player takes the place of the core player (`floorSwaps()` of `core/starts.js`). The lowest week is the week with the lowest weekly Total, the week of the trend floor (owner decision of 2026-11-02 on #230). It can differ from the weakest week by rank of the header. Each player gets the swap-out with the largest gain. The list keeps only gains above 0 and has the same pool, value band and untouchable rule as the schedule gain. "Total" is the change of the 3-week Total. "Lowest after" is the lowest week with the swap, with its Total and rank.
- **Best swaps rules:** the list keeps only swaps with a value gain above 0. Your players are not in the pool. A player of another team is in the list only if his Val is in `[trade] value_band` of the player out (0.95 to 1.10 of the Val out). Free agents have no band. A `[trade] untouchable` player is never a swap-out, for any owner. The page reads both settings from `config.toml`, so the Trades page and the Playoffs page agree.
