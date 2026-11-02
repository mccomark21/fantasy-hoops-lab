// The League page (#218): the playoff value, the starts and the open slots of each team, in the browser.
//
// league/page.py inlines core/starts.js, then this file, then start(). The page data is the JSON of page_data() in
// league/page.py. valueStarted(), bestCore() and streamFill() of core/starts.js give each lineup number. This file
// has no lineup math. weekTotals() and weekRanks() give the numbers of each week, the vulnerable flag and the
// reasons (#229). This file only adds the stream value (stream games x v) and the totals.
// The part before start() has no DOM code, so Node loads the file with require() and tests the rows and the HTML
// (tests/league/test_page.py). Node loads core/starts.js itself.
//
// The core of each team (owner decision 1 of 2026-11-02): the best data.core players by value started alone. Your
// row uses the core that you saved on the Playoffs page (localStorage data.key) and its R switches, else your best
// core.

const League = (() => {
  const S = typeof Starts !== "undefined" ? Starts : require("../core/starts.js");
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const f1 = x => (Math.round(x * 10) / 10).toFixed(1);
  const f2 = x => (Math.round(x * 100) / 100).toFixed(2);
  const pct = x => `${Math.round(x * 100)}%`;
  const COLS = [
    ["team", "Team", "l"], ["record", "Record", ""], ["core", "Core", ""], ["perCore", "Val / core", ""],
    ["stream", "Stream value", ""], ["total", "Total", ""], ["weeks", "Week rank", "wkc"], ["volume", "Volume", "wkc"],
    ["vps", "Value / start", "wkc"], ["starts", "Starts", ""], ["heavy", "Open heavy", ""],
    ["light", "Open light", ""], ["games", "Stream games", ""], ["rate", "Fill rate", ""],
  ];
  // The description of each column header (#227), with the numbers of the run. Team and Record have none. The
  // header tooltip and the "Column meanings" list show the same text.
  function notes(data) {
    const slots = data.slots.length + data.util, b = data.quality_bonus || 0;
    const b1 = String(Number((1 + b).toFixed(4))), more = `${Math.round(b * 100)}%`;
    const n = Object.keys(teams(data)).length, [lo, hi] = data.weak.band;
    return {
      core: `The number of core players: the best ${data.core} by value started, or your core saved on the ` +
        "Playoffs page. The saved core is in this browser only.",
      perCore: `Value started ÷ core players. Value started is the Val of the core starts in ${slots} slots, ` +
        "with the Season Val, else the projection Val (proj tag).",
      stream: `Stream games × v. v = ${f2(data.v)}, the mean Val of the top ${data.v_count} free agents.`,
      total: "Value started + stream value. The # column is the rank by Total.",
      weeks: `The rank of ${n} of each week's Total, weeks ${wkNames(data)} from the left. A red week is ` +
        `vulnerable: rank ${lo} to ${hi} and at least ${Math.round(data.weak.below * 100)}% ` +
        `below the team's mean week. "Weak all 3 weeks": rank ${lo} to ${hi} in each week.`,
      volume: "The games started in each week: core starts + stream starts (the slots of all the game days of the " +
        "week − the unused slots). The shade is the rank of the week.",
      vps: "Each week's Total ÷ Volume. Total = Volume × Value / start. The shade is the rank of the week.",
      starts: "The started core games / the core games (starts + starts lost).",
      heavy: "The open slots on heavy nights that the streams fill / the open slots on heavy nights. An open slot " +
        "is an empty starting slot.",
      light: "The open slots on light nights that the streams fill / the open slots on light nights. A light " +
        `night has ${data.light_games} or fewer NBA games.`,
      games: `Filled heavy + filled light × ${b1}. A light night counts ${more} more.`,
      rate: `Stream games ÷ (open heavy + open light × ${b1}).`,
    };
  }

  // The "Column meanings" list (#227): a <dt> and a <dd> for each column of notes(). The id of each <dd> is the
  // aria-describedby target of its header button.
  function defs(data) {
    const text = notes(data);
    return COLS.filter(([k]) => text[k]).map(([k, label]) =>
      `<dt>${esc(label)}</dt><dd id="lg-d-${k}">${esc(text[k])}</dd>`).join("");
  }

  // The columns that sort from low to high first. All other columns sort from high to low first.
  const UP = new Set(["team", "weeks"]);
  const wkNum = w => w.replace(/\D/g, "");
  const wkNames = data => data.weeks.map(wkNum).join(", ");

  // The engine data of core/starts.js.
  function engine(data) {
    return {
      slots: data.slots, util: data.util, weeks: data.weeks, quality_bonus: data.quality_bonus,
      days: data.days.map(d => ({ date: d.date, week: d.week, quality: d.quality, teams: d.teams, b2b: d.b2b })),
    };
  }

  // The rostered players of each team: {team name: [players]}, in the order of the player file.
  function teams(data) {
    const by = {};
    for (const p of data.players) if (p.owner) (by[p.owner] = by[p.owner] || []).push(p);
    return by;
  }

  // The win share of a record "W-L-T" for the sort: (W + T / 2) / games. No record: -1.
  function share(record) {
    if (!record) return -1;
    const [w, l, t] = record.split("-").map(Number), n = w + l + t;
    return n ? (w + t / 2) / n : 0;
  }

  // A row of the table. core: the core players. roster: the rostered players of the team. resters: as in
  // valueStarted(), or undefined for rests_b2b of the player file. source: "saved" or "best".
  function row(data, eng, team, roster, core, resters, source) {
    const spots = Math.max(0, data.roster_spots - core.length);
    // weekTotals() gives the valueStarted() and streamFill() results too (#229), so the row computes them one time.
    const wt = S.weekTotals(core, eng, { spots, adds: data.adds, resters, v: data.v, few: data.weak.few });
    const t = wt.started, fill = wt.fill;
    const stream = fill.games * data.v, total = t.total.value + stream, inCore = new Set(core.map(p => p.id));
    const starts = {};
    for (const p of core) starts[p.id] = t.marks[p.id].filter(k => k === "s").length;
    const record = (data.records || {})[team] || null;
    return {
      team, record, share: share(record), source, mine: roster.some(p => p.mine), core: core.length, spots,
      value: t.total.value, perCore: core.length ? t.total.value / core.length : 0, stream, total,
      starts: t.total.starts, games_core: t.total.games, lost: t.total.lost,
      heavy: fill.heavy, light: fill.light, open_heavy: fill.open_heavy, open_light: fill.open_light,
      games: fill.games, rate: fill.rate, unused: fill.unused, adds: fill.adds,
      wk: wt.weeks, volume: wt.volume, vps: wt.vps,
      players: core.slice().sort((a, b) => b.value - a.value).map(p => ({ ...p, starts: starts[p.id] })),
      out: roster.filter(p => !inCore.has(p.id)).sort((a, b) => b.value - a.value),
    };
  }

  // The rows of all teams. saved: the saved state of the Playoffs page (localStorage data.key), or null.
  function rows(data, saved) {
    const list = teamRows(data, saved);
    // The weekly ranks, the vulnerable flag and the weakest week (#229). The sort key of Week rank: the worst rank,
    // and the teams that are weak all 3 weeks last.
    S.weekRanks(list.map(r => ({ weeks: r.wk })), data.weeks, data.weak).forEach((k, i) => {
      const r = list[i];
      for (const w of data.weeks) Object.assign(r.wk[w], k.weeks[w]);
      Object.assign(r, { weakAll: k.weakAll, weakest: k.weakest, weeks: k.worst + (k.weakAll ? 100 : 0) });
    });
    return list;
  }

  function teamRows(data, saved) {
    const eng = engine(data), byId = Object.fromEntries(data.players.map(p => [p.id, p]));
    return Object.entries(teams(data)).map(([team, roster]) => {
      if (roster.some(p => p.mine) && saved && Array.isArray(saved.core)) {
        const ids = saved.core.filter(id => byId[id]);
        if (ids.length) {
          const rest = saved.rest || {};
          const resters = ids.filter(id => (id in rest ? !!rest[id] : !!byId[id].rests_b2b));
          return row(data, eng, team, roster, ids.map(id => byId[id]), resters, "saved");
        }
      }
      return row(data, eng, team, roster, S.bestCore(roster, eng, data.core), undefined, "best");
    });
  }

  // {team: rank by Total}, 1 for the highest Total.
  function ranks(list) {
    const out = {};
    list.slice().sort((a, b) => b.total - a.total).forEach((r, i) => { out[r.team] = i + 1; });
    return out;
  }

  // The sort of the table. st: {key, dir}. dir -1: high to low.
  function sorted(list, st) {
    const k = st.key;
    return list.slice().sort((a, b) => {
      if (k === "team") return st.dir * a.team.localeCompare(b.team);
      const key = k === "record" ? "share" : k;
      return st.dir * (a[key] - b[key]) || b.total - a.total;
    });
  }

  // The shade of a rank (#229), from 34% mark (rank 1) to none (the last rank).
  const shade = (rank, n) => `--t:${Math.round(34 * (n - rank) / Math.max(1, n - 1))}%`;

  // A week strip (#229): one box for each week. k: "weeks" (the rank of the Total), "volume" or "vps".
  function strip(data, r, k, n) {
    const fmt = k === "vps" ? f2 : String;
    const boxes = data.weeks.map(w => {
      const x = r.wk[w], rank = x[k === "weeks" ? "r_total" : "r_" + k], val = k === "weeks" ? x.r_total : fmt(x[k]);
      const red = k === "weeks" && x.vulnerable;
      const what = k === "weeks" ? `Total ${f1(x.total)}` : k === "volume" ? `${x.volume} games started` : `${f2(x.vps)} a start`;
      const tip = `Week ${wkNum(w)}: rank ${rank} of ${n}, ${what}${x.vulnerable ? `, vulnerable (${Math.round(x.below * 100)}% below the mean week)` : ""}`;
      return `<span class="wb${red ? " vul" : ""}" style="${shade(rank, n)}" title="${esc(tip)}">${val}</span>`;
    }).join("");
    const lab = k === "weeks" && r.weakAll ? '<em class="weak3">weak all 3 weeks</em>' : "";
    return `<span class="ws">${boxes}</span>${lab}`;
  }

  function cell(r, k, data, n) {
    if (k === "weeks" || k === "volume" || k === "vps") return strip(data, r, k, n);
    if (k === "record") return r.record ? esc(r.record) : '<span class="mute" title="Not in the standings">—</span>';
    if (k === "perCore" || k === "stream" || k === "total" || k === "games") return f1(r[k]);
    if (k === "rate") return pct(r.rate);
    if (k === "starts") return `${r.starts}<small>/ ${r.games_core}</small>`;
    if (k === "heavy") return `${r.heavy}<small>/ ${r.open_heavy}</small>`;
    if (k === "light") return `${r.light}<small>/ ${r.open_light}</small>`;
    return String(r[k]);
  }

  // The reasons of a week (#229), from weekTotals(): the core players with few starts, the starts lost on crowded
  // nights (lost_by) and the open slots that the streams cannot fill. main: the text of the main cause.
  function why(r, w) {
    const x = r.wk[w], items = [];
    if (x.few.length) {
      items.push("Few starts: " + x.few.map(p => `${esc(p.name)} ${p.starts} of ${p.games} games` +
        (p.rested ? `, ${p.rested} rest` : "")).join("; "));
    }
    const by = Object.entries(x.lost_by).sort((a, b) => b[1] - a[1]);
    if (x.lost) items.push(`${x.lost} starts lost on crowded nights: ${by.map(([n, c]) => `${esc(n)} ${c}`).join(", ")}`);
    if (x.unused) items.push(`${x.unused} open slots the streams cannot fill (they fill ${x.filled} of ${x.open}, ` +
      `${r.spots} stream spots, ${x.adds} adds)`);
    const main = x.main === "unused" ? `${x.unused} open slots the streams cannot fill`
      : x.main === "lost" ? `${x.lost} starts lost on crowded nights` : "";
    return { items, main };
  }

  function weekDetail(data, r, n) {
    return '<div class="why">' + data.weeks.map(w => {
      const x = r.wk[w], y = why(r, w);
      const flag = x.vulnerable ? ' <i class="tag vul">vulnerable</i>' : "";
      return `<section><h4>Week ${wkNum(w)}${flag}</h4><p>Total <b>${f1(x.total)}</b>, rank ${x.r_total} of ${n} · ` +
        `Volume ${x.volume} (rank ${x.r_volume}) × ${f2(x.vps)} a start (rank ${x.r_vps})</p>` +
        (y.items.length ? `<ul>${y.items.map(i => `<li>${i}</li>`).join("")}</ul>` : '<p class="mute">No lost starts and no unused slots.</p>') +
        "</section>";
    }).join("") + "</div>";
  }

  function detail(data, r, n) {
    const li = p => `<li><b>${esc(p.name)}</b> <span>${esc(p.team)} · ${esc(p.pos.join("/") || "Util")}` +
      `${!p.owner ? " · FA" : p.owner !== r.team ? " · " + esc(p.owner) : ""}</span>` +
      `<em>${f2(p.value)}${p.mark === "proj" ? '<i class="tag">proj</i>' : ""}</em><span class="s">${p.starts} st</span></li>`;
    const out = r.out.length
      ? `<p class="outp"><b>Outside the core:</b> ${r.out.map(p => `${esc(p.name)} ${f2(p.value)}`).join(", ")}</p>` : "";
    const v = f2(data.v), b = (1 + (data.quality_bonus || 0)).toFixed(1);
    return `<tr class="det"><td colspan="${COLS.length + 1}"><div><p class="dl">Value started <b>${f1(r.value)}</b> · ` +
      `${r.core} core players (${r.source === "saved" ? "your saved Playoffs core" : "best " + data.core}) · ${r.lost} starts lost · ` +
      `${r.spots} stream spots, ${r.adds} adds used · stream value = (${r.heavy} heavy + ${r.light} light × ${b}) × ${v} = ` +
      `${f1(r.stream)} · ${r.unused} unused slots</p>${weekDetail(data, r, n)}<ol class="cp">${r.players.map(li).join("")}</ol>${out}</div></td></tr>`;
  }

  // The HTML of the table and of the summary for the rows and the state st: {key, dir, open}.
  function view(data, list, st) {
    const rk = ranks(list), mine = list.find(r => r.mine), text = notes(data);
    const head = '<thead><tr><th class="l rkh" scope="col">#</th>' + COLS.map(([k, label, c]) => {
      const sort = st.key === k ? (st.dir < 0 ? "descending" : "ascending") : "none";
      const arrow = sort === "none" ? "" : sort === "descending" ? "▼" : "▲";
      const desc = text[k] ? ` aria-describedby="lg-d-${k}"` : "";
      return `<th scope="col" class="${c}" aria-sort="${sort}"><button type="button" data-k="${k}"${desc}>${label}` +
        `<i aria-hidden="true">${arrow}</i></button></th>`;
    }).join("") + "</tr></thead>";
    const body = sorted(list, st).map(r => {
      const open = st.open === r.team;
      const tr = `<tr class="${r.mine ? "mine" : ""}${open ? " on" : ""}" data-t="${esc(r.team)}" tabindex="0" ` +
        `aria-expanded="${open}"><td class="rk">${rk[r.team]}</td>` +
        COLS.map(([k]) => (k === "team"
          ? `<th scope="row" class="tm"><b>${esc(r.team)}</b>${r.mine ? '<em class="tag you">You</em>' : ""}</th>`
          : `<td class="${k}">${cell(r, k, data, list.length)}</td>`)).join("") + "</tr>";
      return tr + (open ? detail(data, r, list.length) : "");
    }).join("");
    const sum = !mine ? "" :
      `<div class="hero"><dt>Your rank</dt><dd>${rk[mine.team]}<small>of ${list.length} by Total</small></dd></div>` +
      `<div><dt>Your core</dt><dd>${mine.core}<small>${mine.source === "saved" ? "saved on Playoffs" : "best " + data.core + ", none saved"}</small></dd></div>` +
      `<div><dt>Your streams fill</dt><dd>${mine.heavy + mine.light}<small>of ${mine.open_heavy + mine.open_light} open slots</small></dd></div>` +
      `<div><dt>v</dt><dd>${f2(data.v)}<small>mean Val of the top ${data.v_count} free agents</small></dd></div>`;
    return { table: head + "<tbody>" + body + "</tbody>", sum, header: header(list) };
  }

  // The header above the table (owner decision of 2026-11-02 on #218): the rank and the league median of your core
  // starts (the Starts column) and of your filled heavy-night open slots. rankMedian() of core/starts.js.
  // The third line (#229): your weakest week, the week with your worst rank of the Total (weekRanks()), and its
  // main cause.
  function header(list) {
    const mine = list.find(r => r.mine);
    if (!mine) return "";
    const line = (label, key) => {
      const r = S.rankMedian(list.map(x => x[key]), mine[key]);
      const med = Number.isInteger(r.median) ? String(r.median) : r.median.toFixed(1);
      return `<li><b>${label}:</b> rank ${r.rank} of ${r.of} (league median ${med})</li>`;
    };
    const w = mine.weakest, x = mine.wk[w], cause = why(mine, w).main;
    const weakest = `<li><b>Your weakest week:</b> week ${wkNum(w)}, rank ${x.r_total} of ${list.length}` +
      `${cause ? `. Main cause: ${cause}` : ""}</li>`;
    return line("Core starts", "starts") + line("Filled heavy", "heavy") + weakest;
  }

  const faList = data => data.v_players.map(p => `${p.name} ${f2(p.value)}`).join(", ");

  // The header tooltip (#227, DESIGN.md "Tooltips"): one card #lg-tt, fixed to the viewport. A mouse shows it on
  // enter and hides it on leave. A keyboard focus shows it. A click or Escape hides it. A scroll hides it, but the card
  // of the header that has the keyboard focus moves with the header (a focus can scroll the table). The card goes 12px below
  // the header, else 12px above it, and stays 8px inside the viewport. Phones use the "Column meanings" list.
  function bindTips(doc, tbl, data) {
    const tip = doc.getElementById("lg-tt"), text = notes(data), win = doc.defaultView;
    let cur = null; // the header button of the card that shows, or null
    const hide = () => { tip.hidden = true; cur = null; };
    function show(b) {
      const k = b.dataset.k;
      if (!text[k]) return hide();
      cur = b;
      const label = COLS.find(c => c[0] === k)[1];
      tip.innerHTML = `<div class="lg-tt-h">${esc(label)}</div><p>${esc(text[k])}</p>`;
      tip.hidden = false;
      const r = b.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
      const vw = doc.documentElement.clientWidth, vh = win.innerHeight;
      let top = r.bottom + 12;
      if (top + h > vh - 8) top = Math.max(8, r.top - 12 - h);
      const left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, vw - 8 - w));
      tip.style.left = `${left}px`;
      tip.style.top = `${top}px`;
    }
    const button = ev => ev.target.closest && ev.target.closest("thead button[data-k]");
    tbl.addEventListener("pointerover", ev => { const b = button(ev); if (b && ev.pointerType === "mouse") show(b); });
    tbl.addEventListener("pointerout", ev => {
      const b = button(ev);
      // A scroll under a still mouse also sends pointerout. Only the header of the card hides it, and only with no focus.
      if (b && b === cur && b !== doc.activeElement && !(ev.relatedTarget && b.contains(ev.relatedTarget))) hide();
    });
    tbl.addEventListener("focusin", ev => { const b = button(ev); if (b && b.matches(":focus-visible")) show(b); });
    tbl.addEventListener("focusout", hide);
    tbl.addEventListener("click", hide, true);
    doc.addEventListener("keydown", ev => { if (ev.key === "Escape") hide(); });
    // A scroll keeps the card of a header with the keyboard focus, at the new place of the header. A scroll under a
    // still mouse can send pointerover to another header, so the focused header wins.
    win.addEventListener("scroll", () => {
      const f = doc.activeElement;
      if (cur && f && tbl.contains(f) && f.matches("thead button[data-k]:focus-visible")) show(f);
      else hide();
    }, true);
  }

  // The page in the browser: draw the view, and change the sort or the open team on each click.
  function start(doc, data) {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(data.key) || "null"); } catch (e) { saved = null; }
    const list = rows(data, saved), st = { key: "total", dir: -1, open: null }, tbl = doc.getElementById("lg");
    function draw() {
      const v = view(data, list, st);
      tbl.innerHTML = v.table;
      doc.getElementById("sum").innerHTML = v.sum;
      doc.getElementById("ranks").innerHTML = v.header;
    }
    tbl.addEventListener("click", ev => {
      const b = ev.target.closest("button[data-k]");
      if (b) {
        const k = b.dataset.k;
        if (st.key === k) st.dir = -st.dir;
        else { st.key = k; st.dir = UP.has(k) ? 1 : -1; }
        draw();
        tbl.querySelector(`button[data-k="${k}"]`).focus();
        return;
      }
      const tr = ev.target.closest("tr[data-t]");
      if (tr) { st.open = st.open === tr.dataset.t ? null : tr.dataset.t; draw(); }
    });
    tbl.addEventListener("keydown", ev => {
      const tr = ev.target.closest("tr[data-t]");
      if (tr && ev.target === tr && (ev.key === "Enter" || ev.key === " ")) {
        ev.preventDefault();
        const t = tr.dataset.t;
        st.open = st.open === t ? null : t;
        draw();
        tbl.querySelector(`tr[data-t="${CSS.escape(t)}"]`).focus();
      }
    });
    doc.getElementById("fa-list").textContent = faList(data);
    doc.getElementById("lg-defs").innerHTML = defs(data);
    bindTips(doc, tbl, data);
    draw();
  }

  return { COLS, notes, defs, engine, teams, share, row, rows, ranks, sorted, header, view, faList, start };
})();

if (typeof module !== "undefined") module.exports = League;
