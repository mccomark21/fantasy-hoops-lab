"""The Value and Comps quadrants of the player card in the browser (#189).

players/value.py draws the Value chart and players/comps.py finds the comps. Both write their data into the shared
player file. profile.FILLS lists this module, so profile.modal() adds STYLE and script(), and the methods note gets
METHODS (a Value line and a Comps line).
- LabCard.fill.value puts the chart, the dud and spike counts and the state line into the quadrant.
- LabCard.fill.comps draws the comps table. A comp links to his own record in the file by slug.
- Each game column and each comps row has the class lab-c-hit and shows its tooltip card with LabCard.bindTip()
  (core/profile.py). A game column also shows the crosshair of DESIGN.md "Tooltips" with LabCard.bindCrosshair().
The module writes no files.
"""

STYLE = """/* The Value and Comps quadrants (issue 189). The quadrant label (.lc-lab) has its rule in core/card_cats.py. */
.lab-card .lc-q h3 .lc-lab b { color: var(--lab-ink); font-weight: 800; }
.lab-card .lc-value .lab-c-state, .lab-card .lc-comps-q .lab-c-state { margin: 2px 0 0; }
.lab-card table.lc-comps { width: 100%; margin-top: 4px; border-collapse: collapse; table-layout: fixed;
  font-variant-numeric: tabular-nums; }
.lab-card .lc-comps col.c-band { width: 40px; }
.lab-card .lc-comps col.c-v { width: 54px; }
.lab-card .lc-comps col.c-d { width: 92px; }
.lab-card .lc-comps thead th { padding: 0 6px 6px; border-bottom: 2px solid var(--mark); color: var(--mark);
  font-size: 11px; font-weight: 800; text-align: right; vertical-align: bottom; }
.lab-card .lc-comps thead .l { text-align: left; }
.lab-card .lc-comps tbody td, .lab-card .lc-comps tbody th { height: 44px; padding: 0 6px;
  border-bottom: 1px solid var(--lab-rule); font-weight: 400; text-align: right; vertical-align: middle; }
.lab-card .lc-comps tbody tr:nth-child(even) > * { background: var(--zebra); }
.lab-card .lc-comps td.band { padding: 0; border-bottom: 1px solid var(--lab-stock); background: var(--team) !important;
  color: var(--team-ink); font-weight: 900; font-stretch: 70%; font-size: 15px; text-align: center; }
.lab-card .lc-comps th.pl { padding: 3px 6px 3px 10px; line-height: 1; text-align: left; }
.lab-card .lc-comps .pl b { font-weight: 900; font-stretch: 66%; font-size: 17px; line-height: 1;
  text-transform: uppercase; }
.lab-card .lc-comps .pl small { display: block; margin-top: 2px; overflow: hidden; color: var(--lab-mute);
  font-size: 12px; line-height: 1.2; text-overflow: ellipsis; white-space: nowrap; }
.lab-card .lc-comps td.n { font-size: 14px; }
.lab-card .lc-comps td.n b { font-weight: 800; }
.lab-card .lc-comps tbody tr { cursor: default; }
.lab-card .lc-comps tbody tr:hover > *, .lab-card .lc-comps tbody tr:focus > * { background: var(--qcol); }
.lab-card .lc-comps tbody tr:focus { outline: 2px solid var(--lab-ink); outline-offset: -2px; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .lab-card .lc-comps td.band {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }
}
:root[data-theme="dark"] .lab-card .lc-comps td.band {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }"""

# The Value and Comps lines of the methods note (the "i" icon). The JS function gives "" for a file with no Value meta.
METHODS = r"""(p, d) => {
  const m = d.meta.value, sgn = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(2);
  if (!m) return "";
  return `<li><b>Value.</b> The value of each ESPN game above the replacement free agent, on the scale of Val. `
    + `Dud: below 0. Spike: ${m.spike == null ? "–" : sgn(m.spike)} or more (the Val of the player at rank ${m.spike_rank}). `
    + `Range: the season mean ± ${m.band_sd} SD / √${m.window}. The SD mixes his own SD with a league SD`
    + `${m.league_sd == null ? "" : ` (${m.league_sd.toFixed(2)})`} worth ${m.prior_games} games. `
    + `A range needs ${m.band_min} games, a flag ${m.flag_min}. Signal: duds or spikes in `
    + `${Math.round(m.rate_flag * 100)}% or more of ${m.consistency_min_games} or more games.</li>`
    + "<li><b>Comps.</b> The 5 nearest players in weighted z-score space. The line: the projection moved toward "
    + "the ESPN line of the last 14 days (weight games / 14). Diff: their weighted z minus his.</li>";
}"""

