# NBA metrics inventory of 2026-11-18

On 2026-11-18 an agent listed each column of `data/nba_stats.csv` and compared it with the box-score categories. The file came from the collector of #251 (PR #256, `3fdaea6`). This page keeps the scratch result so that it outlives the scratchpad. The owner decisions that came from it are in [NBA hustle and tracking stats of 2026-11-18](nba-stats-2026-11-18.md).

## Method

- The file had 471 players and 117 columns: 4 id columns, `gp` and 112 stat columns. The season was 2026-27, with about 10 to 15 games played.
- The agent grouped the played rows of `data/box_scores.csv` by player and took the mean per game. It joined the two files on `name_key`, the same function that the collector uses. All 471 box-score players matched.
- The correlations use the 222 players with 20 or more box-score minutes per game. They are Pearson r. The hustle columns were empty for 8 players. The rebound columns were empty for 14 players.
- Unit: PG is per game (the collector asks for PerGame). TOT is a season total (NBA.com ignores PerGame for these columns). RATE is a ratio, a percent or a rating.
- Tag: `lead:X` is a leading indicator of category X. `role` is role or usage. `eff` is efficiency or conversion. `noise` has little fantasy use. `= X` is the category itself, a copy of the box score.
- `best` is the category with the largest absolute r among PTS, 3PM, REB, AST, STL and BLK. The table shows MIN apart.

## Column inventory

### gp: (merge)

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gp | Games played (first table that has GP) | count | role | 0.00 | 0.00 | 0.04 | -0.01 | -0.06 | -0.01 | 0.09 | STL -0.06 |

### adv: LeagueDashPlayerStats (Advanced)

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adv_min | Minutes per game | PG | role | 0.76 | 0.34 | 0.33 | 0.56 | 0.34 | 0.04 | 1.00 | PTS 0.76 |
| adv_e_off_rating | Estimated points scored by team per 100 poss with player on | RATE | noise | 0.19 | 0.20 | -0.02 | 0.16 | 0.10 | 0.01 | 0.03 | 3PM 0.20 |
| adv_off_rating | Team points per 100 poss with player on | RATE | noise | 0.22 | 0.22 | -0.01 | 0.19 | 0.12 | -0.00 | 0.07 | 3PM 0.22 |
| adv_e_def_rating | Estimated opp points per 100 poss with player on | RATE | noise | -0.03 | 0.00 | -0.18 | -0.00 | -0.21 | -0.15 | -0.02 | STL -0.21 |
| adv_def_rating | Opp points per 100 poss with player on | RATE | noise | -0.03 | -0.00 | -0.16 | -0.01 | -0.20 | -0.12 | -0.01 | STL -0.20 |
| adv_e_net_rating | Estimated off minus def rating | RATE | noise | 0.14 | 0.13 | 0.10 | 0.11 | 0.20 | 0.10 | 0.03 | STL 0.20 |
| adv_net_rating | Off minus def rating | RATE | noise | 0.16 | 0.15 | 0.10 | 0.13 | 0.21 | 0.08 | 0.06 | STL 0.21 |
| adv_ast_pct | Share of teammate FGM he assisted while on floor | RATE | lead:AST | 0.46 | 0.16 | 0.01 | 0.96 | 0.18 | -0.20 | 0.39 | AST 0.96 |
| adv_ast_to | Assists per turnover | RATE | eff | -0.14 | 0.05 | -0.25 | 0.29 | 0.06 | -0.29 | -0.11 | AST 0.29 |
| adv_ast_ratio | Assists per 100 of his possessions | RATE | eff | -0.17 | -0.17 | -0.12 | 0.68 | 0.12 | -0.22 | -0.01 | AST 0.68 |
| adv_oreb_pct | Share of available off rebounds he got | RATE | lead:REB | -0.23 | -0.58 | 0.72 | -0.29 | -0.09 | 0.58 | -0.17 | REB 0.72 |
| adv_dreb_pct | Share of available def rebounds he got | RATE | lead:REB | 0.12 | -0.33 | 0.92 | 0.01 | -0.02 | 0.44 | 0.12 | REB 0.92 |
| adv_reb_pct | Share of all available rebounds he got | RATE | lead:REB | -0.01 | -0.46 | 0.93 | -0.11 | -0.05 | 0.55 | 0.01 | REB 0.93 |
| adv_tm_tov_pct | Turnovers per 100 of his plays | RATE | eff | -0.09 | -0.28 | 0.22 | 0.16 | -0.05 | 0.18 | 0.02 | 3PM -0.28 |
| adv_e_tov_pct | Estimated turnover pct | RATE | eff | -0.10 | -0.29 | 0.23 | 0.16 | -0.05 | 0.18 | 0.01 | 3PM -0.29 |
| adv_efg_pct | Effective FG% (3s worth 1.5) | RATE | eff | 0.13 | 0.13 | 0.15 | -0.08 | -0.09 | 0.15 | -0.02 | REB 0.15 |
| adv_ts_pct | True shooting % (FG+FT) | RATE | eff | 0.28 | 0.18 | 0.14 | 0.02 | -0.07 | 0.12 | 0.08 | PTS 0.28 |
| adv_usg_pct | Share of team plays he ends while on floor | RATE | role | 0.91 | 0.48 | 0.16 | 0.49 | 0.20 | -0.00 | 0.57 | PTS 0.91 |
| adv_e_usg_pct | Estimated usage % | RATE | role | 0.91 | 0.49 | 0.15 | 0.49 | 0.20 | -0.01 | 0.56 | PTS 0.91 |
| adv_e_pace | Estimated team poss per 48 with him on | RATE | role | 0.11 | 0.03 | 0.01 | 0.04 | 0.15 | -0.04 | -0.01 | STL 0.15 |
| adv_pace | Team poss per 48 with him on | RATE | role | 0.05 | 0.01 | -0.02 | 0.01 | 0.11 | -0.06 | -0.08 | STL 0.11 |
| adv_pace_per40 | Pace scaled to 40 min | RATE | noise | 0.05 | 0.01 | -0.01 | 0.01 | 0.11 | -0.06 | -0.08 | STL 0.11 |
| adv_pie | Player Impact Estimate: his share of game events | RATE | noise | 0.75 | 0.21 | 0.55 | 0.50 | 0.24 | 0.26 | 0.46 | PTS 0.75 |
| adv_poss | Possessions played | TOT | role | 0.44 | 0.20 | 0.22 | 0.31 | 0.15 | 0.01 | 0.63 | PTS 0.44 |
| adv_fgm | Field goals made | TOT | noise | 0.83 | 0.35 | 0.32 | 0.43 | 0.18 | 0.12 | 0.69 | PTS 0.83 |
| adv_fga | Field goals attempted | TOT | role | 0.81 | 0.45 | 0.19 | 0.45 | 0.18 | 0.01 | 0.70 | PTS 0.81 |
| adv_fgm_pg | FGM per game | PG | noise | 0.97 | 0.44 | 0.32 | 0.51 | 0.28 | 0.11 | 0.76 | PTS 0.97 |
| adv_fga_pg | FGA per game | PG | role | 0.95 | 0.55 | 0.19 | 0.51 | 0.31 | -0.00 | 0.76 | PTS 0.95 |
| adv_fg_pct | FG% | RATE | eff | 0.18 | -0.27 | 0.45 | 0.02 | -0.05 | 0.37 | 0.09 | REB 0.45 |
| adv_team_count | Number of teams this season (2 = traded) | count | noise | - | - | - | - | - | - | - | - |

