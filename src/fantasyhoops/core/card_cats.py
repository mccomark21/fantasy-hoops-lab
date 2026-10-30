"""The Categories quadrant of the player card (#188): the dot-on-track percentile bars and their tooltip card.

SCRIPT sets LabCard.fill.cats (core/profile.py). It draws one row for each category of the "cats" field of a player
(players/categories.py): the "now" dot (the hero dot), the hollow "proj" dot, the connector and the track. The look
is the Categories quadrant of the "After + tooltips" view of docs/design/players-sample.html and the DESIGN.md
"Charts" rules. The marks use the classes of core/chart.py, and the "now" and "proj" labels follow chart.now_proj().
A player with no "cats" field gets the "No data" box.
A row is a tab stop. A mouse, a tap or the focus shows the tooltip card of LabCard.tip().
profile.modal() adds STYLE and SCRIPT. The module writes no files.
"""

from fantasyhoops.core import chart, tokens

NO_DATA = "No projection: no category ranks."  # the text of the "No data" box

# The chart sizes of the approved sample, in px of the 580px viewBox.
GEOMETRY = {"W": 580, "ROW": 38, "T": 18, "L": 84, "R": 104}

STYLE = """/* The Categories quadrant (issue 188): the heading label, the state line and the tooltip card text. */
.lab-card .lc-q h3 .lc-lab { font-size: 12px; font-weight: 700; font-stretch: 100%; text-transform: none;
  color: var(--lab-mute); }
.lab-card .lc-cats .lab-c-state { margin: 2px 0 0; }
.lab-tt .lab-tt-ctx { color: var(--lab-mute); font-size: 11px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.lab-tt .lab-tt-key { display: flex; align-items: baseline; gap: 6px; margin: 2px 0 1px; }
.lab-tt .lab-tt-num { font-size: 20px; font-weight: 800; font-stretch: 85%; line-height: 1.1; }
.lab-tt .lab-tt-lab { color: var(--lab-mute); font-size: 11px; }
.lab-tt .lab-tt-rows { display: grid; grid-template-columns: auto auto; gap: 1px 14px; margin: 4px 0 0;
  padding-top: 4px; border-top: 1px solid var(--lab-rule); }
.lab-tt .lab-tt-rows dt { color: var(--lab-mute); white-space: nowrap; }
.lab-tt .lab-tt-rows dd { margin: 0; text-align: right; white-space: nowrap; }"""

