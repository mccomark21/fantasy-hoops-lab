# Trade fit notes of 2026-11-13

This page records the work of 2026-11-13 to 2026-11-15 on the trade suggestions. The owner asked for suggestions outside the playoff core, with a note on how each one fits the core. The work is PR #247 on the branch `trade-fit-notes`, commit `mccomark21/fantasy-hoops-lab@d89d0bb`. The earlier design is in [Trade tool design of 2026-10-28](trade-tool-design-2026-10-28.md). The earlier build is in [Trade tool build](trade-tool-build.md).

## Offer list update (2026-11-13)

- On 2026-11-13, a refresh run warned that Rudy Gobert in the `[trade] offer` list was not on the roster.
- On 2026-11-13, the owner set `offer = ["Ajay Mitchell", "Coby White", "Matas Buzelis", "Derrick White"]`.
- On 2026-11-13, a trade run gave 3 suggestions. The best was Derrick White for Joel Embiid, 83 to 84 playoff starts.

## Owner request (2026-11-13)

On 2026-11-13, the owner said: "I don't want to require players to be in my core to suggest trades. Just give me suggestions and tell me how they'd potentially compliment or conflict with my playoff roster if I were to include them."

The chief of staff showed a scratch sample first. The owner then said "go with your own recommendations". The four recommendations of 2026-11-13 were:

1. A bench give frees the spot of the kept player with the lowest Val that is not untouchable or IL.
2. The page shows trades that lose starts. It marks them "Conflict" and ranks them last.
3. `[trade] band_floor = 0.30` gives a value band to a player with a Val near 0. Before, Matas Buzelis (Val -0.66) and Coby White (Val -0.15) had no band.
4. The rank does not change: the gain in starts, then the worst week, then the value.

A later change in the same work also marks a trade "Conflict" when the player you get sits in some of his own games.

## What PR #247 changed (2026-11-15, `mccomark21/fantasy-hoops-lab@d89d0bb`)

- Each row has a fit note under the player you get: "Fits" or "Conflict". The note names the spot he takes, his starts of his games, and the starts that each kept player loses to him.
- A trade is a "Conflict" if the total starts go down, if a kept player loses starts, or if the player you get sits in some of his games.
- The builder uses the same bench rule, so a loaded suggestion shows the same starts. Three trades of the #213 engine fixture changed for this reason.
- The band floor also applies to the builder and to the Playoffs page.
- The PR body reports 229 passed for the trade, playoffs and starts tests. The full suite had 1516 passed and 4 failed.

## Live run (2026-11-15)

- On 2026-11-15, a full refresh published the new Trades page with 12 suggestions.
- The best suggestion was Ajay Mitchell for P.J. Washington, 83 to 88 playoff starts (+5), value +0.23.
- On 2026-11-15, PR #247 was open and not merged.

## Open follow-ups (2026-11-15)

These are notes, not GitHub issues. On 2026-10-27, the owner asked for no new issues until the open work is done.

- 14 players are missing from the `[risk] file`, so they get `rests_b2b` 0. Examples: Alex Sarr, Brandon Ingram, Jimmy Butler III.
- 4 tests in `tests/adds/test_plan.py` fail on `main` too. PR #247 did not cause them.
- The adds run warned that Anthony Black (ORL), Val +3.50, is above the lowest kept player, Ajay Mitchell, Val +1.51.
