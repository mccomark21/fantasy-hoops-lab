"""Draft tools: rankings, the draft board, the auction simulator and the keeper report."""

from fantasyhoops.core import common

# board.py still reads OUT, the folder at import (#127). The other draft modules call out_dir().
OUT = common.OUT / "draft"


def out_dir():
    """The folder of the draft files: output/draft, from common.OUT at the time of the call."""
    return common.OUT / "draft"