### hustle: LeagueHustleStatsPlayer

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hustle_min | Minutes per game (hustle table) | PG | role | 0.76 | 0.34 | 0.33 | 0.56 | 0.34 | 0.04 | 1.00 | PTS 0.76 |
| hustle_contested_shots | Shots he contested | PG | lead:BLK | 0.08 | -0.34 | 0.71 | -0.11 | -0.08 | 0.72 | 0.21 | BLK 0.72 |
| hustle_contested_shots_2pt | 2-pt shots he contested | PG | lead:BLK | 0.01 | -0.39 | 0.69 | -0.18 | -0.18 | 0.75 | 0.10 | BLK 0.75 |
| hustle_contested_shots_3pt | 3-pt shots he contested | PG | noise | 0.23 | -0.05 | 0.41 | 0.10 | 0.18 | 0.32 | 0.39 | REB 0.41 |
| hustle_deflections | Passes/dribbles he tipped | PG | lead:STL | 0.12 | 0.05 | 0.11 | 0.16 | 0.78 | -0.00 | 0.21 | STL 0.78 |
| hustle_charges_drawn | Charges drawn | PG | noise | 0.16 | 0.21 | -0.17 | 0.24 | 0.03 | -0.08 | 0.13 | AST 0.24 |
| hustle_screen_assists | Screens that led directly to a teammate FGM | PG | role | -0.10 | -0.46 | 0.69 | -0.08 | -0.11 | 0.49 | -0.01 | REB 0.69 |
| hustle_screen_ast_pts | Points from those screen assists | PG | role | -0.11 | -0.47 | 0.68 | -0.07 | -0.10 | 0.48 | -0.01 | REB 0.68 |
| hustle_off_loose_balls_recovered | Loose balls recovered on offense | PG | noise | 0.18 | -0.01 | 0.20 | 0.10 | 0.17 | -0.02 | 0.20 | REB 0.20 |
| hustle_def_loose_balls_recovered | Loose balls recovered on defense | PG | lead:STL(weak) | 0.17 | 0.01 | 0.10 | 0.18 | 0.40 | 0.01 | 0.27 | STL 0.40 |
| hustle_loose_balls_recovered | All loose balls recovered | PG | lead:STL(weak) | 0.23 | 0.00 | 0.20 | 0.19 | 0.38 | -0.01 | 0.31 | STL 0.38 |
| hustle_pct_loose_balls_recovered_off | Share of his recoveries on offense | RATE | noise | -0.00 | 0.07 | 0.03 | -0.07 | -0.14 | -0.03 | -0.06 | STL -0.14 |
| hustle_pct_loose_balls_recovered_def | Share of his recoveries on defense | RATE | noise | -0.02 | -0.05 | -0.04 | 0.01 | 0.20 | 0.06 | 0.04 | STL 0.20 |
| hustle_off_boxouts | Offensive box-outs | PG | lead:REB(weak) | -0.10 | -0.40 | 0.57 | -0.12 | -0.08 | 0.36 | -0.03 | REB 0.57 |
| hustle_def_boxouts | Defensive box-outs | PG | lead:REB(weak) | 0.08 | -0.27 | 0.65 | -0.11 | -0.10 | 0.42 | 0.15 | REB 0.65 |
| hustle_box_outs | All box-outs | PG | lead:REB(weak) | 0.03 | -0.36 | 0.71 | -0.13 | -0.11 | 0.46 | 0.11 | REB 0.71 |
| hustle_box_out_player_team_rebs | Box-outs where his team got the board | PG | noise | 0.03 | -0.36 | 0.71 | -0.13 | -0.11 | 0.46 | 0.11 | REB 0.71 |
| hustle_box_out_player_rebs | Box-outs where he got the board | PG | lead:REB(weak) | 0.06 | -0.35 | 0.78 | -0.09 | -0.11 | 0.49 | 0.09 | REB 0.78 |
| hustle_pct_box_outs_off | Share of box-outs on offense | RATE | noise | -0.10 | -0.27 | 0.25 | 0.00 | -0.07 | 0.12 | -0.04 | 3PM -0.27 |
| hustle_pct_box_outs_def | Share of box-outs on defense | RATE | noise | -0.01 | 0.16 | -0.17 | -0.09 | -0.07 | -0.08 | 0.02 | REB -0.17 |
| hustle_pct_box_outs_team_reb | Share of box-outs that won team the board | RATE | noise | -0.16 | -0.11 | 0.09 | -0.17 | -0.18 | 0.04 | -0.06 | STL -0.18 |
| hustle_pct_box_outs_reb | Share of box-outs that he rebounded | RATE | noise | 0.00 | -0.14 | 0.37 | -0.07 | -0.10 | 0.16 | -0.04 | REB 0.37 |

