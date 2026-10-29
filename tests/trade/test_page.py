import re
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from fantasyhoops.core import roster as roster_page
from fantasyhoops.core import publish as site
from fantasyhoops.trade import page
from fantasyhoops.trade.suggest import Suggestion, Suggestions, TradePlayer, TradeSettings

WEEKS = ["wk19", "wk20", "wk21"]
CFG = {"league": {"teams": 14}, "trade": {"kept": 8, "per_player": 3}}
MADE = datetime(2026, 10, 29, 9, 30)
TODAY = MADE.date()
DEADLINE = date(2027, 3, 4)
READ = "Rosters: 16 pages from the cache of 2026-10-29 09:14."
BASE = (28, 27, 26)


def mine(name, value, team="ATL", pos=("PG",), slot="PG", status="", mark="", pg=0.5):
    return TradePlayer(name, team, pos, slot=slot, status=status, value=value, mark=mark, pg=pg, team_id=10)


def theirs(name, value, team="BOS", pos=("SF",), status="", mark="", pg=0.4, team_name="Rival Squad"):
    return TradePlayer(name, team, pos, status=status, value=value, mark=mark, pg=pg, team_id=3, team_name=team_name)


def trade(give, get, after, dv):
    gain = sum(after) - sum(BASE)
    return Suggestion(give, get, BASE, after, gain, min(after) - min(BASE), dv, -dv, (27, 27, 25), (26, 28, 26))


GUARD = mine("Hurt Point Guard", -1.89, team="CHA", slot="IL", status="O")
WING = mine("Nickeil Alexander-Walkerson", 1.72, team="WSH", pos=("SF", "PF"))
ROWS = [
    trade(GUARD, theirs("Steady Combo Guard", -1.70, team="ATL", pos=("PG", "SG")), (29, 30, 27), 0.19),
    trade(GUARD, theirs("Long Name Forward Jr.", -1.83, team="HOU", pos=("PF", "C"), mark="pre"), (28, 29, 28), 0.07),
    trade(WING, theirs("Big Out Center", 1.62, team="UTAH", pos=("C",), status="GTD"), (27, 29, 30), -0.10),
    trade(WING, theirs("Even Guy", 1.72, team="NO", team_name="A Very Long Fantasy Team Name"), (28, 27, 27), 0.0),
]
RESULT = Suggestions(BASE, [], ROWS, 1595, 36, 12)


def render(result=RESULT, deadline=DEADLINE):
    return page.render(result, WEEKS, CFG, MADE, TODAY, deadline, READ)


def test_the_table_has_the_columns_of_the_suggestions_and_the_starts_now_row():
    html = render()
    table = html.split('<table class="sg desk lab-t" id="sg-desk">')[1].split("</table>")[0]
    heads = re.findall(r'<th scope="col"[^>]*>(.*?)</th>', table)
    assert heads == ["#", "You give", "You get", "Partner, est. starts", "Wk19", "Wk20", "Wk21", "Total", "You", "Them"]
    assert '<tr class="now"><th colspan="6" class="l" scope="row">Your starts now</th><td>28</td><td>27</td>' in table
    assert "<td>81</td>" in table
    assert table.count('<tr data-give="') == 4


def test_each_row_shows_both_players_the_partner_the_week_cells_and_both_value_changes():
    html = render()
    row = html.split('<tr data-give="Hurt Point Guard" data-k="0">')[1].split("</tr>")[0]
    assert (
        '<td class="rk"><button type="button" class="ld" aria-label="Load trade 1 in the builder">1</button></td>'
        in row
    )
    assert f'<td class="band" style="{site.band_style("CHA")}">CHA</td>' in row
    assert '<b>Hurt Point Guard</b><span class="status">IL</span><small>CHA · PG</small>' in row
    assert "Val <i>−1.89</i> · Pre <i>0.50</i>" in row
    assert "<b>Steady Combo Guard</b><small>ATL · PG/SG</small>" in row
    assert '<td class="pt">Rival Squad<small class="pe up" aria-hidden="true">' in row
    assert '<td class="wk up s1"><span aria-hidden="true"><b>29</b><small>+1</small>' in row
    assert '<span class="vh">29 starts, up 1 from 28</span>' in row
    assert '<td class="wk up t"><span aria-hidden="true"><b>86</b><small>+5</small>' in row
    assert '<td class="v s1">+0.19<small>+10%</small></td><td class="v">−0.19</td>' in row


