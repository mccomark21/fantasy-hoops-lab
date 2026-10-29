import base64
import copy
import re
from datetime import date

import pytest

from fantasyhoops.core import common, home, publish, tokens
from tests.adds.test_page import CONTRAST
from tests.core.test_roster import browser_page

CFG = common.load_config()


def text(html):
    """The visible text of the <main> of a page, with the tags removed and the spaces joined."""
    main = html.split('<main class="lab-main hm">')[1].split("</main>")[0]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main))


def test_the_home_page_names_no_league_platform_and_no_data_source():
    """Owner change of 2026-10-29 (#172): no "Yahoo" and no "ESPN" in the HTML of the Home page."""
    assert not re.findall(r"yahoo|espn", home.render(CFG), flags=re.I)
    assert "the league site" in text(home.render(CFG)) and "public NBA stats" in text(home.render(CFG))


def test_the_home_page_has_the_sections_of_the_sample_in_order():
    html = home.render(CFG)
    heads = ["<h1>Fantasy Hoops Lab</h1>", ">The pages</h2>", ">About this project</h2>", ">How it works</h2>"]
    places = [html.index(h) for h in heads] + [html.index('<footer class="hm-foot">')]
    assert places == sorted(places)
    assert re.findall(r'<h3><a href="([^"]+)">([^<]+)<svg', html) == [
        ("roster/", "Roster"),
        ("adds/", "Adds plan"),
        ("free-agents/", "Free agents"),
        ("trade/", "Trades"),
    ]
    assert html.count("<figcaption>Example") == 4
    assert html.count("<li><b>") == 3  # the 3 steps of How it works


def test_the_home_page_uses_the_site_shell_with_home_current():
    html = home.render(CFG)
    assert html.index('<body class="lab">') < html.index('<nav class="lab-menu"') < html.index('<main class="lab-main')
    assert '<a href="./" aria-current="page">Home</a>' in html and '<a href="roster/">Roster</a>' in html
    assert publish.page_meta("home", "Fantasy Hoops Lab") in html and publish.TABLE_STYLE in html
    assert html.rstrip().endswith(f"{publish.MENU_SCRIPT}\n</body>\n</html>")
    assert not re.findall(r"__[A-Z0-9_]+__", html)


def test_the_league_facts_come_from_the_config():
    page = text(home.render(CFG))
    assert "Head-to-head, 14 teams" in page and "Auction, $200 budget" in page
    assert "PG, SG, SF, PF, C, Util and 4 bench" in page and "5 each week" in page
    assert "Weeks 19 to 21" in page and "each of the 21 playoff days" in page
    assert "How to use the 5 adds of this fantasy week." in page and "my 8 kept players" in page
    assert "2026–27 season" in page and "punts 3 of them: FG%, FT% and TO" in page
    cfg = copy.deepcopy(CFG)
    cfg["league"].update(teams=12, adds=4, roster_spots=11)
    cfg["auction"]["budget"] = 300
    cfg["trade"]["kept"] = 9
    cfg["playoffs"]["weeks"] = [{"name": "wk20", "start": date(2027, 3, 15), "end": date(2027, 3, 24)}]
    page = text(home.render(cfg))
    assert "Head-to-head, 12 teams" in page and "Auction, $300 budget" in page and "Util and 5 bench" in page
    assert "4 each week" in page and "Weeks 20 to 20" in page and "each of the 10 playoff days" in page
    assert "my 9 kept players" in page


def test_the_page_css_has_no_colors_of_its_own():
    """The page CSS uses only the tokens of core/tokens.py. The example team bands use tokens.TEAM_COLORS."""
    style = re.sub(r"/\*.*?\*/", "", home.PAGE_STYLE, flags=re.S)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", style)
    for team in home.EXAMPLE_TEAMS:
        assert f"--team:{tokens.TEAM_COLORS[team]};" in home.render(CFG)


def test_write_puts_the_page_in_output_home(tmp_path):
    path = home.write(home.render(CFG))
    assert path == common.OUT / "home" / "index.html" and path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (path.parent / "fonts" / tokens.FONT.name).exists()


# Each element of <main> stays inside the page width, and no text box is wider than its element.
FIT = r"""width => {
  const bad = [];
  document.querySelectorAll("main *").forEach(el => {
    if (!el.getClientRects().length) return;
    const r = el.getBoundingClientRect();
    if (r.left < -0.5 || r.right > width + 0.5) bad.push(`${el.tagName}.${el.className} ${r.left}-${r.right}`);
    const s = getComputedStyle(el);
    if (s.overflowX === "visible" && el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && s.display !== "inline")
      bad.push(`${el.tagName}.${el.className} scrolls ${el.scrollWidth}/${el.clientWidth}`);
  });
  return bad;
}"""


def with_font(html):
    """The page with the site font inline, as on the site. set_content() has no fonts/ folder next to the page.

    With no font, each machine uses its own fallback font, and the text widths change from machine to machine.
    """
    font = base64.b64encode(tokens.FONT.read_bytes()).decode()
    return html.replace(f"url({tokens.FONT_HREF})", f"url(data:font/woff2;base64,{font})")


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_the_home_page_fits_and_each_text_is_4_5_to_1_or_more_in_light_and_dark_mode(width):
    """#140 page tests for the Home page (#172): fit, no sideways scroll and contrast, in both themes."""
    with browser_page(width) as pg:
        pg.set_content(with_font(home.render(CFG)))
        pg.evaluate("document.fonts.ready")
        assert pg.evaluate("document.fonts.check('900 20px Archivo')")
        for theme in ("light", "dark"):
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            assert pg.evaluate(FIT, width) == [], (width, theme)
            assert pg.evaluate("document.documentElement.scrollWidth") <= width, (width, theme)
            assert pg.evaluate(CONTRAST) == [], (width, theme)
