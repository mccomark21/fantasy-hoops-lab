# Yahoo reads study

On 2026-10-26, the owner asked three agents to study the Yahoo reads step of a planning run. The [Planning run timings](planning-run-timings.md) page shows that this step took the most time of all steps. Each agent studied one question: the page depth, the two views, and the page loads.

Code facts on this page are as of `mccomark21/fantasy-hoops-lab@9b00797`. The constants `MAX_PAGES` and `MARKET_PAGES` are in `src/fantasyhoops/adds/plan.py`.

## Page depth

Source: one live read on 2026-10-26 and an offline replay of that read.

1. Each team-filtered free-agent list fit on one page. The lists held 15 to 23 free agents, 151 in total over 8 teams.
2. `MAX_PAGES = 10` is an upper limit. In this read, the limit never applied.
3. One run read 33 pages:

   | Pages | Count |
   |---|---|
   | Team-filtered lists (8 teams x 2 views) | 16 |
   | Market lists (6 x 2) | 12 |
   | Waiver lists | 2 |
   | Team page | 1 |
   | Matchup page | 1 |
   | Trends page | 1 |
   | Total | 33 |

4. The read phase took 29.0 s. Of that time, 22.9 s were waits for Yahoo pages: about 0.62 s for each list page, 2.6 s for the matchup page and 1.2 s for the team page.
5. About 6 s went to page handling outside the waits. The code parses each page at least two times.
6. The agent cut the reads to the first N pages, for N = 1, 2, 3, 5 and 10. No cut changed a plan.
7. The 15 best market values came from market page 3 or earlier. One exception: a player who was also on a team page appeared on market page 5.

Suggestion of the agent: change `MARKET_PAGES` from 6 to 3. Add a guard that stops the market read when a page has no player above the 15th-best value. The agent estimated a saving of about 3.7 s.

## Two views

The run reads each free-agent list in two views: the projected view and the recent view (`S_AL14`). The recent view feeds these parts of a plan:

- The blend of the two views, with weight w = games/14. The week of 2026-10-26, w was at most about 0.29.
- The option order and the tiebreaks.
- The aggressive matchup value.
- The Recent column of the page.

An agent read the code and concluded that a projected-only read would not change the started games or the adds of this week. Nobody tested this conclusion.

Ideas from the agent:

1. Keep a cache of the recent pass for each day.
2. Add a setting that skips the recent pass while w is small.
3. Build the recent line from the ESPN box scores. `src/fantasyhoops/fetch/rotation.py` downloads these box scores, but it keeps only the minutes. The agent estimated the effort as M. This idea needs name matching between ESPN and Yahoo.

## Page loads

1. One run opens one Edge window with one tab. The run loads the pages one after the other.
2. Each page is about 3 MB and loads about 60 third-party scripts.

Ideas from the agent. Nobody measured the saving of any of them.

- Get the HTML without a render, with `context.request`. The team page still needs the browser.
- Read with 3 or 4 tabs in parallel. The rate limits of Yahoo are not known.
- Block images and ads.
- Keep a cache for the same day.
- Look at the optional wait of up to 2 s for the score table (`src/fantasyhoops/adds/session.py:88`, `SCORE_WAIT_SECONDS`).

## Other observation

On 2026-10-26, `data/rotation_log.csv` held only rows from 2026-10-20.

## Correction

On 2026-10-26, the chief of staff told the owner that a run reads "up to 10 free-agent pages for each of several teams". The measurement of the same day showed one page for each team. `MAX_PAGES = 10` is only the upper limit.

Related: [Planning run timings](planning-run-timings.md).
