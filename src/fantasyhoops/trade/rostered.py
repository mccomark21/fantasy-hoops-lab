"""The reader of Yahoo's list of rostered players (/players?status=T), the trade targets (#148). It writes no file.

The list is the same Yahoo players table as the free-agent list (adds/readers.py). Each row of a rostered player
has a link to his fantasy team in the Roster Status cell, for example <a href="/nba/22820/3">. The reader takes
the team ID from that link, not from the team name, because a team name can change during the season.
read_rostered() reads the list in both views: the projected view (PROJECTED) and the recent view (RECENT). It keeps
only the players of the other fantasy teams. Free agents and players on waivers are never trade targets.
The pages go through the reader that the caller gives, for example cache.PageCache.rostered() (adds/cache.py).
"""

import re
from dataclasses import dataclass

from fantasyhoops.adds.cache import get_all
from fantasyhoops.adds.lists import PROJECTED, RECENT
from fantasyhoops.adds.readers import STAT_COLUMNS, has_next_page, parse, read_player

ROSTERED_PAGES = 20  # pages of 25 players of each view at most. 14 teams of about 15 players fill about 8 pages.
# The header of the cell with the fantasy team. The free-agent list calls it "Roster Status". The rostered list can
# call it "Owner". No live read has shown the rostered list yet (#148).
TEAM_COLUMNS = ("Roster Status", "Owner")
# The path of a fantasy team page: /nba/<league>/<team ID>, with an optional query or "/".
TEAM_LINK = re.compile(r"/nba/\d+/(\d+)(?:[/?#]|$)")


@dataclass(frozen=True)
class RosteredPlayer:
    """One row of the rostered list: a player on the roster of another fantasy team.

    player, games, line: as in readers.FreeAgent, so blend.blended_options() can take a RosteredPlayer.
    team_id: the ID of his fantasy team, from the team link. team_name: the text of that link.
    """

    player: object
    games: float
    line: dict
    team_id: int
    team_name: str


@dataclass(frozen=True)
class RosteredPage:
    """The result of read_rostered_page(): the kept rows and the rows with no team link.

    players: the RosteredPlayers of the other teams. no_link: the names of the players whose row has no team link.
    """

    players: list
    no_link: list


@dataclass(frozen=True)
class RosteredRead:
    """The result of read_rostered().

    projected, recent: the RosteredPlayers of each view. recent is empty if the read skipped the recent view.
    pages: the pages that the read used in each view, by view (PROJECTED, RECENT).
    no_link: the names of the players whose row has no team link, in both views.
    skipped_recent: True if the read skipped the recent view (lists.skips_recent_view()).
    """

    projected: list
    recent: list
    pages: dict
    no_link: list
    skipped_recent: bool


def rostered_path(offset=0, view=PROJECTED):
    """The path of one page of the rostered list, with the stats of the view. offset: the first row, 0, 25, 50 ..."""
    return f"players?status=T&pos=P&cut_type=33&myteam=0&sort=OR&sdir=1&stat1={view}&count={offset}"


def team_id(href):
    """The fantasy team ID of a team link, for example "/nba/22820/3" -> 3. None if href is not a team link."""
    found = TEAM_LINK.search(href or "")
    return int(found[1]) if found else None


def _number(text):
    """A number from a stat cell. Yahoo shows "-" for a missing value."""
    return 0.0 if text in ("", "-") else float(text)


def _team_link(cell):
    """The (team ID, team name) of the first team link in cell, or None."""
    for link in cell.select("a[href]"):
        found = team_id(link["href"])
        if found is not None:
            return found, link.get_text(" ", strip=True)
    return None


def read_rostered_page(html, own_team, totals=True):
    """The players of the other fantasy teams on one page of the rostered list. Give a RosteredPage.

    own_team: your team ID ([adds] team). The rows of your team are not trade targets.
    totals: True for the projected view (stat1=S_PS7). The page then shows totals, and the function divides them by
    GP*. False for the recent view (stat1=S_AL14), which shows per-game averages.
    html: the HTML of the page or the page from readers.parse().
    A row with no team link (a free agent, a player on waivers or a changed page) is not kept. Its name goes in
    no_link.
    """
    soup = parse(html) if isinstance(html, str) else html
    table = soup.select_one("div.players table")
    if table is None:
        raise ValueError("The rostered list page has no player table (div.players table).")
    header = [th.get_text(" ", strip=True) for th in table.select("thead tr")[-1].find_all("th")]
    team_column = next((header.index(name) for name in TEAM_COLUMNS if name in header), None)
    missing = [name for name in ["GP*", *STAT_COLUMNS] if name not in header]
    if missing:
        raise ValueError(f"The rostered list page has no column {', '.join(missing)}. The header is {header}.")
    column = {name: header.index(name) for name in ["GP*", *STAT_COLUMNS]}
    players, no_link = [], []
    for row in table.select("tbody tr"):
        block = row.select_one(".ysf-player-name")
        if block is None or block.select_one("a.name") is None:
            continue
        player = read_player(block)
        tds = row.find_all("td")
        # The team link is in the team column. If that cell has none, the function looks in the full row.
        cell = tds[team_column] if team_column is not None and team_column < len(tds) else None
        team = (_team_link(cell) if cell is not None else None) or _team_link(row)
        if team is None:
            no_link.append(player.name)
            continue
        if team[0] == own_team:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]
        games = _number(cells[column["GP*"]])
        per = games if totals else 1
        line = {key: _number(cells[column[name]]) / per for name, key in STAT_COLUMNS.items()} if games else {}
        players.append(RosteredPlayer(player, games, line, team_id=team[0], team_name=team[1]))
    return RosteredPage(players, no_link)


def read_rostered(reader, own_team, skip_recent=False):
    """Read all pages of the rostered list in both views. Give a RosteredRead.

    reader: a reader with get(path), for example cache.PageCache.rostered(). own_team: your team ID ([adds] team).
    skip_recent: True while lists.skips_recent_view() skips the recent view. The read then reads the projected view
    only. The read takes page N of each open view together, then page N + 1 of each view that has a "Next 25" link.
    """
    views = [PROJECTED] if skip_recent else [PROJECTED, RECENT]
    found = {view: [] for view in views}
    pages = {view: 0 for view in views}
    no_link = []
    open_views = list(views)
    for page_number in range(ROSTERED_PAGES):
        if not open_views:
            break
        htmls = get_all([(reader, rostered_path(25 * page_number, view)) for view in open_views])
        more = []
        for view, html in zip(open_views, htmls):
            soup = parse(html)
            page = read_rostered_page(soup, own_team, totals=view == PROJECTED)
            found[view] += page.players
            no_link += page.no_link
            pages[view] += 1
            if has_next_page(soup):
                more.append(view)
        open_views = more
    return RosteredRead(
        projected=found[PROJECTED],
        recent=found.get(RECENT, []),
        pages=pages,
        no_link=no_link,
        skipped_recent=skip_recent,
    )


def teams(players):
    """The fantasy teams of players, as {team ID: (team name, number of players)}, by team ID."""
    out = {}
    for p in players:
        name, count = out.get(p.team_id, (p.team_name, 0))
        out[p.team_id] = (name, count + 1)
    return dict(sorted(out.items()))
