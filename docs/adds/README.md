# Weekly adds planner

Status: planned. This guide records the agreed design. The code will be in `src/fantasyhoops/adds/`.

The planner shows how to use your adds in the current fantasy week. It chooses NBA teams for your stream spots, then lists the free agents on those teams. For the terms that all tools share, see the [glossary](../glossary.md).

## Table of contents

- [Goal](#goal)
- [Usage](#usage)
- [The plan](#the-plan)
- [Status rules](#status-rules)
- [Data](#data)
- [Configuration](#configuration)
- [Terms](#terms)
- [Decisions](#decisions)

## Goal

The plan gets the most started games from your stream spots. If two plans have the same started games, the plan with the higher per-game value wins.

Started games come mostly from game volume. The free agents are close in value, so value only breaks ties.

## Usage

```
python -m fantasyhoops.adds.plan
```

One planning run does these steps:

1. It reads your league from Yahoo.
2. It makes the plan for the planning window.
3. It writes the page in `output/adds/`.
4. It publishes the site to GitHub Pages, at `/adds/`.

You can run the planner on any day. Run it before the week starts for the full plan. Run it again during the week after an injury or a new free agent. Each run plans only the days that are left, with the adds that are left.

## The plan

The plan is a series of team windows for each stream spot, for example "Spot 1: CHA Mon–Wed, then PHX Thu–Sun".

- The planner chooses the windows from the NBA schedule. A window counts only the games that fill an open starting slot.
- Each window shows its window options: the best 3 free agents on that team who fit an open position. The options are in order of per-game value. Each option also shows its recent value. You choose the player.
- The planner does not propose a team that has no free agent at an open position.
- A streamer who is already on your roster is a window that costs no add. The planner keeps him if no other team gives more started games for the add.
- An add takes effect on the same day (add delay 0).

The page also warns you when a streamer has a higher rank than your lowest core player. You can then make him core in `config.toml`.

## Status rules

| Player | Main plan | Contingency plan |
|---|---|---|
| Healthy | Plays every game of his team. | None. |
| Out player (O or INJ) | Does not play in the planning window. His slot is open. | None. |
| Flagged player (any other status) | Plays every game of his team. | One for each of his game days. |
| Player on IL | Does not take a roster spot. His spot is a stream spot. | None. |
| Core player on the bench, not on IL | Takes a roster spot. Fills no slot while he is out. Never dropped. | None. |

A contingency plan fills the slot of a flagged player who is ruled out just before his game:

1. First, it tries a lineup move: a bench player who plays that day.
2. If no move works, it gives an add: a free agent whose game starts later that day, and the streamer to drop. It shows the cost: the adds that it uses and the team window that it ends early.

The planner does not keep an add back for contingency plans. The page shows the cost, and you decide.

## Data

| Data | Source |
|---|---|
| Your roster, the statuses, the adds that you used, the dates of the fantasy week | Your Yahoo league pages, with Playwright |
| Free agents, with their recent stats | Your Yahoo league pages, with Playwright. Only players with status FA. |
| NBA schedule | `data/schedule.csv` (`fetch/espn.py`) |
| Per-game value and positions | The projections and `core/valuation.py`, as for the draft tools |

Playwright uses a manual sign-in. The first run opens a browser window, and you sign in to Yahoo by hand. Later runs use the saved session until it expires. See [ADR 1](../adr/0001-playwright-for-league-data.md).

## Configuration

The settings will be in an `[adds]` section of `config.toml`:

| Setting | Meaning |
|---|---|
| `core` | The names of your core players. |
| `add_delay_days` | The add delay. 0 for this league. |

## Terms

The terms that only the planner uses. The shared terms are in the [glossary](../glossary.md).

| Term | Meaning |
|---|---|
| Started game | A game that a player plays in a starting slot. A game on a day with all 6 slots full is not a started game. |
| Plan score | First the started games of the stream spots in the planning window. Ties go to the plan with the higher per-game value of those games. |
| Planning run | One run of `python -m fantasyhoops.adds.plan`. |
| Planning window | Today to the last day of the current fantasy week. |
| Team window | A run of days in which one stream spot holds a player from one NBA team, for example "CHA Mon–Wed". |
| Window options | The best 3 free agents on the team of a team window who fit an open position. |
| Out player | A core player with status O or INJ. |
| Flagged player | A core player with a status other than blank, O or INJ. |
| Contingency plan | How to fill the slot of a flagged player who is ruled out just before his game. |

## Decisions

- [ADR 1: Read league data with Playwright and a manual sign-in](../adr/0001-playwright-for-league-data.md)
- [ADR 2: Publish the adds plan on public GitHub Pages](../adr/0002-publish-adds-plan-publicly.md)
