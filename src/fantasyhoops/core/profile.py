"""The shared player card and the shared player modal of the site (#186).

The card is the 4-quadrant report card of a player: the header (name, team, positions, owner or FA, Val and up to
MAX_SIGNALS signal chips), then the quadrants of QUADRANTS. The /players/ page (players/page.py) and the modal show
the same card. CARD_SCRIPT draws it in the browser from the shared player file, DATA_URL. The script loads the file
once, on the first open.
A player name on the Roster, Free agents and Trade pages is a link (name_link(), or the same markup in a page
script) to #player=<slug>. The link opens the modal over the page. The modal keeps the hash, so the browser Back
button closes it and a copied link opens it. Esc, the Close button and a click on the backdrop close it too. The
focus stays in the modal. On close, the focus goes back to the name, which the script finds again by its slug,
because a page script can draw its names again (build note 1).
Each card rule has the scope .lab-card, so the h1, h2, p and * rules of a page do not change the card (build
note 2). The tooltip card sits in the dialog (build note 3).
publish.shell() puts modal() in place of __PLAYER_MODAL__ in a page template. The module writes no files.
"""

import html

from fantasyhoops.core import card_cats, chart, profile_role
from fantasyhoops.core.common import name_key

DATA_FILE = "players.json"  # the shared player file, in the /players/ folder of the site
DATA_URL = f"../players/{DATA_FILE}"  # the player file from a page in a tool folder of the site
PAGE_URL = "../players/"  # the /players/ page from a page in a tool folder of the site
# The quadrants of the card, in page order: (key, title, the text of the empty box). #187 to #189 fill them.
QUADRANTS = (
    ("role", "Role", "No minutes chart yet."),
    ("cats", "Categories", "No category chart yet."),
    ("value", "Value", "No value chart yet."),
    ("comps", "Comps", "No comps yet."),
)
QUADRANT_KEYS = tuple(key for key, _, _ in QUADRANTS)
# The quadrant fills (#187 to #189). Each module must have STYLE, script() and METHODS. Its script sets
# LabCard.fill.<quadrant> and runs after the card script. METHODS is a JS function (player, file) that gives the
# <li> of the quadrant in the methods note, or "". modal() and card_script() add each fill. A quadrant issue adds one
# entry.
FILLS = (card_cats, profile_role)
MAX_SIGNALS = 3  # the header shows this many signal chips at most
NO_SIGNALS = "No signals: playing to projection"  # the header text when a player has no signal


def slug(name):
    """The slug of a player name in a URL hash, for example "Ace Bailey" -> "ace-bailey". "" if no letter stays.

    The slug is name_key() with "-" for each space, so it has only a to z and "-".
    """
    return name_key(name).replace(" ", "-")


def name_link(name):
    """The HTML of a player name that opens the modal: a link to #player=<slug>. Plain text if the slug is ""."""
    key, text = slug(name), html.escape(name)
    return f'<a class="lab-pname" href="#player={key}" data-player="{key}">{text}</a>' if key else text


def modal(chart_css=True):
    """The modal for the end of a page <body>: the dialog, its style and the scripts of the card and the modal.

    chart_css: True adds chart.CHART_STYLE, for a page whose template has no __CHART_CSS__.
    """
    css = "\n".join(([chart.CHART_STYLE] if chart_css else []) + [CARD_STYLE, MODAL_STYLE] + [f.STYLE for f in FILLS])
    fills = "\n".join(f.script() for f in FILLS)
    return f"{MODAL_HTML}\n<style>\n{css}\n</style>\n<script>\n{card_script()}\n{fills}\n{MODAL_SCRIPT}\n</script>"


def card_script():
    """CARD_SCRIPT with the data URL, the quadrants, the header rules and the methods notes of FILLS."""
    quads = ", ".join(f'["{k}", "{t}", "{e}"]' for k, t, e in QUADRANTS)
    notes = ", ".join(f.METHODS for f in FILLS)
    return (
        CARD_SCRIPT.replace("__DATA_URL__", DATA_URL)
        .replace("__QUADS__", quads)
        .replace("__NOTES__", notes)
        .replace("__MAX_SIGNALS__", str(MAX_SIGNALS))
        .replace("__NO_SIGNALS__", NO_SIGNALS)
    )


