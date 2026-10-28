"""The week file (#140): the adds that the runs of one fantasy week recommended, so that the page can show past days.

The design is in docs/adds/README.md, "Week file". The module writes output/adds/week_plan_<first day>.json, one file
for each fantasy week, for example output/adds/week_plan_2026-10-26.json. The path comes from common.OUT (#127).

Each run replaces the saved adds of today and the later days with its new plan (merged()). It never changes the
saved adds of a past day. So a past day shows the adds that the last run on or before that day recommended for it.
The file holds only the recommendations, not the adds that the owner made on Yahoo. It also holds the days of the
runs, so that the page can name the past days with no saved plan.

Each add has a row: the row of the week grid of the page. assign_rows() gives the rows of the adds of a new plan.
"""

import json
from dataclasses import asdict, dataclass
from datetime import date

from fantasyhoops.core import common


@dataclass(frozen=True)
class SavedAdd:
    """One recommended add: row (from 1), day (the add day), slots, teams, starts (the days that he starts) and
    mixed (see team_plan.TeamAdd)."""

    row: int
    day: date
    slots: tuple
    teams: tuple
    starts: tuple
    mixed: bool = False


@dataclass(frozen=True)
class WeekRecord:
    """The saved recommendations of one fantasy week. runs: the days with a run, sorted. adds: the SavedAdds, in order
    of day, then row."""

    runs: tuple = ()
    adds: tuple = ()


def week_path(first_day):
    """The week file of the fantasy week that starts on first_day, from common.OUT at the time of the call."""
    return common.OUT / "adds" / f"week_plan_{first_day:%Y-%m-%d}.json"


def read_record(first_day):
    """The WeekRecord of the week that starts on first_day. An empty WeekRecord if the file is missing or bad."""
    path = week_path(first_day)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        adds = tuple(
            SavedAdd(
                row=int(a["row"]),
                day=date.fromisoformat(a["day"]),
                slots=tuple(a["slots"]),
                teams=tuple(a["teams"]),
                starts=tuple(date.fromisoformat(d) for d in a["starts"]),
                mixed=bool(a.get("mixed", False)),
            )
            for a in data["adds"]
        )
        return WeekRecord(tuple(date.fromisoformat(d) for d in data["runs"]), adds)
    except (OSError, ValueError, KeyError, TypeError):
        return WeekRecord()


def write_record(first_day, record):
    """Write record to the week file of the week that starts on first_day. Return the path."""
    path = week_path(first_day)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "runs": [d.isoformat() for d in record.runs],
        "adds": [
            {**asdict(a), "day": a.day.isoformat(), "starts": [d.isoformat() for d in a.starts]} for a in record.adds
        ],
    }
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return path


def past_adds(record, today):
    """The saved adds of the days before today."""
    return [a for a in record.adds if a.day < today]


def assign_rows(adds, holders, past):
    """{spot: row} for the spots of the TeamAdds adds of a new plan.

    holders: the holder Option (or None) of each stream spot. past: the saved adds of the past days.
    A spot whose holder plays for a team of the last past add of a row continues that row: the add of that row is
    likely the holder. Each other spot takes the lowest row that has no past add and no spot, in order of spot.
    """
    last = {}
    for a in sorted(past, key=lambda a: a.day):
        last[a.row] = a
    rows, taken = {}, set()
    used = sorted({a.spot for a in adds})
    for s in used:
        holder = holders[s] if s < len(holders) else None
        for row, a in sorted(last.items()):
            if holder and row not in taken and holder.player.team in a.teams:
                rows[s] = row
                taken.add(row)
                break
    row = 1
    for s in used:
        if s in rows:
            continue
        while row in taken or row in last:
            row += 1
        rows[s] = row
        taken.add(row)
    return rows


def merged(record, today, adds, rows):
    """The WeekRecord after a run on today with the TeamAdds adds and their rows ({spot: row}, assign_rows()).

    The saved adds of the days before today stay. The adds of today and later are the adds of the new plan."""
    new = [SavedAdd(rows[a.spot], a.day, a.slots, a.teams, a.starts, a.mixed) for a in adds]
    kept = past_adds(record, today)
    return WeekRecord(
        runs=tuple(sorted(set(record.runs) | {today})),
        adds=tuple(sorted(kept + new, key=lambda a: (a.day, a.row))),
    )
