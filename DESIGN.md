---
name: Fantasy Hoops Lab
description: Analysis pages for one Yahoo fantasy basketball league. Clean, minimal and sleek.
colors:
  stone-page: "#fafaf9"
  stone-header: "#f5f5f4"
  stone-rule: "#e7e5e4"
  stone-average: "#d6d3d1"
  stone-muted: "#78716c"
  stone-ink: "#1c1917"
  accent-violet: "#7c3aed"
  signal-good: "#16a34a"
  signal-bad: "#dc2626"
  signal-warn: "#eab308"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.4
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.4
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  data:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: "tnum"
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.04em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "16px"
  xl: "24px"
components:
  chip:
    backgroundColor: "{colors.stone-page}"
    textColor: "{colors.stone-ink}"
    rounded: "{rounded.pill}"
    padding: "4px 9px"
  chip-selected:
    backgroundColor: "{colors.accent-violet}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "4px 9px"
  stat:
    backgroundColor: "{colors.stone-header}"
    textColor: "{colors.stone-ink}"
    rounded: "{rounded.md}"
    padding: "2px 10px"
  flag-good:
    backgroundColor: "{colors.signal-good}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 4px"
  flag-status:
    backgroundColor: "{colors.signal-warn}"
    textColor: "{colors.stone-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 4px"
  table-header:
    backgroundColor: "{colors.stone-header}"
    textColor: "{colors.stone-ink}"
    padding: "5px 4px"
  site-nav:
    backgroundColor: "{colors.stone-page}"
    textColor: "{colors.stone-muted}"
    padding: "8px 16px"
---

<!-- BASELINE: this file records the design as of 2026-10-27, before the redesign. The redesign of the home page, the site nav and the adds plan will replace the values here. Tokens marked "provisional" are expected to change. -->

# Design System: Fantasy Hoops Lab

## Overview

**Creative North Star: "The Tailored Box Score"**

The site presents data in a clean, minimal way. Each table and chart is cut to fit its numbers, like a tailored suit: sleek and stylish, but never loud. The data carries the page. Type, rules and one accent give the data shape. Decoration does not.

The current pages are dense and flat. They use one neutral stone ramp, one violet accent and three signal colors. All type is the system font. Tables use thin rules and no shadows. The pages have a light theme and a dark theme. Both themes follow `prefers-color-scheme`, and a `data-theme` attribute can force one theme.

The current system meets the minimal part of the North Star. It does not yet meet the stylish part. The pages look generic, and the design does not show its own identity.

**Key Characteristics:**
- The numbers come first: tabular figures, right-aligned columns and thin rules.
- One neutral ramp (warm stone) and one accent (violet).
- The design is flat. Tone and rules show depth, not shadows.
- One page body is 720px wide at most (the adds plan). The home page is 640px.
- Python generators write all CSS inline. The pages load no external files.

## Colors

A warm stone neutral ramp with one violet accent and a traffic-light signal set.

### Primary
- **Accent Violet** (provisional): marks the selected state. It is the color of selected chips, the sorted column, the selected day, open roster spots, links and the "fit" dot. It is the only color for interaction. The redesign will choose the final accent.

### Neutral
- **Stone Ink**: body text, headings and the current nav link.
- **Stone Muted**: secondary text, sub-rows, small labels and the nav background text. It has a contrast ratio of approximately 4.6:1 on Stone Page.
- **Stone Rule**: table rules, chip borders and container borders.
- **Stone Header**: table header rows, stat backgrounds and the open-spot row.
- **Stone Average**: the "average" signal on the draft board.
- **Stone Page**: the page background and the unselected chip background.

### Signals
- **Signal Good**: a cell that is "on" in the plan grid (as a 30% tint), and the "new" flag.
- **Signal Bad**: warnings, and the back-to-back mark on a game.
- **Signal Warn**: the player status flag (for example, GTD), with dark text.

The dark theme uses the same roles with the stone ramp reversed: page `#1c1917`, ink `#f5f5f4`, muted `#a8a29e`, rule `#44403c`, header `#292524`. The accent and the signals move one step lighter (violet `#a78bfa`, good `#22c55e`, bad `#ef4444`, warn `#facc15`).

### Named Rules
**The One Accent Rule.** Violet is the only interaction color. If an element is selected, sorted or chosen, it is violet. No other element is violet.

