# Site redesign: critique and issues of 2026-10-27

On 2026-10-27, the owner started a redesign of the site with the Impeccable skill (`/impeccable`, v4.8.0).

## Setup

- The owner answered the init interview. The answers are in `PRODUCT.md` at the repo root: product register, one owner on a desktop first and on a phone when away, "sharp, analytical", references Cleaning the Glass and The Athletic / FiveThirtyEight, anti-references Yahoo and ESPN apps and generic SaaS dashboards, WCAG 2.2 AA.
- `DESIGN.md` at the repo root records the design of 2026-10-27 as a baseline, before the redesign. The owner named the North Star: "The Tailored Box Score", clean, minimal and sleek, stylish but not loud. The owner kept the violet accent as provisional and gave no opinion on the components yet.
- The scan found two visual systems. The adds page, the draft board, the home page and the nav use stone and violet. The keeper report uses slate and blue with other fonts.
- On 2026-10-27, `PRODUCT.md`, `DESIGN.md` and `.impeccable/` were not committed.

## Critique of the adds page

Two agents assessed `output/adds/adds_plan.html` apart from each other: a design review, and the `impeccable detect` scan with a headless browser. The score was 21/40 (Acceptable), with 1 P0 and 2 P1 issues. The snapshot is in `.impeccable/critique/`.

## Owner decisions

- The adds page stays on GitHub Pages. The owner considered a Claude Dashboard artifact and did not choose it, because a Claude session must republish a dashboard each week.
- The plans table keeps the three plan rows as alternatives. The page does not pick one recommended plan, and the planner does not combine the rows.
- The redesign fixes all 5 priority issues of the critique. The owner asked to file them as GitHub issues. This is an exception to the owner decision of 2026-10-27 to file no new issues until the open ones are done.

## Issues filed

| Issue | Priority | Label | Summary |
| --- | --- | --- | --- |
| #114 | P0 | ready-for-agent | Show the roster spot and the add day of each plan row, and mark rows that use the same spot |
| #115 | P1 | ready-for-agent | Fix the text contrast that fails WCAG AA, with the "W" badge selector bug |
| #116 | P1 | ready-for-agent | Make the free-agent sort and filters work with a keyboard and a screen reader |
| #117 | P2 | ready-for-human | One shared token source and a new visual identity for the home page, the nav and the adds page |
| #118 | P2 | ready-for-agent | Move the run diagnostics into Run time, put the key above the table, add an empty state |

#117 needs the owner for the palette and the type pairing. It refers to `PRODUCT.md` and `DESIGN.md`, so those files must be on `main` before a build starts.
