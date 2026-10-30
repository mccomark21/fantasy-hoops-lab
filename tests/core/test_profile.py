import re
from pathlib import Path

from fantasyhoops.core import chart, profile
from fantasyhoops.core.publish import shell

CFG = {"league": {"teams": 14}}
NAMES = ["Ace Bailey", "Karl-Anthony Towns", "Nikola Jokić", "Jabari Smith Jr.", "D'Angelo Russell"]


def page(names=NAMES, chart_css=False):
    """A page with a name link for each of names and the player modal."""
    links = "".join(f"<p><b>{profile.name_link(n)}</b></p>" for n in names)
    css = "<style>__CHART_CSS__</style>" if chart_css else ""
    template = f"<html><head><meta charset=\"utf-8\"><title>Test</title>__HEAD__{css}</head><body class='lab'>__MENU__"
    return shell(
        template + f"<main class='lab-main'>{links}</main>__PLAYER_MODAL__\n__SCRIPT__</body></html>", "roster", CFG
    )


def test_the_slug_is_the_name_key_with_dashes():
    assert [profile.slug(n) for n in NAMES] == [
        "ace-bailey",
        "karl-anthony-towns",
        "nikola-jokic",
        "jabari-smith",
        "dangelo-russell",
    ]
    assert profile.slug("日本") == ""


def test_a_name_link_goes_to_the_player_hash_and_keeps_the_name_as_text():
    assert profile.name_link("Ace Bailey") == (
        '<a class="lab-pname" href="#player=ace-bailey" data-player="ace-bailey">Ace Bailey</a>'
    )
    assert profile.name_link("D'Angelo <Russell>").endswith(">D&#x27;Angelo &lt;Russell&gt;</a>")
    assert profile.name_link("日本") == "日本"  # no slug: no link


def test_the_shell_puts_the_modal_only_where_the_template_asks_for_it():
    assert shell("<body>__PLAYER_MODAL__</body>", "roster", CFG) == f"<body>{profile.modal()}</body>"
    assert "lab-pmodal" not in shell("<body></body>", "roster", CFG)
    # A page with the chart style gets it once.
    with_chart = shell("<style>__CHART_CSS__</style>__PLAYER_MODAL__", "players", CFG)
    assert with_chart.count(chart.CHART_STYLE) == 1
    assert shell("__PLAYER_MODAL__", "roster", CFG).count(chart.CHART_STYLE) == 1


def test_the_modal_reads_the_shared_player_file_and_has_the_card_and_the_tooltip_in_the_dialog():
    text = profile.modal()
    assert 'fetch("../players/players.json")' in text
    dialog = text.split("</dialog>")[0]
    assert 'id="lab-pm-card"' in dialog and 'id="lab-tt" role="tooltip"' in dialog  # build note 3
    assert '<a class="lab-pm-full" id="lab-pm-full" href="../players/">Open full profile</a>' in dialog
    for key, title, empty in profile.QUADRANTS:
        assert f'["{key}", "{title}", "{empty}"]' in text
    assert f"<b>{profile.NO_SIGNALS}</b>" in text and "slice(0, MAX)" in text and "const MAX = 3;" in text


def test_each_card_rule_has_the_card_scope():
    """Build note 2: the h1, h2, p and * rules of a page must not change the card, and the card must not change the page."""
    css = re.sub(r"/\*.*?\*/", "", profile.CARD_STYLE, flags=re.S)
    selectors = [chunk.split("{")[-2] for chunk in css.split("}") if "{" in chunk]
    assert len(selectors) > 30
    for sel in ",".join(selectors).split(","):
        assert sel.strip().startswith(".lab-card"), sel


def test_no_page_keeps_its_own_copy_of_the_modal():
    """#186: core/profile.py is the one source of the modal. The Players page uses the card of the modal script."""
    src = Path(profile.__file__).parents[1]
    users = [p.relative_to(src).as_posix() for p in src.rglob("*.py") if "lab-pmodal" in p.read_text(encoding="utf-8")]
    assert users == ["core/profile.py"]
    pages = [
        p.relative_to(src).as_posix() for p in src.rglob("*.py") if "__PLAYER_MODAL__" in p.read_text(encoding="utf-8")
    ]
    assert sorted(pages) == [
        "adds/page.py",
        "core/profile.py",
        "core/publish.py",
        "core/roster.py",
        "players/page.py",
        "trade/page.py",
    ]


