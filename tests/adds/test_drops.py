from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd

from fantasyhoops.adds.drops import (SeasonValue, choose_stream_spots, drop_trade_offs, kept_roster, rank_players,
                                     value_warnings)
from fantasyhoops.adds.planner import Option, StreamSpot, schedule_plan
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.core.common import load_config, name_key

SLOTS = ["PG", "SG", "SF", "PF", "C"]
MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def player(name, team="BOS", positions=("SF",), slot="BN", status=""):
    return Player(name, team, tuple(positions), slot=slot, status=status)


def fa(name, team, value=1.0):
    return Option(Player(name, team, ("SF",)), value)


def config(roster_spots, core=(), stream_spots=3):
    return {"league": {"roster_spots": roster_spots}, "adds": {"core": list(core), "stream_spots": stream_spots}}


def values(**ranks):
    """{name_key(name): SeasonValue} from name=(rank, value)."""
    return {name_key(name): SeasonValue(*rv) for name, rv in ranks.items()}


def run(roster, games, free_agents, cfg, vals, adds=5):
    """The stream spots, the plan and the drops for a roster."""
    spots = choose_stream_spots(roster, cfg, vals)
    days = open_slots_by_day(kept_roster(roster, spots), games, SLOTS)
    plan = schedule_plan(days, games, spots, free_agents, adds, SLOTS)
    return spots, plan, drop_trade_offs(plan, roster, spots, games, free_agents, adds, SLOTS, vals)


def test_the_stream_spots_are_the_empty_spots_then_the_lowest_non_core_players():
    # 10 roster spots. 8 players take a spot, 1 is on IL: 2 spots are empty. The setting gives 3 stream spots,
    # so one player is in a stream spot: Nobody, who is not in the projections file. Low is core.
    roster = [player(n) for n in ["Star", "Good", "Mid", "Low", "Lower", "Nobody", "A", "B"]]
    roster.append(player("Hurt", slot="IL", status="O"))
    vals = values(Star=(5, 2.0), Good=(30, 1.0), Mid=(60, 0.5), Low=(150, -1.0), Lower=(120, -0.5),
                  A=(40, 0.8), B=(50, 0.7), Hurt=(200, -2.0))
    cfg = config(10, core=["Low"])
    spots = choose_stream_spots(roster, cfg, vals)
    assert [s.holder.player.name if s.holder else None for s in spots] == [None, None, "Nobody"]
    # With 4 stream spots, the next holder is Lower: Low is core and Hurt is on IL.
    spots = choose_stream_spots(roster, config(10, core=["Low"], stream_spots=4), vals)
    assert [s.holder.player.name for s in spots[2:]] == ["Nobody", "Lower"]


def test_the_plan_never_drops_a_core_player_also_when_he_is_out():
    # Core is Out and has the lowest value. A PHI free agent plays all week. The roster is full.
    games = {d: {"PHI"} for d in WEEK}
    roster = [player("Core", "BOS", status="O"), player("Bench", "DEN")]
    vals = values(Core=(300, -3.0), Bench=(100, 0.0))
    spots, plan, drops = run(roster, games, [fa("Phi", "PHI")], config(2, core=["Core"], stream_spots=1), vals)
    assert [s.holder.player.name for s in spots] == ["Bench"]
    assert [d.holder.name for d in drops] == ["Bench"]
    assert all(w.player.player.name != "Core" for w in plan.windows)
    # All players are core: no stream spots, so no plan can drop a player.
    spots = choose_stream_spots(roster, config(2, core=["Core", "Bench"], stream_spots=1), vals)
    assert spots == []


def test_an_out_holder_has_no_games():
    # The holder is Out. His team plays all week, but he gives no started games. The plan drops him on Mon.
    games = {d: {"BOS", "PHI"} for d in WEEK}
    roster = [player("Hurt", "BOS", status="O")]
    spots, plan, drops = run(roster, games, [fa("Phi", "PHI")], config(1, stream_spots=1), values())
    assert (plan.started_games, plan.adds) == (7, 1)
    assert [(d.holder.name, d.gain) for d in drops] == [("Hurt", 7)]


