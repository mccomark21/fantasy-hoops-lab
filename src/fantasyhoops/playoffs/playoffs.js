// The Playoffs page (#214): the value started of your playoff core, in the browser.
//
// playoffs/page.py inlines core/starts.js, then this file, then start(). The page data is the JSON of page_data()
// in playoffs/page.py. valueStarted() of core/starts.js gives each number of the page. This file has no lineup math.
// The part before start() has no DOM code, so Node loads the file with require() and tests the HTML of the page
// (tests/playoffs/test_page.py). Node loads core/starts.js itself.
//
// The state of the page: {n, core, added, rest, saved}.
//   n: the core size. core: the ids of the core players. added: the ids of the players that the search added.
//   rest: {id: true or false}, the R switches that differ from rests_b2b of the player file.
//   saved: the time of the last save (ISO), or null.
// Save keeps the state in localStorage (data.key). Reset clears the added players, the R switches and the save.

const Playoffs = (() => {
  const S = typeof Starts !== "undefined" ? Starts : require("../core/starts.js");
  const LETTER = ["S", "M", "T", "W", "T", "F", "S"];
  const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MARK_TEXT = { s: "starts", b: "game, sits", r: "rests on back-to-back", n: "no game" };
  const MAX_HITS = 8; // the search shows this many players at most

  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const f1 = v => (v < -0.05 ? "−" : "") + Math.abs(v).toFixed(1);
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
    return { n: m.data.core, core: [], added: [], rest: {}, saved: null };
  }

  const isRest = (m, st, id) => (id in st.rest ? st.rest[id] : !!m.byId[id].rests_b2b);

  // valueStarted() of the players ids. The R switches of the state give the rester set.
  function score(m, st, ids = st.core) {
    return S.valueStarted(ids.map(id => m.byId[id]), m.engine, ids.filter(id => isRest(m, st, id)));
  }

  // The best core of n players (decision 11): your n players with the highest value started alone.
  function bestCore(m, st, n) {
    const solo = Object.fromEntries(m.mine.map(id => [id, score(m, st, [id]).total.value]));
    return m.mine.slice().sort((a, b) => solo[b] - solo[a]).slice(0, n);
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
  const playDays = (m, week) => m.data.days.filter(d => (week === null || d.week === week) && d.teams.length).length;
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
      `<div><dt>Starts</dt><dd>${t.starts}</dd></div>`
    );
  }

  // The totals of each week, then the total.
  function weeksTable(m, sc) {
    const row = (label, w, cls) =>
      `<tr${cls ? ` class="${cls}"` : ""}><th class="l" scope="row">${label}</th><td>${f1(w.value)}</td>` +
      `<td>${w.starts}</td><td>${w.lost}</td><td>${w.open_heavy}</td><td>${w.open_light}</td></tr>`;
    return (
      '<thead><tr><th class="l" scope="col">Week</th><th scope="col">Value started</th><th scope="col">Starts</th>' +
      '<th scope="col">Lost</th><th scope="col">Open heavy</th><th scope="col">Open light</th></tr></thead><tbody>' +
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
      `<tr class="st"><th class="lab" colspan="2" scope="row">Starts</th>${weekTotals((t, w) => `${t.starts}<small>of ${playDays(m, w) * slots}</small>`)}` +
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
      `<dl>${weekDl((t, w) => `${t.starts}<small>of ${playDays(m, w) * slots}</small>`)}</dl>` +
      `<p class="ul">Open slots</p><dl class="u">${weekDl(t => `<b>${t.open_heavy + t.open_light}</b><small>${t.open_light} light</small>`)}</dl>` +
      `<div class="m-row hd">${head}</div>` +
      row(`Starts each day, of ${slots}`, (d, i) => (d.teams.length ? sc.days[i].starts : "")) +
      row("Open slots each day", (d, i) => sc.days[i].open || "") +
      row("NBA games", d => d.games) + "</div>";
    return h;
  }

  // The columns of the Players table: the class of each <col>. The colgroup and the separator rows use this list.
  // #215 adds the Adds column here.
  const PLAYER_COLS = ["c-in", "", "c-v", "c-q", "c-r", "c-x"];

  // The Players table: the core, then the players outside the core (your other players and the added players).
  // #215 adds the Adds column and the weakest-link flag here.
  function players(m, st) {
    const inCore = new Set(st.core);
    const listed = [...new Set([...st.core, ...m.mine, ...st.added])];
    const byVal = l => l.sort((a, b) => m.byId[b].value - m.byId[a].value);
    const coreRows = byVal(st.core.slice()), outRows = byVal(listed.filter(id => !inCore.has(id)));
    const row = (id, inside) => {
      const p = m.byId[id], r = isRest(m, st, id);
      return `<tr class="${inside ? "in" : "out"}"><td><input type="checkbox" data-core="${esc(id)}"${inside ? " checked" : ""} aria-label="${esc(p.name)} in the core"></td>` +
        `<th scope="row"><b>${link(p)}</b>${restTag(m, st, id)}<small>${esc(p.team)} · ${esc(pos(p))} · ${esc(owner(p))}</small></th>` +
        `<td>${valText(p)}${projTag(p)}</td><td>${lightNights(m, st, id)}</td>` +
        `<td><button type="button" class="rb" data-rest="${esc(id)}" aria-pressed="${r}" aria-label="${esc(p.name)} rests on back-to-backs" title="Rests on back-to-backs">R</button></td>` +
        `<td>${p.mine ? "" : `<button type="button" class="x" data-drop="${esc(id)}" aria-label="Remove ${esc(p.name)} from the page" title="Remove">×</button>`}</td></tr>`;
    };
    const cols = PLAYER_COLS.map(c => (c ? `<col class="${c}">` : "<col>")).join("");
    return (
      `<colgroup>${cols}</colgroup>` +
      '<thead><tr><th scope="col" class="l"><span class="vh">In core</span></th><th scope="col" class="l">Player</th>' +
      '<th scope="col">Val</th><th scope="col" title="Games on light nights">Light</th><th scope="col" title="Rests on back-to-backs">R</th>' +
      '<th scope="col"><span class="vh">Remove</span></th></tr></thead><tbody>' +
      `<tr class="sep"><td colspan="${PLAYER_COLS.length}">Core · ${coreRows.length}</td></tr>` + coreRows.map(id => row(id, true)).join("") +
      `<tr class="sep"><td colspan="${PLAYER_COLS.length}">Outside the core · ${outRows.length}</td></tr>` + outRows.map(id => row(id, false)).join("") +
      "</tbody>"
    );
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
      stats: headline(m, st, sc), weeks: weeksTable(m, sc), grid: grid(m, st, sc), phone: phone(m, st, sc),
      players: players(m, st), reset: `Reset to best ${st.n}`, saved: savedText(st), score: sc,
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
      $("grid").innerHTML = v.grid;
      $("mob").innerHTML = v.phone;
      $("pt").innerHTML = v.players;
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

  return { model, newState, open, reset, bestCore, score, lightNights, search, pick, view, start };
})();

if (typeof module !== "undefined") module.exports = Playoffs;
