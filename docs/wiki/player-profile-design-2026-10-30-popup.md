# Player pop-up of 2026-10-30

On 2026-10-30, the owner decided that the player profile opens as a pop-up over the current page. The owner said: "This way you don't leave the page you're on but you get to delve into a player's usage, minutes, etc." This changes decision 5 of [Player profile design of 2026-10-29](player-profile-design-2026-10-29.md). The other decisions of that page and its layout and chart-style decisions stay.

## State before the change (2026-10-30, `mccomark21/fantasy-hoops-lab@c997562`)

- No player profile code existed. #186 (shell) and #187 to #189 (quadrants) were open and blocked by #185.
- Only #186 names the page shape. #187 to #189 fill quadrants and need no change of scope.

## Owner decisions (2026-10-30)

1. Form: a large centered modal that holds the approved 4-quadrant report card unchanged. The page behind is dimmed. On a phone, the modal becomes a full-screen sheet.
2. Pages that open it from a player name: Roster, Free agents and Trade. Not the Adds plan page.
3. The `/players/` page with the search box stays. The modal has an "Open full profile" link to it.
4. Opening the modal changes the URL hash (for example `/free-agents/#player=ace-bailey`). The browser Back button closes the modal. A copied link opens it.

## Chief of staff decisions (2026-10-30), not yet owner-reviewed

- One shared modal (JS and CSS) in `core/`, used by all three pages and by `/players/`. No page keeps its own copy. This keeps the pages consistent, as the owner asked on 2026-10-29 for the charts.
- The player data goes in one shared file that the publish writes. The modal reads it on the first open. The data is not embedded in each page, because three copies of the data would make each page heavy.

## Next steps

- A static sample: the Free agents page with the modal open, made from real data and the approved `docs/design/players-sample.html`. The owner reviews it before #186 changes (owner preference: a sample before a build).
- After approval, edit #186 to the modal scope. Do not file new issues (owner rule of 2026-10-27).

## Modal sample (2026-10-30)

- An agent wrote `.impeccable/review/players-modal-sample.html` (untracked). The background is the Free agents build `output/adds/free_agents.html` (Week 2, made 2026-10-29). The 3 sample players are not free agents, so the agent added rows with made-up table numbers and a note on the page.
- The agent checked it in Chromium (Playwright). At 1440x900 the card fits with no scroll (793 px of 876). At 390x844 it is a full-screen sheet with stacked quadrants that scrolls. The hash, Back, deep link, Esc, Close, backdrop click, focus trap and focus return passed.
- Open point: on a phone, the chart text is very small. The approved sample had the same problem.
- Notes for the #186 build, from the agent: the pages draw names in JS with no player id, and a redraw replaces them, so focus return must find the name by slug. Page-wide `h1`, `h2`, `p` and `*` rules leak into the card, so the card styles need a scope. Tooltips must sit inside the dialog.

## Owner review of the modal sample (2026-10-30)

- On 2026-10-30, the owner approved the modal. The owner said: "Everything else looked good."
- The "Open full profile" link of the sample pointed to `docs/design/players-sample.html`. The owner said that on that page "a lot of the text/font looks blocky" and that it needs a polish pass. The cause was not known at the time of the review.
- Next: an agent finds the cause and makes a Before / After page that changes only the text. An agent edits #186 to the modal scope.
- On 2026-10-30, an agent edited #186 to the modal scope. Item 6 and its criterion became the shared modal (hash, Back, Esc, focus, "Open full profile"). New items 7 and 8 add the shared modal in `core/` and the shared player file. Item 2 reads that file, not embedded JSON. The issue gained the modal fit and phone-sheet criteria, "Build notes" and a note on the approved sample. The title gained "and player modal". #187 to #189 had no page-link line and did not change.

## Cause of the blocky text (2026-10-30)

- As of `mccomark21/fantasy-hoops-lab@24db84c`, `docs/design/players-sample.html` loads `fonts/archivo-latin.woff2`, but `docs/design/` has no `fonts/` folder. The font load fails. The stack falls back to Arial Narrow, which has no width axis, so each `font-stretch` has no effect and weights 800 and 900 render heavy. The modal sample embedded Archivo as base64 and did not have the problem. An agent found this, and the chief of staff checked that the folder is missing.
- The build is not affected: `publish.write_page` calls `tokens.copy_font` (`src/fantasyhoops/core/tokens.py`), which puts the font beside each page.
- An agent wrote `.impeccable/review/players-text-polish.html` (untracked), a Before / After page where After only loads Archivo.
- Follow-up (not filed): a test that each committed HTML file with a `@font-face` or `preload` URL has that file in the repo. Such a test would have caught this.