def test_a_drop_of_a_non_core_player_that_gains_started_games_shows_the_trade_off():
    # Quickley (TOR) plays Mon, Thu and Fri. PHX plays Thu to Sun. Keep him: 3 started games.
    # Drop him for PHX: Mon with him, then PHX to Sun: 5 started games, so +2.
    games = {WEEK[0]: {"TOR"}, WEEK[3]: {"TOR", "PHX"}, WEEK[4]: {"TOR", "PHX"}, WEEK[5]: {"PHX"}, WEEK[6]: {"PHX"}}
    roster = [player("Quickley", "TOR")]
    vals = values(Quickley=(90, -0.52))
    spots, plan, drops = run(roster, games, [fa("Sun", "PHX")], config(1, stream_spots=1), vals)
    assert (plan.started_games, plan.adds) == (5, 1)
    assert len(drops) == 1
    window = drops[0].window
    assert (window.team, window.last_day) == ("PHX", WEEK[6])
    assert drops[0].text() == (f"Drop Quickley (rank 90, season value -0.52) -> PHX {window.add_day:%a %m/%d} to "
                               f"Sun 01/10: +2 started games this week.")


def test_no_drop_when_the_holder_gives_the_same_started_games():
    # Quickley plays all days. A drop gains nothing, so the plan keeps him and uses no add.
    games = {d: {"TOR", "PHX"} for d in WEEK}
    spots, plan, drops = run([player("Quickley", "TOR")], games, [fa("Sun", "PHX")], config(1, stream_spots=1),
                             values(Quickley=(90, -0.52)))
    assert (plan.started_games, plan.adds, drops) == (7, 0, [])


def test_the_gain_of_a_drop_counts_a_rest_game_of_the_holder_as_in_the_plan():
    # Quickley (TOR, on the rest list) plays Mon and Tue. Tue is a second night, so it counts 0.5.
    # PHX plays Tue to Fri. Drop him on Tue: 1 + 4 = 5 started games. Keep him: 1 + 0.5 = 1.5. So +3.5.
    games = {WEEK[0]: {"TOR"}, WEEK[1]: {"TOR", "PHX"}, WEEK[2]: {"PHX"}, WEEK[3]: {"PHX"}, WEEK[4]: {"PHX"}}
    roster, vals = [player("Quickley", "TOR")], values(Quickley=(90, -0.52))
    spots = [StreamSpot(replace(s.holder, rest_games=((WEEK[1], 0.5),)))
             for s in choose_stream_spots(roster, config(1, stream_spots=1), vals)]
    days = open_slots_by_day(kept_roster(roster, spots), games, SLOTS)
    plan = schedule_plan(days, games, spots, [fa("Sun", "PHX")], 5, SLOTS)
    drops = drop_trade_offs(plan, roster, spots, games, [fa("Sun", "PHX")], 5, SLOTS, vals)
    assert (plan.started_games, [d.gain for d in drops]) == (5, [3.5])


def test_a_warning_shows_for_a_streamer_with_a_higher_value_than_the_lowest_core_player():
    games = {d: {"PHI"} for d in WEEK}
    roster = [player("Core", "BOS"), player("Star", "BOS")]
    vals = values(Core=(130, 0.1), Star=(10, 2.0))
    fas = [fa("Good", "PHI", value=0.5), fa("Weak", "PHI", value=-1.0)]
    cfg = config(3, core=["Core", "Star"])
    spots, plan, _ = run(roster, games, fas, cfg, vals)
    assert value_warnings(plan, roster, spots, cfg, vals) == [
        "Warning: Good (PHI) has a value of +0.50. Your lowest core player, Core, has a season value of +0.10. "
        "You can make Good core."]
    # With no core list, the comparison uses the lowest kept player.
    cfg = config(3)
    assert value_warnings(plan, roster, spots, cfg, vals)[0].startswith("Warning: Good (PHI)")
    assert "lowest kept player, Core," in value_warnings(plan, roster, spots, cfg, vals)[0]


def test_rank_players_ranks_by_per_game_value():
    rng = np.random.default_rng(1)
    n = 200
    names = [chr(97 + i // 26) + chr(97 + i % 26) for i in range(n)]  # aa, ab, ...: name_key() drops digits
    df = pd.DataFrame({"player_id": range(n), "first_name": names,
                       "last_name": ["Last"] * n, "games": 70, "minutes": rng.integers(500, 2500, n)})
    for col in ["field_goals", "threes", "free_throws", "offensive_rebounds", "defensive_rebounds", "assists",
                "steals", "blocks"]:
        df[col] = rng.integers(10, 400, n)
    df.loc[0, ["field_goals", "threes", "free_throws", "offensive_rebounds", "defensive_rebounds", "assists",
               "steals", "blocks"]] = 900
    ranks = rank_players(df, load_config())
    assert ranks[name_key("aa Last")].rank == 1
    assert sorted(r.rank for r in ranks.values()) == list(range(1, n + 1))
    by_rank = sorted(ranks.values(), key=lambda r: r.rank)
    assert all(a.value >= b.value for a, b in zip(by_rank, by_rank[1:]))
