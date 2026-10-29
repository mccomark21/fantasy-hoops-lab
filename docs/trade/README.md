# Trade tool

## Goal

The trade tool suggests 1-for-1 trades with the other fantasy teams of the league. A suggestion raises your playoff starts in weeks 19 to 21 and keeps your season value. The design is in [docs/wiki/trade-tool-design-2026-10-28.md](../wiki/trade-tool-design-2026-10-28.md).

## Usage

```sh
python -m fantasyhoops.trade                # Read Yahoo, score the trades, write the page and publish it to /trade/.
python -m fantasyhoops.trade --no-publish   # Write output/trade/index.html. Do not publish.
python -m fantasyhoops.trade --no-cache     # Read each rostered page from Yahoo again.
python -m fantasyhoops.trade.reads          # The live check of the Yahoo reads (#148). It writes only the cache.
```

The run opens Edge with the saved Yahoo sign-in of the adds planner. It is its own command, not part of the planning run.

The terminal shows:

1. The page path.
2. The count of suggestions and the best suggestion, or "No trade raises your playoff starts."
3. The publish line: the URL of the page, or "Publish: skipped (--no-publish)."
4. The warnings: no trade deadline, rows of the rostered list with no team link, your players with no value.

## Publish

The run publishes the page to `/trade/` of the site, for example `https://mccomark21.github.io/fantasy-hoops-lab/trade/`. GitHub can take a few minutes to show the new page.