def test_a_loss_a_no_change_a_status_and_the_pre_mark_show_in_the_rows():
    html = render()
    assert '<td class="wk dn s1"><span aria-hidden="true"><b>27</b><small>−1</small>' in html  # Wk19 of row 3
    assert '<td class="wk eq"><span aria-hidden="true"><b>27</b><small>±0</small>' in html
    assert '<span class="status">GTD</span>' in html
    assert 'Val <i>−1.83</i> <span class="pre">pre</span>' in html
    assert '<td class="v s1 minus">−0.10<small>−6%</small></td>' in html


def test_the_filter_row_has_a_chip_for_each_player_you_give_with_the_count():
    html = render()
    chips = html.split('<div class="filters" id="give-chips">')[1].split("</div>")[0]
    assert '<span class="label">You give (any)</span>' in chips
    assert re.findall(r'data-n="([^"]+)">', chips) == ["Hurt Point Guard", "Nickeil Alexander-Walkerson"]
    assert chips.count("<small>2 trades</small>") == 2
    assert html.index('id="give-chips"') < html.index('id="sg-desk"')
    assert '<p class="count" id="sg-count" aria-live="polite">4 of 4 trades</p>' in html


def test_the_line_under_the_table_and_the_read_time_of_the_cached_pages():
    html = render()
    assert html.index("<b>Starts count your 8 kept players.</b>") > html.index("</table>")
    assert "1,595 pairs, 36 in the value band, 12 with a gain." in html
    assert f'<p class="foot" id="sg-read">{READ}</p>' in html


def test_the_header_shows_the_deadline_the_starts_now_and_the_time_of_the_run():
    html = render()
    assert "<strong>Thu Mar 4</strong> · 126 days" in html
    assert "<strong>28 · 27 · 26</strong> = 81, Wk19–21" in html
    assert "<strong>Thu 10/29</strong> 09:30" in html
    assert "<strong>Not found</strong>" in render(deadline=None)


def test_with_no_suggestion_the_page_says_so_and_has_no_table():
    html = render(Suggestions(BASE, [], [], 10, 0, 0))
    assert '<div class="empty"><p>No trade raises your playoff starts.</p></div>' in html
    assert 'id="sg-desk"' not in html and 'id="give-chips"' not in html


def test_the_page_uses_the_site_shell_and_the_shared_table_style():
    html = render()
    assert site.TABLE_STYLE in html and site.MENU_SCRIPT in html
    assert '<nav class="lab-menu" id="lab-menu"' in html and '<a href="../">Roster</a>' in html
    assert "__" not in re.sub(r"<script.*?</script>", "", html, flags=re.S).replace("lab-t", "")


def test_the_page_escapes_the_names():
    evil = Suggestions(
        BASE, [], [trade(mine("A <b>", 1.0), theirs('B "q"', 1.0, team_name="<T>"), (29, 27, 26), 0)], 1, 1, 1
    )
    html = page.render(evil, WEEKS, CFG, MADE, TODAY, None, "")
    assert "A &lt;b&gt;" in html and "B &quot;q&quot;" in html and "&lt;T&gt;" in html


# The offer list (#170).

OFFER_CFG = {**CFG, "trade": {**CFG["trade"], "offer": ["Hurt Point Guard", "Nickeil Alexander-Walkerson", "Big Man"]}}
KEPT_LINE = "he is not in your 8 kept players, so a trade does not change your playoff starts."


