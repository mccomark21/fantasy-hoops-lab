import pandas as pd
import pytest

from fantasyhoops.adds.readers import Player
from fantasyhoops.core import profile
from fantasyhoops.players import data
from fantasyhoops.players.data import Played, Projected, Signal
from fantasyhoops.trade.rostered import RosteredPlayer


def rostered(name, team_id, team_name, nba="PHI", positions=("PG",)):
    return RosteredPlayer(Player(name, nba, positions), 0, {}, team_id, team_name)


OWNED = data.owned_players(
    [
        rostered("Ace Bailey", 1, "Lamb Chops", "UTAH", ("SF", "PF")),
        rostered("Karl-Anthony Towns", 3, "Doncic Go", "NY", ("PF", "C")),
        rostered("No Data Guy", 3, "Doncic Go"),
    ],
    own_team=1,
)
PROJECTED = {
    "ace bailey": Projected("Ace Bailey", "UTAH", ("SF",), 0.52),
    "karl anthony towns": Projected("Karl-Anthony Towns", "NY", ("C",), 4.65),
    "fa projected": Projected("Fa Projected", "BOS", ("C",), -1.2),
}
PLAYED = {
    "ace bailey": Played("Ace Bailey", "UTAH", 5),
    "fa five": Played("Fa Five", "NY", 5),
    "fa four": Played("Fa Four", "NY", 4),
}
# The Val of the Free agents page: the market value. Fa Plus is above the replacement free agent, Fa Zero is at it.
VALUES = {
    "ace bailey": data.Valued(Player("Ace Bailey", "UTAH", ("SF", "PF")), 0.52),
    "fa plus": data.Valued(Player("Fa Plus", "BOS", ("C",)), 0.31),
    "fa zero": data.Valued(Player("Fa Zero", "BOS", ("PG",)), 0.0),
    "fa four": data.Valued(Player("Fa Four", "NY", ("SG",)), -0.4),
}


def test_the_list_has_each_rostered_player_and_each_free_agent_above_replacement_or_with_5_games():
    """Owner decision of 2026-10-30: a free agent is on the page with a Val above 0 or with 5 or more games."""
    records = data.player_records(OWNED, PROJECTED, PLAYED, VALUES)
    by_slug = {r["slug"]: r for r in records}
    # Each rostered player, also with no Val and no game. Fa Projected has a projection but no Val, Fa Zero is at the
    # replacement level, and Fa Four has 4 games and a Val below 0, so none of the three is on the page.
    assert set(by_slug) == {"ace-bailey", "karl-anthony-towns", "no-data-guy", "fa-plus", "fa-five"}
    assert [r["slug"] for r in records] == ["ace-bailey", "fa-plus", "fa-five", "karl-anthony-towns", "no-data-guy"]
    assert by_slug["ace-bailey"] == {
        "slug": "ace-bailey",
        "name": "Ace Bailey",
        "team": "UTAH",
        "pos": "SF/PF",  # the Yahoo positions of the rostered list
        "owner": "Lamb Chops",
        "mine": True,
        "val": 0.52,
        "games": 5,
        "signals": [],
    }
    assert by_slug["karl-anthony-towns"]["mine"] is False and by_slug["karl-anthony-towns"]["owner"] == "Doncic Go"
    assert by_slug["karl-anthony-towns"]["val"] is None  # no Yahoo line in the run
    assert by_slug["fa-five"] == {
        "slug": "fa-five",
        "name": "Fa Five",
        "team": "NY",
        "pos": "",
        "owner": None,
        "mine": False,
        "val": None,
        "games": 5,
        "signals": [],
    }
    assert by_slug["fa-plus"]["pos"] == "C" and by_slug["fa-plus"]["team"] == "BOS"


def test_the_val_is_the_val_of_the_free_agents_page():
    """Owner decision of 2026-10-30: the same blend and the same replacement value as the Free agents page."""
    from fantasyhoops.adds.blend import blended_options
    from fantasyhoops.adds.readers import FreeAgent
    from fantasyhoops.adds.value import market_value
    from fantasyhoops.trade.rostered import RosteredRead

    scale = pd.DataFrame({"pts": [10.0, 5.0]}, index=["mean", "std"])
    cfg = {"weights": {"pts": 1.0}}
    star = RosteredPlayer(Player("Star", "NY", ("C",)), 3, {"pts": 30.0}, 3, "Doncic Go")
    star_recent = RosteredPlayer(Player("Star", "NY", ("C",)), 7, {"pts": 20.0}, 3, "Doncic Go")
    read = RosteredRead([star], [star_recent], {}, [], False)
    fa = blended_options([FreeAgent(Player("Free Guy", "BOS", ("PG",)), 0, {"pts": 15.0})], [], scale, cfg)
    values = data.market_values(read, fa, 0.5, scale, cfg)
    # Star: (1 - 7/14) x 30 + 7/14 x 20 = 25 points, (25 - 10) / 5 = 3.0, minus 0.5.
    assert values["star"].val == 2.5 == market_value(blended_options([star], [star_recent], scale, cfg)[0].value, 0.5)
    assert values["free guy"].val == market_value(fa[0].value, 0.5) == 0.5
    assert values["free guy"].player.team == "BOS"


