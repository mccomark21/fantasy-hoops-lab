# Weekly adds planner

Status: built. This guide records the design and how the planner works. The code is in `src/fantasyhoops/adds/`. The planner reads your team, finds the open starting slots of each day and ranks the NBA teams by the open days that they cover. Then it makes the team plan: the adds of the stream spots as NBA teams and open slots, not as players (#140). The planner writes the plan page in `output/adds/` and publishes it at `/adds/`. The page shows the team plan as a week grid, the matchup weights, the warnings and a free-agent table with filters. You pick the player in the free-agent table. Each run saves the adds of its plan in the week file, so that the page can show the past days of the week (see [Week file](#week-file)). The terminal prints a short summary (see [Terminal summary](#terminal-summary)). The planner times each step of the run. The page shows the times in the Run time section, and the run appends them to `output/adds/timings.csv`.

The planner shows how to use your adds in the current fantasy week. For the terms that all tools share, see the [glossary](../glossary.md).

## Table of contents

- [Goal](#goal)
- [Usage](#usage)
- [The team plan](#the-team-plan)
- [Rest on back-to-backs](#rest-on-back-to-backs)
- [Value](#value)
- [The page](#the-page)
- [Home page](#home-page)
- [Core and drops](#core-and-drops)
- [Status rules](#status-rules)
- [Role up](#role-up)
- [Data](#data)
- [Configuration](#configuration)
- [Terms](#terms)
- [Decisions](#decisions)

## Goal

The team plan gets the most started games from your stream spots. If two plans have the same started games, the plan with fewer adds wins. If the adds are also the same, the plan whose last teams have more games next week wins (see [Next-week games](#next-week-games)).

Decision (2026-10-28, #140): the planner recommends NBA teams and positions, not players. The player search was slow, and the owner picks the player from the free-agent table. The planner no longer makes the schedule plan, the best plans for one roster spot, the contingency plans or the aggressive plan, and the search benchmark is gone.

A started game of a player in a stream spot who is on the rest list counts less than 1 started game on the second night of a back-to-back. See [Rest on back-to-backs](#rest-on-back-to-backs).

## Usage

```
python -m fantasyhoops.adds.plan
```

One planning run does these steps:

1. It reads your league from Yahoo.
2. It makes the team plan for the planning window.
3. It writes the adds of the plan in the week file, `output/adds/week_plan_<first day>.json` (see [Week file](#week-file)).
4. It writes the page in `output/adds/`, with the font file and its license in `output/adds/fonts/`. It appends the time of each step to `output/adds/timings.csv`.
5. It writes the home page in `output/home/` (see [Home page](#home-page)).
6. It publishes the site to GitHub Pages: the plan page at `/adds/` and the home page at `/`.

To write the page with no publish, add `--no-publish`. The run then makes no home page:

```
python -m fantasyhoops.adds.plan --no-publish
```

The links of the site menu work only on the published site. On the local file, they open folder lists.

A second run on the same day takes some pages from the same-day cache in `output/adds/cache/` (see [Data](#data)). To read each page from Yahoo, add `--no-cache`. The run then writes each page over the cached page:

```
python -m fantasyhoops.adds.plan --no-cache
```

You can run the planner on any day. Run it before the week starts for the full plan. Run it again during the week after an injury or a new free agent. Each run plans only the days that are left, with the adds that are left.

On the last day of a fantasy week, the planner plans the next week. The planning window is the whole next week, and all the adds of the weekly limit are left (5). The run writes the week file of the next week.

The planning window starts today. The team plan does not use the game times. An add for today helps only if his game has not started.

### Terminal summary

Decision (2026-10-28, #130): the terminal prints a short summary. The page shows all other results of the run. At the end of the run, the summary prints these lines in this order:

1. The page path: "Wrote the plan page: <path>".
2. One line for each add of the team plan of today and later (#140), for example "Team plan: Add 1, Thu 10/29: +SG/PF 6 teams. Starts Thu & Sat." With 5 teams or fewer, the line lists them. A plan with no add prints no line.
3. The URL after a publish, or "The run did not publish the page (--no-publish)."
4. The warnings of `value_warnings()`, one line each. The page shows the same warnings.

During the run, the terminal can also print these lines:

- The Yahoo sign-in prompts, when the saved session has expired (`adds/session.py`).
- "Warning: the waiver list shows <name> as "<cell>" with no clear day. The planner skips him." (`adds/readers.py`).
- "Warning: no role-up marks. These files are missing in data/: <files>." (`adds/role_up.py`).
- "Warning: the run did not write the page in the cache ..." (`adds/cache.py`). The run continues.
- "Wrote the home page: <path>" before the plan page, only in a run that publishes (`adds/home.py`).
- "The run did not make the home page. The error:" and the traceback, if the home page fails (`adds/home.py`).

The terminal shows no other result of the plan. Since #140, the run makes no player plan.

## The team plan

Decision (2026-10-28, #140): the team plan gives the adds of the stream spots as NBA teams and open slots. `adds/team_plan.py` makes it. The search does not use the free agents, so it is fast: on the week of 2026-10-26 (7 days, 5 open days, 3 adds), it takes about 0.01 seconds and 174 calls. The schedule search of the live run of 2026-10-26 took 6.59 seconds and 610,861 calls.

### Team-window search

1. Find the open starting slots on each day of the planning window.
2. Rank the NBA teams by the open days that they cover. A team that plays on several open days covers them with one add.
3. On each open day, in order, each stream spot keeps its player or takes a new player of a team that plays that day. A new player can fill each open slot. An add sits on the first day that he starts, so that day is also the latest add day that keeps all his started games.
4. Choose the plan with the most started games. If two plans have the same started games, the plan with fewer adds wins. If the adds are also the same, the plan with more [next-week games](#next-week-games) wins.

A holder (the player in a stream spot now) plays every game of his team until the first add to his spot. That add drops him. An Out holder has no games. The kept players fill the slots first. A new player starts only in a slot that they leave open.

Teams with the same open days are the same choice for the search. A team whose open days are all in the open days of another team is never a better choice, so the search does not try it. The search is exact.

### Slots and teams of an add

Each add of the plan gets its slots and its teams:

- **Slots:** the positions with which the new player starts on each day that he starts, and with which the other stream spots keep their starts. If each position fits, the slots are "Util" (any position). The adds of one day get their slots in order of spot, and the later add sees the slots of the earlier add.
- **Teams:** each NBA team that plays and starts on the add day, and with which the plan has the same score: the same started games, the same adds and the same next-week games. These teams fit the add equally. A team of your kept players can be in the list. The planner does not check the free agents of a team.
- **Starts:** the days that the new player starts with each team of the add. The teams of one add usually play on the same days. If they do not (a mixed add), the starts are only the days of all its teams, and a line under the grid says so.

The free-agent reads do not change: the run still reads the team lists of the best teams (`teams_to_read()`), so the free-agent table has the players of the plan.

### Week file

Decision (2026-10-28, #140): each run writes the recommended adds of the week to `output/adds/week_plan_<first day>.json` (`adds/week_file.py`), for example `output/adds/week_plan_2026-10-26.json`. There is one file for each fantasy week.

1. A run replaces the saved adds of today and the later days with its new plan. It never changes the saved adds of a past day. So a past day shows the adds that the last run on or before that day recommended for it.
2. When a later run changes a future recommendation, the file and the grid show the new add. The old future add is not kept.
3. A run with no add (for example, with no adds left) removes the saved adds of today and later.
4. Each add has its row, its add day, its slots, its teams, its start days and the mixed mark. The file also holds the days of the runs.
5. The file holds only the recommendations, not the adds that you made on Yahoo.
6. On the last day of a week, the run plans the next week and writes the file of the next week.

The row of an add is its row in the week grid. A stream spot continues the row of a past add when its holder plays for a team of the last past add of that row, because that add was likely the holder. Each other spot takes the lowest row with no past add, in order of spot.

### Next-week games

Decision (2026-10-21, #60): a player who holds a stream spot on the last day of the week can stay on the roster next week. Then that spot needs no add on the first day of next week. So the team plan counts the games next week of these players:

1. Next week is the 7 days after the last day of the week to plan. The planner does not read the dates of next week from Yahoo. So a longer week, for example the week of the All-Star break, gets only its first 7 days.
2. Each game of his NBA team next week counts, also on days with all slots full. The open slots of next week are not known yet. A second night of a back-to-back next week also counts 1 game.
3. A game next week counts `next_week_weight` (0.5) of a game this week, because injuries and role changes can occur before then.
4. A holder who is Out gets no next-week games. An empty spot also gets none.

The team plan uses the next-week games only as the last tiebreak. The planner adds a player only on a day that he starts this week. It does not add a player only for his games next week. For the last add of a spot, a team with fewer games next week does not fit the add equally, so it is not in the team list.

#### Next-week mark

Decision (2026-10-21, #76): the free-agent table of the page marks each free agent who plays on an open day early next week. The mark names the day, for example "Mon open".

1. The days are the first `next_week_open_days` (2) days after the last day of the week to plan. Next week starts on the same day as for the next-week games.
2. The open slots of these days come from the same roster as this week: your roster without the players in the stream spots. The [status rules](#status-rules) of today apply.
3. A free agent gets the mark if his NBA team plays on that day and an open slot takes one of his positions. Util takes all positions. This is the rule of the filled square.
4. A day with all slots full gives no mark.

The mark changes no value and no plan. The key above the table shows the mark. The legend in "Columns and marks" under the table names each day and its open slots.

## Rest on back-to-backs

Decision (2026-10-21, #62): a player on the rest list counts less than 1 started game on the second night of a back-to-back. All other players count each game as 1, as before.

- The rest list is the `rests_b2b` column of the `[risk] file` (`data/projection_risk.csv`), the list of the draft tools. The names match after `name_key()`. A player who is not in the file does not rest. If the file does not exist, nobody rests.
- A second night is a game of a team on the day after a game of the same team. A game on the day before the planning window counts too.
- One game of a player on the rest list on a second night counts `1 - rest_chance` started games. `[adds] rest_chance` is 0.5, so the game counts 0.5. No data gives a better value yet. With 0, the planner counts each game as 1.
- The count applies to the holders of the stream spots in the team plan. It does not change the kept players. A new player of the team plan has no name, so his games count 1.

The started games of a plan can now be a fraction, for example 6.5. The tie rules of the plan score stay in the same order. The score rounds the started games to 6 decimals, so that the same games in a different order give a tie.

On each day, the lineup puts the players with no rest risk in the open slots first.

The draft tools do not change. There, `rests_b2b` changes only the playoff game counts, never the season games or the value. `[adds] rest_chance` is separate from `[risk] rest_chance` of the auction simulator.

The free-agent table marks each second night with a small "2", for all players.

## Value

The blended value orders the free agents. It uses your 6 categories and your weights, the same formula as `core/valuation.py`, on a blended stat line:

- The projected line: Yahoo's projection for the next 7 days (from Rotowire). Rotowire updates it during the season.
- The recent line: the player's per-game averages in the last 14 days.
- Blended line = projected line, moved toward the recent line as games accumulate. The weight of the recent line = games in the last 14 days ÷ 14. A player with 7 games gets 50%.

In the first week of the season, the blended value is the projected value, because there are no recent games.

If Yahoo has no projection for a player, but he has recent games, the blended line is the recent line. It is the only stat line that the planner has for him. A player with no projection and no recent games has no value, and the free-agent table does not show him.

The planner reads each free-agent list twice: with `stat1=S_PS7` (the projection for the next 7 days, as totals) and with `stat1=S_AL14` (the averages of the last 14 days). It matches the players of the two lists by name and NBA team.

### Skip of the recent view

Early in the season, the weight w of the recent line is small, but the recent view costs almost half of the Yahoo pages of a run (#90). So the run can skip the recent view:

1. Before the recent view, the run gets the largest possible w from `data/schedule.csv`: the most games that one NBA team played from 14 days ago to today, ÷ 14. These 15 days hold the window of `S_AL14` with or without today.
2. If this w is below `recent_skip_weight` in `[adds]`, the run reads no page of the recent view.
3. Each option then has no recent value, and the blended line is the projected line. A player with no projection is not a candidate, also when he has recent games.
4. The page shows a line in the Run time section: the most games of one team, the largest possible w and the setting. Above the free-agent table, one short sentence says that Val uses the projection only (#118). The Recent column shows "—" for each player.

A player who changed teams in those days can have more games than one team. The run ignores this case. With 0.3, the run skips the recent view while no team played more than 4 games in those days.

Next to each free agent, the page also shows:

- The recent value: the value of the last-14-day line alone.
- The trend: his adds today and this week across all Yahoo leagues, from Transaction Trends. Many of these adds come from leagues that score all 9 categories. So the trend is evidence and a tiebreak, not a plan of its own.
  Transaction Trends shows one day and the 50 most added players of that day. The planner reads one page for each day of this week up to today and adds them. A player who is not on the page of a day counts 0 adds that day. A player who is on no page shows a dash. The trend is a mark only. It changes no value and no plan.

### Market value

The page shows the market value: the blended value above a replacement free agent. The replacement free agent is the free agent at rank 15 by blended value among the free agents that the run read (Out players do not count). His market value is 0. A positive market value is better than the replacement free agent.

The planner itself uses the values on the scale of the projections. A market value is the same value minus one number, so it does not change the order of the players.

### Market read

The market pages are the pages of the full free-agent list, best Yahoo rank first. They give the free agents of the teams that the run does not read. They also set the replacement value. The run reads 3 market pages at most (`MARKET_PAGES`, #92). Before #92, the limit was 6 pages.

1. The run reads the team-filtered lists in both views first.
2. Then it reads the market pages one at a time. It reads each page in both views before the guard checks it.
3. The guard stops the read after a page with no new player above the replacement value of the free agents read before that page. A player who is also on a team-filtered list or on an earlier market page is not new.
4. The guard uses the blended value. While the run skips the recent view, the blended value is the projected value.
5. With fewer than 15 free agents with a value before a page, the guard does not stop the read. The guard counts the same players as the replacement value: the players who play and have a value.

The page shows a line in the Run time section: the market pages that the run read and why the read stopped (#118). For example, "Market: 2 of 3 pages. Page 2 had no new player above the replacement value ..." or "Market: 3 of 3 pages (the limit)."

The [Yahoo reads study](../wiki/yahoo-reads-study.md) of 2026-10-26 found the 15 best market values on market page 3 or earlier. That is the evidence of one run on one day. The run never reads a market page after page 3, also when the guard does not stop the read.

The stat lines come from Yahoo. The season projections file of the draft tools gives only the category scale: the mean and the standard deviation of each category in the player pool. So the values are on the same scale as the per-game value on the draft board. A streamer usually has a value below 0, because the pool holds the drafted players.

### Matchup weights

Decision (2026-10-21, #59): the matchup weights weight the 6 categories by the state of the current matchup. Since #130 (2026-10-28), the run uses the matchup weights only for the matchup section and the Match column of the page. The team plan uses no value.

The planner reads the category totals of your team and your opponent from the score table of the matchup page. The planner finds the score table by its stat headers (PTS, REB, AST, 3PTM, ST, BLK). On 2026-10-21, after the first games, the table had no Score header (#73). The margin of a category is your total minus the total of your opponent. Each category then gets a matchup weight:

1. A margin of `close` or less (a lead or a deficit) keeps weight 1.
2. A margin of `large` or more gets weight `min_weight` (0.5).
3. Between the two, the weight goes down in a straight line.

The `close` and `large` margins in `config.toml` are for a whole week. The planner multiplies them by the share of the week that is left: the days of the planning window ÷ the days of the fantasy week. A lead of 5 3PM is close with 6 days left. With 1 day left, it is a large lead.

The matchup value of a free agent is his value with each category weight times its matchup weight, on the same category scale. A holder in a stream spot gets no matchup value. With all categories tied, all weights are 1, so the matchup value equals the blended value. On the first day of a week, and when the planner plans the next week, the totals are 0, so the weights are 1.

Example: you lead 3PM by 15 with the whole week left. The weight of 3PM goes from 0.70 to 0.35. A free agent who adds 3PM then has a lower Match value on the page. If you trail blocks by 2, blocks keep their weight.

If the matchup page has no score table, all weights are 1, and the page says so.

## The page

The page has two main sections: the team plan, and the free-agent table. Between them, the matchup section shows the total of each category for your team and your opponent, the margin and the matchup weight. The page is public, so it does not show the name of the opponent. After the free-agent table, a section lists the waiver players. The next section lists the role-up marks (see [Role up](#role-up)). Near the end of the page, the Run time section shows the time of each step of the run (see [Run time](#run-time)).

### Team plan

Decision (2026-10-28, #140): the owner approved the C3 heat sample of the week grid. `adds/grid.py` makes the section.

1. Columns: Monday to Sunday of the fantasy week, always, on a desktop and on a phone. At 390px, the 7 columns fit with no sideways scroll. Below 600px, the labels get shorter ("M" and "26" for "Mon" and "10/26").
2. Row "Games": the NBA games of the day (the rows of `data/schedule.csv` for that date, divided by 2).
3. The games of the day shade the whole column: more games, a deeper `mark` tint, from 0% to 40% of the day with the most games. A key under the grid shows the scale.
4. Rows "Add 1" and "Add 2": one row for each stream spot with an add, and 2 rows at least. An add sits in the column of its add day: "+<slots> <teams>", for example "+SG/PF SAC". With 5 teams or fewer, the cell lists them. With `[adds] team_count_at` (6) teams or more, the cell gives the count, for example "+Util 8 teams". A later add in the same row drops the player of the earlier add. The row label counts the adds of the row.
5. A band continues after each add in the same row, through each day that the new player holds the spot: up to the day before the next add in that row, or Sunday. A filled square on the band marks a day that he starts. A held day with no start shows the band only. A key under the grid shows the band with and without the square.
6. A past day is muted. Its add cells show the saved add of the [week file](#week-file) in a dashed muted cell. A past band and its squares use `lab-mute`. A past day with no saved run gets blank add cells and a line under the grid, for example "No saved plan for Mon and Tue."
7. The legend under the grid is collapsed ("How to read the plan"). The keys stay visible.

Click to filter: an add cell and a day header of a day that is not past are buttons. A click sets the filters of the free-agent table and scrolls the page to it:

- An add cell sets the day filter to the start days of the add, the position filter to its slots ("Util" clears the position filter) and the team filter to its teams.
- A day header sets the day filter to that day. It clears the position filter and the team filter.
- A line above the table names the source of the filters and links back to the plan. The clicked cell shows the selected state: stock text on a solid `mark` block. Reset filters hides the line and clears the selected state.

A past add cell is not a button. Each button has a text label. Each state of an add cell and a day header (default, hover, focus, selected, selected and hover, past) has 4.5:1 or more in both themes, and so have the bands and the squares. Page tests check this, and that each add cell and each band fits its cell at 320, 390, 768 and 1280px.

With no free-agent table (no free agents read), the cells are not buttons. When the plan has no add, a line gives the reason: no stream spots, no adds left, the week is over, or no NBA team gives a started game in an open slot.

### Free-agent table

The table shows the free agents that the run read: the free agents of the best teams of the ranking (`teams_to_read()`), and the first 3 pages (75 players) at most of the full free-agent list (see [Market read](#market-read)). It shows the 10 best players for the filters.

- Days: select one day or more. The table shows the players who play on all the selected days. Each day shows your open slots and the NBA games of that day.
- Positions: select one position or more. The table shows the players with one of the selected positions.
- Teams (#140): select one team or more. There is a chip for each team of the free agents that the run read. The table shows the players of the selected teams. With no team selected, the table shows all teams. The count line names the selected teams.
- "Only games that fill an open slot": a game counts only if an open slot of that day takes one of his positions.
- Sort: click Val, Match, Recent or Gms. Gms is the number of his games on the selected days. Sort by Gms to find the player with the most games on those days. Val then puts the players with the same games in order.
- Reset filters: the button next to the checkbox restores the defaults. No day, no position and no team is selected, the checkbox is on, and the sort is Val (#118, #140).
- No match: when no free agent matches the filters, the table hides and a message shows. With selected days, the message is "No free agent plays on all selected days." and a "Clear days" button clears the days (#118).
- Keyboard and screen reader (#116): each chip and each sort header is a button. Press Tab to go to a button, then Enter or Space. The focus stays on the button. The sorted column shows an arrow (▼) and has `aria-sort`. A screen reader reads each day chip as, for example, "Tue 10/27, 5 open slots, 4 NBA games", each dot as "game in an open slot" or "game", and the count line after each change.

Match is the market value with the matchup weights: the matchup value above the matchup value of a replacement free agent. Compare Val and Match to see how the matchup changes the value of a player.

A filter does not change Val or Match, because they are values per game.

A one-line key above the table shows the dots and the flags. The longer text about the columns, the role line and the next-week mark is in "Columns and marks" under the table (#118).

A filled square is a game in an open slot that he can fill. An empty square is a game with no open slot for him. A small "2" marks a game on a second night. A player with a market value of +1.5 or more gets the mark "FA?": a value this high is unusual for a free agent, so check his status. A player with a role-up mark gets the mark "UP", and his line names the absent starter. A player who fits an open slot on one of the first days of next week gets a mark such as "Mon open" (see [Next-week mark](#next-week-mark)).

### Role line

Decision (2026-10-21): the role line is a mark only. It does not change the blended value or the plan.

Each player in the free-agent table has a role line from the rotation log, for example "Min 28.0 L5, 22.0 14d (+6.0) · Starts 3/4 (Regular) · Closes 1/2 (New)":

- Min: his mean minutes in his last 5 games (L5), then his mean minutes in his games of the last 14 days (14d), then the change (L5 minus 14d).
- Starts: his starts / his games in the last 14 days. The word in parentheses is his [starter flag](#starter-flag-and-closer-flag).
- Closes: his closes / the close games of his NBA team in the last 14 days. See [close game](../glossary.md#rotation) in the glossary. A close in a blowout does not count. The word in parentheses is his [closer flag](#starter-flag-and-closer-flag).
- MIN+: the change is `minutes_rise` (4) minutes or more. The mark is next to his name.

The last 5 games are the last 5 games that he played. They can be older than 14 days. The 14 days end yesterday, because the log holds only final games. Early in the season, both windows hold the same games, so the change is 0.

#### Starter flag and closer flag

Decision (2026-10-21, #75): the owner approved this rule. The flags are marks only. They change no value and no plan. `core/role_flags.py` gives the flags, so other tools can use them.

- The starter flag uses his last `window_games` (10) games that he played.
- The closer flag uses the last `close_window` (8) close games of his current NBA team. A close game that he did not play counts as "not closed".
- The windows count games, not days, so they differ from the 14-day counts of the role line. The games end yesterday.

The check order is New, then Regular, then Inconsistent:

| Flag | Starter flag | Closer flag |
| --- | --- | --- |
| New | He started each of his last `new_games` (3) games, and fewer than half of the earlier games in the window. | He closed each of the last `new_closes` (2) close games, and fewer than half of the earlier close games in the window. |
| Regular | He started `regular_share` (70%) or more of the window. | He closed 70% or more of the window. |
| Inconsistent | He started `some_share` (20%) or more, but less than 70%. | He closed 20% or more, but less than 70%. |
| No flag | Less than 20%, or fewer than `min_games` (5) games. | Less than 20%, or fewer than `min_close_games` (4) close games. |

A player with no flag has no word after the count. The legend in "Columns and marks" under the free-agent table gives the rule with the settings of `config.toml`.

The planner links each Yahoo name to an ESPN name after `name_key()`. `data/name_overrides.csv` gives the ESPN name for a player whose names do not match. If two ESPN players have the same name, the player with games for the NBA team of the free agent wins. If neither has games for that team, the free agent gets no role line. A player who is not in the log has no role line. Without `data/rotation_log.csv`, the page has no role lines.

### Waiver players

A separate table lists the waiver players that the run read, best value first. It shows the team, the positions, the clear day, the first day that he can play for you and Val (the same market value as the free-agent table). The section is not on the page when the run read no waiver player. See [Data](#data) for the waiver rules.

### Run time

Decision (2026-10-26, #85): the planner times each step of a planning run. The owner wants faster plans, and the times show which step to change. The times change no plan.

| Step | What it times |
| --- | --- |
| schedule read | `read_schedule()` |
| season values | `season_values()` |
| Yahoo reads | The Yahoo session: your team, the matchup, the free-agent lists and Transaction Trends |
| absence read | `read_absences()` |
| value options | The values of the free agents (`value_options()`) and the role-up marks |
| team plan | The team plan (`team_plan()`, #140) |
| role read | `read_roles()` |
| home page | `build_home()`: the home page (see [Home page](#home-page)). Only a run that publishes has this step. |
| page write and publish | The page and the publish of the site |

A step that does not run has no time. For example, with no adds left, the run reads no free agent and runs no search. The rows "schedule search", "spot plans" and "contingency plans" stopped with #140.

Decision (2026-10-26, #89): the Yahoo reads step also times its sub-steps and counts the Yahoo pages of each sub-step. The rows show which part of the reads uses the time. Issues #90 to #95 check their savings in these rows.

| Sub-step | What it times |
| --- | --- |
| browser start | The start of Edge with the saved profile (`open_league()`). It opens no Yahoo page. |
| league and matchup pages | `read_league()`: your team page and 1 or 2 matchup pages |
| projected pass | `read_team_free_agents()` in the projected view: the free-agent lists of the read teams |
| recent pass | `read_team_free_agents()` in the recent view |
| market pages | `read_market_free_agents()` in both views, page by page (see [Market read](#market-read)) |
| waiver list | `read_waiver_list()` in both views |
| trends | `read_week_trends()`: Transaction Trends |

Since #129, `read_lists()` in `adds/lists.py` reads the free-agent lists and times the four sub-steps from "projected pass" to "waiver list". The functions of these four rows are in the same module. The names, the order and the pages of the rows did not change.

Since #92, the run reads the team lists in both views before the market pages, because the guard of the market read needs their blended values. The market pages and the waiver list rows each hold the pages of both views. The timers do not change the order of the reads. The sub-steps do not time the work between the reads or the close of Edge. One exception since #92: the market pages row also times the guard's values of the new players of each market page. The run reads the category scale before the Yahoo reads step and computes the values of the team-list free agents before the market pages sub-step. So the seconds of the sub-steps add to less than the seconds of the Yahoo reads.

A page is one page that `League` opens (`adds/session.py`): one page in Edge or one raw request (#108). A sign-in opens the same page again, but the page counts one time. A page from the same-day cache counts no page. The pages of the Yahoo reads are the sum of the pages of its sub-steps. A sub-step that does not run has no row. For example, with no adds left, the run reads no free agent, so only the browser start and the league and matchup pages have rows.

With the [skip of the recent view](#skip-of-the-recent-view), the recent pass row stays with 0 pages. The market pages and the waiver list rows then hold the pages of the projected view only (#90).

For the team plan step, the planner also counts the search work:

- Calls: the calls of the search function, cache hits included.
- States: the unique states (open day, players in the spots, adds left) that the search computes.

A step with no search has no counts.

Since #130 (2026-10-28), the terminal shows no step line and no progress line. The step times are in the Run time table and in `output/adds/timings.csv`. The rows of the steps "drop trade-offs" and "aggressive search" stopped with #130, because the run no longer makes these searches.

Above the table, the Run time section shows the lines about the run: the skip of the recent view, the market read and the pages from the cache (#118). Each line shows only when it applies. The page shows the Run time table: the step, the seconds, the calls, the states and the pages. The sub-steps of the Yahoo reads follow the Yahoo reads row, indented. The table has no row for the page write, because the run writes the page before that step ends.

Each step appends its row to `output/adds/timings.csv` when it ends. The rows of the sub-steps follow the row of the Yahoo reads. If you stop a run (Ctrl+C), the file keeps the rows of the finished steps. A stopped step writes no row for its sub-steps. The first steps end before the run knows the planning window. Their rows wait until the run finds the planning window. If the run stops before that, these rows get empty `days`, `open_days` and `adds_left`. All rows of one run have the same `run_at`, so you can compare runs before and after a change.

Decision (2026-10-26, #89): a `timings.csv` with an older header gets the new header at the next run. The run writes the file again with the new columns. The old rows keep their values and get an empty `pages`.

| Column | Value |
| --- | --- |
| `run_at` | The run start, local time to the second, for example `2026-10-25T21:04:33` |
| `days` | The days in the planning window |
| `open_days` | The days in the planning window with an open slot |
| `adds_left` | The adds left for the planning window |
| `step` | The step name from the step table above. A sub-step row has the name "Yahoo reads: <sub-step>", for example `Yahoo reads: market pages`. |
| `seconds` | The time of the step, 2 decimals |
| `calls` | The calls of the search, or empty |
| `states` | The unique states of the search, or empty |
| `pages` | The Yahoo pages of the Yahoo reads and of each of its sub-steps. Empty for the other steps. |

## Home page

Decision (2026-10-28, #120): each run that publishes also writes the home page of the site. The owner sees the roster with the season stats and the fit of each player in the playoff lineup. `adds/home.py` gets the data, and `core/home.py` makes the page.

- The roster is the roster of your team page. The players are in custom-rank order (`draft/rankings.py`). A player with no rank goes last.
- The season stats come from one ESPN `statistics/byathlete` request (`fetch/espn.py`): GP, MIN, PTS, REB, AST, 3PM, STL and BLK per game.
- Each playoff day, the best lineup of the position slots and Util takes the players in rank order (`best_lineup()` in `core/lineup.py`). The IL players are in the lineup pool, because they will likely be back by the playoffs. A player with `rests_b2b` = 1 gets no game on the second night of a back-to-back.
- The vs ideal row uses `ideal_games()` in `core/lineup.py`. The percent bands are `BANDS` in `core/lineup.py`: 90% or more, 70% to 89%, less than 70%. The draft board gets the same rules from `core/lineup.py` (#133).
- A week cell with `[flags] avoid_week_games` games or fewer (2) gets a red box on the games numeral.

The run writes the page before the plan page, so that the Run time table has the home page step. If the home page fails, the run prints the error and continues. The publish then puts the list of the tools at `/`.

## Core and drops

- The core list in `config.toml` holds the players that the planner never suggests to drop. The rule also holds for a core player who is Out.
- The stream spots are the empty roster spots first, also the spots that IL frees. Then, up to `stream_spots` (3), the rostered players with the lowest season value who are not core and not on IL hold a stream spot. The planner keeps all other players, as it keeps the core players.
- A player in a stream spot plays until the first add to his spot. That add drops him. A drop is a suggestion, never an order. Since #130 (2026-10-28), the planner does not compute the trade-off of a drop.
- The plan score counts this week's started games, and the next-week games as a tiebreak (see [Next-week games](#next-week-games)). The started games of a player in a stream spot count. The season value of a player in a stream spot is not in the score. You decide.
- A dropped player who is still a free agent next week can come back in a later plan.

Rostered players are not on the free-agent list. So their rank and season value come from the season projections file of the draft tools: the per-game value (`pg_value` of `core/valuation.py`) and the rank by that value (`pg_rank` on the draft board). The free-agent values use the same category scale, so the numbers compare. A player who is not in the projections file has the lowest value.

The page also warns you when a streamer has a higher blended value than the season value of your lowest core player. Since #140, a streamer is a free agent who plays for a team of an add of the team plan and has one of its slots ("Util": any position). If no core player is on your roster, the warning uses your lowest kept player. You can then make the streamer core.

## Status rules

Yahoo uses the official NBA designations: O (out), Q (questionable), D (doubtful), P (probable) and others. Only players who are Out or Out for Season can go on IL.

| Player | Team plan |
|---|---|
| Healthy | Plays every game of his team. A game of a holder on the rest list on a second night counts `1 - rest_chance` started games. |
| Out player (Out, Out for Season, NA (Not Active) or suspended) | Does not play in the planning window. His slot is open. If he is on IL, his roster spot is a stream spot. The free-agent table does not show a free agent with one of these statuses. |
| Flagged player (Q, D, P or another status) | Plays every game of his team. |
| Core player on the bench, not on IL | Takes a roster spot. Fills no slot while he is out. Never dropped. |

Since #140, the planner makes no contingency plan for a flagged player.

## Role up

Decision (2026-10-21): the planner marks the free agents who can get more minutes because a starter on their NBA team is absent. The mark changes no value and no plan. When a starter is absent, the last-14-day line of his backup does not show the new role yet.

The planner finds the absent starters in the rotation log (`core/rotation.py`). It does not read the statuses of players on other fantasy rosters, so the log is the only source for most starters. The planning run does not update the log. Run `python -m fantasyhoops.fetch.rotation` first.

1. A player is absent when his NBA team played a game after his last game in the log.
2. He is a starter when he started more than half of his last `starter_games` games (5).
3. The absence is new when his first missed game is in the last `days` days (7).
4. The mark stays for the first `games` missed games (3). After those games, the recent line of his backup shows the new role.
5. `core/identity.py` links his ESPN name to his Yahoo positions in `data/yahoo_players.csv`. A row of `data/name_overrides.csv` applies when its `espn_name` matches.
6. A free agent on his team who shares one of his positions gets the mark "role up", with the name of the absent starter.

The page shows the mark in the free-agent table and lists the marks in the section "Role up".

Limits:

- The log shows an absence only after the first missed game. A starter who is Out for the next game, but who has not missed a game yet, gets no mark.
- A starter who rests for one game is absent for that game too. So a rest day can give a mark.
- A player with no Yahoo positions marks no free agent.

## Data

| Data | Source |
|---|---|
| Your roster, the statuses, the adds that you used | Your team page (`/nba/<league>/<team>`) |
| The dates of the fantasy week, the category totals of the matchup | The matchup page of the current week (`/nba/<league>/matchup?mid1=<team>`) |
| Free agents: positions, status, projected and recent stats | The free-agent list (`/players?status=FA`): the first 3 pages at most of the full list (see [Market read](#market-read)), and all pages of the list filtered by NBA team |
| Waiver players and their clear days | The waiver list (`/players?status=W`): the first 6 pages of the full list (`WAIVER_PAGES`). The Roster Status cell shows the clear day, for example "W (Oct 22)". |
| Trend: adds and drops across Yahoo | Transaction Trends (`/nba/<league>/buzzindex?date=<day>&bimtab=A&sort=BI_A`), one page for each day of this week up to today |
| NBA schedule and game times | `data/schedule.csv` (`fetch/espn.py`) |
| Minutes, starts and closes (the role line) | The rotation log: `data/rotation_log.csv` and `data/rotation_scores.csv` (`fetch/rotation.py`). The planning run does not update the log. Run `python -m fantasyhoops.fetch.rotation` first. |

Only players with status FA are free agents. Players on waivers (W) are not. The planner reads the waiver players separately, each with his clear day:

- A waiver player can play for you from the day after his clear day. Example: a player who clears on Wed can start on Thu. The team plan does not know the waiver players, so check the clear day before you claim him for an add.
- A waiver claim is not sure. A team with a higher waiver priority can claim him first. The page marks each waiver player with W.
- A waiver claim uses one add of the weekly limit.
- The Roster Status cell has no year. The planner uses the year of the run day, or the next year if that date is more than 180 days before the run day.
- A W cell without a valid date gives no clear day, for example "W" or "W (Feb 29)" in a year with no Feb 29. The planner prints a warning and skips that player.
- The free-agent table and the replacement value use only the players with status FA.

Playwright uses a manual sign-in with Microsoft Edge. The first run opens an Edge window, and you sign in to Yahoo by hand. Later runs use the saved session in `.auth/yahoo/` until it expires. Each run opens a visible Edge window and closes it at the end. If the session has expired, the planner tells you to sign in in that window and then continues. On each page, the planner waits for the element that its reader needs, for example the player table. It does not wait for all network requests to stop, because Yahoo pages keep loading ads (#74). On a matchup page, the planner also waits up to 0.5 s for the score table. Some matchup pages have no score table, so this wait is short. Before #93, the wait was 2 s. See [ADR 1](../adr/0001-playwright-for-league-data.md).

Since #108, the planner reads some pages with raw requests and not in Edge. A raw request gets the HTML of the page from the server with the cookies of the Edge profile. No script of the page runs. Spike #95 found that the readers give the same rows on the raw HTML and on the HTML of Edge for the player lists and Transaction Trends.

| Page | How the planner reads it |
| --- | --- |
| Free-agent lists: the team lists and the market pages, both views | Raw requests |
| Waiver list, both views | Raw requests |
| Transaction Trends | Raw requests |
| Team page | Edge. A script on the page adds `data-pos`, and `read_roster()` needs it. |
| Matchup pages, this week and next week | Edge. In the live check of 2026-10-27 20:10, during NBA games, the raw matchup page had no score table. |

The planner sends at most 4 raw requests at a time (`MAX_REQUESTS`). These reads go together:

- Page 1 of the free-agent list of each read team. Then the next page of each team that has one.
- The projected page and the recent page of the same market page. The guard decides after each market page, so the planner reads no market page ahead.
- The Transaction Trends pages that are not in the cache.

Each raw request checks three things:

1. The HTTP status. HTTP 999 or 429 raises `YahooBlocked` (see below).
2. The final URL. If the request went to the Yahoo sign-in, the planner opens the page in Edge for the sign-in. Then the raw request reads the page again.
3. The element that the reader needs, for example the player table. A raw page without that element stops the run with an error that names the page.

Edge still starts at the beginning of each run, for the team page, the matchup pages, the cookies and a sign-in.

Yahoo can block the requests of the session. On 2026-10-27, Yahoo gave HTTP 999 "Request denied" after many loads (#95). When a page in Edge or a raw request gives HTTP 999 or 429, the planner raises `YahooBlocked` (`adds/session.py`, #107, #108). The message gives the status and the URL. The planning run stops at once. It does not wait for the element of the page, and it does not try again, because each retry is one more Yahoo load. What to do:

1. Do not start a new run immediately.
2. Wait until the block ends. Nobody has tested how long a block stays.
3. Start a new run. If the run raises `YahooBlocked` again, wait longer.

Yahoo and ESPN use different team codes, for example SAS and SA. The planner maps the Yahoo codes to the ESPN codes of the schedule.

### Page cache

Some Yahoo pages do not change during a day. The run keeps them in `output/adds/cache/` (`adds/cache.py`, #91). The key of a page is its page path. A later run takes a page from the cache, and it does not open that page in Edge.

| Page | Kept |
|---|---|
| The team-filtered lists and the market pages in the recent view (`S_AL14`) | Until the end of the day of the read |
| Transaction Trends of yesterday | Until the end of the day of the read |
| Transaction Trends of 2 or more days before today | For good |

The run never takes these pages from the cache:

- The team page and the matchup pages.
- The waiver list, in both views.
- All lists in the projected view. They give the FA status and the injury flags of each player.
- Transaction Trends of today.

The FA status and the injury flags of each option come only from the projected view of the run. A player who became a free agent after the cached read has no recent line until the next day. His blended line is then his projected line.

A recent view that a run stored earlier in the day does not show the games of that night. After the games end, run the planner with `--no-cache`.

At the start of each run, the run deletes the same-day entries of the days before today. The Transaction Trends entries that the cache keeps for good stay.

The cache is only a speed-up. The run treats a bad cache entry as a miss and reads the page from Yahoo. If the run cannot write an entry, it prints a warning and continues.

When a page comes from the cache, the Run time section of the page says so (#118), for example "The recent view: 14 pages from the cache of 2026-10-26 09:14." The time is the earliest read time of the cached recent pages. The page count of the Run time table counts only the pages from Yahoo. While the run skips the recent view (#90), only the Transaction Trends pages of earlier days come from the cache.

## Configuration

The settings will be in an `[adds]` section of `config.toml`:

| Setting | Meaning |
|---|---|
| `league` | The Yahoo league ID: 22820. |
| `team` | Your team ID in the league: 10 (TradeMark™). |
| `core` | The names of your core players. |
| `stream_spots` | The number of stream spots: 3. The empty spots count first. |
| `add_delay_days` | The add delay. 0 for this league. |
| `page_wait` | The seconds that the planner waits on each Yahoo page for the element that its reader needs: 10. If the element does not appear, the planner stops with an error that names the page and the element. |
| `rest_chance` | The chance that a player on the rest list sits on a second night: 0.5. That game counts `1 - rest_chance` started games. 0 counts each game as 1. |
| `minutes_rise` | The change of minutes (L5 minus 14d) that gets the MIN+ mark: 4. |
| `next_week_weight` | The part of a game this week that a game next week is worth: 0.5. 0 turns off the next-week games. See [Next-week games](#next-week-games). |
| `team_count_at` | From this number of teams, an add cell of the team plan gives the count of its teams, not the list: 6. See [Team plan](#team-plan). |
| `next_week_open_days` | The first days of next week that the page checks for open slots: 2. 0 turns off the next-week mark. See [Next-week mark](#next-week-mark). |
| `team_name` | The team name at the top of the home page: TradeMark™. Without it, the page shows "Roster". |
| `recent_skip_weight` | The run skips the recent view while the largest possible weight of the recent line is below this value: 0.3. 0 never skips. See [Skip of the recent view](#skip-of-the-recent-view). |
| `role_up.starter_games` | A starter started more than half of his last games of this number: 5. |
| `role_up.days` | The first missed game of a new absence is in the last days of this number: 7. |
| `role_up.games` | The role-up mark stays for this number of missed games: 3. |
| `flags.window_games` | The games in the window of the starter flag: 10. See [Starter flag and closer flag](#starter-flag-and-closer-flag). |
| `flags.min_games` | Fewer games than this number give no starter flag: 5. |
| `flags.new_games` | The last games that must all be starts for New: 3. |
| `flags.close_window` | The close games of his team in the window of the closer flag: 8. |
| `flags.min_close_games` | Fewer close games than this number give no closer flag: 4. |
| `flags.new_closes` | The last close games that must all be closes for New: 2. |
| `flags.regular_share` | The share of the window for Regular: 0.7. |
| `flags.some_share` | The share of the window for Inconsistent: 0.2. |

The settings of the [matchup weights](#matchup-weights) are in `[adds.matchup]`:

| Setting | Meaning |
|---|---|
| `close` | For each category, the margin in a whole week that keeps weight 1: pts 40, reb 15, ast 10, 3PM 5, blk 3, stl 3. About what one streamer adds in 3 games. |
| `large` | For each category, the margin in a whole week that gets `min_weight`: 3 × `close`. |
| `min_weight` | The lowest matchup weight: 0.5. Above 0, so a category with a large margin still counts. |

These first values are estimates. There is no better source yet.

## Terms

The terms that only the planner uses. The shared terms are in the [glossary](../glossary.md).

| Term | Meaning |
|---|---|
| Started game | A game that a player plays in a starting slot. A game on a day with all 6 slots full is not a started game. A started game of a player on the rest list on a second night counts `1 - rest_chance`. |
| Open day | A day of the planning window with at least one open starting slot. |
| Plan score | The score that chooses the team plan: first the started games of the stream spots in the planning window. Ties go to the plan with fewer adds, then to the plan with more next-week games. |
| Next-week games | The games next week of the players who hold a stream spot on the last day of the week, x `next_week_weight`. |
| Next-week mark | The mark of a free agent who fits an open slot on one of the first days of next week, for example "Mon open". The mark changes no value. |
| Matchup weight | The weight of a category from your margin in the current matchup: 1 for a close category, down to `min_weight` for a large lead or deficit. |
| Matchup value | The value of a player with each category weight times its matchup weight. With all categories tied, it equals the blended value. |
| Team plan | The adds of the stream spots as NBA teams and open slots, with the most started games and the fewest adds. It names no player. See [The team plan](#the-team-plan). |
| Add (of the team plan) | One recommended move: on its add day, add a player with one of its slots from one of its teams. A later add in the same row drops him. |
| Band | The days after an add that the new player holds the spot, in the week grid. A filled square marks a day that he starts. |
| Week file | `output/adds/week_plan_<first day>.json`: the adds that the runs of one fantasy week recommended. See [Week file](#week-file). |
| Planning run | One run of `python -m fantasyhoops.adds.plan`. |
| Planning window | Today to the last day of the current fantasy week. |
| Team window | A run of days in which one stream spot holds a player from one NBA team: from the add day to the day before the next add to the spot, or the last day of the week. |
| Out player | A core player who is Out, Out for Season, NA (Not Active) or suspended. |
| Flagged player | A player with a status that is not blank and does not make him an Out player, for example Q, D or P. |
| Absent starter | A player who started more than half of his recent games, then missed the last games of his NBA team in the rotation log. See [Role up](#role-up). |
| Role up | The mark of a free agent whose NBA team has an absent starter at one of his positions. The mark changes no value. |
| Trend | The adds and drops of a player across all Yahoo leagues, from Transaction Trends. |
| Waiver player | A player with Yahoo status W. He can play for you from the day after his clear day, as a waiver claim. |
| Clear day | The day that a waiver player clears waivers, from the Roster Status cell, for example "W (Oct 22)". |
| Role line | The minutes, the starts and the closes of a free agent, from the rotation log, with his starter flag and closer flag. |

## Decisions

- [ADR 1: Read league data with Playwright and a manual sign-in](../adr/0001-playwright-for-league-data.md)
- [ADR 2: Publish the adds plan on public GitHub Pages](../adr/0002-publish-adds-plan-publicly.md)
