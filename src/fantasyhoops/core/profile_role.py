"""The Role quadrant of the player card (#187): the minutes chart and its labels, drawn in the browser.

SCRIPT adds LabCard.fill.role to the card script of core/profile.py. It draws the "role" field of a player record
(players/role.py): a game dot for the total minutes of each game, the rolling average (the hero line), the
competitive minutes (a secondary line) and the band of the normal range, with "▲ out" or "▼ out" at a range exit.
The quadrant head gets the usage label and the close-game minutes label. The state line under the chart follows the
DESIGN.md "Thin data" rules. LabCard.role.draw(role) gives the SVG text and the hit columns with no DOM, so a test can
run it in Node. LabCard.bindTip() (core/profile.py) shows the tooltip card of each game column.
The look is the Role quadrant of the approved sample (docs/design/players-sample.html, "After + tooltips"). The marks
use the classes of core/chart.py. The label placement mirrors chart.end_labels(), chart.point_label() and
chart.band_label(). STYLE holds the styles of the quadrant labels. METHODS gives the Role line of the methods note.
profile.FILLS lists the module, so profile.modal() adds STYLE and script(). The module writes no files.
"""

from fantasyhoops.core import chart, tokens

STYLE = """/* The Role quadrant (issue 187): the bold words of the head labels and the state line. */
.lab-card .lc-q h3 .lc-lab b { color: var(--lab-ink); font-weight: 800; }
.lab-card .lc-chart { position: relative; }
.lab-card p.lab-c-state { margin: 2px 0 0; color: var(--lab-mute); }
.lab-card p.lab-c-state b { color: var(--lab-ink); }"""

# The Role line of the methods note (the "i" icon). The JS function gives "" when no player has a role field.
METHODS = r"""(p, d) => {
  const r = p.role || (d.players.find(x => x.role) || {}).role;
  if (!r) return "";
  return `<li><b>Role.</b> Minutes and competitive minutes of each logged game. The line is the average of the last `
    + `${r.window} games. The normal range is the season mean ± 2 × spread / √${r.window}: the spread mixes his own `
    + "spread with a league spread worth 4 games. Usage: the box-score usage rate, and the last "
    + `${r.window} games minus it. Close: the mean minutes in close games and in the other games.</li>`;
}"""

# The sizes of the label placement come from core/chart.py, so that the browser and the Python checks agree.
# The dot sizes come from core/tokens.py.
_PLACE = {
    "__CHAR_W__": chart.CHAR_W,
    "__TXT_H__": chart.TXT_H,
    "__END_GAP__": chart.END_GAP,
    "__END_DX__": chart.END_DX,
    "__END_INSET__": chart.END_INSET,
    "__PLOT_INSET__": chart.PLOT_INSET,
    "__SIDE_DX__": chart.SIDE_DX,
    "__SIDE_DY__": chart.SIDE_DY,
    "__BAND_INSET__": chart.BAND_INSET,
    "__R_GAME__": tokens.CHART_MARKERS["game"],
    "__R_HERO__": tokens.CHART_MARKERS["hero"],
}


def script():
    """SCRIPT with the label placement sizes of core/chart.py."""
    out = SCRIPT
    for key, value in _PLACE.items():
        out = out.replace(key, chart._n(value))
    return out


