"""Value of a free agent: the per-game value (core/valuation.py) of a Yahoo stat line.

The category scale (mean and standard deviation of each category) comes from the player pool of the season
projections file, the same pool as the draft tools. So a value here is on the scale of pg_value on the draft board.

The plan page shows the market value: the value above a replacement free agent, the free agent at rank
REPLACEMENT_RANK by value. The planner itself uses the values on the scale of the projections. A market value is
the same value minus one number, so it does not change the order of the players or of the plans.
"""

import pandas as pd

from fantasyhoops.core.common import latest_projections
from fantasyhoops.core.valuation import category_scale, pg_value
from fantasyhoops.draft.rankings import STATS

REPLACEMENT_RANK = 15  # the market value of the free agent at this rank is 0


def projection_scale(cfg):
    """The category scale of the player pool in the newest projections file. Give it to line_value()."""
    df = pd.read_csv(latest_projections(cfg))
    df = df[df.games > 0].copy()
    for cat, calc in STATS.items():
        df[cat] = calc(df) / df.games
    return category_scale(df, cfg)


def line_value(line, scale, cfg):
    """The per-game value of a per-game stat line ({"pts": ..., "reb": ...}). None for an empty line."""
    return float(pg_value(pd.Series(line), scale, cfg)) if line else None


def replacement_value(options, rank=REPLACEMENT_RANK):
    """The value of the free agent at rank (1 = best) among the options who play and have a value.

    The market value of an option is his value minus this value. With fewer options than rank: the value of the
    last option. None if no option has a value.
    """
    values = sorted((o.value for o in options if o.value is not None and not o.player.out), reverse=True)
    return values[min(rank, len(values)) - 1] if values else None


def market_value(value, replacement):
    """The market value: value minus the replacement value, to 2 decimals. None if one of the two is None."""
    return None if value is None or replacement is None else round(value - replacement, 2)
