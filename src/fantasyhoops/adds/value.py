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


def empty_slot_value(cfg, scale=None):
    """The value of an empty starting slot: the per-game value of a stat line of zeros.

    The aggressive plan counts the value of each started game above this value (planner.aggressive_score()).
    scale: from projection_scale(). If None, the function reads the projections file.
    """
    scale = projection_scale(cfg) if scale is None else scale
    return line_value({cat: 0.0 for cat in cfg["weights"]}, scale, cfg)
