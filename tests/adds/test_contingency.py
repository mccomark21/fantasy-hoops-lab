from datetime import date, timedelta

import pandas as pd

from fantasyhoops.adds.contingency import contingency_plans, game_times
from fantasyhoops.adds.planner import Option, StreamSpot, schedule_plan
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def fa(name, team, positions=("SF",), value=1.0, status=""):
    return Option(Player(name, team, tuple(positions), status=status), value)


def plans(roster, games, free_agents, spots=1, adds=5, times=None):
    days = open_slots_by_day(roster, games, SLOTS)
    stream = [StreamSpot()] * spots
    main = schedule_plan(days, games, stream, free_agents, adds, SLOTS)
    return main, contingency_plans(days, games, main, spots, free_agents, adds, SLOTS, times)


def roster(flag="Q", bench=("PG",)):
    """5 BOS starters (the SF has the status flag) and bench players of BOS with the positions in bench."""
    starters = [Player(f"P{i}", "BOS", (pos,), status=flag if pos == "SF" else "")
                for i, pos in enumerate(["PG", "SG", "SF", "PF", "C"])]
    return starters + [Player(f"B{i}", "BOS", (pos,)) for i, pos in enumerate(bench)]


def test_a_lineup_move_when_a_bench_player_can_fill_the_slot():
    # BOS plays Mon. Six players fill all 6 slots. A seventh player (an SF) sits on the bench. If the
    # questionable SF is out, the bench SF takes a slot, and the number of starters stays the same.
    team = roster(bench=("PG", "SF"))
    _, out = plans(team, {WEEK[0]: {"BOS"}}, [])
    assert [(c.player.name, c.day, c.move.name) for c in out] == [("P2", WEEK[0], "B1")]
    assert out[0].late_adds == ()


def test_a_late_add_with_its_cost_when_no_move_works():
    # BOS plays Mon and Tue. The roster fills all 6 slots on both days, with no bench player. Wed and Thu are open
    # days. The main plan adds a PHI streamer on Wed for Wed and Thu and keeps 4 adds.
    # On Mon the spot is empty, so the late add drops nobody. NYK (19:30) starts before BOS (20:00) and is not
    # a late add. LAL (22:30) is.
    games = {WEEK[0]: {"BOS", "NYK", "LAL"}, WEEK[1]: {"BOS", "LAL"}, WEEK[2]: {"PHI"}, WEEK[3]: {"PHI"}}
    times = {(WEEK[0], "BOS"): "20:00", (WEEK[0], "NYK"): "19:30", (WEEK[0], "LAL"): "22:30"}
    fas = [fa("Phi", "PHI"), fa("Early", "NYK", value=5), fa("Late", "LAL", value=2)]
    main, out = plans(roster(), games, fas, times=times)
    assert (main.started_games, main.adds) == (2, 1)
    assert [(c.day, c.move) for c in out] == [(WEEK[0], None), (WEEK[1], None)]
    mon = out[0]
    assert [(o.player.name, t) for o, t in mon.late_adds] == [("Late", "22:30")]
    assert (mon.drop, mon.lost, mon.adds_left) == (None, (), 4)
    # No time for Tue: each free agent who plays and fits is listed, and you check the game times.
    assert [(o.player.name, t) for o, t in out[1].late_adds] == [("Late", None)]


def test_a_late_add_drops_the_streamer_and_ends_his_window():
    # The PHI streamer holds the spot from Mon to Thu, but PHI does not play Tue. On Tue the flagged SF is out:
    # the late add (LAL) replaces the streamer, so the PHI window ends early and loses Wed and Thu.
    full = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "PF", "C", "C"])]
    games = {WEEK[0]: {"PHI"}, WEEK[1]: {"BOS", "LAL"}, WEEK[2]: {"PHI"}, WEEK[3]: {"PHI"}}
    team = full + [Player("Flag", "BOS", ("SF",), status="Q")]
    main, out = plans(team, games, [fa("Phi", "PHI"), fa("Late", "LAL")], adds=1)
    assert (main.started_games, main.adds) == (3, 1)
    (c,) = out
    assert (c.day, c.drop.team, c.lost, c.adds_left) == (WEEK[1], "PHI", (WEEK[2], WEEK[3]), 0)
    assert [o.player.name for o, _ in c.late_adds] == ["Late"]


def test_no_plan_for_a_healthy_or_an_out_player():
    for flag in ("", "O", "NA"):
        _, out = plans(roster(flag=flag), {WEEK[0]: {"BOS", "LAL"}}, [fa("Late", "LAL")])
        assert out == []


def test_game_times_from_the_schedule():
    sched = pd.DataFrame({"date": ["2027-01-04"], "team": ["BOS"], "opponent": ["NYK"], "time": ["19:30"]})
    assert game_times(sched) == {(WEEK[0], "BOS"): "19:30"}
    assert game_times(sched.drop(columns="time")) == {}