def test_the_page_names_the_offered_players_and_the_reason_of_each_player_with_no_suggestion_above_the_table():
    result = replace(
        RESULT,
        offered=("Hurt Point Guard", "Nickeil Alexander-Walkerson", "Big Man"),
        missed=(("Big Man", KEPT_LINE),),
    )
    html = page.render(result, WEEKS, OFFER_CFG, MADE, TODAY, DEADLINE, READ)
    block = html.split('<div class="offer" id="offer">')[1].split("</div>")[0]
    assert "<p>Offered: Hurt Point Guard, Nickeil Alexander-Walkerson, Big Man (config [trade] offer).</p>" in block
    assert f"<li>No suggestion for Big Man: {KEPT_LINE}</li>" in block
    assert html.index('id="offer"') < html.index('id="give-chips"') < html.index('id="sg-desk"')
    chips = re.findall(r'class="chip" aria-pressed="false" data-n="([^"]+)"', html.split('id="give-chips"')[1])
    assert set(chips) <= set(result.offered)


def test_with_no_suggestion_the_page_still_shows_the_offered_players_and_the_reasons():
    result = Suggestions(BASE, [], [], 10, 0, 0, ("Big Man",), (("Big Man", KEPT_LINE),))
    html = page.render(result, WEEKS, OFFER_CFG, MADE, TODAY, DEADLINE, READ)
    assert f"<li>No suggestion for Big Man: {KEPT_LINE}</li>" in html
    assert '<div class="empty"><p>No trade raises your playoff starts.</p></div>' in html


def test_with_an_empty_offer_list_the_page_says_that_each_player_but_the_untouchable_is_offered():
    html = render()
    assert "<p>Offered: each player who is not untouchable (config [trade] offer is empty).</p>" in html
    assert 'id="offer-miss"' not in html


# The browser checks (#140): the filter, the fit and the contrast. They skip if Chromium is not installed.


@contextmanager
def browser_page(width=1280):
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Error as e:
            pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")
        try:
            yield browser.new_page(viewport={"width": width, "height": 900})
        finally:
            browser.close()


def test_a_chip_press_shows_only_the_trades_of_that_player_and_a_second_press_shows_all():
    with browser_page() as pg:
        pg.set_content(render())
        chip = pg.locator('#give-chips button[data-n="Nickeil Alexander-Walkerson"]')
        chip.click()
        assert chip.get_attribute("aria-pressed") == "true"
        assert pg.locator("#sg-desk tbody tr:visible").count() == 2
        assert pg.locator("#sg-count").text_content() == "2 of 4 trades"
        chip.click()
        assert pg.locator("#sg-desk tbody tr:visible").count() == 4
        assert pg.locator("#sg-count").text_content() == "4 of 4 trades"


# Each visible child box of a cell or a row item is inside its cell, and no cell scrolls sideways.
FIT = r"""width => {
  const bad = [], inside = (r, c) => r.left >= c.left - 0.5 && r.right <= c.right + 0.5
    && r.top >= c.top - 0.5 && r.bottom <= c.bottom + 0.5;
  document.querySelectorAll("#sg-desk th, #sg-desk td, #sg-mob li.ms > span, #sg-mob .nums > span, .mnow span")
    .forEach(c => {
      const box = c.getBoundingClientRect();
      if (!box.width) return;
      if (box.left < 0 || box.right > width) bad.push(`"${c.textContent}" is ${box.left} to ${box.right}`);
      if (c.scrollWidth > c.clientWidth + 1) bad.push(`"${c.textContent}" scrolls sideways`);
      c.querySelectorAll("*").forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width || r.height) && !inside(r, box) && !el.classList.contains("vh"))
          bad.push(`"${el.textContent}" leaves its cell`);
      });
    });
  return bad;
}"""


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_no_cell_overflows_its_cell_and_the_page_has_no_horizontal_scroll(width):
    with browser_page(width) as pg:
        pg.set_content(render())
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(FIT, width) == [], (width, theme)
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme)
        desk = pg.locator("#sg-desk").is_visible()
        assert desk == (width >= 1280), width  # the table at 940px of content and more, the row list below


