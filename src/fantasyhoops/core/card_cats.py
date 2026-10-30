"""The Categories quadrant of the player card (#188): the dot-on-track percentile bars and their tooltip card.

SCRIPT sets LabCard.fill.cats (core/profile.py). It draws one row for each category of the "cats" field of a player
(players/categories.py): the "now" dot (the hero dot), the hollow "proj" dot, the connector and the track. The look
is the Categories quadrant of the "After + tooltips" view of docs/design/players-sample.html and the DESIGN.md
"Charts" rules. The marks use the classes of core/chart.py, and the "now" and "proj" labels follow chart.now_proj().
A player with no "cats" field gets the "No data" box.
A row is a tab stop. LabCard.bindTip() (core/profile.py) shows its tooltip card on a mouse, a tap or the focus.
profile.FILLS lists the module, so profile.modal() adds STYLE and script(). The module writes no files.
"""

from fantasyhoops.core import chart, tokens

NO_DATA = "No projection: no category ranks."  # the text of the "No data" box

# The chart sizes of the approved sample, in px of the 580px viewBox.
GEOMETRY = {"W": 580, "ROW": 38, "T": 18, "L": 84, "R": 104}

STYLE = """/* The Categories quadrant (issue 188): the heading label and the state line. */
.lab-card .lc-q h3 .lc-lab { font-size: 12px; font-weight: 700; font-stretch: 100%; text-transform: none;
  color: var(--lab-mute); }
.lab-card .lc-cats .lab-c-state { margin: 2px 0 0; }"""

# The Categories line of the methods note (the "i" icon), from the cats of the player or, with none, of a player of
# the file. The JS function gives "" when no player has cats.
METHODS = r"""(p, d) => {
  const c = p.cats || (d.players.find(x => x.cats) || {}).cats;
  if (!c || !c.rows || !c.rows.length) return "";
  const ks = c.rows.map(r => `${LabCard.esc(r.cat)} ${r.k}`).join(", ");
  return `<li><b>Categories.</b> The percentile of each category in the pool: the top ${c.pool} players by projected `
    + "value. proj ranks the projection per game. now ranks the season line, shrunk toward the projection: "
    + `(n × season + k × projection) / (n + k), with n games and k in games: ${ks}. `
    + "The k values are agent defaults that the owner did not approve yet.</li>";
}"""

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
    const svg = body.querySelector("svg");
    // The viewport box of the marks of a row: the two dots, 8px wider on each side.
    const markAt = ({ a, b, cy }) => {
      const box = svg.getBoundingClientRect(), k = box.width / W, rx = (b - a) / 2 + 8, mid = (a + b) / 2;
      return { left: box.left + (mid - rx) * k, right: box.left + (mid + rx) * k, top: box.top + (cy - 12) * k,
        bottom: box.top + (cy + 12) * k };
    };
    svg.querySelectorAll(".lab-c-hit").forEach((hit, i) => {
      LabCard.bindTip(hit, body, specs[i].spec, () => markAt(specs[i]));
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