1. The site menu has the tab "Trades" after "Adds plan" (`publish.TOOLS`, #151).
2. The trade run does not make the roster page. Its publish keeps the home page at `/` (`publish.publish()` with `keep_home=True`). If gh-pages has no home page, the root gets the list of the tools.
3. The planning run of the adds planner keeps the `/trade/` folder, because `trade` is in `publish.TOOLS`.
4. Each page carries its own site menu. The home page and the adds page show the Trades tab after their next run.

## Kept set

The playoff starts of a team count only its kept set:

1. Before a trade, the kept set is the top 8 players of the team by value (`[trade] kept`).
2. The untouchable players (`[trade] untouchable`, Cooper Flagg) and the IL players are always in your kept set.
3. In a trade, the player you get takes the spot of the player you give. The run does not rank the kept set again after the trade (Decision comment of 2026-10-28 on #150).
4. If the player you give is not in your kept set, the trade does not change your starts.
5. The partner side uses the same rule. The rostered list does not show the IL slots of a partner, so the starts of a partner are an estimate.

The kept set belongs to the trade tool. It does not change the `stream_spots` of the adds planner.

## Suggestions

`trade/suggest.py` scores each 1-for-1 pair of your players (not the untouchable players) and the players of the other teams.

1. Both players must have a value. A pair with no value on one side is not a suggestion.
2. The value of the player you get must be in the value band: from give − 5% × |give| to give + 10% × |give| (`[trade] value_band`). The band works for values below 0.
3. The trade must raise your total playoff starts by 1 or more.
4. The rank: the gain in total starts, then min(weeks after) − min(weeks before), then the larger value change for you.
5. At most 3 rows for each player you give (`[trade] per_player`), and 20 rows in all (`[trade] rows`).

The playoff starts use the home page rules exactly: `core/home.py` `lineup_fit()` on the days of `home.playoff_days()`. The slots are `[league] slots` and one Util slot. The lineup order is the custom rank of `draft/rankings.py`, and a player with no rank goes last. A rest night on a back-to-back (`rests_b2b` of the `[risk] file`) is not a game. IL and injured players count, with their Yahoo status on the page.

## Value

The value of each player on both sides is the blended value of the adds planner (`adds/blend.py`), from both views of the rostered list. A player with no blended value uses his preseason `pg_value` (`adds/drops.py` `season_values()`), and the page marks it "pre". The page shows the preseason value ("Pre") of each player next to his value ("Val").

## Data

| Data | Source | Reader |
|---|---|---|
| Your roster and IL slots | Your Yahoo team page, from Edge | `adds/readers.py` `read_roster()` |
| The rostered list, projected view (next 7 days) | `players?status=T&...&stat1=S_PS7` | `trade/rostered.py` |
| The rostered list, recent view (last 14 days) | `players?status=T&...&stat1=S_AL14` | `trade/rostered.py` |
| The trade deadline ("Trade End Date") | The league settings page, `settings` | `trade/deadline.py` |
| The playoff days | `data/schedule.csv` (`python -m fantasyhoops.fetch.espn`) | `core/home.py` `playoff_days()` |
| The custom rank | The projections file and `data/` files of the draft tools | `adds/home.py` `read_ranks()` |
| The preseason value | The newest projections file | `adds/drops.py` `season_values()` |
| The rest list | `[risk] file` | `draft/rankings.py` `load_risk()` |

Without `data/schedule.csv`, the run stops with a message that names the file and the fetch command.

The rostered list reader:

1. Reads all pages of each view, until a page has no "Next 25" link.
2. Takes the fantasy team of a row from the team link (`/nba/<league>/<team ID>`), not from the team name. A team name can change during the season.
3. Reads the name, the NBA team, the positions and the status with `read_player()` of `adds/readers.py`.
4. Reads only the projected view while `[adds] recent_skip_weight` skips the recent view (`lists.skips_recent_view()`).

The trade run keeps the rows of your team too, because your players need their blended values. The live check (`trade.reads`) drops them.

The trade deadline reader finds the label "Trade End Date" on the league settings page and reads the first date after it. If the page has no such date, the run continues with no deadline, and a warning names the cached page.

The fixtures in `tests/trade/fixtures/` are hand-made in the shape of the Yahoo players table. They hold no names of managers.

## Page cache

The run keeps the rostered pages and the league settings page in the same-day cache, kind "rostered" (`output/adds/cache/rostered/<YYYY-MM-DD>/`). A second run on the same day reads these pages from the cache. The team page never goes through the cache, because your roster can change during the day. `--no-cache` reads each rostered page from Yahoo again and writes it over the cached page.

The page shows the read time of the rostered pages under the table, for example "Rosters: 16 pages from the cache of 2026-10-28 09:14." If a fix of a reader is necessary, use the cached pages.

## Run time

The run times its steps in `output/trade/timings.csv` with `adds/timing.py`: "Local files", "Yahoo reads" (with the sub-steps "team page" and "rostered list and settings"), "Score" and "Page". The `days`, `open_days` and `adds_left` columns stay empty, because the trade run has no planning window.

The targets: 15 seconds or less with a full cache, 60 seconds or less with no cache.

## Page

`trade/page.py` writes `output/trade/index.html` in the look that the owner picked on #149 (look 3). The page uses `publish.shell()`, the `lab-t` table and `band_style()`.

1. The header shows the trade deadline and the days to it, your playoff starts now and the time of the run.
2. A filter row of the players you give sits above the table. A press on a chip shows only the trades of that player.
3. The table has the players you give and get, the partner team, the playoff starts of each week and the total, and the value change of both teams.
4. Each week cell shows the new count, the change and a small bar. A blue row above the trades shows your starts now.
5. Below 940px of content, a row list replaces the table.
6. The line under the table starts with "Starts count your 8 kept players."
7. The trade builder sits under the table. See [Builder](#builder).

## Builder

The trade builder sits under the suggestions table (#152). It computes a custom trade in the browser, for example 2-for-1, and shows its effect on both teams.

1. Pick one partner team. A new partner clears the players you get.
2. Pick the players you give and the players you get. The untouchable players cannot be given.
3. When you get more players than you give, pick your drops. The builder first picks your lowest value players. It never offers an untouchable player.
4. When you give more players than you get, your open spot stays empty: "1 open roster spot: a free agent can fill it."
5. When the partner gets more players than he gives, he drops his lowest value players that are not on IL. A player with no value goes first. He never drops a player that he gets in the trade. The page names each drop.
6. When you get more players than you give, the partner has an open spot, and the page says so.
7. A click on a suggestion row (or on its rank button) loads that trade into the builder. The row shows as selected until you change the trade.

The result table shows both teams: the playoff starts of each week and the total, now and after the trade, and the value change.

- The kept set rule is the rule of [Kept set](#kept-set). The players that a team gives and drops leave its kept set. The players that it gets take the freed spots, the highest value first. A freed spot with no player stays empty.
- Your value change is sum(get) − sum(give) − sum(your drops). An open spot adds 0. A player with no value adds 0.
- The band verdict (in the band, below the band, above the band) shows only for equal counts. It compares the value sums.
- The partner rows are marked "est.", because the rostered list does not show the IL slots of a partner.

The suggestions table shows the partner starts too: the total before and after, marked "Est.", under the partner name. A text for a screen reader gives the starts of each week. The row list shows the starts of each week, before and after.

The page inlines `draft/team_builder.js` and `trade/trade_builder.js`, as the draft board does. `trade_builder.js` holds the kept set and the drop rules, and calls `scoreCore()` of `team_builder.js` with value = −rank. So the engine starts the players in the lineup order of the home page. `team_builder.js` has no trade code. `trade/builder.py` has the same rules in Python. `tests/trade/test_parity.py` runs both in Node and Python on random rosters and compares the starts, the drops, the open spots and the value changes.

## Configuration

The `[trade]` section of `config.toml`:

| Key | Default | Meaning |
|---|---|---|
| `untouchable` | `["Cooper Flagg"]` | The players that the tool never offers. They are always in your kept set. |
| `value_band` | `[0.95, 1.10]` | The value band of the player you get, as parts of the value you give. |
| `kept` | `8` | The players of a team that the playoff starts count. |
| `per_player` | `3` | The suggestions for each player you give, at most. |
| `rows` | `20` | The suggestions in all, at most. |

The section has no deadline value. The run reads the trade deadline from Yahoo.

## Terms

| Term | Meaning |
|---|---|
| Kept set | The players of a team that its playoff starts count. See [Kept set](#kept-set). |
| Playoff starts | The started games of a team in the playoff weeks, with the home page rules. |
| Value band | The range of values of the player you get, from the value you give. |
| Untouchable | A player that the tool never offers in a trade. |
| Partner | The other fantasy team of a trade. |
| Pre | The preseason `pg_value` of a player. As a mark, it says that the value is the preseason value, because he has no blended value. |

## Decisions

- On 2026-10-28, the owner decided: the trade targets come from the rostered list, the tool is its own command, and the value is the blended value with the preseason value next to it (owner decisions 1, 2 and 13 of the design page).
- On 2026-10-28, the owner decided: the playoff starts count the top 8 players by value, with Flagg and the IL players always in.
- On 2026-10-28, the owner decided: the player you get takes the spot of the player you give in the kept set. This supersedes "the top 8 after the trade" (Decision comment on #150).
- On 2026-10-28, the owner picked look 3 of the prototype round (#149).
- On 2026-10-28, the owner decided: the trade deadline comes from the Yahoo league settings, not from a config value.
- On 2026-10-29, the owner decided: the page shows the partner starts, marked "est.", for the suggestions and for a custom trade (Decision comment on #152).
- On 2026-10-29, the builder of #152 made the build choices of the builder (Decision comment on #152).
