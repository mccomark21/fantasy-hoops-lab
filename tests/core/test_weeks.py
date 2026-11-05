from datetime import date

from fantasyhoops.core.common import load_config
from fantasyhoops.core.weeks import FantasyWeek, fantasy_week, week_number


def test_week_19_starts_on_2027_03_08_and_the_playoff_weeks_match_the_calendar():
    cfg = load_config()
    assert fantasy_week(date(2027, 3, 8), cfg) == FantasyWeek(19, date(2027, 3, 8), date(2027, 3, 14))
    for w in cfg["playoffs"]["weeks"]:
        assert fantasy_week(w["start"], cfg) == FantasyWeek(int(w["name"][2:]), w["start"], w["end"]), w


def test_the_2_long_weeks_hold_2_weeks_and_the_other_weeks_hold_7_days():
    cfg = load_config()
    assert fantasy_week(date(2026, 10, 19), cfg) == FantasyWeek(1, date(2026, 10, 19), date(2026, 10, 25))
    assert fantasy_week(date(2026, 11, 5), cfg).number == 3
    assert fantasy_week(date(2026, 12, 10), cfg) == FantasyWeek(7, date(2026, 11, 30), date(2026, 12, 13))
    assert fantasy_week(date(2026, 12, 14), cfg).number == 8
    assert fantasy_week(date(2027, 2, 20), cfg) == FantasyWeek(17, date(2027, 2, 15), date(2027, 2, 28))
    assert fantasy_week(date(2027, 3, 1), cfg).number == 18


def test_a_day_before_week_1_or_with_no_calendar_has_no_week():
    cfg = load_config()
    assert fantasy_week(date(2026, 10, 18), cfg) is None
    assert week_number(date(2026, 11, 5), {}, default=12) == 12
