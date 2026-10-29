from dataclasses import replace
from datetime import date, timedelta

import pytest

from fantasyhoops.core import home
from fantasyhoops.trade.suggest import (
    PRE,
    Suggestion,
    TradePlayer,
    TradeSettings,
    in_band,
    kept_set,
    limit,
    player_value,
    rank_key,
    suggest,
    swap,
    week_starts,
)

SLOTS = ["PG", "SG", "SF", "PF", "C"]
WEEKS = ["wk19", "wk20", "wk21"]
CFG = {
    "trade": {
        "untouchable": ["Star Keeper"],
        "value_band": [0.95, 1.10],
        "kept": 8,
        "per_player": 3,
        "rows": 20,
    }
}
SETTINGS = TradeSettings.from_config(CFG)


def days(plays=("ALL",), per_week=2, b2b=()):
    """per_week days in each playoff week. plays: the NBA teams that play each day. b2b: back-to-back teams."""
    out, start = [], date(2027, 3, 8)
    for w, name in enumerate(WEEKS):
        for d in range(per_week):
            out.append(home.Day(start + timedelta(days=7 * w + d), name, False, frozenset(plays), frozenset(b2b)))
    return out


def me(name, value, pos="PG", team="ALL", slot="BN", **kw):
    return TradePlayer(name, team, (pos,) if isinstance(pos, str) else pos, slot=slot, value=value, team_id=1, **kw)


def them(name, value, pos="PG", team="ALL", team_id=2, **kw):
    return TradePlayer(name, team, (pos,) if isinstance(pos, str) else pos, value=value, team_id=team_id, **kw)


# The kept set ------------------------------------------------------------------------------------------------------


def test_the_kept_set_has_8_players_with_the_untouchable_and_the_il_players_always_in():
    roster = [me(f"Player {i}", 3.0 - i * 0.3) for i in range(10)]
    roster += [me("Star Keeper", -5.0), me("Hurt Guard", -4.0, slot="IL"), me("Hurt Wing", -4.5, slot="IL+")]
    kept = kept_set(roster, SETTINGS)
    assert len(kept) == 8
    names = {p.name for p in kept}
    assert {"Star Keeper", "Hurt Guard", "Hurt Wing"} <= names
    assert names - {"Star Keeper", "Hurt Guard", "Hurt Wing"} == {f"Player {i}" for i in range(5)}


def test_a_player_with_no_value_comes_after_the_players_with_a_value():
    roster = [me("No Value", None)] + [me(f"Player {i}", -i) for i in range(8)]
    assert "No Value" not in {p.name for p in kept_set(roster, SETTINGS)}


def test_the_player_you_get_takes_the_spot_of_the_player_you_give():
    a, b, c = me("A", 1.0), me("B", 0.5), them("C", 0.1)
    assert swap([a, b], b, c) == [a, c]
    assert swap([a], b, c) == [a]  # b is not in the kept set: the set does not change


# The value band ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "give, get, inside",
    [
        (1.0, 0.95, True),
        (1.0, 0.9499, False),
        (1.0, 1.10, True),
        (1.0, 1.1001, False),
        (2.0, 1.90, True),
        (2.0, 2.20, True),
        (-2.0, -2.10, True),  # below 0: the low edge is give - 5% of |give|
        (-2.0, -2.1001, False),
        (-2.0, -1.80, True),  # below 0: the high edge is give + 10% of |give|
        (-2.0, -1.7999, False),
        (0.0, 0.0, True),
        (0.0, 0.01, False),
    ],
)
def test_the_value_band_holds_both_edges_also_below_0(give, get, inside):
    assert in_band(give, get, SETTINGS.band) is inside


# The pre fallback --------------------------------------------------------------------------------------------------


def test_a_player_with_no_blended_value_uses_his_pg_value_with_the_pre_mark():
    assert player_value(0.4, 1.2) == (0.4, "")
    assert player_value(None, 1.2) == (1.2, PRE)
    assert player_value(None, None) == (None, "")


def test_a_pair_with_no_value_on_one_side_is_not_scored():
    mine = [me("Starter", 1.0, pos="C", team="NONE")]
    result = suggest(mine, [them("Unknown", None, pos="C")], days(), SLOTS, WEEKS, SETTINGS)
    assert result.pairs == 1 and result.in_band == 0 and result.rows == []


# The starts --------------------------------------------------------------------------------------------------------


def test_the_starts_of_a_fixed_roster_equal_the_result_of_lineup_fit():
    roster = [
        me("Guard", 1.0, pos=("PG", "SG"), team="AAA", rank=3),
        me("Wing", 0.8, pos=("SF",), team="BBB", rank=1),
        me("Big", 0.6, pos=("PF", "C"), team="AAA", rank=2, rests_b2b=True),
        me("Center", 0.4, pos=("C",), team="CCC", slot="IL"),
        me("Forward", 0.2, pos=("SF", "PF"), team="AAA"),
    ]
    playoff = days(plays=("AAA", "BBB"), per_week=3, b2b=("AAA",))
    fit = home.lineup_fit([p.roster_player() for p in roster], playoff, SLOTS)
    assert week_starts(roster, playoff, SLOTS, WEEKS) == tuple(fit.team_week(w)[0] for w in WEEKS)
    assert sum(week_starts(roster, playoff, SLOTS, WEEKS)) > 0


