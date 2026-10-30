# Players page and player modal

The Players page at `/players/` is a report card for one player of the league. A player name on the Roster, Free agents and Trades pages opens the same card in a modal over the page. Issue #186 built the page, the header, the empty quadrants and the modal. Issues #187 to #189 fill the quadrants.

## The card

The card has a header and 4 quadrants. It is not a scrolling page: at 1440 x 900, the header and the 4 quadrants fit with no page scroll. Below 800 px wide, the quadrants stack.

- **Header:** the NBA team band, the name, the positions, the owner (or FA), Val and up to 3 signal chips.
  - Val is the projected value per game above replacement (`pg_var` of `core/valuation.py`), from the newest projections file. A player with no projection has no Val ("–").
  - A signal comes from a rule of a quadrant, for example a band exit, a projection gap or consistency. Each chip links to its quadrant. With no signal, the header says "No signals: playing to projection". No rule exists yet. #187 to #189 add their rules to `SIGNAL_RULES` in `players/data.py`.
- **Quadrants:** Role (top left), Categories (top right), Value (bottom left) and Comps (bottom right). A quadrant with no chart shows a dashed box that says what is missing.
- **Methods:** the "i" icon in the header opens the methods and data notes.

## The players

The page and the modal have these players (`players/data.py`):

1. Each rostered player of the league, from the Yahoo rostered list of all teams.
2. Each free agent with a projected value: a row with games in the newest projections file.
3. Each free agent with 5 or more games in `data/rotation_log.csv`.

The names match after `name_key()`. `data/name_overrides.csv` gives the Yahoo name of a projection or ESPN name that does not match.

## The shared player file

The players are in one file, `/players/players.json`. The Players page and the modal read it. The modal reads it on the first open. No page holds its own copy of the players.

The planning run (`python -m fantasyhoops.adds.plan`) and the trade run (`python -m fantasyhoops.trade`) write the page and the file in `output/players/` and publish them at `/players/`:

- The planning run reads the rostered list in the projected view, in its Yahoo reads step. The read uses the same-day cache of the trade run. With `--no-publish`, the run skips the read and the page. If the read fails, the run prints a warning and the publish keeps the `/players/` folder of the site.
- The trade run uses the rostered list that it reads for the trades. After the trade deadline, the trade run reads no rostered list, and its publish keeps the `/players/` folder.

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
- The card uses the shared chart style of `core/chart.py` (DESIGN.md "Charts").
