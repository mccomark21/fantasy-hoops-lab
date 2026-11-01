// The shared lineup-and-starts engine of the browser (#213): the playoff starts of a core, for the draft board,
// the trade builder and the playoffs page. Before #213, this code was in draft/team_builder.js.
//
//   1. Each playoff day, the core players whose teams play go into the position slots (data.slots) and Util.
//      The engine adds them in value order, highest first. It accepts a player only when the slots and Util can
//      still hold all accepted players (bipartite matching). This is best_lineup() in core/lineup.py.
//   2. A player with rests_b2b = 1 does not play on the second night of a back-to-back (day.b2b).
//   3. Started = the accepted players. Lost = the players who play but get no slot.
//      Holes = the empty starting slots on quality days. The engine counts no streamers.
//
// The interface (the global Starts, or module.exports in Node):
//   scoreCore(core, data)             the started games, lost games and holes of each week and each day.
//   fit(core, player, data)           the change of scoreCore() when player joins the core.
//   slotRoster(players, data)         the season slots and the bench of the team table.
//   valueStarted(core, data, resters) the value started, the starts, the starts lost and the open slots (playoffs).
// A player is {id, name, team, pos, value, rests_b2b}. pos: the position slots, for example ["PG", "SG"].
// value must be a number, because a null value gives NaN. The playoffs page gives val, else proj_val, else 0 (#214).
// data: {slots, util, weeks, days}. A day is {date, week, quality, teams, b2b}. valueStarted() also reads
// data.quality_bonus, the bonus of [quality_games] in config.toml.
//
// core/lineup.py is the one source of the lineup-fit rules (#133). The matching and the rest rule stay here too,
// because the pages score the core that the user picks in the browser. tests/draft/test_team_builder.py and
// tests/core/test_starts.py show that they give the same results as core/lineup.py and core/roster.py.
// The file has no DOM code. A page inlines it as a plain script before the script of its tool. Node loads it with
// require(). core/lineup.py gives its path (ENGINE_JS).