# The suggestions ---------------------------------------------------------------------------------------------------

# Your roster: 4 players of the team ALL (plays each day), and one C of the team NONE (no game). kept = 5.
FIVE = TradeSettings(SETTINGS.untouchable, SETTINGS.band, 5, 3, 20)
MINE = [
    me("Star Keeper", 0.1, pos="SF"),
    me("Point", 2.0, pos="PG"),
    me("Shooter", 1.5, pos="SG"),
    me("Power", 1.2, pos="PF"),
    me("Idle Center", 1.0, pos="C", team="NONE"),
    me("Bench Big", 0.8, pos="C", team="NONE"),
]


def test_a_trade_that_fills_an_empty_slot_is_a_suggestion_with_its_gain():
    others = [them("Busy Center", 1.0, pos="C"), them("Cheap Center", 0.5, pos="C")]
    result = suggest(MINE, others, days(), SLOTS, WEEKS, FIVE)
    assert result.base == (8, 8, 8)
    assert result.pairs == 5 * 2  # 5 players you can give (not Star Keeper), 2 players of the other teams
    assert [(s.give.name, s.get.name) for s in result.rows] == [("Idle Center", "Busy Center")]
    row = result.rows[0]
    assert row.after == (10, 10, 10) and row.gain == 6 and row.min_gain == 2
    assert row.dv == pytest.approx(0.0) and row.partner_dv == pytest.approx(0.0)


def test_no_row_without_a_gain():
    # Busy Point is in the band of Point, but Point already starts each day: no gain, no row.
    result = suggest(MINE, [them("Busy Point", 2.0, pos="PG")], days(), SLOTS, WEEKS, FIVE)
    assert result.in_band >= 1 and result.gains == 0 and result.rows == []


def test_the_player_you_get_below_the_kept_line_adds_no_starts():
    # Bench Big is not kept. Giving him for a busy center changes no counted player, so no gain.
    result = suggest(MINE, [them("Busy Big", 0.8, pos="C")], days(), SLOTS, WEEKS, FIVE)
    assert result.rows == []


def test_giving_an_il_player_does_not_move_the_next_player_up():
    # The IL player is in the kept set. The player you get takes his spot, so Busy Bench (6th by value, not kept)
    # does not come in. A new rank of the kept set after the trade would bring Busy Bench in and show a gain.
    mine = [*MINE[:4], me("Hurt Center", -1.0, pos="C", team="NONE", slot="IL"), me("Busy Bench", 0.9, pos="C")]
    result = suggest(mine, [them("Idle Swap", -1.0, pos="C", team="NONE")], days(), SLOTS, WEEKS, FIVE)
    assert result.rows == []


def test_the_untouchable_player_is_never_given():
    others = [them("Wing Twin", 0.1, pos="SF")]
    result = suggest(MINE, others, days(), SLOTS, WEEKS, FIVE)
    assert all(s.give.name != "Star Keeper" for s in result.rows)
    assert result.pairs == 5


def test_the_partner_side_uses_the_same_rule():
    partner = [them("Busy Center", 1.0, pos="C")] + [them(f"Filler {i}", 3.0 - i, pos="PG") for i in range(6)]
    result = suggest(MINE, partner, days(), SLOTS, WEEKS, FIVE)
    row = result.rows[0]
    assert row.partner_before and len(row.partner_after) == 3
    assert sum(row.partner_after) < sum(row.partner_before)  # their busy center goes, an idle center comes


# The rank and the limits -------------------------------------------------------------------------------------------


def row(give, get, gain, min_gain, dv):
    return Suggestion(me(give, 1.0), them(get, 1.0), (8, 8, 8), (8, 8, 8), gain, min_gain, dv, -dv)


def test_the_rank_is_the_gain_then_the_weakest_week_then_your_value_change():
    rows = [
        row("A", "w", 1, 2, 0.5),
        row("B", "x", 3, 0, -0.1),
        row("C", "y", 1, 2, 0.6),  # ties with A on the gain and the weakest week: the larger value change first
        row("D", "z", 1, 3, -0.2),  # ties with A and C on the gain: the larger gain of the weakest week first
    ]
    assert [r.give.name for r in sorted(rows, key=rank_key)] == ["B", "D", "C", "A"]


def test_at_most_3_rows_for_each_player_you_give_and_20_in_all():
    rows = [row("Point", f"p{i}", 9, 0, 0.0) for i in range(5)]
    rows += [row(f"Giver {g}", f"g{g}-{i}", 5, 0, 0.0) for g in range(10) for i in range(3)]
    out = limit(rows, 3, 20)
    assert len(out) == 20
    assert [r.get.name for r in out if r.give.name == "Point"] == ["p0", "p1", "p2"]


def test_the_settings_come_from_the_trade_section():
    assert SETTINGS.kept == 8 and SETTINGS.band == (0.95, 1.10) and SETTINGS.per_player == 3 and SETTINGS.rows == 20
    assert SETTINGS.is_untouchable(replace(me("x", 0), name="Star  Keeper"))
