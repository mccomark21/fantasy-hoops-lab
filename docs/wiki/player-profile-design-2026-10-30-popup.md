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