const Starts = (() => {
  // Per-day team sets for each data object, so that a call does not make them again.
  const _daySets = new WeakMap();

  function _sets(data) {
    let sets = _daySets.get(data);
    if (!sets) {
      sets = data.days.map(d => ({ teams: new Set(d.teams), b2b: new Set(d.b2b || []) }));
      _daySets.set(data, sets);
    }
    return sets;
  }

  function _utilNames(data) {
    const n = data.util === undefined ? 1 : data.util;
    return Array.from({ length: n }, (_, i) => (i === 0 ? "Util" : "Util" + (i + 1)));
  }

  // Maximum matching of players to position slots (_match in core/lineup.py).
  // Returns holder: slot -> index in lineup. A player with no slot goes to Util.
  function _match(lineup, slots) {
    const holder = {};
    function place(i, tried) {
      for (const slot of slots) {
        if (lineup[i].pos.includes(slot) && !tried.has(slot)) {
          tried.add(slot);
          if (!(slot in holder) || place(holder[slot], tried)) {
            holder[slot] = i;
            return true;
          }
        }
      }
      return false;
    }
    for (let i = 0; i < lineup.length; i++) place(i, new Set());
    return holder;
  }

  // One playoff day. ordered: the core in value order, highest first.
  // lineup: the started players (objects), for valueStarted(). scoreCore() does not return it.
  function _day(ordered, day, sets, data) {
    const slots = data.slots, utils = _utilNames(data);
    const lineup = [], sat = [], rested = [];
    for (const p of ordered) {
      if (!sets.teams.has(p.team)) continue;
      if (p.rests_b2b && sets.b2b.has(p.team)) {
        rested.push(p.name);
        continue;
      }
      const trial = lineup.concat([p]);
      const placed = Object.keys(_match(trial, slots)).length;
      // The players with no position slot go to Util
      if (trial.length - placed <= utils.length) lineup.push(p);
      else sat.push(p.name);
    }

    const holder = _match(lineup, slots), starters = {}, empty = [], inSlot = new Set();
    for (const slot of slots) {
      if (slot in holder) {
        starters[slot] = lineup[holder[slot]].name;
        inSlot.add(holder[slot]);
      } else {
        empty.push(slot);
      }
    }
    const util = lineup.filter((_, i) => !inSlot.has(i));
    utils.forEach((name, i) => {
      if (i < util.length) starters[name] = util[i].name;
      else empty.push(name);
    });
    return {
      date: day.date, week: day.week, quality: !!day.quality, starters, sat, rested, empty, lineup,
      started: lineup.length, holes: day.quality ? empty.length : 0,
    };
  }

  function _ordered(core) {
    // A stable sort: two players with the same value keep the order of core
    return core.slice().sort((a, b) => b.value - a.value);
  }

  function _totals(dayResults, data) {
    const weeks = {}, total = { started: 0, lost: 0, holes: 0 };
    for (const w of data.weeks) weeks[w] = { started: 0, lost: 0, lost_by: {}, holes: 0 };
    for (const d of dayResults) {
      const w = weeks[d.week] || (weeks[d.week] = { started: 0, lost: 0, lost_by: {}, holes: 0 });
      w.started += d.started;
      w.lost += d.sat.length;
      w.holes += d.holes;
      for (const name of d.sat) w.lost_by[name] = (w.lost_by[name] || 0) + 1;
    }
    for (const w of Object.values(weeks)) {
      total.started += w.started;
      total.lost += w.lost;
      total.holes += w.holes;
    }
    const last = weeks[data.weeks[data.weeks.length - 1]];
    const finals = { started: last.started, lost: last.lost, holes: last.holes };
    return { weeks, total, finals };
  }

  // The engine result in #8: weeks, total, finals and days. core is a list of players from data.players.
  function scoreCore(core, data) {
    const ordered = _ordered(core), sets = _sets(data);
    const days = data.days.map((day, i) => _day(ordered, day, sets[i], data));
    const result = _totals(days, data);
    result.days = days.map(d => ({
      date: d.date, quality: d.quality, starters: d.starters, sat: d.sat, rested: d.rested, empty: d.empty,
    }));
    return result;
  }

  // The last base score, so that fit() for each row of the board scores the core one time only.
  let _base = null;

  function _baseDays(core, data) {
    const key = core.map(p => p.id + ":" + p.value + ":" + p.team + ":" + p.rests_b2b + ":" + p.pos.join("/")).join("|");
    if (!_base || _base.data !== data || _base.key !== key) {
      const ordered = _ordered(core), sets = _sets(data);
      _base = { data, key, ordered, days: data.days.map((day, i) => _day(ordered, day, sets[i], data)) };
    }
    return _base;
  }

  // Δ against scoreCore(core, data) when player joins the core:
  // {started, finals, holes_removed, games, quality, quality_started}.
  // games and quality: the games and quality-day games that the player can play (no rest nights).
  // quality_started: Δ started games on quality days. started < games means that his games push out other players
  // or that he sits, so the ratio started / games shows a logjam.
  // Only the days on which the team of the player plays can change, so fit() scores those days again.
  function fit(core, player, data) {
    const base = _baseDays(core, data), sets = _sets(data);
    const finalsWeek = data.weeks[data.weeks.length - 1];
    const ordered = _ordered(base.ordered.concat([player]));
    let started = 0, finals = 0, holes = 0, games = 0, quality = 0, qualityStarted = 0;
    data.days.forEach((day, i) => {
      if (!sets[i].teams.has(player.team)) return;
      if (!(player.rests_b2b && sets[i].b2b.has(player.team))) {
        games += 1;
        if (day.quality) quality += 1;
      }
      const before = base.days[i], after = _day(ordered, day, sets[i], data);
      const delta = after.started - before.started;
      started += delta;
      if (day.week === finalsWeek) finals += delta;
      if (day.quality) qualityStarted += delta;
      holes += before.holes - after.holes;
    });
    return { started, finals, holes_removed: holes, games, quality, quality_started: qualityStarted };
  }

  // Season slots for the team table: {slots: {slot: player}, bench: [players]}. players is in priority order
  // (the page sorts by value, highest first). The same matching as a playoff day fills the position slots and Util.
  // A player who does not fit goes to the bench. Legal lineups are a matroid, so this order gives the starting
  // slots the highest-value legal lineup: a bench player can start only in place of a higher-value player.
  function slotRoster(players, data) {
    const slots = data.slots, utils = _utilNames(data), lineup = [], bench = [];
    for (const p of players) {
      const trial = lineup.concat([p]);
      if (trial.length - Object.keys(_match(trial, slots)).length <= utils.length) lineup.push(p);
      else bench.push(p);
    }
    const holder = _match(lineup, slots), out = {}, inSlot = new Set();
    for (const slot of slots) {
      if (slot in holder) {
        out[slot] = lineup[holder[slot]];
        inSlot.add(holder[slot]);
      }
    }
    lineup.filter((_, i) => !inSlot.has(i)).forEach((p, i) => { out[utils[i]] = p; });
    return { slots: out, bench };
  }

  // The value started of a core (playoffs page, decisions 2, 4 to 8, 13 and 15 of the playoffs page design).
  // core: players with value = the per-game Val. The value is the value of one started game and the lineup order.
  // data.quality_bonus: the light-night bonus. A started game on a quality day counts value x (1 + bonus).
  // resters: optional, a Set or a list of player ids. When given, a player rests on the second night of a
  // back-to-back only if his id is in it, and rests_b2b of the player has no effect.
  // The result:
  //   days: [{date, week, quality, starts, lost, open, value}] in the order of data.days.
  //     starts: the started core games. lost: the core games that sit. open: the empty starting slots that a
  //     stream player can fill, 0 on a day with no NBA games. value: the value started of the day.
  //   weeks: {week: {value, starts, light_starts, lost, open_heavy, open_light}}. light: on quality days.
  //   total: the same fields as a week, for all weeks.
  //   marks: {player id: one mark for each day}: "s" starts, "b" game but sits, "r" rests, "n" no game.
  //     The marks of lineup_fit() in core/roster.py.
  function valueStarted(core, data, resters) {
    let players = core;
    if (resters !== undefined && resters !== null) {
      const set = resters instanceof Set ? resters : new Set(resters);
      players = core.map(p => ({ ...p, rests_b2b: set.has(p.id) }));
    }
    const bonus = data.quality_bonus || 0, ordered = _ordered(players), sets = _sets(data);
    const zero = () => ({ value: 0, starts: 0, light_starts: 0, lost: 0, open_heavy: 0, open_light: 0 });
    const weeks = {}, total = zero(), marks = {}, days = [];
    for (const w of data.weeks) weeks[w] = zero();
    for (const p of players) marks[p.id] = [];
    data.days.forEach((day, i) => {
      const d = _day(ordered, day, sets[i], data), on = new Set(d.lineup);
      const open = sets[i].teams.size ? d.empty.length : 0;
      const value = d.lineup.reduce((s, p) => s + p.value, 0) * (day.quality ? 1 + bonus : 1);
      days.push({ date: day.date, week: day.week, quality: !!day.quality, starts: d.started, lost: d.sat.length, open, value });
      const w = weeks[day.week] || (weeks[day.week] = zero());
      for (const t of [w, total]) {
        t.value += value;
        t.starts += d.started;
        t.lost += d.sat.length;
        if (day.quality) {
          t.light_starts += d.started;
          t.open_light += open;
        } else {
          t.open_heavy += open;
        }
      }
      for (const p of players) {
        let mark = "n";
        if (sets[i].teams.has(p.team)) mark = p.rests_b2b && sets[i].b2b.has(p.team) ? "r" : on.has(p) ? "s" : "b";
        marks[p.id].push(mark);
      }
    });
    return { days, weeks, total, marks };
  }

  return { scoreCore, fit, slotRoster, valueStarted };
})();

if (typeof module !== "undefined") module.exports = Starts;
