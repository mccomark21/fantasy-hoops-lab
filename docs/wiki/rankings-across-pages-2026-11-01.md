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

## Decision: Season value (2026-11-01)

- The owner said: "Outside of playoffs, I think I want ranking to be actual custom rank value. As in the current season's stats to date." On 2026-11-01 the box scores held 89 games (10/20 to 11/1), a median of 5 games for each player and 7 at most.
- The chief of staff recommended: one Season value (the custom formula on season-to-date box scores, blended with the projection until `blend_games = 10`, the projection for 0 games, above the replacement free agent), used as Val on every page, the Playoffs page too, with a "Next 7" column kept on the Free agents page. The owner said: "you can skip the sample on this one and just build it".
- Issues: #222 (the seam and the Players, Free agents, Roster and Adds pages) and #223 (Trades and Playoffs, blocked by #222). Not in scope: the kept-set rule, fix 5 above, which the owner has not decided.
- On 2026-11-01, the owner picked "Half penalty" for missed games (Decision comment on #222). PR #224 merged as `mccomark21/fantasy-hoops-lab@75b07c7`. A `refresh --no-publish` ran ok (40 s), but it does not rewrite the Roster page or `players.json`, so the chief of staff computed the new ranks with `SeasonValues` and the pool replacement estimate (scratch `222-ranks.py`). Owner's roster, old draft Rk → new Season rank: Flagg 12 → 8, Miller 38 → 15, Murray 28 → 38, D. White 31 → 61, Quickley 78 → 62, Banchero 30 → 65 (2 games), Mitchell 128 → 90, Buzelis 39 → 95, Fears 100 → 98, Okongwu 60 → 101, Gobert 69 → 112, Coby White 77 → 129 (0 games), Nurkić 105 → 133 (0 games). Top free agent by Season value: Ryan Rollins (rank 88). The new Adds warning says Rollins (+2.18) is above Buzelis (+2.03), the lowest kept player.
- On 2026-11-01, PR #225 for #223 merged as `mccomark21/fantasy-hoops-lab@51f0976` (Trades on the Season value; Pre column removed, Decision 2 on #223). The chief of staff then ran `refresh` with publish (45 s, all ok). The run's replacement per-game value was −4.00. On the published pages, all 13 of the owner's players have the same Val on the Players and Trades pages (Flagg 6.61, Miller 5.65, Murray 3.89 … Coby White 0.58, Nurkić 0.51). Trade suggestion: give Coby White, get Brandon Ingram, 84 → 86 starts. Open owner decisions: the IL rule of the kept set (forces Coby White and Nurkić in), a value band in Val units (the band is narrow near replacement), and whether to restore the Pre column.
