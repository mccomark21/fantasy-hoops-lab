---
version: 1
slug: "src-fantasyhoops-core-publish-py"
primary_target: "src/fantasyhoops/core/publish.py"
related_targets: []
---

# Surface brief: home page and site menu

## Scope

The home page of the GitHub Pages site (`core/publish.py`, `home_page()` and `nav_bar()`), and the site menu that every tool page shares. Mode: Operate. Build path: code-led.

## Job

The owner opens the site and sees the current roster in custom-rank order:
- the 2026-27 season stats to date (ESPN, per game)
- the playoff games and starts for wk19, wk20, wk21 and the total
- a day grid for the 21 playoff days that shows who fits in the lineup each day, with the higher-ranked players placed first (the `scoreCore` engine of `draft/team_builder.js`)

The menu is a side panel, not a top bar. The page must not be slower to use than the current site. It must not look too plain or too decorative.

## Constraints

- Desktop first, and usable on a phone.
- WCAG 2.2 AA in both themes. No state shown by color only.
- Sample first: the owner approves a static sample before an issue is filed and the generator is built.
- Data: the roster comes from the Yahoo team page that the adds run reads. The stats come from one ESPN `statistics/byathlete` request. The rank and the playoff counts come from `draft/rankings.py` and `core/schedule.py`.

## Unresolved

- Where the home-page data is built: at the end of each adds run, or in a separate step.
- The dark theme of the world. The decision sketch was light only.

## Direction contract

THESIS: Each player's season, set like the back of his basketball card: a team-color band, the stat line, and the playoff schedule as the fine print. It refuses the fantasy-app roster grid, with its logos, badges and gray zebra rows.

OWN-WORLD: Bright white coated stock, royal-blue ink (#1d4f91) for the menu ground and the rules, card red (#c8102e) for rank numerals, alerts and IL, and flat two-ink offset color with no gradients or shadows. Archivo: heavy condensed caps for names, a sturdy grotesk for the stat line, tabular numerals. In the dark theme, the stock turns to a deep navy card back with white ink.

STORY: The owner sees who is on the team, how each player is doing this season, and whether each one fits the lineup on each playoff day. The red numbers show where starts are lost, so the owner knows which spot to upgrade.

FIRST VIEWPORT: A 216px royal-blue side menu with the site name, Roster (current), Adds plan, Draft board and Keeper report. The main area opens on a header with the team name in condensed caps, plus the week and the adds used. Below it is the full roster table: a team block, the rank, the player, 8 stat columns, the 4 playoff columns (starts/games) and the 21-day grid in three weeks of seven. Then the team-starts total row, an IL divider and the key.

FORM: Card Back, my top-ranked grounded candidate (1 of 7), chosen as the pick card over the assigned Center-Hung. seed:44f4e78605ff12e4

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