# The card. The sizes and the look are those of the approved sample (.impeccable/review/players-modal-sample.html).
CARD_STYLE = """/* The player card (issue 186). Each rule has the scope .lab-card, so the page rules do not change the card. */
.lab-card, .lab-card *, .lab-card *::before, .lab-card *::after { box-sizing: border-box; }
.lab-card { background: var(--lab-stock); color: var(--lab-ink); font: 400 13px/1.35 var(--lab-face);
  font-variant-numeric: tabular-nums; text-align: left; }
.lab-card h2, .lab-card h3, .lab-card p, .lab-card ul, .lab-card dl, .lab-card dd { margin: 0; padding: 0; border: 0;
  letter-spacing: normal; color: inherit; }
.lab-card a { color: var(--mark); }
.lab-card :focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.lab-card .lc-msg { padding: 18px 0; color: var(--lab-mute); }
.lab-card .lc-head { display: flex; flex-wrap: wrap; align-items: stretch; gap: 8px 16px; padding-bottom: 8px;
  border-bottom: 3px solid var(--mark); }
.lab-card .lc-band { flex: none; width: 54px; display: flex; align-items: center; justify-content: center;
  background: var(--team); color: var(--team-ink); font-weight: 900; font-stretch: 70%; font-size: 19px; }
.lab-card .lc-name { color: var(--mark); font-weight: 900; font-stretch: 66%; font-size: 38px; line-height: .9;
  text-transform: uppercase; }
.lab-card .lc-sub { margin-top: 3px; font-size: 12px; color: var(--lab-mute); }
.lab-card .lc-sub b { color: var(--lab-ink); font-weight: 800; }
.lab-card .lc-kv { display: flex; align-items: flex-end; }
.lab-card .lc-kv div { padding: 0 12px; border-left: 1px solid var(--lab-rule); }
.lab-card .lc-kv dt { font-size: 11px; color: var(--lab-mute); }
.lab-card .lc-kv dd { font-weight: 900; font-stretch: 75%; font-size: 24px; line-height: 1; }
.lab-card .lc-kv dd small { margin-left: 3px; font-size: 11px; font-weight: 600; font-stretch: 100%;
  color: var(--lab-mute); }
.lab-card .lc-sigs { display: flex; flex-direction: column; justify-content: flex-end; gap: 4px; max-width: 330px;
  list-style: none; }
.lab-card .lc-sigs a { display: flex; gap: 6px; align-items: baseline; color: var(--lab-ink); text-decoration: none;
  font-size: 12px; }
.lab-card .lc-sigs a:hover .lc-t { text-decoration: underline; }
.lab-card .lc-sig-k { flex: none; padding: 0 4px; border: 1.5px solid var(--lab-ink); font-size: 10.5px;
  font-weight: 800; white-space: nowrap; }
.lab-card .lc-sig-k.alert { background: var(--lab-red); border-color: var(--lab-red); color: var(--lab-on-red); }
.lab-card .lc-none { font-size: 12px; color: var(--lab-mute); }
.lab-card .lc-none b { color: var(--lab-ink); font-weight: 800; }
.lab-card .lc-info { position: relative; margin-left: auto; align-self: flex-start; }
.lab-card .lc-info summary { list-style: none; cursor: pointer; width: 22px; height: 22px; display: flex;
  align-items: center; justify-content: center; border: 1.5px solid var(--lab-ink); color: var(--lab-ink);
  font-weight: 900; font-size: 13px; font-style: italic; }
.lab-card .lc-info summary::-webkit-details-marker { display: none; }
.lab-card .lc-info[open] summary { background: var(--lab-ink); color: var(--lab-stock); }
.lab-card .lc-pop { position: absolute; right: 0; top: 28px; z-index: 20; width: min(560px, 86vw); max-height: 70vh;
  overflow: auto; padding: 10px 14px; border: 1.5px solid var(--lab-ink); background: var(--lab-stock);
  color: var(--lab-ink); font-size: 12px; }
.lab-card .lc-pop h3 { margin: 0 0 4px; font-weight: 900; font-stretch: 75%; font-size: 15px; text-transform: uppercase; }
.lab-card .lc-pop ul { padding-left: 16px; }
.lab-card .lc-pop li { margin: 4px 0; }
.lab-card .lc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 28px; margin-top: 10px; }
.lab-card .lc-q { min-width: 0; display: flex; flex-direction: column; }
.lab-card .lc-q h3 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; padding-bottom: 3px;
  border-bottom: 1px solid var(--mark); font-weight: 900; font-stretch: 75%; font-size: 17px; line-height: 1.1;
  text-transform: uppercase; scroll-margin-top: 60px; }
.lab-card .lc-body { margin-top: 6px; }
.lab-card .lc-empty { display: flex; align-items: center; justify-content: center; min-height: 120px; padding: 18px; }
@media (max-width: 799px) {
  .lab-card .lc-grid { grid-template-columns: 1fr; gap: 12px; }
  .lab-card .lc-q { padding: 10px 12px; border: 1.5px solid var(--lab-rule); }
  .lab-card .lc-info { margin-left: 0; }
  .lab-card .lc-kv div:first-child { padding-left: 0; border-left: 0; }
}"""

