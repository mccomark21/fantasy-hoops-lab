import pytest

from fantasyhoops.trade.builder import ABOVE, BELOW, IN, custom_trade, kept_after, partner_drops
from fantasyhoops.trade.suggest import TradeSettings, kept_set, swap
from tests.trade.test_suggest import SETTINGS, SLOTS, WEEKS, days, me, them

FIVE = TradeSettings(SETTINGS.untouchable, SETTINGS.band, 5, 3, 20)
# Your roster: 4 players of the team ALL (plays each day) and 2 C of the team NONE (no game). kept = 5.
MINE = [
    me("Star Keeper", 0.1, pos="SF"),
    me("Point", 2.0, pos="PG"),
    me("Shooter", 1.5, pos="SG"),
    me("Power", 1.2, pos="PF"),
    me("Idle Center", 1.0, pos="C", team="NONE"),
    me("Bench Big", 0.8, pos="C", team="NONE"),
]
PARTNER = [
    them("Busy Center", 1.0, pos="C"),
    them("Busy Wing", 0.9, pos="SF"),
    them("Busy Guard", 0.7, pos="SG"),
    them("Hurt Forward", -3.0, pos="PF", slot="IL"),
    them("Low Guard", -1.0, pos="PG"),
    them("Lowest Guard", -2.0, pos="PG"),
]


def trade(give, get, drops=(), mine=MINE, partner=PARTNER):
    pick = {p.name: p for p in mine + partner}
    return custom_trade(
        mine,
        partner,
        [pick[n] for n in give],
        [pick[n] for n in get],
        [pick[n] for n in drops],
        days(),
        SLOTS,
        WEEKS,
        FIVE,
    )


def test_a_1_for_1_trade_equals_the_swap_rule_of_the_suggestions():
    t = trade(["Idle Center"], ["Busy Center"])
    kept = kept_set(MINE, FIVE)
    assert kept_after(kept, [MINE[4]], [PARTNER[0]]) == swap(kept, MINE[4], PARTNER[0])
    assert t.mine.before == (8, 8, 8) and t.mine.after == (10, 10, 10)
    assert t.mine.dv == pytest.approx(0.0) and t.partner.dv == pytest.approx(0.0)
    assert t.band == IN and t.mine.open == 0 and t.partner.open == 0 and t.partner.drops == ()


def test_the_players_you_get_take_the_spots_of_the_players_you_give_the_highest_value_first():
    a, b, c = me("A", 1.0), me("B", 0.5), me("C", 0.2)
    x, y = them("X", 0.1), them("Y", 0.9)
    assert kept_after([a, b, c], [a, c], [x, y]) == [y, b, x]
    assert kept_after([a, b], [a, b], [x]) == [x]  # the second freed spot stays empty
    assert kept_after([a, b], [a], [x, y]) == [y, b]  # x gets no freed spot: he is not in the kept set


def test_a_2_for_1_trade_uses_your_drop_and_takes_off_its_value():
    t = trade(["Idle Center"], ["Busy Center", "Busy Wing"], drops=["Bench Big"])
    assert t.mine.drops == (MINE[5],)
    assert t.mine.dv == pytest.approx(1.0 + 0.9 - 1.0 - 0.8)
    assert t.band == "" and t.mine.open == 0
    assert t.partner.open == 1 and t.partner.drops == ()
    assert t.partner.dv == pytest.approx(1.0 - 1.9)


def test_a_dropped_kept_player_frees_a_spot_for_the_second_player_you_get():
    # Power (kept) is the drop: Busy Wing takes his spot, so both players you get count.
    t = trade(["Idle Center"], ["Busy Center", "Busy Wing"], drops=["Power"])
    assert sum(t.mine.after) == sum(t.mine.before) + 6


def test_a_1_for_2_trade_leaves_your_spot_open_and_the_partner_drops_his_lowest_player_not_on_il():
    t = trade(["Idle Center", "Bench Big"], ["Busy Center"])
    assert t.mine.open == 1 and t.mine.drops == ()
    assert t.mine.dv == pytest.approx(1.0 - 1.8)  # the open spot adds 0
    assert t.partner.drops == (PARTNER[5],)  # Lowest Guard, not the Hurt Forward on IL
    assert t.partner.dv == pytest.approx(1.8 - 1.0 + 2.0)


def test_the_partner_drops_a_player_with_no_value_first_and_never_a_player_that_he_gets():
    team = [them("Known", -5.0), them("Unknown", None)]
    assert partner_drops(team, [], 1) == (team[1],)
    assert partner_drops(team, [team[1]], 1) == (team[0],)
    assert partner_drops(team, [], 0) == ()


def test_the_band_verdict_shows_only_for_equal_counts():
    assert trade(["Point"], ["Busy Center"]).band == BELOW
    assert trade(["Bench Big"], ["Busy Center"]).band == ABOVE
    assert trade(["Point", "Shooter"], ["Busy Center", "Busy Wing"]).band == BELOW


@pytest.mark.parametrize(
    "give, get, drops",
    [
        ([], ["Busy Center"], []),
        (["Star Keeper"], ["Busy Center"], []),
        (["Point"], ["Busy Center", "Busy Wing"], []),
        (["Point"], ["Busy Center", "Busy Wing"], ["Point"]),
        (["Point"], ["Busy Center", "Busy Wing"], ["Star Keeper"]),
    ],
)
def test_a_trade_that_breaks_a_rule_raises(give, get, drops):
    with pytest.raises(ValueError):
        trade(give, get, drops)
