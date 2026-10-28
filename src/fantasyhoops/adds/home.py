"""The data of the home page at the end of a planning run (#120). It writes output/home/index.html (core/home.py).

The roster comes from your Yahoo team page, which the run reads (LeagueData.roster). The rank and rests_b2b come from
draft/rankings.py. The season stats come from one ESPN statistics/byathlete request (fetch/espn.py). The playoff days
come from data/schedule.csv (core/schedule.py).
"""

import traceback

import pandas as pd

from fantasyhoops.core import home
from fantasyhoops.core.common import name_key
from fantasyhoops.core.schedule import playoff_schedule
from fantasyhoops.draft.rankings import build_rankings, load_risk
from fantasyhoops.fetch.espn import season_stats


def roster_players(roster, ranks, risk, stats):
    """A home.RosterPlayer for each adds Player of roster.

    ranks: {name_key: rank}. risk: {name_key: rests_b2b}. stats: {name_key: stats} (fetch/espn.py).
    The names match after name_key(). A stats row of a different NBA team still matches: a trade changes the team.
    """
    out = []
    for p in roster:
        key = name_key(p.name)
        out.append(
            home.RosterPlayer(
                name=p.name,
                team=p.team,
                positions=tuple(p.positions),
                slot=p.slot,
                status=p.status,
                status_name=p.status_name,
                rank=ranks.get(key),
                rests_b2b=bool(risk.get(key, 0)),
                stats=stats.get(key),
            )
        )
    return out


def read_ranks(cfg, sched):
    """{name_key(name): rank} of the custom rankings (draft/rankings.py)."""
    teams = playoff_schedule(sched, cfg)[0]
    df = build_rankings(cfg, teams)
    out = {}
    for name, rank in zip(df.name, df["rank"]):
        out.setdefault(name_key(name), int(rank))
    return out


def read_risk(roster, cfg):
    """{name_key(name): rests_b2b} for the players of roster, from the [risk] file (draft/rankings.py)."""
    names = pd.Series([p.name for p in roster])
    risk = load_risk(names, cfg)
    return {name_key(n): int(r) for n, r in zip(names, risk.rests_b2b)}


def build_home(data, cfg, sched, today):
    """Write the home page for the LeagueData of a run. Return its path, or None if the page failed.

    A failure prints the error and does not stop the run. The publish then keeps the list of the tools as the home page.
    """
    try:
        players = roster_players(
            data.roster, read_ranks(cfg, sched), read_risk(data.roster, cfg), season_stats(cfg["league"]["espn_season"])
        )
        text = home.render(
            players,
            home.playoff_days(sched, cfg),
            cfg,
            week=data.week.number,
            adds=(data.adds.used, data.adds.limit),
            today=today,
            team_name=cfg["adds"].get("team_name"),
        )
        path = home.write(text)
    except Exception:
        print("The run did not make the home page. The error:")
        traceback.print_exc()
        return None
    print(f"Wrote the home page: {path}")
    return path