# The contrast of each visible text against the solid background behind it (WCAG 2.2, as tests/adds/test_page.py).
CONTRAST = r"""() => {
  const rgb = s => { const p = s.match(/[\d.]+/g).map(Number);
    return s.startsWith("color(") ? [p[0] * 255, p[1] * 255, p[2] * 255, p[3] ?? 1] : [p[0], p[1], p[2], p[3] ?? 1]; };
  const over = (t, b) => [0, 1, 2].map(i => t[i] * t[3] + b[i] * (1 - t[3])).concat(1);
  const lum = c => c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const out = [], seen = new Set(), walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    const el = walk.currentNode.parentElement;
    if (!walk.currentNode.textContent.trim() || seen.has(el) || !el.getClientRects().length) continue;
    if (el.closest(".vh")) continue;
    seen.add(el);
    const chain = []; for (let e = el; e; e = e.parentElement) chain.unshift(e);
    let bg = [255, 255, 255, 1], alpha = 1;
    for (const e of chain) { const s = getComputedStyle(e); bg = over(rgb(s.backgroundColor), bg); alpha *= +s.opacity; }
    const s = getComputedStyle(el), fg = rgb(s.color); fg[3] *= alpha;
    const [a, b] = [lum(over(fg, bg)), lum(bg)], ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (ratio < 4.5) out.push(`${el.tagName}.${el.className} "${el.textContent.trim()}" ${ratio.toFixed(2)}`);
  }
  return out;
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_each_text_is_4_5_to_1_or_more_in_light_and_dark_mode_with_a_chip_pressed_and_not(width):
    with browser_page(width) as pg:
        pg.set_content(render())
        for state in ("default", "pressed"):
            if state == "pressed":
                pg.locator("#give-chips button").first.click()
            for theme in ("light", "dark"):
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                assert pg.evaluate(CONTRAST) == [], (width, theme, state)


def test_a_value_change_that_rounds_to_0_has_no_sign_and_a_team_code_of_4_letters_gets_the_small_band():
    assert page.change_text(0.004) == page.change_text(-0.004) == "±0.00"
    assert page.change_text(-0.1) == "−0.10"
    assert 'class="band b4"' in render() and ">UTAH</td>" in render()


def test_the_menu_shows_trades_after_adds_plan_as_the_current_page():
    """#151: the Trades tab of publish.TOOLS."""
    html = render()
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", html) == ["Roster", "Adds plan", "Free agents", "Trades"]
    assert '<a href="../trade/" aria-current="page">Trades</a>' in html


@pytest.mark.parametrize("width", [320, 390, 768])
def test_the_open_menu_drawer_has_4_5_to_1_text_and_no_horizontal_scroll(width):
    """#151: the phone drawer with the Trades tab, in light and dark mode. The tests above check the desktop panel."""
    with browser_page(width) as pg:
        pg.set_content(render())
        pg.locator(".lab-open").click()
        assert pg.locator("#lab-menu").get_attribute("class") == "lab-menu open"
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(CONTRAST) == [], (width, theme)
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme)


# The trade builder (#152) -------------------------------------------------------------------------------------------

SETTINGS = TradeSettings(frozenset({"star keeper"}), (0.95, 1.10), 8, 3, 20)
TEAMS = ("ATL", "BOS", "CHA", "HOU", "NO", "UTAH", "WSH", "DAL")
PLAYOFF = [
    roster_page.Day(
        date(2027, 3, 8) + timedelta(days=7 * w + d), name, d == 0, frozenset(TEAMS[d : d + 5]), frozenset()
    )
    for w, name in enumerate(WEEKS)
    for d in range(3)
]
MINE = [
    mine("Star Keeper", 3.06, team="DAL", pos=("SG", "SF", "PF"), slot="PF"),
    GUARD,
    WING,
    mine("Bench Center", -0.73, team="ATL", pos=("C",), slot="BN"),
    mine("Spare Guard", -1.42, team="BOS", pos=("PG", "SG"), slot="BN"),
]
OTHERS = [s.get for s in ROWS] + [
    theirs("Rival Low Man", -3.1, team="DAL", pos=("C",)),
    theirs("Rival Hurt Man", -2.0, team="NO", pos=("PF",), status="O"),
    replace(theirs("Other Team Star", 2.2, team="BOS"), team_id=7, team_name="Second Squad"),
]
BUILDER = page.builder_data(RESULT, MINE, OTHERS, PLAYOFF, ["PG", "SG", "SF", "PF", "C"], WEEKS, SETTINGS)


