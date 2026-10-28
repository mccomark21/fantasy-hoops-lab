# Home page sample of 2026-10-27

On the evening of 2026-10-27, the owner ran the Impeccable skill on the home page and the site menu. The owner stopped the session before a review of the result. This page records what the session left on disk. It follows [decision-site-redesign-2026-10-27](decision-site-redesign-2026-10-27.md). The repo was at `mccomark21/fantasy-hoops-lab@570c687`.

## Surface brief (2026-10-27, 20:57)

The brief is `.impeccable/surfaces/src-fantasyhoops-core-publish-py.md`. Its target is `src/fantasyhoops/core/publish.py` (`home_page()` and `nav_bar()`).

The job of the home page, as the brief states it: the owner opens the site and sees the current roster in custom-rank order, with these parts:

- the 2026-27 season stats to date (ESPN, per game)
- the playoff games and starts for wk19, wk20, wk21 and the total
- a day grid for the 21 playoff days that shows who fits in the lineup each day, with the higher-ranked players placed first (the `scoreCore` engine of `draft/team_builder.js`)

Other points of the brief:

- The menu is a side panel, not a top bar.
- The page must not be slower to use than the current site.
- Sample first: the owner approves a static sample before an issue is filed and the generator is built.
- The roster comes from the Yahoo team page that the adds run reads. The stats come from one ESPN `statistics/byathlete` request.

## Candidate directions (2026-10-27, about 20:56)

The session wrote 5 candidate mocks in `.impeccable/mocks/decision/`. The names come from the file names. The notes come from a short look at the colors and fonts of each file.

| File | Direction | Look |
| --- | --- | --- |
| `canon.html` | Canon | Gray rules, blue links, zebra rows. Close to a plain default table. |
| `card-back.html` | Card Back | Back of a basketball card: royal blue `#1d4f91`, card red `#c8102e`, Archivo and Archivo Narrow on white. |
| `center-hung.html` | Center-Hung | Dark ground with amber and red, and the dot-matrix font Doto. |
| `challenger-crouwel.html` | Challenger Crouwel | White ground with blue `#2f6bff` and orange `#ff4f00`. |
| `challenger-splitflap.html` | Challenger Split-flap | Near-black and amber, Barlow Condensed. |

## The pick

The skill assigned Center-Hung. The direction contract in the brief chose Card Back over it: "Card Back, my top-ranked grounded candidate (1 of 7), chosen as the pick card over the assigned Center-Hung. seed:44f4e78605ff12e4". The text says "1 of 7", but only 5 mocks are on disk. The session left no record of the other 2 candidates.

The contract thesis: each player's season looks like the back of his basketball card, with a team-color band, the stat line, and the playoff schedule as the fine print. Red numbers show where starts are lost. The first viewport is a 216px royal-blue side menu with Roster, Adds plan, Draft board and Keeper report, and the full roster table in the main area.

## Static samples (2026-10-27, about 21:10)

The session made two static samples in `.impeccable/review/`, with the Archivo font in `.impeccable/review/fonts/`:

- `sample-index.html`: the home page in the Card Back direction.
- `sample-adds.html`: an adds page sample.

It took screenshots at 21:10: `desktop.png`, `desktop-dark.png`, `mobile.png`, `mobile-dark.png`, `mobile-menu.png`, `mobile-scrolled.png` and `adds-desktop.png`.

The contract says that the build ends with a finish review, a verdict, and an update of `DESIGN.md`. The session left no record of a finish review.

## Unresolved items in the brief

- Where the home-page data is built: at the end of each adds run, or in a separate step.
- The dark theme of the world. The decision sketch was light only. The contract names a deep navy card back with white ink for the dark theme, and the session took dark screenshots. The brief still lists the dark theme as unresolved.

## State on 2026-10-28

- The owner had not approved the sample.
- No issue was filed for the home page or the generator. By the brief, an issue waits for the owner approval of the sample.
- `.impeccable/mocks/`, `.impeccable/review/` and `.impeccable/surfaces/` were not committed.
- The scope of the sample touches the scope of #117 (one shared token source and a new visual identity for the home page, the nav and the adds page). The session left no record that links the two.

## Owner feedback of 2026-10-28

The owner looked at the sample and gave these points. The direction stays Card Back. The revision does not choose a new direction.

1. The owner likes the Card Back style. The rows must be easier to scan, with gentle zebra stripes like `canon.html`.
2. In the 21-day playoff grid, a quality day must be a shaded column for the full height of the table, not only a mark in the header.
3. On a phone, each player is a row that opens and closes. The closed row shows Team, Rank, Player, POS, GP and the total playoff games. A tap shows the rest: the stats, the weekly starts and games, and the day grid.
4. The playoff starts include the IL players. They count in the lineup fit, the weekly starts and the team totals, because they will likely be back by the playoffs. The rule stays the same: the best lineup each day, higher rank first. The IL players keep a visible IL marker. The key and the footnote change to match.
5. The page keeps both themes. Light is the white stock, and dark is the navy card back. Both follow the system setting. Both themes must meet WCAG 2.2 AA contrast, also on the zebra rows and the shaded columns.
6. Gentle vertical rules separate the column sections (Team, Rank and Player | season stats | playoff starts and games | day grid). Rules also separate the playoff weeks: Wk19 | Wk20 | Wk21 in the weekly columns, and the three 7-day weeks in the day grid. The rules are thin and low in contrast in both themes. On a phone, the rules are inside the opened row.
7. The site menu gets a light and dark theme switch. The default follows the system setting. A choice overrides the system setting and stays in the browser. The switch is in the shared site menu, so that each tool page can use it later. Point 7 replaces the earlier instruction of the same day not to add a switch.