### pass: PtStats Passing

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pass_min | Minutes per game (passing table) | PG | role | 0.76 | 0.34 | 0.33 | 0.56 | 0.34 | 0.04 | 1.00 | PTS 0.76 |
| pass_passes_made | Passes made | PG | role | 0.53 | 0.18 | 0.22 | 0.88 | 0.29 | -0.12 | 0.66 | AST 0.88 |
| pass_passes_received | Passes received | PG | role | 0.70 | 0.39 | 0.00 | 0.89 | 0.28 | -0.20 | 0.69 | AST 0.89 |
| pass_ast | Assists (tracking count) | PG | = AST | 0.52 | 0.19 | 0.07 | 1.00 | 0.25 | -0.17 | 0.56 | AST 1.00 |
| pass_ft_ast | Passes that led to fouled shooter who made a FT | PG | lead:AST(weak) | 0.40 | 0.20 | -0.02 | 0.74 | 0.27 | -0.18 | 0.46 | AST 0.74 |
| pass_secondary_ast | Hockey assists (pass before the assist) | PG | noise | 0.64 | 0.41 | -0.02 | 0.67 | 0.23 | -0.14 | 0.56 | AST 0.67 |
| pass_potential_ast | Passes to a shooter who shot (made or missed or fouled) | PG | lead:AST | 0.55 | 0.21 | 0.06 | 0.96 | 0.27 | -0.18 | 0.59 | AST 0.96 |
| pass_ast_points_created | Points from his assists | PG | = AST | 0.52 | 0.18 | 0.08 | 1.00 | 0.25 | -0.17 | 0.56 | AST 1.00 |
| pass_ast_adj | AST + FT AST + secondary AST | PG | lead:AST | 0.56 | 0.24 | 0.05 | 0.99 | 0.27 | -0.18 | 0.59 | AST 0.99 |
| pass_ast_to_pass_pct | Assists per pass | RATE | eff | 0.34 | 0.15 | -0.14 | 0.77 | 0.14 | -0.19 | 0.25 | AST 0.77 |
| pass_ast_to_pass_pct_adj | Adjusted assists per pass | RATE | eff | 0.41 | 0.23 | -0.17 | 0.75 | 0.18 | -0.21 | 0.31 | AST 0.75 |

