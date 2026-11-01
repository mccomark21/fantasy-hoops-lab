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
from fantasyhoops.core.lineup import ENGINE_JS, ideal_games
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
