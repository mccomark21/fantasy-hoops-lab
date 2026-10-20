"""Value of a free agent: the per-game value (core/valuation.py) of a Yahoo stat line.

The category scale (mean and standard deviation of each category) comes from the player pool of the season
projections file, the same pool as the draft tools. So a value here is on the scale of pg_value on the draft board.
"""
import pandas as pd

from fantasyhoops.core.common import latest_projections
from fantasyhoops.core.valuation import category_scale, pg_value
from fantasyhoops.draft.rankings import STATS


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
