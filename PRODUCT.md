# Product

## Register

product

## Users

One owner manages one team in a 14-team Yahoo head-to-head league. The owner punts FG%, FT% and TO.

- The owner uses a desktop most of the time, to plan the adds for the week.
- When the owner is away from the desk, the owner uses a phone to look at the plan and do the adds.
- The site is public on GitHub Pages, but the pages are for the owner. The pages do not have to explain themselves to people who do not know them.

The job: make the add, drop and start decisions for this week quickly, and trust the numbers behind them.

## Product Purpose

The site publishes the output of the analysis tools as static pages: the weekly adds plan, the draft board and the keeper report. The home page links to each tool.

Success: the owner opens the adds plan and finds the decision for the week (who to add, on which day) in seconds. The page also shows the data that supports the decision.

The first surfaces to redesign are the home page with the shared site nav (`core/publish.py`) and the adds plan (`adds/page.py`). The draft pages follow the same system later.

## Brand Personality

Sharp, analytical. The site is like a scout's notebook or a model sheet: the numbers come first, and each mark has a purpose. The tone is plain and exact. The site does not use hype or decoration.

References:

- Cleaning the Glass: a quiet, serious stats product for people who know the game, with dense numbers and a clear hierarchy.
- The Athletic and FiveThirtyEight: editorial data graphics where the typography and the charts carry the identity.

## Anti-references

- Yahoo and ESPN fantasy apps: clutter, ads, many competing badges and too many colors.
- Generic SaaS dashboards: rounded card grids, hero metrics with big numbers and small labels, and gradient accents.

## Design Principles

1. **Decision first.** Each page leads with the decision. The supporting data comes after the decision, and is easy to find.
2. **Numbers are the interface.** Tables and figures are the main content, not decoration. Make them scannable: aligned, tabular and clearly ranked.
3. **One system.** All pages use the same tokens, type, nav and table conventions, so a new tool page looks like part of the site.
4. **Earn each mark.** Color, weight and borders carry meaning (good, bad, selected, open). Remove a mark that does not carry meaning.
5. **Desktop depth, phone reach.** Design for the desktop first. The decision for the week must also be clear and usable on a phone.

## Accessibility & Inclusion

WCAG 2.2 AA baseline: text contrast at least 4.5:1, keyboard access for all controls, and visible focus. Good and bad states must not use color only. Use a sign, a label or a shape too. All motion must obey `prefers-reduced-motion`.
