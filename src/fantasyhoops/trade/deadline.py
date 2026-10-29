"""The reader of the trade deadline ("Trade End Date") on the Yahoo league settings page (#148). It writes no file.

The league settings page is /nba/<league>/settings. No live read has shown the page yet, so the reader is tolerant:
it finds the label "Trade End Date" and reads the first date after it. It knows these date forms:
"2027-02-05", "2/5/2027", "Feb 5, 2027", "Thu, Feb 5, 2027", "February 5 2027", "5 Feb 2027" and "Feb 5" (no year).
"""

import re
from datetime import date, datetime

from fantasyhoops.adds.readers import parse

SETTINGS_PATH = "settings"  # the path of the league settings page for session.League.get()
LABEL = "trade end date"
AFTER = 80  # the characters after the label in which the reader looks for the date
_MONTH = r"(?P<month>[A-Za-z]{3,9})\.?"
_FORMS = [
    re.compile(r"(?P<year>\d{4})-(?P<mon>\d{1,2})-(?P<day>\d{1,2})"),
    re.compile(r"(?P<mon>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4}|\d{2})(?!\d)"),
    re.compile(_MONTH + r"\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{4}))?"),
    re.compile(r"(?P<day>\d{1,2})\s+" + _MONTH + r"(?:,?\s+(?P<year>\d{4}))?"),
]


class TradeDeadlineNotFound(ValueError):
    """The league settings page has no "Trade End Date" with a date that the reader knows."""


def _month(name):
    for form in ("%b", "%B"):
        try:
            return datetime.strptime(name[:3] if form == "%b" else name, form).month
        except ValueError:
            continue
    return None


def _year(month, day, today):
    """The date of month and day with no year: the year of today, or the next year if that date is more than
    180 days before today (as readers.clear_day())."""
    found = date(today.year, month, day)
    return date(today.year + 1, month, day) if (today - found).days > 180 else found


def find_date(text, today):
    """The first date in text, in a form of the module docstring. None if text has no such date."""
    best = None
    for form in _FORMS:
        found = form.search(text)
        if found is None or (best is not None and found.start() >= best[0]):
            continue
        parts = found.groupdict()
        month = int(parts["mon"]) if parts.get("mon") else _month(parts["month"])
        if month is None:
            continue
        year = parts.get("year")
        try:
            if year is None:
                value = _year(month, int(parts["day"]), today)
            else:
                year = int(year) + (2000 if len(year) == 2 else 0)
                value = date(year, month, int(parts["day"]))
        except ValueError:
            continue
        best = (found.start(), value)
    return best[1] if best else None


def read_trade_deadline(html, today):
    """The trade deadline of the league, from the HTML of the league settings page.

    today: the day of the read, for the year of a date with no year.
    The function raises TradeDeadlineNotFound if the page has no "Trade End Date" label, or no date after it.
    """
    text = " ".join(parse(html).get_text(" ", strip=True).split())
    start = text.lower().find(LABEL)
    if start < 0:
        raise TradeDeadlineNotFound('The league settings page has no "Trade End Date".')
    after = text[start + len(LABEL) : start + len(LABEL) + AFTER]
    found = find_date(after, today)
    if found is None:
        raise TradeDeadlineNotFound(
            f'The league settings page has no date after "Trade End Date". The text after the label is {after!r}.'
        )
    return found
