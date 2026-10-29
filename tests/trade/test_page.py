import re
from contextlib import contextmanager
from datetime import date, datetime

import pytest

from fantasyhoops.core import publish as site
from fantasyhoops.trade import page
from fantasyhoops.trade.suggest import Suggestion, Suggestions, TradePlayer

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
    assert heads == ["#", "You give", "You get", "Partner", "Wk19", "Wk20", "Wk21", "Total", "You", "Them"]
    assert '<tr class="now"><th colspan="6" class="l" scope="row">Your starts now</th><td>28</td><td>27</td>' in table
    assert "<td>81</td>" in table
    assert table.count('<tr data-give="') == 4


def test_each_row_shows_both_players_the_partner_the_week_cells_and_both_value_changes():
    html = render()
    row = html.split('<tr data-give="Hurt Point Guard">')[1].split("</tr>")[0]
    assert '<td class="rk">1</td>' in row
    assert f'<td class="band" style="{site.band_style("CHA")}">CHA</td>' in row
    assert '<b>Hurt Point Guard</b><span class="status">IL</span><small>CHA · PG</small>' in row
    assert "Val <i>−1.89</i> · Pre <i>0.50</i>" in row
    assert "<b>Steady Combo Guard</b><small>ATL · PG/SG</small>" in row
    assert '<td class="pt">Rival Squad</td>' in row
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