def test_the_page_with_the_modal_passes_the_chart_style_check():
    assert chart.style_problems(page()) == []


def test_a_name_opens_the_modal_and_the_hash_back_esc_close_and_the_backdrop_close_it(modal_site):
    modal_site.open("roster", page())
    modal_site.check_modal()


def test_the_modal_shows_the_header_and_no_signals_text_and_at_most_3_signal_chips(modal_site):
    sig = {"kind": "Range exit", "quadrant": "role", "up": False, "text": "Minutes above the range"}
    records = [
        {
            "slug": "ace-bailey",
            "name": "Ace Bailey",
            "team": "UTAH",
            "pos": "SF/PF",
            "owner": "Lamb Chops",
            "mine": True,
            "val": 0.52,
            "games": 5,
            "signals": [sig] * 4,
        },
        {
            "slug": "nikola-jokic",
            "name": "Nikola Jokić",
            "team": "",
            "pos": "",
            "owner": None,
            "mine": False,
            "val": None,
            "games": 0,
            "signals": [],
        },
    ]
    pg = modal_site.open("roster", page(), records=records, hash="#player=ace-bailey")
    pg.locator("#lab-pm-name").wait_for()
    head = pg.locator("#lab-pmodal .lc-head")
    assert head.locator(".lc-band").inner_text() == "UTAH"
    assert head.locator(".lc-sub").inner_text() == "SF/PF · Lamb Chops (you)"
    assert head.locator(".lc-kv dd").inner_text().startswith("+0.52")
    chips = head.locator(".lc-sigs a")
    assert chips.count() == 3  # 4 signals, 3 chips
    chips.first.click()  # a chip goes to its quadrant and keeps the modal open
    assert pg.evaluate("document.activeElement.id") == "lab-pm-h-role"
    assert pg.evaluate("location.hash") == "#player=ace-bailey"
    pg.goto(modal_site.url + "roster/#player=nikola-jokic")
    pg.locator("#lab-pm-name").wait_for()
    assert head.locator(".lc-sigs").inner_text() == profile.NO_SIGNALS
    assert head.locator(".lc-sub").inner_text() == "– · FA" and head.locator(".lc-kv dd").inner_text().startswith("–")
    assert [t.text_content() for t in pg.locator("#lab-pmodal .lc-q h3").all()] == [
        "Role",
        "Categories",
        "Value",
        "Comps",
    ]
    pg.goto(modal_site.url + "roster/#player=no-such-player")
    pg.locator("#lab-pm-card .lc-msg").wait_for()
    assert "not in the player file" in pg.locator("#lab-pm-card").inner_text()


def test_below_800px_the_modal_is_a_full_screen_sheet_with_stacked_quadrants(modal_site):
    modal_site.page.set_viewport_size({"width": 390, "height": 844})
    pg = modal_site.open("roster", page(), hash="#player=ace-bailey")
    pg.locator("#lab-pm-name").wait_for()
    box = pg.locator("#lab-pmodal").bounding_box()
    assert (box["x"], box["y"], box["width"], box["height"]) == (0, 0, 390, 844)
    quads = [q.bounding_box() for q in pg.locator("#lab-pmodal .lc-q").all()]
    assert len({round(q["x"]) for q in quads}) == 1 and [q["y"] for q in quads] == sorted(q["y"] for q in quads)


def test_on_close_the_focus_goes_to_the_name_that_a_page_script_drew_again(modal_site):
    """Build note 1: a page script can replace the names while the modal is open. The focus finds the new name."""
    pg = modal_site.open("roster", page())
    pg.locator('a.lab-pname[data-player="karl-anthony-towns"]').click()
    pg.locator("#lab-pm-name").wait_for()
    pg.evaluate(
        "document.querySelectorAll('main a.lab-pname').forEach(a => { const b = a.cloneNode(true);"
        " b.dataset.redrawn = '1'; a.replaceWith(b); })"
    )
    pg.keyboard.press("Escape")
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    assert pg.evaluate("[document.activeElement.dataset.player, document.activeElement.dataset.redrawn]") == [
        "karl-anthony-towns",
        "1",
    ]