def render_builder():
    return page.render(RESULT, WEEKS, CFG, MADE, TODAY, DEADLINE, READ, BUILDER)


def test_the_builder_sits_under_the_suggestions_with_the_partner_pick_and_both_tables():
    html = render_builder()
    assert html.index('id="sg-read"') < html.index('<section id="builder"') < html.index("</main>")
    assert '<h2 id="builder-h">Trade builder</h2>' in html
    options = re.findall(r'<option value="(\d+)">([^<]+)</option>', html)
    assert options == [("3", "Rival Squad"), ("7", "Second Squad")]
    for part in ('id="pk-give"', 'id="pk-get"', 'id="open-me" hidden', 'id="drop" hidden', 'id="res"'):
        assert part in html
    assert 'id="builder"' not in render()  # a page with no builder data has no builder


def test_the_builder_data_has_both_rosters_the_suggestions_and_the_engine_data():
    me = {p["name"]: p for p in BUILDER["me"]}
    assert me["Star Keeper"]["untouchable"] and not me[WING.name]["untouchable"]
    assert me[GUARD.name]["il"] and me[GUARD.name]["val"] == -1.89 and me[GUARD.name]["pg"] == 0.5
    assert [len(t["roster"]) for t in BUILDER["teams"]] == [6, 1]
    first = BUILDER["sugg"][0]
    assert first == {"team": 3, "give": [me[GUARD.name]["id"]], "get": [BUILDER["teams"][0]["roster"][0]["id"]]}
    assert BUILDER["engine"]["util"] == 1 and BUILDER["engine"]["kept"] == 8 and len(BUILDER["engine"]["days"]) == 9
    html = render_builder()
    assert '<script type="application/json" id="trade-data">' in html
    assert "const TeamBuilder = " in html and "const TradeBuilder = " in html


def test_the_builder_allows_a_player_who_is_not_on_the_offer_list():
    """#170: the offer list limits only the suggestions. The builder blocks only the untouchable players."""
    settings = replace(SETTINGS, offer=(GUARD.name,))
    data = page.builder_data(RESULT, MINE, OTHERS, PLAYOFF, ["PG", "SG", "SF", "PF", "C"], WEEKS, settings)
    assert [p["name"] for p in data["me"] if not p["untouchable"]] == [p.name for p in MINE[1:]]


def test_the_partner_starts_show_as_an_estimate_in_the_table_and_the_row_list():
    html = render()
    row = html.split('<tr data-give="Hurt Point Guard" data-k="0">')[1].split("</tr>")[0]
    assert (
        '<small class="pe up" aria-hidden="true"><span>Est. 27·27·25 = 79</span>'
        "<span>→ 26·28·26 = <b>80</b> +1</span></small>"
    ) in row
    assert "Partner starts, an estimate: 80, up 1 from 79. Weeks: 27 · 27 · 25 before, 26 · 28 · 26 after." in row
    assert '<span class="pst"><em>Them, est.</em>27 · 27 · 25 = 79 → 26 · 28 · 26 = 80 <b>+1</b></span>' in html


def test_the_page_data_escapes_a_closing_script_tag():
    evil = replace(OTHERS[-1], name="</script><b>x")
    data = page.builder_data(RESULT, MINE, OTHERS[:-1] + [evil], PLAYOFF, ["PG"], WEEKS, SETTINGS)
    html = page.render(RESULT, WEEKS, CFG, MADE, TODAY, DEADLINE, READ, data)
    assert "<\\/script><b>x" in html and "</script><b>x" not in html


def test_a_click_on_a_suggestion_row_loads_it_into_the_builder():
    with browser_page() as pg:
        pg.set_content(render_builder())
        assert pg.locator("#res").text_content() == "Pick at least 1 player to give and 1 player to get."
        pg.locator('#sg-desk tr[data-k="1"] td.pt').click()
        assert pg.locator("#partner").input_value() == "3"
        assert pg.locator(f'#pk-give input[aria-label="Give {GUARD.name}"]').is_checked()
        assert pg.locator('#pk-get input[aria-label="Get Long Name Forward Jr."]').is_checked()
        assert pg.locator("#pk-give input:checked, #pk-get input:checked").count() == 2
        assert pg.locator('#sg-desk tr[data-k="1"]').get_attribute("aria-current") == "true"
        assert pg.locator("#live").text_content() == "Trade 2 is in the builder."
        assert pg.locator("#rt tbody tr").count() == 4
        assert "After the trade, est." in pg.locator("#rt").text_content()
        assert pg.locator("#open-me").is_hidden() and pg.locator("#drop").is_hidden()


