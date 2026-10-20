# Weekly adds planner

Status: in progress. This guide records the agreed design. The code is in `src/fantasyhoops/adds/`. Steps 1 and 2 work: the planner reads your team, prints the open starting slots of each day, ranks the NBA teams by the open days that they cover and prints the schedule plan for the stream spots, with the trade-off of each drop. The schedule plan uses the projected value, not the blended value yet. The aggressive plan, the page and the publish step are not built yet.

The planner shows how to use your adds in the current fantasy week. It gives two plans. The schedule plan chooses NBA teams first, then the free agents on those teams. The aggressive plan starts from the best free agents and uses more adds. For the terms that all tools share, see the [glossary](../glossary.md).

## Table of contents

- [Goal](#goal)
- [Usage](#usage)
- [The plans](#the-plans)
- [Value](#value)
- [Core and drops](#core-and-drops)
- [Status rules](#status-rules)
- [Data](#data)
- [Configuration](#configuration)
- [Terms](#terms)
- [Decisions](#decisions)

## Goal

Each plan gets the most started games from your stream spots. If two plans have the same started games, the plan with fewer adds wins. If the adds are also the same, the plan with the higher blended value of the started games wins.

The two plans give you a real choice: few adds and a good schedule, or more adds and better players.

## Usage

```
python -m fantasyhoops.adds.plan
```

One planning run does these steps:

1. It reads your league from Yahoo.
2. It makes the two plans for the planning window.
3. It writes the page in `output/adds/`.
4. It publishes the site to GitHub Pages, at `/adds/`.

You can run the planner on any day. Run it before the week starts for the full plans. Run it again during the week after an injury or a new free agent. Each run plans only the days that are left, with the adds that are left.

On the last day of a fantasy week, the planner plans the next week. The planning window is the whole next week, and all the adds of the weekly limit are left (5).

The planning window starts today. The schedule has no game times. An add for today helps only if his game has not started.

## The plans

Both plans are a series of team windows for each stream spot, for example "Spot 1: CHA Mon–Wed, then PHX Thu–Sun". A window counts only the games that fill an open starting slot. An add takes effect on the same day (add delay 0). The page shows the latest day for each add, so that you can wait for injury news.

### Schedule plan

1. Find the open starting slots on each day of the planning window.
2. Rank the NBA teams by the open days that they cover. A team that plays on several open days covers them with one add.
3. Search the free agents of the best teams. The planner reads the free-agent list filtered by team, so it finds players far down the overall list. It reads the 8 teams with the most open days, and the best team for each open day that those 8 teams do not cover.
4. Choose the team windows that give the most started games. If two plans have the same started games, the plan with fewer adds wins. A free agent must fit an open position on that day, with the other added players.

Each window shows its window options: the best 3 free agents on that team who fit the window, in order of blended value. A free agent fits the window if the plan keeps all its started games with him. Until the blended value is built, the options are in order of projected value.

The search is exact. It looks at each open day in order. On each day, each stream spot keeps its player or gets a free agent who starts that day. The search does not know which players the plan dropped earlier in the week. A dropped player goes on waivers, so the plan then takes a different free agent with the same team and positions, if one exists.

### Aggressive plan

1. Start from the top free agents by blended value.
2. Use more adds, up to the adds that are left, when a better player gains started games.

### Comparison

The page shows the two plans side by side: the adds that each plan uses, its started games and the blended value of those started games.

## Value

The blended value orders the free agents. It uses your 6 categories and your weights, the same formula as `core/valuation.py`, on a blended stat line:

- The projected line: Yahoo's projection for the next 7 days (from Rotowire). Rotowire updates it during the season.
- The recent line: the player's per-game averages in the last 14 days.
- Blended line = projected line, moved toward the recent line as games accumulate. The weight of the recent line = games in the last 14 days ÷ 14. A player with 7 games gets 50%.

In the first week of the season, the blended value is the projected value, because there are no recent games.

Next to each free agent, the page also shows:

- The recent value: the value of the last-14-day line alone.
- The trend: his adds today and this week across all Yahoo leagues, from Transaction Trends. Many of these adds come from leagues that score all 9 categories. So the trend is evidence and a tiebreak, not a plan of its own.

The stat lines come from Yahoo. The season projections file of the draft tools gives only the category scale: the mean and the standard deviation of each category in the player pool. So the values are on the same scale as the per-game value on the draft board. A streamer usually has a value below 0, because the pool holds the drafted players.

## Core and drops

- The core list in `config.toml` holds the players that the planner never suggests to drop. The rule also holds for a core player who is Out.
- The stream spots are the empty roster spots first, also the spots that IL frees. Then, up to `stream_spots` (3), the rostered players with the lowest season value who are not core and not on IL hold a stream spot. The planner keeps all other players, as it keeps the core players.
- A player in a stream spot plays until the first add to his spot. That add drops him. A drop is a suggestion, never an order. The output shows the trade-off, for example "Drop Quickley (rank 90, season value -0.52) -> PHX Thu 01/07 to Sun 01/10: +2 started games this week".
- The gain of a drop is the started games of the plan minus the started games of the best plan that keeps him. Both counts include the started games of the kept players.
- The plan score counts only this week's started games. The started games of a player in a stream spot count. The season cost of a drop is shown, not scored. You decide.
- A dropped player who is still a free agent next week can come back in a later plan.

Rostered players are not on the free-agent list. So their rank and season value come from the season projections file of the draft tools: the per-game value (`pg_value` of `core/valuation.py`) and the rank by that value (`pg_rank` on the draft board). The free-agent values use the same category scale, so the numbers compare. A player who is not in the projections file has the lowest value, and the output says so.

The page also warns you when a streamer (a window option) has a higher blended value than the season value of your lowest core player. If no core player is on your roster, the warning uses your lowest kept player. You can then make the streamer core.

## Status rules

Yahoo uses the official NBA designations: O (out), Q (questionable), D (doubtful), P (probable) and others. Only players who are Out or Out for Season can go on IL.

| Player | Main plan | Contingency plan |
|---|---|---|
| Healthy | Plays every game of his team. | None. |
| Out player (Out, Out for Season, NA (Not Active) or suspended) | Does not play in the planning window. His slot is open. If he is on IL, his roster spot is a stream spot. A free agent with one of these statuses is not in the plan. | None. |
| Flagged player (Q, D, P or another status) | Plays every game of his team. | One for each of his game days. |
| Core player on the bench, not on IL | Takes a roster spot. Fills no slot while he is out. Never dropped. | None. |

A contingency plan fills the slot of a flagged player who is ruled out just before his game:

1. First, it tries a lineup move: a bench player who plays that day.
2. If no move works, it gives an add: a free agent whose game starts later that day, and the streamer to drop. It shows the cost: the adds that it uses and the team window that it ends early.

The planner does not keep an add back for contingency plans. The page shows the cost, and you decide.

## Data

| Data | Source |
|---|---|
| Your roster, the statuses, the adds that you used | Your team page (`/nba/<league>/<team>`) |
| The dates of the fantasy week, the matchup | The matchup page of the current week (`/nba/<league>/matchup?mid1=<team>`) |
| Free agents: positions, status, projected and recent stats | The free-agent list (`/players?status=FA`), all pages, and the same list filtered by NBA team |
| Trend: adds and drops across Yahoo | Transaction Trends (`/nba/<league>/buzzindex`) |
| NBA schedule | `data/schedule.csv` (`fetch/espn.py`) |

Only players with status FA are free agents. Players on waivers (W) are not.

Playwright uses a manual sign-in with Microsoft Edge. The first run opens an Edge window, and you sign in to Yahoo by hand. Later runs use the saved session in `.auth/yahoo/` until it expires. Each run opens a visible Edge window and closes it at the end. If the session has expired, the planner tells you to sign in in that window and then continues. See [ADR 1](../adr/0001-playwright-for-league-data.md).

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

## Terms

The terms that only the planner uses. The shared terms are in the [glossary](../glossary.md).

| Term | Meaning |
|---|---|
| Started game | A game that a player plays in a starting slot. A game on a day with all 6 slots full is not a started game. |
| Open day | A day of the planning window with at least one open starting slot. |
| Plan score | First the started games of the stream spots in the planning window. Ties go to the plan with fewer adds, then to the plan with the higher blended value of the started games. |
| Schedule plan | The plan that chooses NBA teams by the open days that they cover, then free agents on those teams, with the fewest adds. |
| Aggressive plan | The plan that starts from the top free agents by blended value and uses more adds. |
| Planning run | One run of `python -m fantasyhoops.adds.plan`. |
| Planning window | Today to the last day of the current fantasy week. |
| Team window | A run of days in which one stream spot holds a player from one NBA team, for example "CHA Mon–Wed". |
| Window options | The best 3 free agents on the team of a team window who fit an open position. |
| Out player | A core player who is Out, Out for Season, NA (Not Active) or suspended. |
| Flagged player | A core player with a status that is not blank and does not make him an Out player, for example Q, D or P. |
| Contingency plan | How to fill the slot of a flagged player who is ruled out just before his game. |
| Trend | The adds and drops of a player across all Yahoo leagues, from Transaction Trends. |

## Decisions

- [ADR 1: Read league data with Playwright and a manual sign-in](../adr/0001-playwright-for-league-data.md)
- [ADR 2: Publish the adds plan on public GitHub Pages](../adr/0002-publish-adds-plan-publicly.md)
