# Schedule map of 2026-11-04

On 2026-11-04, the chief of staff ran a design grilling session about the adds planner page. The owner made three decisions and set one next step. This page records them. Nothing on this page is built. Main was at `mccomark21/fantasy-hoops-lab@ae2ccdd`.

## Owner decisions (2026-11-04)

1. The redesign has two outputs from one data source. The first output is the interactive adds page for the owner. The second output is a fixed image that a GitHub workflow posts to Bluesky each Monday. The owner will build that workflow. This decision resumes the Bluesky posts plan, which the owner paused on 2026-10-26. See [Bluesky streaming posts](bluesky-streaming-posts.md).
2. The Monday image tells the schedule story. The image is a "schedule map": it shows which NBA teams play on which days, and it is not specific to one fantasy team. The map puts weight on light nights, the days when few teams play. The adds page will reuse the same map, with the owner's roster on top. The owner rejected two other stories for the image: a player story and a personal team story.
3. "Art meets analytics" becomes a principle in `PRODUCT.md` and a new scoped "Poster" mode in `DESIGN.md`. The Poster mode is for hero graphics and shareable images only. The Box Score rules stay for tables and working UI. The schedule map is the first use of the Poster mode. The owner chose this option over two others: replace the site-wide North Star, or evolve it. On 2026-11-04, nobody had changed `PRODUCT.md` or `DESIGN.md`.

## Next step (2026-11-04)

An agent makes a compare page at `.impeccable/review/schedule-map-compare.html`. The page shows four concepts for the schedule map, so the owner can pick a direction:

1. Dot timetable.
2. Tiered type poster.
3. Night skyline.
4. Transit map.

## Related pages

- [Bluesky streaming posts](bluesky-streaming-posts.md): the plan of 2026-10-26 for weekly streaming images on Bluesky, paused the same day.
- [Site redesign of 2026-10-27](decision-site-redesign-2026-10-27.md): the Impeccable setup and the first critique of the adds page.
- [Team plan of 2026-10-28](team-plan-2026-10-28.md): the owner decision to recommend teams and positions for the stream spots, not players.
