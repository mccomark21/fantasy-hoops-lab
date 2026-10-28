import json
from datetime import date, timedelta

from fantasyhoops.adds.planner import Option, StreamSpot
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.team_plan import TeamAdd
from fantasyhoops.adds.week_file import (
    SavedAdd,
    WeekRecord,
    assign_rows,
    merged,
    past_adds,
    read_record,
    week_path,
    write_record,
)
from fantasyhoops.core import common

MON = date(2026, 10, 26)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def add(spot, day, teams=("SAC",), slots=("SG",)):
    return TeamAdd(spot, day, WEEK[6], slots, teams, (day,))


def run(record, today, adds, holders=(None, None, None)):
    """The record after a run on today with the TeamAdds adds, as the planning run makes it."""
    rows = assign_rows(adds, list(holders), past_adds(record, today))
    return merged(record, today, adds, rows)


def test_the_week_file_is_under_common_out_and_names_the_first_day_of_the_week():
    assert week_path(MON) == common.OUT / "adds" / "week_plan_2026-10-26.json"


def test_a_written_record_reads_back_the_same():
    record = WeekRecord(
        runs=(WEEK[0], WEEK[2]),
        adds=(SavedAdd(1, WEEK[3], ("SG", "PF"), ("ATL", "SAC"), (WEEK[3], WEEK[5]), True),),
    )
    path = write_record(MON, record)
    assert path == week_path(MON)
    assert read_record(MON) == record
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["adds"][0] == {
        "row": 1,
        "day": "2026-10-29",
        "slots": ["SG", "PF"],
        "teams": ["ATL", "SAC"],
        "starts": ["2026-10-29", "2026-10-31"],
        "mixed": True,
    }


def test_a_missing_or_bad_file_gives_an_empty_record():
    assert read_record(MON) == WeekRecord()
    week_path(MON).parent.mkdir(parents=True, exist_ok=True)
    week_path(MON).write_text("{not json", encoding="utf-8")
    assert read_record(MON) == WeekRecord()


def test_a_later_run_replaces_a_future_day_and_keeps_a_past_day():
    # The run of Mon recommends adds on Mon and Thu. The run of Wed recommends Fri. Mon is past on Wed, so its add
    # stays. The Thu add of the Mon run is not kept.
    monday = run(WeekRecord(), WEEK[0], [add(0, WEEK[0], ("OKC",)), add(1, WEEK[3], ("ATL",))])
    assert [(a.row, a.day, a.teams) for a in monday.adds] == [(1, WEEK[0], ("OKC",)), (2, WEEK[3], ("ATL",))]
    write_record(MON, monday)
    wednesday = run(read_record(MON), WEEK[2], [add(0, WEEK[4], ("BOS",))])
    write_record(MON, wednesday)
    saved = read_record(MON)
    assert saved.runs == (WEEK[0], WEEK[2])
    assert [(a.day, a.teams) for a in saved.adds] == [(WEEK[0], ("OKC",)), (WEEK[4], ("BOS",))]
    # A second run on the same day replaces the adds of that day too.
    again = run(saved, WEEK[2], [add(0, WEEK[2], ("CHI",))])
    assert [(a.day, a.teams) for a in again.adds] == [(WEEK[0], ("OKC",)), (WEEK[2], ("CHI",))]
    assert again.runs == (WEEK[0], WEEK[2])


def test_a_run_with_no_add_removes_the_future_adds_and_keeps_the_past_adds():
    record = run(WeekRecord(), WEEK[0], [add(0, WEEK[0]), add(1, WEEK[4])])
    assert [a.day for a in run(record, WEEK[1], []).adds] == [WEEK[0]]


def test_a_spot_whose_holder_plays_for_a_team_of_a_past_add_continues_its_row():
    # Mon: row 1 adds a SG from OKC, row 2 a PG from POR. On Wed, spot 1 holds an OKC player, so its add goes in row 1.
    record = run(WeekRecord(), WEEK[0], [add(0, WEEK[0], ("OKC",)), add(1, WEEK[0], ("POR",))])
    holders = [None, Option(Player("Ajay", "OKC", ("SG",)), -1.0), None]
    rows = assign_rows([add(1, WEEK[3]), add(2, WEEK[3])], holders, past_adds(record, WEEK[2]))
    # Spot 2 has no link. Rows 1 and 2 hold past adds, so it takes row 3.
    assert rows == {1: 1, 2: 3}


def test_with_no_past_adds_the_spots_take_the_rows_in_order():
    holders = [StreamSpot().holder] * 3
    assert assign_rows([add(2, WEEK[1]), add(0, WEEK[3]), add(2, WEEK[5])], holders, []) == {0: 1, 2: 2}
