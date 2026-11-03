// The Playoffs page (#214, #215): the value started of your playoff core, in the browser.
//
// playoffs/page.py inlines core/starts.js, then this file, then start(). The page data is the JSON of page_data()
// in playoffs/page.py. valueStarted(), adds() and bestSwaps() of core/starts.js give each number of the page. This
// file has no lineup math.
// The part before start() has no DOM code, so Node loads the file with require() and tests the HTML of the page
// (tests/playoffs/test_page.py). Node loads core/starts.js itself.
//
// The Floor block (#230): coreFloor(), floorSwaps() and trendPoints() of core/starts.js give its numbers and the
// ranking of the Best swaps by the gain to the worst week. data.history: the earlier rows of the history file.
//
// The state of the page: {n, core, added, rest, saved, filter, rank}.
//   n: the core size. core: the ids of the core players. added: the ids of the players that the search added.
//   rest: {id: true or false}, the R switches that differ from rests_b2b of the player file.
//   saved: the time of the last save (ISO), or null. filter: the owner filter of the Best swaps list, "fa", "other"
//   or "all". rank: the ranking of the Best swaps list, "schedule" (the default) or "floor". Save keeps neither.
// Save keeps the state in localStorage (data.key). Reset clears the added players, the R switches and the save.

const Playoffs = (() => {
  const S = typeof Starts !== "undefined" ? Starts : require("../core/starts.js");
  const LETTER = ["S", "M", "T", "W", "T", "F", "S"];
  const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MARK_TEXT = { s: "starts", b: "game, sits", r: "rests on back-to-back", n: "no game" };
  const MAX_HITS = 8; // the search shows this many players at most
  const SWAP_ROWS = 10; // the Best swaps list shows this many rows at most (decision 16)
  const FILTERS = [["fa", "Free agents"], ["other", "Other teams"], ["all", "All"]]; // decision 17
  const FILTER_NOUN = { fa: "free agents", other: "other teams' players", all: "players" };
  const RANKS = [["schedule", "Schedule gain"], ["floor", "Worst-week gain"]]; // #230: the default first

  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const f1 = v => (v < -0.05 ? "−" : "") + Math.abs(v).toFixed(1);
  const sgn = v => (v >= 0.05 ? "+" : "") + f1(v);
  const sgnInt = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v);
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const wkLabel = w => w[0].toUpperCase() + w.slice(1);
  const dayDate = d => new Date(d.date + "T12:00:00");

  // The model of the page data: the engine data of core/starts.js, the players by id and your players.
  // Each player of data.players has a number in value (page.py: val, else proj_val, else 0), so no null value
  // reaches valueStarted().
  function model(data) {
    const engine = {
      slots: data.slots, util: data.util, weeks: data.weeks, quality_bonus: data.quality_bonus,
      days: data.days.map(d => ({ date: d.date, week: d.week, quality: d.quality, teams: d.teams, b2b: d.b2b })),
    };
    const byId = Object.fromEntries(data.players.map(p => [p.id, p]));
    return { data, engine, byId, mine: data.players.filter(p => p.mine).map(p => p.id) };
  }

  function newState(m) {
    return { n: m.data.core, core: [], added: [], rest: {}, saved: null, filter: "all", rank: "schedule" };
  }

  const isRest = (m, st, id) => (id in st.rest ? st.rest[id] : !!m.byId[id].rests_b2b);

  // valueStarted() of the players ids. The R switches of the state give the rester set.
  function score(m, st, ids = st.core) {
    return S.valueStarted(ids.map(id => m.byId[id]), m.engine, ids.filter(id => isRest(m, st, id)));
  }

  // The ids of all pool players who rest on back-to-backs, for the swap search: the R switches, else rests_b2b.
  const resters = (m, st) => new Set(m.data.players.filter(p => isRest(m, st, p.id)).map(p => p.id));

  // The Adds of each listed player and the weakest link (decision 9): adds() of core/starts.js. The weakest link is
  // the core player with the lowest Adds, if the core has 2 or more players. A core player with a Val below 0 still
  // starts (review nit 3 of #216), so his Adds is below 0, and he is the weakest link.
  function addsOf(m, st, listed) {
    const inCore = new Set(st.core), pl = ids => ids.map(id => m.byId[id]);
    const adds = S.adds(pl(st.core), m.engine, resters(m, st), pl(listed.filter(id => !inCore.has(id))));
    const weak = st.core.length > 1 ? st.core.reduce((a, b) => (adds[b] < adds[a] ? b : a)) : null;
    return { adds, weak };
  }

  // The pool of the Best swaps list for an owner filter: the players who are not yours and not in the core.
  function swapPool(m, st, filter) {
    const inCore = new Set(st.core);
    const keep = p => filter === "all" || (filter === "fa" ? !p.owner : !!p.owner);
    return m.data.players.filter(p => !p.mine && !inCore.has(p.id) && keep(p));
  }

  // The Best swaps (decisions 16 to 18): bestSwaps() of core/starts.js. The players of other teams have the value
  // band of [trade] value_band. Free agents have no band. A [trade] untouchable player is never a swap-out.
  function swaps(m, st, filter = st.filter) {
    const pool = swapPool(m, st, filter);
    return S.bestSwaps(st.core.map(id => m.byId[id]), pool, m.engine, {
      resters: resters(m, st), band: m.data.band, banded: pool.filter(p => p.owner).map(p => p.id),
      untouchable: m.data.untouchable, limit: SWAP_ROWS,
    });
  }

  // The weekTotals() options of the page (#230): the settings of the League page (#229) and the R switches.
  const weekOpts = (m, st) => ({
    n: m.data.core, roster_spots: m.data.roster_spots, adds: m.data.adds, v: m.data.v, few: m.data.weak.few,
    weak: m.data.weak, resters: resters(m, st),
  });

  // The weekly Totals of the other teams (#230): otherTotals() of core/starts.js. The page does not change them, so
  // the model keeps them.
  function others(m) {
    if (!m.others) m.others = S.otherTotals(m.data.players, m.engine, weekOpts(m, newState(m)));
    return m.others;
  }

  // The floor of the core ids (#230): coreFloor() of core/starts.js, with the R switches of the state.
  function floor(m, st, ids = st.core) {
    return S.coreFloor(ids.map(id => m.byId[id]), others(m), m.engine, weekOpts(m, st));
  }

  // The Best swaps by the gain to the worst week (#230): floorSwaps() of core/starts.js. The same pool, value band
  // and untouchable rule as swaps().
  function floorSwaps(m, st, filter = st.filter) {
    const pool = swapPool(m, st, filter);
    return S.floorSwaps(st.core.map(id => m.byId[id]), pool, others(m), m.engine, {
      ...weekOpts(m, st), band: m.data.band, banded: pool.filter(p => p.owner).map(p => p.id),
      untouchable: m.data.untouchable, limit: SWAP_ROWS,
    });
  }

  // The best core of n players (decision 11): your n players with the highest value started alone, bestCore() of
  // core/starts.js. The League page uses the same rule (#218).
  function bestCore(m, st, n) {
    return S.bestCore(m.mine.map(id => m.byId[id]), m.engine, n, resters(m, st)).map(p => p.id);
  }

  // The light nights of a player (decision 6): his games on quality days, from the marks of valueStarted().
  // A rest night is not a game.
  function lightNights(m, st, id) {
    return count(m, score(m, st, [id]).marks[id], weekDays(m, null))[2];
  }

  // The display order of the core: Val, highest first.
  const ordered = (m, st) => st.core.slice().sort((a, b) => m.byId[b].value - m.byId[a].value);

  const owner = p => (p.mine ? "Mine" : p.owner || "FA");
  const pos = p => p.pos.join("/") || "Util";
  const valText = p => (p.mark === "none" ? "–" : f1(p.value));
  const projTag = p => (p.mark === "proj" ? '<em class="tag">proj</em>' : "");
  const restTag = (m, st, id) => (isRest(m, st, id) ? '<em class="tag" title="Rests on back-to-backs">R</em>' : "");
  const link = p => `<a class="lab-pname" href="#player=${esc(p.id)}" data-player="${esc(p.id)}">${esc(p.name)}</a>`;
  const band = (m, team) => m.data.bands[team] || m.data.bands[""];

  function dayClass(m, i, base) {
    const d = m.data.days[i], first = i === 0 || m.data.days[i - 1].week !== d.week;
    return [base, d.quality ? "q" : "", first ? "wk1" : ""].filter(Boolean).join(" ");
  }

  const dayLabel = d => { const dt = dayDate(d); return `${MONTH[dt.getMonth()]} ${dt.getDate()}`; };
  const slotCount = m => m.data.slots.length + m.data.util;

  // (starts, games, games on light nights) of the marks of a player on the days idx. A rest night is not a game.
  function count(m, marks, idx) {
    const games = idx.filter(i => marks[i] === "s" || marks[i] === "b");
    return [idx.filter(i => marks[i] === "s").length, games.length, games.filter(i => m.data.days[i].quality).length];
  }

  const weekDays = (m, w) => m.data.days.map((d, i) => i).filter(i => w === null || m.data.days[i].week === w);

  // The headline (decisions 4 to 6): value started, then the core, the starts lost, the open slots and the starts.
  function headline(m, st, sc) {
    const t = sc.total;
    return (
      `<div class="hero"><dt>Value started</dt><dd>${f1(t.value)}</dd></div>` +
      `<div><dt>Core</dt><dd>${st.core.length}<small>players</small></dd></div>` +
      `<div><dt>Starts lost</dt><dd>${t.lost}</dd></div>` +
      `<div><dt>Open slots</dt><dd>${t.open_heavy + t.open_light}<small>${t.open_heavy} heavy · ${t.open_light} light</small></dd></div>` +
      `<div><dt>Starts</dt><dd>${t.starts}<small>/ ${plural(t.games, "game")} · ideal ${t.ideal}</small></dd>` +
      `<dd class="sub">${clashes(t)} · ${belowIdeal(t)}</dd></div>`
    );
  }

  // The starts of a week or of all weeks against the games of the core and the ideal of the Roster page (owner
  // decision of 2026-11-01 on #214). games = starts + lost. ideal: idealGames() of core/starts.js.
  const clashes = t => `${t.games - t.starts} lost to slot clashes`;
  const belowIdeal = t => `${Math.max(0, t.ideal - t.games)} below ideal`;
  const startsText = t => `${t.starts} starts of ${plural(t.games, "game")}, ideal ${t.ideal}: ${clashes(t)}, ${belowIdeal(t)}`;

  // The totals of each week, then the total.
  function weeksTable(m, sc) {
    const row = (label, w, cls) =>
      `<tr${cls ? ` class="${cls}"` : ""}><th class="l" scope="row">${label}</th><td>${f1(w.value)}</td>` +
      `<td>${w.starts} / ${w.games}<small>${clashes(w)}</small></td><td>${w.ideal}<small>${belowIdeal(w)}</small></td>` +
      `<td>${w.open_heavy}</td><td>${w.open_light}</td></tr>`;
    return (
      '<thead><tr><th class="l" scope="col">Week</th><th scope="col">Value started</th><th scope="col">Starts / games</th>' +
      '<th scope="col">Ideal</th><th scope="col">Open heavy</th><th scope="col">Open light</th></tr></thead><tbody>' +
      m.data.weeks.map(w => row(wkLabel(w), sc.weeks[w])).join("") + row("Total", sc.total, "t") + "</tbody>"
    );
  }

  function weekCell(m, marks, w, cls) {
    const [s, g, q] = count(m, marks, weekDays(m, w));
    return (
      `<td class="${cls}${s < g ? " lo" : ""}">${s}<s aria-hidden="true">/${g}</s>` +
      `<span class="vh"> starts of ${plural(g, "game")}</span><small class="qg">${q} q</small></td>`
    );
  }

  const mark = (d, k, title = true) => {
    const label = `${dayLabel(d)}${d.quality ? ", light night" : ""}: ${MARK_TEXT[k]}`;
    return `<i class="${k}" role="img" aria-label="${label}"${title ? ` title="${label}"` : ""}></i>`;
  };

  // The core grid (decisions 13 and 15): a row for each core player with the marks of the Roster grid, then the
  // Starts, Open slots and NBA games rows.
  function grid(m, st, sc) {
    const D = m.data, nd = D.days.length, nw = D.weeks.length, slots = slotCount(m);
    const wCls = i => (i ? "w" : "w w1");
    let h =
      '<caption class="vh">The core in Val order, the starts and games of each playoff week and the playoff days.</caption>' +
      `<colgroup><col class="c-band"><col class="c-pl"><col class="c-w" span="${nw + 1}"><col class="c-d" span="${nd}"></colgroup>` +
      `<thead><tr class="top"><td colspan="2"></td><th colspan="${nw + 1}" scope="colgroup" class="fine sec">Starts / games</th>` +
      `<th colspan="${nd}" scope="colgroup" class="l sec gdh">Playoff days · ${esc(D.span)} · <i class="qk" aria-hidden="true"></i>light night</th></tr>` +
      '<tr class="sub"><th scope="col" class="l">Team</th><th scope="col" class="l">Player</th>' +
      D.weeks.map((w, i) => `<th scope="col" class="${wCls(i)}">${wkLabel(w)}</th>`).join("") + '<th scope="col" class="w t">T</th>' +
      D.days.map((d, i) => {
        const dt = dayDate(d);
        return `<th scope="col" class="${dayClass(m, i, "d")}"><abbr title="${dt.toDateString()}${d.quality ? ", light night" : ""}">` +
          `${LETTER[dt.getDay()]}</abbr><u>${dt.getDate()}</u></th>`;
      }).join("") + "</tr></thead><tbody>";
    const core = ordered(m, st);
    if (!core.length) h += `<tr><td class="empty" colspan="${3 + nw + nd}">No core players. Tick a player in the Players table.</td></tr>`;
    for (const id of core) {
      const p = m.byId[id], marks = sc.marks[id];
      h += `<tr><td class="band" style="${band(m, p.team)}">${esc(p.team)}</td>` +
        `<th class="pl" scope="row"><b>${link(p)}</b>${restTag(m, st, id)}<small>${esc(pos(p))} · Val ${valText(p)}${p.mark === "proj" ? " proj" : ""}</small></th>` +
        D.weeks.map((w, i) => weekCell(m, marks, w, wCls(i))).join("") + weekCell(m, marks, null, "w t") +
        marks.map((k, i) => `<td class="${dayClass(m, i, "d")}">${mark(D.days[i], k)}</td>`).join("") + "</tr>";
    }
    const weekTotals = f => D.weeks.map((w, i) => `<td class="${wCls(i)}">${f(sc.weeks[w], w)}</td>`).join("") + `<td class="w t">${f(sc.total, null)}</td>`;
    h += "</tbody><tfoot>" +
      `<tr class="st"><th class="lab" colspan="2" scope="row">Starts</th>${weekTotals(t => `<span aria-hidden="true" title="${startsText(t)}">${t.starts}<small>of ${t.games}</small><small>ideal ${t.ideal}</small></span><span class="vh">${startsText(t)}</span>`)}` +
      sc.days.map((d, i) => `<td class="${dayClass(m, i, "d")}">${D.days[i].teams.length ? `${d.starts}<small>/${slots}</small><span class="vh"> of ${slots} slots start</span>` : ""}</td>`).join("") + "</tr>" +
      `<tr class="os"><th class="lab" colspan="2" scope="row">Open slots</th>${weekTotals(t => `${t.open_heavy + t.open_light}<small>${t.open_light} light</small>`)}` +
      sc.days.map((d, i) => `<td class="${dayClass(m, i, "d")}">${d.open || ""}</td>`).join("") + "</tr>" +
      `<tr class="og"><th class="lab" colspan="2" scope="row">NBA games</th>${weekTotals(() => "")}` +
      D.days.map((d, i) => `<td class="${dayClass(m, i, "d")}">${d.games}</td>`).join("") + "</tr></tfoot>";
    return h;
  }

  // The day head of a phone row: a letter and a date for each day.
  function phoneHead(m) {
    return m.data.days.map((d, i) => {
      const dt = dayDate(d), cls = dayClass(m, i, "");
      return `<span${cls ? ` class="${cls}"` : ""} aria-hidden="true">${LETTER[dt.getDay()]}<u>${dt.getDate()}</u></span>`;
    }).join("");
  }

  // The phone grid (the tap-to-open rows of the Roster page): one row for each core player, then the totals.
  function phone(m, st, sc) {
    const D = m.data, slots = slotCount(m), head = phoneHead(m);
    let h = '<div class="m-head" aria-hidden="true"><span>Team</span><span>Player · Val</span><span>St</span><span>Gms</span><span></span></div>';
    const core = ordered(m, st);
    if (!core.length) h += '<p class="m-empty">No core players. Tick a player in the Players table.</p>';
    for (const id of core) {
      const p = m.byId[id], marks = sc.marks[id], [s, g] = count(m, marks, weekDays(m, null));
      const weeks = [...D.weeks, null].map(w => {
        const [ws, wg, wq] = count(m, marks, weekDays(m, w));
        return `<div${ws < wg ? ' class="lo"' : ""}><dt>${w ? wkLabel(w) : "Total"}</dt><dd><b>${ws}</b><s>/${wg}</s><small>${wq} q</small></dd></div>`;
      }).join("");
      const cells = marks.map((k, i) => { const cls = dayClass(m, i, ""); return `<span${cls ? ` class="${cls}"` : ""}>${mark(D.days[i], k, false)}</span>`; }).join("");
      h += '<details class="m-p">' +
        `<summary><span class="band" style="${band(m, p.team)}">${esc(p.team)}</span>` +
        `<span class="nm"><b>${link(p)}</b>${restTag(m, st, id)}<small>${esc(pos(p))} · Val ${valText(p)}${p.mark === "proj" ? " proj" : ""}</small></span>` +
        `<span class="gp"><span class="vh">, playoff starts </span>${s}</span>` +
        `<span class="tg"><span class="vh">, playoff games </span>${g}</span><span class="chev" aria-hidden="true"></span></summary>` +
        `<div class="m-body"><dl class="m-weeks" aria-label="Playoff starts / games">${weeks}</dl>` +
        `<div class="m-grid">${head}${cells}</div></div></details>`;
    }
    const weekDl = f => D.weeks.map(w => `<div><dt>${wkLabel(w)}</dt><dd>${f(sc.weeks[w], w)}</dd></div>`).join("") +
      `<div class="t"><dt>Total</dt><dd>${f(sc.total, null)}</dd></div>`;
    const row = (label, f) => `<p class="ul">${label}</p><div class="m-row">${D.days.map((d, i) => {
      const cls = dayClass(m, i, ""); return `<span${cls ? ` class="${cls}"` : ""}>${f(d, i)}</span>`; }).join("")}</div>`;
    h += '<div class="m-tot"><b>Core starts</b>' +
      `<dl>${weekDl(t => `${t.starts}<small>of ${plural(t.games, "game")}</small><small>ideal ${t.ideal}</small><small>${clashes(t)}</small><small>${belowIdeal(t)}</small>`)}</dl>` +
      `<p class="ul">Open slots</p><dl class="u">${weekDl(t => `<b>${t.open_heavy + t.open_light}</b><small>${t.open_light} light</small>`)}</dl>` +
      `<div class="m-row hd">${head}</div>` +
      row(`Starts each day, of ${slots}`, (d, i) => (d.teams.length ? sc.days[i].starts : "")) +
      row("Open slots each day", (d, i) => sc.days[i].open || "") +
      row("NBA games", d => d.games) + "</div>";
    return h;
  }

  // The Why list of a week (#230): the same reasons as the team detail of the League page (#229), from weekTotals().
  function why(f, w, spots) {
    const x = f.wt.weeks[w], items = [];
    if (x.few.length) {
      items.push("<b>Few starts:</b> " + x.few.map(p => `${esc(p.name)} ${p.starts} of ${plural(p.games, "game")}` +
        (p.rested ? `, ${p.rested} rest` : "")).join("; "));
    }
    const by = Object.entries(x.lost_by).sort((a, b) => b[1] - a[1]);
    if (x.lost) items.push(`<b>${x.lost} starts lost on crowded nights:</b> ${by.map(([n, c]) => `${esc(n)} ${c}`).join(", ")}`);
    if (x.unused) items.push(`<b>${x.unused} open slots the streams cannot fill:</b> they fill ${x.filled} of ${x.open} ` +
      `(${plural(spots, "stream spot")}, ${x.adds} adds)`);
    const main = x.main === "unused" ? `${x.unused} open slots the streams cannot fill`
      : x.main === "lost" ? `${x.lost} starts lost on crowded nights` : "";
    return { items, main };
  }

  // The Floor block (#230): the weekly Totals, Volume and Value per start of the core, the weakest week, the spread,
  // the Why list and the trend. They change when the core changes. f: floor().
  function floorView(m, st, f) {
    if (!st.core.length) return "<p>The core needs 1 or more players.</p>";
    const D = m.data, n = f.teams, w = f.weakest, spots = Math.max(0, D.roster_spots - st.core.length);
    const x = { ...f.wt.weeks[w], ...f.rk.weeks[w] }, y = why(f, w, spots), mean = f.wt.total / D.weeks.length;
    const f2 = v => v.toFixed(2);
    let h = '<dl class="stats fl-stats">' +
      `<div class="hero"><dt>Weakest week</dt><dd>${wkLabel(w)}<small>rank ${x.r_total} of ${n} · Total ${f1(x.total)}</small></dd></div>` +
      `<div><dt>Spread</dt><dd>${f1(f.spread)}<small>best − worst week</small></dd></div>` +
      `<div><dt>Mean week</dt><dd>${f1(mean)}<small>Total ${f1(f.wt.total)} ÷ ${D.weeks.length}</small></dd></div></dl>`;
    const row = w2 => {
      const a = f.wt.weeks[w2], r = f.rk.weeks[w2], weak = w2 === w;
      return `<tr${weak ? ' class="weak"' : ""}><th class="l" scope="row">${wkLabel(w2)}${weak ? ' <em class="tag weak">Weakest</em>' : ""}</th>` +
        `<td><b>${f1(a.total)}</b><small>rank ${r.r_total} of ${n}</small></td><td>${f1(a.value)}</td><td>${f1(a.stream)}</td>` +
        `<td>${a.volume}<small>rank ${r.r_volume}</small></td><td>${f2(a.vps)}<small>rank ${r.r_vps}</small></td></tr>`;
    };
    h += '<div class="fl-scroll"><table class="wk fl-t" aria-label="Floor of each week"><thead><tr><th class="l" scope="col">Week</th>' +
      '<th scope="col" title="Value started + stream value">Total</th><th scope="col">Value started</th><th scope="col" title="Stream games × v">Stream</th>' +
      '<th scope="col" title="Core starts + stream starts">Volume</th><th scope="col" title="Total ÷ Volume">Value / start</th></tr></thead><tbody>' +
      D.weeks.map(row).join("") +
      `<tr class="t"><th class="l" scope="row">Total</th><td>${f1(f.wt.total)}</td><td>${f1(D.weeks.reduce((s, k) => s + f.wt.weeks[k].value, 0))}</td>` +
      `<td>${f1(D.weeks.reduce((s, k) => s + f.wt.weeks[k].stream, 0))}</td><td>${f.wt.volume}</td><td>${f2(f.wt.vps)}</td></tr></tbody></table></div>`;
    h += `<div class="why"><h3>Why ${wkLabel(w)} is the weakest week</h3>` +
      (y.main ? `<p><b>Main cause:</b> ${y.main}.</p>` : "") +
      (y.items.length ? `<ul>${y.items.map(i => `<li>${i}</li>`).join("")}</ul>` : "<p>No lost starts and no unused slots.</p>") + "</div>";
    return h + trend(m, f);
  }

  const TREND_MIN = 2; // the trend shows a line from this many points

  // The points of the trend (#230): trendPoints() of the earlier rows of the history file, then the core on the page
  // now. floor: the lowest weekly Total (owner decision 2 of 2026-11-02 on #230). f: floor().
  function trendRuns(m, f) {
    const D = m.data;
    return S.trendPoints(D.history || [], D.weeks).concat([{
      made: D.made, now: true, floor: f.lowest, week: f.low_week, rank: f.rk.weeks[f.low_week].r_total, total: f.wt.total,
    }]);
  }

  // The trend of the floor and the Total, run by run (#230). The line needs TREND_MIN points, else the block says
  // why it is empty.
  function trend(m, f) {
    const runs = trendRuns(m, f), D = m.data;
    if (runs.length < TREND_MIN) {
      return '<div class="trend"><h3>Trend, run by run</h3><p class="state"><b>No trend yet.</b> Each planning run saves ' +
        `the weekly Totals of your best ${D.core} to the history. The line starts at the first run on a later day.</p></div>`;
    }
    const W = 580, L = 40, R = 92, H = 92, T = 12, B = 10, pw = W - L - R;
    const xs = i => L + (i * pw) / (runs.length - 1);
    const md = s => { const d = new Date(s + "T12:00:00"); return `${d.getMonth() + 1}/${d.getDate()}`; };
    const panel = (key, label, hero, y0) => {
      const vals = runs.map(r => r[key]), lo = Math.min(...vals), hi = Math.max(...vals), pad = Math.max(1, (hi - lo) * 0.15);
      const a = Math.floor(lo - pad), b = Math.ceil(hi + pad), ys = v => y0 + T + (H - T - B) * (1 - (v - a) / (b - a));
      const pts = runs.map((r, i) => `${xs(i).toFixed(1)},${ys(r[key]).toFixed(1)}`).join(" ");
      const ticks = [a, (a + b) / 2, b].map(v => `<text class="tk" x="${L - 6}" y="${(ys(v) + 3.5).toFixed(1)}" text-anchor="end">${Math.round(v)}</text>`).join("");
      const last = runs[runs.length - 1], lx = xs(runs.length - 1), ly = ys(last[key]);
      const dots = runs.map((r, i) => r.now ? "" :
        `<circle class="dot" cx="${xs(i).toFixed(1)}" cy="${ys(r[key]).toFixed(1)}" r="3.5"><title>${md(r.made)}: ${label} ${f1(r[key])}${key === "floor" ? `, ${wkLabel(r.week)} rank ${r.rank}` : ""}</title></circle>`).join("");
      return `<text class="pl" x="${L}" y="${y0 + 8}">${label}</text>${ticks}` +
        `<polyline class="${hero ? "hero" : "sec"}" points="${pts}"/>${dots}` +
        `<circle class="${hero ? "now" : "now sec"}" cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="4"><title>Now, this core: ${label} ${f1(last[key])}</title></circle>` +
        `<text class="${hero ? "el" : "el2"}" x="${lx + 8}" y="${(ly + 4).toFixed(1)}">${label} ${f1(last[key])}</text>`;
    };
    const svg = `<svg class="tr" viewBox="0 0 ${W} ${2 * H + 34}" role="img" aria-label="The floor and the Total of each run.">` +
      panel("floor", "Floor", true, 0) + panel("total", "Total", false, H + 6) +
      runs.map((r, i) => `<text class="dt" x="${xs(i).toFixed(1)}" y="${2 * H + 28}" text-anchor="middle">${r.now ? "now" : md(r.made)}</text>`).join("") + "</svg>";
    return `<div class="trend"><h3>Trend, run by run</h3>${svg}<p class="state">${plural(runs.length - 1, "earlier planning run")} ` +
      `with the best ${D.core} of your roster. The last point is the core on this page now. Floor: the lowest weekly Total of each run.</p></div>`;
  }

  // The columns of the Players table: the class of each <col>. The colgroup and the separator rows use this list.
  const PLAYER_COLS = ["c-in", "", "c-v", "c-q", "c-a", "c-r", "c-x"];

  // The Adds cell (decision 9): the Adds, the weakest-link flag, and "if added" for a player outside the core.
  function addsCell(a, weak, inside) {
    return `<td class="a"><span${a < -0.05 ? ' class="neg"' : ""}>${sgn(a)}</span>` +
      (weak ? '<br><em class="tag weak" title="The core player with the lowest Adds">Weakest</em>' : "") +
      (inside ? "" : "<small>if added</small>") + "</td>";
  }

  // The Players table: the core, then the players outside the core (your other players and the added players).
  function players(m, st) {
    const inCore = new Set(st.core);
    const listed = [...new Set([...st.core, ...m.mine, ...st.added])];
    const { adds, weak } = addsOf(m, st, listed);
    const byVal = l => l.sort((a, b) => m.byId[b].value - m.byId[a].value);
    const coreRows = byVal(st.core.slice()), outRows = byVal(listed.filter(id => !inCore.has(id)));
    const row = (id, inside) => {
      const p = m.byId[id], r = isRest(m, st, id);
      return `<tr class="${inside ? "in" : "out"}"><td><input type="checkbox" data-core="${esc(id)}"${inside ? " checked" : ""} aria-label="${esc(p.name)} in the core"></td>` +
        `<th scope="row"><b>${link(p)}</b>${restTag(m, st, id)}<small>${esc(p.team)} · ${esc(pos(p))} · ${esc(owner(p))}</small></th>` +
        `<td>${valText(p)}${projTag(p)}</td><td>${lightNights(m, st, id)}</td>${addsCell(adds[id], id === weak, inside)}` +
        `<td><button type="button" class="rb" data-rest="${esc(id)}" aria-pressed="${r}" aria-label="${esc(p.name)} rests on back-to-backs" title="Rests on back-to-backs">R</button></td>` +
        `<td>${p.mine ? "" : `<button type="button" class="x" data-drop="${esc(id)}" aria-label="Remove ${esc(p.name)} from the page" title="Remove">×</button>`}</td></tr>`;
    };
    const cols = PLAYER_COLS.map(c => (c ? `<col class="${c}">` : "<col>")).join("");
    return (
      `<colgroup>${cols}</colgroup>` +
      '<thead><tr><th scope="col" class="l"><span class="vh">In core</span></th><th scope="col" class="l">Player</th>' +
      '<th scope="col">Val</th><th scope="col" title="Games on light nights">Light</th>' +
      '<th scope="col" title="The value started of the core with the player minus without him">Adds</th>' +
      '<th scope="col" title="Rests on back-to-backs">R</th>' +
      '<th scope="col"><span class="vh">Remove</span></th></tr></thead><tbody>' +
      `<tr class="sep"><td colspan="${PLAYER_COLS.length}">Core · ${coreRows.length}</td></tr>` + coreRows.map(id => row(id, true)).join("") +
      `<tr class="sep"><td colspan="${PLAYER_COLS.length}">Outside the core · ${outRows.length}</td></tr>` + outRows.map(id => row(id, false)).join("") +
      "</tbody>"
    );
  }

  // The Best swaps list (decisions 16 to 18): the owner filter, the band rule, then the rows. A row loads the swap.
  function swapList(m, st) {
    const chips = FILTERS.map(([k, label]) =>
      `<button type="button" class="chip" data-filter="${k}" aria-pressed="${st.filter === k}">${label}</button>`).join("");
    const band = m.data.band, never = m.data.untouchable.map(id => esc(m.byId[id] ? m.byId[id].name : id)).join(", ");
    let h = "<p>Each free agent and player of another team, swapped with each core player. The best swap of each " +
      "player, top 10 by schedule gain: the value gain minus (Val in − Val out) × the starts of the player out. " +
      "Only swaps that raise value started. Click a row to load the swap.</p>" +
      `<div class="chips" role="group" aria-label="Owner">${chips}</div>` +
      `<p class="band">Other teams: Val in ${band[0].toFixed(2)} to ${band[1].toFixed(2)} × the Val of the player out. ` +
      `${never ? `Never swapped out: ${never}. ` : ""}Free agents: no band.</p>`;
    const ranks = RANKS.map(([k, label]) =>
      `<button type="button" class="chip" data-rank="${k}" aria-pressed="${st.rank === k}">${label}</button>`).join("");
    h += `<div class="chips" role="group" aria-label="Rank by"><span class="chl">Rank by</span>${ranks}</div>`;
    if (!st.core.length) return h + "<p>The core needs 1 or more players.</p>";
    if (st.rank === "floor") return h + floorList(m, st);
    const rows = swaps(m, st);
    h += '<table class="sw"><thead><tr><th scope="col" class="l">Player</th><th scope="col" class="l">Owner</th>' +
      '<th scope="col" class="l">Swap out</th><th scope="col" title="Schedule gain">Schedule</th>' +
      '<th scope="col" title="Value gain">Value</th><th scope="col" title="Starts gain (light nights)">Starts</th></tr></thead><tbody>';
    if (rows.length < SWAP_ROWS) {
      h += `<tr class="few"><td colspan="6">Only ${rows.length} ${FILTER_NOUN[st.filter]} have a swap that raises value started.</td></tr>`;
    }
    for (const r of rows) {
      const p = m.byId[r.in], o = m.byId[r.out];
      h += `<tr tabindex="0" data-swap="${esc(r.in)}" data-out="${esc(r.out)}" aria-label="Load the swap: ${esc(p.name)} in, ${esc(o.name)} out">` +
        `<th scope="row"><b>${link(p)}</b>${projTag(p)}<small>${esc(p.team)} · ${esc(pos(p))} · Val ${valText(p)}</small></th>` +
        `<td class="l">${esc(owner(p))}</td><td class="l">${esc(o.name)}</td>` +
        `<td class="g${r.schedule < -0.05 ? " neg" : ""}">${sgn(r.schedule)}</td><td>${sgn(r.gain)}</td>` +
        `<td>${sgnInt(r.starts)} <small>(${sgnInt(r.light)} light)</small></td></tr>`;
    }
    return h + "</tbody></table>";
  }

  // The rows of the Best swaps list ranked by the gain to the worst week (#230, floorSwaps()). The worst week is the
  // week with the lowest weekly Total, the week of the trend floor (owner decision of 2026-11-02 on #230).
  function floorList(m, st) {
    const rows = floorSwaps(m, st), f = floor(m, st), w = f.low_week;
    let h = `<p class="band">Ranked by the gain to the Total of your lowest week now (${wkLabel(w)}, ${f1(f.lowest)}). ` +
      "Total gain: the gain to the 3-week Total. Lowest after: the lowest week with the swap, its Total and rank.</p>" +
      '<table class="sw"><thead><tr><th scope="col" class="l">Player</th><th scope="col" class="l">Owner</th>' +
      `<th scope="col" class="l">Swap out</th><th scope="col" title="Gain to the Total of ${wkLabel(w)}">${wkLabel(w)}</th>` +
      '<th scope="col" title="Gain to the 3-week Total">Total</th><th scope="col" title="The lowest week with the swap">Lowest after</th></tr></thead><tbody>';
    if (rows.length < SWAP_ROWS) {
      h += `<tr class="few"><td colspan="6">Only ${rows.length} ${FILTER_NOUN[st.filter]} have a swap that raises ${wkLabel(w)}.</td></tr>`;
    }
    for (const r of rows) {
      const p = m.byId[r.in], o = m.byId[r.out];
      h += `<tr tabindex="0" data-swap="${esc(r.in)}" data-out="${esc(r.out)}" aria-label="Load the swap: ${esc(p.name)} in, ${esc(o.name)} out">` +
        `<th scope="row"><b>${link(p)}</b>${projTag(p)}<small>${esc(p.team)} · ${esc(pos(p))} · Val ${valText(p)}</small></th>` +
        `<td class="l">${esc(owner(p))}</td><td class="l">${esc(o.name)}</td>` +
        `<td class="g">${sgn(r.gain)}</td><td${r.total < -0.05 ? ' class="neg"' : ""}>${sgn(r.total)}</td>` +
        `<td>${wkLabel(r.after)} ${f1(r.after_total)} <small>(rank ${r.rank})</small></td></tr>`;
    }
    return h + "</tbody></table>";
  }

  // Load a swap (decision 16): the player in takes the place of the player out in the core.
  function swap(m, st, id, out) {
    st.core = st.core.map(c => (c === out ? id : c));
    if (!m.byId[id].mine && !st.added.includes(id)) st.added.push(id);
  }

  // The search (decision 3): the pool players whose name has the text, accents ignored. The text needs 2 letters.
  const norm = t => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  function search(m, text) {
    const t = norm(text.trim());
    return t.length < 2 ? [] : m.data.players.filter(p => norm(p.name).includes(t)).slice(0, MAX_HITS);
  }

  function hitsHtml(m, st, hits, at) {
    const inCore = new Set(st.core);
    return hits.map((p, i) => `<li role="option" id="hit-${i}" aria-selected="${i === at}"><button type="button" tabindex="-1" data-pick="${esc(p.id)}"${i === at ? ' class="on"' : ""}>` +
      `<b>${esc(p.name)}</b><span>${esc(p.team)} · ${esc(pos(p))} · ${esc(owner(p))}${inCore.has(p.id) ? " · in core" : ""}</span>` +
      `<em>${valText(p)}</em></button></li>`).join("");
  }

  // Add a player to the core. A player who is not yours goes on the added list too.
  function pick(m, st, id) {
    if (!st.core.includes(id)) st.core.push(id);
    if (!m.byId[id].mine && !st.added.includes(id)) st.added.push(id);
  }

  // The state of the page at open: the saved state if it is valid, else the best core.
  function open(m, saved) {
    const st = newState(m);
    if (saved && Array.isArray(saved.core)) {
      const known = l => (Array.isArray(l) ? l.filter(id => m.byId[id]) : []);
      st.n = Number.isInteger(saved.n) && saved.n > 0 ? saved.n : st.n;
      st.core = known(saved.core);
      st.added = known(saved.added);
      st.rest = Object.fromEntries(Object.entries(saved.rest || {}).filter(([id]) => m.byId[id]));
      st.saved = saved.saved || null;
    } else {
      st.core = bestCore(m, st, st.n);
    }
    return st;
  }

  // Reset (chief of staff choice of 2026-11-01): the best core of n players, with no added players and no R switches.
  function reset(m, st) {
    st.added = [];
    st.rest = {};
    st.saved = null;
    st.core = bestCore(m, st, st.n);
  }

  const savedText = st => {
    if (!st.saved) return "Not saved";
    const d = new Date(st.saved);
    return `Saved ${WEEKDAY[d.getDay()]} ${d.getMonth() + 1}/${d.getDate()}`;
  };

  // The HTML of each part of the page for a state.
  function view(m, st) {
    const sc = score(m, st);
    return {
      stats: headline(m, st, sc), weeks: weeksTable(m, sc), floor: floorView(m, st, floor(m, st)), grid: grid(m, st, sc), phone: phone(m, st, sc),
      players: players(m, st), swaps: swapList(m, st), reset: `Reset to best ${st.n}`, saved: savedText(st), score: sc,
    };
  }

  // The page in the browser: draw the view, and change the state on each control.
  function start(doc, data) {
    const m = model(data), $ = id => doc.getElementById(id), store = data.key;
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(store) || "null"); } catch (e) { saved = null; }
    const st = open(m, saved);
    const max = Math.max(1, m.mine.length);
    $("n").max = max;

    function draw() {
      const v = view(m, st);
      $("stats").innerHTML = v.stats;
      $("wk").innerHTML = v.weeks;
      $("fl").innerHTML = v.floor;
      $("grid").innerHTML = v.grid;
      $("mob").innerHTML = v.phone;
      $("pt").innerHTML = v.players;
      $("sw").innerHTML = v.swaps;
      $("reset").textContent = v.reset;
      $("saved").textContent = v.saved;
      $("n").value = st.n;
    }

    $("n").addEventListener("change", () => {
      st.n = Math.max(1, Math.min(max, parseInt($("n").value, 10) || data.core));
      st.core = bestCore(m, st, st.n);
      draw();
    });
    $("reset").addEventListener("click", () => {
      reset(m, st);
      try { localStorage.removeItem(store); } catch (e) { /* the browser blocks storage */ }
      draw();
    });
    $("save").addEventListener("click", () => {
      st.saved = new Date().toISOString();
      try {
        localStorage.setItem(store, JSON.stringify({ n: st.n, core: st.core, added: st.added, rest: st.rest, saved: st.saved }));
      } catch (e) {
        st.saved = null;
        $("saved").textContent = "Not saved: this browser blocks storage";
        return;
      }
      $("saved").textContent = savedText(st);
    });
    doc.addEventListener("click", e => {
      const r = e.target.closest("[data-rest]"), x = e.target.closest("[data-drop]");
      if (r) {
        const id = r.dataset.rest, now = !isRest(m, st, id);
        if (now === !!m.byId[id].rests_b2b) delete st.rest[id]; else st.rest[id] = now;
        draw();
      }
      if (x) {
        const id = x.dataset.drop;
        st.core = st.core.filter(c => c !== id);
        st.added = st.added.filter(c => c !== id);
        draw();
      }
    });
    $("sw").addEventListener("click", e => {
      const c = e.target.closest("[data-filter]"), tr = e.target.closest("tr[data-swap]"), rk = e.target.closest("[data-rank]");
      if (rk) {
        st.rank = rk.dataset.rank;
        $("sw").innerHTML = swapList(m, st);
      } else if (c) {
        st.filter = c.dataset.filter;
        $("sw").innerHTML = swapList(m, st);
      } else if (tr && !e.target.closest("a")) {
        swap(m, st, tr.dataset.swap, tr.dataset.out);
        draw();
      }
    });
    $("sw").addEventListener("keydown", e => {
      const tr = e.target.closest("tr[data-swap]");
      if (tr && e.target === tr && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        swap(m, st, tr.dataset.swap, tr.dataset.out);
        draw();
      }
    });
    doc.addEventListener("change", e => {
      const c = e.target.closest("[data-core]");
      if (!c) return;
      const id = c.dataset.core;
      st.core = c.checked ? [...st.core, id] : st.core.filter(x => x !== id);
      draw();
    });

    const q = $("q"), res = $("res");
    let hits = [], at = -1;
    function showHits() {
      hits = search(m, q.value);
      at = hits.length ? 0 : -1;
      res.hidden = !hits.length;
      q.setAttribute("aria-expanded", String(!!hits.length));
      res.innerHTML = hitsHtml(m, st, hits, at);
      if (at >= 0) q.setAttribute("aria-activedescendant", "hit-0"); else q.removeAttribute("aria-activedescendant");
    }
    function choose(id) {
      pick(m, st, id);
      q.value = "";
      showHits();
      draw();
    }
    q.addEventListener("input", showHits);
    q.addEventListener("keydown", e => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!hits.length) return;
        e.preventDefault();
        at = (at + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length;
        [...res.querySelectorAll("button")].forEach((b, i) => {
          b.classList.toggle("on", i === at);
          b.parentNode.setAttribute("aria-selected", String(i === at));
        });
        q.setAttribute("aria-activedescendant", `hit-${at}`);
      } else if (e.key === "Enter" && at >= 0) {
        e.preventDefault();
        choose(hits[at].id);
      } else if (e.key === "Escape") {
        q.value = "";
        showHits();
      }
    });
    res.addEventListener("click", e => { const b = e.target.closest("[data-pick]"); if (b) choose(b.dataset.pick); });
    draw();
  }

  return { floor, floorSwaps, model, newState, open, reset, bestCore, score, lightNights, addsOf, swaps, swap, search, pick, view, start };
})();

if (typeof module !== "undefined") module.exports = Playoffs;