### reb: PtStats Rebounding

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reb_min | Minutes per game (rebound table) | PG | role | 0.76 | 0.36 | 0.32 | 0.55 | 0.33 | 0.03 | 0.99 | PTS 0.76 |
| reb_oreb | Offensive rebounds | PG | = OREB | -0.09 | -0.51 | 0.80 | -0.21 | 0.02 | 0.55 | 0.03 | REB 0.80 |
| reb_oreb_contest | Contested off rebounds (opp within 3.5 ft) | PG | noise | -0.07 | -0.50 | 0.79 | -0.19 | 0.03 | 0.56 | 0.01 | REB 0.79 |
| reb_oreb_uncontest | Uncontested off rebounds | PG | noise | -0.11 | -0.33 | 0.52 | -0.17 | 0.01 | 0.33 | 0.06 | REB 0.52 |
| reb_oreb_contest_pct | Share of his off rebounds that were contested | RATE | noise | -0.07 | -0.33 | 0.50 | -0.17 | 0.01 | 0.37 | -0.07 | REB 0.50 |
| reb_oreb_chances | Off rebound chances (he was within 3.5 ft of the ball) | PG | lead:REB | -0.10 | -0.53 | 0.77 | -0.21 | -0.00 | 0.56 | 0.02 | REB 0.77 |
| reb_oreb_chance_pct | OREB per OREB chance | RATE | eff | -0.10 | -0.17 | 0.25 | -0.18 | 0.04 | 0.12 | -0.08 | REB 0.25 |
| reb_oreb_chance_defer | Off chances he left to a teammate | PG | noise | -0.16 | -0.37 | 0.51 | -0.15 | 0.05 | 0.23 | -0.02 | REB 0.51 |
| reb_oreb_chance_pct_adj | OREB per (chance - deferred) | RATE | eff | -0.13 | -0.13 | 0.19 | -0.18 | 0.05 | 0.06 | -0.10 | REB 0.19 |
| reb_avg_oreb_dist | Mean distance from rim of his off rebounds (ft) | RATE | role | 0.15 | 0.44 | -0.53 | 0.15 | 0.02 | -0.42 | 0.08 | REB -0.53 |
| reb_dreb | Defensive rebounds | PG | = DREB | 0.38 | -0.15 | 0.94 | 0.21 | 0.11 | 0.41 | 0.44 | REB 0.94 |
| reb_dreb_contest | Contested def rebounds | PG | noise | 0.23 | -0.26 | 0.85 | -0.01 | -0.03 | 0.51 | 0.27 | REB 0.85 |
| reb_dreb_uncontest | Uncontested def rebounds | PG | noise | 0.42 | -0.06 | 0.86 | 0.32 | 0.19 | 0.28 | 0.49 | REB 0.86 |
| reb_dreb_contest_pct | Share of his def rebounds contested | RATE | noise | -0.02 | -0.29 | 0.46 | -0.25 | -0.15 | 0.42 | -0.00 | REB 0.46 |
| reb_dreb_chances | Def rebound chances | PG | lead:REB | 0.35 | -0.19 | 0.92 | 0.17 | 0.08 | 0.48 | 0.40 | REB 0.92 |
| reb_dreb_chance_pct | DREB per DREB chance | RATE | eff | 0.21 | 0.00 | 0.36 | 0.17 | 0.11 | 0.02 | 0.26 | REB 0.36 |
| reb_dreb_chance_defer | Def chances he left to a teammate | PG | noise | 0.13 | -0.26 | 0.70 | -0.01 | -0.01 | 0.51 | 0.21 | REB 0.70 |
| reb_dreb_chance_pct_adj | DREB per (chance - deferred) | RATE | eff | 0.10 | -0.09 | 0.37 | 0.06 | 0.06 | 0.12 | 0.19 | REB 0.37 |
| reb_avg_dreb_dist | Mean distance of his def rebounds (ft) | RATE | role | 0.04 | 0.38 | -0.70 | 0.20 | 0.07 | -0.52 | 0.03 | REB -0.70 |
| reb_reb | Total rebounds | PG | = REB | 0.24 | -0.31 | 1.00 | 0.07 | 0.09 | 0.52 | 0.33 | REB 1.00 |
| reb_reb_contest | Contested rebounds | PG | noise | 0.09 | -0.42 | 0.91 | -0.11 | 0.00 | 0.59 | 0.16 | REB 0.91 |
| reb_reb_uncontest | Uncontested rebounds | PG | noise | 0.35 | -0.14 | 0.89 | 0.24 | 0.17 | 0.33 | 0.45 | REB 0.89 |
| reb_reb_contest_pct | Share of his rebounds contested | RATE | noise | -0.13 | -0.45 | 0.58 | -0.33 | -0.08 | 0.52 | -0.08 | REB 0.58 |
| reb_reb_chances | All rebound chances | PG | lead:REB | 0.18 | -0.36 | 0.95 | 0.01 | 0.05 | 0.57 | 0.27 | REB 0.95 |
| reb_reb_chance_pct | REB per chance | RATE | eff | 0.21 | 0.02 | 0.39 | 0.15 | 0.13 | 0.04 | 0.25 | REB 0.39 |
| reb_reb_chance_defer | Chances he left to a teammate | PG | noise | 0.06 | -0.33 | 0.73 | -0.06 | 0.01 | 0.50 | 0.16 | REB 0.73 |
| reb_reb_chance_pct_adj | REB per (chance - deferred) | RATE | eff | 0.15 | 0.02 | 0.35 | 0.09 | 0.11 | 0.05 | 0.21 | REB 0.35 |
| reb_avg_reb_dist | Mean distance of his rebounds (ft) | RATE | role | 0.03 | 0.41 | -0.73 | 0.18 | 0.04 | -0.53 | 0.01 | REB -0.73 |