def test_a_1_for_2_trade_shows_the_open_spot_line_and_the_partner_drop():
    with browser_page() as pg:
        pg.set_content(render_builder())
        pg.locator('#sg-desk tr[data-k="0"] button.ld').click()
        pg.locator('#pk-give input[aria-label="Give Bench Center"]').check()
        assert pg.locator("#open-me").text_content() == "1 open roster spot: a free agent can fill it."
        assert pg.locator("#sg-desk tr[aria-current]").count() == 0  # a changed trade is not the suggestion
        # His lowest value player that he keeps: Rival Low Man (−3.10), not the player that he gives.
        assert pg.locator("#drop-them").text_content().startswith("Rival Squad drops Rival Low Man")
        assert pg.locator("#drop").is_hidden()


def test_a_2_for_1_trade_asks_for_your_drop_and_the_partner_gets_an_open_spot():
    with browser_page() as pg:
        pg.set_content(render_builder())
        pg.locator('#sg-desk tr[data-k="0"] button.ld').click()
        pg.locator('#pk-get input[aria-label="Get Big Out Center"]').check()
        assert pg.locator("#drop").is_visible()
        assert "You get 1 more player than you give. Pick your drop." in pg.locator("#drop-chips").text_content()
        pressed = pg.locator('#drop-chips button[aria-pressed="true"]')
        assert pressed.count() == 1 and pressed.text_content().startswith("Spare Guard")  # the lowest value first
        assert pg.locator('#drop-chips button:has-text("Star Keeper")').count() == 0  # never the untouchable
        pg.locator('#drop-chips button:has-text("Bench Center")').click()
        assert pg.locator('#drop-chips button[aria-pressed="true"]').text_content().startswith("Bench Center")
        assert "You drop Bench Center" in pg.locator("#res").text_content()
        assert pg.locator("#open-them").text_content() == "Rival Squad: 1 open roster spot: a free agent can fill it."


def test_a_new_partner_clears_the_players_you_get():
    with browser_page() as pg:
        pg.set_content(render_builder())
        pg.locator('#sg-desk tr[data-k="0"] button.ld').click()
        pg.locator("#partner").select_option("7")
        assert pg.locator("#pk-get tbody tr").count() == 1
        assert pg.locator("#pk-get input:checked").count() == 0
        assert pg.locator("#get-h").text_content() == "You get from Second Squad"


def builder_states(pg):
    """Put the builder in each state in turn: default, selected (a loaded row and a 2-for-1), hover and focus-visible.
    Yield the name of each state."""
    yield "default"
    pg.locator('[data-k="0"] button.ld:visible').first.click()
    pg.locator('#pk-get input[aria-label="Get Big Out Center"]').check()
    yield "selected"
    pg.locator('[data-k="1"]:visible').first.hover()
    pg.locator("#pk-get tbody tr").nth(3).hover()
    yield "hover"
    pg.locator("#clear").focus()
    pg.keyboard.press("Tab")
    pg.keyboard.press("Tab")
    yield "focus-visible"


BUILDER_FIT = FIT.replace(
    '.mnow span")',
    '.mnow span, #builder th, #builder td, #builder .line, #builder .chip, #builder select")',
)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_no_builder_cell_overflows_and_the_page_has_no_horizontal_scroll_in_each_state(width):
    assert BUILDER_FIT != FIT
    with browser_page(width) as pg:
        pg.set_content(render_builder())
        for state in builder_states(pg):
            for theme in ("light", "dark"):
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                assert pg.evaluate(BUILDER_FIT, width) == [], (width, theme, state)
                assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme, state)


