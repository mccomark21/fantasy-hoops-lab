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

Superseded in part later on 2026-11-04: a leg no longer lists all the teams that fit it. The poster names only what is scarce. See [Skyline + ladder poster, v2-v5 (2026-11-04)](#skyline--ladder-poster-v2-v5-2026-11-04).

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

Superseded in part later on 2026-11-04: weak point 1 no longer applies. The rung rule is now "nested when free". See [Skyline + ladder poster, v2-v5 (2026-11-04)](#skyline--ladder-poster-v2-v5-2026-11-04).

### Notes (2026-11-04)

- Data: on 2026-11-04, `data/schedule.csv` had NBA Cup knockout games with no schedule for the weeks of Nov 30 and Dec 7. A Monday job must handle these weeks.
- Reuse: `team_plan` in `src/fantasyhoops/adds/team_plan.py` (line 106 at `ae2ccdd`) already searches chained adds per stream spot for the owner's roster.

## Skyline + ladder poster, v2-v5 (2026-11-04)

On 2026-11-04, the owner reviewed versions v2 to v5 of the poster on the compare page `.impeccable/review/schedule-map-compare.html`. The compare page is not committed. Its script is in a session scratchpad.

### Layout and rung rule (2026-11-04)

1. The owner chose a hybrid. The night skyline is on top. The add ladder is below. The day columns of the two parts align.
2. The rung rule is "nested when free" (concept 7C). Each rung keeps the legs of the rung above it and splits one leg. If that split loses games, the rung shows the best split instead, with a RE-PLAN tag.
3. On weeks A, B and C, all rung rules gave the same result.
4. On week D (Nov 9-15), the nested rule lost 1 game on rung 4.

### Items the owner removed (2026-11-04)

- The computed headline. The owner said: "the takeaway must come from the visual".
- The label of the rung rule.
- The big date line. The year "2026" went into the top-left kicker.
- The method note "One open spot, every day. Leg = days one team holds the spot."
- The label "Teams that play each night".

The owner also had the gap between the totals column and the chart made smaller.

### Ladder and skyline scale (v3, 2026-11-04)

1. In v3, the ladder became a week calendar.
2. The skyline scale was fixed at 30 teams. This scale wasted space.
3. The owner challenged the fixed scale. The skyline now fits the busiest night of the week. Thus bar heights differ from one week to the next.

### Owner principle: name only what is scarce (2026-11-04)

1. Long team lists add no value. The poster writes "N teams to choose from" instead of the list.
2. The key insight of a week is a leg with low volume, for example a Thursday with 2 games. The owner plans around that leg.
3. The poster always draws a back-to-back as a line between dots. The poster names a back-to-back only when a leg depends on one that 5 or fewer teams have.

### Week types (2026-11-04)

The poster checks the week types in this order. The first match sets the type.

1. Dead-day: 2 or more empty days in a row, or 3 or more light nights in a row.
2. Anchor: a night with 4 or fewer games, and a leg with 5 or fewer teams depends on that night.
3. Heavy-team: a few teams play more games than all other teams, and the 1-add rung depends on them.
4. Stream every day: all other weeks.

The test weeks have these types:

| Week | Dates | Type |
| --- | --- | --- |
| A | Nov 2-8 | Anchor |
| B | Feb 15-21 | Dead-day |
| C | Jan 11-17 | Heavy-team (DEN 5) |
| D | Nov 9-15 | Anchor |
| E | Feb 8-14 2027 | Heavy-team (POR 5) |

On 2026-11-04, no test week has the type "stream every day".

### Team colors and rung bands (v5, 2026-11-04)

1. Team abbreviations are chips in the team's primary color. The chip text passes a 4.5:1 contrast ratio.
2. The team chips are a deliberate exception to the DESIGN.md rule "Ink Only". The exception applies to team identity only.
3. Each rung is one light-blue band across the whole row. White dividers separate the legs. The anchor night has a deeper tint.
4. The owner rejected dark-blue event blocks.

Known weak point on 2026-11-04: many team primary colors are navy or red.

### Candidate Poster-mode rules (2026-11-04)

These rules are candidates for the Poster mode in `DESIGN.md`. On 2026-11-04, nobody had written them in `DESIGN.md`.

1. The hero fills its frame. It scales to the data, not to the theoretical maximum.
2. Ink and words go to what is scarce.
3. Team colors go on team chips only.

## Related pages

- [Bluesky streaming posts](bluesky-streaming-posts.md): the plan of 2026-10-26 for weekly streaming images on Bluesky, paused the same day.
- [Site redesign of 2026-10-27](decision-site-redesign-2026-10-27.md): the Impeccable setup and the first critique of the adds page.
- [Team plan of 2026-10-28](team-plan-2026-10-28.md): the owner decision to recommend teams and positions for the stream spots, not players.