### def: PtStats Defense

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| def_min | Minutes per game (defense table) | PG | role | 0.76 | 0.34 | 0.33 | 0.56 | 0.34 | 0.04 | 1.00 | PTS 0.76 |
| def_stl | Steals | PG | = STL | 0.26 | 0.11 | 0.09 | 0.25 | 1.00 | -0.06 | 0.34 | STL 1.00 |
| def_blk | Blocks | PG | = BLK | 0.05 | -0.29 | 0.53 | -0.16 | -0.07 | 1.00 | 0.05 | BLK 1.00 |
| def_dreb | Defensive rebounds | PG | = DREB | 0.38 | -0.17 | 0.95 | 0.21 | 0.11 | 0.42 | 0.44 | REB 0.95 |
| def_def_rim_fgm | Opp FGM at rim (<6 ft) while he defended | PG | noise | 0.12 | -0.27 | 0.60 | 0.04 | 0.02 | 0.45 | 0.29 | REB 0.60 |
| def_def_rim_fga | Opp FGA at rim while he defended | PG | lead:BLK | 0.10 | -0.34 | 0.69 | -0.03 | -0.07 | 0.63 | 0.23 | REB 0.69 |
| def_def_rim_fg_pct | Opp FG% at rim vs him | RATE | eff | 0.01 | 0.18 | -0.29 | 0.12 | 0.24 | -0.39 | 0.04 | BLK -0.39 |

### touch: PtStats Possessions

