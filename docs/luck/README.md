# Luck page

## Goal

The Luck page at `/luck/` shows which players are lucky or unlucky in each category (#254). Luck is the makes of a player this season against the makes that his chances expect. The owner approved the sample of real data on 2026-11-20. The math is in `players/luck.py`. [docs/players/README.md](../players/README.md), "Luck", gives a short summary of it.

## Publish

The planning run (`python -m fantasyhoops.adds.plan`) writes `output/luck/index.html` after the League page and publishes it to `/luck/` in the same publish. The page reads `data/nba_stats.csv` and `data/nba_stats_2025-26.csv` ([docs/fetch/README.md](../fetch/README.md)). It takes the owner of each player from the player file of the run (`players.json`).

The run makes no Luck page in these cases. The site then keeps the old page.

- The run makes no Players page.
- `data/nba_stats.csv` does not exist. The run prints a line.
- The module cannot read the stats file. The run prints a warning.

## The page

- **Header:** the date of the newest dated copy of the NBA.com stats, and the count of players.
- **Rules line:** the math in one paragraph, with the ready rule of `[players.luck]`.
- **Filter:** All players, My team, Other teams, Free agents. Each chip shows its count. A player who is not on a fantasy roster is a free agent.
- **Table:** one row for each player with a ready category. The default sort is Luck, the most unlucky first. A click on the Luck header or on a z header sorts by that column. A second click reverses the sort. Players with no z in that column go last.
- **Columns:** the NBA team, the player (his fantasy team, or "Free agent", and his games), Luck, then 4 columns for each of STL, BLK, AST, REB and 3PM.

| Column | Meaning |
| --- | --- |
| Luck | The sum of the ready z / the square root of their count. |
| Ch/g | Chances a game. |
| Act/g | Makes a game. |
| Exp/g | Expected makes a game: chances × the baseline rate. |
| z | (makes − expected makes) / the spread of chance. A dash: not ready. |

- Each z shows its sign in the text (+ or −). A z of 2 or more from 0 is bold. The page uses no color for good or bad.
- A player name links to his card on the Players page when the player file has him.

## Code

- `luck/page.py`: `page_rows()`, `render()` and `write_site()`. The filter and the sort are a short inline script.
- `players/luck.py`: the luck math.
- `tests/luck/test_page.py`: the rows, the owners, the page HTML and, in Chromium, the filter and the sort.
