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
