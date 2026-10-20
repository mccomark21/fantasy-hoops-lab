# 2. Publish the adds plan on public GitHub Pages

Date: 2026-10-20

Status: Accepted

## Context

The weekly adds planner writes an HTML page in `output/adds/`. You make the adds on your phone, so the page must open on a phone. The draft board uses GitHub Pages for this. GitHub Pages sites on this plan are public.

The plan page shows your roster, your core, your streamers and your adds plan. Anyone with the URL can see them, including the other managers in the league.

A private claude.ai artifact can also put the page on a phone, and only you can see it.

## Decision

Publish the plan page on GitHub Pages. The site has this layout:

- `/`: a Fantasy Hoops Lab home page with one line and one link for each tool.
- `/draft/`: the draft board and its playoff window pages.
- `/adds/`: the adds plan.

One shared publish step in `core/` writes the whole site from `output/`.

The user wants to show this work. The user's portfolio is a separate site, and it links to the root of this site. The site itself is only about Fantasy Hoops Lab. The user accepts that the other managers can see the strategy.

## Consequences

- Each published plan shows your roster and your planned adds to anyone with the URL.
- The draft board moves from the root to `/draft/`. The old URL of the board stops working.
- `draft/publish.py` becomes the shared publish step. It no longer replaces the pages of the other tools.
- A new tool adds one folder and one line on the home page.
