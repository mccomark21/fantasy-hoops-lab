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

## Follow-ups (not filed)

- A weekly consistency view, after about 6 weeks of data.
- Change-point detection on the trends, at about 20 or more games.
- Glossary terms for competitive minutes, dud, spike and signal.