| column | meaning | unit | tag | r PTS | r 3PM | r REB | r AST | r STL | r BLK | r MIN | best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| touch_min | Minutes per game (possessions table) | PG | role | 0.76 | 0.34 | 0.33 | 0.56 | 0.34 | 0.04 | 1.00 | PTS 0.76 |
| touch_points | Points | PG | = PTS | 1.00 | 0.54 | 0.24 | 0.52 | 0.26 | 0.04 | 0.76 | PTS 1.00 |
| touch_touches | Touches (times he got the ball) | PG | role | 0.74 | 0.29 | 0.25 | 0.87 | 0.28 | -0.07 | 0.76 | AST 0.87 |
| touch_front_ct_touches | Front-court touches | PG | role | 0.73 | 0.20 | 0.52 | 0.61 | 0.24 | 0.12 | 0.78 | PTS 0.73 |
| touch_time_of_poss | Minutes holding the ball | PG | role | 0.62 | 0.36 | -0.11 | 0.82 | 0.21 | -0.23 | 0.58 | AST 0.82 |
| touch_avg_sec_per_touch | Seconds per touch | RATE | role | 0.36 | 0.31 | -0.38 | 0.58 | 0.13 | -0.36 | 0.28 | AST 0.58 |
| touch_avg_drib_per_touch | Dribbles per touch | RATE | role | 0.43 | 0.35 | -0.40 | 0.64 | 0.22 | -0.41 | 0.30 | AST 0.64 |
| touch_pts_per_touch | Points per touch | RATE | eff | 0.54 | 0.46 | 0.01 | -0.27 | 0.03 | 0.11 | 0.21 | PTS 0.54 |
| touch_elbow_touches | Elbow touches | PG | role | 0.21 | -0.38 | 0.70 | 0.15 | 0.02 | 0.46 | 0.24 | REB 0.70 |
| touch_post_touches | Post-up touches | PG | role | 0.45 | -0.14 | 0.59 | 0.21 | 0.13 | 0.27 | 0.37 | REB 0.59 |
| touch_paint_touches | Paint touches | PG | lead:REB/BLK(proxy) | 0.02 | -0.53 | 0.82 | -0.15 | -0.04 | 0.61 | 0.09 | REB 0.82 |
| touch_pts_per_elbow_touch | Points per elbow touch | RATE | eff | 0.30 | 0.16 | 0.07 | -0.05 | 0.05 | 0.03 | 0.19 | PTS 0.30 |
| touch_pts_per_post_touch | Points per post touch | RATE | eff | 0.17 | 0.05 | 0.13 | -0.10 | 0.02 | 0.11 | 0.05 | PTS 0.17 |
| touch_pts_per_paint_touch | Points per paint touch | RATE | eff | 0.31 | 0.03 | 0.16 | -0.07 | -0.01 | 0.21 | 0.24 | PTS 0.31 |

## Role and usage change signals

The file is one snapshot of the season to date. A role change needs two dated snapshots, or a split by game or by the last N games, which the collector does not ask for. These columns are the ones to compare between snapshots:

| column | why | r MIN | r PTS |
|---|---|---|---|
| adv_min | minutes, the base of all counting stats | 1.00 | 0.76 |
| adv_usg_pct | share of plays he ends. a jump = bigger role | 0.57 | 0.91 |
| adv_e_usg_pct | same, estimated | 0.56 | 0.91 |
| touch_touches | ball volume. r AST 0.87 | 0.76 | 0.74 |
| touch_time_of_poss | on-ball time. r AST 0.82: on-ball creator | 0.58 | 0.62 |
| touch_front_ct_touches | half-court involvement | 0.78 | 0.73 |
| touch_avg_sec_per_touch | creator vs. finisher style | 0.28 | 0.36 |
| touch_avg_drib_per_touch | creator vs. finisher style | 0.30 | 0.43 |
| pass_passes_made | playmaking volume | 0.66 | 0.53 |
| pass_passes_received | offense runs through him | 0.69 | 0.70 |
| adv_fga_pg | shot volume | 0.76 | 0.95 |
| adv_poss | TOTAL possessions. divide by gp | 0.63 | 0.44 |
| adv_pace | team pace while on court. more poss = more of everything (r with cats ~0) | -0.08 | 0.05 |
| adv_e_pace | estimated pace | -0.01 | 0.11 |
| touch_paint_touches / touch_post_touches / touch_elbow_touches | where he gets the ball. big-man role shifts | 0.09 | 0.02 |
| hustle_screen_assists | screener role (bigs) | -0.01 | -0.10 |

## Due for more and due for less

Method: the players with 20 or more minutes per game and 5 or more games. A linear fit across the pool gives actual = a + b x indicator. The gap is actual minus fit. A negative gap means "due for more".

A gap mixes luck and real skill. For example, elite shot-blockers convert contests to blocks at a higher rate every year. A large positive gap on a known specialist is skill, not luck. The luck design of 2026-11-18 handles this with a baseline from the 2025-26 season.

3PM has no NBA.com indicator in this file. The indicator is the box-score 3PA x the league 3P% (0.352).

### STL: stl vs hustle_deflections (r = 0.77, n = 212, fit stl = 0.19 + 0.390 x)

| side | player | team | gp | MPG | hustle_deflections | stl | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Ryan Rollins | MIL | 13 | 23.8 | 3.23 | 0.77 | 1.45 | -0.68 |
| more | Alex Caruso | OKC | 11 | 20.2 | 4.40 | 1.27 | 1.90 | -0.63 |
| more | Rudy Gobert | MIN | 14 | 28.9 | 2.00 | 0.36 | 0.97 | -0.61 |
| more | Oso Ighodaro | PHX | 11 | 22.7 | 1.45 | 0.18 | 0.75 | -0.57 |
| more | Collin Murray-Boyles | TOR | 13 | 25.0 | 3.69 | 1.08 | 1.63 | -0.55 |
| less | Christian Braun | DEN | 12 | 33.7 | 2.50 | 2.17 | 1.16 | +1.00 |
| less | Zion Williamson | NOP | 14 | 32.1 | 2.93 | 2.00 | 1.33 | +0.67 |
| less | Cedric Coward | MEM | 13 | 28.7 | 1.77 | 1.46 | 0.88 | +0.58 |
| less | Nolan Traore | BKN | 12 | 22.6 | 1.27 | 1.25 | 0.68 | +0.57 |
| less | Collin Gillespie | PHX | 13 | 24.8 | 2.62 | 1.77 | 1.21 | +0.56 |

