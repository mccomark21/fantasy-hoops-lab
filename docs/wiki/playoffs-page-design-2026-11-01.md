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
