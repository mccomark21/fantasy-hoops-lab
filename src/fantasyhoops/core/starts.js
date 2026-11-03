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
//   idealGames(size, data, week)      the ideal started games of a core of size players in a week (ideal_games()).
//   adds(core, data, resters, others) the Adds of each player: the change of value started with him (#215).
//   bestSwaps(core, pool, data, opts) the best swap of each pool player into the core, best schedule gain first (#215).
//   inBand(give, get, band)           true if the value get is in the value band of the value give ([trade] value_band).
//   bestCore(players, data, n, resters) the n players with the highest value started alone (#214, #218).
//   streamFill(core, data, opts)      the open slots that the stream spots fill, the stream games, the fill rate and
//                                     the unused slots (League page, #218).
//   rankMedian(values, value)         the rank of value among values (1 is the most) and the median (#218).
//   weekTotals(core, data, opts)      the Total, the volume, the value per start and the reasons of each week (#229).
//   weekRanks(teams, weeks, weak)     the weekly ranks, the vulnerable flag and the weakest week of each team (#229).
//   otherTotals(players, data, opts)  weekTotals() of the best core of each other team (Playoffs page, #230).
//   coreFloor(core, others, data, opts) the weekly Totals, the ranks, the weakest week and the floor of a core (#230).
//   floorSwaps(core, pool, others, data, opts) the best swaps by the gain to the worst week (#230).
//   historyRow(players, data, opts)   the weekly Totals and ranks of your best core, for the history file (#230).
//   trendPoints(rows, weeks)          the floor and the Total of each row of the history file (#230).
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

  // The ideal started games of a core of size players in one week: ideal_games() of core/lineup.py (#214).
  // Each player gets the most games of any NBA team that week. Each game day has at most the starting slots
  // (the position slots + Util).
  function idealGames(size, data, week) {
    const counts = {};
    let gameDays = 0;
    for (const d of data.days) {
      if (d.week !== week) continue;
      if (d.teams.length) gameDays += 1;
      for (const t of d.teams) counts[t] = (counts[t] || 0) + 1;
    }
    const most = Math.max(0, ...Object.values(counts));
    return Math.min(size * most, (data.slots.length + _utilNames(data).length) * gameDays);
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
  //   weeks: {week: {value, starts, light_starts, lost, open_heavy, open_light, games, ideal}}. light: on quality
  //     days. games: the core games with no rest nights, starts + lost. ideal: idealGames() of the core size (#214).
  //   total: the same fields as a week, for all weeks. Its ideal is the sum of the ideals of the weeks.
  //   marks: {player id: one mark for each day}: "s" starts, "b" game but sits, "r" rests, "n" no game.
  //     The marks of lineup_fit() in core/roster.py.
  function valueStarted(core, data, resters) {
    let players = core;
    if (resters !== undefined && resters !== null) {
      const set = resters instanceof Set ? resters : new Set(resters);
      players = core.map(p => ({ ...p, rests_b2b: set.has(p.id) }));
    }
    const bonus = data.quality_bonus || 0, ordered = _ordered(players), sets = _sets(data);
    const zero = () => ({ value: 0, starts: 0, light_starts: 0, lost: 0, open_heavy: 0, open_light: 0, games: 0, ideal: 0 });
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
        t.games += d.started + d.sat.length;
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
    for (const [w, t] of Object.entries(weeks)) {
      t.ideal = idealGames(core.length, data, w);
      total.ideal += t.ideal;
    }
    return { days, weeks, total, marks };
  }

  // The value band of [trade] value_band in config.toml: give - (1 - band[0]) x |give| to give + (band[1] - 1) x |give|.
  // in_band() of trade/suggest.py. A value on an edge is in the band, also with a rounding error of the float math.
  function inBand(give, get, band) {
    const low = give - (1 - band[0]) * Math.abs(give), high = give + (band[1] - 1) * Math.abs(give);
    return low - 1e-9 <= get && get <= high + 1e-9;
  }

  const _ids = x => (x instanceof Set ? x : new Set(x || []));

  // The Adds of each player (decision 9 of the playoffs page design, #215). resters: as in valueStarted().
  // A core player: the value started of the core minus the value started of the core without him.
  // A player of others (not in the core): the value started of the core with him minus the value started of the core.
  // A core player with a value below 0 still starts when his team plays (review nit 3 of #216). The core without him
  // starts higher, so his Adds is below 0.
  // The result: {player id: Adds}.
  function adds(core, data, resters, others = []) {
    const value = list => valueStarted(list, data, resters).total.value;
    const base = value(core), out = {};
    for (const p of core) out[p.id] = base - value(core.filter(q => q.id !== p.id));
    for (const p of others) out[p.id] = value(core.concat([p])) - base;
    return out;
  }

  // The best swaps of the playoffs page (decisions 16 to 18 of the playoffs page design, #215).
  // For each pool player who is not in the core, try him in place of each core player. Keep his best swap.
  //   gain: the change of value started. The result keeps only a swap with a gain above 0.
  //   schedule: the schedule gain, gain - (value in - value out) x the starts of the player out in the core.
  //     It is the part of the gain that does not come from the value of the player alone. The rank uses it.
  //   starts, light: the change of the starts and of the light-night starts.
  // opts: {resters, band, banded, untouchable, limit}.
  //   resters: as in valueStarted(). It must hold the pool players who rest too.
  //   band and banded: a player of banded (ids) is listed only if his value is in the value band (inBand()) of the
  //     player out. The playoffs page gives the players of other teams. Free agents have no band.
  //   untouchable: the ids of the core players who are never a swap-out.
  //   limit: the number of rows, 10 if not given.
  // The result: [{in, out, gain, schedule, starts, light}], the highest schedule gain first. in and out: player ids.
  function bestSwaps(core, pool, data, opts = {}) {
    const resters = opts.resters, limit = opts.limit === undefined ? 10 : opts.limit;
    const banded = _ids(opts.banded), untouchable = _ids(opts.untouchable), inCore = new Set(core.map(p => p.id));
    const now = valueStarted(core, data, resters), base = now.total, startsOf = {};
    for (const p of core) startsOf[p.id] = now.marks[p.id].filter(k => k === "s").length;
    const rows = [];
    for (const p of pool) {
      if (inCore.has(p.id)) continue;
      let best = null;
      for (const o of core) {
        if (untouchable.has(o.id)) continue;
        if (opts.band && banded.has(p.id) && !inBand(o.value, p.value, opts.band)) continue;
        const t = valueStarted(core.map(c => (c.id === o.id ? p : c)), data, resters).total;
        const gain = t.value - base.value;
        if (gain <= 1e-9) continue;
        const schedule = gain - (p.value - o.value) * startsOf[o.id];
        if (!best || schedule > best.schedule) {
          best = { in: p.id, out: o.id, gain, schedule, starts: t.starts - base.starts, light: t.light_starts - base.light_starts };
        }
      }
      if (best) rows.push(best);
    }
    rows.sort((a, b) => b.schedule - a.schedule);
    return rows.slice(0, limit);
  }

  // The best core of n players (decision 11 of the playoffs page design, the League page #218): the n players with
  // the highest value started alone, highest first. resters: as in valueStarted(). A stable sort: two players with
  // the same value started keep the order of players.
  function bestCore(players, data, n, resters) {
    const solo = new Map(players.map(p => [p, valueStarted([p], data, resters).total.value]));
    return players.slice().sort((a, b) => solo.get(b) - solo.get(a)).slice(0, n);
  }

  // True if the slots and Util can hold all players of trial (the acceptance rule of _day()).
  function _fits(trial, data) {
    return trial.length - Object.keys(_match(trial, data.slots)).length <= _utilNames(data).length;
  }

  // The stream players who start on one day, with the position-slot logic of count() in adds/team_plan.py: the core
  // lineup of the day keeps its slots. Then each stream player in spot order starts if the slots and Util can still
  // hold all accepted players (best_lineup() in core/lineup.py).
  // members: one {team, pos} or null for each stream spot. pos null: a new player who has not started yet. On his
  // first start he takes the positions that fit that day (slots_of() and _positions() in adds/team_plan.py): all
  // positions if each fits, as an open Util slot gives.
  // The result: {started: the spot indexes that start, fixed: {spot index: positions} for the first starts}.
  function _streamDay(lineup, members, teams, data) {
    let on = lineup;
    const started = [], fixed = {};
    members.forEach((m, k) => {
      if (!m || !teams.has(m.team)) return;
      let pos = m.pos;
      if (!pos) {
        pos = data.slots.filter(p => _fits(on.concat([{ pos: [p] }]), data));
        if (!pos.length) return;
        fixed[k] = pos;
      } else if (!_fits(on.concat([{ pos }]), data)) {
        return;
      }
      on = on.concat([{ pos }]);
      started.push(k);
    });
    return { started, fixed };
  }

  // The starts of the members on the days from to the end of week (a list of {lineup, teams}). No add.
  function _rest(week, members, from, data) {
    let held = members.slice(), n = 0;
    for (let i = from; i < week.length; i++) {
      const r = _streamDay(week[i].lineup, held, week[i].teams, data);
      held = held.map((m, k) => (k in r.fixed ? { team: m.team, pos: r.fixed[k] } : m));
      n += r.started.length;
    }
    return n;
  }

  // The fill of one week: the open slots that the stream spots fill with the add limit of the week.
  // At the start of the week, each spot holds a player of the team that gives the most starts (a player kept from
  // the week before, so no add). Each day, the held players start first. For each open slot that is left, an add
  // puts a player of a team that plays that day in a spot whose player does not start that day. The add with the
  // most starts that day and on the days that are left wins. Heavy nights first (owner decision 2 of 2026-11-02):
  // on a light night, an add is used only if the adds left are more than the heavy nights with open slots that are
  // left in the week.
  function _fillWeek(week, spots, adds, data) {
    const out = { heavy: 0, light: 0, adds: 0 };
    if (!spots) return out;
    const teams = [...new Set(week.flatMap(d => [...d.teams]))].sort();
    let held = [];
    for (let k = 0; k < spots; k++) {
      let best = null, most = -1;
      for (const t of teams) {
        const n = _rest(week, held.concat([{ team: t, pos: null }]), 0, data);
        if (n > most) [best, most] = [t, n];
      }
      held.push(best === null ? null : { team: best, pos: null });
    }
    week.forEach((d, i) => {
      const heavyLeft = week.filter((e, j) => j > i && !e.quality && e.open > 0).length;
      const limit = d.quality ? adds - heavyLeft : adds;
      let r = _streamDay(d.lineup, held, d.teams, data);
      while (r.started.length < d.open && out.adds < limit) {
        const idle = held.map((_, k) => k).filter(k => !r.started.includes(k));
        let pick = null, most = -1;
        for (const k of idle) {
          for (const t of [...d.teams].sort()) {
            const trial = held.map((m, j) => (j === k ? { team: t, pos: null } : m));
            const today = _streamDay(d.lineup, trial, d.teams, data);
            if (!today.started.includes(k) || today.started.length <= r.started.length) continue;
            const fixedTrial = trial.map((m, j) => (j in today.fixed ? { team: m.team, pos: today.fixed[j] } : m));
            const n = today.started.length + _rest(week, fixedTrial, i + 1, data);
            if (n > most) [pick, most] = [trial, n];
          }
        }
        if (!pick) break;
        held = pick;
        out.adds += 1;
        r = _streamDay(d.lineup, held, d.teams, data);
      }
      held = held.map((m, k) => (k in r.fixed ? { team: m.team, pos: r.fixed[k] } : m));
      if (d.quality) out.light += r.started.length;
      else out.heavy += r.started.length;
    });
    return out;
  }

  // The stream fill of a core (League page, owner decisions of 2026-11-02 on #218): the open slots of valueStarted()
  // that the stream spots can fill. opts: {spots, adds, resters}. spots: the stream spots. adds: the add limit of
  // each week ([league] adds). resters: as in valueStarted(). See _fillWeek() for the rules.
  // The result: {heavy, light, open_heavy, open_light, adds, games, rate, unused, weeks: {week: {heavy, light, adds}}}.
  //   heavy, light: the filled open slots on heavy and on light nights. open_heavy, open_light: the open slots.
  //   games: the stream games, heavy + light x (1 + data.quality_bonus).
  //   rate: the fill rate, games / (open_heavy + open_light x (1 + bonus)). 0 with no open slot.
  //   unused: the open slots that the streams do not fill, (open_heavy - heavy) + (open_light - light).
  function streamFill(core, data, opts = {}) {
    const vs = valueStarted(core, data, opts.resters), bonus = data.quality_bonus || 0;
    // The rest rule of valueStarted(), so that the lineup of each day is the lineup of valueStarted()
    const set = opts.resters === undefined || opts.resters === null ? null : _ids(opts.resters);
    const ordered = _ordered(set ? core.map(p => ({ ...p, rests_b2b: set.has(p.id) })) : core);
    const sets = _sets(data), byWeek = {};
    data.days.forEach((day, i) => {
      const d = _day(ordered, day, sets[i], data);
      (byWeek[day.week] = byWeek[day.week] || []).push({
        lineup: d.lineup, teams: sets[i].teams, quality: !!day.quality, open: vs.days[i].open,
      });
    });
    const out = { heavy: 0, light: 0, adds: 0, weeks: {} };
    for (const [w, week] of Object.entries(byWeek)) {
      const f = _fillWeek(week, Math.max(0, opts.spots || 0), opts.adds || 0, data);
      out.weeks[w] = f;
      out.heavy += f.heavy;
      out.light += f.light;
      out.adds += f.adds;
    }
    out.open_heavy = vs.total.open_heavy;
    out.open_light = vs.total.open_light;
    out.games = out.heavy + out.light * (1 + bonus);
    const room = out.open_heavy + out.open_light * (1 + bonus);
    out.rate = room > 0 ? out.games / room : 0;
    out.unused = out.open_heavy - out.heavy + (out.open_light - out.light);
    return out;
  }

  // The rank of value among values and the median of values (the header of the League page, owner decision of
  // 2026-11-02 on #218). Rank 1 is the most. Equal values share the higher rank: rank = 1 + the values above value.
  // The median of an even count is the mean of the two middle values. No values: rank 1, median 0.
  function rankMedian(values, value) {
    const s = values.slice().sort((a, b) => a - b), n = s.length;
    const median = n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0;
    return { rank: 1 + values.filter(x => x > value).length, of: n, median };
  }

  // The numbers of each playoff week of a core (League page, #229). opts: {spots, adds, resters} as in streamFill(),
  // v: the value of one stream game, few: the most starts of a core player with "few starts".
  // The result: {weeks: {week: {...}}, total, volume, vps, started, fill}. For each week:
  //   value: the value started (valueStarted()). stream: the stream games of the week x v. total: value + stream.
  //   volume: the games started, core starts + filled heavy + filled light. vps: total / volume (value per start).
  //   starts, lost: the core starts and the starts lost. lost_by: {player name: starts lost} (scoreCore()).
  //   open: the open slots. filled: the open slots that the streams fill. unused: open - filled. adds: the adds used.
  //   few: the core players with opts.few or fewer starts, fewest first: {name, starts, games, rested}. games: the
  //     days with a game and no rest ("s" or "b" marks). rested: the rest nights ("r" marks).
  //   main: the main cause of a weak week, "unused" or "lost": the cause with more games. With equal counts,
  //     "unused". null if both are 0.
  // total, volume and vps: the same numbers for all weeks. total is the Total of the League page.
  // started, fill: the valueStarted() and streamFill() results of the core, so that a caller does not compute them again.
  function weekTotals(core, data, opts = {}) {
    const set = opts.resters === undefined || opts.resters === null ? null : _ids(opts.resters);
    const players = set ? core.map(p => ({ ...p, rests_b2b: set.has(p.id) })) : core;
    const vs = valueStarted(core, data, opts.resters);
    const fill = streamFill(core, data, { spots: opts.spots, adds: opts.adds, resters: opts.resters });
    const sc = scoreCore(players, data), bonus = data.quality_bonus || 0, v = opts.v || 0, few = opts.few || 0;
    const weeks = {};
    let total = 0, volume = 0;
    for (const w of data.weeks) {
      const a = vs.weeks[w], f = fill.weeks[w] || { heavy: 0, light: 0, adds: 0 };
      const stream = (f.heavy + f.light * (1 + bonus)) * v, filled = f.heavy + f.light;
      const open = a.open_heavy + a.open_light, unused = open - filled, vol = a.starts + filled;
      const lowStarts = core.map(p => {
        const m = vs.marks[p.id].filter((_, i) => data.days[i].week === w);
        const count = k => m.filter(x => x === k).length;
        return { name: p.name, starts: count("s"), games: count("s") + count("b"), rested: count("r") };
      }).filter(p => p.starts <= few).sort((x, y) => x.starts - y.starts);
      const main = unused >= a.lost ? (unused ? "unused" : null) : "lost";
      weeks[w] = {
        value: a.value, stream, total: a.value + stream, volume: vol, vps: vol ? (a.value + stream) / vol : 0,
        starts: a.starts, lost: a.lost, lost_by: sc.weeks[w].lost_by, open, filled, unused, adds: f.adds,
        few: lowStarts, main,
      };
      total += a.value + stream;
      volume += vol;
    }
    return { weeks, total, volume, vps: volume ? total / volume : 0, started: vs, fill };
  }

  // The weekly ranks and the vulnerable flag of the teams of the league (League page, #229). teams: a list of
  // weekTotals() results. weeks: the week names. weak: {band: [lo, hi], below} of [league_page] in config.toml.
  // The result: one object for each team, in the order of teams:
  //   weeks: {week: {r_total, r_volume, r_vps, below, vulnerable}}. r_*: the rank of the week's total, volume and
  //     vps among the teams (rankMedian()). below: 1 - total / the mean week of the team.
  //   weakAll: true if the rank of the total is in the band in each week ("weak all 3 weeks").
  //   vulnerable: the rank of the total is in the band and below >= weak.below, and weakAll is false.
  //   weakest: the week with the worst rank of the total (owner decision 1 of 2026-11-02 on #229). With equal ranks,
  //     the week with the lower total, then the first week. worst: the rank of that week.
  function weekRanks(teams, weeks, weak) {
    const [lo, hi] = weak.band, inBand = r => r >= lo && r <= hi;
    const out = teams.map(() => ({ weeks: {} }));
    for (const w of weeks) {
      const rank = k => {
        const vals = teams.map(t => t.weeks[w][k]);
        return teams.map(t => rankMedian(vals, t.weeks[w][k]).rank);
      };
      const rt = rank("total"), rv = rank("volume"), rp = rank("vps");
      teams.forEach((_, i) => { out[i].weeks[w] = { r_total: rt[i], r_volume: rv[i], r_vps: rp[i] }; });
    }
    teams.forEach((t, i) => {
      const o = out[i], mean = weeks.reduce((s, w) => s + t.weeks[w].total, 0) / (weeks.length || 1);
      o.weakAll = weeks.length > 0 && weeks.every(w => inBand(o.weeks[w].r_total));
      for (const w of weeks) {
        const x = o.weeks[w];
        x.below = mean ? 1 - t.weeks[w].total / mean : 0;
        // The 1e-9 keeps a week at exactly weak.below in the flag, also with a rounding error of the float math
        x.vulnerable = !o.weakAll && inBand(x.r_total) && x.below >= weak.below - 1e-9;
      }
      o.weakest = weeks.reduce((a, w) => {
        const x = o.weeks[w], y = o.weeks[a];
        return x.r_total > y.r_total || (x.r_total === y.r_total && t.weeks[w].total < t.weeks[a].total) ? w : a;
      }, weeks[0]);
      o.worst = o.weakest === undefined ? 0 : o.weeks[o.weakest].r_total;
    });
    return out;
  }

  // The weekTotals() options of a core of the Playoffs page (#230), as the League page counts a row (#229).
  // opts: {resters, roster_spots, adds, v, few}. The stream spots: roster_spots - the core size, 0 at least.
  const _weekOpts = (core, opts) => ({
    spots: Math.max(0, (opts.roster_spots || 0) - core.length), adds: opts.adds, resters: opts.resters, v: opts.v,
    few: opts.few,
  });

  // The weekly Totals of the other teams of the league (Playoffs page, #230): weekTotals() of the best core of each
  // team, as the League page counts the rows of the other teams (#229). players: the pool. A player with an owner
  // and no mine flag is on another team. opts: {n, roster_spots, adds, v, few}. n: the core size.
  // The result: one weekTotals() result for each other team, in the order of the first player of each team.
  function otherTotals(players, data, opts) {
    const by = new Map();
    for (const p of players) {
      if (!p.owner || p.mine) continue;
      if (!by.has(p.owner)) by.set(p.owner, []);
      by.get(p.owner).push(p);
    }
    return [...by.values()].map(roster => {
      const core = bestCore(roster, data, opts.n);
      return weekTotals(core, data, _weekOpts(core, { ...opts, resters: undefined }));
    });
  }

  // The floor of a core (Playoffs page, #230). others: otherTotals(). opts: {resters, roster_spots, adds, v, few,
  // weak}. weak: {band, below} as in weekRanks().
  // The result: {wt, rk, weakest, spread, lowest, low_week, teams}.
  //   wt: weekTotals() of the core. rk: weekRanks() of the core among the teams of the league.
  //   weakest: the week with the worst rank of the Total (owner decision 1 of 2026-11-02 on #229).
  //   spread: the best weekly Total - the worst weekly Total. lowest: the lowest weekly Total (owner decision 2 of
  //   2026-11-02 on #230), low_week: its week (the first week on equal Totals). teams: the teams of the ranks.
  function coreFloor(core, others, data, opts) {
    const wt = weekTotals(core, data, _weekOpts(core, opts));
    const rk = weekRanks(others.concat([wt]), data.weeks, opts.weak).pop();
    const totals = data.weeks.map(w => wt.weeks[w].total), lowest = Math.min(...totals);
    return {
      wt, rk, weakest: rk.weakest, spread: Math.max(...totals) - lowest, lowest,
      low_week: data.weeks[totals.indexOf(lowest)], teams: others.length + 1,
    };
  }

  // The data of one week. valueStarted() and streamFill() count each week alone, so weekTotals() of this data gives
  // the same numbers for the week as weekTotals() of all the data.
  const _weekData = (data, w) => ({ ...data, weeks: [w], days: data.days.filter(d => d.week === w) });

  // The Best swaps by the gain to the worst week (Playoffs page, owner decisions 3 and 5 of 2026-11-02 on #230). The
  // worst week is the week with the lowest weekly Total (low_week of coreFloor()), the week of the trend floor. It is
  // not the weakest week by rank. others: otherTotals().
  // opts: the opts of coreFloor() and {band, banded, untouchable, limit} as in bestSwaps().
  // For each pool player, the swap-out with the largest gain to the Total of the worst week now. Only a swap with a
  // gain above 0. A player with a value of 0 or less, or with no game in the worst week, cannot raise it.
  // The result: [{in, out, gain, total, week, after, rank, after_total}], the largest gain first.
  //   gain: the change of the Total of the worst week. total: the change of the Total of all weeks. week: the worst
  //   week now. after: the lowest week with the swap, rank: its rank, after_total: its Total.
  function floorSwaps(core, pool, others, data, opts = {}) {
    const limit = opts.limit === undefined ? 10 : opts.limit;
    const banded = _ids(opts.banded), untouchable = _ids(opts.untouchable);
    const inCore = new Set(core.map(p => p.id)), base = coreFloor(core, others, data, opts), w = base.low_week;
    const now = base.wt.weeks[w].total, week = _weekData(data, w);
    const plays = new Set(week.days.flatMap(d => d.teams)), rows = [];
    for (const p of pool) {
      if (inCore.has(p.id) || !(p.value > 0) || !plays.has(p.team)) continue;
      let best = null;
      for (const o of core) {
        if (untouchable.has(o.id)) continue;
        if (opts.band && banded.has(p.id) && !inBand(o.value, p.value, opts.band)) continue;
        const swapped = core.map(c => (c.id === o.id ? p : c));
        const gain = weekTotals(swapped, week, _weekOpts(swapped, opts)).weeks[w].total - now;
        if (gain <= 1e-9) continue;
        if (!best || gain > best.gain + 1e-9) best = { in: p.id, out: o.id, gain, swapped };
      }
      if (best) rows.push(best);
    }
    rows.sort((a, b) => b.gain - a.gain);
    return rows.slice(0, limit).map(r => {
      const f = coreFloor(r.swapped, others, data, opts);
      return {
        in: r.in, out: r.out, gain: r.gain, total: f.wt.total - base.wt.total, week: w, after: f.low_week,
        rank: f.rk.weeks[f.low_week].r_total, after_total: f.lowest,
      };
    });
  }

  // The row of the history file of one planning run (Playoffs page, owner decision 1 of 2026-11-02 on #230): the
  // weekly Totals of the best core of your roster, with the rests_b2b of the player file. players: the pool, with
  // mine on your players. opts: {n, roster_spots, adds, v, few, weak}.
  // The result: {core: the ids of the core, weeks: {week: {total, rank}}, total: the Total of all weeks}.
  function historyRow(players, data, opts) {
    const core = bestCore(players.filter(p => p.mine), data, opts.n);
    const f = coreFloor(core, otherTotals(players, data, opts), data, { ...opts, resters: undefined });
    const weeks = {};
    for (const w of data.weeks) weeks[w] = { total: f.wt.weeks[w].total, rank: f.rk.weeks[w].r_total };
    return { core: core.map(p => p.id), weeks, total: f.wt.total };
  }

  // The points of the trend (Playoffs page, owner decision 2 of 2026-11-02 on #230): one point for each row of the
  // history file, in the order of rows. weeks: the week names.
  // The result: [{made, floor, week, rank, total}]. floor: the lowest weekly Total of the row, week: its week (the
  // first week on equal Totals), rank: its rank. total: the sum of the weekly Totals.
  function trendPoints(rows, weeks) {
    return rows.map(r => {
      const week = weeks.reduce((a, w) => (r.weeks[w].total < r.weeks[a].total ? w : a), weeks[0]);
      return {
        made: r.made, floor: r.weeks[week].total, week, rank: r.weeks[week].rank,
        total: weeks.reduce((s, w) => s + r.weeks[w].total, 0),
      };
    });
  }

  return {
    scoreCore, fit, slotRoster, valueStarted, idealGames, adds, bestSwaps, inBand, bestCore, streamFill, rankMedian,
    weekTotals, weekRanks, otherTotals, coreFloor, floorSwaps, historyRow, trendPoints,
  };
})();

if (typeof module !== "undefined") module.exports = Starts;