8. The team-starts footer shows the totals the way the draft board shows them: the starts that the team gets, the total possible starts, and the percent of the starts that the team uses. The footer shows them for each week and the total, in both themes and on a phone.

This answers the dark-theme question in the brief: the page has both themes.

### What changed in the sample

The revised sample is `.impeccable/review/sample-index.html`. The old sample is `.impeccable/review/sample-index-v1.html`, and its screenshots are in `.impeccable/review/v1-screens/`. A script in the session scratchpad wrote the new sample from the data of the old sample, `data/schedule.csv` and `data/projection_risk.csv`. Neither `.impeccable/` nor `src/` is committed.

- Zebra rows: every second row has a light tint (`#eff3f8` on white, `#142540` on navy). The phone rows use the same tint.
- Quality days: the day grid now has one table column for each day. A quality day has a tinted column from the header to the team-starts row, and the header cell stays a solid block. The block is the sign that does not depend on color only.
- Section rules: 1px rules in a low-contrast blue-gray (`#d2d9e4` light, `#2e4264` dark).
- Phone: each player is a `<details>` row. The closed row shows the team band, the rank, the name with POS and the roster slot below it, GP and the total playoff games. The open row shows the 7 other stats, the 4 weekly cells and the 21-day grid. The desktop table is not shown on a phone.
- IL: Paolo Banchero (rank 30) and Coby White (rank 77) are now in rank order with the other players and carry a red IL flag. The IL divider row ("Games only. Not in the team starts.") is removed. The "Game, on IL" mark is removed from the key. The key has new items for "Quality day" and "IL: on IL now, counts in the starts". The footnote says that the IL players are in the lineup pool because they will likely be back by the playoffs.
- Theme switch: a group of three buttons in the side menu and in the phone menu: Auto, Light and Dark. The pressed button has `aria-pressed="true"` and a white fill. The choice is in `localStorage` (key `lab-theme`) inside `try`/`catch`. A small script in `<head>` sets the theme before the first paint.

### New playoff starts

The script copied the engine rule of `draft/team_builder.js`: slots PG, SG, SF, PF, C and one Util, players in custom-rank order, and no second night of a back-to-back for a player with `rests_b2b` = 1. Without the IL players, the script got the old totals again (34, 34 and 33 = 101, with 8 starts lost and 9 open slots on quality days). This check shows that the script copies the old sample.

| Week | Old (IL out) | New (IL in) |
| --- | --- | --- |
| Wk19 | 34 | 35 |
| Wk20 | 34 | 36 |
| Wk21 | 33 | 33 |
| Total | 101 | 104 |

With the IL players in the pool, 26 starts are lost to a full lineup (Black 9, Mitchell 8, Gobert 3, Quickley 3, White 3), and 8 slots are open on quality days. Coby White has `rests_b2b` = 1, so he rests on one back-to-back night (Mar 11).

### Point 8: the footer totals

The draft board does not use the term "potential starts". Its team-table footer (`src/fantasyhoops/draft/board.py`, `renderFooter`, lines 1259-1305) has two percent rows. The sample copies both rows with their labels and math:

- **Used (started / games)**: the started games / the games of the players. A rest night of a player with `rests_b2b` = 1 is not a game (`plays()`, line 1119).
- **vs ideal**: the started games / min(the number of players × the most games of any NBA team that week, 6 slots × the days of the week) (line 1268). The draft board has 6 starting slots (PG, SG, SF, PF, C and Util), not 8.

The board shows each cell as `started/all · N%`. The sample shows the percent in bold with `started/all` below it, because the week columns are narrow.

| Row | Wk19 | Wk20 | Wk21 | Total |
| --- | --- | --- | --- | --- |
| Started | 35 | 36 | 33 | 104 |
| Used (started / games) | 35/43 · 81% | 36/41 · 88% | 33/46 · 72% | 104/130 · 80% |
| vs ideal | 35/42 · 83% | 36/42 · 86% | 33/42 · 79% | 104/126 · 83% |

The 12 players are more than 6 slots × 7 days can hold, so the ideal for each week is 42, the slot limit. The board colors a percent green at 90% or more, yellow at 70% to 89% and red below 70%. The sample does not copy these colors, because the Card Back palette has no yellow or green. The footnote now gives the two definitions. The per-player week cells still count a rest night as a game, as before. Thus the games of a week in the Used row can be smaller than the sum of the player cells (Wk19: 43, not 44, because of the rest night of Coby White).

The screenshots `desktop.png`, `desktop-dark.png` and `mobile.png` were taken again after this change.

### Contrast check

The check computed the WCAG ratios for the text and the marks on the page, the zebra, the quality column and the quality column on a zebra row, in both themes. All text is at 4.5:1 or more where it appears. The red text appears only on the page and the zebra (5.28:1 light, 5.59:1 dark). The "no game" dash was at 2.79:1 on the shaded zebra cells in the light theme, so its color changed to `#6f7889` (3.34:1).

### Screenshots (2026-10-28)

In `.impeccable/review/`: `desktop.png`, `desktop-dark.png`, `mobile.png` (rows closed), `mobile-open.png` (the Banchero row open), `mobile-dark.png`, `mobile-menu.png` (the phone menu with the theme switch), `theme-auto-light.png`, `theme-dark-chosen.png` (Dark chosen on a light system) and `theme-light-chosen.png` (Light chosen on a dark system).

### Open

- The owner has not approved the revised sample. No issue is filed.
- The brief still lists where the home-page data is built.
