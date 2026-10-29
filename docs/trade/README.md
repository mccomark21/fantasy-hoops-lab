# Trade tool

The trade tool will suggest trades with the other fantasy teams of the league. The design is in [docs/wiki/trade-tool-design-2026-10-28.md](../wiki/trade-tool-design-2026-10-28.md). This guide covers the Yahoo reads (#148). The suggestions and the page come in later issues.

## Yahoo reads

`fantasyhoops.trade` reads these pages through the Yahoo session of the adds planner (`adds/session.py`):

| Page | Path | Reader |
|---|---|---|
| The rostered list, projected view (next 7 days) | `players?status=T&...&stat1=S_PS7` | `trade/rostered.py` |
| The rostered list, recent view (last 14 days) | `players?status=T&...&stat1=S_AL14` | `trade/rostered.py` |
| The league settings | `settings` | `trade/deadline.py` |

The rostered list reader:

1. Reads all pages of each view, until a page has no "Next 25" link.
2. Keeps only the players of the other fantasy teams. It drops the rows of your team (`[adds] team`).
3. Takes the fantasy team of a row from the team link (`/nba/<league>/<team ID>`), not from the team name. A team name can change during the season.
4. Reads the name, the NBA team, the positions and the status with `read_player()` of `adds/readers.py`.
5. Reads only the projected view while `[adds] recent_skip_weight` skips the recent view (`lists.skips_recent_view()`).

The trade deadline reader finds the label "Trade End Date" on the league settings page and reads the first date after it. If the page has no such date, the read continues with no deadline and names the cached page.

## Cache

The reads keep the raw pages in the same-day cache, kind "rostered" (`output/adds/cache/rostered/<YYYY-MM-DD>/`). A second read on the same day opens no Yahoo page. `--no-cache` reads each page from Yahoo again. If a reader fails on a real page, use the cached page to fix the reader.

## Live check

```sh
python -m fantasyhoops.trade.reads
```

The command opens Edge, reads the pages and prints:

- The page count of each view and the number of players of other teams.
- Each fantasy team: its ID, its name and its number of players.
- The rows with no team link. Expect 0.
- The trade deadline, or why the read did not find it.

The fixtures in `tests/trade/fixtures/` are hand-made in the shape of the Yahoo players table, because no live read had shown these pages on 2026-10-28. They hold no names of managers.
