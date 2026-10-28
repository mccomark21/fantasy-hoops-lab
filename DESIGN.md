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
  mark: "#1d4f91"
  zebra: "#eff3f8"
  qcol: "#e0e8f4"
  qcol-z: "#d6e0ef"
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

`core/tokens.py` holds each token with a light value and a dark value. `core/publish.py` (the menu and the home page) and `adds/page.py` use only `var(--...)`. The adds page gives some tokens short names (`--fg`, `--muted`, `--q`), but it defines no colors.

| Token | Light | Dark | Job |
| --- | --- | --- | --- |
| `lab-stock` | `#ffffff` | `#0e1a2e` | The page ground. |
| `lab-ink` | `#14171c` | `#eef2f8` | Text. The "fit" square and the flags. |
| `lab-mute` | `#5b6270` | `#a7b2c4` | Secondary text. |
| `lab-rule` | `#e7e9ee` | `#23334d` | Row rules. |
| `lab-blue` | `#1d4f91` | `#16305a` | The menu ground. |
| `lab-blue-deep` | `#163f75` | `#1f3f73` | The hover of a menu item. |
| `lab-on-blue` | `#ffffff` | `#ffffff` | Text on the menu. |
| `lab-red` | `#c8102e` | `#ff6b7d` | Alerts: warnings, injury status, back-to-back marks, the current-page marker. |
| `lab-on-red` | `#ffffff` | `#0e1a2e` | Text on `lab-red`. |
| `mark` | `#1d4f91` | `#8fb3ff` | Heading rules, the page title, links, and the selected or sorted state. |
| `zebra` | `#eff3f8` | `#142540` | Every second table row. |
| `qcol` / `qcol-z` | `#e0e8f4` / `#d6e0ef` | `#1c3254` / `#223a60` | A shaded cell: a started game in the plan grid. `-z` is the shade on a zebra row. |
| `vrule` | `#d2d9e4` | `#2e4264` | Vertical rules between table sections. |
| `lamp-off` | `#6f7889` | `#7d8eab` | Chip borders and marks that are off. |
| `lab-scrim` | `rgb(8 16 32 / .5)` | same | The shade behind the open drawer. |

All small text is at least 4.5:1 in both themes. `lamp-off` on `lab-stock` is 4.45:1, so use it only for borders and marks, not for text.

### Named Rules
**The One Source Rule.** A new color goes into `core/tokens.py` with a light value and a dark value. A page never writes a hex value.

**The Text Accent Rule.** As text color, `mark` shows only the page title, links, and the selected or sorted state. Pressed chips are a solid `mark` block. The sorted column and the selected day have `mark` text and a 3px `mark` bar under the header. Other marks (the fit square, the `+` add mark, the open row, the FA?, MIN+ and UP flags) use ink.

**The Red Is Alert Rule.** `lab-red` marks only something that needs attention. It is never a decoration.

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
- The adds page body is 720px wide at most, with 28px side padding (16px below 600px). The home page body is 640px.
- The plan grid hides long labels below 600px. The free-agent table shows its wide columns at 600px and wider.

## Elevation & Depth

The system is flat. No surface has a shadow. Zebra rows, shaded cells and rules show the structure.

## Shapes

All corners are square: chips, flags, the theme switch, the menu buttons and the status tag.

## Components

### Site menu
- **Desktop:** a `lab-blue` panel with the site name in condensed caps, the league line, the items Roster and Adds plan, and the theme switch at the bottom.
- **Current page:** a `lab-stock` row with ink text and a 9px `lab-red` square.
- **Theme switch:** three square buttons, Auto, Light and Dark, with `aria-pressed`. The pressed button is `lab-stock` with ink text. A script in `<head>` applies the saved choice before the first paint.

### Chips
- **Style:** a square button with a 1.5px `lamp-off` border on `lab-stock`. A second line in small muted text can show a count.
- **Selected:** a solid `mark` fill with `lab-stock` text (`aria-pressed="true"`).
- **Empty:** a chip with no matching players has a dashed border and muted text.

### Stats
- **Style:** no box. Each stat is a muted 12px label above a 24px condensed value. A 1px rule separates the stats.

### Flags
- **Style:** a square tag with a 1.5px ink border and 11px bold ink text (FA?, MIN+, UP). The next-week flag is solid ink with stock text. The status flag (for example, Q or O) is solid `lab-red` with `lab-on-red` text.

### Tables
- **Style:** full width, collapsed borders, 1px `lab-rule` row rules, zebra rows, and a 2px `mark` rule under the head.
- **Sorted column and selected day:** `mark` text and a 3px `mark` bar under the header. Cells of a selected day have a 12% `mark` tint.

### Plan grid (signature component)
- **Style:** a fixed-layout table with one row for each plan and one column for each day. A started game is a `qcol` cell with a bold number. The Open row is bold, with a 2px ink rule below it.

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
