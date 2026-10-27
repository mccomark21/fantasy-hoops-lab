"""Matchup weights: the weight of each category from the state of the current matchup. Design: docs/adds/README.md,
"Matchup weights". The module writes no files.

- read_matchup(): the category scores of your team and your opponent, from the score table of the matchup page.
- matchup_weights(): a weight for each category. A close category keeps weight 1. A category that you lead or trail
  by a large margin gets less weight, down to [adds.matchup] min_weight. The margins in config.toml are for a whole
  week. The function multiplies them by the share of the week that is left.
- weighted_cfg(): cfg with the category weights times the matchup weights. The matchup value of a stat line is its
  value with this cfg, on the same category scale.
- matchup_plan(): the aggressive plan with the matchup values in the plan score.
With all categories tied, all weights are 1, and the matchup value equals the blended value.
"""

import math
import re
from dataclasses import dataclass, replace

import pandas as pd
from bs4 import BeautifulSoup

from fantasyhoops.adds.planner import StreamSpot, aggressive_plan, counted_games, next_week_totals
from fantasyhoops.adds.readers import STAT_COLUMNS
from fantasyhoops.adds.value import line_value
from fantasyhoops.core.common import latest_projections, name_key
from fantasyhoops.draft.rankings import STATS


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


def season_lines(projections, scale, cfg):
    """{name_key(name): per-game stat line} for the players of a projections DataFrame with games > 0.

    Two players with the same name key: the line of the player with the higher value (line_value() with cfg) is in
    the result. drops.rank_players() keeps the same player, so a holder gets the line of his own season value.
    """
    df = projections[projections.games > 0].copy()
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    out = {}
    for row in df.itertuples():
        key, line = name_key(f"{row.first_name} {row.last_name}"), {cat: getattr(row, cat) for cat in STATS}
        if key not in out or line_value(line, scale, cfg) > line_value(out[key], scale, cfg):
            out[key] = line
    return out


def matchup_spots(spots, scale, cfg, matchup_cfg, projections=None):
    """The StreamSpots, each holder with his matchup value: the value of his season projection with the matchup cfg.

    cfg: the config without the matchup weights. A holder who is not in the projections file gets no matchup value.
    projections: a projections DataFrame. If None, the function reads the newest projections file, but only if a
    spot has a holder.
    """
    if not any(s.holder for s in spots):
        return list(spots)
    if projections is None:
        projections = pd.read_csv(latest_projections(cfg))
    lines = season_lines(projections, scale, cfg)
    return [
        StreamSpot(
            replace(s.holder, matchup_value=line_value(lines.get(name_key(s.holder.player.name)), scale, matchup_cfg))
        )
        if s.holder
        else s
        for s in spots
    ]


def _finite(value):
    return value is not None and math.isfinite(value)


def matchup_plan(days, games, spots, free_agents, adds_left, slots, empty_value, next_week=None, next_weight=0.0):
    """The aggressive plan (planner.aggressive_plan()) with the matchup value of each Option in the plan score.

    empty_value: the value of an empty slot with the matchup weights. The Plan holds the original Options, and its
    value is the total blended value of its started games, as in the other plans. matchup_score() gives its score.
    next_week, next_weight: the next-week bonus of planner.schedule_plan(). The bonus also uses the matchup values.
    The next value of the Plan uses the blended values.
    """
    original = {}

    def scored(o):
        new = replace(o, blended_value=o.match)
        original[o.player] = o
        return new

    plan = aggressive_plan(
        days,
        games,
        [StreamSpot(scored(s.holder)) if s.holder else s for s in spots],
        [scored(o) for o in free_agents],
        adds_left,
        slots,
        empty_value,
        next_week,
        next_weight,
    )
    windows = tuple(
        replace(
            w,
            player=original.get(w.player.player, w.player),
            options=tuple(original.get(o.player, o) for o in w.options),
        )
        for w in plan.windows
    )
    value = sum(
        counted_games(w.player.rest_games, w.started) * (w.player.value if _finite(w.player.value) else 0.0)
        for w in windows
    )
    next_games, next_value = next_week_totals(windows, next_week, next_weight)
    return replace(plan, windows=windows, value=value, next_games=next_games, next_value=next_value)


def matchup_score(plan, empty_value):
    """The sum of the matchup value above an empty slot of the started games of a Plan.

    empty_value: the value of an empty slot with the matchup weights. A player with no finite matchup value counts as
    an empty slot.
    """
    return sum(
        counted_games(w.player.rest_games, w.started)
        * ((w.player.match if _finite(w.player.match) else empty_value) - empty_value)
        for w in plan.windows
    )


def matchup_lines(matchup, weights):
    """Text lines for the terminal: the score and the weight of each category."""
    if matchup is None:
        return ["Matchup: the planner did not find the category scores on the matchup page. All weights are 1."]
    names = {key: name for name, key in STAT_COLUMNS.items()}
    out = [f"Matchup against {matchup.opponent} (you - opponent, weight):"]
    for cat in weights:
        out.append(
            f"  {names.get(cat, cat):<5} {matchup.mine.get(cat, 0):>6g} - {matchup.theirs.get(cat, 0):<6g} "
            f"margin {matchup.margin(cat):+g}, weight {weights[cat]:.2f}"
        )
    return out
