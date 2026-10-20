from fantasyhoops.core.lineup import best_lineup, open_slots, starting_slots

SLOTS = ["PG", "SG", "SF", "PF", "C"]


def test_util_takes_a_second_player_at_one_position():
    # C and Util take the 2 best centers. The third center sits.
    assert best_lineup([{"C"}, {"C"}, {"C"}], SLOTS) == [0, 1]


def test_a_player_with_several_positions_takes_his_open_position():
    # PG and Util are full after 0 and 1. The PG/SG player starts at SG. The next PG sits.
    assert best_lineup([{"PG"}, {"PG"}, {"PG", "SG"}, {"PG"}], SLOTS) == [0, 1, 2]


def test_a_starter_moves_to_his_other_position_to_make_room():
    # 0 moves from PG to SG so that 1 gets PG. 2 takes Util. 3 is SG only and sits: the better players hold SG and Util.
    assert best_lineup([{"PG", "SG"}, {"PG"}, {"PG"}, {"SG"}], SLOTS) == [0, 1, 2]


def test_more_players_than_slots():
    # 8 players for 6 slots: each slot is full, and the 2 worst players sit.
    players = [{"PG"}, {"SG"}, {"SF"}, {"PF"}, {"C"}, {"SF", "PF"}, {"C"}, {"PG", "SG", "SF", "PF", "C"}]
    assert best_lineup(players, SLOTS) == [0, 1, 2, 3, 4, 5]


def test_no_players():
    assert best_lineup([], SLOTS) == []


def test_open_slots_counts_the_slots_that_no_player_fills():
    # The SF/PF player moves to PF so that the SF player gets SF. PG and C stay open.
    assert open_slots([["SF", "PF"], ["SF"], ["SG"]], SLOTS) == 2


def test_starting_slots_names_the_slot_of_each_starter():
    # 0 moves to SG so that 1 gets PG. 2 is the second PG and takes Util. 3 sits.
    assert starting_slots([{"PG", "SG"}, {"PG"}, {"PG"}, {"SG"}], SLOTS) == {0: "SG", 1: "PG", 2: "Util"}


def test_starting_slots_with_no_players():
    assert starting_slots([], SLOTS) == {}
