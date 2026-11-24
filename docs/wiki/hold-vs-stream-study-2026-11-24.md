# Hold vs stream study of 2026-11-24

This page records a read-only study of 2026-11-24. The study asks when a player in the rank band 65 to 100 is worth his roster spot, and when a stream spot is worth more. The code is at `mccomark21/fantasy-hoops-lab@1d49fd9`. The study changed no file under `src/` or `data/`. The scripts are in the session scratchpad (`study.py`, `study2.py`). They are not in the repo.

## Owner question (2026-11-24)

On 2026-11-24, the owner said: "I want to identify when a player should be rostered vs streaming a roster spot. For example, keeping a player with a rest of season ranking roughly around 100 who plays 3-4 times in a week vs streaming the roster spot and getting 5-6 games that week. I have a lot of players above rank 65 up to ~100 and I can't decide if I should be streaming spots or holding them. If we could identify a range/threshold where there are diminishing returns it would help me manage more aggressively in order to win."

## Short answer (2026-11-24)

1. Per game, a player of rank 65 to 100 is only 7% to 21% better than the mean of the 10 best free agents. So one extra started game of a streamer beats most of the edge of a held player.
2. The limit is not the rank. The limit is the 5 adds of each week and the 6 starting slots of each day. These two caps make the returns of each extra stream spot smaller.
3. With 5 adds, stream spots 1 to 3 gain. Spot 4 is about even. Spot 5 loses. See [Diminishing returns](#diminishing-returns-2026-11-24).
4. The rule: hold your best 7 active players, whatever their rank in 1 to 100. Stream the other 3 spots. Use a 4th stream spot only in a week where the plan gives it 4 or more started games and the held player gets 2 or fewer starts. Never use a 5th stream spot for a player of rank 100 or better.

## Method (2026-11-24)

### Per-game value

- Rank is the rank by Val of `SeasonValues.ranks()` in `core/season_value.py` (`mccomark21/fantasy-hoops-lab@1d49fd9`). The replacement value is the free agent at rank 15 among the free agents of the planning run of 2026-11-24, as in `adds/value.py` `season_replacement()`. The study ranks match the Roster page of that run (Quickley 63, Coby White 76, Mitchell 79, Derrick White 84, Buzelis 89).
- Per-game value is `pg_value()` of `core/valuation.py` on the BBM projection of 2026-11-24, with the scale of the projections file. The 6 categories are PTS, REB, AST, 3PM, BLK and STL with the `[weights]` of `config.toml`.
- `pg_value()` has its 0 at the pool mean. A weekly total adds the raw stats of each game. So the study uses the raw value: `pg_value` minus `pg_value` of a line with no stats (-11.58). The raw value is linear in the counting stats. A game with no stats has a raw value of 0. Without this change, a streamer below the mean would lose value with more games.

### Free-agent pool

- The free agents are the projection lines that are not on a roster in the rostered list of 2026-11-24 (`output/adds/cache/rostered/2026-11-24/`, read with `trade/rostered.py` `read_rostered_page()`) and not on the owner roster. That gives 353 free agents. 169 of them have a games share of 0.6 or more.
- The streamer value `s` is the mean raw value of the 10 best of these free agents (9.38). This is the `[league_page] v_free_agents` rule (10). The study also checks the 3rd best free agent (9.93) and the 15th best (8.21, the replacement level).

### Weekly started games

- The roster is the owner roster of the Roster page of 2026-11-24 (`output/roster/index.html`). Paolo Banchero and Dejounte Murray are on IL, so they take no spot and do not start.
- For n stream spots, the core is the best 10 - n active players by rank. `adds/slots.py` `open_slots_by_day()` gives the starters and the open slots of each day. The held players start in rank order, so a low held player sits when the slots are full.
- `adds/team_plan.py` `team_plan()` gives the started games of the n stream spots. Two bounds:
  - lo: empty spots and 5 adds. This gives no credit to the players that stay from the last week.
  - hi: empty spots and 5 + n adds. This treats each staying player as one free add. It is an upper bound.
- The weeks are week 6 (11/23 to 11/29), week 8 (12/14 to 12/20), week 9 (12/21 to 12/27) and week 10 (12/28 to 1/3). Week 7 (11/30 to 12/13) is out, because `data/schedule.csv` has no games on 12/4 to 12/11 (the NBA Cup knockout days, `[skyline] unscheduled`).

## Per-game value by rank (2026-11-24)

Each rank row is the median of the 7 players around that rank.

| Rank or free agent | pg_value | Raw value per game | Games of a top-10 streamer (s = 9.38) | Games of a replacement streamer (s = 8.21) |
| --- | --- | --- | --- | --- |
| Rank 50 | 0.20 | 11.79 | 1.26 | 1.44 |
| Rank 65 | -0.22 | 11.36 | 1.21 | 1.38 |
| Rank 80 | -0.74 | 10.84 | 1.16 | 1.32 |
| Rank 100 | -1.57 | 10.01 | 1.07 | 1.22 |
| Rank 120 | -2.26 | 9.33 | 0.99 | 1.14 |
| Free agent 1 (Mikel Brown Jr., rank 96) | -1.18 | 10.40 | 1.11 | 1.27 |
| Free agent 5 (Jonathan Kuminga, rank 114) | -2.04 | 9.55 | 1.02 | 1.16 |
| Free agent 10 (Reed Sheppard, rank 144) | -3.05 | 8.53 | 0.91 | 1.04 |
| Free agent 15 (Ja'Kobe Walter, rank 157) | -3.37 | 8.21 | 0.88 | 1.00 |

On 2026-11-24, the 10 best free agents have ranks 96 to 144. The 20 best have ranks 96 to 169. The pool of the Free agents page (122 players of the teams that the run read) is weaker: its 5th best has rank 141.

## Break-even games (2026-11-24)

S is the streamer games that equal G started games of a held player of rank R. S = G x raw value of R / s, with s = 9.38.

| Rank | G = 2 | G = 3 | G = 4 |
| --- | --- | --- | --- |
| 50 | 2.5 | 3.8 | 5.0 |
| 65 | 2.4 | 3.6 | 4.8 |
| 80 | 2.3 | 3.5 | 4.6 |
| 100 | 2.1 | 3.2 | 4.3 |
| 120 | 2.0 | 3.0 | 4.0 |

G is his started games, not his games. A held player who sits on a full day adds nothing that day. In the drop tests below, a held player of rank 63 to 89 got about 2 starts per week as the 8th to 9th player, and about 2.5 starts as the 7th player, from about 3 to 4 games.

## Diminishing returns (2026-11-24)

The mean of weeks 6, 8, 9 and 10. Each step drops the lowest active player and opens one more stream spot.

| Stream spots | Player dropped at this step | Stream started games per week (lo to hi) | Per spot (lo to hi) | Net gain of the step, in top-10 streamer games per week (lo to hi) |
| --- | --- | --- | --- | --- |
| 1 | Isaiah Joe (203) | 5.25 | 5.25 | +3.6 |
| 2 | Matas Buzelis (89) | 9.25 to 9.75 | 4.6 to 4.9 | +1.8 to +2.3 |
| 3 | Derrick White (84) | 12.0 to 12.75 | 4.0 to 4.25 | +0.8 to +1.0 |
| 4 | Ajay Mitchell (79) | 14.5 to 16.75 | 3.6 to 4.2 | -0.3 to +1.2 |
| 5 | Coby White (76) | 17.5 to 21.0 | 3.5 to 4.2 | -1.5 to -0.2 |

1. The 5 adds bind from 3 stream spots on. In each test week, the lo plan used all 5 adds at 3, 4 and 5 spots.
2. Each new spot adds fewer games: about 4 for spot 2, about 3 for spot 3, 2.5 to 4 for spot 4.
3. The cost of a step tends to grow: a held player higher in the order starts more of his games, because fewer players compete for the slots. The core lost 15.6, 20.8, 18.4, 26.4 and 41.7 raw value per week at the 5 steps.
4. With the replacement streamer (s = 8.21), the step to 3 spots is +0.5 to +0.8, the step to 4 spots is -0.7 to +0.8, and the step to 5 spots is -2.1 to -0.8.
5. The gain flattens at 3 stream spots and turns negative at 5. Spot 4 is within the noise.

Weeks differ. In week 10, a 4th spot got 4 to 7 more started games. In week 9, it got 2 to 3.

## Drop tests per player (2026-11-24)

Each test drops one player and gives his spot to a new stream spot. The table gives the mean of the 4 test weeks, with s = 9.38.

| Player | Rank | Base: 1 stream spot (hold 9) | Base: 3 stream spots (hold 7) |
| --- | --- | --- | --- |
| Immanuel Quickley | 63 | loses 1.9 starts, gains 3.75 to 4.0 games, net +1.5 to +1.7 streamer games | loses 2.6 starts, gains 2.25 to 3.75 games, net -0.9 to +0.6 |
| Coby White | 76 | loses 2.1 starts, gains 4.25 to 4.5 games, net +1.8 to +2.0 | loses 2.8 starts, gains 2.75 to 4.5 games, net -0.6 to +1.2 |
| Ajay Mitchell | 79 | loses 2.0 starts, gains 4.0 to 4.25 games, net +1.7 to +2.0 | loses 2.5 starts, gains 2.5 to 4.0 games, net -0.3 to +1.2 |
| Derrick White | 84 | loses 1.75 starts, gains 3.75 to 4.0 games, net +1.8 to +2.0 | not tested (he is a stream-spot holder at this base) |
| Matas Buzelis | 89 | loses 2.0 starts, gains 4.0 to 4.5 games, net +1.8 to +2.3 | not tested (he is a stream-spot holder at this base) |

The 5 players are close. The order of the drops matters more than the rank inside 63 to 89.

## Owner roster, rank 54 to 134 (2026-11-24)

Games come from `data/schedule.csv`. Week 6 is 11/23 to 11/29 (2 or 3 games are left on 11/24). Week 7 counts only the known days (11/30 to 12/3 and 12/12 to 12/13). The playoff weeks are weeks 19, 20 and 21.

| Player | Rank | Raw value per game | Week 6 games (left) | Week 7 known games | Playoff games wk19/wk20/wk21 | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Paolo Banchero (IL) | 54 | 12.26 | 3 (3) | 2 | 3/4/4 | Hold. He takes a top-7 spot when he comes back. |
| Immanuel Quickley | 63 | 11.43 | 3 (2) | 3 | 3/4/4 | Hold. |
| Coby White | 76 | 11.12 | 3 (2) | 3 | 4/3/4 | Hold. He is the 7th active player after Banchero comes back. |
| Ajay Mitchell | 79 | 10.57 | 3 (2) | 3 | 4/3/4 | Marginal. Hold while Banchero is on IL. He becomes the 8th player when Banchero comes back. |
| Derrick White | 84 | 10.53 | 3 (3) | 3 | 4/3/4 | Stream candidate. |
| Matas Buzelis | 89 | 10.40 | 3 (2) | 3 | 3/3/4 | Stream candidate. |
| Dejounte Murray (IL) | 134 | 10.98 | 3 (2) | 3 | 4/4/3 | Hold on IL. He takes no spot. His per-game value is the value of a rank-75 player. His rank is low because BBM projects few games (share 0.36). |

A "Stream candidate" is a player in the 8th to 10th active spot. The planner already treats Derrick White and Buzelis as stream-spot holders (`[adds] stream_spots = 3`, `adds/drops.py`). Mitchell, Coby White, Buzelis and Derrick White are also in `[trade] offer`. A 2-for-1 trade of two of them for one better player would open a stream spot and keep their value. The study did not test trades.

## Threshold rule (2026-11-24)

1. Hold your best 7 active players by rank. On 2026-11-24, ranks 1 to about 80 fill these 7 spots.
2. Stream the 8th to 10th spots. On 2026-11-24, this means ranks about 84 to 100 and lower. A held player in these spots gets about 2 starts per week. A stream spot gets about 3 to 4 started games.
3. Turn on a 4th stream spot only in a week where the plan gives it at least 1.2 x the starts of the held player that it replaces (rank 65 to 80) or 1.1 x (rank 80 to 100). In practice: 4 or more stream starts against 2 or fewer starts of the held player.
4. Never turn on a 5th stream spot while it replaces a player of rank 100 or better.
5. A player below rank about 110 is worth no more per game than the free agents 1 to 5. Stream his spot.

## Uncertainty and gaps (2026-11-24)

- The per-game gaps of 7% to 21% are small. BBM projection error is likely of this size, so the rank order inside 63 to 100 is weak evidence.
- The free-agent pool comes from one day (2026-11-24). It changes with injuries and drops. A streamer must also play on the right days, so the real streamer is likely between free agent 3 and free agent 15, not always the top-10 mean.
- The team plan gives a new player every position. A real free agent fits fewer slots, so the stream games are likely a little lower than the table.
- The lo bound gives no credit to the players that stay from the last week. The hi bound gives too much. The true value is between them.
- The raw value adds the 6 categories in a straight line. H2H categories are not linear: a category that is already won or lost gains little. The matchup weights (`adds/matchup.py`) are not in the study.
- The model ignores the rest on back-to-backs of the held players, the add delay, waivers and the first come of other managers to a free agent.
- `data/schedule.csv` has no games on 12/4 to 12/11, so week 7 is out of the study.
- A dropped player of rank 65 to 100 is better than each free agent on 2026-11-24 (the best free agent has rank 96). Another team can add him. The study does not price this loss or his playoff weeks.
- The study tested 4 weeks of one roster. Other rosters, or weeks with more light nights, can give other numbers.
