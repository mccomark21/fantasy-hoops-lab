---
name: Fantasy Hoops Lab
description: Analysis pages for one Yahoo fantasy basketball league. Card Back identity, approved 2026-10-28 (#117).
colors:
  # Light theme (white stock). The dark values are in the Colors section and in src/fantasyhoops/core/tokens.py.
  lab-stock: "#ffffff"
  lab-ink: "#14171c"
  lab-mute: "#5b6270"
  lab-rule: "#e7e9ee"
  lab-blue: "#1d4f91"
  lab-blue-deep: "#163f75"
  lab-on-blue: "#ffffff"
  lab-red: "#c8102e"
  lab-on-red: "#ffffff"
  lab-green: "#17743a"
  mark: "#1d4f91"
  zebra: "#eff3f8"
  qcol: "#e0e8f4"
  qcol-z: "#dae3f1"
  vrule: "#d2d9e4"
  lamp-off: "#6f7889"
typography:
  display:
    fontFamily: "Archivo, Arial Narrow, system-ui, sans-serif"
    fontSize: "clamp(30px, 4vw, 44px)"
    fontWeight: 900
    fontStretch: "66%"
    lineHeight: 0.9
    textTransform: "uppercase"
  section:
    fontFamily: "Archivo, Arial Narrow, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 900
    fontStretch: "75%"
    lineHeight: 1.1
    textTransform: "uppercase"
  body:
    fontFamily: "Archivo, Arial Narrow, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  data:
    fontFamily: "Archivo, Arial Narrow, system-ui, sans-serif"
    fontSize: "12-13px"
    fontWeight: 400
    fontFeature: "tnum"
  label:
    fontFamily: "Archivo, Arial Narrow, system-ui, sans-serif"
    fontSize: "11-12px"
    fontWeight: 800
rounded:
  none: "0"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "16px"
  xl: "28px"
components:
  menu:
    backgroundColor: "{colors.lab-blue}"
    textColor: "{colors.lab-on-blue}"
    width: "216px"
  menu-current:
    backgroundColor: "{colors.lab-stock}"
    textColor: "{colors.lab-ink}"
    marker: "{colors.lab-red}"
  chip:
    backgroundColor: "{colors.lab-stock}"
    textColor: "{colors.lab-ink}"
    border: "1.5px solid {colors.lamp-off}"
    rounded: "{rounded.none}"
  chip-selected:
    backgroundColor: "{colors.mark}"
    textColor: "{colors.lab-stock}"
    rounded: "{rounded.none}"
  flag:
    textColor: "{colors.lab-ink}"
    border: "1.5px solid {colors.lab-ink}"
  flag-status:
    backgroundColor: "{colors.lab-red}"
    textColor: "{colors.lab-on-red}"
---

# Design System: Fantasy Hoops Lab

## Overview

**Creative North Star: "The Tailored Box Score"**, in the form **Card Back**.

Each page reads like the back of a basketball card: white coated stock, royal-blue ink for the rules and the headings, and card red for alerts. The print is flat two-ink offset color, with no gradients and no shadows. In the dark theme, the stock turns to a deep navy card back with white ink. The owner approved this identity on 2026-10-28 (#117). The approved sample is `.impeccable/review/sample-index.html`.

**Key Characteristics:**
- One token source: `src/fantasyhoops/core/tokens.py`. Pages hold no literal colors.
- One family, Archivo, self-hosted next to each page in `fonts/`. Heavy condensed caps for names and headings. A sturdy grotesk with tabular figures for data.
- A royal-blue side menu on a desktop. A top bar with a drawer on a phone.
- Square corners. Rules, not boxes or shadows, give the page its structure.
- Light and dark themes follow `prefers-color-scheme`. The Auto, Light and Dark switch in the menu sets `data-theme` on `<html>` and keeps the choice in `localStorage`.

## Colors

`core/tokens.py` holds each token with a light value and a dark value. `core/publish.py` (the menu), `core/home.py` (the Home page) and `adds/page.py` use only `var(--...)`. The adds page gives some tokens short names (`--fg`, `--muted`, `--q`), but it defines no colors.

| Token | Light | Dark | Job |
| --- | --- | --- | --- |
| `lab-stock` | `#ffffff` | `#0e1a2e` | The page ground. |
| `lab-ink` | `#14171c` | `#eef2f8` | Text. The "fit" square and the flags. |
| `lab-mute` | `#5b6270` | `#a7b2c4` | Secondary text. |
| `lab-rule` | `#e7e9ee` | `#23334d` | Row rules. |
| `lab-blue` | `#1d4f91` | `#16305a` | The menu ground. |
| `lab-blue-deep` | `#163f75` | `#1f3f73` | The hover of a menu item. |
| `lab-on-blue` | `#ffffff` | `#ffffff` | Text on the menu. |
| `lab-red` | `#c8102e` | `#ff7d8d` | Alerts: warnings, injury status, back-to-back marks, the current-page marker, a deficit in the matchup table. |
| `lab-on-red` | `#ffffff` | `#0e1a2e` | Text on `lab-red`. |
| `lab-green` | `#17743a` | `#6fd08c` | A lead in the matchup table of the adds page (#144). |
| `mark` | `#1d4f91` | `#8fb3ff` | Heading rules, the page title, links, and the selected or sorted state. |
| `zebra` | `#eff3f8` | `#142540` | Every second table row. |
| `qcol` / `qcol-z` | `#e0e8f4` / `#dae3f1` | `#1c3254` / `#223a60` | A shaded cell: a quality day or a started game on the Roster page. `-z` is the shade on a zebra row. |
| `vrule` | `#d2d9e4` | `#2e4264` | Vertical rules between table sections. |
| `lamp-off` | `#6f7889` | `#7d8eab` | Chip borders and marks that are off. |
| `lab-scrim` | `rgb(8 16 32 / .5)` | same | The shade behind the open drawer. |

All small text is at least 4.5:1 in both themes. The back-to-back mark is `lab-red` on `qcol-z`: 4.55:1 in light and 4.65:1 in dark (#115). `lamp-off` on `lab-stock` is 4.45:1, so use it only for borders and marks, not for text.

### Named Rules
**The One Source Rule.** A new color goes into `core/tokens.py` with a light value and a dark value. A page never writes a hex value.

**The Text Accent Rule.** As text color, `mark` shows only the page title, links, the heads of the Roster-look tables, and the selected or sorted state. Pressed chips are a solid `mark` block. The sorted column and the selected day have `mark` text and a 3px `mark` bar under the header. The teams of an add cell in the week grid are buttons, so they show as `mark` text with an underline, as a link. Other marks (the fit square, the band and the start square of the week grid, the FA?, MIN+ and UP flags) use ink.

**The Red Is Alert Rule.** `lab-red` marks only something that needs attention. It is never a decoration. A category that you trail in the matchup needs attention, so its margin is `lab-red`.

**The Green Is Lead Rule.** `lab-green` marks only a category that you lead in the matchup table. It is text only. On `zebra`, it is 5.2:1 in light and 8.1:1 in dark.

## Typography

**Font:** Archivo (Omnibus-Type, SIL Open Font License 1.1). One variable file, `archivo-latin.woff2`, with the weights 400 to 900 and the widths 62% to 125%. The fallback is Arial Narrow, then system-ui.

### Hierarchy
- **Display** (900, width 66%, uppercase, 30–44px): the page title, with a 3px `mark` rule below it.
- **Section** (900, width 75%, uppercase, 19px): h2, with a 2px `mark` rule below it.
- **Body** (400, 14px, line-height 1.4).
- **Data** (400, 12–13px, tabular figures). Totals use 800.
- **Label** (800, 11–12px): table heads and filter labels. Not uppercase and not letter-spaced.
- **Stat** (900, width 75%, 24px value, with a 12px muted label above it).

### Named Rules
**The Tabular Rule.** All numbers use `font-variant-numeric: tabular-nums`.

## Layout

- The side menu is 216px wide and fixed at the left at 900px and wider. The main area starts at its right edge.
- Below 900px, the menu is a drawer. A 48px blue bar at the top holds the site name and a Menu button. The drawer moves the focus to its Close button, closes on Escape and on the scrim, and makes the page behind it inert.
- The adds page body is 720px wide at most, with 28px side padding (16px below 600px). The Home page body is 1000px wide at most. Below 1100px, each page row and the About section go to one column.
- The week grid shows its 7 day columns at each width. Below 600px, it shows short labels ("M" and "26"). The free-agent table shows its wide columns at 600px and wider.

## Elevation & Depth

The system is flat. No surface has a shadow. Zebra rows, shaded cells and rules show the structure.

## Shapes

All corners are square: chips, flags, the theme switch, the menu buttons and the status tag.

## Components

### Site menu
- **Desktop:** a `lab-blue` panel with the site name in condensed caps, the league line, the items Home, Roster, Adds plan, Free agents and Trades, and the theme switch at the bottom.
- **Current page:** a `lab-stock` row with ink text and a 9px `lab-red` square.
- **Theme switch:** three square buttons, Auto, Light and Dark, with `aria-pressed`. The pressed button is `lab-stock` with ink text. A script in `<head>` applies the saved choice before the first paint.

### Chips
- **Style:** a square button with a 1.5px `lamp-off` border on `lab-stock`. A second line in small muted text can show a count.
- **Selected:** a solid `mark` fill with `lab-stock` text (`aria-pressed="true"`).
- **Empty:** a day chip with no open slot has a dashed border and muted text. When it is selected, it keeps the dashed border and has the `mark` fill with `lab-stock` text, as the other selected chips (#115).

### Stats
- **Style:** no box. Each stat is a muted 12px label above a 24px condensed value. A 1px rule separates the stats.

### Flags
- **Style:** a square tag with a 1.5px ink border and 11px bold ink text (FA?, MIN+, UP). The next-week flag is solid ink with stock text. The status flag (for example, Q or O) is solid `lab-red` with `lab-on-red` text.

### Tables
- **Style:** full width, collapsed borders, 1px `lab-rule` row rules, zebra rows, and a 2px `mark` rule under the head.
- **Roster look (#143):** the Roster table of the Roster page, the examples of the Home page, and the free-agent table and the waiver table of the adds page, use the class `lab-t`. `publish.TABLE_STYLE` in `core/publish.py` is the one source of its CSS. The head has 11px bold `mark` text. The first column is the team band: the color of the NBA team (`tokens.TEAM_COLORS`) with text at 4.5:1 or more (`publish.band_style()`). The player cell has the name in heavy condensed caps (20px, 18px below 900px) and a 12px muted line below it.
- **Sorted column and selected day:** a 3px `mark` bar under the header. The sorted column also has an arrow (▼). Cells of a selected day have a 12% `mark` tint.

### Matchup table
- **Style:** the matchup section of the adds page (#144), above the team plan. One column for each category and the rows You, Opp, Margin and Weight, in a fixed layout that fits 320px.
- **Margin:** ink for a close margin, `lab-green` for a lead, `lab-red` for a deficit. A large margin is bold (800). The sign stays.
- **Weight:** 1.00 in bold ink. Lower weights step to a 50% mix of ink and `lab-mute`, then to `lab-mute`.
- **Key:** a line under the table shows each look.

### Week grid (signature component)
- **Style:** the team plan of the adds page (#140, the approved C3 heat sample). A fixed-layout table with one column for each day of the fantasy week and the rows Games, Add 1 and Add 2. The games of the day shade the whole column with a `mark` tint, 0% to 40%, mixed with `lab-stock`. The Games row has a 2px ink rule below it.
- **Add cell:** a box of `lab-stock` with a 1.5px ink border and a 3px top border: "+<slots>" in condensed caps, then the teams. Hover: the `zebra` ground. Selected (the cell that set the filters): `lab-stock` text on a solid `mark` block. Focus: a 2px ink outline. A day header that set the filters has the same selected state.
- **Band:** a 6px ink band through the days that the new player holds the spot, with an 18px ink square (14px below 600px) on each day that he starts.
- **Past day:** a 10% `lab-mute` ground and `lab-mute` text. A past add is a dashed `lamp-off` box with `lab-mute` text. A past band and its square are `lab-mute`.

## Do's and Don'ts

### Do:
- **Do** take each color from `core/tokens.py`, with a light value and a dark value.
- **Do** use tabular figures for all numbers.
- **Do** show a state with a shape, a label or a sign as well as a color.
- **Do** keep corners square and surfaces flat.

### Don't:
- **Don't** write a hex value in a page generator. The draft board (`draft/board.py`) and the keeper report (`draft/report.py`) keep their own palettes. They are not on the site (owner decision of 2026-10-28).
- **Don't** use `mark` as a text color for a mark that is not selected, sorted or a link.
- **Don't** use side-stripe borders. A notice gets a full border.
- **Don't** add gradients, shadows or rounded pills.