def test_the_signals_are_the_first_3_of_the_rules_and_each_links_to_a_quadrant():
    def rule(n):
        return lambda record: Signal(f"Rule {n}", "role", n % 2 == 0, f"{record['name']} {n}")

    record = {"name": "Ace Bailey"}
    found = data.signals(record, [rule(1), lambda r: None, rule(2), rule(3), rule(4)])
    assert [s["kind"] for s in found] == ["Rule 1", "Rule 2", "Rule 3"]
    assert found[0] == {"kind": "Rule 1", "quadrant": "role", "up": False, "text": "Ace Bailey 1"}
    assert data.signals(record) == []  # no rule yet: the header says profile.NO_SIGNALS
    with pytest.raises(ValueError, match="not a quadrant"):
        data.signals(record, [lambda r: Signal("Bad", "trends", True, "x")])
    rules = [rule(1)]
    assert data.player_records(OWNED, {}, {}, {}, rules)[0]["signals"][0]["kind"] == "Rule 1"
    assert profile.MAX_SIGNALS == 3


OVERRIDES = pd.DataFrame(
    {
        "player_id": ["10"],
        "name": ["Proj Name"],
        "espn_name": ["Espn Name"],
        "yahoo_name": ["Yahoo Name"],
        "team": [""],
    }
)


def projections():
    """4 players. With 1 team of 2 roster spots, the pool is the first 2 and the replacement tier is the third."""
    rows = [("10", "Proj", "Name", 30), ("11", "Big", "Star", 40), ("12", "Mid", "Guy", 20), ("13", "Low", "Guy", 10)]
    df = pd.DataFrame(rows, columns=["player_id", "first_name", "last_name", "pts"])
    df["player_id"] = df.player_id.astype(int)
    for col in ("free_throws", "threes", "offensive_rebounds", "assists", "steals", "blocks"):
        df[col] = 0
    df["field_goals"] = df.pop("pts") * 10
    df["defensive_rebounds"] = 0
    df["games"] = 10
    df["minutes"] = df.field_goals
    return pd.concat([df, df.head(1).assign(player_id=99, first_name="No", last_name="Games", games=0)])


CFG = {
    "league": {"teams": 1, "roster_spots": 2},
    "weights": {"pts": 1.0},
    "games": {"full_season": 10, "power": 1},
    "auction": {"spots": 2, "budget": 200, "min_bid": 1},
}


def test_a_projection_and_a_log_name_find_the_yahoo_name_of_an_override():
    rosters = pd.DataFrame({"espn_name": ["Espn Name"], "team": ["MIA"]})
    yahoo = pd.DataFrame(
        {"yahoo_id": [1], "name": ["Yahoo Name"], "positions": ["SG,SF"], "status": [""], "yahoo_rank": [1]}
        | {c: [0] for c in ("pct_drafted", "yahoo_cost", "yahoo_value", "adp")}
    )
    projected = data.projected_players(projections(), rosters, yahoo, OVERRIDES, CFG)
    assert set(projected) == {"yahoo name", "big star", "mid guy", "low guy"}  # no row with 0 games
    assert projected["yahoo name"] == Projected("Yahoo Name", "MIA", ("SG", "SF"), projected["yahoo name"].value)
    # The value is per game above the replacement tier (Mid Guy), so the replacement player is at 0.
    assert (
        projected["mid guy"].value == pytest.approx(0) and projected["big star"].value > projected["yahoo name"].value
    )
    log = pd.DataFrame(
        {
            "game_id": ["1", "2", "2", "3"],
            "date": pd.to_datetime(["2026-10-20", "2026-10-22", "2026-10-22", "2026-10-24"]),
            "player_id": ["7", "7", "7", "8"],
            "player": ["Espn Name"] * 3 + ["Other Guy"],
            "team": ["MIA", "MIA", "MIA", "BOS"],
        }
    )
    played = data.played_players(log, OVERRIDES)
    assert played == {"yahoo name": Played("Espn Name", "MIA", 2), "other guy": Played("Other Guy", "BOS", 1)}
    records = data.player_records(
        {}, projected, played, {"yahoo name": data.Valued(Player("Yahoo Name", "MIA", ()), 1.0)}
    )
    assert [(r["name"], r["games"]) for r in records if r["slug"] == "yahoo-name"] == [("Yahoo Name", 2)]


def test_with_no_data_files_the_reads_give_no_players(monkeypatch, tmp_path):
    monkeypatch.setattr(data.common, "DATA", tmp_path)
    monkeypatch.setattr(data.common, "ROOT", tmp_path)
    assert data.read_projected({"league": {"projections": "data/Projections_*.csv"}}) == ({}, None)
    assert data.read_played() == ({}, None, None)