_SCRIPT = r"""(() => {
  const C = window.LabCard;
  if (!C) return;
  const esc = C.esc;
  const sgn = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(2);
  const svgBox = (svg, x, y0, y1, rx) => {
    const b = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, sx = b.width / vb.width, sy = b.height / vb.height;
    return { left: b.left + (x - rx) * sx, right: b.left + (x + rx) * sx, top: b.top + (y0 - 6) * sy,
      bottom: b.top + (y1 + 6) * sy };
  };
  const aria = s => `${s.ctx}. ${s.label} ${s.value}. ` + s.rows.map(([a, b]) => `${a} ${b}`).join(". ");
  const head = (body, html) => {
    const h = body.previousElementSibling;
    if (h) h.insertAdjacentHTML("beforeend", ` <span class="lc-lab">${html}</span>`);
  };
  const empty = (body, text) => { body.innerHTML = `<div class="lab-c-empty lc-empty">${esc(text)}</div>`; };
  C.fill.value = (body, p) => {
    const v = p.value;
    if (!v || !v.svg) { empty(body, (v && v.empty) || "No value chart yet."); return; }
    const pct = k => Math.round(100 * k / v.n);
    head(body, `Duds <b>${v.duds} of ${v.n}</b> (${pct(v.duds)}%) · Spikes <b>${v.spikes} of ${v.n}</b> (${pct(v.spikes)}%)`);
    body.innerHTML = `<div class="lc-value">${v.svg}<p class="lab-c-state">${v.state}</p></div>`;
    const svg = body.querySelector("svg"), cross = svg.querySelector(".lab-c-cross");
    svg.querySelectorAll(".lab-c-hit").forEach(r => {
      const t = v.tips[+r.dataset.i];
      if (!t) return;
      r.setAttribute("tabindex", "0");
      r.setAttribute("aria-label", aria(t));
      C.bindTip(r, body, t, () => svgBox(svg, t.x, t.y0, t.y1, 8));
      C.bindCrosshair(r, cross, t.x);
    });
  };
  C.fill.comps = (body, p, d) => {
    const list = (p.comps || []).map(c => [c, d.bySlug.get(c.slug)]).filter(([, q]) => q);
    if (!list.length) { empty(body, p.comps ? "No other player has a line: no comps." : "No projection and no recent games: no comps."); return; }
    head(body, `nearest ${list.length} on the blended line`);
    const owner = q => q.owner ? `${q.owner}${q.mine ? " (you)" : ""}` : "FA";
    body.innerHTML = `<div class="lc-comps-q"><table class="lc-comps"><colgroup><col class="c-band"><col><col class="c-v"><col class="c-d"></colgroup>
<thead><tr><th class="l" scope="col">Team</th><th class="l" scope="col">Player</th><th scope="col">Val</th><th scope="col">Biggest diff</th></tr></thead>
<tbody>${list.map(([c, q]) => `<tr class="lab-c-hit" tabindex="0"><td class="band" style="${esc(d.bands[q.team] || d.bands[""])}">${esc(q.team || "–")}</td>`
      + `<th class="pl" scope="row"><b>${esc(q.name)}</b><small>${esc(q.pos || "–")} · ${esc(owner(q))}</small></th>`
      + `<td class="n"><b>${C.val(q.val)}</b></td><td class="n">${esc(c.cat)} ${sgn(c.diff)}</td></tr>`).join("")}</tbody></table>
<p class="lab-c-state">Val: the Val of the header (his: ${C.val(p.val)}). Diff: their weighted z minus his.</p></div>`;
    const last = p.name.split(" ").pop();
    body.querySelectorAll("tbody tr").forEach((tr, i) => {
      const [c, q] = list[i];
      const s = { ctx: `${q.name} · ${owner(q)}`, value: C.val(q.val), label: "Val",
        rows: [["Biggest diff", `${c.cat} ${sgn(c.diff)} z`], ["Distance", c.dist.toFixed(2)], [`${last}'s Val`, C.val(p.val)]] };
      tr.setAttribute("aria-label", aria(s));
      C.bindTip(tr, body, s, () => tr.getBoundingClientRect());
    });
  };
})();"""


def script():
    """The script of the two quadrants. It runs after the card script (profile.modal())."""
    return _SCRIPT
