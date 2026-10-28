"""Readers for the Yahoo league pages: HTML in, data out. They do not open a browser (see adds/session.py).

The selectors are in .scratch/yahoo/NOTES.md (local only) and in the fixtures in tests/adds/fixtures/.
The readers of a player list page take the HTML or a page from parse(). Parse a page one time with parse(),
then give it to read_free_agents() or read_waiver_players() and to has_next_page() (#93).
"""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime

from bs4 import BeautifulSoup

from fantasyhoops.adds.teams import espn_code

# Statuses that keep a player out of all games: O (Out), Out for Season, NA (Not Active) and suspended.
# Yahoo shows the full name in the title. The pages of 2026-10-20 had no suspended player, so the code SUSP
# is a guess. A title that starts with "Suspen" (Suspended, Suspension) also counts.
OUT_STATUSES = {"O", "OFS", "NA", "SUSP"}
OUT_TITLES = ("out", "not active", "suspen")


@dataclass(frozen=True)
class Player:
    """One player on a Yahoo roster or in a Yahoo player list.

    team: the ESPN code of his NBA team (the code of data/schedule.csv).
    positions: his Yahoo positions, for example ("PG", "SG").
    slot: his slot on your roster today: a starting slot ("PG", ..., "Util"), "BN" or "IL". "" in a player list.
    status: the Yahoo status, for example "Q" or "O". "" for a healthy player.
    status_name: the full status, for example "Questionable". "" for a healthy player.
    clear_day: the day that he clears waivers, for a player on waivers (W). None for all other players.
    """

    name: str
    team: str
    positions: tuple
    slot: str = ""
    status: str = ""
    status_name: str = ""
    clear_day: date | None = None

    @property
    def on_waivers(self):
        """True if the player is on waivers (W). He can play for you only after his clear day."""
        return self.clear_day is not None

    @property
    def on_il(self):
        """True if the player is in an IL slot. He takes no roster spot and cannot start."""
        return self.slot.startswith("IL")

    @property
    def out(self):
        """True if the player is Out, Out for Season, Not Active or suspended. He does not play in the planning window."""
        return self.status in OUT_STATUSES or self.status_name.lower().startswith(OUT_TITLES)


@dataclass(frozen=True)
class Week:
    """The current fantasy week: its number and its days, first to last."""

    number: int
    days: tuple

    @property
    def start(self):
        return self.days[0]

    @property
    def end(self):
        return self.days[-1]


@dataclass(frozen=True)
class Adds:
    """The adds that you used this week and the adds that the league gives each week."""

    used: int
    limit: int

    @property
    def left(self):
        return self.limit - self.used


@dataclass(frozen=True)
class FreeAgent:
    """One row of the free-agent list with stat1=S_PS7 (Yahoo's projection for the next 7 days).

    games: the projected games in the next 7 days (GP*). 0 when Yahoo has no projection ("-").
    line: the projected per-game stats with the stat keys of core/valuation.py, for example {"pts": 15.2, ...}.
    Empty when games is 0.
    A row of the list with stat1=S_AL14 (the last 14 days) has the same fields: games is the games in the last
    14 days, and line is the per-game averages of those games.
    """

    player: Player
    games: float
    line: dict


# Free-agent list column (header text) -> stat key of core/valuation.py.
STAT_COLUMNS = {"PTS": "pts", "REB": "reb", "AST": "ast", "3PTM": "threes", "BLK": "blk", "ST": "stl"}


def parse(html):
    """The parsed page of the HTML. A reader can take this page in place of the HTML, so a page parses one time."""
    return BeautifulSoup(html, "html.parser")


def _soup(html):
    """The parsed page: html as it is if parse() gave it, else parse(html)."""
    return html if isinstance(html, BeautifulSoup) else parse(html)


def read_player(block, slot=""):
    """A Player from the name block of a Yahoo player table (div.ysf-player-name).

    The roster page and the free-agent list use the same name block.
    """
    link = block.select_one("a.name")
    # The link text can be short ("K. Caldwell-Pope"). The title has the full name.
    name = link.get("title") or link.get_text(strip=True)
    team, _, positions = block.select_one("span.D-b > span.Fz-xxs").get_text(strip=True).partition(" - ")
    status = block.select_one(".ysf-player-status span")
    return Player(
        name=name,
        team=espn_code(team.strip()),
        positions=tuple(p.strip() for p in positions.split(",") if p.strip()),
        slot=slot,
        status=status.get_text(strip=True) if status else "",
        status_name=status.get("title", "") if status else "",
    )


