"""core/starts.js, the shared lineup-and-starts engine of the browser (#213).

1. The draft engine and the trade engine give the numbers of before the move. fixtures/starts_before_213.json holds
   a fixed input and the output of draft/team_builder.js and trade/trade_builder.js at
   mccomark21/fantasy-hoops-lab@4071364, before the move.
2. valueStarted() rests a player of the rester set as lineup_fit() of core/roster.py does.
3. valueStarted() adds the light-night bonus of [quality_games] in config.toml.
"""

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from fantasyhoops import draft
from fantasyhoops.core import roster as roster_page
from fantasyhoops.core.common import load_config
from fantasyhoops.core.lineup import ENGINE_JS, best_lineup, ideal_games
from fantasyhoops.draft import board
from fantasyhoops.trade import page as trade_page

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")

DRAFT_ENGINE = Path(draft.__file__).parent / "team_builder.js"
BEFORE = Path(__file__).parent / "fixtures" / "starts_before_213.json"
SLOTS = ["PG", "SG", "SF", "PF", "C"]

# argv: the draft engine and the trade engine. Reads {"draft", "trade"} on stdin (the "input" of the fixture).
# Writes the numbers of both engines: the draft score, fits, slots, bench, footer and bands, and the trade results.
# globalThis.TeamBuilder is for the trade engine of before the move. The engine of after the move loads core/starts.js.
DRIVER = """
const TB = require(process.argv[1]);
globalThis.TeamBuilder = TB;
const TR = require(process.argv[2]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { draft, trade } = JSON.parse(text);
  const d = draft.data, byId = new Map(d.players.map(p => [p.id, p]));
  const core = draft.core.map(id => byId.get(id));
  const score = TB.scoreCore(core, d);
  const fits = draft.fit.map(id => TB.fit(core, byId.get(id), d));
  const roster = TB.slotRoster(core, d);
  const slots = Object.fromEntries(Object.entries(roster.slots).map(([s, p]) => [s, p.name]));
  const footer = TB.footerWeeks(core, score, d);
  const bands = draft.ratios.map(r => TB.band(r, d));
  const t = trade.data, all = new Map(t.me.map(p => [p.id, p]));
  t.teams.forEach(team => team.roster.forEach(p => all.set(p.id, p)));
  const pick = ids => ids.map(id => all.get(id));
  const trades = trade.cases.map(c => {
    const team = t.teams.find(x => x.id === c.team);
    const r = TR.trade(t.me, team.roster, pick(c.give), pick(c.get), pick(c.drops), t.engine);
    const ids = side => ({ ...side, drops: side.drops.map(p => p.id) });
    return { mine: ids(r.mine), partner: ids(r.partner), band: r.band };
  });
  const starts = TR.weekStarts(t.me, t.engine);
  process.stdout.write(JSON.stringify({
    draft: { score, fits, slots, bench: roster.bench.map(p => p.name), footer, bands },
    trade: { trades, starts },
  }));
});
"""


