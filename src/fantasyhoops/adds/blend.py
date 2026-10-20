"""Blended value of a free agent: his projected line, moved toward his recent line. Design: docs/adds/README.md, Value.

- Projected line: Yahoo's projection for the next 7 days (free-agent list, stat1=S_PS7), per game.
- Recent line: his per-game averages in the last 14 days (stat1=S_AL14).
- Blended line = (1 - w) x projected line + w x recent line. The weight w = games in the last 14 days / 14, 1 at most.
- A player with no recent games: blended line = projected line.
- A player with no projection but with recent games: blended line = recent line, because it is the only stat line
  that the planner has for him. He is then a candidate for the plans. A player with no projection and no recent
  games has no blended value and is not a candidate.
"""
from fantasyhoops.adds.planner import Option
from fantasyhoops.adds.value import line_value

RECENT_DAYS = 14  # the days of the recent line (stat1=S_AL14)


def recent_weight(games):
    """The weight of the recent line: games in the last 14 days / 14, 1 at most."""
    return min(games / RECENT_DAYS, 1.0)


def blend_line(projected, recent, games):
    """The blended per-game line. projected, recent: per-game lines ({} if none). games: the recent games."""
    if not recent or not games:
        return projected
    if not projected:
        return recent
    w = recent_weight(games)
    return {key: (1 - w) * projected[key] + w * recent.get(key, 0.0) for key in projected}


def blended_options(free_agents, recent, scale, cfg):
    """An Option for each FreeAgent of the projected view, with his projected, recent and blended values.

    free_agents: the FreeAgents of the projected view (S_PS7). recent: the FreeAgents of the recent view (S_AL14)
    of the same lists. The function matches the players of the two views by name and NBA team. A player who is
    not in the recent view has no recent games. scale, cfg: for line_value() (adds/value.py).
    """
    by_player = {(f.player.name, f.player.team): f for f in recent}
    out = []
    for f in free_agents:
        r = by_player.get((f.player.name, f.player.team))
        games, line = (r.games, r.line) if r else (0, {})
        out.append(Option(f.player,
                          projected_value=line_value(f.line, scale, cfg),
                          recent_value=line_value(line, scale, cfg) if games else None,
                          blended_value=line_value(blend_line(f.line, line, games), scale, cfg)))
    return out
