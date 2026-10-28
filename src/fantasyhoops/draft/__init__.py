"""Draft tools: rankings, the draft board, the auction simulator and the keeper report."""

from fantasyhoops.core import common


def out_dir():
    """The folder of the draft files: output/draft, from common.OUT at the time of the call."""
    return common.OUT / "draft"