# The name links, the dialog and the tooltip card. Square corners and no shadow (DESIGN.md Shapes, Elevation).
MODAL_STYLE = """/* The player modal (issue 186): a large centered dialog. Below 800px, a full-screen sheet. */
/* inline-block: the link box is the line box of the name, so it stays in the name cell. */
a.lab-pname { display: inline-block; color: inherit; text-decoration: underline; text-decoration-thickness: 1px;
  text-underline-offset: 3px; }
a.lab-pname:hover { color: var(--mark); text-decoration-thickness: 2px; }
a.lab-pname:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
dialog.lab-pmodal { box-sizing: border-box; width: min(1240px, calc(100vw - 48px)); max-width: none;
  max-height: calc(100dvh - 24px); margin: auto; padding: 0; overflow: auto; overscroll-behavior: contain;
  border: 1.5px solid var(--lab-ink); border-radius: 0; background: var(--lab-stock); color: var(--lab-ink); }
dialog.lab-pmodal::backdrop { background: var(--lab-scrim); }
.lab-pm-bar { display: flex; align-items: center; gap: 6px 14px; padding: 8px 24px 0; font: 400 12px/1.35 var(--lab-face); }
.lab-pm-k { color: var(--lab-mute); font-weight: 700; }
.lab-pm-full { color: var(--mark); font-weight: 800; }
.lab-pm-close { margin-left: auto; min-height: 24px; padding: 3px 9px; border: 1.5px solid var(--lab-ink);
  border-radius: 0; background: var(--lab-stock); color: var(--lab-ink); font: 800 12px/1.35 var(--lab-face);
  cursor: pointer; }
.lab-pm-close:hover { background: var(--lab-ink); color: var(--lab-stock); }
.lab-pm-bar :focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
dialog.lab-pmodal .lab-card { padding: 8px 24px 16px; }
/* The tooltip card of the charts (DESIGN.md "Tooltips"). It sits in the dialog, in the top layer. */
.lab-tt { position: fixed; z-index: 50; pointer-events: none; box-sizing: border-box; min-width: 168px;
  max-width: 260px; padding: 7px 10px 8px; border: 1px solid var(--lamp-off); border-radius: 0;
  background: var(--lab-stock); color: var(--lab-ink); font: 400 12px/1.3 var(--lab-face);
  font-variant-numeric: tabular-nums; }
.lab-tt[hidden] { display: none; }
.lab-tt .lab-tt-ctx { color: var(--lab-mute); font-size: 11px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.lab-tt .lab-tt-key { display: flex; align-items: baseline; gap: 6px; margin: 2px 0 1px; }
.lab-tt .lab-tt-num { font-size: 20px; font-weight: 800; font-stretch: 85%; line-height: 1.1; }
.lab-tt .lab-tt-lab { color: var(--lab-mute); font-size: 11px; }
.lab-tt .lab-tt-rows { display: grid; grid-template-columns: auto auto; gap: 1px 14px; margin: 4px 0 0;
  padding-top: 4px; border-top: 1px solid var(--lab-rule); }
.lab-tt .lab-tt-rows dt { color: var(--lab-mute); white-space: nowrap; }
.lab-tt .lab-tt-rows dd { margin: 0; text-align: right; white-space: nowrap; }
@media (max-width: 799px) {
  dialog.lab-pmodal { width: 100vw; height: 100dvh; max-height: none; margin: 0; border: 0; }
  .lab-pm-bar { position: sticky; top: 0; z-index: 4; padding: 8px 14px; background: var(--lab-stock);
    border-bottom: 1px solid var(--lab-rule); }
  .lab-pm-close { min-height: 32px; padding: 4px 12px; }
  dialog.lab-pmodal .lab-card { padding: 8px 14px 32px; }
}"""

