# Playoffs page

## Goal

The Playoffs page at `/playoffs/` models the playoff core of your team: the players who start in weeks 19 to 21. You pick the core from your team, the free agents and the players of other teams. The other roster spots are stream spots. The design is in [docs/wiki/playoffs-page-design-2026-11-01.md](../wiki/playoffs-page-design-2026-11-01.md) (decisions 1 to 18, #214 and #215).

## Publish

The planning run (`python -m fantasyhoops.adds.plan`) writes `output/playoffs/index.html` after the Players page, and publishes it to `/playoffs/` in the same publish. The page takes its pool from the player file of that run (`players.json`). When the run makes no Players page, it makes no Playoffs page, and the site keeps the old page. The trade run keeps `/playoffs/` on the site.

## The page

- **Open:** the page opens on your saved core. With no save, it opens on the best core: your N players with the highest value started. N is `[playoffs] core` of `config.toml` (8).
- **Core size:** the number box sets N and picks the best core again.
- **Search:** finds any player of the pool, with his owner (Mine, a team name or FA). A click adds the player to the core.
- **R switch:** marks a player as a rester or not. A rester sits on the second night of each back-to-back. The switch does not change the rest list (the `[risk]` file).
- **Save:** keeps the core, N, the added players and the R switches in this browser (localStorage). The page shows the save date.
- **Reset to best N:** clears the added players, the R switches and the save, and sets the best core.
- **Headline:** value started, the core size, the starts lost, the open slots (heavy and light days) and the starts. A table gives the totals of each week.
- **Core grid:** a row for each core player with the marks of the Roster grid, then the Starts, Open slots and NBA games rows. On a phone, each player is a row that opens with a tap.
- **Players table:** the core, then the players outside the core, with Val, the light-night count, Adds and the R switch. A name opens the player modal. The core player with the lowest Adds has the "Weakest" flag (the weakest link).
- **Best swaps:** the top 10 swaps of a free agent or a player of another team into the core, by schedule gain. The owner filter shows Free agents, Other teams or All. Each row shows the player, the owner, the core player to swap out, the schedule gain, the value gain and the starts gain (light nights). A click on the row loads the swap into the core. A click on the name opens the player modal.

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
- **Best swaps rules:** the list keeps only swaps with a value gain above 0. Your players are not in the pool. A player of another team is in the list only if his Val is in `[trade] value_band` of the player out (0.95 to 1.10 of the Val out). Free agents have no band. A `[trade] untouchable` player is never a swap-out, for any owner. The page reads both settings from `config.toml`, so the Trades page and the Playoffs page agree.
