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

Superseded in part later on 2026-11-04: copies of the compare page and its script are now in `.impeccable/mocks/schedule-skyline/`. See [Prototype files (2026-11-04)](#prototype-files-2026-11-04).

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

Superseded in part later on 2026-11-04: in v6, the owner also removed the top-left kicker. The year "2026" is now in the small title line. See [Schedule Skyline v6 and the build plan (2026-11-04)](#schedule-skyline-v6-and-the-build-plan-2026-11-04).

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

   Clarified later on 2026-11-04: a no-game day counts as a light night in this rule. See [Phone rule and post images (2026-11-04)](#phone-rule-and-post-images-2026-11-04).
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

Superseded in part later on 2026-11-04: item 3 was a misreading by the assistant. The owner wanted blue only on the day column of the anchor night, not a band across the whole row. See [Schedule Skyline v6 and the build plan (2026-11-04)](#schedule-skyline-v6-and-the-build-plan-2026-11-04).

### Candidate Poster-mode rules (2026-11-04)

These rules are candidates for the Poster mode in `DESIGN.md`. On 2026-11-04, nobody had written them in `DESIGN.md`.

1. The hero fills its frame. It scales to the data, not to the theoretical maximum.
2. Ink and words go to what is scarce.
3. Team colors go on team chips only.

## Schedule Skyline v6 and the build plan (2026-11-04)

On 2026-11-04, the owner reviewed v6 of the poster. The owner said: "I love the graphic". The owner approved the v6 graphic.

### Name and title (2026-11-04)

1. The owner chose the name "Schedule Skyline" from 10 options.
2. The title is "Schedule Skyline" in large type. Below it, "Week N · 2026" is in small type.

### v6 changes (2026-11-04)

1. Anchor column: a semi-transparent blue stripe covers the day column of the anchor night only. This change corrects the v5 band across the whole row.
2. Ladder: the leg blocks are white on a grey calendar grid.
3. Skyline unit: the skyline now counts games per night, not teams. In v5, the 6-game line was drawn at 12 teams.
4. Skyline line: the page scales the poster to about 0.45x. Thus the thin line drew under 1 px and did not show. The line is now 1.5 px with a paper halo. The pixel check `check_line.py` passes 70 of 70 cells.
5. No-game days: a darker neutral grey hatch with the text "NO NBA GAMES". A no-game day is never blue.
6. Zero-gain rungs: these rungs stay dimmed with the text "+0 · a Nth add gains nothing".
7. Gain mark: a "+1" tag replaces the gain ring. The owner found the ring unclear.

### Items the owner removed in v6 (2026-11-04)

- The footer.
- The week-type stamp. The owner said: "I'm not even defining it on the page".
- The top-left kicker.

The week type still drives the layout internally. See [Week types (2026-11-04)](#week-types-2026-11-04).

### Build decisions (2026-11-04)

1. On `adds_plan.html`, the Skyline replaces only the team-plan grid. The other blocks stay.
2. The ladder on the page uses the owner's roster through `team_plan`.
3. A click on a leg opens the filtered Free agents view.
4. One question is open: how one rung shows several stream spots. A sample comes first, before the build.
5. The Bluesky image stays team-agnostic.
6. A GitHub Actions job runs each Monday. It does not use AWS. It posts a 1080x1350 PNG to Bluesky.

   Superseded later on 2026-11-04: the post has 2 images, not one 1080x1350 image. See [Phone rule and post images (2026-11-04)](#phone-rule-and-post-images-2026-11-04).
7. The post text is short. It has `#FantasyBasketball`, a line about what Schedule Skyline is, and the dates.
8. The job does a dry run first.
9. A GitHub secret holds the Bluesky app password.

### Follow-up: data source credit (2026-11-04)

This follow-up is not a GitHub issue. The owner's rule of 2026-10-27 says: no new issues until the open issues are done.

1. The credit line went away with the footer. Thus the poster names no data source.
2. The prototype uses ESPN's schedule.
3. The Bluesky decision of 2026-10-26 said: inputs must come from sources whose terms allow automated use. See [Bluesky streaming posts](bluesky-streaming-posts.md).
4. On 2026-11-04, the owner chose not to block on this point.
5. Revisit this point before real posting runs for a long time.

### Prototype files (2026-11-04)

The prototype files are in `.impeccable/mocks/schedule-skyline/`. They are not committed.

- `schedule-map-compare.html`: the compare page.
- `schedule_map.py`: the prototype script.
- `check_line.py`: the pixel check for the skyline line.

### Lessons (2026-11-04)

1. Scale the hero to the data, not to the theoretical maximum.
2. When the page scales the poster, measure visibility. Do not judge it by eye.
3. Use one unit, games, in labels, rule lines and classifiers.

## Phone rule and post images (2026-11-04)

Later on 2026-11-04, the owner answered three open questions (Q15-Q17).

### Q15: the Bluesky post has 2 images (2026-11-04)

1. "For now", the Bluesky post splits into 2 images. Image 1 is the skyline. Image 2 is the ladder.
2. Each image is 1080x1350.
3. All text must be 11 px or more at a 390 px display width. On a 1080 px image, this is about 30 px or more.
4. Evidence: in the PNG export test, the text of the single v6 poster measured 4-9 px at 390 px.
5. This decision supersedes the "one 1080x1350 image" claim in [Build decisions (2026-11-04)](#build-decisions-2026-11-04).
6. The phone layout of the adds page is a separate question. On 2026-11-04, it is still open. On 2026-11-05, the owner proposed a transposed layout. See [Transposed phone layout (2026-11-05)](#transposed-phone-layout-2026-11-05).

### Q16: Poster mode inherits the site chart rules (2026-11-04)

Poster mode inherits the site chart rules. These named exceptions apply:

- Team chips.
- The calendar grid.
- The mark-blue accents for the anchor.
- The "+1" tags.
- The light-night line.

### Q17: no-game days in the dead-day rule (2026-11-04)

1. In the dead-day rule, a no-game day counts toward "3 or more light nights in a row".
2. No-game days stay visually separate. They keep the grey hatch.

### Issue updates (2026-11-04)

1. #235: the renderer draws the skyline panel and the ladder panel as separate 1080x1350 images for the post, and the combined layout for the page.
2. #236: the phone layout of the page is still open. The sample must include a phone proposal for the owner.
3. #237: the export makes 2 PNGs and the post text. Each PNG is under 1 MB. A test measures the 11 px at 390 px rule.
4. #238: the post attaches the 2 images in order, each with its own alt text.

### Merges and an open gap (2026-11-04)

1. PR #239 (closes #233) merged as `1cf0ee7`. PR #240 (closes #234) merged as `5825fda`.
2. Open gap, found by the merger: the v6 game dots use the `mark` ink. As of `5825fda`, the Poster mode exception list in DESIGN.md does not name the dots, so the dots break the chart rules. Do this before #235 starts: add the dots to the exception list, or draw them in the text ink. The owner has not decided.

   Decided on 2026-11-05: the owner chose to add the game dots to the Poster mode exception list in DESIGN.md. The dots keep the `mark` ink of v6. #235 makes this DESIGN.md change.

## Transposed phone layout (2026-11-05)

1. On 2026-11-05, the owner proposed a transposed phone layout for the adds page. The skyline and the ladder read top to bottom (Mon at the top, Sun at the bottom). Each panel fits one phone screen. Only desktop keeps both panels horizontal, together on one screen.
2. The chief of staff agreed and noted: keep equal row heights in the two panels so that the days align while you scroll, use 3-letter team codes in chips, and check chip room in a sample.
3. The owner asked that the sample also show the transposed panels as the 2 Bluesky post images (1080x1350). The approved post design (v6, 2 images) does not change unless the owner approves after the sample.
4. The phone layout stays in the scope of #236. No new issue.
5. The #235 builder got a note: keep the day-axis geometry in one place, so that a later orientation option is a small change. #235 does not build the transposed layout.
6. Sample file: `.impeccable/review/236-phone-sample.html` (untracked).
7. Sample result of 2026-11-05 (agent report, measured in headless Edge): the smallest text is 11 px at 390 px in all 20 images. No overlaps remain after 2 fixes. On the phone screens all chips fit, with rows about 89 px tall. In the post images, rows are about 51 px tall at 390 px. One leg (post A, rung 4, Thu) shows 2 chips plus "+2". The skyline post image has a large empty top band. The agent recommended to keep the v6 2-image post and use the transposed layout on the phone only. The owner has not decided. Script: `.impeccable/mocks/schedule-skyline/transposed.py` (untracked).

## PR #241 decisions (2026-11-05)

PR #241 (closes #235) opened at head `edbf6d4`. The reviewer found 1 blocker. On 2026-11-05, the owner decided these points:

1. Post header rows: accepted. In the post images, the rung totals go in a header row above each rung, the line label goes in a key under the title, and the post line is 4 px wide. The cause is the 30 px phone rule.
2. RE-PLAN triangles: left out. A RE-PLAN rung shows only the RE-PLAN tag.
3. Orientation: the top-to-bottom (transposed) layout is used on the phone page AND in the 2 Bluesky post images. The owner did not take the sample agent's advice to keep v6 for the post. This supersedes Q15 item 1 of [Phone rule and post images](#phone-rule-and-post-images-2026-11-04) as to the layout inside each image. There are still 2 images, each 1080x1350.
4. Build place: PR #241 adds the transposed layout to the one shared renderer before the merge, and fixes the 3 post problems of the sample (rows about 51 px tall, a leg that drops chips, the empty top band). #236 and #237 then use it.
5. Blue marks (the blocker): the 5 extra `mark` marks of v6 (light-night skyline blocks, light-night counts, light-night day heads, rung gain text, line key text) go into the Poster mode exception list in DESIGN.md. A test must fail when the renderer uses `mark` on a mark that is not in the list.

6. Owner look at the compare page of head `a790af6` (2026-11-05): "they look great", except that in some views the no-game hatch is drawn behind the legs. It must run over them. The owner said this happened "again". The builder must fix it in all layouts and add a test of the draw order.
7. The 2 optional nits of the re-review are fixed before the merge (the mark-role check reads all SVG shape types and checks the dark theme).

8. Head `c5c76d5` fixed the hatch (draw-order test and a Chromium hit-test) and the 2 nits. The owner approved the compare page ("looks great now"). PR #241 merged as `f438cad` on 2026-11-05 and closed #235. Gap noted by the merger: the last reviewer pass was at `a790af6`; the commits after it had owner approval but no second review.
9. On 2026-11-05, #236 and #237 started at the same time in separate worktrees.

10. PR #242 (for #237) opened at head `67cc7f9`. On 2026-11-05, the owner decided: the post title shows dates (for example "Nov 9–15"), not a week number; the adds page shows the owner's Yahoo week number. The chief of staff confirmed that on a Monday the default week is the week that starts that day. Open point: with 7-day weeks from 2026-10-19, Mar 8 is week 21, but `config.toml` names it wk19, so the Yahoo calendar has longer weeks that the repo does not know yet.

11. Later on 2026-11-05, the owner asked to tag both post images with "Mahhhk Draft" and to add "#MahhhkDraft" to the post text. This supersedes "no footer, no credit line" of #235 only for this one tag, and only in the post images. The default placement is a small sign-off in a bottom corner, in the text ink; the owner sees it on the #237 review page.

Lesson (2026-11-05): the exception list was written from the v6 description, not from the v6 drawing. The same gap came up twice (the game dots, then these 5 marks). A test that ties the list to the code stops a third time.

## Related pages

- [Bluesky streaming posts](bluesky-streaming-posts.md): the plan of 2026-10-26 for weekly streaming images on Bluesky, paused the same day.
- [Site redesign of 2026-10-27](decision-site-redesign-2026-10-27.md): the Impeccable setup and the first critique of the adds page.
- [Team plan of 2026-10-28](team-plan-2026-10-28.md): the owner decision to recommend teams and positions for the stream spots, not players.
