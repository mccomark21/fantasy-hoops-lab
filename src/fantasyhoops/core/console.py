"""Terminal output helper that each command calls at the start of its __main__ block. It writes no files.

On Windows, Python writes piped or redirected output in the cp1252 code page.
A print of a player name with a letter outside cp1252 (for example "č") then stops the run (#87).
"""

import sys


def use_utf8_output(*streams):
    """Set each stream to UTF-8. With no streams, set the standard output and the standard error.

    The helper skips a stream that has no reconfigure() method, for example a stream that a test replaced.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=stream.errors)  # without errors=, reconfigure() resets it to strict
