from datetime import date
from pathlib import Path

import pytest

from fantasyhoops.trade.deadline import TradeDeadlineNotFound, find_date, read_trade_deadline

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 28)


def test_the_deadline_comes_from_the_trade_end_date_of_the_league_settings():
    html = (FIXTURES / "league_settings.html").read_text(encoding="utf-8")
    assert read_trade_deadline(html, TODAY) == date(2027, 2, 4)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2027-02-04", date(2027, 2, 4)),
        ("2/4/2027", date(2027, 2, 4)),
        ("2/4/27", date(2027, 2, 4)),
        ("Feb 4, 2027", date(2027, 2, 4)),
        ("Thu, Feb 4, 2027", date(2027, 2, 4)),
        ("February 4 2027", date(2027, 2, 4)),
        ("4 Feb 2027", date(2027, 2, 4)),
        ("Thu Feb 4", date(2027, 2, 4)),  # no year: the next year, because Feb 4, 2026 is long past
        ("Nov 30", date(2026, 11, 30)),
    ],
)
def test_the_reader_knows_the_date_forms(text, expected):
    assert find_date(text, TODAY) == expected


def test_the_label_can_be_in_its_own_element_and_in_another_case():
    html = "<dl><dt>TRADE END DATE</dt><dd><span>Feb 4, 2027</span></dd></dl>"
    assert read_trade_deadline(html, TODAY) == date(2027, 2, 4)


def test_a_page_with_no_trade_end_date_gives_a_clear_error():
    with pytest.raises(TradeDeadlineNotFound, match='no "Trade End Date"'):
        read_trade_deadline("<table><tr><td>Max Teams:</td><td>14</td></tr></table>", TODAY)


def test_a_trade_end_date_with_no_date_gives_a_clear_error():
    with pytest.raises(TradeDeadlineNotFound, match="no date after"):
        read_trade_deadline("<p>Trade End Date: None</p>", TODAY)
