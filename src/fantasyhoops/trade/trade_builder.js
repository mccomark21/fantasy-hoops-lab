// Trade builder engine (#152): the playoff starts and the value change of a custom trade, for both teams.
//
//   1. The kept set of a team: the untouchable and IL players, then the highest values, data.kept in all.
//   2. The players that a team gives (and drops) leave its kept set. The players that it gets take the freed spots,
//      the highest value first. The kept set is not ranked again (Decision comment of 2026-10-28 on #150).
//   3. When you get more players than you give, you pick your drops. When you give more, the spot stays empty.
//   4. When the partner gets more players than he gives, he drops his lowest value players that are not on IL.
//   5. The starts come from scoreCore() of draft/team_builder.js. The engine gets value = -rank, so its value sort
//      gives the lineup order of the Roster page (core/roster.py rank_order()). A player with no rank goes last.
//
// trade/builder.py has the same rules in Python. tests/trade/test_parity.py shows that both give the same results.
// The file has no DOM code. trade/page.py inlines it after team_builder.js. Node loads it with require(), after it
// sets globalThis.TeamBuilder. A player is {id, name, team, pos, rank, rests_b2b, val, il, untouchable}.
// val is the value of the trade tool (the blended value, else the preseason value), or null.

const TradeBuilder = (() => {
  const NO_RANK = -1e9; // the engine value of a player with no rank: after all players with a rank

  const num = p => (p.val == null ? 0 : p.val);

  // The players by value, highest first. A player with no value goes last. Equal values keep their order.
  function byValue(players) {
    return players.slice().sort((a, b) => (a.val == null) - (b.val == null) || num(b) - num(a));
  }

  function keptSet(players, kept) {
    const always = players.filter(p => p.untouchable || p.il);
    const rest = byValue(players.filter(p => !always.includes(p)));
    const chosen = new Set(always.concat(rest.slice(0, Math.max(0, kept - always.length))));
    return players.filter(p => chosen.has(p));
  }

  function keptAfter(kept, out, incoming) {
    const gone = new Set(out), queue = byValue(incoming), after = [];
    for (const p of kept) {
      if (!gone.has(p)) after.push(p);
      else if (queue.length) after.push(queue.shift());
    }
    return after;
  }

  function partnerDrops(team, out, n) {
    if (n <= 0) return [];
    const gone = new Set(out);
    const left = team.filter(p => !gone.has(p) && !p.il);
    return left.sort((a, b) => (a.val != null) - (b.val != null) || num(a) - num(b)).slice(0, n);
  }

  function engineValue(p) {
    return p.rank == null ? NO_RANK : -p.rank;
  }

  // The team starts of each week of data.weeks, with scoreCore() of team_builder.js.
  function weekStarts(players, data) {
    const core = players.map(p => ({ ...p, value: engineValue(p) }));
    const result = TeamBuilder.scoreCore(core, data);
    return data.weeks.map(w => result.weeks[w].started);
  }

  function inBand(give, get, band) {
    const low = give - (1 - band[0]) * Math.abs(give), high = give + (band[1] - 1) * Math.abs(give);
    return low - 1e-9 <= get && get <= high + 1e-9;
  }

  const sum = list => list.reduce((s, p) => s + num(p), 0);

  // A custom trade. mine, team: the players of both teams. give, get, drops: lists of players.
  // data: {slots, util, weeks, days, kept, band}. The result has mine and partner, each {before, after, dv, drops,
  // open}, and band: "in", "below" or "above" for equal counts, else "".
  function trade(mine, team, give, get, drops, data) {
    const kept = keptSet(mine, data.kept);
    const me = {
      before: weekStarts(kept, data),
      after: weekStarts(keptAfter(kept, give.concat(drops), get), data),
      dv: sum(get) - sum(give) - sum(drops),
      drops,
      open: Math.max(0, give.length - get.length),
    };
    const theirs = partnerDrops(team, get, give.length - get.length);
    const pkept = keptSet(team, data.kept);
    const partner = {
      before: weekStarts(pkept, data),
      after: weekStarts(keptAfter(pkept, get.concat(theirs), give), data),
      dv: sum(give) - sum(get) - sum(theirs),
      drops: theirs,
      open: Math.max(0, get.length - give.length),
    };
    let band = "";
    if (give.length === get.length) {
      const g = sum(give), r = sum(get);
      band = inBand(g, r, data.band) ? "in" : r < g ? "below" : "above";
    }
    return { mine: me, partner, band };
  }

  return { keptSet, keptAfter, partnerDrops, engineValue, weekStarts, trade };
})();

if (typeof module !== "undefined") module.exports = TradeBuilder;