**The Copied Token Problem.** Each page generator holds its own copy of the tokens (`adds/page.py`, `draft/board.py`, `core/publish.py`). The site nav uses literal hex values. The keeper report (`draft/report.py`) uses a different palette: slate neutrals and a blue accent (`#1d5fd1`). The redesign must move all pages to one shared token source.

## Typography

**Body Font:** system-ui (with -apple-system, Segoe UI, sans-serif)

**Character:** One family in a few weights. The type is neutral and does not carry identity now. The keeper report is the exception: it defines separate display, body and data fonts with 16px body text.

### Hierarchy
- **Headline** (700, 22px): the page title (h1).
- **Title** (700, 16px): section headings (h2). Card headings (h3) use 15px.
- **Body** (400, 14px, line-height 1.4): paragraphs and most text.
- **Data** (400, 12–13px, tabular figures): table cells. Plan totals use 700 at 14px.
- **Label** (400, 11px, 0.04em, uppercase): stat labels and filter group labels.

### Named Rules
**The Tabular Rule.** All numbers use `font-variant-numeric: tabular-nums`, so that the digits align in each column.

## Layout

The page body is one centered column. The adds plan is 720px wide at most and the home page is 640px. The body padding is 24px at the top and bottom and 16px at the sides. Gaps between controls are 6px. Sections are 20px apart.

There is one breakpoint, at 600px:
- Below 600px, the plan grid hides long labels and makes its columns narrower.
- At 600px and wider, the free-agent table shows its wide columns.

The draft board is the exception. It is a full-width table in a scroll container with a sticky header.

## Elevation & Depth

The system is flat. Header rows and stats use the Stone Header tint to show depth. Containers use one 1px Stone Rule border. The one shadow on the site is the dropdown menu on the draft board (`0 4px 12px rgba(0,0,0,.2)`).

### Named Rules
**The Flat Page Rule.** Surfaces have no shadow. Only a floating menu has a shadow.

## Shapes

Corners are small. Flags and pills use 4px. Stats, inputs and buttons use 6px. Containers and the tool list use 8px. Chips are fully round (999px). The plan grid and the free-agent table have square corners.

## Components

### Chips
- **Style:** a round button with a Stone Rule border on Stone Page. A second line in small muted text can show a count.
- **Selected:** a violet fill with white text. The `aria-pressed="true"` attribute sets the state.
- **Empty:** a chip with no matching players is at 55% opacity.

### Stats
- **Style:** a small inline box with a Stone Header fill and a Stone Rule border. It shows a value in bold 17px and an uppercase 11px label.
- **Key stat:** a stat with a Stone Ink border.

### Flags
- **Style:** an inline label with a 4px radius, 11px bold text and a solid fill. The "new" flag is green. The "up" flag is violet. The "next week" flag is ink on page. The status flag is yellow with dark text.

### Tables
- **Style:** full width, collapsed borders, 1px Stone Rule lines between rows, a Stone Header row at the top.
- **Sortable header:** the pointer cursor. The sorted column is violet.
- **Selected day:** the column header is violet and the cells have a 10% violet tint.

### Navigation
- **Style:** a bar at the top of each page with 14px text, a Stone Page background and a 1px bottom rule. The links are violet and bold. The current page link is ink. The nav has no hover state and no mobile treatment.

### Plan grid (signature component)
- **Style:** a fixed-layout table with one row for each plan and one column for each day. A cell that is "on" has a 30% green tint. The open-spot row has a header tint with violet bold text. A moves column at the right lists the adds and drops in 11px text.

## Do's and Don'ts

### Do:
- **Do** use tabular figures for all numbers.
- **Do** keep violet for the selected state, the sorted state and links only.
- **Do** keep surfaces flat, with 1px Stone Rule borders and the Stone Header tint.
- **Do** supply a light theme and a dark theme for each token, and support the `data-theme` override.

### Don't:
- **Don't** add a new page with its own palette. The keeper report shows the problem.
- **Don't** put white text on Signal Good. White on `#16a34a` is approximately 3.3:1, which fails WCAG AA for 11px text. The "new" flag does this now.
- **Don't** add new side-stripe borders. The skip notice on the adds plan uses a 3px left border in Signal Warn. The redesign must replace it.
- **Don't** show good and bad with color only. PRODUCT.md requires a sign, a label or a shape too.