### BLK: blk vs hustle_contested_shots_2pt (r = 0.77, n = 212, fit blk = -0.01 + 0.227 x)

| side | player | team | gp | MPG | hustle_contested_shots_2pt | blk | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Domantas Sabonis | SAC | 12 | 34.0 | 4.58 | 0.08 | 1.03 | -0.95 |
| more | Wendell Carter Jr. | ORL | 13 | 32.3 | 7.00 | 0.77 | 1.58 | -0.81 |
| more | Paul Reed | DET | 13 | 26.6 | 6.77 | 0.77 | 1.53 | -0.76 |
| more | Isaiah Hartenstein | OKC | 14 | 24.9 | 4.21 | 0.29 | 0.95 | -0.66 |
| more | Brook Lopez | LAC | 13 | 24.4 | 7.00 | 0.92 | 1.58 | -0.66 |
| less | Victor Wembanyama | SAS | 15 | 30.0 | 9.07 | 4.07 | 2.05 | +2.02 |
| less | Peyton Watson | CLE | 12 | 27.5 | 3.33 | 1.50 | 0.75 | +0.75 |
| less | Matisse Thybulle | LAL | 15 | 24.9 | 0.93 | 0.93 | 0.20 | +0.73 |
| less | Keon Ellis | BKN | 12 | 21.2 | 1.27 | 0.92 | 0.28 | +0.64 |
| less | Myles Turner | MIL | 13 | 27.1 | 6.38 | 2.08 | 1.44 | +0.64 |

### BLK (rim): blk vs def_def_rim_fga (r = 0.67, n = 212, fit blk = -0.03 + 0.246 x)

| side | player | team | gp | MPG | def_def_rim_fga | blk | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Domantas Sabonis | SAC | 12 | 34.0 | 6.80 | 0.08 | 1.65 | -1.56 |
| more | Paul Reed | DET | 13 | 26.6 | 5.70 | 0.77 | 1.38 | -0.61 |
| more | Joel Embiid | PHI | 12 | 31.5 | 5.80 | 0.83 | 1.40 | -0.57 |
| more | Julius Randle | BKN | 13 | 32.9 | 3.30 | 0.23 | 0.79 | -0.55 |
| more | Trey Murphy III | NOP | 9 | 32.8 | 3.20 | 0.22 | 0.76 | -0.54 |
| less | Victor Wembanyama | SAS | 15 | 30.0 | 6.50 | 4.07 | 1.57 | +2.49 |
| less | Donovan Clingan | POR | 14 | 25.7 | 4.70 | 2.29 | 1.13 | +1.16 |
| less | Aday Mara | OKC | 14 | 21.6 | 3.60 | 1.71 | 0.86 | +0.85 |
| less | Matisse Thybulle | LAL | 15 | 24.9 | 0.50 | 0.93 | 0.10 | +0.84 |
| less | Mo Bamba | UTA | 11 | 20.7 | 3.80 | 1.73 | 0.91 | +0.82 |

### AST: ast vs pass_potential_ast (r = 0.97, n = 212, fit ast = 0.09 + 0.537 x)

| side | player | team | gp | MPG | pass_potential_ast | ast | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Nolan Traore | BKN | 12 | 22.6 | 7.70 | 2.67 | 4.23 | -1.56 |
| more | Brandon Miller | CHA | 12 | 30.5 | 6.70 | 2.50 | 3.69 | -1.19 |
| more | Ryan Rollins | MIL | 13 | 23.8 | 9.00 | 3.92 | 4.92 | -1.00 |
| more | Dennis Schroder | CHA | 9 | 30.0 | 10.60 | 4.89 | 5.78 | -0.89 |
| more | Shai Gilgeous-Alexander | OKC | 14 | 33.1 | 9.60 | 4.36 | 5.25 | -0.89 |
| less | Javon Small | MEM | 7 | 22.0 | 7.10 | 5.43 | 3.90 | +1.53 |
| less | Davion Mitchell | MIA | 14 | 35.5 | 14.20 | 9.21 | 7.72 | +1.50 |
| less | Andrew Nembhard | IND | 11 | 33.4 | 12.20 | 7.73 | 6.64 | +1.08 |
| less | Day'Ron Sharpe | BKN | 13 | 23.8 | 5.70 | 4.23 | 3.15 | +1.08 |
| less | Luka Doncic | LAL | 13 | 36.3 | 12.30 | 7.69 | 6.70 | +0.99 |

