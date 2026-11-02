"""The command python -m fantasyhoops.refresh: the refresh run of refresh/run.py (#220). It writes no files itself."""

import sys

from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.refresh.run import main

if __name__ == "__main__":
    use_utf8_output()
    sys.exit(main())
