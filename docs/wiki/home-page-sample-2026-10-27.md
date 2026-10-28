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