_SCRIPT = r"""(() => {
  const G = __GEOMETRY__, M = __MARKERS__, NP = __NOW_PROJ__, NO_DATA = "__NO_DATA__";
  const esc = LabCard.esc;
  const f1 = v => v == null ? "–" : (Math.round(v * 10) / 10).toFixed(1);
  const ord = v => {
    const n = Math.round(v), t = n % 100;
    return n + ((t >= 11 && t <= 13) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
  };
  const n2 = v => String(Math.round(v * 100) / 100);
  const text = (x, y, s, kind, anchor) => `<text class="lab-c-${kind}" x="${n2(x)}" y="${n2(y)}"`
    + (anchor && anchor !== "start" ? ` text-anchor="${anchor}"` : "") + `>${esc(s)}</text>`;
  // The "now" and "proj" labels of the first row: chart.now_proj() of core/chart.py.
  const nowProj = (xs, xp, cy) => {
    if (Math.abs(xs - xp) > NP.apart) return [[xs, cy - NP.dy, "middle"], [xp, cy - NP.dy, "middle"]];
    if (xs <= xp) return [[xs + NP.dx, cy - NP.dy, "end"], [xp - NP.dx, cy + NP.below, "start"]];
    return [[xs - NP.dx, cy - NP.dy, "start"], [xp + NP.dx, cy + NP.below, "end"]];
  };
  // The tooltip card (DESIGN.md "Tooltips"): beside the mark, never over it, 8px inside the viewport.
  const showTip = (tip, spec, mark) => {
    const add = (parent, tag, cls, s) => {
      const node = document.createElement(tag);
      if (cls) node.className = cls;
      if (s != null) node.textContent = s;
      parent.appendChild(node);
      return node;
    };
    tip.replaceChildren();
    add(tip, "div", "lab-tt-ctx", spec.ctx);
    const key = add(tip, "div", "lab-tt-key");
    add(key, "span", "lab-tt-num", spec.value);
    add(key, "span", "lab-tt-lab", spec.label);
    const dl = add(tip, "dl", "lab-tt-rows");
    spec.rows.slice(0, 3).forEach(([a, b]) => { add(dl, "dt", null, a); add(dl, "dd", null, b); });
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight, gap = 12, pad = 8;
    let x = mark.right + gap, y = (mark.top + mark.bottom) / 2 - h / 2;
    if (x + w > innerWidth - pad) x = mark.left - gap - w;
    if (x < pad) {
      x = Math.max(pad, Math.min(innerWidth - pad - w, (mark.left + mark.right) / 2 - w / 2));
      y = mark.top - gap - h >= pad ? mark.top - gap - h : mark.bottom + gap;
    }
    y = Math.max(pad, Math.min(innerHeight - pad - h, y));
    tip.style.left = Math.round(x) + "px";
    tip.style.top = Math.round(y) + "px";
  };
  const hideAll = () => document.querySelectorAll(".lab-tt").forEach(t => { t.hidden = true; });
  // A tap outside a chart target, a scroll or Escape hides the card. The modal also hides it on its own scroll.
  document.addEventListener("pointerdown", e => { if (!(e.target.closest && e.target.closest(".lab-c-hit"))) hideAll(); });
  window.addEventListener("scroll", hideAll, { passive: true });
  // In the modal, the dialog handles Escape: the first Escape hides the card, the next one closes the modal.
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !(e.target.closest && e.target.closest("dialog"))) hideAll();
  });

  LabCard.fill.cats = (body, p) => {
    const c = p.cats;
    if (!c || !c.rows || !c.rows.length) {
      body.innerHTML = `<div class="lab-c-empty lc-empty">${NO_DATA}</div>`;
      return;
    }
    const h3 = body.parentElement && body.parentElement.querySelector("h3");
    if (h3) h3.insertAdjacentHTML("beforeend", `<span class="lc-lab">percentile of the ${c.pool}-player pool</span>`);
    const { W, ROW, T, L, R } = G, H = T + ROW * c.rows.length;
    const x = v => L + (W - L - R) * v / 100;
    let s = [0, 50, 100].map(t => text(x(t), T - 6, t === 50 ? "50th pct" : String(t), "tick", "middle")).join("");
    s += `<line class="lab-c-ref" x1="${n2(x(50))}" y1="${T}" x2="${n2(x(50))}" y2="${H - 6}"/>`;
    s += text(W - R + 30, T - 6, "per game", "tick");
    const specs = [];
    c.rows.forEach((r, i) => {
      const cy = T + ROW * i + ROW / 2, xs = x(r.now), xp = x(r.proj);
      s += text(0, cy + 4, r.cat, "label") + text(34, cy + 4, `×${r.w.toFixed(2)}`, "tick");
      s += `<line class="lab-c-track" x1="${n2(x(0))}" y1="${n2(cy)}" x2="${n2(x(100))}" y2="${n2(cy)}"/>`;
      s += `<line class="lab-c-conn" x1="${n2(xp)}" y1="${n2(cy)}" x2="${n2(xs)}" y2="${n2(cy)}"/>`;
      s += `<circle class="lab-c-proj" cx="${n2(xp)}" cy="${n2(cy)}" r="${M.proj}"/>`;
      s += `<circle class="lab-c-hero-dot" cx="${n2(xs)}" cy="${n2(cy)}" r="${M.now}"/>`;
      if (i === 0) {
        const [now, proj] = nowProj(xs, xp, cy);
        s += text(now[0], now[1], "now", "label", now[2]) + text(proj[0], proj[1], "proj", "tick", proj[2]);
      }
      s += text(W - R + 14, cy + 4, f1(r.raw), "label") + text(W - R + 46, cy + 4, "proj " + f1(r.line), "tick");
      const spec = {
        ctx: `${r.cat} · punt weight ${r.w.toFixed(2)}`, value: ord(r.now), label: "percentile now",
        rows: [["Projection", ord(r.proj)], ["Per game now", c.n ? `${f1(r.raw)} (shrunk ${f1(r.shrunk)})` : "–"],
          ["Season weight", `${Math.round(r.nw * 100)}% after ${c.n} ${c.n === 1 ? "game" : "games"}`]],
      };
      specs.push({ spec, a: Math.min(xs, xp), b: Math.max(xs, xp), cy });
      const aria = `${spec.ctx}. ${spec.label} ${spec.value}. ` + spec.rows.map(([a, b]) => `${a} ${b}`).join(". ");
      s += `<rect class="lab-c-hit" x="0" y="${n2(cy - ROW / 2)}" width="${W}" height="${ROW}" tabindex="0"`
        + ` aria-label="${esc(aria)}"/>`;
    });
    const first = c.rows[0], last = c.rows[c.rows.length - 1];
    const state = c.n
      ? `${c.n} ${c.n === 1 ? "game" : "games"}: the season line has ${Math.round(first.nw * 100)}% of the weight for ${esc(first.cat)}, ${Math.round(last.nw * 100)}% for ${esc(last.cat)}.`
      : "<b>No games yet:</b> now is the projection.";
    body.innerHTML = `<div class="lc-cats"><svg class="lab-chart" viewBox="0 0 ${W} ${H}" role="img"`
      + ` aria-label="Percentile of each category in the pool: now and projection">${s}</svg>`
      + `<p class="lab-c-state">${state}</p></div>`;
    const svg = body.querySelector("svg"), tip = LabCard.tip(body);
    if (!tip) return;
    // The viewport box of the marks of a row: the two dots, 8px wider on each side.
    const markAt = ({ a, b, cy }) => {
      const box = svg.getBoundingClientRect(), k = box.width / W, rx = (b - a) / 2 + 8, mid = (a + b) / 2;
      return { left: box.left + (mid - rx) * k, right: box.left + (mid + rx) * k, top: box.top + (cy - 12) * k,
        bottom: box.top + (cy + 12) * k };
    };
    svg.querySelectorAll(".lab-c-hit").forEach((hit, i) => {
      const on = () => showTip(tip, specs[i].spec, markAt(specs[i]));
      const off = () => { tip.hidden = true; };
      hit.setAttribute("aria-describedby", tip.id);
      hit.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") on(); });
      hit.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") off(); });
      hit.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") { on(); e.stopPropagation(); } });
      hit.addEventListener("focus", on);
      hit.addEventListener("blur", off);
    });
  };
})();"""


def script():
    """The script of the quadrant, with the sizes of core/chart.py and core/tokens.py. It runs after the card script."""
    now_proj = {
        "apart": chart.NOW_PROJ_APART,
        "dy": chart.NOW_PROJ_DY,
        "below": chart.PROJ_BELOW_DY,
        "dx": chart.NOW_PROJ_DX,
    }
    markers = {"now": tokens.CHART_MARKERS["now"], "proj": tokens.CHART_MARKERS["proj"]}
    return (
        _SCRIPT.replace("__GEOMETRY__", str(GEOMETRY).replace("'", '"'))
        .replace("__MARKERS__", str(markers).replace("'", '"'))
        .replace("__NOW_PROJ__", str(now_proj).replace("'", '"'))
        .replace("__NO_DATA__", NO_DATA)
    )
