# Weekly adds planner

Status: built. This guide records the design and how the planner works. The code is in `src/fantasyhoops/adds/`. The planner reads your team, prints the open starting slots of each day, ranks the NBA teams by the open days that they cover and prints the schedule plan for the stream spots, with the trade-off of each drop and the contingency plans. The schedule plan uses the blended value for the option order and the tiebreak. Then it prints the category totals of the current matchup with the matchup weights, the aggressive plan, the comparison of the two plans and the best plans for one roster spot. The aggressive plan uses the matchup value. The planner writes the plan page in `output/adds/` and publishes it at `/adds/`. The page shows the best plans for one roster spot, the matchup weights and a free-agent table with filters. It does not show the schedule plan, the aggressive plan or the comparison.

The planner shows how to use your adds in the current fantasy week. It gives two plans. The schedule plan chooses NBA teams first, then the free agents on those teams. The aggressive plan starts from the best free agents and uses more adds. For the terms that all tools share, see the [glossary](../glossary.md).

## Table of contents

- [Goal](#goal)
- [Usage](#usage)
- [The plans](#the-plans)
- [Rest on back-to-backs](#rest-on-back-to-backs)
- [Value](#value)
- [The page](#the-page)
- [Core and drops](#core-and-drops)
- [Status rules](#status-rules)
- [Role up](#role-up)
- [Data](#data)
- [Configuration](#configuration)
- [Terms](#terms)
- [Decisions](#decisions)

## Goal

The schedule plan gets the most started games from your stream spots. If two plans have the same started games, the plan with fewer adds wins. If the adds are also the same, the plan with the higher blended value of the started games wins. If the value is also the same, the plan whose last streamers have more games next week wins.

The aggressive plan gets the most value from your stream spots: the sum of the matchup value above an empty slot of its started games, plus a bonus for the games next week of its last streamers. It can give up started games for better players. The matchup value weights the categories by the state of the current matchup (see [Matchup weights](#matchup-weights)).

The two plans give you a real choice: few adds and a good schedule, or more adds and better players.

A started game of a player on the rest list on the second night of a back-to-back counts less than 1 started game. See [Rest on back-to-backs](#rest-on-back-to-backs).

## Usage

```
python -m fantasyhoops.adds.plan
```

One planning run does these steps:

1. It reads your league from Yahoo.
2. It makes the two plans for the planning window.
3. It writes the page in `output/adds/`.
4. It publishes the site to GitHub Pages, at `/adds/`.

To write the page with no publish, add `--no-publish`:

```
python -m fantasyhoops.adds.plan --no-publish
```

You can run the planner on any day. Run it before the week starts for the full plans. Run it again during the week after an injury or a new free agent. Each run plans only the days that are left, with the adds that are left.

On the last day of a fantasy week, the planner plans the next week. The planning window is the whole next week, and all the adds of the weekly limit are left (5).

The planning window starts today. The main plan does not use the game times. An add for today helps only if his game has not started.

## The plans

Both plans are a series of team windows for each stream spot, for example "Spot 1: CHA Mon–Wed, then PHX Thu–Sun". A window counts only the games that fill an open starting slot. An add takes effect on the same day (add delay 0). The page shows the latest day for each add, so that you can wait for injury news.

### Schedule plan

1. Find the open starting slots on each day of the planning window.
2. Rank the NBA teams by the open days that they cover. A team that plays on several open days covers them with one add.
3. Search the free agents of the best teams. The planner reads the free-agent list filtered by team, so it finds players far down the overall list. It reads the 8 teams with the most open days, and the best team for each open day that those 8 teams do not cover.
4. Choose the team windows that give the most started games. If two plans have the same started games, the plan with fewer adds wins. If the adds are also the same, the plan with the higher blended value of the started games wins. If the value is also the same, the plan with more [next-week games](#next-week-games) wins. A free agent must fit an open position on that day, with the other added players.

Each window shows its window options: the best 3 free agents on that team who fit the window, in order of blended value. A free agent fits the window if the plan keeps all its started games with him. Each option shows his projected, recent and blended value and the games of his team next week.

The search is exact. It looks at each open day in order. On each day, each stream spot keeps its player or gets a free agent who starts that day. The search does not know which players the plan dropped earlier in the week. A dropped player goes on waivers, so the plan then takes a different free agent with the same team and positions, if one exists.

### Aggressive plan

Decision (2026-10-20): the score of the aggressive plan is the sum of the value above an empty slot of its started games. So the aggressive plan can give up started games for better players. It uses no more than the adds that are left. Since 2026-10-21 (#59), the score uses the [matchup value](#matchup-weights).

The aggressive plan uses the same free agents and the same exact search as the schedule plan, with a different plan score:

1. Each started game counts its value above an empty slot: the matchup value of the player minus the matchup value of an empty slot. With all categories tied, the matchup value is the blended value.
2. The plan adds the next-week bonus: for each of its [next-week games](#next-week-games), the matchup value above an empty slot of that player. The bonus is never less than 0.
3. The plan with the highest sum wins. Ties go to the plan with fewer adds, then to the plan with more started games.
4. The plan uses more adds, up to the adds that are left, when the better players give a higher sum.

The value of an empty slot is the value of a stat line of zeros on the category scale of the season projections file. It is about -11.8 with the projections file of 2026-10-12.

Why the planner does not add the blended values as they are: a free agent usually has a value below 0, because the scale comes from the drafted players. In the free-agent lists of 2026-10-20, the 47 free agents had blended values from -1.6 to -9.2. With a plain sum, each started game of a free agent lowers the sum, so the plan adds nobody. A check with the pages of 2026-10-20 gave a plan with 0 adds. With the value above an empty slot, each started game counts more than 0 (a free agent at -1.6 counts +10.3, at -4.5 counts +7.4). The value is a weighted sum of the counting stats, so the sum is the value of all the stats that the started games add. One game of a player at -1.6 (+10.3) then beats one game of a player at -4.5 (+7.4). But two games of the player at -4.5 (+14.8) beat one game of the player at -1.6.

Two other reference values were checked and not used. Replacement level (rank 140, about -2.7) makes most streamers count below 0, so the plan leaves open slots empty. The lowest value of the free agents that the run read changes with the teams that the run read.

A holder who is not in the projections file counts as an empty slot in the aggressive plan. The schedule plan counts him as 0.

The planner shows no drop trade-offs for the aggressive plan, because the gain of a drop counts started games. The windows of the aggressive plan show which players it drops.

### Next-week games

Decision (2026-10-21, #60): a player who holds a stream spot on the last day of the week can stay on the roster next week. Then that spot needs no add on the first day of next week. So both plans count the games next week of these players:

1. Next week is the 7 days after the last day of the week to plan. The planner does not read the dates of next week from Yahoo. So a longer week, for example the week of the All-Star break, gets only its first 7 days.
2. Each game of his NBA team next week counts, also on days with all slots full. The open slots of next week are not known yet. A second night of a back-to-back next week also counts 1 game.
3. A game next week counts `next_week_weight` (0.5) of a game this week, because injuries and role changes can occur before then.
4. A player who is Out gets no next-week games. An empty spot also gets none.

The schedule plan uses the next-week games only as the last tiebreak. The aggressive plan adds their matchup value above an empty slot to its score as a bonus. The bonus is a separate term and never less than 0, so it never lowers the part of the score from this week. The aggressive plan can choose a plan with a lower value this week if the bonus is larger than the difference.

The planner adds a player only on a day that he starts this week. It does not add a player only for his games next week. The best plans for one roster spot, the drop trade-offs and the contingency plans do not use the next-week games.

The terminal shows the games next week of each window option, and the games next week of the last players of each plan.

### Comparison

The terminal shows the two plans side by side: the adds that each plan uses, its started games and the blended value of those started games. The blended value is the sum of the blended values of the started games. A free agent usually has a value below 0, so a plan with more started games can have a lower sum. So the comparison also shows the value above an empty slot. The last row is the matchup value above an empty slot, the score of the aggressive plan for this week. The rows have no next-week bonus. With all matchup weights at 1, the last two rows are the same. If the two plans are the same, the planner says so and shows the aggressive plan in one line.

## Rest on back-to-backs

Decision (2026-10-21, #62): a player on the rest list counts less than 1 started game on the second night of a back-to-back. All other players count each game as 1, as before.

- The rest list is the `rests_b2b` column of the `[risk] file` (`data/projection_risk.csv`), the list of the draft tools. The names match after `name_key()`. A player who is not in the file does not rest. If the file does not exist, nobody rests.
- A second night is a game of a team on the day after a game of the same team. A game on the day before the planning window counts too.
- One game of a player on the rest list on a second night counts `1 - rest_chance` started games. `[adds] rest_chance` is 0.5, so the game counts 0.5. No data gives a better value yet. With 0, the planner counts each game as 1.
- The value of that game in the plan score is the blended value times the same count.
- The count applies to the free agents and to the players in the stream spots. It does not change the kept players.

The started games of a plan can now be a fraction, for example 6.5. The tie rules of the plan score stay in the same order. The score rounds the started games to 6 decimals, so that the same games in a different order give a tie. So a player with no rest risk beats a player on the rest list with the same games.

On each day, the lineup puts the players with no rest risk in the open slots first, then the players with the higher value. A window option fits only if the plan keeps all its counted started games with him.

The draft tools do not change. There, `rests_b2b` changes only the playoff game counts, never the season games or the value. `[adds] rest_chance` is separate from `[risk] rest_chance` of the auction simulator.

The page marks each second night with a small "2", for all players. The terminal marks it with "b2b".

## Value

The blended value orders the free agents. It uses your 6 categories and your weights, the same formula as `core/valuation.py`, on a blended stat line:

- The projected line: Yahoo's projection for the next 7 days (from Rotowire). Rotowire updates it during the season.
- The recent line: the player's per-game averages in the last 14 days.
- Blended line = projected line, moved toward the recent line as games accumulate. The weight of the recent line = games in the last 14 days ÷ 14. A player with 7 games gets 50%.

In the first week of the season, the blended value is the projected value, because there are no recent games.

If Yahoo has no projection for a player, but he has recent games, the blended line is the recent line. It is the only stat line that the planner has for him. A player with no projection and no recent games has no value, and the plans do not use him.

The planner reads each free-agent list twice: with `stat1=S_PS7` (the projection for the next 7 days, as totals) and with `stat1=S_AL14` (the averages of the last 14 days). It matches the players of the two lists by name and NBA team.

Next to each free agent, the page also shows:

- The recent value: the value of the last-14-day line alone.
- The trend: his adds today and this week across all Yahoo leagues, from Transaction Trends. Many of these adds come from leagues that score all 9 categories. So the trend is evidence and a tiebreak, not a plan of its own.
  Transaction Trends shows one day and the 50 most added players of that day. The planner reads one page for each day of this week up to today and adds them. A player who is not on the page of a day counts 0 adds that day. A player who is on no page shows a dash. Between two options with the same blended value, the option with more adds this week comes first, then more adds today. The trend never changes the plan score.

### Market value

The page shows the market value: the blended value above a replacement free agent. The replacement free agent is the free agent at rank 15 by blended value among the free agents that the run read (Out players do not count). His market value is 0. A positive market value is better than the replacement free agent.

The planner itself uses the values on the scale of the projections. A market value is the same value minus one number, so it does not change the order of the players or of the plans.

The stat lines come from Yahoo. The season projections file of the draft tools gives only the category scale: the mean and the standard deviation of each category in the player pool. So the values are on the same scale as the per-game value on the draft board. A streamer usually has a value below 0, because the pool holds the drafted players.

### Matchup weights

Decision (2026-10-21, #59): the aggressive plan weights the 6 categories by the state of the current matchup. The schedule plan, the option order and the best plans for one roster spot keep the blended value.

The planner reads the category totals of your team and your opponent from the score table of the matchup page. The planner finds the score table by its stat headers (PTS, REB, AST, 3PTM, ST, BLK). On 2026-10-21, after the first games, the table had no Score header (#73). The margin of a category is your total minus the total of your opponent. Each category then gets a matchup weight:

1. A margin of `close` or less (a lead or a deficit) keeps weight 1.
2. A margin of `large` or more gets weight `min_weight` (0.5).
3. Between the two, the weight goes down in a straight line.

The `close` and `large` margins in `config.toml` are for a whole week. The planner multiplies them by the share of the week that is left: the days of the planning window ÷ the days of the fantasy week. A lead of 5 3PM is close with 6 days left. With 1 day left, it is a large lead.

The matchup value of a player is his value with each category weight times its matchup weight, on the same category scale. A holder gets the matchup value of his season projection. With all categories tied, all weights are 1, so the matchup value equals the blended value. On the first day of a week, and when the planner plans the next week, the totals are 0, so the weights are 1.

Example: you lead 3PM by 15 with the whole week left. The weight of 3PM goes from 0.70 to 0.35. A streamer who adds 3PM is then worth less in the aggressive plan. If you trail blocks by 2, blocks keep their weight.

If the matchup page has no score table, all weights are 1, and the terminal and the page say so.

## The page

The page has two main sections: the best plans for one roster spot, and the free-agent table. Between them, the matchup section shows the total of each category for your team and your opponent, the margin and the matchup weight. The page is public, so it does not show the name of the opponent. After the free-agent table, a section lists the waiver players. The next section lists the role-up marks (see [Role up](#role-up)).

### Best plans for one roster spot

Each row is a plan for one stream spot. A row can use more than one add in that spot, for example player A on Tue and Thu, then player B on Sat and Sun. A row never uses adds in two spots. Each row uses different players, so the rows are alternatives.

To make a row, the planner runs the search of the schedule plan for each stream spot alone. The other stream players stay in their spots. It keeps the best result: the most games gained, then the fewest adds, then the highest value. Then it removes the players of that row and makes the next row. The page shows 3 rows.

| Column | What it shows |
| --- | --- |
| Days | The started games of the new players on that day. A `+` marks a latest add day. A small "2" marks a game on a second night. |
| Adds | The adds of the row. |
| Gms | The games gained: the started games of the new players minus the started games that the dropped player loses. A fraction if a player on the rest list starts on a second night. |
| Moves | One line for each add, for example "+Alex Caruso (OKC) – Tue, Thu & Sun", then the drop. |

The rows can all use the same spot. Usually that is the spot whose player loses the fewest games.

### Free-agent table

The table shows the free agents that the run read: the free agents of the teams that the schedule plan reads, and the first 6 pages (150 players) of the full free-agent list. It shows the 10 best players for the filters.

- Days: select one day or more. The table shows the players who play on all the selected days. Each day shows your open slots and the NBA games of that day.
- Positions: select one position or more. The table shows the players with one of the selected positions.
- "Only games that fill an open slot": a game counts only if an open slot of that day takes one of his positions.
- Sort: click Val, Match, Recent or Gms. Gms is the number of his games on the selected days. Sort by Gms to find the player with the most games on those days. Val then puts the players with the same games in order.

Match is the market value with the matchup weights: the matchup value above the matchup value of a replacement free agent. Compare Val and Match to see how the matchup changes the value of a player.

A filter does not change Val or Match, because they are values per game.

A filled dot is a game in an open slot that he can fill. An empty circle is a game with no open slot for him. A small "2" marks a game on a second night. A player with a market value of +1.5 or more gets the mark "FA?": a value this high is unusual for a free agent, so check his status. A player with a role-up mark gets the mark "UP", and his line names the absent starter.

### Role line

Decision (2026-10-21): the role line is a mark only. It does not change the blended value or the plans.

Each player in the free-agent table has a role line from the rotation log, for example "Min 28.0 L5, 22.0 14d (+6.0) · Starts 3/4 · Closes 1/2":

- Min: his mean minutes in his last 5 games (L5), then his mean minutes in his games of the last 14 days (14d), then the change (L5 minus 14d).
- Starts: his starts / his games in the last 14 days.
- Closes: his closes / the close games of his NBA team in the last 14 days. See [close game](../glossary.md#rotation) in the glossary. A close in a blowout does not count.
- MIN+: the change is `minutes_rise` (4) minutes or more. The mark is next to his name.

The last 5 games are the last 5 games that he played. They can be older than 14 days. The 14 days end yesterday, because the log holds only final games. Early in the season, both windows hold the same games, so the change is 0.

The planner links each Yahoo name to an ESPN name after `name_key()`. `data/name_overrides.csv` gives the ESPN name for a player whose names do not match. If two ESPN players have the same name, the player with games for the NBA team of the free agent wins. If neither has games for that team, the free agent gets no role line. A player who is not in the log has no role line. Without `data/rotation_log.csv`, the page has no role lines.

### Waiver players

A separate table lists the waiver players that the run read, best value first. It shows the team, the positions, the clear day, the first day that a plan can use him and Val (the same market value as the free-agent table). The section is not on the page when the run read no waiver player. See [Data](#data) for the waiver rules.

## Core and drops

- The core list in `config.toml` holds the players that the planner never suggests to drop. The rule also holds for a core player who is Out.
- The stream spots are the empty roster spots first, also the spots that IL frees. Then, up to `stream_spots` (3), the rostered players with the lowest season value who are not core and not on IL hold a stream spot. The planner keeps all other players, as it keeps the core players.
- A player in a stream spot plays until the first add to his spot. That add drops him. A drop is a suggestion, never an order. The output shows the trade-off, for example "Drop Quickley (rank 90, season value -0.52) -> PHX Thu 01/07 to Sun 01/10: +2 started games this week".
- The gain of a drop is the started games of the plan minus the started games of the best plan that keeps him. Both counts include the started games of the kept players.
- The plan score counts this week's started games, and the next-week games as a tiebreak or a bonus (see [Next-week games](#next-week-games)). The started games of a player in a stream spot count. The season cost of a drop is shown, not scored. You decide.
- A dropped player who is still a free agent next week can come back in a later plan.

Rostered players are not on the free-agent list. So their rank and season value come from the season projections file of the draft tools: the per-game value (`pg_value` of `core/valuation.py`) and the rank by that value (`pg_rank` on the draft board). The free-agent values use the same category scale, so the numbers compare. A player who is not in the projections file has the lowest value, and the output says so.

The page also warns you when a streamer (a window option) has a higher blended value than the season value of your lowest core player. If no core player is on your roster, the warning uses your lowest kept player. You can then make the streamer core.

## Status rules

Yahoo uses the official NBA designations: O (out), Q (questionable), D (doubtful), P (probable) and others. Only players who are Out or Out for Season can go on IL.

| Player | Main plan | Contingency plan |
|---|---|---|
| Healthy | Plays every game of his team. A game of a player on the rest list on a second night counts `1 - rest_chance` started games. | None. |
| Out player (Out, Out for Season, NA (Not Active) or suspended) | Does not play in the planning window. His slot is open. If he is on IL, his roster spot is a stream spot. A free agent with one of these statuses is not in the plan. | None. |
| Flagged player (Q, D, P or another status) | Plays every game of his team. | One for each of his game days. |
| Core player on the bench, not on IL | Takes a roster spot. Fills no slot while he is out. Never dropped. | None. |

A contingency plan fills the slot of a flagged player who is ruled out just before his game:

1. First, it tries a lineup move: a bench player who plays that day. The planner makes the lineup of that day again without the flagged player, with the players of the main plan in the stream spots. A move works if the number of starters stays the same.
2. If no move works, it gives an add: a free agent whose game starts later that day, and the streamer to drop. The add goes to an empty stream spot if there is one. Otherwise it replaces the streamer who loses the fewest started games, and that streamer must not start that day. It shows the cost: the add that it uses, the adds left after the main plan and the team window that it ends early.

A flagged player gets a plan only for the days on which he starts. On a day when he sits on the bench, his status changes nothing.

The game times come from the `time` column of `data/schedule.csv` (US Eastern). A schedule file without this column still works. The plan then lists each free agent who plays that day and fits, and tells you to check that his game starts after the game of the flagged player.

The planner does not keep an add back for contingency plans. The page shows the cost, and you decide. The terminal prints the contingency plans after the main plan.

## Role up

Decision (2026-10-21): the planner marks the free agents who can get more minutes because a starter on their NBA team is absent. The mark changes no value and no plan. When a starter is absent, the last-14-day line of his backup does not show the new role yet.

The planner finds the absent starters in the rotation log (`core/rotation.py`). It does not read the statuses of players on other fantasy rosters, so the log is the only source for most starters. The planning run does not update the log. Run `python -m fantasyhoops.fetch.rotation` first.

1. A player is absent when his NBA team played a game after his last game in the log.
2. He is a starter when he started more than half of his last `starter_games` games (5).
3. The absence is new when his first missed game is in the last `days` days (7).
4. The mark stays for the first `games` missed games (3). After those games, the recent line of his backup shows the new role.
5. `core/identity.py` links his ESPN name to his Yahoo positions in `data/yahoo_players.csv`. A row of `data/name_overrides.csv` applies when its `espn_name` matches.
6. A free agent on his team who shares one of his positions gets the mark "role up", with the name of the absent starter.

The terminal prints each absent starter and the free agents at his positions. Each window option with the mark ends with "role up: <name> absent". The page shows the mark in the free-agent table and lists the marks in the section "Role up".

Limits:

- The log shows an absence only after the first missed game. A starter who is Out for the next game, but who has not missed a game yet, gets no mark.
- A starter who rests for one game is absent for that game too. So a rest day can give a mark.
- A player with no Yahoo positions marks no free agent.

## Data

| Data | Source |
|---|---|
| Your roster, the statuses, the adds that you used | Your team page (`/nba/<league>/<team>`) |
| The dates of the fantasy week, the category totals of the matchup | The matchup page of the current week (`/nba/<league>/matchup?mid1=<team>`) |
| Free agents: positions, status, projected and recent stats | The free-agent list (`/players?status=FA`): the first 6 pages of the full list, and all pages of the list filtered by NBA team |
| Waiver players and their clear days | The waiver list (`/players?status=W`): the first 6 pages of the full list. The Roster Status cell shows the clear day, for example "W (Oct 22)". |
| Trend: adds and drops across Yahoo | Transaction Trends (`/nba/<league>/buzzindex?date=<day>&bimtab=A&sort=BI_A`), one page for each day of this week up to today |
| NBA schedule and game times | `data/schedule.csv` (`fetch/espn.py`) |
| Minutes, starts and closes (the role line) | The rotation log: `data/rotation_log.csv` and `data/rotation_scores.csv` (`fetch/rotation.py`). The planning run does not update the log. Run `python -m fantasyhoops.fetch.rotation` first. |

Only players with status FA are free agents. Players on waivers (W) are not. The planner reads the waiver players separately, each with his clear day:

- A plan can use a waiver player from the day after his clear day. Example: a player who clears on Wed can start in a Thu window.
- A waiver claim is not sure. A team with a higher waiver priority can claim him first. The terminal and the page mark each waiver player with W.
- A waiver claim uses one add of the weekly limit.
- The Roster Status cell has no year. The planner uses the year of the run day, or the next year if that date is more than 180 days before the run day.
- A W cell without a valid date gives no clear day, for example "W" or "W (Feb 29)" in a year with no Feb 29. The planner prints a warning and skips that player.
- The terminal list and the page show the same Val: the market value of the free-agent table.
- The free-agent table and the replacement value use only the players with status FA.

Playwright uses a manual sign-in with Microsoft Edge. The first run opens an Edge window, and you sign in to Yahoo by hand. Later runs use the saved session in `.auth/yahoo/` until it expires. Each run opens a visible Edge window and closes it at the end. If the session has expired, the planner tells you to sign in in that window and then continues. On each page, the planner waits for the element that its reader needs, for example the player table. It does not wait for all network requests to stop, because Yahoo pages keep loading ads (#74). See [ADR 1](../adr/0001-playwright-for-league-data.md).

Yahoo and ESPN use different team codes, for example SAS and SA. The planner maps the Yahoo codes to the ESPN codes of the schedule.

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
| `role_up.starter_games` | A starter started more than half of his last games of this number: 5. |
| `role_up.days` | The first missed game of a new absence is in the last days of this number: 7. |
| `role_up.games` | The role-up mark stays for this number of missed games: 3. |

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
| Plan score | The score that chooses a plan. Schedule plan: first the started games of the stream spots in the planning window. Ties go to the plan with fewer adds, then to the plan with the higher blended value of the started games, then to the plan with more next-week games. Aggressive plan: the sum of the matchup value above an empty slot of the started games, plus the next-week bonus. Ties go to the plan with fewer adds, then to the plan with more started games. |
| Next-week games | The games next week of the players who hold a stream spot on the last day of the week, x `next_week_weight`. |
| Value above an empty slot | The blended value of a player minus the value of an empty slot (a stat line of zeros, about -11.8). The aggressive plan uses the matchup value of the player and of the empty slot. |
| Matchup weight | The weight of a category from your margin in the current matchup: 1 for a close category, down to `min_weight` for a large lead or deficit. |
| Matchup value | The value of a player with each category weight times its matchup weight. With all categories tied, it equals the blended value. |
| Schedule plan | The plan that chooses NBA teams by the open days that they cover, then free agents on those teams, with the fewest adds. |
| Aggressive plan | The plan with the highest sum of the matchup value above an empty slot of its started games. It can use more adds and give up started games for better players. |
| Planning run | One run of `python -m fantasyhoops.adds.plan`. |
| Planning window | Today to the last day of the current fantasy week. |
| Team window | A run of days in which one stream spot holds a player from one NBA team, for example "CHA Mon–Wed". |
| Window options | The best 3 free agents on the team of a team window who fit an open position. |
| Out player | A core player who is Out, Out for Season, NA (Not Active) or suspended. |
| Flagged player | A core player with a status that is not blank and does not make him an Out player, for example Q, D or P. |
| Absent starter | A player who started more than half of his recent games, then missed the last games of his NBA team in the rotation log. See [Role up](#role-up). |
| Role up | The mark of a free agent whose NBA team has an absent starter at one of his positions. The mark changes no value. |
| Contingency plan | How to fill the slot of a flagged player who is ruled out just before his game. |
| Trend | The adds and drops of a player across all Yahoo leagues, from Transaction Trends. |
| Waiver player | A player with Yahoo status W. A plan can use him from the day after his clear day, as a waiver claim. |
| Clear day | The day that a waiver player clears waivers, from the Roster Status cell, for example "W (Oct 22)". |
| Role line | The minutes, the starts and the closes of a free agent, from the rotation log. |

## Decisions

- [ADR 1: Read league data with Playwright and a manual sign-in](../adr/0001-playwright-for-league-data.md)
- [ADR 2: Publish the adds plan on public GitHub Pages](../adr/0002-publish-adds-plan-publicly.md)
