"""Matchup weights: the weight of each category from the state of the current matchup. Design: docs/adds/README.md,
"Matchup weights". The module writes no files.

- read_matchup(): the category scores of your team and your opponent, from the score table of the matchup page.
- matchup_weights(): a weight for each category. A close category keeps weight 1. A category that you lead or trail
  by a large margin gets less weight, down to [adds.matchup] min_weight. The margins in config.toml are for a whole
  week. The function multiplies them by the share of the week that is left.
- weighted_cfg(): cfg with the category weights times the matchup weights. The matchup value of a stat line is its
  value with this cfg, on the same category scale. The Match column of the plan page shows it.
With all categories tied, all weights are 1, and the matchup value equals the blended value.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from fantasyhoops.adds.readers import STAT_COLUMNS


@dataclass(frozen=True)
class Matchup:
    """The category scores of the current matchup: {stat key: total} for your team and for your opponent."""

    opponent: str
    mine: dict
    theirs: dict

    def margin(self, cat):
        """Your total minus the total of your opponent. Above 0: you lead the category."""
        return self.mine.get(cat, 0.0) - self.theirs.get(cat, 0.0)


def _number(text):
    """A number from a score cell. Yahoo shows "-" before the first game."""
    return 0.0 if text in ("", "-") else float(text)


def read_matchup(html, team):
    """The Matchup on the matchup page (/nba/<league>/matchup?mid1=<team>), or None if the page has no score table.

    The score table has the stat headers of STAT_COLUMNS and one row for each team. The header does not always
    have a "Score" cell. team: your team ID. Your row is the row with the link to /nba/<league>/<team>. The team name is
    the text of the first team link with text, because the first link can be a logo with no text.
    """
    for table in BeautifulSoup(html, "html.parser").find_all("table"):
        head = table.select("thead tr")
        heads = [cell.get_text(" ", strip=True) for cell in head[-1].find_all(["th", "td"])] if head else []
        if not set(STAT_COLUMNS) <= set(heads):
            continue
        rows = []
        for row in table.select("tbody tr"):
            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            link = next((a for a in row.select("a[href]") if a.get_text(strip=True)), None)
            if link is None or len(cells) != len(heads):
                continue
            scores = {key: _number(cells[heads.index(name)]) for name, key in STAT_COLUMNS.items()}
            yours = re.search(rf"/nba/\d+/{team}/?$", link["href"]) is not None
            rows.append((yours, link.get_text(strip=True), scores))
        mine = [r for r in rows if r[0]]
        theirs = [r for r in rows if not r[0]]
        if len(mine) == 1 and len(theirs) == 1:
            return Matchup(opponent=theirs[0][1], mine=mine[0][2], theirs=theirs[0][2])
    return None


def category_weight(margin, close, large, min_weight):
    """The weight of a category: 1 if the margin is close or less, min_weight if it is large or more, linear between.

    The sign of the margin has no effect: a large lead and a large deficit get the same weight.
    """
    size = abs(margin)
    if size <= close:
        return 1.0
    if size >= large:
        return min_weight
    return 1.0 - (1.0 - min_weight) * (size - close) / (large - close)


def matchup_weights(matchup, cfg, share_left):
    """{category: weight} for the categories of cfg["weights"]. All weights are 1 if matchup is None.

    share_left: the days of the planning window / the days of the fantasy week. The function multiplies the
    margins of [adds.matchup] (close and large, for a whole week) by this share.
    """
    if matchup is None:
        return {cat: 1.0 for cat in cfg["weights"]}
    m = cfg["adds"]["matchup"]
    return {
        cat: category_weight(
            matchup.margin(cat), m["close"][cat] * share_left, m["large"][cat] * share_left, m["min_weight"]
        )
        for cat in cfg["weights"]
    }


def weighted_cfg(cfg, weights):
    """A copy of cfg with each category weight times its matchup weight. A category not in weights keeps its weight."""
    return {**cfg, "weights": {cat: w * weights.get(cat, 1.0) for cat, w in cfg["weights"].items()}}
