"""Readers for the Yahoo league pages: HTML in, data out. They do not open a browser (see adds/session.py).

The selectors are in .scratch/yahoo/NOTES.md (local only) and in the fixtures in tests/adds/fixtures/.
"""
import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup

from fantasyhoops.adds.teams import espn_code

# Statuses that keep a player out of all games: O (Out) and Out for Season. Yahoo shows the full name in the title.
OUT_STATUSES = {"O", "OFS"}


@dataclass(frozen=True)
class Player:
    """One player on a Yahoo roster or in a Yahoo player list.

    team: the ESPN code of his NBA team (the code of data/schedule.csv).
    positions: his Yahoo positions, for example ("PG", "SG").
    slot: his slot on your roster today: a starting slot ("PG", ..., "Util"), "BN" or "IL". "" in a player list.
    status: the Yahoo status, for example "Q" or "O". "" for a healthy player.
    status_name: the full status, for example "Questionable". "" for a healthy player.
    """
    name: str
    team: str
    positions: tuple
    slot: str = ""
    status: str = ""
    status_name: str = ""

    @property
    def on_il(self):
        """True if the player is in an IL slot. He takes no roster spot and cannot start."""
        return self.slot.startswith("IL")

    @property
    def out(self):
        """True if the player is Out or Out for Season. He does not play in the planning window."""
        return self.status in OUT_STATUSES or self.status_name.lower().startswith("out")


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


def _soup(html):
    return BeautifulSoup(html, "html.parser")


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
    return [read_player(row.select_one(".ysf-player-name"), row["data-pos"])
            for row in rows if row.select_one(".ysf-player-name a.name")]


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
