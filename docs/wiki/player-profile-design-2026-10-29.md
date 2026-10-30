# Player profile design of 2026-10-29

On 2026-10-29, the owner asked for a player profile page. The page must give insights that the Roster page and the Free agents page do not show. It is also a place for deeper statistical analysis. The chief of staff ran a grilling session. The owner answered 10 questions.

## Facts found (2026-10-29, `mccomark21/fantasy-hoops-lab@6f75b7a`)

- The repo had no per-game box scores.
- `fetch/rotation.py` `update()` reads the ESPN game summary of each game (`/summary?event=`). The summary holds the full box score. The code kept only the minutes.
- `data/rotation_scores.csv` holds the score at each scoring play (`game_id, sec, home_score, away_score`). Competitive minutes can use it directly, with no interpolation.
- The code did not save the game summaries. A box-score backfill must read each logged game summary again.
- No code computed usage rate.
- `core/publish.py` deletes a folder that is not in `TOOLS` at the next publish. A new `/players/` folder must go into `TOOLS`.
- The local `data/rotation_log.csv` held 3 games, last written 2026-10-21.
- No issue was open on 2026-10-29.

## Owner decisions (2026-10-29)

1. The page shows game-by-game trends of minutes and usage. No other page showed a trend.
2. Each trend shows a game dot, a rolling line and a band of the normal range (the season mean plus or minus the expected noise for that window). A flag shows when the rolling line leaves the band. Change-point detection is a later option, at about 20 or more games.
3. A new stat, competitive minutes, leaves out the minutes after a game is decided. A game is decided when the lead is too large to lose at about a 99% win chance. The lead needed grows with the square root of the time left (about 22 points at the start of the 3rd quarter, 16 with 12 minutes left, 11 with 6 minutes left). The minutes trend shows competitive minutes beside total minutes.
4. A category chart shows the percentile of each of the 6 weighted categories (PTS, REB, AST, 3PM, STL, BLK). Each category has two marks: the season-to-date percentile and the preseason projection percentile. Small-sample categories shrink toward the projection. The population is the valuation pool of 140 players (14 teams, 10 spots). A label shows the punt weight of each category.
5. One `/players/` page holds the data as embedded JSON. A search box picks the player. The URL hash keeps the pick. Player names on Roster, Free agents and Trade link to it. The page includes every rostered player of the league, and each free agent with a projected value or 5 or more games.
6. More sections, in this order under the trends: the value trend (rolling per-game value), consistency, and similar players. The minutes chart has a close-game minutes label. The page does not repeat the playoff schedule. It links to Roster.
7. The top of the page has the plain header and a signals strip. Each signal comes from a defined rule (a band exit, a projection gap, consistency) and links to its chart. With no signal, the strip says "No signals: playing to projection". The owner said: "yeah we can try out b".
8. Consistency shows the dud rate (games below replacement level), the spike rate (games at a top-30 level) and one tick per game.
9. Similar players are the 5 nearest players in weighted z-score space on the blended line. Each one shows Val, owner (or FA) and the category with the largest difference.
10. A static sample with real data for 3 contrasting players comes first. After the owner reviews it, the chief of staff splits the work into issues for the ticket pipeline.

## First sample (2026-10-29)

- An agent wrote `.impeccable/review/players-sample.html` (untracked) for Ace Bailey (minutes riser), Immanuel Quickley (30% of his minutes after the game was decided) and Karl-Anthony Towns (steady star).
- The rotation fetch added 65 games (68 in all, 2026-10-20 to 2026-10-28). It found 9 players with a minute gap to the box score. The largest was Naji Marshall: 14.8 in the log, 21 in the box score.
- 13 ESPN names had no projection match (for example "Luguentz Dort", "Ronald Holland II"). They need rows in `data/name_overrides.csv`.
- A fit to the 68 games gave σ = 0.313 points per √second. That σ gives leads of about 28 (start of the 3rd quarter), 20 (12 minutes left) and 14 (6 minutes left). The chief of staff's estimate in decision 3 (22, 16, 11) used σ = 0.251, which was too low. The chief of staff recommended the measured σ. The owner did not answer this point. The second sample uses the measured σ.
- Agent defaults, not yet owner-approved: rolling window 3 games, a band needs 3 games, a flag needs 5. Shrinkage strength in games: PTS, REB, AST 4. 3PM, BLK 10. STL 15. The blended line used projections plus ESPN games of the last 14 days, not Yahoo lines.

## Owner decision on layout (2026-10-29)

On 2026-10-29, the owner rejected the long scrolling page of the first sample. The owner said: "I was thinking it wouldn't be something you'd scroll down. Like a very valuble 4 quadrant report card". This supersedes the section order of decisions 6 and 7. The owner accepted this layout:

1. Header: name, team, positions, owner or FA, Val, and 2 or 3 signal chips (the signals strip shrinks into the header).
2. Role (top left): the minutes chart with competitive minutes as a second line. Usage and close-game minutes become labels. Usage has no chart.
3. Categories (top right): the 6 percentile bars, unchanged from decision 4.
4. Value (bottom left): the value line and band. The game dots show dud, normal or spike, which replaces the consistency strip.
5. Comps (bottom right): the 5 similar players of decision 9.
6. Methods notes go behind an info icon. Below about 800 px wide, the quadrants stack.

## Owner decisions on chart style (2026-10-29)

1. The owner said the sample charts had "a clunky look". The owner picked two causes: the marks were too heavy, and too many marks had the same weight. A polish pass with a Before / After toggle followed.
2. The owner asked for the same polish on the adds plan page. An agent made a read-only audit of the adds page first.
3. The owner approved chart rules in DESIGN.md, written from the approved polish.
4. The owner said: "lets make sure we're consistent across the site if we make changes". The owner picked shared code plus a test:
   - one shared chart style in `core/` (CSS classes from `tokens.py` in the page shell of `core/publish.py`, and small SVG helpers),
   - a test that fails on inline stroke widths, raw hex colors or a chart outside the shared classes,
   - one issue per page to adopt it (home, roster, free agents, adds, trade, players), each with a Before / After page for the owner.
5. On 2026-10-29, the owner approved the After charts of the polish pass. The owner said: "oh yeah this looks loads better". After has no gridlines, frames or legends. It uses direct labels, one hero mark per chart, muted secondary marks, dot-on-track category bars and small triangles for duds and spikes.
6. The adds page audit of 2026-10-29 ranked 7 heavy or busy spots (heat columns through empty add rows, the 2px games rule, the boxy add cell, the busy matchup table, heading rules, the band size, bold games numbers). Items 1, 3 and 6 change values in the DESIGN.md "Week grid" section and need owner approval on a Before / After page.
7. Order: owner approval of the polish, then the DESIGN.md rules with the shared module and the test, then each page.

## Follow-ups (not filed)

- Name-match rows for 13 ESPN players, and the 9 rotation-log minute gaps. These come before the page build.

- A weekly consistency view, after about 6 weeks of data.
- Change-point detection on the trends, at about 20 or more games.
- Glossary terms for competitive minutes, dud, spike and signal.
