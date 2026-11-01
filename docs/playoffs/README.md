# Playoffs page

## Goal

The Playoffs page at `/playoffs/` models the playoff core of your team: the players who start in weeks 19 to 21. You pick the core from your team, the free agents and the players of other teams. The other roster spots are stream spots. The design is in [docs/wiki/playoffs-page-design-2026-11-01.md](../wiki/playoffs-page-design-2026-11-01.md) (decisions 1 to 15, #214).

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
- **Players table:** the core, then the players outside the core, with Val, the light-night count and the R switch. A name opens the player modal.

## The numbers

`valueStarted()` of `core/starts.js` gives each number. The page script (`playoffs/playoffs.js`) has no lineup math.

- **Val:** the Val of the Free agents page. A player with no Val gets his projection-based Val (`proj_val`) with the "proj" tag. A player with neither shows "–" and counts as 0.
- **Lineup:** each day, the core players start in Val order, highest first, in the position slots and Util.
- **Value started:** the sum of the Val of each started game in weeks 19 to 21. A game on a light night (6 or fewer NBA games) counts `[quality_games] bonus` more (10%).
- **Starts lost:** the core games that sit because the lineup is full. A rest night is not a start lost.
- **Open slots:** the empty starting slots that a stream player can fill. A day with no NBA games has none.
- **Starts / games:** the starts of the core against its games (the core games less the rest nights, so starts + starts lost). "N lost to slot clashes" is games − starts.
- **Ideal:** the ideal of the Roster page, `ideal_games()` of `core/lineup.py` (`idealGames()` of `core/starts.js`): min(core size × the most games of any NBA team that week, 6 × the game days). "N below ideal" is ideal − games. The headline, the week table, the Starts row of the grid and the phone totals show both (owner decision of 2026-11-01).

## Later

The "Adds" column, the weakest-link flag and the "Best swaps" list are #215.
