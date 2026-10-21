from fantasyhoops.adds.planner import Option
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.value import replacement_value


def option(value, status=""):
    return Option(Player("P", "PHI", ("C",), status=status), value)


def test_the_replacement_value_is_the_value_at_the_rank():
    options = [option(v) for v in (0.5, 3.0, -1.0, 2.0, None)]
    assert replacement_value(options, rank=2) == 2.0
    # An Out player does not count.
    assert replacement_value([option(9.0, "O"), *options], rank=1) == 3.0


def test_with_few_options_the_replacement_is_the_last_one():
    assert replacement_value([option(1.0), option(-2.0)], rank=15) == -2.0
    assert replacement_value([option(None)]) is None
