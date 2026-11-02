# Rankings across pages (2026-11-01)

On 2026-11-01, the owner said: "seems like we have conflicting rankings across pages. Can you analayze and summarize?" A read-only agent compared the pages on the data of the 19:31 refresh, as of `mccomark21/fantasy-hoops-lab@7219e8b`. Its scripts are `rank-*.py` / `rank-*.js` in the session scratchpad.

## Four numbers rank players

| Page | Ranks by | Window | Core rule |
| --- | --- | --- | --- |
| Roster (Rk, lineup order) | Custom draft rank, `pg_var × (games/82)^1.25` | Preseason projections, full season | None |
| Adds plan (stream spots) | Pre (`pg_value`, per game) | Preseason projections | 3 lowest by Pre, not IL, not `[adds] core` |
| Free agents, Players | Val: blended value (Yahoo 7-day projection + last 14 days) minus the 15th-best free agent | Next 7 + last 14 days | None |
| Playoffs | Value started (Val × starts, +10% light nights) | Val + playoff schedule | Best `[playoffs] core` by value started |
| Trades | Blended value with no replacement subtracted (labeled "Val"); lineup by draft rank | Next 7 + last 14 days | Untouchable + all IL players + best by value, 8 in all |

## Findings

- 82 vs 85 starts: on the 19:31 data the Playoffs best core gives 84 (85 was the 10/31 data). The two cores differ by one player: Trades keeps Coby White (forced by the IL rule, Val −0.41, rests on back-to-backs); Playoffs keeps Quickley.
- Ajay Mitchell: lowest on the team by draft rank (128) and Pre (131), 7th by Val (3.14). Adds makes him a stream spot; Trades and Playoffs keep him.
- Buzelis and Gobert: kept by Adds (Pre), dropped by Playoffs and Trades (Val).
- Trades "Val" lacks the replacement offset (Flagg 3.55 vs 7.40 elsewhere), so the `[trade] value_band` around a player differs between Trades and Playoffs, against decision 18 of [Playoffs page design](playoffs-page-design-2026-11-01.md).
- Bug: `read_ranks` (adds/roster.py), `rank_players` (adds/drops.py) and `read_risk` (trade/run.py) key on the projection name and ignore `data/name_overrides.csv`. This gives the "no rank" warning for Alex Sarr and Nic Claxton, and may explain the 9 players with no `[risk]` match.
- Bug: the IL rule keeps an IL player whose value is below replacement.

## Proposed fixes, smallest first

1. Trades: subtract the run's replacement from the blended value, so Val is one number on all pages.
2. Use `link_players` / name overrides in the three lookups.
3. Order the Trades lineup by Val, as Playoffs does.
4. Adds stream spots by Val (Pre only with no Val).
5. One shared core rule for Trades and Playoffs: value started plus untouchable; an IL player only when he adds value.
6. Label each page's basis.

Also on 2026-11-01: the owner asked why PTS is bold on the Roster page. `td.n:nth-child(6) { font-weight: 800; }` in `core/roster.py` came with #173 (`ec0e2a1`), copied from the older Adds roster table. On the Roster page column 6 is PTS, so the bold has no meaning there.