@pytest.mark.parametrize("width", [390, 1280])
def test_each_builder_text_is_4_5_to_1_or_more_in_each_state_and_theme(width):
    with browser_page(width) as pg:
        pg.set_content(render_builder())
        for state in builder_states(pg):
            for theme in ("light", "dark"):
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                assert pg.evaluate(CONTRAST) == [], (width, theme, state)


# The edge states of #153: the page after the trade deadline and the warning lines.

PAST = date(2026, 3, 2)
WARNINGS = [
    'Warning: no trade deadline. The league settings page has no "Trade End Date".',
    "Warning: these players have no rank and go last in the lineup order: "
    + ", ".join(f"Very Long Unmatched Player Name{n}" for n in range(12))
    + ".",
]


def test_the_deadline_page_has_the_header_with_the_time_of_the_run_and_the_deadline_line():
    html = page.render_deadline(CFG, MADE, PAST)
    assert "<strong>Mon Mar 2</strong> · passed" in html
    assert "<strong>Thu 10/29</strong> 09:30" in html
    line = "The trade deadline was Monday, March 2, 2026. Yahoo accepts no more trades this season."
    assert f'<div class="empty" id="deadline"><p>{line}</p></div>' in html
    assert 'id="sugg"' not in html and 'id="builder"' not in html
    assert 'aria-current="page">Trades</a>' in html
    assert "__" not in re.sub(r"<script.*?</script>", "", html, flags=re.S).replace("lab-t", "")


def test_the_warning_lines_show_under_the_header_and_a_page_with_no_warning_has_no_block():
    html = page.render(RESULT, WEEKS, CFG, MADE, TODAY, None, READ, None, WARNINGS)
    assert html.index("</header>") < html.index('<ul class="warn" id="warnings"') < html.index('id="sugg"')
    assert "<li>Warning: no trade deadline. The league settings page has no &quot;Trade End Date&quot;.</li>" in html
    assert 'class="warn"' not in render()


def edge_pages():
    return {
        "deadline": page.render_deadline(CFG, MADE, PAST),
        "warnings": page.render(RESULT, WEEKS, CFG, MADE, TODAY, None, READ, None, WARNINGS),
        "offer": page.render(
            replace(RESULT, offered=("Hurt Point Guard",), missed=(("Nickeil Alexander-Walkerson", KEPT_LINE),)),
            WEEKS,
            OFFER_CFG,
            MADE,
            TODAY,
            DEADLINE,
            READ,
        ),
    }


EDGE_FIT = r"""width => {
  const bad = [];
  document.querySelectorAll(".head, .meta div, #warnings li, #deadline p, #offer p, #offer li").forEach(c => {
    const box = c.getBoundingClientRect();
    if (box.left < 0 || box.right > width) bad.push(`"${c.textContent}" is ${box.left} to ${box.right}`);
    if (c.scrollWidth > c.clientWidth + 1) bad.push(`"${c.textContent}" scrolls sideways`);
  });
  return bad;
}"""


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_the_deadline_page_and_the_warning_lines_fit_with_no_horizontal_scroll(width):
    with browser_page(width) as pg:
        for name, html in edge_pages().items():
            pg.set_content(html)
            for theme in ("light", "dark"):
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                assert pg.evaluate(EDGE_FIT, width) == [], (name, width, theme)
                assert pg.evaluate("document.documentElement.scrollWidth") <= width, (name, width, theme)
                if name == "warnings":
                    assert pg.evaluate(FIT, width) == [], (name, width, theme)


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_the_deadline_page_and_the_warning_lines_are_4_5_to_1_or_more_in_light_and_dark_mode(width):
    with browser_page(width) as pg:
        for name, html in edge_pages().items():
            pg.set_content(html)
            for theme in ("light", "dark"):
                pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
                assert pg.evaluate(CONTRAST) == [], (name, width, theme)


def test_the_trade_pages_have_the_icon_links_and_the_preview_tags():
    """#166: the head of the Trades page and of the deadline page has publish.page_meta()."""
    assert site.page_meta("trade", "Trades") in render()
    assert site.page_meta("trade", "Trades") in page.render_deadline(CFG, MADE, PAST)
