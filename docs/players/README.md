# Players page and player modal

The Players page at `/players/` is a report card for one player of the league. A player name on the Roster, Free agents and Trades pages opens the same card in a modal over the page. Issue #186 built the page, the header, the empty quadrants and the modal. Issues #187 to #189 fill the quadrants.

## The card

The card has a header and 4 quadrants. It is not a scrolling page: at 1440 x 900, the header and the 4 quadrants fit with no page scroll. Below 800 px wide, the quadrants stack.

- **Header:** the NBA team band, the name, the positions, the owner (or FA), Val and up to 3 signal chips.
  - Val is the Val of the Free agents page (owner decision of 2026-10-30): the blended value per game above a replacement free agent (0 = the free agent at rank 15 by value). The value and the replacement come from the same planning run as the Free agents page. A free agent gets his Val from the free-agent lists of the run. A rostered player gets it from the rostered list, with the same blend. A player with no Yahoo line in the run has no Val ("–").
  - A signal comes from a rule of a quadrant, for example a band exit, a projection gap or consistency. Each chip links to its quadrant. With no signal, the header says "No signals: playing to projection". The rules are in `SIGNAL_RULES` in `players/data.py`. The Categories quadrant gives the projection-gap rule (#188).
- **Quadrants:** Role (top left), Categories (top right), Value (bottom left) and Comps (bottom right). A quadrant with no chart shows a dashed box that says what is missing.
- **Methods:** the "i" icon in the header opens the methods and data notes.

## The Categories quadrant

The Categories quadrant (#188) shows the percentile of each weighted category (PTS, REB, AST, 3PM, BLK, STL) as a dot-on-track bar (`players/categories.py`, `core/card_cats.py`).

- **proj** (the hollow dot): the per-game projection of the player, ranked among the projections of the pool.
- **now** (the filled dot): his season line, shrunk toward his projection, ranked among the shrunk lines of the pool.
- **Pool:** the valuation pool of `core/valuation.py`, the top 140 players by projected value (14 teams x 10 spots). A pool player with no game has his projection as his shrunk line.
- **Shrinkage:** now = (n x season + k x projection) / (n + k). n is the number of games that he played in `data/box_scores.csv`. k is in `[players.categories] shrink` of `config.toml`: PTS, REB, AST 4. 3PM, BLK 10. STL 15. These values are agent defaults that the owner did not approve yet.
- **Percentile:** 100 x (pool players below + half of the pool players equal) / 140.
- **Row:** the category, its punt weight from `[weights]` (for example ×0.70), the season per game and "proj" with the projection per game. A mouse, a tap or the focus on a row shows its tooltip card.
- **Projection gap:** a header signal when a category has 5 or more games and a gap of 25 or more percentile points between now and proj (`gap_games` and `gap_points`). The largest gap gives the chip, for example "REB above projection: percentile 63 vs 25".
- A player with no projection shows the box "No projection: no category ranks."

## The players

The page and the modal have these players (`players/data.py`):

1. Each rostered player of the league, from the Yahoo rostered list of all teams.
2. Each free agent with a Val above 0: above the replacement free agent of the Free agents page.
3. Each free agent with 5 or more games in `data/rotation_log.csv`.

The owner chose this rule on 2026-10-30.

The names match after `name_key()`. `data/name_overrides.csv` gives the Yahoo name of a projection or ESPN name that does not match.

## The shared player file

The players are in one file, `/players/players.json`. The Players page and the modal read it. The modal reads it on the first open. No page holds its own copy of the players.

The planning run (`python -m fantasyhoops.adds.plan`) writes the page and the file in `output/players/` and publishes them at `/players/`:

- The planning run reads the rostered list in its Yahoo reads step, after the free-agent lists, in the same views as those lists. A run that reads no free-agent list has no Val, so it reads the projected view only. The read uses the same-day cache of the trade run. With `--no-publish`, the run skips the read and the page.
- If the read fails (a changed page, a Yahoo timeout, a network error), the run prints a warning, the plan publishes and the publish keeps the `/players/` folder of the site. A Yahoo block stops the run, as for each other Yahoo read (#107).
- The trade run (`python -m fantasyhoops.trade`) does not write the page: it reads no free-agent list, so it has no Val of the Free agents page. Its publish keeps the `/players/` folder.

## The Players page

- A search box finds a player by name. The URL hash keeps the pick, for example `/players/#ace-bailey`. The hash opens that player on load and on Back or Forward.
- With no hash, the page shows the first player of the file: the highest Val.

## The player modal

A player name on the Roster, Free agents and Trades pages is a link. The Adds plan page has no name links.

- A click on a name opens the modal and changes the URL hash, for example `/free-agents/#player=ace-bailey`.
- The browser Back button closes the modal. A copied link with the hash opens the modal on load.
- Esc, the Close button and a click on the backdrop close the modal.
- The focus stays in the modal while it is open. On close, the focus goes back to the player name.
- "Open full profile" goes to `/players/#<player>`.
- Below 800 px wide, the modal is a full-screen sheet with stacked quadrants.

## Code

- `core/profile.py`: the one shared card and modal (CSS and JS), `slug()` and `name_link()`. `publish.shell()` puts the modal in place of `__PLAYER_MODAL__` in a page template. The card styles have the scope `.lab-card`, so the rules of a page do not change the card.
- `players/data.py`: the player rule, Val, the games and the signal rules.
- `players/page.py`: the Players page and the player file.
- `players/categories.py`: the percentiles of the Categories quadrant and its signal rule. `core/card_cats.py`: the chart of the quadrant (`LabCard.fill.cats`).
- The card uses the shared chart style of `core/chart.py` (DESIGN.md "Charts").
