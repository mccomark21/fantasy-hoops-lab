"""The calendar of the fantasy weeks of the Yahoo league: [weeks] in config.toml (#236).

Week 1 starts on [weeks] first. Each week is Monday to Sunday, except a long week of [weeks] long: 2 weeks in one.
The adds page takes its week number from this calendar. The module writes no files.
"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class FantasyWeek:
    """One fantasy week: its number, its first day and its last day."""

    number: int
    start: object
    end: object


def fantasy_week(day, cfg):
    """The FantasyWeek that holds day, or None if day is before week 1 or cfg has no [weeks] section."""
    if "weeks" not in cfg:
        return None
    first = cfg["weeks"]["first"]
    long = {w["start"]: w["end"] for w in cfg["weeks"].get("long", ())}
    if day < first:
        return None
    number, start = 1, first
    while True:
        end = long.get(start, start + timedelta(days=6))
        if day <= end:
            return FantasyWeek(number, start, end)
        number, start = number + 1, end + timedelta(days=1)


def week_number(day, cfg, default=None):
    """The number of the fantasy week that holds day, or default if the calendar does not hold day."""
    week = fantasy_week(day, cfg)
    return week.number if week else default