### REB: reb vs reb_reb_chances (r = 0.95, n = 212, fit reb = -0.42 + 0.567 x)

| side | player | team | gp | MPG | reb_reb_chances | reb | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Moussa Diabate | CHA | 12 | 29.6 | 23.80 | 10.25 | 13.08 | -2.83 |
| more | Daniel Gafford | DAL | 14 | 21.1 | 13.20 | 5.07 | 7.07 | -2.00 |
| more | Patrick Williams | CHI | 6 | 22.7 | 9.80 | 3.17 | 5.14 | -1.98 |
| more | Caleb Martin | DAL | 10 | 21.7 | 9.40 | 3.10 | 4.92 | -1.82 |
| more | Toumani Camara | POR | 14 | 29.1 | 9.90 | 3.43 | 5.20 | -1.77 |
| less | Ausar Thompson | DET | 12 | 27.8 | 12.30 | 8.67 | 6.56 | +2.11 |
| less | Giannis Antetokounmpo | MIA | 14 | 32.2 | 19.10 | 12.50 | 10.42 | +2.08 |
| less | Karl-Anthony Towns | NYK | 14 | 32.7 | 22.30 | 14.07 | 12.23 | +1.84 |
| less | LeBron James | PHI | 11 | 32.5 | 11.10 | 7.18 | 5.88 | +1.30 |
| less | Obi Toppin | IND | 11 | 20.1 | 6.30 | 4.36 | 3.16 | +1.21 |

### 3PM: fg3m vs exp3 (r = 0.95, n = 212, fit fg3m = -0.12 + 1.090 x)

| side | player | team | gp | MPG | exp3 | fg3m | fit | gap |
|---|---|---|---|---|---|---|---|---|
| more | Brandon Miller | CHA | 12 | 30.5 | 3.58 | 2.75 | 3.77 | -1.02 |
| more | Jalen Johnson | ATL | 11 | 34.4 | 1.41 | 0.73 | 1.41 | -0.68 |
| more | Scoot Henderson | POR | 14 | 22.2 | 1.51 | 0.86 | 1.52 | -0.66 |
| more | Joel Embiid | PHI | 12 | 31.5 | 1.17 | 0.50 | 1.15 | -0.65 |
| more | Dennis Schroder | CHA | 9 | 30.0 | 1.37 | 0.78 | 1.37 | -0.59 |
| less | Stephen Curry | GSW | 10 | 26.5 | 3.31 | 4.30 | 3.48 | +0.82 |
| less | Jamal Murray | DEN | 12 | 36.3 | 2.55 | 3.42 | 2.66 | +0.76 |
| less | Cam Spencer | MEM | 14 | 21.7 | 1.23 | 1.93 | 1.22 | +0.71 |
| less | Grayson Allen | CHA | 13 | 27.2 | 2.60 | 3.38 | 2.71 | +0.68 |
| less | Derrick Jones Jr. | LAC | 12 | 28.8 | 1.38 | 2.00 | 1.38 | +0.62 |

## Data oddities

- 6 minute columns (adv/hustle/pass/reb/def/touch_min) are the same stat. r = 0.99-1.00. reb_min mean is higher because 14 low-minute players have no rebound row.
- adv_fgm, adv_fga, adv_poss are season TOTALS although the request asks PerGame (NBA.com behavior). adv_fgm_pg / adv_fga_pg are the per-game forms.
- Exact duplicates of box categories: def_stl, def_blk, reb_reb, reb_oreb, reb_dreb, def_dreb, pass_ast, touch_points (r 1.00 with box). pass_ast_points_created is about 2.6 x AST (r 1.00).
- hustle_box_outs and hustle_box_out_player_team_rebs are nearly the same number (identical r).
- Small-sample extremes in low-minute players: adv_ast_pct max 1.0, adv_usg_pct max 0.5, adv_efg_pct max 1.5, adv_off_rating max 200, net rating max 118. Filter on minutes before using any RATE column.
- adv_team_count = 2 for traded players (only values 1 and 2). gp has 15 distinct values (max 15).
- hustle_charges_drawn has 19 distinct values, mean 0.025: near-zero signal.
- Negative r with 3PM for all rebound, box-out, rim and paint columns: a big-man axis, not a 3PM signal.
- Pace columns have r ~0 with every category at this sample size.