MODAL_HTML = """<dialog class="lab-pmodal" id="lab-pmodal" aria-label="Player profile">
<div class="lab-pm-bar"><span class="lab-pm-k">Player profile</span>
<a class="lab-pm-full" id="lab-pm-full" href="../players/">Open full profile</a>
<button type="button" class="lab-pm-close" id="lab-pm-close">Close <span aria-hidden="true">×</span></button></div>
<div class="lab-card" id="lab-pm-card"></div>
<div class="lab-tt" id="lab-tt" role="tooltip" hidden></div>
</dialog>"""

# LabCard: load() gives the player file, render() draws the card of one player. fill.<quadrant>(body, player, data)
# draws a quadrant. Without it, the quadrant shows its empty box. #187 to #189 add them.
CARD_SCRIPT = r"""window.LabCard = (() => {
  const QUADS = [__QUADS__];
  // The methods notes of the quadrant fills (profile.FILLS): each gives the HTML of its <li>, or "".
  const NOTES = [__NOTES__];
  const MAX = __MAX_SIGNALS__;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const val = v => v == null ? "–" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(2);
  const fill = {};
  const out = { data: null, fill, esc, val };
  let loading = null;
  out.load = () => {
    if (!loading) {
      loading = fetch("__DATA_URL__").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(d => { d.bySlug = new Map(d.players.map(p => [p.slug, p])); out.data = d; return d; });
      loading.catch(() => { loading = null; });  // the next open tries the file again
    }
    return loading;
  };
  const signals = p => {
    const s = (p.signals || []).slice(0, MAX);
    if (!s.length) return '<li class="lc-none"><b>__NO_SIGNALS__</b></li>';
    return s.map(x => `<li><a href="#" data-q="${esc(x.quadrant)}"><span class="lc-sig-k${x.up ? "" : " alert"}">`
      + `${esc(x.kind)} ${x.up ? "▲" : "▼"}</span><span class="lc-t">${esc(x.text)}</span></a></li>`).join("");
  };
  const methods = (d, p) => {
    const m = d.meta, log = m.log_first ? ` ESPN games in the rotation log, ${esc(m.log_first)} to ${esc(m.log_last)}.` : "";
    return '<h3>Methods and data</h3><ul>'
      + `<li><b>Players.</b> Each rostered player of the league (${m.rostered}), and each free agent with a Val above 0 (above the replacement free agent) or ${m.min_games} or more games (${m.free_agents}).</li>`
      + `<li><b>Owners.</b> The Yahoo rostered list of ${esc(m.made)}.</li>`
      + (m.has_val ? `<li><b>Val.</b> The Val of the Free agents page: blended value per game above a replacement free agent (0 = the free agent at rank ${m.replacement_rank} by value). A player with no Yahoo line in the run has no Val.</li>`
        : "<li><b>Val.</b> The run has no replacement free agent, so no player has a Val.</li>")
      + (m.projections ? `<li><b>Projections.</b> <code>${esc(m.projections)}</code>.</li>` : "")
      + (log ? `<li><b>Games.</b>${log}</li>` : "")
      + NOTES.map(note => note(p, d)).join("")
      + `<li><b>Signals.</b> Each signal comes from a rule of a quadrant and links to it. The header shows ${MAX} at most.</li></ul>`;
  };
  // The tooltip card of a card root. In the modal: #lab-tt, in the dialog (the top layer). On the Players page:
  // #lab-tt-page, outside the closed dialog, so that it can show.
  out.tip = root => document.getElementById(root.closest("dialog") ? "lab-tt" : "lab-tt-page");
  // The tooltip card (DESIGN.md "Tooltips"): the context line, the key number and its label, and up to 3 rows. The card
  // goes beside the mark, never over it, and stays 8px inside the viewport.
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
    if (spec.rows && spec.rows.length) {
      const dl = add(tip, "dl", "lab-tt-rows");
      spec.rows.slice(0, 3).forEach(([a, b]) => { add(dl, "dt", null, a); add(dl, "dd", null, b); });
    }
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
  // The one tooltip function of the quadrant fills. target: a chart target in the card root. The target must have the
  // class lab-c-hit (core/chart.py): the tap rule below hides the card on a tap outside each lab-c-hit element.
  // spec: {ctx, value, label, rows: [[name, value]]}. markAt(): the viewport box {left, right, top, bottom} of the
  // marks of the target. A mouse shows the card on enter and hides it on leave. A tap shows it and keeps it. The focus
  // shows it.
  out.bindTip = (target, root, spec, markAt) => {
    const tip = out.tip(root);
    if (!tip) return;
    const on = () => showTip(tip, spec, markAt());
    const off = () => { tip.hidden = true; };
    target.setAttribute("aria-describedby", tip.id);
    target.addEventListener("pointerenter", e => { if (e.pointerType === "mouse") on(); });
    target.addEventListener("pointerleave", e => { if (e.pointerType === "mouse") off(); });
    target.addEventListener("pointerdown", e => { if (e.pointerType !== "mouse") { on(); e.stopPropagation(); } });
    target.addEventListener("focus", on);
    target.addEventListener("blur", off);
  };
  // A tap outside a chart target, a scroll or Escape hides the card. In the modal, the dialog handles Escape: the
  // first Escape hides the card, the next one closes the modal. The modal also hides the card on its own scroll.
  const hideTips = () => document.querySelectorAll(".lab-tt").forEach(t => { t.hidden = true; });
  document.addEventListener("pointerdown", e => { if (!(e.target.closest && e.target.closest(".lab-c-hit"))) hideTips(); });
  window.addEventListener("scroll", hideTips, { passive: true });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !(e.target.closest && e.target.closest("dialog"))) hideTips();
  });
  // root: the .lab-card element. p: one player of the file. d: the file. id: a prefix for the ids of the card.
  out.render = (root, p, d, id) => {
    const owner = p.owner ? `${esc(p.owner)}${p.mine ? " (you)" : ""}` : "FA";
    root.innerHTML = `<header class="lc-head">
<div class="lc-band" style="${esc(d.bands[p.team] || d.bands[""])}">${esc(p.team || "–")}</div>
<div class="lc-who"><h2 class="lc-name" id="${id}-name">${esc(p.name)}</h2>
<p class="lc-sub">${esc(p.pos || "–")} · <b>${owner}</b></p></div>
<dl class="lc-kv"><div><dt>Val</dt><dd>${val(p.val)}</dd></div></dl>
<ul class="lc-sigs" aria-label="Signals">${signals(p)}</ul>
<details class="lc-info"><summary aria-label="Methods and data" title="Methods and data">i</summary>
<div class="lc-pop">${methods(d, p)}</div></details>
</header>
<div class="lc-grid">${QUADS.map(([k, t]) => `<section class="lc-q" id="${id}-q-${k}" aria-labelledby="${id}-h-${k}">`
      + `<h3 id="${id}-h-${k}" tabindex="-1">${t}</h3><div class="lc-body" data-q="${k}"></div></section>`).join("")}</div>`;
    QUADS.forEach(([k, , empty]) => {
      const body = root.querySelector(`.lc-body[data-q="${k}"]`);
      if (fill[k]) fill[k](body, p, d);
      else body.innerHTML = `<div class="lab-c-empty lc-empty">${empty}</div>`;
    });
    root.querySelectorAll(".lc-sigs a").forEach(a => a.addEventListener("click", e => {
      e.preventDefault();
      const h = document.getElementById(`${id}-h-${a.dataset.q}`);
      if (h) { h.scrollIntoView({ block: "nearest" }); h.focus({ preventScroll: true }); }
    }));
  };
  return out;
})();"""

