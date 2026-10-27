# Bluesky streaming posts

On 2026-10-26, the owner gave an idea: a scheduled job that turns streaming advice into images and posts them to Bluesky. The same day, agents did a first feasibility study, a check of sources that need no login, a prototype of an availability estimate, and a study of the platform defaults. This page records all of it. Nothing on this page is built.

Code facts on this page are as of `mccomark21/fantasy-hoops-lab@969b1fa`.

The prototype scripts and the sample card of 2026-10-26 were throwaway files in a session scratchpad. They are not in the repo. The numbers below come from the agent reports of that day.

## The idea and the owner decisions

The owner prefers free GitHub Actions to run the job. AWS is also available.

Owner decisions on 2026-10-26:

| Question | Decision |
|---|---|
| Audience | A general audience, not only the owner's league. |
| "Available" | A player under 50% rostered. Later the same day, the owner asked for our own estimate instead of the ESPN `percentOwned` value. |
| Category build | The owner's punt build only. |
| Cadence | Weekly, on Monday. |

Open on 2026-10-26: the owner did not answer the terms question. The ESPN terms bar automated access. The Sleeper projections come from Rotowire. One option is to post ranks only and credit the sources.

## First feasibility study

1. The Yahoo login blocks a cloud runner. `src/fantasyhoops/adds/session.py` opens a visible Edge profile (`headless=False`, `channel="msedge"`). [ADR 0001](../adr/0001-playwright-for-league-data.md) records that Yahoo blocked an automated sign-in.
2. The repo is private. A private repo gets 2,000 GitHub Actions minutes each month on the free plan.
3. Bluesky facts from the agent: the `atproto` Python library can post. A post holds up to 4 images. Keep each image under 1 MB. Each image takes alt text. Post text holds 300 graphemes.
4. The agent made a sample card: a Playwright screenshot of the plans table, 1080 px wide, 105 KB. The chief of staff judged it readable.

Unverified: the agent cited `bsky.network/docs` URLs for the Bluesky facts. The Bluesky docs are usually at https://docs.bsky.app. Nobody checked the facts against that site.

## Sources that need no login

An agent made live GET requests on 2026-10-26.

| Source | What it gave | Notes |
|---|---|---|
| ESPN fantasy API, `kona_player_info` view | `percentOwned`, per-game lines, 7, 15 and 30-day splits. 1,098 players with the `x-fantasy-filter` header. | Undocumented. |
| Sleeper per-date projections, `https://api.sleeper.com/projections/nba/2026/{week}` | Projections for each date. | Undocumented. The data comes from Rotowire. |
| Sleeper trending adds | The players with the most adds. | |
| ESPN schedule | The game schedule. | `src/fantasyhoops/fetch/espn.py` already reads it. |
| Yahoo Fantasy API | HTTP 401. | Needs OAuth. |

Terms:

- The Sleeper API docs say the API is "free for non-commercial use": https://docs.sleeper.com. The wiki writer added this URL. The study did not give it.
- The Disney Terms of Use, section 2.B(x), bar access by automated means: https://disneytermsofuse.com. The wiki writer added this URL. The study did not give it. The agent did not verify that espn.com links to these terms.

## Own availability estimate (prototype)

The agent built a throwaway estimate of which players are available. It ranked players by season value with the owner's punt weights, plus 0.2 times the recent value. It called a player "available" when the player's rank was above a cutoff K. It compared the result with ESPN `percentOwned` under 50%, over a contested pool of 305 players.

| Cutoff K | Precision | Recall |
|---|---|---|
| 110 | 0.918 | 0.952 |
| 156 | 0.98 | 0.78 |

Other results:

- The Yahoo preseason ADP helped a little.
- Overrides for stash players and for trends did not help. The trend works as a "hot" tag.
- Misses of two kinds:
  1. Big-name scorers that the punt weights rank low, for example Mikal Bridges (86% rostered) and DeMar DeRozan (71%).
  2. Players that the projection likes but the public does not roster.
- In the owner's 14-team league, the best free agents sat at our ranks 110 to 150.

## Platform defaults

An agent read the help pages of Yahoo and ESPN on 2026-10-26.

1. The Yahoo and ESPN classic defaults both have 13 active roster slots: 10 starters and 3 bench.
2. The default league size is 10 teams on both. On Yahoo, private and prize leagues default to 12 teams.
3. The default scoring is head-to-head points on both. ESPN calls points the "most commonly used" format.
4. The ESPN default category list has 8 categories.
5. The cutoff from the slot count is 130 (10 teams x 13) to 156 (12 teams x 13).
6. Remove OUT and IL players before the cut.
7. No official data gives the share of leagues for each league size.

Sources:

- https://help.yahoo.com/kb/SLN6919.html
- https://help.yahoo.com/kb/SLN37162.html
- https://www.espn.com/nba/story/_/id/20800285
- https://support.espn.com/hc/en-us/articles/4669578914324-Scoring-Format
- https://support.espn.com/hc/en-us/articles/360004868351-Fantasy-Basketball

Not verified: the defaults of Sleeper, Fantrax and CBS.

## Open point

On 2026-10-26, the chief of staff recorded this point. The prototype's best cutoff, K = 110, is below the slot count of 130 to 156. A possible cause: the punt value ranks players in a different order from how the public rosters them. A general rank for the availability step, such as points or 9-category value plus ADP, may move the best K toward 130. Nobody tested this.

Related: [ADR 0001](../adr/0001-playwright-for-league-data.md), [Yahoo reads study](yahoo-reads-study.md).
