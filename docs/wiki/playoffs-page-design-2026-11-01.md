# Playoffs page design of 2026-11-01

On 2026-11-01, the owner asked for a "playoffs" page: "I need the ability to play with my playoff roster." The owner wants to pick players from the team, free agents or other teams, and to keep a core of 8 (changeable) "who don't miss starts", so that adds and trades bring "quality game core players". The chief of staff ran a grilling session.

## Facts found (2026-11-01, `mccomark21/fantasy-hoops-lab@3856a3a`)

- The Roster page playoff grid uses `lineup_fit()` (`core/roster.py`) and `best_lineup()` (`core/lineup.py`): a greedy fill of PG, SG, SF, PF, C and Util by custom rank. `rests_b2b` players lose the second night of a back-to-back.
- `config.toml`: 10 spots (6 starters, 4 bench), playoff weeks 19 to 21 (2027-03-08 to 2027-03-28), `quality_games` (6 or fewer NBA games in a day).
- The Trades page builder runs in the browser (`trade/trade_builder.js`, `scoreCore()` of `draft/team_builder.js`) and keeps 8 players (`[trade] kept`). It works one partner at a time and has no free agents.
- No wiki page covered playoffs or the core strategy. `[simulation] core = 7` holds the draft model.

## Owner decisions (2026-11-01)

1. A new `/playoffs/` page. It shares one lineup-and-starts engine with the Trades builder, so the numbers match.
2. The page models only the core (8 by default, changeable). The other spots are stream spots. Each day shows core starts lost (a core game that sits) and open slots for streams.
3. The pool is every player of `players.json` (all rostered players of the league and the listed free agents), with an owner tag. A name opens the player modal.
4. The headline number is value started: the sum of the per-game Val (the Free agents Val) of each started core game in weeks 19 to 21. Starts lost and open slots (heavy and light days) show beside it.
5. When more core players have games than slots, the higher per-game Val starts, within the position rules. This holds for added free agents and other teams' players.
6. Value started gives light-night starts (6 or fewer NBA games) the `quality_games` bonus of `config.toml` (+10%), the same as the Roster page. Each player shows a light-night count.
7. Today's injuries are ignored. No per-week "out" switch. The owner said: "if a player is labeled as someone who rests back-to-backs then I want to account for that in playoffs."
8. A player on the rest list (`rests_b2b` = 1 in the `[risk]` file) always sits the second night of a back-to-back, as on the Roster grid, with an "R" tag. A switch on the page marks any player as a rester or not. The switch does not change the file.
9. Each player has an "Adds" value: the core's value started with the player minus without the player. The lowest is flagged as the weakest link. The owner changed the suggestion part: "instead of listing the 5 best players lets just list the best teams & positions", for example "PF/C - SAC" or "SG - ORL,ATL,MEM".
10. The team-and-position fits rank by the open starting slots a player there would fill in weeks 19 to 21 with the weakest link out, with the light-night bonus. Teams with the same score share a row. The page shows the top 5 rows.
11. The page opens on the owner's roster with the best core pre-picked: the N players with the highest value started. The other players show as "outside the core". A number box sets N (8 by default, from `config.toml`) and re-picks. The owner added: "give me a save button so I can switch the core over time by using the page."
12. Save keeps the core and the rester switches in the browser (localStorage). The page opens on the saved core, shows the save date, and has a "Reset to best 8" button. No share link and no repo save.
13. The page has the Roster grid for the core (one row per player, the same marks), plus an "open slots" row and an "NBA games" row with light nights shaded. Above it: the headline and the totals of each week. Beside it: the player table with "Adds" and the weakest-link flag. Below it: the team-and-position fits.
14. A player with no Val (on 2026-10-31: 29 free agents with no Yahoo line, and Brandon Ingram, Jimmy Butler III and Kristaps Porziņģis) gets the projection-based Val with a "proj" tag.

## First sample (2026-11-01)

- An agent wrote `.impeccable/review/playoffs-sample.html` (untracked) from the 10/31 `players.json`, with working browser code.
- Best core of 8: Flagg, Murray, Banchero, Miller, Mitchell, White, Okongwu, Quickley. Value started 394.6, 85 starts, 4 starts lost, 41 open slots (30 heavy, 11 light). A search of all 1287 cores of 8 found the same core.
- Weakest link: Quickley, Adds +22.2. Top fit: "C – NO, PHX, TOR: +11 starts (4 light)". C fits lead because the core has one C.
- `scoreCore()` and `fit()` of `draft/team_builder.js` ran unchanged with value = Val. `trade_builder.js` adds only its own wrapper.
- Problems found: `players.json` keeps no replacement value, so the sample guessed the projection Val (decision 14) from a median gap. The real build needs the replacement value of the run. Reset kept the R switches and the added players, which the decisions did not settle. On a phone, the grid scrolls sideways and does not use the Roster accordion.
- On 2026-11-01, the owner said: "sample looks good". The owner did not answer two open points, so the chief of staff took its recommendations: Reset clears everything back to the roster's best core (added players and rester switches too), and on a phone the grid uses the Roster page's tap-to-open rows.
- Next: split the work into issues, with the shared engine first (the lesson of 2026-11-01 in [Run of 2026-10-30](run-2026-10-30.md)).
15. On 2026-11-01, the owner asked: "Can we add a row that shows the total starts we get per day?" The grid gets a core-starts row (core starts out of 6 each day, with a total for each week), next to the open-slots and NBA-games rows. The sample agent added it.
- The sample agent added a "Starts" row above "Open slots": starts out of 6 each day and a total for each week (85 of 126 for the best core). The sample has no phone tap-to-open rows yet; the build adds them.
16. On 2026-11-01, the owner said: "I changed my mind and I'd like a list of the top 10 players who add the most value to my roster. If we dropped the lowest or swapped out an even stronger player". This supersedes the team-and-position fits of decisions 9 and 10 (the owner picked "replace them"). The page lists the 10 pool players (free agents and other teams' players) with the largest gain in value started. For each, it tries a swap with every core player and keeps the best. Each row shows the player, the owner, the core player to swap out, the value gain and the starts gain (light nights). A click on the row loads the swap. A click on the name opens the profile. The "Adds" column and the weakest-link flag of decision 9 stay.
- The sample agent built the "Best swaps" list (about 100 ms in the browser). Top 3 on the 10/31 data: Jokić for Quickley +91.4, Wembanyama for Quickley +81.7, Dončić for White +75.5. The top rows were mostly stars on other teams, so the list ranked raw talent more than schedule fit. The chief of staff asked the owner about a filter or a schedule-fit ranking.
