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
3. The offered players and one line for each offered player with no suggestion. See [Offer list](#offer-list).
4. The publish line: the URL of the page, or "Publish: skipped (--no-publish)."
5. The warnings: no trade deadline, rows of the rostered list with no team link, your players with no value, names of the offer list that are not on your roster, and the players with no match in a data file. See [Edge states](#edge-states).

## Publish

The run publishes the page to `/trade/` of the site, for example `https://mccomark21.github.io/fantasy-hoops-lab/trade/`. GitHub can take a few minutes to show the new page.

1. The site menu has the tab "Trades" after "Adds plan" (`publish.TOOLS`, #151).
2. The trade run does not make the Roster page. Its publish keeps the `/roster/` folder, because `roster` is in `publish.TOOLS` (#172). Each publish writes the Home page at `/`.
3. The planning run of the adds planner keeps the `/trade/` folder, because `trade` is in `publish.TOOLS`.
4. Each page carries its own site menu. The Roster page and the adds page show the Trades tab after their next run.

## Kept set

The playoff starts of a team count only its kept set:

1. Before a trade, the kept set is the top 8 players of the team by value (`[trade] kept`).
2. The untouchable players (`[trade] untouchable`, Cooper Flagg) and the IL players are always in your kept set.
3. In a trade, the player you get takes the spot of the player you give. The run does not rank the kept set again after the trade (Decision comment of 2026-10-28 on #150).
4. If the player you give is not in your kept set, the trade does not change your starts.
5. The partner side uses the same rule. The rostered list does not show the IL slots of a partner, so the starts of a partner are an estimate.

The kept set belongs to the trade tool. It does not change the `stream_spots` of the adds planner.

## Suggestions

`trade/suggest.py` scores each 1-for-1 pair of your offered players and the players of the other teams. See [Offer list](#offer-list).

1. Both players must have a value. A pair with no value on one side is not a suggestion.
2. The value of the player you get must be in the value band: from give − 5% × |give| to give + 10% × |give| (`[trade] value_band`). The band works for values below 0.
3. The trade must raise your total playoff starts by 1 or more.
4. The rank: the gain in total starts, then min(weeks after) − min(weeks before), then the larger value change for you.
5. At most 3 rows for each player you give (`[trade] per_player`), and 20 rows in all (`[trade] rows`).

The playoff starts use the Roster page rules exactly: `core/roster.py` `lineup_fit()` on the days of `roster.playoff_days()`. The slots are `[league] slots` and one Util slot. The lineup order is the custom rank of `draft/rankings.py`, and a player with no rank goes last. A rest night on a back-to-back (`rests_b2b` of the `[risk] file`) is not a game. IL and injured players count, with their Yahoo status on the page.

## Offer list

The `[trade] offer` list in `config.toml` names the players that you are willing to trade (#170). Edit the list through the season.

1. The suggestions give only the players on the list. The match uses `common.name_key()`.
2. An empty list offers each player who is not untouchable.
3. `untouchable` wins over `offer`. A player on both lists is never given.
4. A name on the list that is not on your roster gives a warning in the terminal and on the page.
5. The trade builder still allows any player who is not untouchable. The list limits only the suggestions.
6. The kept set rule does not change. An offered player outside your kept set gets no suggestion, because a trade of him does not change your playoff starts.

The page shows a line above the table, for example "Offered: Rudy Gobert, Matas Buzelis, Coby White (config [trade] offer)." The names come from your roster, in the roster order. With an empty list, the line says "Offered: each player who is not untouchable (config [trade] offer is empty)."

Under that line, each player on the list with no suggestion gets one line with the reason. The run uses the first reason that applies:

| Reason | Line after "No suggestion for <name>: " |
|---|---|
| He is untouchable. | "he is on the [trade] untouchable list, and untouchable wins over offer." |
| He has no value. | "he has no value." |
| He is not in your kept set. | "he is not in your 8 kept players, so a trade does not change your playoff starts." |
| No player of another team is in his value band. | "no player of another team has a value in his value band." |
| No trade in his value band raises your starts. | "no trade in his value band raises your playoff starts." |
| His trades fall outside the row limit. | "his trades rank below the 20 trades that the page shows." |

The terminal prints the same lines after the best suggestion. With an empty list, no player gets a reason line.

## Value

The value of each player on both sides is the blended value of the adds planner (`adds/blend.py`), from both views of the rostered list. A player with no blended value uses his preseason `pg_value` (`adds/drops.py` `season_values()`), and the page marks it "pre". The page shows the preseason value ("Pre") of each player next to his value ("Val").

## Data

| Data | Source | Reader |
|---|---|---|
| Your roster and IL slots | Your Yahoo team page, from Edge | `adds/readers.py` `read_roster()` |
| The rostered list, projected view (next 7 days) | `players?status=T&...&stat1=S_PS7` | `trade/rostered.py` |
| The rostered list, recent view (last 14 days) | `players?status=T&...&stat1=S_AL14` | `trade/rostered.py` |
| The trade deadline ("Trade End Date") | The league settings page, `settings` | `trade/deadline.py` |
| The playoff days | `data/schedule.csv` (`python -m fantasyhoops.fetch.espn`) | `core/roster.py` `playoff_days()` |
| The custom rank | The projections file and `data/` files of the draft tools | `adds/roster.py` `read_ranks()` |
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

The run times its steps in `output/trade/timings.csv` with `adds/timing.py`: "Local files", "Yahoo reads" (with the sub-steps "settings", "team page" and "rostered list"), "Score" and "Page". After the trade deadline, the steps are "Local files", "Yahoo reads" (only "settings") and "Page". The `days`, `open_days` and `adds_left` columns stay empty, because the trade run has no planning window.

The targets: 15 seconds or less with a full cache, 60 seconds or less with no cache.

## Page

`trade/page.py` writes `output/trade/index.html` in the look that the owner picked on #149 (look 3). The page uses `publish.shell()`, the `lab-t` table and `band_style()`.

1. The header shows the trade deadline and the days to it, your playoff starts now and the time of the run.
2. The line of the offered players sits above the table, with a reason line for each offered player with no suggestion.
3. A filter row of the players you give sits above the table. It shows only offered players with a suggestion. A press on a chip shows only the trades of that player.
4. The table has the players you give and get, the partner team, the playoff starts of each week and the total, and the value change of both teams.
5. Each week cell shows the new count, the change and a small bar. A blue row above the trades shows your starts now.
6. Below 940px of content, a row list replaces the table. The row list has one column for each playoff week in `[playoffs] weeks` and one for the total, as the table does.
7. The line under the table starts with "Starts count your 8 kept players."
8. The trade builder sits under the table. See [Builder](#builder).

## Builder

The trade builder sits under the suggestions table (#152). It computes a custom trade in the browser, for example 2-for-1, and shows its effect on both teams.

1. Pick one partner team. A new partner clears the players you get.
2. Pick the players you give and the players you get. The untouchable players cannot be given. The players that are not on the offer list can be given.
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

The suggestions table shows the partner starts too, marked "Est.", under the partner name: the starts of each week and the total, before (first line) and after (second line). The row list on a phone shows the same numbers on one line.

The page inlines `draft/team_builder.js` and `trade/trade_builder.js`, as the draft board does. `trade_builder.js` holds the kept set and the drop rules, and calls `scoreCore()` of `team_builder.js` with value = −rank. So the engine starts the players in the lineup order of the Roster page. `team_builder.js` has no trade code. `trade/builder.py` has the same rules in Python. `tests/trade/test_parity.py` runs both in Node and Python on random rosters and compares the starts, the drops, the open spots and the value changes.

## Edge states

The run handles these states (#153):

1. **After the trade deadline.** The run reads the league settings first. If today is after the trade deadline, the run does not read your team page or the rostered list. It writes and publishes a short `/trade/` page: "The trade deadline was <date>. Yahoo accepts no more trades this season." The header shows the deadline with "passed" and the time of the run. The Trades tab stays. On the deadline day, the run still suggests trades.
2. **No trade deadline.** If the league settings page has no "Trade End Date" with a date, the run continues. The terminal prints one warning, and the page shows the same warning under the header. The header shows "Not found".
3. **A player with no match in a data file.** The run matches the names with `common.name_key()`. A player with no match in the rankings gets no rank and goes last in the lineup order. A player with no match in the `[risk] file` gets `rests_b2b` 0. A player with no match in the projections file gets no Pre value. For each file, the terminal prints one warning line with the names of both sides, and the page shows the same lines under the header. A line with 3 players or fewer names all of them, for example "Lost A and Lost B". A line with more players gives the count and the first 3 names, for example "11 players, such as A, B and C".
4. **Yahoo read failure.** If the run cannot read Yahoo (`YahooBlocked`, `PageNotReady`, or a sign-in that does not finish before the timeout), the run stops with the error. It does not write or publish a page, so the last good page stays on the site.

The page header always shows the date and time of the run ("Made").

## Configuration

The `[trade]` section of `config.toml`:

| Key | Default | Meaning |
|---|---|---|
| `untouchable` | `["Cooper Flagg"]` | The players that the tool never offers. They are always in your kept set. |
| `offer` | `["Rudy Gobert", "Matas Buzelis", "Coby White"]` | The players that the suggestions can give. An empty list offers each player who is not untouchable. See [Offer list](#offer-list). |
| `value_band` | `[0.95, 1.10]` | The value band of the player you get, as parts of the value you give. |
| `kept` | `8` | The players of a team that the playoff starts count. |
| `per_player` | `3` | The suggestions for each player you give, at most. |
| `rows` | `20` | The suggestions in all, at most. |

The section has no deadline value. The run reads the trade deadline from Yahoo.

## Terms

| Term | Meaning |
|---|---|
| Kept set | The players of a team that its playoff starts count. See [Kept set](#kept-set). |
| Playoff starts | The started games of a team in the playoff weeks, with the Roster page rules. |
| Value band | The range of values of the player you get, from the value you give. |
| Untouchable | A player that the tool never offers in a trade. |
| Partner | The other fantasy team of a trade. |
| Offered player | A player on your roster that the suggestions can give: on the `[trade] offer` list (or any player if the list is empty), and not untouchable. |
| Pre | The preseason `pg_value` of a player. As a mark, it says that the value is the preseason value, because he has no blended value. |

## Decisions

- On 2026-10-28, the owner decided: the trade targets come from the rostered list, the tool is its own command, and the value is the blended value with the preseason value next to it (owner decisions 1, 2 and 13 of the design page).
- On 2026-10-28, the owner decided: the playoff starts count the top 8 players by value, with Flagg and the IL players always in.
- On 2026-10-28, the owner decided: the player you get takes the spot of the player you give in the kept set. This supersedes "the top 8 after the trade" (Decision comment on #150).
- On 2026-10-28, the owner picked look 3 of the prototype round (#149).
- On 2026-10-28, the owner decided: the trade deadline comes from the Yahoo league settings, not from a config value.
- On 2026-10-29, the owner decided: the page shows the partner starts, marked "est.", for the suggestions and for a custom trade (Decision comment on #152).
- On 2026-10-29, the builder of #152 made the build choices of the builder (Decision comment on #152).
- On 2026-10-29, the builder of #153 made the choices of the edge states (Decision comments on #153).
- On 2026-10-29, the owner decided: a config list `[trade] offer` limits the players that the suggestions give. The kept set rule does not change (#170). The builder of #170 made the choices of the reason lines (Decision comments on #170).
