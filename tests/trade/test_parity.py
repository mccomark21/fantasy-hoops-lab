"""Node runs trade_builder.js with team_builder.js on fixture rosters. The results equal the Python rules (#152)."""

import json
import random
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from fantasyhoops.core import roster as roster_page
from fantasyhoops.trade import page
from fantasyhoops.trade.builder import custom_trade
from fantasyhoops.trade.suggest import Suggestions, TradePlayer, TradeSettings, suggest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")

SLOTS = ["PG", "SG", "SF", "PF", "C"]
WEEKS = ["wk19", "wk20", "wk21"]
SETTINGS = TradeSettings(frozenset({"star keeper"}), (0.95, 1.10), 8, 3, 20)
TEAMS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
POSITIONS = [("PG",), ("SG",), ("SF",), ("PF",), ("C",), ("PG", "SG"), ("SF", "PF"), ("PF", "C"), ("SG", "SF")]

# Reads {"data", "cases", "order"} on stdin. Each case is {team, give, get, drops} with the player ids.
# Writes {"trades": [TradeBuilder.trade() with the drops as ids], "order": [engine values], "starters": [...]}.
DRIVER = """
globalThis.TeamBuilder = require(process.argv[1]);
const TradeBuilder = require(process.argv[2]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { data, cases, order } = JSON.parse(text);
  const byId = new Map(data.me.map(p => [p.id, p]));
  data.teams.forEach(t => t.roster.forEach(p => byId.set(p.id, p)));
  const pick = ids => ids.map(id => byId.get(id));
  const ids = side => ({ ...side, drops: side.drops.map(p => p.id) });
  const trades = cases.map(c => {
    const team = data.teams.find(t => t.id === c.team);
    const r = TradeBuilder.trade(data.me, team.roster, pick(c.give), pick(c.get), pick(c.drops), data.engine);
    return { mine: ids(r.mine), partner: ids(r.partner), band: r.band };
  });
  const core = pick(order).map(p => ({ ...p, value: TradeBuilder.engineValue(p) }));
  const score = TeamBuilder.scoreCore(core, data.engine);
  process.stdout.write(JSON.stringify({
    trades,
    order: core.map(p => p.value),
    starters: score.days.map(d => Object.values(d.starters).sort()),
  }));
});
"""