def run_engines(given, draft_engine=DRAFT_ENGINE, trade_engine=trade_page.TRADE_ENGINE):
    """The numbers of the draft engine and the trade engine on the input of the fixture."""
    out = subprocess.run(
        ["node", "-e", DRIVER, str(draft_engine), str(trade_engine)],
        input=json.dumps(given),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


# argv: core/starts.js. Reads {"core", "data", "resters"} on stdin. Writes valueStarted() of the core.
VALUE_DRIVER = """
const Starts = require(process.argv[1]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { core, data, resters } = JSON.parse(text);
  process.stdout.write(JSON.stringify(Starts.valueStarted(core, data, resters === null ? undefined : resters)));
});
"""


def value_started(core, data, resters=None):
    out = subprocess.run(
        ["node", "-e", VALUE_DRIVER, str(ENGINE_JS)],
        input=json.dumps({"core": core, "data": data, "resters": resters}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


def day(when, week, teams, quality=False, b2b=()):
    return {"date": when, "week": week, "quality": quality, "teams": list(teams), "b2b": list(b2b)}


def player(id, team, pos, value, rests_b2b=False):
    return {"id": id, "name": id, "team": team, "pos": pos.split("/"), "value": value, "rests_b2b": rests_b2b}


def engine_data(days, bonus=0.0):
    return {"slots": SLOTS, "util": 1, "weeks": ["wk19"], "days": days, "quality_bonus": bonus}


def test_the_draft_and_trade_engines_give_the_numbers_of_before_the_move():
    fixture = json.loads(BEFORE.read_text(encoding="utf-8"))
    assert run_engines(fixture["input"]) == fixture["before"]


def test_no_tool_engine_keeps_a_copy_of_the_lineup_code():
    for path in (DRAFT_ENGINE, trade_page.TRADE_ENGINE):
        text = path.read_text(encoding="utf-8")
        assert "function _match" not in text and "function _day" not in text, path.name
    assert trade_page.ENGINE == ENGINE_JS


def test_the_pages_run_the_inlined_engines_with_no_require():
    # A browser has no require() and no module. The draft board inlines its engine in a closure with a module object.
    draft_page = (
        "const engine = (() => { const module = {exports: {}};\n"
        + board.engine_js()
        + "\nreturn module.exports; })();\nout.push(typeof engine.scoreCore, typeof engine.footerWeeks);\n"
    )
    trade_script = (
        trade_page.ENGINE.read_text(encoding="utf-8")
        + "\n"
        + trade_page.TRADE_ENGINE.read_text(encoding="utf-8")
        + "\nout.push(typeof TradeBuilder.trade, typeof Starts.valueStarted);\n"
    )
    script = "const out = [];\n" + "".join(
        f"((require, module) => {{\n{s}\n}})();\n" for s in (draft_page, trade_script)
    )
    script += "process.stdout.write(out.join(' '));"
    # The script goes on stdin, because it is longer than a Windows command line.
    got = subprocess.run(["node"], input=script, capture_output=True, text=True, check=True, encoding="utf-8").stdout
    assert got == "function function function function"


def test_a_player_in_the_rester_set_sits_the_second_night_as_in_lineup_fit():
    # Day 1: BOS and NY play. Day 2: both play again, a back-to-back. The rester set holds "a" only.
    days = [
        roster_page.Day(date(2027, 3, 8), "wk19", False, frozenset({"BOS", "NY"}), frozenset()),
        roster_page.Day(date(2027, 3, 9), "wk19", False, frozenset({"BOS", "NY"}), frozenset({"BOS", "NY"})),
    ]
    a = roster_page.RosterPlayer("a", "BOS", ("PG",), rank=1, rests_b2b=True)
    b = roster_page.RosterPlayer("b", "NY", ("C",), rank=2, rests_b2b=False)
    fit = roster_page.lineup_fit([a, b], days, SLOTS)
    want = {p.name: marks for p, marks in zip(fit.players, fit.marks)}

    data = engine_data([day(d.date.isoformat(), d.week, sorted(d.teams), b2b=sorted(d.b2b)) for d in days])
    # rests_b2b of the players says the opposite. The rester set decides.
    core = [player("a", "BOS", "PG", 5.0, rests_b2b=False), player("b", "NY", "C", 4.0, rests_b2b=True)]
    got = value_started(core, data, resters=["a"])
    assert got["marks"] == want == {"a": ["s", "r"], "b": ["s", "s"]}
    assert [d["starts"] for d in got["days"]] == fit.started == [2, 1]

    # With no rester set, rests_b2b of each player decides.
    assert value_started(core, data)["marks"] == {"a": ["s", "s"], "b": ["s", "r"]}


def test_a_started_game_on_a_light_night_gets_the_quality_games_bonus_of_the_config():
    cfg = load_config()
    bonus = cfg["quality_games"]["bonus"]
    assert bonus > 0
    # A light night (6 or fewer NBA games) and a heavy night. "a" starts on both. "b" plays only on the light night.
    days = [day("2027-03-08", "wk19", ["BOS", "NY"], quality=True), day("2027-03-09", "wk19", ["BOS"])]
    core = [player("a", "BOS", "PG", 4.0), player("b", "NY", "C", 2.5)]
    got = value_started(core, engine_data(days, bonus))
    light, heavy = got["days"]
    assert light["value"] == pytest.approx((4.0 + 2.5) * (1 + bonus))
    assert heavy["value"] == pytest.approx(4.0)
    week = got["weeks"]["wk19"]
    assert week["value"] == pytest.approx(got["total"]["value"]) == pytest.approx(6.5 * (1 + bonus) + 4.0)
    assert (week["starts"], week["light_starts"]) == (3, 2)


def test_value_started_counts_the_starts_lost_and_the_open_slots_of_each_day():
    # 3 C players and 1 C slot + 1 Util: 1 C sits. The 4 empty slots are open. A day with no games has no open slot.
    days = [
        day("2027-03-08", "wk19", ["BOS"], quality=True),
        day("2027-03-09", "wk19", ["NY"]),
        day("2027-03-10", "wk19", []),
    ]
    core = [player("c1", "BOS", "C", 3.0), player("c2", "BOS", "C", 2.0), player("c3", "BOS", "C", 1.0)]
    got = value_started(core, engine_data(days))
    assert [(d["starts"], d["lost"], d["open"]) for d in got["days"]] == [(2, 1, 4), (0, 0, 6), (0, 0, 0)]
    assert got["marks"]["c3"] == ["b", "n", "n"]
    week = got["weeks"]["wk19"]
    assert (week["lost"], week["open_light"], week["open_heavy"]) == (1, 4, 6)


# argv: core/starts.js. Reads {"data", "cases"} on stdin, cases [[size, week], ...]. Writes idealGames() of each case.
IDEAL_DRIVER = """
const Starts = require(process.argv[1]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { data, cases } = JSON.parse(text);
  process.stdout.write(JSON.stringify(cases.map(([size, week]) => Starts.idealGames(size, data, week))));
});
"""


def test_ideal_games_of_the_engine_equals_ideal_games_of_core_lineup():
    """#214: the Starts row of the playoffs page gets the ideal of the Roster page from the engine."""
    teams = ["BOS", "NY", "LAL", "DEN", "MIA", "PHX"]
    days = []
    for i in range(14):
        playing = [t for k, t in enumerate(teams) if (i + k) % 3 != 0 and (i * k) % 5 != 1]
        days.append(day(f"2027-03-{8 + i:02d}", "wk19" if i < 7 else "wk20", playing if i != 3 else []))
    data = {"slots": SLOTS, "util": 1, "weeks": ["wk19", "wk20"], "days": days}
    cases = [[size, week] for size in range(0, 11) for week in ("wk19", "wk20")]
    out = subprocess.run(
        ["node", "-e", IDEAL_DRIVER, str(ENGINE_JS)],
        input=json.dumps({"data": data, "cases": cases}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    want = [ideal_games(size, [d["teams"] for d in days if d["week"] == week], SLOTS) for size, week in cases]
    assert json.loads(out.stdout) == want
    assert len(set(want)) > 5  # the cases reach both limits: the team games and the slots of the game days


def test_value_started_gives_the_games_and_the_ideal_of_each_week():
    # 3 C players of BOS: 2 start and 1 sits on each BOS day. "r" rests on the back-to-back.
    days = [
        day("2027-03-08", "wk19", ["BOS", "NY"]),
        day("2027-03-09", "wk19", ["BOS", "NY"], b2b=["BOS", "NY"]),
        day("2027-03-10", "wk19", ["NY"]),
    ]
    core = [player("c1", "BOS", "C", 3.0), player("c2", "BOS", "C", 2.0), player("c3", "BOS", "C", 1.0)]
    core.append(player("r", "NY", "PG", 0.5, rests_b2b=True))
    got = value_started(core, engine_data(days))
    week = got["weeks"]["wk19"]
    assert (week["starts"], week["lost"], week["games"]) == (6, 2, 8)  # the rest night is not a game
    assert week["ideal"] == ideal_games(4, [d["teams"] for d in days], SLOTS) == 12
    assert (got["total"]["games"], got["total"]["ideal"]) == (8, 12)


# argv: core/starts.js. stdin: {fn, args}. Writes the result of Starts[fn](...args).
CALL_DRIVER = """
const Starts = require(process.argv[1]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { fn, args } = JSON.parse(text);
  process.stdout.write(JSON.stringify(Starts[fn](...args)));
});
"""


def call(fn, *args):
    out = subprocess.run(
        ["node", "-e", CALL_DRIVER, str(ENGINE_JS)],
        input=json.dumps({"fn": fn, "args": args}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


# One week of two days. A and B play both days, C plays the first day. The second day is a light night (+10%).
SWAP_DAYS = engine_data(
    [day("2027-03-08", "wk19", ["A", "B", "C"]), day("2027-03-09", "wk19", ["A", "B"], quality=True)], bonus=0.1
)
# x: 5 + 5.5 = 10.5. y: 2 + 2.2 = 4.2. z has a value below 0 and still starts (review nit 3 of #216): -1.
SWAP_CORE = [player("x", "A", "PG", 5.0), player("y", "B", "C", 2.0), player("z", "C", "SF", -1.0)]
SWAP_POOL = [
    player("p1", "A", "SF", 0.5),  # for z: gain 1.05 + 1 = 2.05, schedule 2.05 - 1.5 x 1 = 0.55
    player("p2", "C", "C", 6.0),  # other team: no core player has a value band that holds 6
    player("p3", "B", "PF", 2.1),  # other team, in the band of y: gain 4.41 - 4.2 = 0.21, schedule 0.21 - 0.1 x 2
    player("p4", "A", "PG", -2.0),  # each swap lowers the value started
    player("p6", "C", "PF", 4.0),  # for z: gain 4 + 1 = 5, schedule 5 - 5 x 1 = 0
]
BAND = [0.95, 1.10]


def swaps(**opts):
    rows = call("bestSwaps", SWAP_CORE, SWAP_POOL, SWAP_DAYS, {"band": BAND, "banded": ["p2", "p3"], **opts})
    return [(r["in"], r["out"]) for r in rows], rows


def test_adds_is_the_value_started_with_the_player_minus_without_him():
    """Decision 9 of the playoffs page design (#215). A core player with a value below 0 has Adds below 0."""
    got = call("adds", SWAP_CORE, SWAP_DAYS, None, [player("w", "A", "SG", 1.0)])
    assert got == pytest.approx({"x": 10.5, "y": 4.2, "z": -1.0, "w": 2.1})


def test_best_swaps_keep_a_gain_above_0_and_rank_by_schedule_gain():
    """Decisions 16 and 17: the best swap of each pool player, the highest schedule gain first, gain above 0 only."""
    pairs, rows = swaps()
    # p6 has the largest gain (5.0) but the lowest schedule gain (0.0), so he is last.
    assert pairs == [("p1", "z"), ("p3", "y"), ("p6", "z")]
    assert [r["gain"] for r in rows] == pytest.approx([2.05, 0.21, 5.0])
    assert [r["schedule"] for r in rows] == pytest.approx([0.55, 0.01, 0.0], abs=1e-9)
    assert (rows[0]["starts"], rows[0]["light"]) == (1, 1)  # p1 plays both days, z plays one
    assert all(r["gain"] > 0 for r in rows)
    assert swaps(limit=1)[0] == [("p1", "z")]


def test_best_swaps_never_swap_out_an_untouchable_player():
    """Decision 18: an untouchable player is never a swap-out. p1 and p6 had a gain only in place of z."""
    pairs, _ = swaps(untouchable=["z"])
    assert pairs == [("p3", "y")]


def test_best_swaps_keep_a_banded_player_in_the_value_band_of_the_player_out():
    """Decision 18: the band holds only for the banded players (other teams). Free agents have no band."""
    assert ("p2", "z") not in swaps()[0]
    assert ("p2", "z") in swaps(banded=["p3"])[0]
    assert call("inBand", 2.0, 2.2, BAND) and not call("inBand", 2.0, 2.21, BAND)
    assert call("inBand", -1.0, -1.05, BAND) and not call("inBand", -1.0, -0.89, BAND)


def test_best_core_takes_the_players_with_the_highest_value_started_alone():
    """#214, #218: the Playoffs page and the League page pick the best core with bestCore()."""
    days = [day("2027-03-08", "wk19", ["A", "B"]), day("2027-03-09", "wk19", ["A"])]
    players = [player("b", "B", "PG", 3.0), player("a", "A", "C", 2.0), player("c", "C", "SF", 9.0)]
    # Value started alone: a 4.0 (2 games), b 3.0 (1 game), c 0 (no game).
    assert [p["id"] for p in call("bestCore", players, engine_data(days), 2)] == ["a", "b"]


# The fill tests (#218). FULL: 5 players of team K, one for each position slot, so Util is the only open slot.
FULL = [player(f"k{n}", "K", pos, 5.0 - n) for n, pos in enumerate(SLOTS)]


def test_a_stream_player_fills_only_the_positions_that_fit_on_his_first_start():
    """#218 owner approval: the fill count checks the open position slots, as the Adds planner does. Day 1 has only C
    open and day 2 has only PG open. A stream player takes C on day 1, so he cannot fill PG on day 2."""
    a = [player("a1", "A", "PG", 3), player("a2", "A", "SG", 3), player("a3", "A", "SF", 3)]
    a += [player("a4", "A", "PF", 3), player("a5", "A", "SF", 2)]  # a5 takes Util
    b = [player("b1", "B", "SG", 1), player("b2", "B", "SF", 1), player("b3", "B", "PF", 1)]
    b += [player("b4", "B", "C", 1), player("b5", "B", "C", 0.5)]  # b5 takes Util
    data = engine_data([day("2027-03-08", "wk19", ["A", "X"]), day("2027-03-09", "wk19", ["B", "X"])])
    got = call("streamFill", a + b, data, {"spots": 1, "adds": 0})
    assert (got["open_heavy"], got["heavy"], got["adds"], got["unused"]) == (2, 1, 0, 1)
    # With 1 add, a player of a team that plays on day 2 fills PG.
    got = call("streamFill", a + b, data, {"spots": 1, "adds": 1})
    assert (got["heavy"], got["adds"], got["unused"]) == (2, 1, 0)
    # A stream player starts only where best_lineup() of core/lineup.py (count() of team_plan()) starts him.
    assert len(best_lineup([set(p["pos"]) for p in b] + [{"C"}], SLOTS)) == 5  # C on day 2: no start
    assert len(best_lineup([set(p["pos"]) for p in b] + [{"PG"}], SLOTS)) == 6


def test_the_fill_uses_the_adds_on_heavy_nights_first_and_gives_the_stream_games_the_fill_rate_and_the_unused():
    """Owner decisions of 2026-11-02 on #218. Day 1 is a light night (only L plays), days 2 and 3 are heavy nights
    (only H and only H2 play). Each day, a full core of a team that plays only that day leaves Util open. With 1 add,
    the add goes to a heavy night."""
    days = [
        day("2027-03-08", "wk19", ["K1", "L"], quality=True),
        day("2027-03-09", "wk19", ["K2", "H"]),
        day("2027-03-10", "wk19", ["K3", "H2"]),
    ]
    core = [{**p, "id": p["id"] + t, "team": t} for t in ("K1", "K2", "K3") for p in FULL]
    data = engine_data(days, bonus=0.1)
    got = call("streamFill", core, data, {"spots": 1, "adds": 1})
    # The week starts with a player of H (each team gives 1 start, H is first by name). The add goes to day 3.
    assert (got["heavy"], got["light"], got["adds"]) == (2, 0, 1)
    assert (got["open_heavy"], got["open_light"]) == (2, 1)
    assert got["games"] == pytest.approx(2.0)
    assert got["rate"] == pytest.approx(2 / (2 + 1 * 1.1))
    assert got["unused"] == 1
    assert got["weeks"] == {"wk19": {"heavy": 2, "light": 0, "adds": 1}}
    # With 3 adds (more than the 2 heavy nights with open slots), the light night gets an add too.
    got = call("streamFill", core, data, {"spots": 1, "adds": 3})
    assert (got["heavy"], got["light"], got["unused"]) == (2, 1, 0)
    assert got["games"] == pytest.approx(2 + 1.1) and got["rate"] == pytest.approx(1.0)
    # No stream spot: no fill, and a fill rate of 0.
    got = call("streamFill", core, data, {"spots": 0, "adds": 5})
    assert (got["heavy"], got["light"], got["games"], got["rate"], got["unused"]) == (0, 0, 0, 0, 3)


def test_the_fill_resets_the_adds_each_week_and_fills_no_slot_that_is_not_open():
    days = [
        day("2027-03-08", "wk19", ["K", "H"]),
        day("2027-03-15", "wk20", ["K", "H2"]),
        day("2027-03-16", "wk20", []),
    ]
    data = {**engine_data(days), "weeks": ["wk19", "wk20"]}
    got = call("streamFill", FULL, data, {"spots": 2, "adds": 0})
    # Each week starts with kept players of the best teams, so no add is needed. 2 spots fill only 1 open slot a day.
    assert (got["heavy"], got["open_heavy"], got["adds"]) == (2, 2, 0)
    assert got["weeks"]["wk20"] == {"heavy": 1, "light": 0, "adds": 0}


def test_rank_median_gives_rank_1_to_the_most_and_the_median_of_the_league():
    """Owner decision of 2026-11-02 on #218: the header of the League page."""
    assert call("rankMedian", [5, 3, 3, 1], 3) == {"rank": 2, "of": 4, "median": 3}
    assert call("rankMedian", [5, 3, 3, 1], 5) == {"rank": 1, "of": 4, "median": 3}
    assert call("rankMedian", [1, 2, 9], 1) == {"rank": 3, "of": 3, "median": 2}
    assert call("rankMedian", [1, 4], 1)["median"] == 2.5
