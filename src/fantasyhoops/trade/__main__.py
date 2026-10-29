"""The command python -m fantasyhoops.trade: the trade run of trade/run.py (#150). It writes the files of run.py."""

from fantasyhoops.core.console import use_utf8_output
from fantasyhoops.trade.run import main

if __name__ == "__main__":
    use_utf8_output()
    main()