def read_roster(html):
    """The players on your team page (/nba/<league>/<team>), in the order of the page. Empty slots are not in the list."""
    rows = _soup(html).select("table#statTable0 tbody tr")
    if not rows:
        raise ValueError("The team page has no roster table (table#statTable0).")
    return [
        read_player(row.select_one(".ysf-player-name"), row["data-pos"])
        for row in rows
        if row.select_one(".ysf-player-name a.name")
    ]


def read_adds(html):
    """The adds that you used this week, from the team page: "You have used 0 of your 5 player adds for this week." """
    text = _soup(html).get_text(" ", strip=True)
    found = re.search(r"You have used (\d+) of your (\d+) player adds", text)
    if not found:
        raise ValueError("The team page does not show the adds that you used this week.")
    return Adds(used=int(found[1]), limit=int(found[2]))


def read_week(html):
    """The current fantasy week, from the matchup page (/nba/<league>/matchup?mid1=<team>).

    The page has one link for each day of the week, for example "/nba/22820/matchup?week=1&date=2026-10-20&...".
    """
    days, number = [], None
    for link in _soup(html).select("a.Navtarget[href]"):
        found = re.search(r"[?&]week=(\d+)&date=(\d{4}-\d{2}-\d{2})", link["href"])
        if found:
            number = int(found[1])
            days.append(date.fromisoformat(found[2]))
    if not days:
        raise ValueError("The matchup page has no links to the days of the week.")
    return Week(number=number, days=tuple(sorted(set(days))))


def _number(text):
    """A number from a stat cell. Yahoo shows "-" for a missing value."""
    return 0.0 if text in ("", "-") else float(text)


def read_free_agents(html, totals=True):
    """The players with status FA on one page of the free-agent list (/nba/<league>/players?status=FA&stat1=S_PS7).

    The page shows TOTALS for the next 7 days. This function divides them by GP* to get a per-game line.
    totals: False for a page with per-game averages (stat1=S_AL14). The function then does not divide.
    html: the HTML of the page or the page from parse().
    """
    # Players on waivers (W) are not free agents.
    return _read_list(html, totals, lambda cell, player: (cell == "FA", None))


def clear_day(cell, today):
    """The clear day of a Roster Status cell such as "W (Oct 22)". None for a cell with no valid clear day.

    The cell has no year. The year is the year of today, or the next year if that date is more than
    180 days before today. A date that does not exist in that year (Feb 29) gives None.
    """
    found = re.fullmatch(r"W \((\w{3}) (\d{1,2})\)", cell)
    if not found:
        return None
    try:
        month = datetime.strptime(found[1], "%b").month
        day = date(today.year, month, int(found[2]))
        return date(today.year + 1, month, day.day) if (today - day).days > 180 else day
    except ValueError:
        return None


def read_waiver_players(html, today, totals=True):
    """The players on waivers (W) on one page of the player list with status=W, each with his clear day.

    The Roster Status cell shows the clear day, for example "W (Oct 22)" (seen on 2026-10-21).
    A W cell without a valid clear day: the planner cannot tell when he is free. The function prints a warning
    and skips him. today: the day of the run, for the year of the clear day. totals and html: see read_free_agents().
    """

    def keep(cell, player):
        if not cell.startswith("W"):
            return False, None
        day = clear_day(cell, today)
        if day is None:
            print(f'Warning: the waiver list shows {player.name} as "{cell}" with no clear day. The planner skips him.')
        return day is not None, day

    return _read_list(html, totals, keep)


def _read_list(html, totals, keep):
    """The FreeAgents of one page of a player list.

    keep(Roster Status cell, Player) -> (keep the row?, clear day).
    """
    table = _soup(html).select_one("div.players table")
    if table is None:
        raise ValueError("The free-agent page has no player table (div.players table).")
    header = [th.get_text(" ", strip=True) for th in table.select("thead tr")[-1].find_all("th")]
    column = {name: header.index(name) for name in ["Roster Status", "GP*", *STAT_COLUMNS]}
    out = []
    for row in table.select("tbody tr"):
        block = row.select_one(".ysf-player-name")
        if block is None or block.select_one("a.name") is None:
            continue
        cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
        player = read_player(block)
        kept, day = keep(cells[column["Roster Status"]], player)
        if not kept:
            continue
        games = _number(cells[column["GP*"]])
        per = games if totals else 1
        line = {key: _number(cells[column[name]]) / per for name, key in STAT_COLUMNS.items()} if games else {}
        out.append(FreeAgent(player=replace(player, clear_day=day), games=games, line=line))
    return out


def has_next_page(html):
    """True if a page of a Yahoo player list has a "Next 25" link. The last page has no such link.

    html: the HTML of the page or the page from parse().
    """
    return any(a.get_text(strip=True) == "Next 25" for a in _soup(html).select("a"))
