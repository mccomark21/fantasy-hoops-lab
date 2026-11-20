# NBA.com stats collector

`fantasyhoops.fetch.nba_stats` downloads the hustle and tracking stats of a season from stats.nba.com (#251, #252). No page uses the data yet. The luck module (#254) uses the makes and chances columns.

## Usage

The refresh run runs the collector as step 3. To run it by itself, run it from the repo root:

```sh
python -m fantasyhoops.fetch.nba_stats                    # The current season: data/nba_stats.csv and a dated copy
python -m fantasyhoops.fetch.nba_stats --season 2025-26   # A past season: data/nba_stats_2025-26.csv
```

`--out PATH` writes the output file to another path. The dated copy then goes in the `nba_stats/` folder next to that path.

The current season comes from `[league] espn_season` in `config.toml`. ESPN uses the year that the season ends, so `espn_season = 2027` gives the NBA.com season `2026-27`.

## Files

| File | Contents |
| --- | --- |
| `data/nba_stats.csv` | The current season. One row for each player that NBA.com lists. |
| `data/nba_stats/<YYYY-MM-DD>.csv` | A dated copy of `data/nba_stats.csv`. A second run on the same day replaces the copy of that day. |
| `data/nba_stats_<season>.csv` | A past season, for example `data/nba_stats_2025-26.csv`. A past season gets no dated copy. Collect 2025-26 one time. |

The collector writes no file when a request fails. Then the last good file stays. The refresh run prints the failure and continues with the next step.

## Tables

The collector reads 5 league-wide tables with the `nba_api` package, one request for each table. All stats are season totals, not per game. The table label is the prefix of its columns.

| Label | NBA.com table | Columns that the work uses |
| --- | --- | --- |
| `base` | `LeagueDashPlayerStats`, Base | STL, BLK, AST, REB, 3PM, 3PA |
| `hustle` | `LeagueHustleStatsPlayer` | Deflections, contested 2-point shots |
| `pass` | `LeagueDashPtStats`, Passing | Potential assists |
| `reb` | `LeagueDashPtStats`, Rebounding | Rebound chances |
| `touch` | `LeagueDashPtStats`, Possessions | Touches, time of possession. Kept for later role-change work. |

The owner chose these 5 tables on 2026-11-18. See the table decision in the [wiki](../wiki/nba-stats-2026-11-18.md).

## Columns

The first 16 columns are the same in each file:

| Column | Contents |
| --- | --- |
| `nba_id` | The NBA.com player id |
| `name`, `name_key`, `team` | The player name, the name for matching across sources, and the team |
| `gp` | Games played |
| `season` | The NBA.com season, for example `2025-26` |
| `stl_makes`, `stl_chances` | Steals and deflections |
| `blk_makes`, `blk_chances` | Blocks and contested 2-point shots |
| `ast_makes`, `ast_chances` | Assists and potential assists |
| `reb_makes`, `reb_chances` | Rebounds and rebound chances |
| `threes_makes`, `threes_chances` | 3-pointers made and 3-pointers attempted |

The category names are the keys of `[weights]` in `config.toml`. A makes column is a copy of a `base_` column. A chances column is a copy of a column of its table, for example `hustle_deflections`.

All other columns follow. Each column name is the table label and the NBA.com column name in lower case, for example `touch_time_of_poss`. The collector drops the id columns, the team record, the ranks and the work columns of each table.

A player who is missing from a table gets empty cells in the columns of that table. For example, on 2026-11-20, 6 of the 473 players had no hustle row.

## The rebound chances of the two seasons

On 2026-11-20, the league rate of rebounds for each rebound chance was 0.695 in 2025-26 and 0.543 in 2026-27. The other categories changed less. The cause is not known. A change of the NBA.com definition is possible. The luck module (#254) must check this before it uses the 2025-26 rebound rate as a baseline.

| Category | League rate 2025-26 | League rate 2026-27 (2026-11-20) |
| --- | --- | --- |
| STL | 0.484 | 0.475 |
| BLK | 0.193 | 0.218 |
| AST | 0.558 | 0.553 |
| REB | 0.695 | 0.543 |
| 3PM | 0.360 | 0.354 |