def node(data, cases, order=()):
    out = subprocess.run(
        ["node", "-e", DRIVER, str(page.ENGINE), str(page.TRADE_ENGINE)],
        input=json.dumps({"data": data, "cases": cases, "order": list(order)}),
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return json.loads(out.stdout)


def playoff_days(rng):
    """3 to 4 days in each playoff week, with random teams, quality days and back-to-backs."""
    out, start = [], date(2027, 3, 8)
    for w, name in enumerate(WEEKS):
        for d in range(rng.randint(3, 4)):
            plays = frozenset(t for t in TEAMS if rng.random() < 0.6)
            b2b = frozenset(t for t in plays if rng.random() < 0.3)
            out.append(roster_page.Day(start + timedelta(days=7 * w + d), name, rng.random() < 0.3, plays, b2b))
    return out


def roster(rng, prefix, team_id, n, mine):
    out = []
    for i in range(n):
        value = None if rng.random() < 0.08 else round(rng.uniform(-4, 4), 2)
        out.append(
            TradePlayer(
                name="Star Keeper" if mine and i == 0 else f"{prefix} {i}",
                team=rng.choice(TEAMS),
                positions=rng.choice(POSITIONS),
                slot=("IL" if rng.random() < 0.15 else "BN") if mine else "",
                status=rng.choice(["", "", "", "O", "GTD"]),
                value=value,
                pg=round(rng.uniform(-4, 4), 2),
                rank=None if rng.random() < 0.1 else rng.randint(1, 200),
                rests_b2b=rng.random() < 0.3,
                team_id=1 if mine else team_id,
                team_name="" if mine else f"Team {team_id}",
            )
        )
    return out


def fixture(seed):
    rng = random.Random(seed)
    mine = roster(rng, "Mine", 1, 13, True)
    others = [p for t in (2, 3) for p in roster(rng, f"T{t}", t, rng.randint(10, 13), False)]
    return rng, playoff_days(rng), mine, others


def cases(rng, mine, others):
    """Random trades: 1-for-1, 2-for-1, 1-for-2, 3-for-1, 1-for-3 and 2-for-2, with legal drops."""
    out = []
    can_give = [p for p in mine if not SETTINGS.is_untouchable(p)]
    for n_give, n_get in [(1, 1), (1, 1), (2, 1), (1, 2), (3, 1), (1, 3), (2, 2)] * 2:
        team_id = rng.choice([2, 3])
        team = [p for p in others if p.team_id == team_id]
        give = rng.sample(can_give, n_give)
        get = rng.sample(team, n_get)
        left = [p for p in can_give if p not in give]
        drops = rng.sample(left, max(0, n_get - n_give))
        out.append((team_id, give, get, drops))
    return out


@pytest.mark.parametrize("seed", range(6))
def test_the_js_trade_equals_the_python_trade_on_random_rosters(seed):
    rng, playoff, mine, others = fixture(seed)
    data = page.builder_data(Suggestions((), [], [], 0, 0, 0), mine, others, playoff, SLOTS, WEEKS, SETTINGS)
    ids = {p: d["id"] for p, d in zip(mine, data["me"])}
    for t in data["teams"]:
        team = [p for p in others if p.team_id == t["id"]]
        ids.update({p: d["id"] for p, d in zip(team, t["roster"])})
    trades = cases(rng, mine, others)
    js = node(
        data,
        [
            {"team": t, "give": [ids[p] for p in g], "get": [ids[p] for p in r], "drops": [ids[p] for p in d]}
            for t, g, r, d in trades
        ],
    )["trades"]
    for (team_id, give, get, drops), got in zip(trades, js):
        team = [p for p in others if p.team_id == team_id]
        want = custom_trade(mine, team, give, get, drops, playoff, SLOTS, WEEKS, SETTINGS)
        for side, w in (("mine", want.mine), ("partner", want.partner)):
            g = got[side]
            assert tuple(g["before"]) == w.before and tuple(g["after"]) == w.after, (seed, side, give, get)
            assert g["dv"] == pytest.approx(w.dv)
            assert g["drops"] == [ids[p] for p in w.drops]
            assert g["open"] == w.open
        assert got["band"] == want.band


def test_a_suggestion_row_gives_the_same_starts_and_value_changes_in_the_builder():
    for seed in range(6):
        rng, playoff, mine, others = fixture(seed)
        result = suggest(mine, others, playoff, SLOTS, WEEKS, SETTINGS)
        if result.rows:
            break
    assert result.rows, "no fixture seed gave a suggestion"
    data = page.builder_data(result, mine, others, playoff, SLOTS, WEEKS, SETTINGS)
    js = node(data, [{**s, "drops": []} for s in data["sugg"]])["trades"]
    for s, got in zip(result.rows, js):
        assert tuple(got["mine"]["before"]) == s.before and tuple(got["mine"]["after"]) == s.after
        assert tuple(got["partner"]["before"]) == s.partner_before
        assert tuple(got["partner"]["after"]) == s.partner_after
        assert got["mine"]["dv"] == pytest.approx(s.dv) and got["partner"]["dv"] == pytest.approx(s.partner_dv)


def test_the_engine_gets_value_minus_rank_so_its_order_is_the_rank_order_of_the_home_page():
    # Three PGs and one Util on each day: the two best ranks start, and the player with no rank sits.
    day = roster_page.Day(date(2027, 3, 8), "wk19", False, frozenset({"AAA"}), frozenset())
    players = [
        TradePlayer("No Rank", "AAA", ("PG",), value=9.0, rank=None),
        TradePlayer("Rank 30", "AAA", ("PG",), value=1.0, rank=30),
        TradePlayer("Rank 4", "AAA", ("PG",), value=-1.0, rank=4),
    ]
    data = page.builder_data(Suggestions((), [], [], 0, 0, 0), players, [], [day], SLOTS, ["wk19"], SETTINGS)
    out = node(data, [], [p["id"] for p in data["me"]])
    assert out["order"] == [-1e9, -30, -4]
    fit = roster_page.lineup_fit([p.roster_player() for p in players], [day], SLOTS)
    started = sorted(p.name for p, marks in zip(fit.players, fit.marks) if marks[0] == roster_page.START)
    assert out["starters"] == [started] == [["Rank 30", "Rank 4"]]


def test_the_page_inlines_both_engines():
    text = page.builder_script({"me": [], "teams": [], "sugg": [], "engine": {}})
    assert Path(page.ENGINE).read_text(encoding="utf-8") in text
    assert Path(page.TRADE_ENGINE).read_text(encoding="utf-8") in text