# The modal. The hash is #player=<slug>. A name link adds a history entry, so Back closes the modal. A copied link
# opens the modal on load with no entry of its own, so Close then removes the hash in place.
MODAL_SCRIPT = r"""(() => {
  const dlg = document.getElementById("lab-pmodal");
  if (!dlg || !window.LabCard) return;
  const card = document.getElementById("lab-pm-card"), full = document.getElementById("lab-pm-full");
  const closer = document.getElementById("lab-pm-close"), tip = document.getElementById("lab-tt");
  let openSlug = null, pushed = false, ask = 0;
  const slugOf = () => { const m = location.hash.match(/^#player=([a-z0-9-]+)$/); return m ? m[1] : null; };
  // A page script can draw its names again, so the name is found again by its slug, the shown one first.
  const nameOf = slug => {
    const all = [...document.querySelectorAll(`a.lab-pname[data-player="${slug}"]`)].filter(a => !dlg.contains(a));
    return all.find(a => a.getClientRects().length) || all[0] || null;
  };
  const draw = (slug, d) => {
    const p = d.bySlug.get(slug);
    if (!p) {
      card.innerHTML = '<p class="lc-msg">No profile for this player: he is not in the player file.</p>';
      dlg.setAttribute("aria-label", "Player profile");
      return;
    }
    LabCard.render(card, p, d, "lab-pm");
    dlg.setAttribute("aria-label", `${p.name}, player profile`);
  };
  function show(slug) {
    openSlug = slug;
    full.href = `../players/#${slug}`;
    if (!dlg.open) { dlg.showModal(); document.body.classList.add("lab-locked"); }
    const n = ++ask;
    if (LabCard.data) draw(slug, LabCard.data);
    else {
      card.innerHTML = '<p class="lc-msg">Loading the player file…</p>';
      LabCard.load().then(d => { if (n === ask && dlg.open) draw(slug, d); }, () => {
        if (n === ask && dlg.open) card.innerHTML = '<p class="lc-msg">The player file did not load. Try again later.</p>';
      });
    }
    dlg.scrollTop = 0;
    closer.focus();
  }
  function hide() {
    if (!dlg.open) return;
    const slug = openSlug;
    tip.hidden = true;
    dlg.close();
    document.body.classList.remove("lab-locked");
    openSlug = null; pushed = false;
    const back = slug && nameOf(slug);
    if (back) back.focus();
  }
  function requestClose() {
    if (pushed) { pushed = false; history.back(); }
    else { history.replaceState(null, "", location.href.split("#")[0]); hide(); }
  }
  closer.addEventListener("click", requestClose);
  dlg.addEventListener("cancel", e => {
    e.preventDefault();
    const info = dlg.querySelector(".lc-info[open]");
    if (info) { info.open = false; info.querySelector("summary").focus(); return; }
    if (!tip.hidden) { tip.hidden = true; return; }
    requestClose();
  });
  dlg.addEventListener("click", e => { if (e.target === dlg) requestClose(); });
  dlg.addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
  // The focus stays in the modal: Tab from the last control goes to the first, Shift+Tab from the first to the last.
  dlg.addEventListener("keydown", e => {
    if (e.key !== "Tab") return;
    const f = [...dlg.querySelectorAll('a[href], button, summary, [tabindex="0"]')].filter(n => n.getClientRects().length);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
  // A name link changes the hash itself. The capture stops the click there, so a click handler of a table row
  // (for example the trade builder) does not also act on it.
  document.addEventListener("click", e => {
    if (e.target.closest && e.target.closest("a.lab-pname") && !dlg.open) e.stopPropagation();
  }, true);
  window.addEventListener("hashchange", () => {
    const slug = slugOf();
    if (slug) { if (slug !== openSlug) { show(slug); pushed = true; } }
    else hide();
  });
  const first = slugOf();
  if (first) show(first);
})();"""
