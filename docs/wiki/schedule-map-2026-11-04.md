# Schedule map of 2026-11-04

On 2026-11-04, the chief of staff ran a design grilling session about the adds planner page. The owner made three decisions and set one next step. This page records them. Nothing on this page is built. Main was at `mccomark21/fantasy-hoops-lab@ae2ccdd`.

## Owner decisions (2026-11-04)

1. The redesign has two outputs from one data source. The first output is the interactive adds page for the owner. The second output is a fixed image that a GitHub workflow posts to Bluesky each Monday. The owner will build that workflow. This decision resumes the Bluesky posts plan, which the owner paused on 2026-10-26. See [Bluesky streaming posts](bluesky-streaming-posts.md).
2. The Monday image tells the schedule story. The image is a "schedule map": it shows which NBA teams play on which days, and it is not specific to one fantasy team. The map puts weight on light nights, the days when few teams play. The adds page will reuse the same map, with the owner's roster on top. The owner rejected two other stories for the image: a player story and a personal team story.
3. "Art meets analytics" becomes a principle in `PRODUCT.md` and a new scoped "Poster" mode in `DESIGN.md`. The Poster mode is for hero graphics and shareable images only. The Box Score rules stay for tables and working UI. The schedule map is the first use of the Poster mode. The owner chose this option over two others: replace the site-wide North Star, or evolve it. On 2026-11-04, nobody had changed `PRODUCT.md` or `DESIGN.md`.

Superseded in part later on 2026-11-04: the hero story of the image is now a ladder of add patterns, not "which teams play the most". The map stays team-agnostic. See [Ladder of add patterns (2026-11-04)](#ladder-of-add-patterns-2026-11-04).

## Next step (2026-11-04)

An agent makes a compare page at `.impeccable/review/schedule-map-compare.html`. The page shows four concepts for the schedule map, so the owner can pick a direction:

1. Dot timetable.
2. Tiered type poster.
3. Night skyline.
4. Transit map.

Superseded later on 2026-11-04: the owner saw concepts 1-5 and said they were "too simple". See [Ladder of add patterns (2026-11-04)](#ladder-of-add-patterns-2026-11-04).

## Ladder of add patterns (2026-11-04)

On 2026-11-04, the compare page `.impeccable/review/schedule-map-compare.html` showed concepts 1-5. The page had a week toggle with three weeks:

- A: Nov 2-8.
- B: Feb 15-21, the All-Star week, with 5 light nights.
- C: Jan 11-17, the week with the widest spread of game counts.

The owner said the concepts were "too simple". The owner wants ideal patterns: how one person gets the most out of 1 to 4 adds through a single stream roster spot. This story replaces "which teams play the most" as the hero story of the image. The schedule map stays team-agnostic.

### Owner decisions (2026-11-04)

1. "Best" means the most games. Light-night games break a tie. A light night is a day with 6 or fewer NBA games. The owner rejected weighted games and a two-lane version for the public image.
2. The poster shows a ladder of patterns for 1, 2, 3 and 4 adds. Each leg is a day window that one team holds. Each leg lists the teams that fit it. The poster shows the gain from each extra add. The owner rejected a poster that names one specific chain.

### Prototype: concept 6 "Ladder" (2026-11-04)

On 2026-11-04, concept 6 "Ladder" gave these game totals for 1, 2, 3 and 4 adds:

| Week | 1 add | 2 adds | 3 adds | 4 adds |
| --- | --- | --- | --- | --- |
| A | 4 | 5 | 6 | 6 |
| B | 3 | 3 | 4 | 4 |
| C | 5 | 5 | 6 | 7 |

In week B, the 2nd add gains only a light-night game. The prototype has two known weak points on 2026-11-04:

1. Each rung is an independent optimum. Thus the legs can change order or teams from one rung to the next.
2. The dots follow the first tied team in alphabetical order.

### Notes (2026-11-04)

- Data: on 2026-11-04, `data/schedule.csv` had NBA Cup knockout games with no schedule for the weeks of Nov 30 and Dec 7. A Monday job must handle these weeks.
- Reuse: `team_plan` in `src/fantasyhoops/adds/team_plan.py` (line 106 at `ae2ccdd`) already searches chained adds per stream spot for the owner's roster.

## Related pages

- [Bluesky streaming posts](bluesky-streaming-posts.md): the plan of 2026-10-26 for weekly streaming images on Bluesky, paused the same day.
- [Site redesign of 2026-10-27](decision-site-redesign-2026-10-27.md): the Impeccable setup and the first critique of the adds page.
- [Team plan of 2026-10-28](team-plan-2026-10-28.md): the owner decision to recommend teams and positions for the stream spots, not players.