SCRIPT = r"""(() => {
  const LC = window.LabCard;
  if (!LC) return;
  const W = 580, H = 268, L = 30, R = 104, T = 12, B = 22;  // the canvas and the plot margins of the sample
  const CW = __CHAR_W__, TH = __TXT_H__, GAP = __END_GAP__, EDX = __END_DX__, EIN = __END_INSET__;
  const PIN = __PLOT_INSET__, SDX = __SIDE_DX__, SDY = __SIDE_DY__, BIN = __BAND_INSET__;
  const R_GAME = __R_GAME__, R_HERO = __R_HERO__;
  const esc = LC.esc;
  const n = v => { const t = (+v).toFixed(2).replace(/\.?0+$/, ""); return t === "-0" ? "0" : t; };
  const f1 = v => v == null ? "–" : v.toFixed(1);
  const fMin = v => v == null ? "–" : `${f1(v)} min`;
  const sgn1 = v => (v > 0 ? "+" : v < 0 ? "−" : "±") + Math.abs(v).toFixed(1);
  const tw = s => s.length * CW;
  const hits = (r, boxes) => boxes.some(b => r.x < b.x + b.w && r.x + r.w > b.x && r.y < b.y + b.h && r.y + r.h > b.y);
  const attrs = a => Object.entries(a).map(([k, v]) => ` ${k}="${typeof v === "number" ? n(v) : esc(v)}"`).join("");
  const tag = (name, a) => `<${name}${attrs(a)}/>`;
  const text = (x, y, s, cls, anchor) => `<text class="${cls}" x="${n(x)}" y="${n(y)}"`
    + (anchor ? ` text-anchor="${anchor}"` : "") + `>${esc(s)}</text>`;
  const path = pts => "M" + pts.map(([x, y]) => `${n(x)},${n(y)}`).join("L");
  function niceTicks(lo, hi, count) {
    const span = hi - lo, raw = span / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= count) || 10 * mag;
    const a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, out = [];
    for (let v = a; v <= b + 1e-9; v += step) out.push(+v.toFixed(6));
    return { ticks: out, lo: a, hi: b };
  }
  function segBoxes(pts, pad) {
    const out = [];
    for (let i = 1; i < pts.length; i++) {
      const [x1, y1] = pts[i - 1], [x2, y2] = pts[i], k = Math.max(1, Math.ceil(Math.hypot(x2 - x1, y2 - y1) / 4));
      for (let j = 0; j <= k; j++) out.push({ x: x1 + (x2 - x1) * j / k - pad, y: y1 + (y2 - y1) * j / k - pad, w: 2 * pad, h: 2 * pad });
    }
    return out;
  }
  // chart.end_labels(): move labels that are less than GAP apart by the same amount, inside [top, bottom].
  function endLabels(ys, top, bottom) {
    const order = ys.map((y, i) => i).sort((a, b) => ys[a] - ys[b]);
    let placed = order.map(i => ys[i]);
    const lo = top + EIN, hi = bottom - EIN;
    for (let pass = 0; pass < 20; pass++) {
      let moved = false;
      for (let i = 1; i < placed.length; i++) {
        const gap = placed[i] - placed[i - 1];
        if (gap < GAP) { const h = (GAP - gap) / 2; placed[i - 1] -= h; placed[i] += h; moved = true; }
      }
      placed = placed.map(y => Math.max(lo, Math.min(hi, y)));
      if (!moved) break;
    }
    for (let i = 1; i < placed.length; i++) placed[i] = Math.max(placed[i], placed[i - 1] + GAP);
    if (placed.length) {
      placed[placed.length - 1] = Math.min(placed[placed.length - 1], hi);
      for (let i = placed.length - 2; i >= 0; i--) placed[i] = Math.min(placed[i], placed[i + 1] - GAP);
    }
    const out = new Array(ys.length);
    order.forEach((i, j) => { out[i] = placed[j]; });
    return out;
  }
  // chart.point_label(): right, left, above, below. The first clear side, or null.
  function pointLabel(s, cx, cy, boxes, plot) {
    const w = tw(s);
    const sides = [[cx + SDX, cy - TH / 2], [cx - SDX - w, cy - TH / 2], [cx - w / 2, cy - SDY - TH], [cx - w / 2, cy + SDY]];
    for (const [x, y] of sides) {
      const r = { x, y, w, h: TH };
      if (x < plot.x + PIN || x + w > plot.x + plot.w - PIN || y < plot.y + PIN || y + TH > plot.y + plot.h - PIN || hits(r, boxes)) continue;
      boxes.push(r);
      return [x, y + TH - 2];
    }
    return null;
  }
  // chart.band_label(): bottom-left, top-left, bottom-right, top-right. The first clear corner, or null.
  function bandLabel(s, bb, boxes) {
    const w = tw(s), left = bb.x + BIN, right = bb.x + bb.w - BIN - w, top = bb.y + BIN, bottom = bb.y + bb.h - BIN - TH;
    for (const [x, y] of [[left, bottom], [left, top], [right, bottom], [right, top]]) {
      const r = { x, y, w, h: TH };
      if (!hits(r, boxes)) { boxes.push(r); return [x, y + TH - 2]; }
    }
    return null;
  }
  const ctx = g => `${g.d} vs ${g.opp} · ${g.start ? "start" : "bench"}` + (g.close ? " · close game" : "");
  // The SVG text of the minutes chart and its hit columns. role: the "role" field of a player record.
  function draw(role) {
    const gs = role.games, k = gs.length, win = role.window, band = role.lo != null;
    const vals = gs.flatMap(g => [g.min, g.comp]).concat(role.roll, band ? [role.lo, role.hi] : []).filter(v => v != null);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (hi - lo < 2) { lo -= 1; hi += 1; }
    const nt = niceTicks(Math.max(0, lo - (hi - lo) * 0.05), hi + (hi - lo) * 0.05, 4);  // no minutes below 0
    const y = v => T + (H - T - B) * (1 - (v - nt.lo) / (nt.hi - nt.lo));
    const step = (W - L - R) / Math.max(k, 1), x = i => L + step * (i + 0.5);
    const plot = { x: L, y: T, w: W - L - R, h: H - T - B }, boxes = [];
    const comp = gs.map((g, i) => g.comp == null ? null : [x(i), y(g.comp)]).filter(Boolean);
    const hero = role.roll.map((v, i) => v == null ? null : [x(i), y(v)]).filter(Boolean);
    gs.forEach((g, i) => boxes.push({ x: x(i) - 6, y: y(g.min) - 6, w: 12, h: 12 }));
    boxes.push(...segBoxes(comp, 2), ...segBoxes(hero, 3));
    if (hero.length) { const [hx, hy] = hero[hero.length - 1]; boxes.push({ x: hx - 6, y: hy - 6, w: 12, h: 12 }); }
    let out = nt.ticks.map(t => text(L - 6, y(t) + 4, String(t), "lab-c-tick", "end")).join("");
    let labels = "";
    if (band) {
      const bb = { x: L, y: y(role.hi), w: W - L - R, h: y(role.lo) - y(role.hi) };
      out += tag("rect", { class: "lab-c-band", x: bb.x, y: bb.y, width: bb.w, height: bb.h });
      const s = `normal range ${f1(role.lo)}–${f1(role.hi)}`, at = bandLabel(s, bb, boxes);
      if (at) labels += text(at[0], at[1], s, "lab-c-tick");
    }
    if (comp.length > 1) out += tag("path", { class: "lab-c-second", d: path(comp) });
    gs.forEach((g, i) => { out += tag("circle", { class: "lab-c-game", cx: x(i), cy: y(g.min), r: R_GAME }); });
    if (hero.length > 1) out += tag("path", { class: "lab-c-hero", d: path(hero) });
    const ends = [];
    const last = gs[k - 1];
    if (last.comp != null) ends.push([y(last.comp), `competitive ${f1(last.comp)}`, "lab-c-tick"]);
    if (hero.length) {
      const [hx, hy] = hero[hero.length - 1];
      out += tag("circle", { class: "lab-c-hero-dot", cx: hx, cy: hy, r: R_HERO });
      if (role.roll[k - 1] != null) ends.push([hy, `${win}-game ${f1(role.roll[k - 1])}`, "lab-c-label"]);
    }
    ends.push([y(last.min), `game ${f1(last.min)}`, "lab-c-tick"]);
    const ly = endLabels(ends.map(e => e[0]), T, H - B);
    ends.forEach(([, s, cls], i) => { labels += text(W - R + EDX, ly[i] + 4, s, cls); });
    (role.exits || []).forEach(([i, dir]) => {
      const at = pointLabel(dir === "up" ? "▲ out" : "▼ out", x(i), y(role.roll[i]), boxes, plot);
      if (at) labels += text(at[0], at[1], dir === "up" ? "▲ out" : "▼ out", "lab-c-exit");
    });
    // A date under each game. With many games, every kth date, from the last game back, so that no two touch.
    const every = Math.max(1, Math.ceil((Math.max(...gs.map(g => tw(g.d))) + 6) / step));
    gs.forEach((g, i) => { if ((k - 1 - i) % every === 0) labels += text(x(i), H - 6, g.d, "lab-c-tick", "middle"); });
    const cols = gs.map((g, i) => {
      const ys = [g.min, g.comp ?? g.min, role.roll[i] ?? g.min].map(y);
      const avg = role.roll[i] == null ? `needs ${win} games` : fMin(role.roll[i]);
      const spec = { ctx: ctx(g), value: fMin(g.min), label: "minutes",
        rows: [["Competitive", fMin(g.comp)], [`${win}-game avg`, avg], ["Usage", g.usg == null ? "–" : `${f1(g.usg)}%`]] };
      return { x: x(i), left: x(i) - step / 2, width: step, top: Math.min(...ys), bottom: Math.max(...ys), spec };
    });
    const hit = cols.map((c, i) => tag("rect", { class: "lab-c-hit", x: c.left, y: T, width: c.width, height: H - T - B,
      tabindex: "0", "data-i": String(i), "aria-label": `${c.spec.ctx}. ${c.spec.value} ${c.spec.label}. `
        + c.spec.rows.map(([a, b]) => `${a} ${b}`).join(". ") })).join("");
    const cross = tag("line", { class: "lab-c-cross", x1: 0, x2: 0, y1: T, y2: H - B, visibility: "hidden" });
    const svg = `<svg class="lab-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Total and competitive minutes in each game">`
      + out + labels + cross + hit + "</svg>";
    return { svg, cols };
  }
  function heads(role) {
    const g = role.games.length;
    const usg = role.usg == null ? "USG <b>–</b>" : `USG <b>${Math.round(role.usg)}%</b>`
      + (role.usg_last == null ? " (too few games for a trend)"
        : ` ${role.usg_last - role.usg >= 0 ? "▲" : "▼"} ${sgn1(role.usg_last - role.usg)} last ${role.window}`);
    const close = role.close_n ? `Close <b>${role.close_n} of ${g}</b>: ${f1(role.close_min)} min`
      + (role.other_min == null ? "" : ` (${f1(role.other_min)} other)`) : `Close <b>0 of ${g}</b>`;
    return `<span class="lc-lab">${usg}</span><span class="lc-lab">${close}</span>`;
  }
  // The crosshair of a trend chart (DESIGN.md "Tooltips"): it shows while the tooltip card of its game column shows.
  // LabCard.bindTip() of core/profile.py shows the card. These handlers follow the same show and hide rules.
  let crossShown = null;
  const hideCross = () => { if (crossShown) crossShown.setAttribute("visibility", "hidden"); crossShown = null; };
  const showCross = (cross, cx) => {
    hideCross();
    cross.setAttribute("x1", n(cx)); cross.setAttribute("x2", n(cx)); cross.setAttribute("visibility", "visible");
    crossShown = cross;
  };
  document.addEventListener("pointerdown", e => { if (!(e.target.closest && e.target.closest(".lab-c-hit"))) hideCross(); });
  window.addEventListener("scroll", hideCross, { passive: true, capture: true });
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideCross(); });
  LC.role = { draw, heads };
  LC.fill.role = (body, p) => {
    const role = p.role;
    if (!role || !role.games || !role.games.length) {
      body.innerHTML = '<div class="lab-c-empty lc-empty">No games in the rotation log: no minutes chart.</div>';
      return;
    }
    const h3 = body.previousElementSibling;
    if (h3) h3.insertAdjacentHTML("beforeend", heads(role));
    const { svg, cols } = draw(role);
    const [lead, rest] = role.state;
    body.innerHTML = `<div class="lc-chart">${svg}</div>`
      + `<p class="lab-c-state">${lead ? `<b>${esc(lead)}</b> ` : ""}${esc(rest)}</p>`;
    const el = body.querySelector("svg"), cross = el.querySelector(".lab-c-cross");
    el.querySelectorAll(".lab-c-hit").forEach(r => {
      const c = cols[+r.dataset.i];
      const markAt = () => {
        const b = el.getBoundingClientRect(), s = b.width / W, t = b.height / H;
        return { left: b.left + (c.x - 8) * s, right: b.left + (c.x + 8) * s,
          top: b.top + (c.top - 6) * t, bottom: b.top + (c.bottom + 6) * t };
      };
      LC.bindTip(r, body, c.spec, markAt);
      const on = () => showCross(cross, c.x);
      r.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") on(); });
      r.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") hideCross(); });
      r.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") on(); });
      r.addEventListener("focus", on);
      r.addEventListener("blur", hideCross);
    });
  };
})();"""
